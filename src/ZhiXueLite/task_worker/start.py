import time
from loguru import logger
from task_worker.database import init_db
from task_worker.manager import task_manager
from task_worker.handlers.exam import fetch_exam_list_handler


def main():
    logger.info("Initializing task worker...")

    # 初始化数据库
    init_db()

    # 注册任务处理器
    task_manager.register_task_handler("fetch_exam_list", fetch_exam_list_handler)

    # 启动任务管理器
    try:
        task_manager.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        task_manager.stop()
        logger.info("Task worker stopped by user.")


if __name__ == "__main__":
    main()
