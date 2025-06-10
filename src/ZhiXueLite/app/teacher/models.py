from typing import Optional

from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import BaseDBClass


class ZhiXueTeacher(BaseDBClass):
    """智学网教师账号模型"""
    __tablename__ = "zhixue_teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    cookie: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    login_method: Mapped[str] = mapped_column(String(20), nullable=False, default="changyan")
    school_id: Mapped[str] = mapped_column(String(50), nullable=False)
    school_name: Mapped[str] = mapped_column(String(100), nullable=False)
