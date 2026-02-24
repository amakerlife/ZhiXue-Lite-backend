"""
pytest 配置文件
"""
import os
import pytest


# 在导入 app 之前设置测试环境变量，防止加载生产配置
os.environ["FLASK_ENV"] = "testing"

# 使用环境变量中的 DATABASE_URL（CI 环境），否则使用 SQLite 内存数据库（本地开发）
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

os.environ["TURNSTILE_ENABLED"] = "False"
os.environ["CAPTCHA_URL"] = "http://fake-captcha.test"
os.environ["FONT_PATH"] = "/fake/font/path"

from datetime import datetime
from unittest.mock import Mock
from app import create_app
from app.database import db as _db
from app.database.models import User, School, ZhiXueStudentAccount, ZhiXueTeacherAccount
from app.utils.crypto import encrypt


# Flask 应用和数据库 Fixtures

@pytest.fixture(scope="session")
def app():
    """
    创建测试用的 Flask 应用实例
    """
    # 创建应用实例，会自动加载 TestingConfig
    app = create_app()

    return app


@pytest.fixture(scope="function")
def db(app):
    """
    创建测试用的数据库
    """
    with app.app_context():
        _db.create_all()  # 创建所有表
        yield _db  # 在这里暂停，让测试函数使用数据库
        _db.session.remove()  # 清理会话
        _db.drop_all()  # 删除所有表


@pytest.fixture
def client(app, db):
    """
    创建测试客户端
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    创建 CLI 测试运行器
    """
    return app.test_cli_runner()


