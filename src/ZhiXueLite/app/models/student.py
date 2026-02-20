from flask import json
from zhixuewang.student import StudentAccount

from app.utils.crypto import decrypt, encrypt
from app.utils.login_zhixue import set_user_session, update_login_status, get_session_by_captcha


class ExtendedStudentAccount(StudentAccount):
    """
    主要用于临时修复上游问题
    """

    def update_login_status(self) -> bool:
        """
        更新登录状态，如果更新了则保存新 cookie 到数据库（仅在 Flask 上下文中）

        Returns:
            bool: 是否更新了 session
        """
        return update_login_status(self)

    def get_cookie(self) -> str:
        """
        获取 Cookie 字符串（JSON 格式）
        """
        if not self.get_session():
            return "[]"
        cookies = []
        for cookie in self.get_session().cookies:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path
            })
        return json.dumps(cookies)


def login_student(username: str, password: str, method: str = "changyan") -> ExtendedStudentAccount:
    """
    登录学生账号

    Args:
        username (str): 用户名
        password (str): 密码

    Returns:
        ExtendedStudentAccount: 学生账号
    """
    session = get_session_by_captcha(username, password, method)
    return ExtendedStudentAccount(session).set_base_info()


def login_student_session(cookie: str) -> ExtendedStudentAccount:
    """
    通过 session 登录学生账号

    Args:
        cookie (str): Cookie 字符串（JSON 格式，已加密）

    Returns:
        ExtendedStudentAccount: 学生账号
    """
    cookie = decrypt(cookie)
    session = set_user_session(cookie)
    account = ExtendedStudentAccount(session)
    updated = account.update_login_status()
    student_account = account.set_base_info()
    if updated:
        try:
            # 检查是否在 Flask 上下文中
            from flask import has_app_context
            if has_app_context():
                from app.database import db
                from app.database.models import ZhiXueStudentAccount
                account = db.session.get(ZhiXueStudentAccount, student_account.id)
                if account:
                    account.cookie = encrypt(student_account.get_cookie())
                    db.session.commit()
        except ImportError:
            pass

    return student_account
