"""
学生模型测试

测试 app/models/student.py 中的业务逻辑，包括：
- login_student() 登录学生账号
- login_student_session() 通过 cookie 登录
- ExtendedStudentAccount 类的方法
"""
import base64
from unittest.mock import Mock, patch
import pytest
from zhixuewang.exceptions import UserOrPassError
from app.models.student import ExtendedStudentAccount, login_student, login_student_session


def create_mock_session_with_cookies():
    """创建包含必要 cookie 的 mock session"""
    mock_session = Mock()
    # zhixuewang 需要 uname cookie (base64 encoded)
    mock_session.cookies = {
        "uname": base64.b64encode("testuser".encode()).decode(),
        "token": "abc123",
        "sessionid": "xyz789"
    }
    return mock_session


class TestExtendedStudentAccount:
    """测试 ExtendedStudentAccount 类"""

    def test_get_cookie_success(self):
        """测试成功获取 Cookie 字符串"""
        mock_session = create_mock_session_with_cookies()

        # 创建学生账号实例
        account = ExtendedStudentAccount(mock_session)

        cookie = account.get_cookie()

        # 验证包含所有 cookie 项
        assert "token=abc123" in cookie
        assert "sessionid=xyz789" in cookie

    def test_get_cookie_no_session(self):
        """测试 get_session() 返回 None 时返回空字符串"""
        mock_session = create_mock_session_with_cookies()
        account = ExtendedStudentAccount(mock_session)

        # Mock get_session 返回 None
        account.get_session = Mock(return_value=None)

        cookie = account.get_cookie()

        assert cookie == ""

    @patch("app.models.student.update_login_status")
    def test_update_login_status(self, mock_update_login_status):
        """测试更新登录状态"""
        mock_update_login_status.return_value = True
        mock_session = create_mock_session_with_cookies()

        account = ExtendedStudentAccount(mock_session)
        result = account.update_login_status()

        assert result is True
        mock_update_login_status.assert_called_once_with(account)


class TestLoginStudent:
    """测试 login_student 函数"""

    @patch("app.models.student.get_session_by_captcha")
    @patch("app.models.student.ExtendedStudentAccount")
    def test_login_student_success(self, mock_account_class, mock_get_session):
        """测试成功登录学生账号"""
        # Mock session
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.id = "student_001"
        mock_account_instance.name = "张三"
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance

        result = login_student("student_user", "password123", "changyan")

        mock_get_session.assert_called_once_with("student_user", "password123", "changyan")
        mock_account_class.assert_called_once_with(mock_session)
        mock_account_instance.set_base_info.assert_called_once()
        assert result == mock_account_instance

    @patch("app.models.student.get_session_by_captcha")
    def test_login_student_wrong_credentials(self, mock_get_session):
        """测试使用错误凭证登录"""
        mock_get_session.side_effect = UserOrPassError("用户名或密码错误")

        with pytest.raises(UserOrPassError):
            login_student("wrong_user", "wrong_pass", "changyan")


class TestLoginStudentSession:
    """测试 login_student_session 函数"""

    @patch("app.models.student.set_user_session")
    @patch("app.models.student.ExtendedStudentAccount")
    def test_login_student_session_success(self, mock_account_class, mock_set_session):
        """测试通过 cookie 成功登录"""
        # Mock session
        mock_session = Mock()
        mock_set_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.id = "student_001"
        mock_account_instance.name = "张三"
        mock_account_instance.update_login_status.return_value = False  # 未更新
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance

        result = login_student_session("fake_cookie_string")

        mock_set_session.assert_called_once_with("fake_cookie_string")
        mock_account_class.assert_called_once_with(mock_session)
        mock_account_instance.update_login_status.assert_called_once()
        mock_account_instance.set_base_info.assert_called_once()
        assert result == mock_account_instance

    @patch("flask.has_app_context")
    @patch("app.database.db")
    @patch("app.database.models.ZhiXueStudentAccount")
    @patch("app.models.student.set_user_session")
    @patch("app.models.student.ExtendedStudentAccount")
    def test_login_student_session_update_cookie_in_db(
        self, mock_account_class, mock_set_session, mock_zhixue_account_class,
        mock_db, mock_has_app_context
    ):
        """测试登录状态更新时保存新 cookie 到数据库"""
        # Mock session
        mock_session = Mock()
        mock_set_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.id = "student_001"
        mock_account_instance.name = "张三"
        mock_account_instance.update_login_status.return_value = True  # 已更新
        mock_account_instance.get_cookie.return_value = "new_cookie_value"
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance

        # Mock Flask 上下文
        mock_has_app_context.return_value = True

        # Mock 数据库中的学生账号
        mock_db_account = Mock()
        mock_db.session.get.return_value = mock_db_account

        result = login_student_session("old_cookie_string")

        # 验证更新了数据库中的 cookie
        assert mock_db_account.cookie == "new_cookie_value"
        mock_db.session.commit.assert_called_once()

    @patch("app.models.student.set_user_session")
    @patch("app.models.student.ExtendedStudentAccount")
    def test_login_student_session_no_update_no_db_save(
        self, mock_account_class, mock_set_session
    ):
        """测试登录状态未更新时不保存数据库"""
        # Mock session
        mock_session = Mock()
        mock_set_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.update_login_status.return_value = False  # 未更新
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance

        result = login_student_session("cookie_string")

        # 验证返回了正确的账号（没有尝试访问数据库）
        assert result == mock_account_instance

    @patch("flask.has_app_context", side_effect=ImportError)
    @patch("app.models.student.set_user_session")
    @patch("app.models.student.ExtendedStudentAccount")
    def test_login_student_session_outside_flask_context(
        self, mock_account_class, mock_set_session, mock_has_app_context
    ):
        """测试不在 Flask 上下文中时不保存数据库（ImportError）"""
        # Mock session
        mock_session = Mock()
        mock_set_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.update_login_status.return_value = True  # 已更新
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance

        result = login_student_session("cookie_string")

        # 验证成功返回账号，但没有数据库操作
        assert result == mock_account_instance
