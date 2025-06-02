from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import BaseDb


class TaskStatus(Enum):
    PENDING = "pending"      # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败


class BackgroundTask(BaseDb):
    __tablename__ = 'background_tasks'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 任务类型，如 'fetch_exam_list'
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 关联的用户ID

    # 任务参数（JSON字符串）
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 任务结果（JSON字符串）
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 进度信息（可选）
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    progress_message: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    def __repr__(self):
        return f'<BackgroundTask {self.id}: {self.task_type} - {self.status}>'

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
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'user_id': self.user_id,
            'progress': self.progress,
            'progress_message': self.progress_message,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result
        }
