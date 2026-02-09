from datetime import datetime, timedelta
from enum import Enum
import secrets
from typing import Optional
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

from flask_login import UserMixin
from sqlalchemy import UUID, Boolean, DateTime, Float, ForeignKey, Index, String, Text, Integer, UniqueConstraint
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


class PermissionLevel(Enum):
    """权限级别"""
    DENIED = 0      # 禁止
    SELF = 1        # 个人: 只能访问自己的数据
    SCHOOL = 2      # 校内: 可访问同校数据
    GLOBAL = 3      # 全局: 可访问所有数据


class PermissionType(Enum):
    """权限类型及位置"""
    FETCH_DATA = 0          # 拉取数据（列表、详情）
    REFETCH_EXAM_DATA = 1   # 重新拉取考试详情数据
    VIEW_EXAM_LIST = 2      # 查看考试列表
    VIEW_EXAM_DATA = 3      # 查看考试详情
    EXPORT_SCORE_SHEET = 4  # 导出成绩单（无个人权限）


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

    __table_args__ = (
        Index("ix_zhixue_teacher_accounts_school", "school_id"),
    )


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

    __table_args__ = (
        Index("ix_zhixue_student_accounts_school", "school_id"),
    )

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


class ExamSchool(BaseDBClass):
    """考试-学校关联表，支持联考场景

    一场考试可以关联多个学校（联考），每个学校独立维护数据保存状态。
    """
    __tablename__ = "exam_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey("exams.id"), nullable=False)
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"), nullable=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)  # 每个学校单独跟踪数据保存状态

    exam: Mapped["Exam"] = relationship("Exam", back_populates="schools")
    school: Mapped["School"] = relationship("School")

    __table_args__ = (
        UniqueConstraint("exam_id", "school_id"),
        Index("ix_exam_schools_exam", "exam_id"),
        Index("ix_exam_schools_school", "school_id"),
    )


class Exam(BaseDBClass):
    """考试信息模型"""
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[float] = mapped_column(Float)
    # DEPRECATED: is_saved 已迁移到 ExamSchool.is_saved（支持联考后每个学校独立保存状态）
    # 保留此字段用于向下兼容，数据库迁移时会删除
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    # DEPRECATED: school_id 已改为多对多关系（通过 ExamSchool 表）
    # 保留此字段用于向下兼容，新代码应使用 schools 关系
    school_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("schools.id"), nullable=True)

    user_exams: Mapped[list["UserExam"]] = relationship("UserExam", back_populates="exam")
    scores: Mapped[list["Score"]] = relationship("Score", back_populates="exam")
    # DEPRECATED: 保留单一 school 关系用于向下兼容
    school: Mapped[Optional["School"]] = relationship("School", foreign_keys=[school_id], back_populates="exams")
    # 新的多对多关系
    schools: Mapped[list["ExamSchool"]] = relationship("ExamSchool", back_populates="exam")

    __table_args__ = (
        Index("ix_exams_school_created", "school_id", "created_at"),
        Index("ix_exams_created", "created_at"),
    )

    def get_school_ids(self) -> list[str]:  # FIXME: N+1 查询
        """获取所有参与学校的 ID"""
        return [es.school_id for es in self.schools]

    def get_schools_saved_status(self) -> list[dict]:
        """获取所有参与学校的保存状态信息"""
        return [
            {
                "school_id": es.school_id,
                "school_name": es.school.name,
                "is_saved": es.is_saved
            }
            for es in self.schools
        ]

    def is_saved_for_school(self, school_id: str) -> bool:
        """检查指定学校是否已保存考试数据

        Args:
            school_id: 学校 ID

        Returns:
            bool: 该学校是否已保存数据
        """
        for es in self.schools:
            if es.school_id == school_id:
                return es.is_saved
        return False

    def get_exam_school(self, school_id: str) -> Optional["ExamSchool"]:
        """获取指定学校的考试关联记录

        Args:
            school_id: 学校 ID

        Returns:
            ExamSchool | None: 关联记录，不存在则返回 None
        """
        for es in self.schools:
            if es.school_id == school_id:
                return es
        return None


class UserExam(BaseDBClass):
    """用户考试关联模型。关联智学网学生账户和其所有考试"""
    __tablename__ = "user_exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zhixue_id: Mapped[str] = mapped_column(String(50), ForeignKey("zhixue_student_accounts.id"))
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey("exams.id"))

    zhixue: Mapped["ZhiXueStudentAccount"] = relationship("ZhiXueStudentAccount", back_populates="user_exams")
    exam: Mapped["Exam"] = relationship("Exam", back_populates="user_exams")

    __table_args__ = (
        Index("ix_user_exams_zhixue_exam", "zhixue_id", "exam_id"),
    )


