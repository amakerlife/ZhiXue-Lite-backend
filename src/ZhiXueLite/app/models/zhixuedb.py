from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import BaseDBClass
if TYPE_CHECKING:
    from app.exam.models import Exam
    from app.user.models import User


class School(BaseDBClass):
    """智学网学校模型"""
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    teacher: Mapped["ZhiXueTeacher"] = relationship("ZhiXueTeacher", back_populates="school")
    students: Mapped[list["ZhiXueUser"]] = relationship("ZhiXueUser", back_populates="school")
    exams: Mapped[list["Exam"]] = relationship("Exam", back_populates="school")


class ZhiXueTeacher(BaseDBClass):
    """智学网教师账号模型"""
    __tablename__ = "zhixue_teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    realname: Mapped[str] = mapped_column(String(80), nullable=False)
    cookie: Mapped[str] = mapped_column(Text, nullable=False)
    login_method: Mapped[str] = mapped_column(String(20), nullable=False, default="changyan")
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"))

    school: Mapped["School"] = relationship("School", back_populates="teacher")


class ZhiXueUser(BaseDBClass):
    """智学网学生账户模型"""
    __tablename__ = "zhixue_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    realname: Mapped[str] = mapped_column(String(80), nullable=False)
    cookie: Mapped[str] = mapped_column(Text, nullable=False)
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"), nullable=False)

    users: Mapped[Optional[list["User"]]] = relationship("User", back_populates="zhixue")
    school: Mapped["School"] = relationship("School", back_populates="students")

    def to_dict_all(self):
        return {
            "id": self.id,
            "username": self.username,
            "realname": self.realname,
            "school_id": self.school_id,
            "school_name": self.school.name if self.school else None
        }