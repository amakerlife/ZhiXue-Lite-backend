import json
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from flask import Flask
from sqlalchemy import select
from app.database import db
from app.task.models import BackgroundTask, TaskStatus
from loguru import logger


class TaskManager:
    """后台任务管理器"""

    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.task_handlers: Dict[str, Callable] = {}
        self.polling_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.poll_interval = 2  # 轮询间隔（秒）

    def init_app(self, app: Flask):
        """初始化Flask应用"""
        self.app = app

    def register_task_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self.task_handlers[task_type] = handler
        logger.debug(f"Registered task handler for: {task_type}")

    def create_task(self, task_type: str, user_id: int, parameters: Optional[Dict[str, Any]] = None) -> BackgroundTask:
        """创建新任务"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            task = BackgroundTask(
                task_type=task_type,
                user_id=user_id,
                parameters=json.dumps(parameters) if parameters else None
            )
            db.session.add(task)
            db.session.commit()
            logger.info(f"Task created: {task.id} - {task_type}")
            return task

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """获取任务信息"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            return db.session.get(BackgroundTask, task_id)

    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        """更新任务状态"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            task = db.session.get(BackgroundTask, task_id)

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
                logger.debug(f"Task updated: {task_id} - {status.value}")

    def update_task_progress(self, task_id: str, progress: int, message: Optional[str] = None):
        """更新任务进度"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            try:
                task = db.session.get(BackgroundTask, task_id)

                if task:
                    task.progress = progress
                    if message:
                        task.progress_message = message
                    db.session.commit()
                    logger.debug(f"Task progress updated: {task_id} - {progress}%")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Task progress update failed: {task_id} - {str(e)}")
                raise

    def get_pending_tasks(self):
        """获取待处理的任务"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            stmt = (select(BackgroundTask)
                    .where(BackgroundTask.status == TaskStatus.PENDING.value)
                    .order_by(BackgroundTask.created_at))
            return db.session.scalars(stmt).all()

    def get_next_pending_task(self):
        """获取下一个待处理的任务"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            stmt = (select(BackgroundTask)
                    .where(BackgroundTask.status == TaskStatus.PENDING.value)
                    .order_by(BackgroundTask.created_at)
                    .limit(1))
            return db.session.scalar(stmt)

    def process_task(self, task: BackgroundTask):
        """处理单个任务"""
        if not self.app:
            raise RuntimeError("TaskManager not initialized with app")

        with self.app.app_context():
            try:
                logger.info(f"Starting task processing: {task.id} - {task.task_type}")
                self.update_task_status(task.id, TaskStatus.PROCESSING)

                # 获取任务处理器
                handler = self.task_handlers.get(task.task_type)
                if not handler:
                    raise ValueError(f"Task handler not found for: {task.task_type}")
                parameters = json.loads(task.parameters) if task.parameters else {}

                result = handler(task.id, task.user_id, parameters)

                self.update_task_status(
                    task.id,
                    TaskStatus.COMPLETED,
                    result=json.dumps(result) if result else None,
                    progress=100
                )
                logger.info(f"Task finished: {task.id} - {task.task_type}")
            except Exception as e:
                logger.error(f"Task failed: {task.id} - {str(e)}")
                self.update_task_status(
                    task.id,
                    TaskStatus.FAILED,
                    error_message=str(e)
                )

    def polling_worker(self):
        """轮询工作线程"""
        logger.info("Polling worker started")

        while self.is_running:
            try:
                # 获取单个待处理任务
                task = self.get_next_pending_task()

                if task:
                    # 在当前线程中直接处理任务
                    self.process_task(task)
                else:
                    # 没有任务时休眠
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Polling worker error: {str(e)}")
                time.sleep(self.poll_interval)

        logger.info("Polling worker stopped")

    def start(self):
        """启动任务管理器"""
        if self.is_running:
            logger.warning("Task Manager is already running")
            return

        self.is_running = True
        self.polling_thread = threading.Thread(
            target=self.polling_worker,
            daemon=True
        )
        self.polling_thread.start()
        logger.info("Task Manager started")

    def stop(self):
        """停止任务管理器"""
        self.is_running = False
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=5)
        logger.info("Task Manager stopped")


task_manager = TaskManager()
