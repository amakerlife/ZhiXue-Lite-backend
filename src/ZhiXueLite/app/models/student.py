import re

from flask import json
from zhixuewang.models import StuClass, School
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

    def set_parent_info(self):
        """
        设置家长账号信息
        """
        self.update_login_status()
        self.is_parent = True
        r = self._session.get(
            "https://www.zhixue.com/container/container/parent/index/"
        )
        if not r.ok:
            raise ValueError(f"Error fetching parent index: {r.text}")
        current_child_match = re.search(r"var\s+currentChild\s*=\s*(\{.*?\});", r.text, re.DOTALL)
        if not current_child_match:
            raise ValueError("currentChild not found in parent index page")
        current_child = json.loads(current_child_match.group(1))
        if current_child.get("id") is None or current_child.get("name") is None:
            raise ValueError(f"currentChild data seems lost: {current_child}")
        self.name = current_child["name"]
        self.child_id = current_child["id"]
        self.clazz = StuClass(school=School(id=current_child["school"]["schoolId"], name=current_child["school"]["schoolName"]))

        r = self._session.get(
            "https://www.zhixue.com/apicourse/web/student/get/userInfo",
            headers={"Referer": "https://www.zhixue.com/course/"}
        )
        if not r.ok:
            raise ValueError(f"Error fetching user info: {r.text}")
        data = r.json()["result"]["user"]
        self.id = data["id"]
        self.role = data["role"]
        self.username = data["loginName"]

        # r = self._session.get(
        #     "https://www.zhixue.com/container/contact/parent/clazzs"
        # )
        # if not r.ok:
        #     raise ValueError(f"Error fetching class info: {r.text}")
        # data = r.json()["school"]
        # self.clazz = StuClass(school=School(id=data["id"], name=data["name"]))

        # r = self._session.get(
        #     "https://www.zhixue.com/addon/error/book/index"
        # )
        # if not r.ok:
        #     raise ValueError(f"Error fetching token: {r.text}")
        # token = r.json()["result"]
        # print(r.text)
        # r = self._session.get(
        #     "https://www.zhixue.com/zhixuebao/base/common/getUserInfo",
        #     headers={"Token": token, "Xtoken": token}
        # )
        # if not r.ok:
        #     raise ValueError(f"Error fetching child info: {r.text}")
        # self.child_id = r.json()["result"]["curChildId"]

        return self

    def set_base_info(self):
        if getattr(self, "is_parent", False):
            return self.set_parent_info()
        return super().set_base_info()


def login_student(username: str, password: str, method="changyan", is_parent=False) -> ExtendedStudentAccount:
    """
    登录学生账号

    Args:
        username (str): 用户名
        password (str): 密码
        method (str): 验证码获取方式，默认为 "changyan"
        is_parent (bool): 是否为家长账号，默认为 False

    Returns:
        ExtendedStudentAccount: 学生账号
    """
    session = get_session_by_captcha(username, password, method)
    account = ExtendedStudentAccount(session)
    account.is_parent = is_parent
    return account.set_base_info()


def login_student_session(cookie: str, is_parent: bool) -> ExtendedStudentAccount:
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
    account.is_parent = is_parent
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
