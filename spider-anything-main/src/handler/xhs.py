import time
import uuid
import random
import typing as t
import asyncio
import traceback
from datetime import datetime

import httpx
import asyncpg
import aiofiles
from loguru import logger
from tortoise import Tortoise
from playwright.async_api import Page

from src.utils import call_feishu_notion, convert_str_cookie_to_dict
from src.const import ROOT_PATH, XHS_DATA_PATH, TEST_DATA_PATH
from src.settings import settings
from src.model.xhs import XhsNotes, XhsNoteComments
from src.schema.xhs import XhsNote, XhsNoteComment, XhsSearchParams
from src.core.browser import Browser


# 配置 loguru 日志
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    format="<green>{time:MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="DEBUG" if settings.debug else "INFO",
    colorize=True
)
logger.add(
    sink=f"{ROOT_PATH}/logs/xhs_error_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="1 day",
    retention="30 days",
    compression="zip"
)


def get_video_url_arr(note_item: t.Dict) -> t.List:
    """ 获取视频url数组 """
    logger.debug(f"note_item: {note_item}")
    if note_item.get("type") != "video":
        return []

    video_arr = []
    origin_video_key = note_item.get("video", {}).get("consumer", {}).get("originVideoKey", None)

    # 降级有水印
    if origin_video_key == "":
        videos = note_item.get("video").get("media").get("stream").get("h264")
        if type(videos).__name__ == "list":
            video_arr = [v.get("masterUrl") for v in videos]
    else:
        video_arr = [f"http://sns-video-bd.xhscdn.com/{origin_video_key}"]

    logger.debug(f"video_arr: {video_arr}")
    return video_arr


async def get_xhs_note(keyword: str, note_item: t.Dict) -> XhsNote:
    """ 获取小红书笔记内容 """
    logger.debug(f"note_item: {note_item}")

    note_id = note_item.get("noteId")
    tag_list: t.List[t.Dict] = note_item.get("tagList", [])
    user_info = note_item.get("user", {})
    image_list: t.List[t.Dict] = note_item.get("imageList", [])
    interact_info = note_item.get("interactInfo", {})

    for img in image_list:
        if img.get("urlDefault") != "":
            img.update({"url": img.get("urlDefault")})

    try:
        video_url = ",".join(get_video_url_arr(note_item))
    except Exception:
        video_url = ""

    xhs_note_item = {
        "note_id": note_id,
        "type": note_item.get("type"),
        "title": note_item.get("title", note_item.get("desc")[:255] if len(note_item.get("desc", "")) > 255 else note_item.get("desc")),
        "desc": note_item.get("desc"),
        "time": note_item.get("time"),
        "video_url": video_url,
        "user_id": user_info.get("userId"),
        "nickname": user_info.get("nickname"),
        "avatar": user_info.get("avatar"),
        "liked_count": interact_info.get("likedCount"),
        "collected_count": interact_info.get("collectedCount"),
        "comment_count": interact_info.get("commentCount"),
        "share_count": interact_info.get("shareCount"),
        "ip_location": note_item.get("ipLocation"),
        "image_list": ",".join([img.get("url", "") for img in image_list]),
        "tag_list": ",".join([tag.get("name", "") for tag in tag_list if tag.get("type") == "topic"]),
        "note_url": f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note_item.get("xsecToken")}&xsec_source=pc_search",
        "xsec_token": note_item.get("xsecToken"),
        "source_keyword": keyword,
        "add_ts": int(time.time() * 1000),
        "last_modify_ts": int(time.time() * 1000),
        "last_update_time": note_item.get("lastUpdateTime"),
        "extra": note_item,
    }

    logger.debug(f"xhs_note_item: {xhs_note_item}")
    return XhsNote.model_validate(xhs_note_item)


