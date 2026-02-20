"""
权限系统测试

测试 User.has_permission() 方法和权限控制逻辑
"""
from datetime import datetime
from app.database.models import User, School, ZhiXueStudentAccount, PermissionType, PermissionLevel
from app.utils.crypto import encrypt


def test_user_permissions_string_format(db):
    """
    测试权限字符串的格式
    """
    user = User(
        username="testuser",
        email="test@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow()
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    assert user.permissions == "10110"


def test_admin_has_all_permissions(db):
    """
    测试管理员拥有所有权限
    """
    admin = User(
        username="admin",
        email="admin@example.com",
        role="admin",
        permissions="33333",
        created_at=datetime.utcnow()
    )
    admin.set_password("adminpass")
    db.session.add(admin)
    db.session.commit()

    assert admin.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SELF) is True
    assert admin.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SCHOOL) is True
    assert admin.has_permission(PermissionType.FETCH_DATA, PermissionLevel.GLOBAL) is True
    assert admin.has_permission(PermissionType.VIEW_EXAM_LIST, PermissionLevel.GLOBAL) is True


def test_user_permission_levels(db):
    """
    测试用户权限级别检查

    权限字符串 "10110" 的含义：
    - 位置 0 (FETCH_DATA): 级别 1 (SELF)
    - 位置 1 (REFETCH_EXAM_DATA): 级别 0 (DENIED)
    - 位置 2 (VIEW_EXAM_LIST): 级别 1 (SELF)
    - 位置 3 (VIEW_EXAM_DATA): 级别 1 (SELF)
    - 位置 4 (EXPORT_SCORE_SHEET): 级别 0 (DENIED)
    """
    # 创建学校和智学网账号
    school = School(id="school_001", name="测试中学")
    zhixue_account = ZhiXueStudentAccount(
        id="zx_001",
        username="zxuser",
        password=encrypt("encrypted_password"),
        realname="张三",
        cookie=encrypt("fake_cookie"),
        school_id="school_001"
    )
    db.session.add_all([school, zhixue_account])

    user = User(
        username="normaluser",
        email="user@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        zhixue_account_id="zx_001"
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    assert user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SELF) is True
    assert user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SCHOOL) is False
    assert user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.GLOBAL) is False

    assert user.has_permission(PermissionType.REFETCH_EXAM_DATA, PermissionLevel.SELF) is False
    assert user.has_permission(PermissionType.REFETCH_EXAM_DATA, PermissionLevel.SCHOOL) is False

    assert user.has_permission(PermissionType.VIEW_EXAM_LIST, PermissionLevel.SELF) is True
    assert user.has_permission(PermissionType.VIEW_EXAM_LIST, PermissionLevel.SCHOOL) is False


def test_permission_requires_zhixue_account(db):
    """
    测试 SELF 级权限需要智学网账号
    """
    user = User(
        username="unbound",
        email="unbound@example.com",
        role="user",
        permissions="10110"
    )

    db.session.add(user)
    db.session.commit()

    assert user.has_permission(PermissionType.VIEW_EXAM_LIST, PermissionLevel.SELF) is False


def test_school_permission_requires_school_id(db):
    """
    测试 SCHOOL 级权限需要 school_id
    """
    user = User(
        username="noschool",
        email="noschool@example.com",
        role="user",
        permissions="22222",
        created_at=datetime.utcnow(),
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    assert user.has_permission(PermissionType.VIEW_EXAM_LIST, PermissionLevel.SCHOOL) is False


def test_user_with_manual_school(db):
    """
    测试手动分配学校的用户权限
    """
    school = School(id="school_001", name="测试中学")
    db.session.add(school)

    user = User(
        username="manualschool",
        email="manual@example.com",
        role="user",
        permissions="22222",
        created_at=datetime.utcnow(),
        manual_school_id="school_001"
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    assert user.has_permission(PermissionType.VIEW_EXAM_LIST, PermissionLevel.SCHOOL) is True
    assert user.school_id == "school_001"
