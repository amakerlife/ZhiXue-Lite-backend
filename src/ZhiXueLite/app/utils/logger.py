import os
import sys
from pathlib import Path

from loguru import logger


def setup_logger(app=None):
    """配置 loguru 日志记录器"""
    logger.remove()

    if app is None:
        raise ValueError("Please provide a Flask app instance.")

    log_level = app.config.get("LOG_LEVEL")

    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    log_dir = app.config.get("LOG_DIR")

    if not log_dir:
        project_root = Path(__file__).parents[4]
        log_dir = os.path.join(project_root, "logs")

    os.makedirs(log_dir, exist_ok=True)

    # 按日期分割日志文件
    log_file = os.path.join(log_dir, "app.log")
    logger.add(
        log_file,
        level=log_level,
        rotation="00:00",
        retention="60 days",
        # compression="zip",
        encoding="utf-8",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    # 记录错误日志
    error_log_file = os.path.join(log_dir, "app.error.log")
    logger.add(
        error_log_file,
        level="ERROR",
        rotation="00:00",
        retention="120 days",
        # compression="zip",
        encoding="utf-8",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    logger.info(f"loguru initialized with level: {log_level}, directory: {log_dir}")

    return logger
