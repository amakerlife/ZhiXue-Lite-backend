from loguru import logger

from task_worker.manager import task_manager
from task_worker.handlers.exam import fetch_exam_list_handler


def register_task_handlers():
    """注册所有任务处理器"""
    task_manager.register_task_handler("fetch_exam_list", fetch_exam_list_handler)
    logger.info("All task handlers registered successfully.")