async def get_xhs_note_comment(note_id: str, comment_item: t.Dict) -> XhsNoteComment:
    logger.debug(f"comment_item: {comment_item}")

    comment_id = comment_item.get("id")
    user_info = comment_item.get("userInfo", {})
    target_comment = comment_item.get("targetComment", {})
    comment_pictures = [item.get("urlDefault", "") for item in comment_item.get("pictures", [])]

    xhs_note_comment_item = {
        "note_id": note_id,
        "comment_id": comment_id,
        "content": comment_item.get("content"),
        "avatar": user_info.get("image"),
        "user_id": user_info.get("userId"),
        "nickname": user_info.get("nickname"),
        "picture_list": ",".join(comment_pictures), 
        "like_count": comment_item.get("likeCount"),
        "ip_location": comment_item.get("ipLocation"),
        "sub_comment_count": comment_item.get("subCommentCount"),
        "parent_comment_id": target_comment.get("id"),
        "create_time": comment_item.get("createTime"),
        "add_ts": int(time.time() * 1000),
        "last_modify_ts": int(time.time() * 1000),
        "extra": comment_item,
    }

    logger.debug(f"xhs_note_comment_item: {xhs_note_comment_item}")
    return XhsNoteComment.model_validate(xhs_note_comment_item)


class XhsHandler:

    def __init__(self, browser: Browser, home_url: str = "https://www.xiaohongshu.com"):
        self.browser = browser
        self.home_url = home_url
        self.home_page: Page
        self.is_init = False
        logger.info("Created XHS handler instance successfully, waiting for initialize...")

    async def db_init(self):
        logger.info("Start initialize database")
        database = "test" if settings.test else "xhs"
        try:
            # 尝试连接到数据库
            conn = await asyncpg.connect(
                host=settings.pgsql.host,
                port=settings.pgsql.port,
                user=settings.pgsql.user,
                password=settings.pgsql.password,
                database=database
            )
            await conn.close()
            logger.info(f"Database {database} already exists")
        except asyncpg.InvalidCatalogNameError:
            # 数据库不存在，创建它
            logger.info(f"Database {database} does not exists, creating...")
            # 连接到默认的postgres数据库来创建新数据库
            conn = await asyncpg.connect(
                host=settings.pgsql.host,
                port=settings.pgsql.port,
                user=settings.pgsql.user,
                password=settings.pgsql.password,
                database="postgres"
            )
            await conn.execute(f'CREATE DATABASE "{database}"')
            await conn.close()
            logger.info(f"Database {database} created successfully")
        except Exception as e:
            logger.error(f"Error checking/creating database: {e}")
            raise
        config = {
            "connections": {
                "default": {
                    "engine": "tortoise.backends.asyncpg",
                    "credentials": {
                        "host": settings.pgsql.host,
                        "port": settings.pgsql.port,
                        "user": settings.pgsql.user,
                        "password": settings.pgsql.password,
                        "database": database,
                        "minsize": 1,
                        "maxsize": 1024,
                    },
                }
            },
            "apps": {
                "models": {
                    "models": [
                        "src.model.xhs",
                    ],
                    "default_connection": "default"
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai"
        }
        await Tortoise.init(config)
        await Tortoise.generate_schemas(safe=True)
        logger.info("Database initialized successfully")

    async def init(self):
        logger.info("Start initialize handler")
        await self.db_init()
        await self.browser.context.add_init_script(path=str(ROOT_PATH / "src/js/stealth.min.js"))
        await self.browser.context.add_cookies(
            [
                {
                    "name": "webId",
                    "value": uuid.uuid4().hex,
                    "domain": ".xiaohongshu.com",
                    "path": "/",
                }
            ]
        )
        logger.info("Open home page")
        self.home_page = await self.browser.context.new_page()
        await self.home_page.goto(self.home_url, timeout=60000, wait_until="domcontentloaded")
        await self.home_page.wait_for_selector(".main-container", timeout=60000)
        await asyncio.sleep(3)
        await self.login()
        self.is_init = True
        logger.info("Handler initialized successfully")

    async def login(self):
        """ 检查登录状态并使用设定的方式进行登录 """
        logger.info("Check login state...")
        state = await self.home_page.evaluate("() => window.__INITIAL_STATE__")
        is_login = state.get("user", {}).get("isLogining", {}).get("_value", False)
        if not is_login:
            logger.info(f"User don't login, use {settings.xhs.login_type} login")
            if settings.xhs.login_type == "qrcode":
                await self.login_by_qrcode()
            elif settings.xhs.login_type == "phone":
                await self.login_by_mobile()
            elif settings.xhs.login_type == "cookie":
                await self.login_by_cookie()
        else:
            logger.info("User is logined")

    async def login_by_mobile(self):
        pass

    async def login_by_qrcode(self):
        pass

    async def login_by_cookie(self):
        """ 使用 Cookie 登录 """
        logger.info("Start login by cookie")
        for key, value in convert_str_cookie_to_dict(settings.xhs.cookie).items():
            if key != "web_session":
                continue
            await self.browser.context.add_cookies([{
                "name": key,
                "value": value,
                "domain": ".xiaohongshu.com",
                "path": "/"
            }])
        await self.home_page.reload()
        await asyncio.sleep(2)
        logger.info("Login successfully")

    async def handle_search(self, keyword: str, params: XhsSearchParams):
        """ 通过关键词搜索笔记 """
        logger.info(f"Start search by keyword: {keyword}, use params: {params.format_params}")
        
        # 使用 playwright 模拟键盘输入进行搜索
        try:
            await self.home_page.wait_for_selector("#search-input", timeout=120000)
            await self.home_page.evaluate("""
            (keyword) => {
                const closeEL = document.querySelector(".input-button .close-icon")
                if (closeEL) {
                    closeEL.click()
                }

                const input = document.querySelector("#search-input");
                const text = keyword;
                input.value = "";

                // 模拟每个字符的键盘输入
                for (let char of text) {
                    // 按键按下事件
                    input.dispatchEvent(new KeyboardEvent("keydown", {
                        key: char,
                        code: "Key" + char.toUpperCase(),
                        bubbles: true,
                        cancelable: true
                    }));
                    
                    // 更新输入框的值
                    input.value += char;
                    
                    // 触发input事件
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                    
                    // 按键抬起事件
                    input.dispatchEvent(new KeyboardEvent("keyup", {
                        key: char,
                        code: "Key" + char.toUpperCase(),
                        bubbles: true,
                        cancelable: true
                    }));
                }
                document.querySelector(".search-icon").click()
            }
            """, keyword)
            await self.home_page.wait_for_selector(".filter", timeout=120000)

            # 使用 playwright 模拟点击筛选条件
            try:
                await self.home_page.evaluate("""
                async (params) => {
                    const sortType = parseInt(params[0]);
                    const noteType = parseInt(params[1]);
                    const noteTimeType = parseInt(params[2]);
                    const searchScopeType = parseInt(params[3]);
                    const locationType = parseInt(params[4]);
                    const delay = Math.random() * 1000 + 3000;
                    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
                    // 排序类型
                    if (sortType != 0) {
                        document.querySelector(".filter").click();
                        await sleep(delay)
                        const filters = document.querySelectorAll(".filters-wrapper .filters")
                        const sortTypeFilter = filters[0]
                        sortTypeFilter.querySelectorAll(".tags")[sortType].click()
                        await sleep(delay)
                        document.querySelector(".filter").click();
                    }
                    // 笔记类型
                    if (noteType != 0) {
                        document.querySelector(".filter").click();
                        await sleep(delay)
                        const filters = document.querySelectorAll(".filters-wrapper .filters")
                        const noteTypeFilter = filters[1]
                        noteTypeFilter.querySelectorAll(".tags")[noteType].click()
                        await sleep(delay)
                        document.querySelector(".filter").click();
                    }
                    // 笔记时间类型
                    if (noteTimeType != 0) {
                        document.querySelector(".filter").click();
                        await sleep(delay)
                        const filters = document.querySelectorAll(".filters-wrapper .filters")
                        const noteTimeTypeFilter = filters[2]
                        noteTimeTypeFilter.querySelectorAll(".tags")[noteTimeType].click()
                        await sleep(delay)
                        document.querySelector(".filter").click();
                    }
                    // 搜索范围类型
                    if (searchScopeType != 0) {
                        document.querySelector(".filter").click();
                        await sleep(delay)
                        const filters = document.querySelectorAll(".filters-wrapper .filters")
                        const searchScopeTypeFilter = filters[3]
                        searchScopeTypeFilter.querySelectorAll(".tags")[searchScopeType].click()
                        await sleep(delay)
                        document.querySelector(".filter").click();
                    }
                    // 位置类型
                    if (locationType != 0) {
                        document.querySelector(".filter").click();
                        await sleep(delay)
                        const filters = document.querySelectorAll(".filters-wrapper .filters")
                        const locationTypeFilter = filters[4]
                        locationTypeFilter.querySelectorAll(".tags")[locationType].click()
                        await sleep(delay)
                        document.querySelector(".filter").click();
                    }
                }""", [
                    params.sort_type.value, 
                    params.note_type.value, 
                    params.note_time_type.value, 
                    params.search_scope_type.value, 
                    params.location_type.value
                ])
            except Exception:
                # 适应不同版本的筛选条件
                await self.home_page.evaluate("""async () => {
                    const selectors = document.querySelectorAll(".dropdown-container")
                    Array.from(selectors).forEach(selector => {
                        if (selector.textContent.includes("最新") && selector.textContent.includes("综合")) {
                            document.querySelectorAll(".dropdown-container")[2].querySelectorAll("li")[1].click()
                        }
                    })
                }""")
            await self.home_page.wait_for_load_state("domcontentloaded", timeout=120000)
            await asyncio.sleep(random.randint(3, 5))
        except Exception:
            await call_feishu_notion("通知: 可能出现验证码，请前往处理")
            await asyncio.sleep(random.randint(120, 300))
            await self.handle_search(keyword, params)
            return

    async def handle_loop_click_item(self, num: int = 20):
        """ 在搜索结果页点击笔记将信息记录到 state 中 """
        logger.info(f"Start loop click item, target num: {num}")
        try:
            logs = await self.home_page.evaluate("""
            async (num) => {
                const delay = Math.random() * 60000 + 10000;
                const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
                const lawlogs = []
                const getNoteNum = (initialState) => {
                    if (!initialState || !initialState.note || !initialState.note.noteDetailMap) {
                        return 0;
                    }
                    const noteDetailMap = initialState.note.noteDetailMap;
                    let noteKeyNum = 0;
                    Object.keys(noteDetailMap).forEach(key => {
                        if (key !== "undefined" && key !== "" && key !== null && noteDetailMap[key].hasOwnProperty("note") && noteDetailMap[key].note.hasOwnProperty("time")) {
                            noteKeyNum++;
                        }
                    })
                    return noteKeyNum;
                }

                let loop = 1;
                let items = document.querySelectorAll(".feeds-container section");
                let noteNum = getNoteNum(window.__INITIAL_STATE__);
                // 以笔记数量为单位控制循环是否停止
                while (noteNum < num) {
                    console.log(`spider: 第 ${loop} 次循环`);
                    lawlogs.push(`第 ${loop} 次循环`)
                    loop++;
                    for (const item of items) {
                        // 如果不是笔记元素，则跳过
                        if (!item || !item.querySelector(".footer") || !item.querySelector(".cover")) {
                            console.log("spider: 不是笔记元素，跳过", item);
                            lawlogs.push(`${item.innerHTML} 不是笔记元素，跳过`)
                            continue;
                        }

                        // 滚动到笔记元素
                        try {
                            item.scrollIntoView({ behavior: "smooth", block: "start" });
                            await sleep(1000);
                        } catch (e) {}

                        // 如果笔记元素已经存在，则跳过
                        try {
                            if (Object.keys(window.__INITIAL_STATE__.note.noteDetailMap).includes(item.querySelector("a[style=\\"display: none;\\"]").href.split("/").slice(-1)[0])) {
                                console.log("spider: 笔记元素已经存在，跳过", item);
                                lawlogs.push(`${item.innerHTML} 笔记元素已经存在，跳过`)
                                continue;
                            }
                        } catch (e) {}

                        // 如果笔记元素没有封面，则跳过
                        if (!item.querySelector(".cover")) {
                            console.log("spider: 笔记元素没有封面，跳过", item);
                            lawlogs.push(`${item.innerHTML} 笔记元素没有封面，跳过`)
                            continue;
                        }

                        // 点击笔记元素封面
                        item.querySelector(".cover").click();
                        await sleep(delay);

                        // 如果笔记元素没有关闭按钮，则跳过
                        if (!document.querySelector(".close.close-mask-dark")) {
                            console.log("笔记元素没有关闭按钮，跳过", item);
                            lawlogs.push(`${item.innerHTML} 笔记元素没有关闭按钮，跳过`)
                            continue;
                        }

                        // 点击笔记元素关闭按钮
                        document.querySelector(".close.close-mask-dark").click();
                        await sleep(3000);

                        // 如果笔记数量达到目标数量，则停止循环
                        noteNum = getNoteNum(window.__INITIAL_STATE__);
                        console.log(`spider: noteNum: ${noteNum}, num: ${num}`);
                        if (noteNum >= num) {
                            console.log("spider: 笔记数量达到目标数量，停止循环");
                            lawlogs.push(`${noteNum} > ${num} 笔记数量达到目标数量，停止循环`)
                            break;
                        }
                    }

                    // 加入随机滚动以防止循环滚动
                    items = document.querySelectorAll(".feeds-container section");
                    try {
                        const randomIndex = Math.floor(Math.random() * 5) + 11;
                        items[randomIndex].scrollIntoView({ behavior: "smooth", block: "start" });
                    } catch (e) {}

                    // 更新笔记元素列表
                    items = document.querySelectorAll(".feeds-container section");
                }
                return lawlogs;
            }""", num)
            logger.debug(f"handle_loop_click_item js logs: {logs}")
        except Exception:
            logger.error(traceback.format_exc())
            return {}

        state = await self.home_page.evaluate("() => window.__INITIAL_STATE__")
        notes = state.get("note", {}).get("noteDetailMap", {})
        logger.debug(f"notes: {notes}")

        if "undefined" in notes.keys():
            del notes["undefined"]
        if "" in notes.keys():
            del notes[""]

        logger.info(f"Get {len(notes)} noteDetailMap")
        return notes

    async def handle_save_note(self, note: XhsNote):
        """ 保存笔记 """
        try:
            is_exists = await XhsNotes.filter(note_id=note.note_id).exists()
            if is_exists:
                logger.info(f"Note {note.note_id} already exists")
                return
            await XhsNotes.create(**note.model_dump())
            logger.info(f"Save note {note.note_id} successfully")
        except Exception:
            logger.error(f"Save note {note.note_id} failed: {traceback.format_exc()}")

    async def handle_save_note_comment(self, comment: XhsNoteComment):
        """ 保存笔记评论 """
        try:
            is_exists = await XhsNoteComments.filter(comment_id=comment.comment_id).exists()
            if is_exists:
                logger.info(f"Note comment {comment.comment_id} already exists")
                return
            await XhsNoteComments.create(**comment.model_dump())
            logger.info(f"Save note comment {comment.comment_id} successfully")
        except Exception:
            logger.error(f"Save note comment {comment.comment_id} failed: {traceback.format_exc()}")

    async def handle_download_note_media(self, note: XhsNote):
        """ 下载笔记媒体文件 """
        save_path = TEST_DATA_PATH / f"xhs/{note.note_id}" if settings.test else XHS_DATA_PATH / f"{note.note_id}"
        save_path.mkdir(parents=True, exist_ok=True)
        for index, video in enumerate(note.videos):
            try:
                response = await self.browser.context.request.get(video, timeout=0)
                if response.ok:
                    async with aiofiles.open(str(save_path / f"{index}.mp4"), "wb") as f:
                        await f.write(await response.body())
                        logger.info(f"Download video {index} for {note.note_id} successfully")
            except Exception:
                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        resp = await client.get(video)
                        resp.raise_for_status()
                        async with aiofiles.open(str(save_path / f"{index}.mp4"), "wb") as f:
                            await f.write(resp.content)
                        logger.info(f"Download video {index} for {note.note_id} successfully")
                except Exception:
                    logger.error(f"Download video {index} for {note.note_id} failed: {traceback.format_exc()}")

        for index, image in enumerate(note.images):
            try:
                response = await self.browser.context.request.get(image)
                if response.ok:
                    async with aiofiles.open(str(save_path / f"{index}.webp"), "wb") as f:
                        await f.write(await response.body())
                    logger.info(f"Download image {index} for {note.note_id} successfully")
            except Exception:
                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        resp = await client.get(image)
                        resp.raise_for_status()
                        async with aiofiles.open(str(save_path / f"{index}.webp"), "wb") as f:
                            await f.write(resp.content)
                    logger.info(f"Download image {index} for {note.note_id} successfully")
                except Exception:
                    logger.error(f"Download image {index} for {note.note_id} failed: {traceback.format_exc()}")

    async def handle_convert_note(self, keyword: str, note_detail_item: dict) -> tuple[XhsNote, list[XhsNoteComment]]:
        """ 将笔记信息转换为 XhsNote 和 XhsNoteComment 对象 """
        note = note_detail_item.get("note")
        try:
            if note.get("time") is None:
                return None, []
            xhs_note = await get_xhs_note(keyword, note)
        except Exception:
            logger.error(f"Convert note failed, error info: {traceback.format_exc()}\nnote_detail_item: {note_detail_item}")
            return None, []

        comments = note_detail_item.get("comments", {}).get("list", [])
        xhs_note_comments = []
        for comment in comments:
            try:
                real_comment = await get_xhs_note_comment(xhs_note.note_id, comment)
                xhs_note_comments.append(real_comment)
            except Exception:
                logger.error(f"Convert comment failed, error info: {traceback.format_exc()}\ncomment: {comment}")
                continue

        logger.info(f"Get {xhs_note.note_id} and {len(xhs_note_comments)} comments successfully")
        return xhs_note, xhs_note_comments

    async def handle_save_note_task(self, *, xhs_note: XhsNote, xhs_note_comments: list[XhsNoteComment]):
        """ 保存笔记和笔记评论和笔记媒体文件 """
        await self.handle_save_note(xhs_note)
        for comment in xhs_note_comments:
            await self.handle_save_note_comment(comment)
        await self.handle_download_note_media(xhs_note)

    async def crawler_by_keywords(self, keywords: list[str] = [], num: int = 20, params: XhsSearchParams = None):
        """ 通过关键词搜索笔记并保存到数据库 """
        if len(keywords) == 0:
            keywords = settings.xhs.keywords_list

        params = params or XhsSearchParams()

        logger.warning(f"Start crawler by keywords: {keywords}")
        for keyword in keywords:
            try:
                await self.handle_search(keyword, params)
            except Exception:
                logger.error(traceback.format_exc())
                continue
            notes = await self.handle_loop_click_item(num)
            task_args = []
            for note_detail_item in notes.values():
                xhs_note, xhs_note_comments = await self.handle_convert_note(keyword, note_detail_item)
                if xhs_note is None:
                    continue
                task_args.append({
                    "xhs_note": xhs_note,
                    "xhs_note_comments": xhs_note_comments
                })
            
            semaphore = asyncio.Semaphore(10)

            async def sem_task(task_args):
                async with semaphore:
                    await self.handle_save_note_task(**task_args)

            tasks = [sem_task(task_args) for task_args in task_args]
            await asyncio.gather(*tasks)

            if settings.test:
                break
            else:
                await self.home_page.reload(wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(random.randint(60, 120))
