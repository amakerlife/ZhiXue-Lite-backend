import base64
import json
from typing import Tuple

import requests
from loguru import logger
from requests import Session
from zhixuewang.exceptions import (
    LoginError,
    UserOrPassError,
    UserNotFoundError,
)
from zhixuewang.session import get_basic_session
from zhixuewang.urls import Url

from app.config import Config
from app.models.exceptions import LoginCaptchaError

captcha_api = Config.GEETEST_CAPTCHA_URL

MAX_RETRIES = 5
TIMEOUT = 10
CHANGYAN_LOGIN_URL = "https://pass.changyan.com/login/checkLogin"
CHANGYAN_AGREEMENT_URL = "https://pass.changyan.com/login/updateUserAgreementStatus"
ZHIXUE_LOGIN_URL = "https://www.zhixue.com/edition/login?from=web_login"


def gen_encrypted_password(password: str) -> str:
    """生成加密后的密码"""
    if len(password) != 32:
        password = (
            pow(
                int.from_bytes(password.encode()[::-1], "big"),
                65537,
                186198350384465244738867467156319743461,
            )
            .to_bytes(16, "big")
            .hex()
        )  # by immoses648
    return password


def gen_captcha_data(session: requests.Session) -> dict:
    """
    获取验证码数据

    Args:
        session (requests.Session): Session

    Raises:
        LoginCaptchaError: 获取验证码失败

    Returns:
        dict: 验证码数据
    """
    logger.info("Getting captcha")
    captcha_data = {}
    for attempt in range(MAX_RETRIES):
        try:
            captcha_data = session.get(captcha_api, timeout=TIMEOUT).json()["data"]
        except Exception as e:
            logger.warning(f"Failed to get captcha: {e}")
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Failed to get captcha after {MAX_RETRIES} "
                             f"attempts")
                raise LoginCaptchaError(
                    f"Failed to get captcha after " f"{MAX_RETRIES} attempts"
                )
            continue
        if captcha_data["result"] == "success":
            break
    return captcha_data


def login_via_changyan(
    username: str, password: str, captcha_data: dict, session: requests.Session
) -> Tuple[str, Session]:
    """
    通过畅言登录

    Args:
        username (str): 用户名
        password (str): 密码（encrypted）
        captcha_data (dict): 验证码数据
        session (requests.Session): Session

    Raises:
        LoginError: 登录错误

    Returns:
        Tuple[str, Session]: 验证码数据，session
    """
    data = {
        "i": username,
        "p": password,
        "f": "1",
        "c": "",
        "a": "0",
        "m": "",
        "dm": "web",
        "co": captcha_data["seccode"]["captcha_output"],
        "gt": captcha_data["seccode"]["gen_time"],
        "ln": captcha_data["seccode"]["lot_number"],
        "pt": captcha_data["seccode"]["pass_token"],
        "ct": "web",
        "cat": "third",
    }
    captcha_result = session.post(CHANGYAN_LOGIN_URL, data=data).json()
    if captcha_result["Msg"] == "用户未签署过用户协议" or captcha_result["Code"] == -11:
        session.post(CHANGYAN_AGREEMENT_URL)
        captcha_data = gen_captcha_data(session)
        data.update({
            "co": captcha_data["seccode"]["captcha_output"],
            "gt": captcha_data["seccode"]["gen_time"],
            "ln": captcha_data["seccode"]["lot_number"],
            "pt": captcha_data["seccode"]["pass_token"],
        })
        captcha_result = session.post(CHANGYAN_LOGIN_URL, data=data).json()
    if captcha_result["Msg"] != "获取用户信息成功":
        logger.error(
            f"Failed to login(changyan): {username}: "
            f"{captcha_result['Msg']}"
        )
        raise LoginError(f"Failed to login: {username}: "
                         f"{captcha_result['Msg']}")
    logger.info(f"Successfully logged in(changyan): {username}")
    return json.loads(captcha_result["Data"])["captchaResult"], session


def login_via_zhixue(
    username: str, password: str, captcha_data: dict, session: requests.Session
) -> Tuple[str, Session]:
    """
    通过智学网登录

    Args:
        username (str): 用户名
        password (str): 密码（unencrypted）
        captcha_data (dict): 验证码数据
        session (requests.Session): Session

    Raises:
        LoginError: 登录错误

    Returns:
        Tuple[str, Session]: 验证码数据，session
    """
    data = {
        "appId": "zx-container-client",
        "captchaType": "third",
        "thirdCaptchaExtInfo[captcha_output]": (
            captcha_data["seccode"]["captcha_output"]
        ),
        "thirdCaptchaExtInfo[gen_time]": captcha_data["seccode"]["gen_time"],
        "thirdCaptchaExtInfo[lot_number]": (
            captcha_data["seccode"]["lot_number"]
        ),
        "thirdCaptchaExtInfo[pass_token]": (
            captcha_data["seccode"]["pass_token"]
        ),
        "loginName": username,
        "password": password,
    }

    captcha_result = session.post(ZHIXUE_LOGIN_URL, data=data).json()
    if captcha_result["result"] != "success":
        logger.error(
            f"Failed to login(zhixue): {username}: "
            f"{captcha_result['message']}"
        )
        raise LoginError(
            f"Failed to login: {username}: " f"{captcha_result['message']}"
        )
    logger.info(f"Successfully logged in(zhixue): {username}")

    return captcha_result["data"]["captchaId"], session


