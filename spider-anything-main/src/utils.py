import re
import time
import hmac
import base64
import hashlib
import typing as t

import httpx

from src.const import ROOT_PATH
from src.settings import settings


def convert_cookies(cookies: t.Optional[t.List[t.Dict]]) -> t.Tuple[str, t.Dict]:
    if not cookies:
        return "", {}
    cookies_str = ";".join([f"{cookie.get('name')}={cookie.get('value')}" for cookie in cookies])
    cookie_dict = dict()
    for cookie in cookies:
        cookie_dict[cookie.get("name")] = cookie.get("value")
    return cookies_str, cookie_dict


def convert_str_cookie_to_dict(cookie_str: str) -> t.Dict:
    cookie_dict: t.Dict[str, str] = dict()
    if not cookie_str:
        return cookie_dict
    for cookie in cookie_str.split(";"):
        cookie = cookie.strip()
        if not cookie:
            continue
        cookie_list = cookie.split("=")
        if len(cookie_list) != 2:
            continue
        cookie_value = cookie_list[1]
        if isinstance(cookie_value, list):
            cookie_value = "".join(cookie_value)
        cookie_dict[cookie_list[0]] = cookie_value
    return cookie_dict


def camel_to_snake(camel_case: str) -> str:
    """ 将小驼峰命名转换为下划线命名
    Args:
        camel_case: 小驼峰命名的字符串，如 "userName"
    Returns:
        下划线命名的字符串，如 "user_name"
    """
    # 使用正则表达式在小写字母后跟大写字母的地方插入下划线
    snake_case = re.sub(r'([a-z])([A-Z])', r'\1_\2', camel_case)
    # 转换为小写
    return snake_case.lower()


def generate_feishu_sign(timestamp: str, secret: str) -> str:
    """ 生成飞书签名 """
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

async def call_feishu_notion(message: str):
    """ 调用飞书机器人发送消息 """
    async_client = httpx.AsyncClient()
    timestamp = str(int(time.time()))
    secret = settings.feishu.webhook_secret
    sign = generate_feishu_sign(timestamp, secret)
    await async_client.post(
        settings.feishu.webhook,
        json={
            "sign": sign,
            "content": {"text": message},
            "msg_type": "text",
            "timestamp": timestamp,
        },
    )
    await async_client.aclose()


def get_js_code(platform: str, filename: str) -> str:
    with open(f"{ROOT_PATH}/src/js/{platform}/{filename}.js", "r", encoding="utf-8") as f:
        return f.read()


def check_str_has(string: str, keywords: t.Union[str, t.List[str]]) -> bool:
    if isinstance(keywords, str):
        keywords = [keywords]
    for keyword in keywords:
        if keyword in string:
            return True
    return False