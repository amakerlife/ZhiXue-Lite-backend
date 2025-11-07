"""
用户 API 测试

这个文件测试用户相关的 API 端点：注册、登录、认证等
"""
from datetime import datetime
from app.database.models import User
import pytest


@pytest.fixture
def test_user(db):
    """
    创建一个测试用户的 fixture
    """
    user = User(
        username="testuser",
        email="test@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True  # 测试时直接设置为已验证
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


def test_user_login_success(client, test_user):
    """
    测试用户登录成功
    """
    response = client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    assert response.status_code == 200

    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "登录成功"
    assert "user" in data
    assert data["user"]["username"] == "testuser"


def test_user_login_wrong_password(client, test_user):
    """
    测试错误密码登录
    """
    response = client.post("/user/login", json={
        "login": "testuser",
        "password": "wrongpassword"
    })

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert "密码错误" in data["message"]


def test_user_login_email(client, test_user):
    """
    测试使用邮箱登录
    """
    response = client.post("/user/login", json={
        "login": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["user"]["username"] == "testuser"


def test_get_current_user_authenticated(client, test_user):
    """
    测试获取当前用户信息（已登录）
    """
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.get("/user/me")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["user"]["username"] == "testuser"
    assert data["user"]["email"] == "test@example.com"


def test_get_current_user_unauthenticated(client):
    """
    测试未登录访问受保护端点
    """
    response = client.get("/user/me")

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


def test_banned_user_login(client, db):
    """
    测试被封禁用户无法登录
    """
    user = User(
        username="banneduser",
        email="banned@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
        is_active=False
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    response = client.post("/user/login", json={
        "login": "banneduser",
        "password": "password123"
    })

    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "用户已被禁用" in data["message"]


def test_user_logout(client, test_user):
    """
    测试用户登出功能
    """
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/logout")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "登出" in data["message"]

    response = client.get("/user/me")
    assert response.status_code == 401
