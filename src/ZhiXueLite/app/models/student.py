import requests
from zhixuewang.student import StudentAccount

from app.utils.login_zhixue import set_user_session, update_login_status, get_session_by_captcha


class ExtendedStudentAccount(StudentAccount):
    """
    主要用于临时修复上游问题
    """

    def update_login_status(self):
        """
        更新登录状态
        """
        update_login_status(self)

    def get_cookie(self) -> str:
        """
        获取 Cookie 字符串
        """
        if not self.get_session():
            return ""
        cookie_items = []
        for name, value in self.get_session().cookies.items():
            cookie_items.append(f"{name}={value}")
        return "; ".join(cookie_items)


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
        cookie (str): Cookie 字符串

    Returns:
        ExtendedStudentAccount: 学生账号
    """
    session = set_user_session(cookie)
    account = ExtendedStudentAccount(session)
    account.update_login_status()
    return account.set_base_info()
