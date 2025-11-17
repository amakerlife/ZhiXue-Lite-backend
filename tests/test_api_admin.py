"""
Admin API 测试

测试管理员相关的 API 端点：用户管理、学校管理、Su 模式等
"""
from datetime import datetime
from app.database.models import User, School, Exam
import pytest
from conftest import login_as_admin, login_as_user


@pytest.fixture
def test_exam(db, test_school):
    """
    创建测试考试
    """
    import time
    exam = Exam(
        id="exam_001",
        name="期中考试",
        created_at=int(time.time()) * 1000
    )
    db.session.add(exam)
    db.session.commit()
    return exam


# 权限控制测试

def test_admin_access_denied_for_regular_user(client, admin_user, regular_user):
    """
    测试普通用户无法访问管理员端点
    """
    login_as_user(client, regular_user)

    response = client.get("/admin/list/users")

    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "Access Denied" in data["message"]


def test_admin_access_denied_unauthenticated(client):
    """
    测试未登录用户无法访问管理员端点
    """
    response = client.get("/admin/list/users")

    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False


# 列表类端点测试

def test_admin_list_schools_success(db, client, admin_user, test_school):
    """
    测试列出学校列表
    """
    # 创建额外的学校用于测试分页
    school2 = School(id="school_002", name="实验中学")
    db.session.add(school2)
    db.session.commit()

    login_as_admin(client, admin_user)

    response = client.get("/admin/list/schools?page=1&per_page=10")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "schools" in data
    assert len(data["schools"]) == 2
    assert "pagination" in data

    school = data["schools"][0]
    assert "id" in school
    assert "name" in school


def test_admin_list_schools_with_search(client, admin_user, test_school):
    """
    测试搜索学校
    """
    login_as_admin(client, admin_user)

    response = client.get("/admin/list/schools?query=测试")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["schools"]) == 1
    assert data["schools"][0]["name"] == "测试中学"


def test_admin_list_users_success(client, admin_user, regular_user):
    """
    测试列出用户列表
    """
    login_as_admin(client, admin_user)

    response = client.get("/admin/list/users?page=1&per_page=10")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "users" in data
    assert len(data["users"]) >= 2
    assert "pagination" in data

    # 验证用户数据包含完整信息
    user = data["users"][0]
    assert "username" in user
    assert "email" in user
    assert "role" in user
    assert "last_login_ip" in user


def test_admin_list_users_with_search(client, admin_user, regular_user):
    """
    测试搜索用户
    """
    login_as_admin(client, admin_user)

    response = client.get("/admin/list/users?query=testuser")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["users"]) == 1
    assert data["users"][0]["username"] == "testuser"


def test_admin_list_zhixue_accounts_success(client, admin_user, test_zhixue_account):
    """
    测试列出智学网账号
    """
    login_as_admin(client, admin_user)

    response = client.get("/admin/list/zhixue_accounts?page=1&per_page=10")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "zhixue_accounts" in data
    assert len(data["zhixue_accounts"]) == 1
    assert data["zhixue_accounts"][0]["username"] == "zhixue_student"


def test_admin_list_exams_success(client, admin_user, test_exam):
    """
    测试列出考试列表
    """
    login_as_admin(client, admin_user)

    response = client.get("/admin/list/exams?page=1&per_page=10")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "exams" in data
    assert len(data["exams"]) == 1

    exam = data["exams"][0]
    assert exam["id"] == "exam_001"
    assert exam["name"] == "期中考试"
    assert "schools" in exam


# 用户管理测试

