import time
import json
import typing as t
import hashlib
import asyncio
import traceback
from random import randint
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import httpx
import asyncpg
import aiofiles
from loguru import logger
from tortoise import Tortoise
from playwright.async_api import Page, Response

from src.utils import check_str_has, call_feishu_notion, convert_str_cookie_to_dict
from src.const import ROOT_PATH, TEST_DATA_PATH, TWITTER_DATA_PATH
from src.settings import settings
from src.core.browser import Browser
from src.model.twitter import TwitterSearchResult, TwitterUser, TwitterTweet, TwitterMedia, TwitterConversation, TwitterDetailResult


# 配置 loguru 日志
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    format="<level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
    colorize=True
)
logger.add(
    sink=f"{ROOT_PATH}/logs/twitter_error_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log",
    format="{level: <8} | {message}",
    level="INFO",
    rotation="1 day",
    retention="30 days",
    compression="zip"
)
if settings.debug:
    logger.add(
        sink=f"{ROOT_PATH}/logs/twitter_debug_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        compression="zip"
    )


not_tweet_keywords = ["promoted", "toptabsrpusermodule", "cursor", "relevanceprompt"]


def get_tweet_from_conversation(conversation: t.Dict):
    tweet_wrapper = conversation.get("item", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
    if "tweet" in tweet_wrapper.keys():
        return tweet_wrapper.get("tweet", {})
    return tweet_wrapper


def get_tweet_detail_instructions(content: t.Dict):
    return content.get("data", {}).get("threaded_conversation_with_injections_v2", {}).get("instructions", [])


def get_search_timeline_instructions(content: t.Dict):
    return content.get("data", {}).get("search_by_raw_query", {}).get("search_timeline", {}).get("timeline", {}).get("instructions", [])


def translate_time(time_str: str):
    try:
        dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
        ts = int(dt.timestamp())
        return ts * 1000
    except Exception as e:
        logger.error(f"时间转换失败: {time_str}，错误: {e}")
        return time.time() * 1000


class TwitterHandler:

    def __init__(self, browser: Browser, home_url: str = "https://www.x.com"):
        self.keyword = ""
        self.task_result = {}
        self.browser = browser
        self.home_url = home_url
        self.home_page: Page
        self.is_init = False
        self.loading_list = [False, False]
        logger.info("Created Twitter handler instance successfully, waiting for initialize...")

    async def sleep(self, min_t: int, max_t: int):
        await asyncio.sleep(randint(min_t, max_t))

    async def quick_sleep(self):
        await self.sleep(4, 8)
    
    async def slow_sleep(self):
        await self.sleep(30, 60)

    async def __save_user(self, user: t.Dict):
        """ 保存/更新用户信息 """
        try:
            logger.debug(f"| User info: {user}")
            if not user:
                logger.error("| User info is empty")
                return
            
            user_instance = await TwitterUser.filter(id=user.get("rest_id")).first()
            if user_instance:
                if hashlib.md5(json.dumps(user_instance.content).encode()).hexdigest() == hashlib.md5(json.dumps(user).encode()).hexdigest():
                    logger.info(f"| User {user.get('rest_id')} already exists")
                    return
                logger.info(f"| Start update user: {user.get('rest_id')}")
                history = user_instance.history + [user]
                user_instance.avatar=user.get("avatar", {}).get("image_url", None),
                user_instance.username=user.get("core", {}).get("name", None)
                user_instance.screen_name=user.get("core", {}).get("screen_name", None)
                user_instance.description=user.get("legacy", {}).get("description", None)
                user_instance.location=user.get("location", {}).get("location", None)
                user_instance.favourites_count=user.get("legacy", {}).get("favourites_count", 0)
                user_instance.followers_count=user.get("legacy", {}).get("followers_count", 0)
                user_instance.friends_count=user.get("legacy", {}).get("friends_count", 0)
                user_instance.statuses_count=user.get("legacy", {}).get("statuses_count", 0)
                user_instance.content=user
                user_instance.created_at=translate_time(user.get("core", {}).get("created_at", None))
                user_instance.history=history
                await user_instance.save()
                logger.info(f"| Update user {user.get('rest_id')} successfully")
            else:
                logger.info(f"| Start save user: {user.get('rest_id')}")
                await TwitterUser.create(
                    id=user.get("rest_id"),
                    avatar=user.get("avatar", {}).get("image_url", None),
                    username=user.get("core", {}).get("name", None),
                    screen_name=user.get("core", {}).get("screen_name", None),
                    description=user.get("legacy", {}).get("description", None),
                    location=user.get("location", {}).get("location", None),
                    favourites_count=user.get("legacy", {}).get("favourites_count", 0),
                    followers_count=user.get("legacy", {}).get("followers_count", 0),
                    friends_count=user.get("legacy", {}).get("friends_count", 0),
                    statuses_count=user.get("legacy", {}).get("statuses_count", 0),
                    content=user,
                    created_at=translate_time(user.get("core", {}).get("created_at", None)),
                )
                logger.info(f"| Save user {user.get('rest_id')} successfully")
        except Exception:
            logger.error(f"| Save user error: {traceback.format_exc()}")

    async def __save_tweet(self, tweet: t.Dict):
        """ 保存推文信息 """
        try:
            logger.info("=" * 50)
            logger.debug(f"| Tweet info: {tweet}")
            if not tweet:
                logger.error("| Tweet info is empty")
                return

            self.task_result[self.keyword]["tweets"].append(tweet.get("rest_id"))
            is_exists = await TwitterTweet.filter(id=tweet.get("rest_id")).exists()
            if is_exists:
                logger.info(f"| Tweet {tweet.get('rest_id')} already exists")
                return

            has_quote = tweet.get("legacy", {}).get("is_quote_status", False)
            quote_tweet_id = None
            if has_quote:
                quote_tweet = tweet.get("quoted_status_result", {}).get("result", {})
                if quote_tweet:
                    logger.debug(f"| Quote tweet: {quote_tweet}")
                    quote_tweet_id = quote_tweet.get("rest_id", None)
                    await self.__save_tweet(quote_tweet)

            user = tweet.get("core", {}).get("user_results", {}).get("result", {})
            await self.__save_user(user)

            logger.info(f"| Start save tweet: {tweet.get('rest_id')}")
            
            media = tweet.get("legacy", {}).get("entities", {}).get("media", [])
            if not media:
                media = tweet.get("legacy", {}).get("extended_entities", {}).get("media", [])

            await TwitterTweet.create(
                id=tweet.get("rest_id"),
                quote_id=quote_tweet_id,
                parent_id=tweet.get("legacy", {}).get("in_reply_to_status_id_str", None),
                user_id=user.get("rest_id"),
                url=f"https://x.com/{user.get("core", {}).get("screen_name", None)}/status/{tweet.get('rest_id')}",
                full_text=tweet.get("legacy", {}).get("full_text", None),
                lang=tweet.get("legacy", {}).get("lang", None),
                quote_count=tweet.get("legacy", {}).get("quote_count", 0),
                reply_count=tweet.get("legacy", {}).get("reply_count", 0),
                retweet_count=tweet.get("legacy", {}).get("retweet_count", 0),
                favorite_count=tweet.get("legacy", {}).get("favorite_count", 0),
                bookmark_count=tweet.get("legacy", {}).get("bookmark_count", 0),
                with_media=len(media) > 0,
                content=tweet,
                keyword=self.keyword,
                created_at=translate_time(tweet.get("legacy", {}).get("created_at", None)),
            )
            self.task_result[self.keyword]["saved_tweets"].append(tweet.get("rest_id"))
            logger.info(f"| Save tweet {tweet.get('rest_id')} successfully")
        except Exception:
            logger.error(f"| Save tweet error: {traceback.format_exc()}")

        for media_item in media:
            await self.__save_media(tweet.get('rest_id'), "tweet", media_item)
        logger.info("=" * 50)

    async def __download_media(self, tweet_id: str, media_type: str, media_id: str, media_url: str) -> str:
        """ 下载媒体文件并返回 sha256 值 """
        logger.info(f"| Start download media: {media_url}")
        save_path = TEST_DATA_PATH / f"twitter/{tweet_id}" if settings.test else TWITTER_DATA_PATH / f"{tweet_id}"
        save_path = save_path / media_type
        save_path.mkdir(parents=True, exist_ok=True)

        ext = media_url.split("?")[0].split(".")[-1]
        if not ext:
            ext = "mp4" if media_type == "video" else "jpg"

        try:
            response = await self.browser.context.request.get(media_url, timeout=0)
            if response.ok:
                async with aiofiles.open(str(save_path / f"{media_id}.{ext}"), "wb") as f:
                    body = await response.body()
                    sha256_hash = hashlib.sha256(body).hexdigest()
                    await f.write(body)
                    logger.info(f"| Download {media_type} {media_id} for {tweet_id} successfully")
                    return sha256_hash
            raise Exception(response.text())
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    resp = await client.get(media_url)
                    resp.raise_for_status()
                    async with aiofiles.open(str(save_path / f"{media_id}.{ext}"), "wb") as f:
                        sha256_hash = hashlib.sha256(resp.content).hexdigest()
                        await f.write(resp.content)
                    logger.info(f"| Download {media_type} {media_id} for {tweet_id} successfully")
                    return sha256_hash
            except Exception:
                logger.error(f"| Download {media_type} {media_id} for {tweet_id} failed: {traceback.format_exc()}")
        return None

    async def __save_media(self, source_id: str, source_type: str, media: t.Dict):
        """ 保存媒体文件 """
        try:
            if await TwitterMedia.filter(id=media.get("id_str")).exists():
                logger.info(f"| Media {media.get('id_str')} already exists")
                return 
            logger.debug(f"| Media info: {media}")
            download_url = media.get("media_url_https", None)
            if media.get("type") == "video":
                download_url = media.get("video_info").get("variants")[-1].get("url")
            sha256 = await self.__download_media(source_id, media.get("type"), media.get("id_str"), download_url)

            logger.info(f"| Start save media: {media.get('id_str')}")
            await TwitterMedia.create(
                id=media.get('id_str'),
                source_id=source_id,
                source_type=source_type,
                download_url=download_url,
                type=media.get("type", None),
                sha256=sha256,
                content=media,
            )
            logger.info(f"| Save media {media.get('id_str')} successfully")
        except Exception:
            logger.error(f"| Save media error: {traceback.format_exc()}")

    async def __save_conversation(self, tweet_id: str, conversation: t.Dict):
        """ 保存对话信息 """
        try:
            logger.info("=" * 50)
            logger.debug(f"| Conversation info: {conversation}")
            if not conversation:
                logger.error("| Conversation info is empty")
                return
            
            self.task_result[self.keyword]["conversations"].append(conversation.get("rest_id"))
            is_exists = await TwitterConversation.filter(id=conversation.get("rest_id")).exists()
            if is_exists:
                logger.info(f"| Conversation {conversation.get('rest_id')} already exists")
                return

            has_quote = conversation.get("legacy", {}).get("is_quote_status", False)
            quote_tweet_id = None
            if has_quote:
                quote_tweet = conversation.get("quoted_status_result", {}).get("result", {})
                if quote_tweet:
                    logger.debug(f"| Quote tweet: {quote_tweet}")
                    quote_tweet_id = quote_tweet.get("rest_id", None)
                    await self.__save_conversation(tweet_id, quote_tweet)

            user = conversation.get("core", {}).get("user_results", {}).get("result", {})
            await self.__save_user(user)

            logger.info(f"| Start save conversation: {conversation.get('rest_id')}")
            
            media = conversation.get("legacy", {}).get("entities", {}).get("media", [])
            if not media:
                media = conversation.get("legacy", {}).get("extended_entities", {}).get("media", [])

            await TwitterConversation.create(
                id=conversation.get("rest_id"),
                tweet_id=tweet_id,
                quote_id=quote_tweet_id,
                parent_id=conversation.get("legacy", {}).get("in_reply_to_status_id_str", None),
                user_id=user.get("rest_id"),
                url=f"https://x.com/{user.get("core", {}).get("screen_name", None)}/status/{conversation.get('rest_id')}",
                full_text=conversation.get("legacy", {}).get("full_text", None),
                lang=conversation.get("legacy", {}).get("lang", None),
                quote_count=conversation.get("legacy", {}).get("quote_count", 0),
                reply_count=conversation.get("legacy", {}).get("reply_count", 0),
                retweet_count=conversation.get("legacy", {}).get("retweet_count", 0),
                favorite_count=conversation.get("legacy", {}).get("favorite_count", 0),
                bookmark_count=conversation.get("legacy", {}).get("bookmark_count", 0),
                with_media=len(media) > 0,
                content=conversation,
                keyword=self.keyword,
                created_at=translate_time(conversation.get("legacy", {}).get("created_at", None)),
            )
            logger.info(f"| Save conversation {conversation.get('rest_id')} successfully")
        except Exception:
            logger.error(f"| Save conversation error: {traceback.format_exc()}")

        for media_item in media:
            await self.__save_media(conversation.get('rest_id'), "tweet", media_item)
        logger.info("=" * 50)

    async def __handle_search_timeline(self, response: Response):
        """ 处理搜索结果

        1. 筛选正常搜索结果(排除广告) / promoted
        2. 保存推文信息
        """
        logger.info(f"Handle search timeline from {self.home_page.url}")
        if response.status != 200:
            return

        try:
            self.loading_list[0] = True
            content = await response.text()
            logger.debug(f"Search timeline response content: {content}")
            await TwitterSearchResult.create(
                keyword=self.keyword,
                url=response.url.split("?")[0],
                url_with_params=response.url,
                content=content,
            )
            logger.info("Save search timeline result to database")
            format_content = json.loads(content)
            logger.debug(f"Search timeline format content: {format_content}")
            search_timeline_instructions = get_search_timeline_instructions(format_content)
            logger.debug(f"Search timeline instructions: {search_timeline_instructions}")
            logger.info(f"Start save at least {len(search_timeline_instructions)} tweets...")
            for instruction in search_timeline_instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    entries = instruction.get("entries", [])
                    for entry in entries:
                        if check_str_has(entry.get("entryId", ""), not_tweet_keywords):
                            continue
                        logger.debug(f"Entry info: {entry}")
                        tweet_list = len(entry.get("content", {}).get("items", []))
                        if tweet_list:
                            for tweet in tweet_list:
                                if check_str_has(tweet.get("entryId", ""), not_tweet_keywords):
                                    continue
                                tweet = get_tweet_from_conversation(tweet)
                                await self.__save_tweet(tweet)
                        else:
                            tweet = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                            await self.__save_tweet(tweet)
        except Exception:
            logger.error(f"Handle search timeline error: {content}")
        finally:
            self.loading_list[0] = False

    async def __handle_tweet_detail(self, response: Response):
        """ 处理推文详情结果

        1. 筛选非广告内容和非推文内容
        2. 保存推文详情中的对话
        """
        if response.status != 200:
            return

        logger.debug(f"Response url: {response.url}")
        parsed_url = urlparse(response.url)
        logger.debug(f"Parsed url: {parsed_url}")
        query_dict = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed_url.query).items()}
        logger.debug(f"Query dict: {query_dict}")
        tweet_id = json.loads(query_dict.get("variables", "{}")).get("focalTweetId", None)

        try:
            self.loading_list[1] = True
            content = await response.text()
            logger.debug(f"Tweet detail response content: {content}")
            await TwitterDetailResult.create(
                url=response.url.split("?")[0],
                url_with_params=response.url,
                tweet_id=tweet_id,
                content=content,
            )
            logger.info("Save tweet detail result to database")
            format_content = json.loads(content)
            logger.debug(f"Tweet detail format content: {format_content}")
            tweet_detail_instructions = get_tweet_detail_instructions(format_content)
            logger.info(f"Start save at least {len(tweet_detail_instructions)} conversations...")
            for instruction in tweet_detail_instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    entries = instruction.get("entries", [])
                    for entry in entries:
                        # 排除非正文内容
                        if check_str_has(entry.get("entryId", ""), not_tweet_keywords):
                            continue
                        # 排除推文内容
                        if entry.get("entryId", "").startswith("tweet-"):
                            continue

                        logger.debug(f"Entry info: {entry}")
                        conversation_list = entry.get("content", {}).get("items", [])
                        if len(conversation_list) > 0:
                            for conversation in conversation_list:
                                if check_str_has(conversation.get("entryId", ""), not_tweet_keywords):
                                    continue
                                if conversation.get("entryId", "").startswith("tweet-"):
                                    continue
                                tweet = get_tweet_from_conversation(conversation)
                                await self.__save_conversation(tweet_id, tweet)
                        else:
                            tweet = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                            await self.__save_conversation(tweet_id, tweet)
        except Exception:
            logger.error(f"Handle tweet detail error: {traceback.format_exc()}")
        finally:
            self.loading_list[1] = False

    async def __handle_browser_disconnected(self):
        """ 处理 browser 异常退出的回调函数 """
        logger.error("Browser 已异常退出，正在进行清理和重启操作...")
        await call_feishu_notion("Twitter-通知：Browser 异常退出")

    async def __listen_init(self):
        logger.info("Start listen response")
        async def on_response(response):
            if "SearchTimeline" in response.url:
                await self.__handle_search_timeline(response)
            if "TweetDetail" in response.url:
                await self.__handle_tweet_detail(response)
        self.home_page.on("response", on_response)
        self.browser.on("disconnected", self.__handle_browser_disconnected)

    async def __db_init(self):
        logger.info("Start initialize database")
        database = "test" if settings.test else "twitter"
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
                        "src.model.twitter",
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
        await self.__db_init()
        logger.info("Open home page")
        self.home_page = await self.browser.context.new_page()
        await self.home_page.goto(self.home_url, timeout=60000, wait_until="domcontentloaded")
        await self.home_page.wait_for_load_state("domcontentloaded")
        await self.quick_sleep()
        await self.login()
        await self.__listen_init()
        self.is_init = True
        logger.info("Handler initialized successfully")

    async def login(self):
        """ 检查登录状态并使用设定的方式进行登录 """
        logger.info("Check login state...")
        state = await self.home_page.evaluate("() => window.__META_DATA__")
        is_login = state.get("isLoggedIn", False)
        if not is_login:
            logger.info(f"User don't login, use {settings.twitter.login_type} login")
            if settings.twitter.login_type == "qrcode":
                await self.login_by_qrcode()
            elif settings.twitter.login_type == "phone":
                await self.login_by_mobile()
            elif settings.twitter.login_type == "cookie":
                await self.login_by_cookie()
        else:
            logger.info("User is logined")

    async def login_by_cookie(self, retry=0):
        """ 使用 Cookie 登录 """
        if retry > 3:
            logger.error("Login by cookie failed, retry more than 3 times")
            await call_feishu_notion("Twitter-通知：Cookie 登录失败，重试次数超过 3 次")
            await self.browser.close()
            return

        if retry > 0:
            logger.info(f"Start login by cookie, retry {retry} times")
        else:
            logger.info("Start login by cookie")

        for key, value in convert_str_cookie_to_dict(settings.twitter.cookie).items():
            await self.browser.context.add_cookies([{
                "name": key,
                "value": value,
                "domain": ".x.com",
                "path": "/"
            }])
        await self.home_page.reload()
        await self.quick_sleep()
        state = await self.home_page.evaluate("() => window.__META_DATA__")
        is_login = state.get("isLoggedIn", False)
        if not is_login:
            await self.login_by_cookie(retry + 1)
        else:
            logger.info("Login successfully")

    async def handle_search_keyword(self, keyword: str, sort_type: str = "top"):
        self.keyword = keyword
        await self.home_page.wait_for_selector("input[placeholder=\"Search\"]", timeout=120000)
        search_input = self.home_page.locator("input[placeholder=\"Search\"]")
        await search_input.focus()
        await search_input.type(keyword, delay=100)
        await search_input.press("Enter")
        if sort_type == "latest":
            tabs = await self.home_page.locator("div[role=\"presentation\"] a[role=\"tab\"]").all()
            tabs[1].click()

    async def task(self, keywords: t.Union[str, t.List[str]], num: int = 20):
        """ 推文抓取任务，抓取指定关键词的推文，并保存到数据库中 """
        if isinstance(keywords, str):
            keywords = [keywords]

        for i, keyword in enumerate(keywords):
            self.task_result[keyword] = {
                "tweets": [],
                "saved_tweets": [],
                "conversations": [],
                "saved_conversations": [],
            }
            await self.handle_search_keyword(keyword)
            loop_num = 0
            while len(set(self.task_result[keyword]["saved_tweets"])) < num:
                logger.info(f"Saved tweets: {len(set(self.task_result[keyword]['saved_tweets']))}/{num}")
                if any(self.loading_list):
                    await self.quick_sleep()
                    continue

                start_len = len(set(self.task_result[keyword]["saved_tweets"]))
                await self.home_page.evaluate("""
                    () => {
                        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
                    }
                """)
                await self.quick_sleep()
                await self.home_page.evaluate("""
                    () => {
                        window.scrollBy({ top: 100, behavior: 'smooth' });
                    }
                """)
                end_len = len(set(self.task_result[keyword]["saved_tweets"]))

                # 如果循环次数大于2次，则认为已经没有更多推文了
                if start_len == end_len:
                    loop_num += 1
                    if loop_num > 2:
                        break
                else:
                    loop_num = 0
            await call_feishu_notion(f"Twitter-通知：抓取关键词 {i+1}/{len(keywords)} 推文任务完成，共抓取 {len(self.task_result[keyword]['saved_tweets'])} 条推文")

            for tweet_id in self.task_result[keyword]["saved_tweets"]:
                tweet = await TwitterTweet.filter(id=tweet_id).first()
                if tweet and tweet.reply_count > 0:
                    await self.home_page.goto(tweet.url, timeout=60000, wait_until="domcontentloaded")
                    await self.quick_sleep()
                    loop_num = 0
                    while True:
                        logger.info(f"Saved conversations: {len(set(self.task_result[keyword]['saved_conversations']))}")
                        start_len = len(set(self.task_result[keyword]["saved_conversations"]))
                        await self.home_page.evaluate("""
                            () => {
                                window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
                            }
                        """)
                        await self.quick_sleep()
                        await self.home_page.evaluate("""
                            () => {
                                window.scrollBy({ top: 100, behavior: 'smooth' });
                            }
                        """)
                        await self.quick_sleep()
                        end_len = len(set(self.task_result[keyword]["saved_conversations"]))

                        # 如果循环次数大于2次，则认为已经没有更多对话了
                        if start_len == end_len:
                            loop_num += 1
                            if loop_num > 2:
                                break
                        else:
                            loop_num = 0
                    while any(self.loading_list):
                        await self.quick_sleep()
            await call_feishu_notion(f"Twitter-通知：抓取关键词 {i+1}/{len(keywords)} 对话任务完成，共抓取 {len(self.task_result[keyword]['saved_conversations'])} 条对话")
            await self.slow_sleep()

    async def get_detail_task(self):
        tweets = await TwitterTweet.all()
        for tweet in tweets:
            await self.home_page.goto(tweet.url, timeout=60000, wait_until="domcontentloaded")
            await self.quick_sleep()
            while any(self.loading_list):
                await self.quick_sleep()
