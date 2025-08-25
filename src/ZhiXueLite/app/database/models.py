from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import UserMixin
from sqlalchemy import UUID, Boolean, DateTime, Float, ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import BaseDBClass


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"        # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLING = "cancelling"  # 取消中
    CANCELLED = "cancelled"    # 已取消


class School(BaseDBClass):
    """智学网学校模型"""
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    teacher: Mapped["ZhiXueTeacherAccount"] = relationship("ZhiXueTeacherAccount", back_populates="school")
    student_accounts: Mapped[list["ZhiXueStudentAccount"]] = relationship(
        "ZhiXueStudentAccount", back_populates="school")
    exams: Mapped[list["Exam"]] = relationship("Exam", back_populates="school")


class ZhiXueTeacherAccount(BaseDBClass):
    """智学网教师账号模型"""
    __tablename__ = "zhixue_teacher_accounts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    realname: Mapped[str] = mapped_column(String(80), nullable=False)
    cookie: Mapped[str] = mapped_column(Text, nullable=False)
    login_method: Mapped[str] = mapped_column(String(20), nullable=False, default="changyan")
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"))

    school: Mapped["School"] = relationship("School", back_populates="teacher")


class ZhiXueStudentAccount(BaseDBClass):
    """智学网学生账号模型"""
    __tablename__ = "zhixue_student_accounts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    realname: Mapped[str] = mapped_column(String(80), nullable=False)
    cookie: Mapped[str] = mapped_column(Text, nullable=False)
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"), nullable=False)

    users: Mapped[Optional[list["User"]]] = relationship("User", back_populates="zhixue")
    school: Mapped["School"] = relationship("School", back_populates="student_accounts")
    user_exams: Mapped[list["UserExam"]] = relationship("UserExam", back_populates="zhixue")

    def to_dict_all(self):
        return {
            "id": self.id,
            "username": self.username,
            "realname": self.realname,
            "school_id": self.school_id,
            "school_name": self.school.name if self.school else None,
            "binded_count": len(self.users) if self.users else 0
        }


class Student(BaseDBClass):
    """学生信息模型"""
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(50))
    no: Mapped[str] = mapped_column(String(50))  # 自定义考号，studentNo
    number: Mapped[str] = mapped_column(String(50))  # 准考证号，userNum

    scores: Mapped[list["Score"]] = relationship("Score", back_populates="student")


class Exam(BaseDBClass):
    """考试信息模型"""
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[float] = mapped_column(Float)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"))  # TODO: 支持联考

    user_exams: Mapped[list["UserExam"]] = relationship("UserExam", back_populates="exam")
    scores: Mapped[list["Score"]] = relationship("Score", back_populates="exam")
    school: Mapped["School"] = relationship("School", back_populates="exams")


class UserExam(BaseDBClass):
    """用户考试关联模型。关联智学网学生账户和其所有考试"""
    __tablename__ = "user_exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zhixue_id: Mapped[str] = mapped_column(String(50), ForeignKey("zhixue_student_accounts.id"))
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey("exams.id"))

    zhixue: Mapped["ZhiXueStudentAccount"] = relationship("ZhiXueStudentAccount", back_populates="user_exams")
    exam: Mapped["Exam"] = relationship("Exam", back_populates="user_exams")


class Score(BaseDBClass):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey("students.id"))
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey("exams.id"))
    subject_id: Mapped[str] = mapped_column(String(50))
    subject_name: Mapped[str] = mapped_column(String(50))
    class_name: Mapped[str] = mapped_column(String(50))
    sort: Mapped[int] = mapped_column(Integer, default=1)

    score: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 为空时表示原始数据无成绩，下同
    standard_score: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    class_rank: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    school_rank: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    score_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="ok")  # 状态，ok 正常，错误状态待发掘

    student: Mapped["Student"] = relationship("Student", back_populates="scores")
    exam: Mapped["Exam"] = relationship("Exam", back_populates="scores")


class BackgroundTask(BaseDBClass):
    __tablename__ = "background_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), default=lambda: str(uuid.uuid4()))

    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 任务类型，如 fetch_exam_list
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)  # 关联的用户ID

    # 任务参数（JSON字符串）
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 任务结果（JSON字符串）
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 任务超时时间（秒）
    timeout: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 进度信息（可选）
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    progress_message: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    user = relationship("User", back_populates="background_tasks")

    def __repr__(self):
        return f"<BackgroundTask {self.id}: {self.task_type} - {self.status}>"

    @property
    def status_enum(self) -> TaskStatus:
        """获取状态枚举"""
        return TaskStatus(self.status)

    @status_enum.setter
    def status_enum(self, value: TaskStatus):
        """设置状态枚举"""
        self.status = value.value

    def to_dict(self):
        return {
            "id": self.uuid,
            "task_type": self.task_type,
            "status": self.status,
            "user_id": self.user_id,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result
        }


class User(UserMixin, BaseDBClass):
    """用户模型"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registration_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    zhixue_account_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("zhixue_student_accounts.id"), nullable=True)

    zhixue: Mapped[Optional["ZhiXueStudentAccount"]] = relationship("ZhiXueStudentAccount", back_populates="users")
    background_tasks: Mapped[list["BackgroundTask"]] = relationship("BackgroundTask", back_populates="user")

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
            "zhixue_username": self.zhixue.username if self.zhixue else None,
            "zhixue_realname": self.zhixue.realname if self.zhixue else None,
            "zhixue_school": self.zhixue.school.name if self.zhixue else None,
        }