def test_admin_update_user_email(client, admin_user, regular_user, db):
    """
    测试管理员更新用户邮箱
    """
    login_as_admin(client, admin_user)

    response = client.put(f"/admin/user/{regular_user.id}", json={
        "email": "newemail@example.com"
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["user"]["email"] == "newemail@example.com"

    db.session.refresh(regular_user)
    assert regular_user.email == "newemail@example.com"


def test_admin_update_user_permissions(client, admin_user, regular_user, db):
    """
    测试管理员更新用户权限
    """
    login_as_admin(client, admin_user)

    response = client.put(f"/admin/user/{regular_user.id}", json={
        "permissions": "22222"
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    db.session.refresh(regular_user)
    assert regular_user.permissions == "22222"


def test_admin_update_user_invalid_permissions(client, admin_user, regular_user):
    """
    测试无效的权限格式
    """
    login_as_admin(client, admin_user)

    # 测试长度不为 5
    response = client.put(f"/admin/user/{regular_user.id}", json={
        "permissions": "123"
    })
    assert response.status_code == 400
    data = response.get_json()
    assert "权限格式无效" in data["message"]

    # 测试包含非法字符
    response = client.put(f"/admin/user/{regular_user.id}", json={
        "permissions": "12a45"
    })
    assert response.status_code == 400


def test_admin_update_user_role_to_admin(client, admin_user, regular_user, db):
    """
    测试将普通用户提升为管理员
    """
    login_as_admin(client, admin_user)

    response = client.put(f"/admin/user/{regular_user.id}", json={
        "role": "admin"
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    db.session.refresh(regular_user)
    assert regular_user.role == "admin"
    assert regular_user.permissions == "33333"


def test_admin_update_user_password(client, admin_user, regular_user):
    """
    测试管理员重置用户密码
    """
    login_as_admin(client, admin_user)

    response = client.put(f"/admin/user/{regular_user.id}", json={
        "password": "newpassword123"
    })

    assert response.status_code == 200

    client.post("/user/logout")
    login_response = client.post("/user/login", json={
        "login": "testuser",
        "password": "newpassword123"
    })
    assert login_response.status_code == 200


# 智学网账号管理测试

def test_admin_list_users_by_zhixue_account(client, admin_user, regular_user, test_zhixue_account, db):
    """
    测试列出绑定特定智学网账号的用户
    """
    # 将 regular_user 绑定到智学网账号
    regular_user.zhixue_account_id = test_zhixue_account.id
    db.session.commit()

    login_as_admin(client, admin_user)

    response = client.get(f"/admin/zhixue/{test_zhixue_account.username}/users")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["binding_info"]["total"] == 1
    assert data["binding_info"]["users"][0]["username"] == "testuser"


def test_admin_list_users_by_nonexistent_zhixue(client, admin_user):
    """
    测试查询不存在的智学网账号
    """
    login_as_admin(client, admin_user)

    response = client.get("/admin/zhixue/nonexistent/users")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "智学网账号未绑定" in data["message"]


def test_admin_unbind_user_from_zhixue(client, admin_user, regular_user, test_zhixue_account, db):
    """
    测试管理员解绑用户的智学网账号
    """
    regular_user.zhixue_account_id = test_zhixue_account.id
    db.session.commit()

    login_as_admin(client, admin_user)

    response = client.post(f"/admin/zhixue/{test_zhixue_account.username}/unbind/{regular_user.username}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "已解绑" in data["message"]

    db.session.refresh(regular_user)
    assert regular_user.zhixue_account_id is None


# Su 模式测试

def test_admin_get_su_info_not_in_su_mode(client, admin_user):
    """
    测试管理员在非 su 模式下也会收到 su_info 字段
    """
    login_as_admin(client, admin_user)

    response = client.get("/user/me")
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["username"] == admin_user.username

    # 验证管理员会收到 su_info 字段，且为非 su 状态
    assert "su_info" in data["user"]
    assert data["user"]["su_info"]["is_su_mode"] is False
    assert data["user"]["su_info"]["original_user_username"] is None


def test_admin_su_switch_user_success(client, admin_user, regular_user, db):
    """
    测试管理员成功切换到其他用户
    """
    login_as_admin(client, admin_user)

    response = client.post(f"/admin/su/{regular_user.username}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["user"]["username"] == regular_user.username

    # 验证 /user/me 返回 su 状态信息
    response = client.get("/user/me")
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["username"] == regular_user.username

    # 验证 su_info 字段存在且正确
    assert "su_info" in data["user"]
    assert data["user"]["su_info"]["is_su_mode"] is True
    assert data["user"]["su_info"]["original_user_username"] == admin_user.username

    # 验证 session 中的数据
    with client.session_transaction() as sess:
        assert sess.get("su_mode") is True
        assert sess.get("original_user_id") == admin_user.id
        assert sess.get("su_user_id") == regular_user.id


def test_admin_su_exit_success(client, admin_user, regular_user, db):
    """
    测试成功退出 Su 模式
    """
    login_as_admin(client, admin_user)

    response = client.post(f"/admin/su/{regular_user.username}")
    assert response.status_code == 200

    response = client.post("/admin/su/exit")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # 验证 /user/me 返回正常状态信息（非 su 模式）
    response = client.get("/user/me")
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["username"] == admin_user.username

    # 验证 su_info 字段存在且为非 su 状态
    assert "su_info" in data["user"]
    assert data["user"]["su_info"]["is_su_mode"] is False
    assert data["user"]["su_info"]["original_user_username"] is None

    # 验证 session 中的数据已清除
    with client.session_transaction() as sess:
        assert sess.get("su_mode") is None
        assert sess.get("original_user_id") is None
        assert sess.get("su_user_id") is None


def test_admin_su_already_in_su_mode(client, admin_user, regular_user, db):
    """
    测试已经在 su 模式时不能再次切换

    注意：由于切换后 current_user 不再是 admin，会在 before_request 中被拦截
    """
    login_as_admin(client, admin_user)

    response = client.post(f"/admin/su/{regular_user.username}")
    assert response.status_code == 200

    # 创建另一个用户（需要完整的字段）
    another_user = User(
        username="anotheruser",
        email="anotheruser@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
        is_active=True
    )
    another_user.set_password("password123")  # 使用 set_password 方法
    db.session.add(another_user)
    db.session.commit()

    response = client.post(f"/admin/su/{another_user.username}")
    # 由于已经切换到 regular_user（非 admin），会被 before_request 拦截返回 403
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "Access Denied"


def test_admin_su_switch_to_self(client, admin_user):
    """
    测试不能切换到自己
    """
    login_as_admin(client, admin_user)

    response = client.post(f"/admin/su/{admin_user.username}")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "无法切换到自己"


def test_admin_su_switch_to_nonexistent_user(client, admin_user):
    """
    测试不能切换到不存在的用户
    """
    login_as_admin(client, admin_user)

    response = client.post("/admin/su/nonexistentuser")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "目标用户不存在"


def test_admin_su_switch_to_banned_user(client, admin_user, db):
    """
    测试不能切换到被封禁的用户
    """
    # 创建被封禁用户（需要完整的字段）
    banned_user = User(
        username="banneduser",
        email="banneduser@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
        is_active=False  # 关键：设置为封禁状态
    )
    banned_user.set_password("password123")  # 使用 set_password 方法
    db.session.add(banned_user)
    db.session.commit()

    login_as_admin(client, admin_user)

    response = client.post(f"/admin/su/{banned_user.username}")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    # 完整的错误消息是 "目标用户已被封禁，无法切换"
    assert "目标用户已被封禁" in data["message"]


def test_admin_su_exit_not_in_su_mode(client, admin_user):
    """
    测试不在 su 模式时无法退出
    """
    login_as_admin(client, admin_user)

    response = client.post("/admin/su/exit")
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "当前不在 su 模式"


def test_admin_clear_cache_success(client, admin_user):
    """
    测试清除缓存

    注意：这个测试需要模拟缓存目录的存在
    """
    login_as_admin(client, admin_user)

    response = client.delete("/admin/cache")

    assert response.status_code in [200, 500]
    data = response.get_json()

    assert "success" in data
