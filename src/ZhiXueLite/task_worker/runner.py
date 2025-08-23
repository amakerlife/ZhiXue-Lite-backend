import sys
import json
import argparse
from typing import Any, Dict

from loguru import logger

from task_worker.database import init_db, get_session
from task_worker.repository import update_task_status, update_task_progress
from app.database.models import TaskStatus


def load_task_handlers() -> Dict[str, Any]:
    """动态加载所有任务处理器"""
    handlers = {}

    try:
        import task_worker.handlers.exam as h
        handlers["fetch_exam_list"] = h.fetch_exam_list_handler
        handlers["fetch_exam_details"] = h.fetch_exam_details_handler
        logger.debug(f"Loaded task handlers: {list(handlers.keys())}")
    except ImportError as e:
        logger.error(f"Failed to import task handlers: {e}")

    return handlers


def execute_task(task_uuid: str, task_id: int, task_type: str, user_id: int, parameters: Dict[str, Any]):
    """执行单个任务"""
    init_db()
    handlers = load_task_handlers()

    logger.info(f"Starting task execution: {task_uuid} - {task_type}")

    with get_session() as session:
        try:
            update_task_status(session, task_uuid, TaskStatus.PROCESSING)
            session.commit()

            handler = handlers.get(task_type)
            if not handler:
                raise ValueError(f"Task handler not found for: {task_type}")

            result = handler(session, task_id, user_id, parameters)

            update_task_status(
                session,
                task_uuid,
                TaskStatus.COMPLETED,
                result=json.dumps(result) if result else None,
                progress=100
            )
            session.commit()

            logger.info(f"Task completed successfully: {task_uuid}")
            return 0

        except Exception as e:
            logger.error(f"Task failed: {task_uuid} - {str(e)}")
            try:
                update_task_status(
                    session,
                    task_uuid,
                    TaskStatus.FAILED,
                    error_message=str(e)
                )
                session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update task status: {db_error}")
            return 1


def main():
    parser = argparse.ArgumentParser(description="Execute a single background task")
    parser.add_argument("--task-uuid", required=True, help="Task UUID")
    parser.add_argument("--task-id", type=int, required=True, help="Task ID")
    parser.add_argument("--task-type", required=True, help="Task type")
    parser.add_argument("--user-id", type=int, required=True, help="User ID")
    parser.add_argument("--parameters", default="{}", help="Task parameters as JSON string")

    args = parser.parse_args()

    try:
        parameters = json.loads(args.parameters)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid parameters JSON: {e}")
        return 1

    return execute_task(
        args.task_uuid,
        args.task_id,
        args.task_type,
        args.user_id,
        parameters
    )


if __name__ == "__main__":
    sys.exit(main())
