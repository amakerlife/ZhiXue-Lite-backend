import time
from loguru import logger
from task_worker.database import init_db
from task_worker.manager import task_manager


def main():
    logger.info("Initializing task worker...")

    init_db()

    try:
        task_manager.start()
        logger.info("Task worker started successfully.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        task_manager.stop()
        logger.info("Task worker stopped by user.")


if __name__ == "__main__":
    main()
