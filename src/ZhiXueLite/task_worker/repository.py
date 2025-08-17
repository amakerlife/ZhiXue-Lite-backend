
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from app.database.models import BackgroundTask, TaskStatus
from task_worker.database import get_session

def get_next_pending_task() -> Optional[BackgroundTask]:
    """获取下一个待处理的任务"""
    session = get_session()
    stmt = (
        select(BackgroundTask)
        .where(BackgroundTask.status == TaskStatus.PENDING.value)
        .order_by(BackgroundTask.created_at)
        .limit(1)
    )
    return session.scalar(stmt)

def update_task_status(task_uuid: str, status: TaskStatus, **kwargs):
    """更新任务状态"""
    session = get_session()
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
        session.commit()

def update_task_progress(task_id: int, progress: int, message: Optional[str] = None):
    """更新任务进度"""
    session = get_session()
    try:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.progress = progress
            if message:
                task.progress_message = message
            session.commit()
    except Exception as e:
        session.rollback()
        raise e
