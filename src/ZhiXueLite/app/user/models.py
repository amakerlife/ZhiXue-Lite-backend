from datetime import datetime
from typing import Optional, TYPE_CHECKING
from flask_login import UserMixin
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import BaseDBClass
from werkzeug.security import generate_password_hash, check_password_hash
if TYPE_CHECKING:
    from app.models.zhixuedb import ZhiXueUser


class User(UserMixin, BaseDBClass):
    """用户模型"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registration_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    zhixue_account_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("zhixue_users.id"), nullable=True)

    zhixue: Mapped[Optional["ZhiXueUser"]] = relationship("ZhiXueUser", back_populates="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "zhixue_username": self.zhixue.username if self.zhixue else None,
            "zhixue_realname": self.zhixue.realname if self.zhixue else None,
            "zhixue_school": self.zhixue.school.name if self.zhixue else None,
        }

    def to_dict_all(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "registration_ip": self.registration_ip,
            "last_login_ip": self.last_login_ip,
            "zhixue_account_id": self.zhixue_account_id,
        }
