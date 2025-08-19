from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger
from app.database.models import BackgroundTask, TaskStatus
from task_worker.database import get_session


def get_next_pending_task() -> Optional[BackgroundTask]:
    """获取下一个待处理的任务"""
    with get_session() as session:
        stmt = (
            select(BackgroundTask)
            .where(BackgroundTask.status == TaskStatus.PENDING.value)
            .order_by(BackgroundTask.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        task = session.scalar(stmt)
        if task:
            # 确保对象在 session 关闭后仍可用
            session.expunge(task)
        return task


def update_task_status(session: Session, task_uuid: str, status: TaskStatus, **kwargs):
    """更新任务状态 - 在现有 session 中操作，不提交事务"""
    task = session.scalar(select(BackgroundTask).where(BackgroundTask.uuid == task_uuid))
    if task:
        task.status_enum = status
        if status == TaskStatus.PROCESSING and not task.started_at:
            task.started_at = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = datetime.utcnow()
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)


def update_task_progress(session: Session, task_id: int, progress: int, message: Optional[str] = None):
    """更新任务进度 - 立即提交进度更新到数据库"""
    try:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.progress = progress
            if message:
                task.progress_message = message
            session.commit()

    except Exception as e:
        logger.error(f"Failed to update task progress: {e}")
        try:
            session.rollback()
        except:
            pass