@pytest.fixture
def regular_user(db):
    """
    创建标准测试用户（普通用户）

    默认配置：
    - 用户名：testuser
    - 邮箱：test@example.com
    - 角色：user
    - 权限：10110（SELF 级基础权限）
    - 密码：password123
    - 已验证邮箱
    """
    user = User(
        username="testuser",
        email="test@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
        is_active=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_user(db):
    """
    创建管理员用户

    默认配置：
    - 用户名：admin
    - 邮箱：admin@example.com
    - 角色：admin
    - 权限：33333（全部权限最高级别）
    - 密码：admin123
    - 已验证邮箱
    """
    admin = User(
        username="admin",
        email="admin@example.com",
        role="admin",
        permissions="33333",
        created_at=datetime.utcnow(),
        email_verified=True,
        is_active=True
    )
    admin.set_password("admin123")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def unverified_user(db):
    """
    创建邮箱未验证的测试用户

    默认配置：
    - 用户名：unverified
    - 邮箱：unverified@example.com
    - 角色：user
    - 权限：10110（SELF 级基础权限）
    - 密码：password123
    - 邮箱未验证
    - 带有验证 token
    """
    user = User(
        username="unverified",
        email="unverified@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=False,
        is_active=True
    )
    user.set_password("password123")
    user.generate_email_verification_token()
    db.session.add(user)
    db.session.commit()
    return user


# 公共测试数据 Fixtures

@pytest.fixture
def test_school(db):
    """
    创建测试学校

    学校 ID：school_001
    学校名称：测试中学
    """
    school = School(
        id="school_001",
        name="测试中学"
    )
    db.session.add(school)
    db.session.commit()
    return school


@pytest.fixture
def test_zhixue_account(db, test_school):
    """
    创建测试智学网账号

    依赖：test_school fixture
    配置：
    - 账号 ID：zhixue_001
    - 用户名：zhixue_student
    - 真实姓名：张三
    - 关联学校：school_001
    """
    account = ZhiXueStudentAccount(
        id="zhixue_001",
        username="zhixue_student",
        password=encrypt("password"),
        realname="张三",
        cookie=encrypt("fake_cookie_string"),
        school_id=test_school.id
    )
    db.session.add(account)
    db.session.commit()
    return account


@pytest.fixture
def test_teacher_account(db, test_school):
    """
    创建测试智学网教师账号

    依赖：test_school fixture
    配置：
    - 账号 ID：teacher_001
    - 用户名：zhixue_teacher
    - 真实姓名：李老师
    - 登录方式：changyan
    - 关联学校：school_001
    """
    teacher = ZhiXueTeacherAccount(
        id="teacher_001",
        username="zhixue_teacher",
        password=encrypt("teacher_password"),
        realname="李老师",
        cookie=encrypt("fake_teacher_cookie"),
        login_method="changyan",
        school_id=test_school.id
    )
    db.session.add(teacher)
    db.session.commit()
    return teacher


# 公共辅助函数

def login_as_user(client, user, password="password123"):
    """
    辅助函数：以指定用户身份登录

    Args:
        client: Flask 测试客户端
        user: User 模型实例
        password: 用户密码（默认：password123）

    Returns:
        client: 登录后的客户端（支持链式调用）

    Raises:
        AssertionError: 如果登录失败

    Example:
        login_as_user(client, test_user)
        response = client.get("/user/me")
    """
    response = client.post("/user/login", json={
        "login": user.username,
        "password": password
    })
    assert response.status_code == 200, f"登录失败: {response.get_json()}"
    return client


def login_as_admin(client, admin_user, password="admin123"):
    """
    辅助函数：以管理员身份登录

    Args:
        client: Flask 测试客户端
        admin_user: 管理员 User 对象
        password: 管理员密码（默认：admin123）

    Returns:
        client: 登录后的客户端

    Raises:
        AssertionError: 如果登录失败

    Example:
        login_as_admin(client, admin_user)
        response = client.get("/admin/list/users")
    """
    response = client.post("/user/login", json={
        "login": admin_user.username,
        "password": password
    })
    assert response.status_code == 200, f"管理员登录失败: {response.get_json()}"
    return client


# Pytest 钩子函数

def pytest_sessionfinish(session, exitstatus):
    """
    pytest 钩子：测试会话结束后自动清理
    """
    import shutil
    from pathlib import Path

    # flask_session 目录路径（在项目根目录）
    flask_session_dir = Path(__file__).parent.parent / "flask_session"

    # 如果目录存在，删除它
    if flask_session_dir.exists():
        shutil.rmtree(flask_session_dir)
        print(f"\n[Test Cleanup] Removed flask_session directory: {flask_session_dir}")


# Mock Fixtures for zhixuewang

@pytest.fixture
def mock_zhixue_student_account():
    """
    创建 mock 智学网学生账号对象

    模拟 ExtendedStudentAccount 对象，包含：
    - id: 学生 ID
    - name: 学生姓名
    - clazz.school.id: 学校 ID
    - clazz.school.name: 学校名称
    - get_cookie(): 返回 cookie 字符串
    """
    mock_account = Mock(spec=[])
    mock_account.id = "mock_student_001"
    mock_account.name = "学生 001"
    mock_account.is_parent = False
    mock_account.clazz = Mock()
    mock_account.clazz.school = Mock()
    mock_account.clazz.school.id = "mock_school_001"
    mock_account.clazz.school.name = "学校 001"
    mock_account.get_cookie = Mock(return_value="mock_cookie_string")
    return mock_account


@pytest.fixture
def mock_zhixue_teacher_account():
    """
    创建 mock 智学网教师账号对象

    模拟 ExtendedTeacherAccount 对象，包含：
    - id: 教师 ID
    - name: 教师姓名
    - school.id: 学校 ID
    - school.name: 学校名称
    - get_cookie(): 返回 cookie 字符串
    """
    mock_account = Mock()
    mock_account.id = "mock_teacher_001"
    mock_account.name = "教师 001"
    mock_account.school = Mock()
    mock_account.school.id = "mock_school_002"
    mock_account.school.name = "学校 002"
    mock_account.get_cookie.return_value = "mock_teacher_cookie_string"
    return mock_account
