"""
用户模型测试
"""
import pytest
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from app.database.models import User


def test_create_user(db):
    """
    测试创建用户
    """
    user = User(
        username="testuser",
        email="test@example.com",
        role="user",
        created_at=datetime.utcnow()
    )
    user.set_password("password123")

    db.session.add(user)
    db.session.commit()

    saved_user = db.session.query(User).filter_by(username="testuser").first()

    assert saved_user is not None
    assert saved_user.username == "testuser"
    assert saved_user.email == "test@example.com"
    assert saved_user.role == "user"


def test_user_password(db):
    """
    测试用户密码加密和验证
    """
    user = User(
        username="passworduser",
        email="password@example.com",
        role="user",
        created_at=datetime.utcnow()
    )
    user.set_password("mysecret123")

    assert user.password_hash != "mysecret123"
    assert len(str(user.password_hash)) > 20  # 加密后的密码很长

    assert user.check_password("mysecret123") is True

    assert user.check_password("wrongpassword") is False
    assert user.check_password("") is False


def test_user_is_admin_property(db):
    """
    测试 is_admin 属性
    """
    admin_user = User(
        username="adminuser",
        email="admin@example.com",
        role="admin",
        created_at=datetime.utcnow()
    )
    admin_user.set_password("adminpass")
    normal_user = User(
        username="normaluser",
        email="normal@example.com",
        role="user",
        created_at=datetime.utcnow()
    )
    normal_user.set_password("userpass")
    db.session.add(admin_user)
    db.session.add(normal_user)
    db.session.commit()

    assert admin_user.is_admin is True
    assert normal_user.is_admin is False


def test_user_unique_constraint(db):
    """
    测试用户名唯一性约束

    数据库约束是数据完整性的重要保障
    """
    user1 = User(
        username="duplicate",
        email="user1@example.com",
        role="user",
        created_at=datetime.utcnow()
    )
    user1.set_password("password1")
    db.session.add(user1)
    db.session.commit()

    user2 = User(
        username="duplicate",
        email="user2@example.com",
        role="user",
        created_at=datetime.utcnow()
    )
    user2.set_password("password2")
    db.session.add(user2)

    with pytest.raises(IntegrityError):
        db.session.commit()


def test_user_to_dict_includes_email_verified(db):
    """确保 user 序列化数据包含 email_verified"""
    user = User(
        username="dictuser",
        email="dictuser@example.com",
        role="user",
        created_at=datetime.utcnow(),
        email_verified=False,
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    assert user.to_dict()["email_verified"] is False
    assert user.to_dict_all()["email_verified"] is False
