import json
import threading
import time
from typing import Optional, Callable

from loguru import logger

from app.database.models import BackgroundTask, TaskStatus
from task_worker.database import init_db, get_session
from task_worker.repository import get_next_pending_task, update_task_status


class TaskManager:
    """后台任务管理器"""

    def __init__(self):
        self.task_handlers: dict[str, Callable] = {}
        self.polling_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.poll_interval = 2

    def register_task_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self.task_handlers[task_type] = handler
        logger.debug(f"Registered task handler for: {task_type}")

    def process_task(self, task: BackgroundTask):
        """处理单个任务"""
        with get_session() as session:
            try:
                logger.info(f"Starting task processing: {task.uuid} - {task.task_type}")
                update_task_status(session, task.uuid, TaskStatus.PROCESSING)

                handler = self.task_handlers.get(task.task_type)
                if not handler:
                    raise ValueError(f"Task handler not found for: {task.task_type}")

                parameters = json.loads(task.parameters) if task.parameters else {}
                result = handler(session, task.id, task.user_id, parameters)

                update_task_status(
                    session,
                    task.uuid,
                    TaskStatus.COMPLETED,
                    result=json.dumps(result) if result else None,
                    progress=100
                )
                logger.info(f"Task finished: {task.uuid} - {task.task_type}")

            except Exception as e:
                logger.error(f"Task failed: {task.uuid} - {str(e)}")
                update_task_status(
                    session,
                    task.uuid,
                    TaskStatus.FAILED,
                    error_message=str(e)
                )

    def polling_worker(self):
        """轮询工作线程"""
        logger.info("Polling worker started")
        init_db()

        while self.is_running:
            try:
                task = get_next_pending_task()

                if task:
                    self.process_task(task)
                else:
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