class Score(BaseDBClass):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey("students.id"))
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey("exams.id"))
    school_id: Mapped[str] = mapped_column(String(50), ForeignKey("schools.id"))
    subject_id: Mapped[str] = mapped_column(String(50))
    subject_name: Mapped[str] = mapped_column(String(50))
    class_name: Mapped[str] = mapped_column(String(50))
    sort: Mapped[int] = mapped_column(Integer, default=1)

    score: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 为空时表示原始数据无成绩，下同
    standard_score: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    class_rank: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    school_rank: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    score_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="ok")  # 状态，ok 正常，错误状态待发掘
    is_calculated: Mapped[bool] = mapped_column(Boolean, default=False)  # 总分是否为计算得到

    student: Mapped["Student"] = relationship("Student", back_populates="scores")
    exam: Mapped["Exam"] = relationship("Exam", back_populates="scores")
    school: Mapped["School"] = relationship("School")

    __table_args__ = (
        Index("ix_scores_exam_student", "exam_id", "student_id"),
        Index("ix_scores_exam_school", "exam_id", "school_id"),
        Index("ix_scores_exam_sort", "exam_id", "sort"),
    )


class BackgroundTask(BaseDBClass):
    __tablename__ = "background_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(UUID(as_uuid=False), default=lambda: str(uuid.uuid4()), unique=True)

    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 任务类型，如 fetch_student_exam_list
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)  # 关联的用户ID
    hide: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否对用户隐藏

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

    __table_args__ = (
        Index("ix_background_tasks_status_created", "status", "created_at"),
        Index("ix_background_tasks_uuid_user", "uuid", "user_id"),
        Index("ix_background_tasks_user_created", "user_id", "created_at"),
    )

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
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(200))
    role: Mapped[Optional[str]] = mapped_column(String(20))
    permissions: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registration_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    zhixue_account_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("zhixue_student_accounts.id"), nullable=True)
    manual_school_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("schools.id"), nullable=True)

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email_verification_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    zhixue: Mapped[Optional["ZhiXueStudentAccount"]] = relationship("ZhiXueStudentAccount", back_populates="users")
    manual_school: Mapped[Optional["School"]] = relationship("School", foreign_keys=[manual_school_id])
    background_tasks: Mapped[list["BackgroundTask"]] = relationship("BackgroundTask", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def generate_email_verification_token(self, expires_hours: int = 24):
        """生成邮箱验证令牌

        Args:
            expires_hours: 令牌有效期（小时），默认 24 小时
        """
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_token_expires = datetime.utcnow() + timedelta(hours=expires_hours)

    def verify_email_token(self, token: str) -> bool:
        """验证邮箱令牌是否有效，并更新邮箱验证状态

        Args:
            token: 待验证的令牌

        Returns:
            bool: 令牌有效返回 True，否则返回 False
        """
        if not self.email_verification_token or not self.email_verification_token_expires:
            return False

        if datetime.utcnow() > self.email_verification_token_expires:
            return False

        if self.email_verification_token == token:
            self.email_verified = True
            self.email_verification_token = None
            self.email_verification_token_expires = None
            return True

        return False

    def __get_zhixue_info(self):
        """获取智学网账号信息"""
        zhixue_info = {
            "username": self.zhixue.username if self.zhixue else None,
            "realname": self.zhixue.realname if self.zhixue else None,
            "school_name": self.school_name,
            "school_id": self.school_id,
            "school_has_teacher": False
        }

        if self.zhixue:
            zhixue_info["school_has_teacher"] = (
                self.zhixue.school is not None and
                self.zhixue.school.teacher is not None
            )

        return zhixue_info

    def to_dict(self):
        return {
            "username": self.username,
            "email": self.email,
            "email_verified": self.email_verified,
            "role": self.role,
            "permissions": self.permissions,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_manual_school": self.manual_school_id is not None,
            "zhixue_info": self.__get_zhixue_info(),
        }

    def to_dict_all(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "email_verified": self.email_verified,
            "role": self.role,
            "permissions": self.permissions,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "registration_ip": self.registration_ip,
            "last_login_ip": self.last_login_ip,
            "is_manual_school": self.manual_school_id is not None,
            "zhixue_info": self.__get_zhixue_info(),
        }

    @property
    def is_admin(self) -> bool:
        """检查用户是否为管理员"""
        return self.role == "admin"

    @property
    def is_authenticated(self) -> bool:
        """检查用户是否已认证（覆盖 UserMixin 的方法）"""
        return True

    @property
    def is_anonymous(self) -> bool:
        """检查用户是否为匿名用户（覆盖 UserMixin 的方法）"""
        return False

    def get_id(self) -> str:
        """返回用户的唯一标识符（覆盖 UserMixin 的方法）"""
        return str(self.id)

    @property
    def school_id(self) -> Optional[str]:
        """获取用户所属学校 ID

        优先返回智学网账号绑定的学校，否则返回管理员手动分配的学校。
        """
        if self.zhixue:
            return self.zhixue.school_id
        return self.manual_school_id

    @property
    def school_name(self) -> Optional[str]:
        """获取用户所属学校名称

        优先返回智学网账号绑定的学校，否则返回管理员手动分配的学校。
        """
        if self.zhixue:
            return self.zhixue.school.name if self.zhixue.school else None
        return self.manual_school.name if self.manual_school else None

    def has_permission(self, permission_type: PermissionType, required_level: PermissionLevel) -> bool:
        """检查用户是否有指定级别的权限"""
        if self.is_admin:
            return True

        if not self.permissions or len(self.permissions) <= permission_type.value:
            return False

        user_level = int(self.permissions[permission_type.value])

        if user_level < required_level.value:
            return False

        if self.school_id is None and required_level == PermissionLevel.SCHOOL:
            return False

        if self.zhixue is None and self.manual_school is None and required_level == PermissionLevel.SELF:
            return False

        return True
