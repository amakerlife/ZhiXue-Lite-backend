from zhixuewang.student import StudentAccount

from ZhiXueLite.app.utils.login_zhixue import update_login_status, get_session_by_captcha


class ExtendedStudentAccount(StudentAccount):
    """
    主要用于临时修复上游问题
    """

    def update_login_status(self):
        """
        更新登录状态
        """
        update_login_status(self)


def login_student(username: str, password: str, method: str = "changyan") -> ExtendedStudentAccount:
    """登录学生账号

    Args:
        username (str): 用户名
        password (str): 密码

    Returns:
        ExtendedStudentAccount: 学生账号
    """
    session = get_session_by_captcha(username, password, method)
    return ExtendedStudentAccount(session).set_base_info()
