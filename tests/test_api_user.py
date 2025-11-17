"""
用户 API 测试

这个文件测试用户相关的 API 端点：注册、登录、认证等
"""
from datetime import datetime
from unittest.mock import patch
from app.database.models import User


def test_user_login_success(client, regular_user):
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


def test_user_login_wrong_password(client, regular_user):
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


def test_user_login_email(client, regular_user):
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


def test_user_logout(client, regular_user):
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


def test_user_signup_success(client, db):
    """测试用户注册成功"""
    response = client.post("/user/signup", json={
        "username": "newuser",
        "password": "password123",
        "email": "new@example.com"
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert "注册成功" in data["message"]
    user = db.session.query(User).filter_by(username="newuser").first()
    assert user is not None
    assert user.email == "new@example.com"


def test_user_signup_missing_fields(client):
    """测试注册时缺少必要字段"""
    response = client.post("/user/signup", json={
        "username": "test"
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "缺少必要字段" in data["message"]


def test_user_signup_invalid_username(client):
    """测试用户名包含 @ 符号（不合法）"""
    response = client.post("/user/signup", json={
        "username": "test@user",
        "password": "password123",
        "email": "test@example.com"
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "用户名不合法" in data["message"]


def test_user_signup_duplicate_username(client, regular_user):
    """测试用户名已被使用"""
    response = client.post("/user/signup", json={
        "username": "testuser",
        "password": "password123",
        "email": "different@example.com"
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "用户名已被使用" in data["message"]


def test_user_signup_duplicate_email(client, regular_user):
    """测试邮箱已被使用"""
    response = client.post("/user/signup", json={
        "username": "anotheruser",
        "password": "password123",
        "email": "test@example.com"
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "邮箱已被使用" in data["message"]


def test_update_user_info_success(db, client, regular_user):
    """测试成功更新用户信息"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.put("/user/me", json={
        "email": "new_email@example.com",
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "用户信息已更新" in data["message"]
    user = db.session.query(User).filter_by(username="testuser").first()
    assert user.email == "new_email@example.com"


def test_update_user_info_invalid_field(db, client, regular_user):
    """测试更新用户信息时提供无效字段"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.put("/user/me", json={
        "permission": "33333"
    })

    assert response.status_code == 200
    user = db.session.query(User).filter_by(username="testuser").first()
    assert user.permissions == "10110"


def test_update_user_password(db, client, regular_user):
    """测试成功更新用户密码"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.put("/user/me", json={
        "currentPassword": "password123",
        "password": "newpassword123"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "用户信息已更新" in data["message"]

    client.post("/user/logout")

    response = client.post("/user/login", json={
        "login": "testuser",
        "password": "newpassword123"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


def test_update_user_password_wrong_current(db, client, regular_user):
    """测试更新用户密码时提供错误的当前密码"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.put("/user/me", json={
        "currentPassword": "wrongpassword",
        "password": "newpassword123"
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "当前密码错误" in data["message"]


def test_update_user_info_requires_login(client):
    """测试未登录无法更新用户信息"""
    response = client.put("/user/me", json={
        "email": "new_email@example.com",
    })

    assert response.status_code == 401


def test_show_self_info(client, regular_user):
    """测试用户查看自己的信息"""
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
    assert "permissions" in data["user"]
    assert "password" not in data["user"]

    # 验证普通用户不会收到 su_info 字段
    assert "su_info" not in data["user"]


def test_show_other_user_info(client, regular_user, db):
    """测试用户查看其他用户的信息"""
    other_user = User(
        username="otheruser",
        email="other@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True
    )
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.commit()
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })
    response = client.get(f"/user/show/{other_user.id}")
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "您无权访问该页面" in data["message"]


def test_zhixue_unbind_success(client, regular_user, test_zhixue_account, db):
    """测试成功解绑智学网账号"""
    # 先绑定智学网账号
    regular_user.zhixue = test_zhixue_account
    db.session.commit()

    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/zhixue/unbind")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "已解绑" in data["message"]

    # 验证用户的智学网账号确实被解绑
    db.session.refresh(regular_user)
    assert regular_user.zhixue is None


def test_zhixue_unbind_not_bound(client, regular_user, db):
    """测试未绑定时解绑智学网账号（应该也成功）"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    # 确保用户未绑定
    assert regular_user.zhixue is None

    response = client.post("/user/zhixue/unbind")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


def test_zhixue_unbind_requires_login(client):
    """测试未登录无法解绑智学网账号"""
    response = client.post("/user/zhixue/unbind")

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


def test_zhixue_binding_info_success(client, regular_user, test_zhixue_account, db):
    """测试成功获取智学网账号绑定信息"""
    # 先绑定智学网账号
    regular_user.zhixue = test_zhixue_account
    db.session.commit()

    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.get("/user/zhixue/binding_info")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "binding_info" in data
    assert isinstance(data["binding_info"], list)
    # 验证绑定信息中包含当前用户
    assert any(user["username"] == "testuser" for user in data["binding_info"])


def test_zhixue_binding_info_not_bound(client, regular_user):
    """测试未绑定时获取智学网账号绑定信息"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    # 确保用户未绑定
    assert regular_user.zhixue is None

    response = client.get("/user/zhixue/binding_info")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "未绑定" in data["message"]


# 邮件验证功能测试


@patch("app.user.routes.is_email_verification_enabled")
def test_email_verify_success(mock_is_enabled, client, unverified_user, db):
    """测试成功验证邮箱"""
    mock_is_enabled.return_value = True

    client.post("/user/login", json={
        "login": "unverified",
        "password": "password123"
    })

    token = unverified_user.email_verification_token

    response = client.get(f"/user/email/verify/{token}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "邮箱验证成功"

    db.session.refresh(unverified_user)
    assert unverified_user.email_verified is True
    assert unverified_user.email_verification_token is None
    assert unverified_user.email_verification_token_expires is None


@patch("app.user.routes.is_email_verification_enabled")
def test_email_verify_invalid_token(mock_is_enabled, client, unverified_user):
    """测试使用无效 token 验证邮箱"""
    mock_is_enabled.return_value = True

    client.post("/user/login", json={
        "login": "unverified",
        "password": "password123"
    })

    invalid_token = "invalid_token_12345"

    response = client.get(f"/user/email/verify/{invalid_token}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "无效的验证令牌" in data["message"]


@patch("app.user.routes.is_email_verification_enabled")
def test_email_verify_expired_token(mock_is_enabled, client, unverified_user, db):
    """测试使用过期 token 验证邮箱"""
    mock_is_enabled.return_value = True

    client.post("/user/login", json={
        "login": "unverified",
        "password": "password123"
    })

    token = unverified_user.email_verification_token
    from datetime import timedelta
    unverified_user.email_verification_token_expires = datetime.utcnow() - timedelta(hours=1)
    db.session.commit()

    response = client.get(f"/user/email/verify/{token}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "已过期" in data["message"]


@patch("app.user.routes.is_email_verification_enabled")
def test_email_verify_disabled(mock_is_enabled, client, unverified_user):
    """测试邮件验证功能未启用时的行为"""
    mock_is_enabled.return_value = False

    client.post("/user/login", json={
        "login": "unverified",
        "password": "password123"
    })

    token = unverified_user.email_verification_token

    response = client.get(f"/user/email/verify/{token}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "邮件验证功能未启用" in data["message"]


def test_email_verify_requires_login(client, unverified_user):
    """测试未登录无法验证邮箱"""
    token = unverified_user.email_verification_token

    response = client.get(f"/user/email/verify/{token}")

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


@patch("app.user.routes.create_task")
@patch("app.user.routes.is_email_verification_enabled")
def test_resend_verification_email_success(mock_is_enabled, mock_create_task, client, unverified_user, db):
    """测试成功重新发送验证邮件"""
    mock_is_enabled.return_value = True

    client.post("/user/login", json={
        "login": "unverified",
        "password": "password123"
    })

    old_token = unverified_user.email_verification_token

    response = client.post("/user/email/resend-verification")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "验证邮件已发送" in data["message"]

    db.session.refresh(unverified_user)
    new_token = unverified_user.email_verification_token
    assert new_token is not None
    assert new_token != old_token

    mock_create_task.assert_called_once()
    call_args = mock_create_task.call_args
    assert call_args[1]["task_type"] == "send_verification_email"
    assert call_args[1]["user_id"] == unverified_user.id
    assert call_args[1]["parameters"]["email_type"] == "reverify"
    assert call_args[1]["parameters"]["to_email"] == "unverified@example.com"
    assert call_args[1]["parameters"]["username"] == "unverified"
    assert call_args[1]["parameters"]["token"] == new_token


@patch("app.user.routes.is_email_verification_enabled")
def test_resend_verification_email_already_verified(mock_is_enabled, client, regular_user):
    """测试邮箱已验证时无法重新发送验证邮件"""
    mock_is_enabled.return_value = True

    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/email/resend-verification")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "邮箱已验证" in data["message"]


@patch("app.user.routes.is_email_verification_enabled")
def test_resend_verification_email_disabled(mock_is_enabled, client, unverified_user):
    """测试邮件验证功能未启用时无法重新发送"""
    mock_is_enabled.return_value = False

    client.post("/user/login", json={
        "login": "unverified",
        "password": "password123"
    })

    response = client.post("/user/email/resend-verification")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "邮件验证功能未启用" in data["message"]


def test_resend_verification_email_requires_login(client):
    """测试未登录无法重新发送验证邮件"""
    response = client.post("/user/email/resend-verification")

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


def test_zhixue_binding_info_requires_login(client):
    """测试未登录无法获取智学网账号绑定信息"""
    response = client.get("/user/zhixue/binding_info")

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


@patch("app.user.routes.login_student")
def test_zhixue_bind_success(mock_login_student, client, regular_user, mock_zhixue_student_account, db):
    """测试成功绑定智学网账号（使用 mock）"""
    mock_login_student.return_value = mock_zhixue_student_account

    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/zhixue/bind", json={
        "username": "zhixue_test",
        "password": "zhixue_pass"
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "已绑定" in data["message"]

    mock_login_student.assert_called_once_with("zhixue_test", "zhixue_pass")

    db.session.refresh(regular_user)
    assert regular_user.zhixue is not None
    assert regular_user.zhixue.username == "zhixue_test"


@patch("app.user.routes.login_student")
def test_zhixue_bind_login_failure(mock_login_student, client, regular_user):
    """测试绑定时智学网登录失败"""
    mock_login_student.side_effect = Exception("用户名或密码错误")

    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/zhixue/bind", json={
        "username": "wrong_user",
        "password": "wrong_pass"
    })

    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "连接智学网失败" in data["message"]


def test_zhixue_bind_already_bound(client, regular_user, test_zhixue_account, db):
    """测试用户已绑定时无法再次绑定"""
    regular_user.zhixue = test_zhixue_account
    db.session.commit()

    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/zhixue/bind", json={
        "username": "another_user",
        "password": "another_pass"
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "已绑定" in data["message"]


def test_zhixue_bind_requires_login(client):
    """测试未登录无法绑定智学网账号"""
    response = client.post("/user/zhixue/bind", json={
        "username": "zhixue_user",
        "password": "zhixue_pass"
    })

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


def test_zhixue_bind_missing_fields(client, regular_user):
    """测试绑定时缺少必要字段"""
    client.post("/user/login", json={
        "login": "testuser",
        "password": "password123"
    })

    response = client.post("/user/zhixue/bind", json={
        "username": "zhixue_user"
        # 缺少 password
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "缺少必要字段" in data["message"]
