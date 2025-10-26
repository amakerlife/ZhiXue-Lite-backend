from datetime import datetime
import json
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select
from app.database import db
from app.database.models import BackgroundTask, TaskStatus


def create_task(
    task_type: str,
    user_id: int,
    parameters: Optional[dict[str, Any]] = None,
    timeout: Optional[int] = None,
    hide: bool = False
) -> BackgroundTask:
    """创建新任务"""
    task = BackgroundTask(
        task_type=task_type,
        user_id=user_id,
        parameters=json.dumps(parameters) if parameters else None,
        timeout=timeout,
        hide=hide
    )
    db.session.add(task)
    db.session.commit()
    logger.info(f"Task created: {task.uuid} - {task_type}")
    return task


def get_task(task_uuid: str) -> Optional[BackgroundTask]:
    """获取任务信息"""
    return db.session.scalar(select(BackgroundTask).where(BackgroundTask.uuid == task_uuid))


def update_task_status(task_uuid: str, status: TaskStatus, **kwargs):
    """更新任务状态"""
    task = get_task(task_uuid)
    if task:
        task.status_enum = status
        if status == TaskStatus.PROCESSING and not task.started_at:
            task.started_at = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = datetime.utcnow()
        # 更新其他字段
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        db.session.commit()
        logger.debug(f"Task updated: {task_uuid} - {status.value}")


def update_task_progress(task_id: int, progress: int, message: Optional[str] = None):
    """更新任务进度"""
    try:
        task = db.session.get(BackgroundTask, task_id)
        if task:
            task.progress = progress
            if message:
                task.progress_message = message
            db.session.commit()
            logger.debug(f"Task progress updated: {task.uuid} - {progress}%")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Task progress update failed: {task_id}(db id) - {str(e)}")
        raise


def get_pending_tasks():
    """获取待处理的任务"""
    stmt = (select(BackgroundTask)
            .where(BackgroundTask.status == TaskStatus.PENDING.value)
            .order_by(BackgroundTask.created_at))
    return db.session.scalars(stmt).all()