def get_session_by_captcha(username: str, password: str, login_method: str = "changyan") -> requests.Session:
    """
    通过用户名和密码获取 session，使用验证码

    Args:
        username (str): 用户名
        password (str): 密码
        login_method (str): 登录方式，默认为 "changyan"
            "changyan" 或 "zhixue"

    Raises:
        UserOrPassError: 用户名或密码错误
        UserNotFoundError: 未找到用户
        LoginError: 登录错误

    Returns:
        requests.session: session
    """
    origin_password = password
    password = gen_encrypted_password(password)
    session = get_basic_session()

    actual_method = ""  # 实际使用的登录方式

    if username.isdigit() and len(username) == 8:
        login_method = "zhixue"

    if login_method == "zhixue":
        try:
            captcha_data = gen_captcha_data(session)
            captcha_id, session = login_via_zhixue(
                username, origin_password, captcha_data, session
            )
            actual_method = "zhixue"
        except LoginError as e:
            try:
                if (e.__str__().find("密码错误") != -1):
                    raise e
                if (origin_password == "111111"):
                    raise LoginError("密码强度过低")
                captcha_data = gen_captcha_data(session)
                captcha_id, session = login_via_changyan(
                    username, password, captcha_data, session
                )
                actual_method = "changyan"
            except LoginError as e:
                logger.info(f"Failed to login(web): {e}")
                raise e
    else:
        try:
            if (origin_password == "111111"):
                raise LoginError("密码强度过低")
            captcha_data = gen_captcha_data(session)
            captcha_id, session = login_via_changyan(
                username, password, captcha_data, session
            )
            actual_method = "changyan"
        except LoginError as e:
            try:
                if (e.__str__().find("密码错误") != -1):
                    raise e
                captcha_data = gen_captcha_data(session)
                captcha_id, session = login_via_zhixue(
                    username, origin_password, captcha_data, session
                )
                actual_method = "zhixue"
            except LoginError as e:
                logger.info(f"Failed to login(web): {e}")
                raise e

    # 原登录逻辑
    r = session.get(Url.SSO_URL)
    text = r.text.strip().replace("\\", "").replace("'", "")
    json_obj = json.loads(text[1:-1])
    if json_obj["code"] != 1000:
        raise LoginError(json_obj["data"])
    lt = json_obj["data"]["lt"]
    execution = json_obj["data"]["execution"]
    r = session.get(
        Url.SSO_URL,
        params={
            "appId": "pass6port18",
            "captchaId": captcha_id,
            "captchaType": "third",
            "thirdCaptchaParam": captcha_data["seccode"],
            "encode": "true",
            "sourceappname": "tkyh,tkyh",
            "_eventId": "submit",
            "client": "web",
            "type": "loginByNormal",
            "key": "auto",
            "lt": lt,
            "execution": execution,
            "customLogoutUrl": "https://www.zhixue.com/login.html",
            "username": username,
            "password": password,
        },
    )
    cleaned_text = r.text.strip().replace("\\", "").replace("'", "")[1:-1]
    json_obj = json.loads(cleaned_text)
    if json_obj["code"] != 1001:
        if json_obj["code"] == 1002:
            raise UserOrPassError()
        if json_obj["code"] == 2009:
            raise UserNotFoundError()
        raise LoginError(json_obj["data"])
    ticket = json_obj["data"]["st"]
    session.post(
        Url.SERVICE_URL,
        data={
            "action": "login",
            "ticket": ticket,
        },
    )
    session.cookies.set("uname", base64.b64encode(username.encode()).decode())
    session.cookies.set("pwd", base64.b64encode(origin_password.encode()).decode())
    session.cookies.set("login_method", actual_method)
    return session


def update_login_status(account):
    """更新登录状态. 如果 session 过期自动重新获取

    Returns:
        bool: 是否更新了 session
    """
    r = account._session.get(Url.GET_LOGIN_STATE)
    data = r.json()
    if data["result"] == "success":
        return False
    # session 过期
    password = base64.b64decode(account._session.cookies["pwd"].encode()).decode()
    login_method = account._session.cookies.get("login_method", "changyan")
    account._session = get_session_by_captcha(account.username, password, login_method)
    return True


def set_user_session(cookie: str) -> Session:
    """
    通过 cookie 获取用户 session

    Args:
        cookie (str): 用户的 cookie 字符串，JSON 格式

    Returns:
        Session: 会话对象
    """
    session = get_basic_session()

    try:
        data = json.loads(cookie)
        if not isinstance(data, list):
            raise ValueError("Cookie data is not in expected JSON list format; falling back to legacy format")
        for c in data:
            session.cookies.set(c["name"], c["value"],
                                domain=c.get("domain", ""), path=c.get("path", "/"))
    except (ValueError, json.JSONDecodeError):
        for item in cookie.split(";"):
            if "=" in item:
                name, value = item.strip().split("=", 1)
                session.cookies.set(name, value)

    return session
