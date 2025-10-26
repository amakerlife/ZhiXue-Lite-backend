from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from app.utils.email import send_reverification_email, send_signup_verification_email, send_email_change_verification_email
from task_worker.repository import update_task_progress


def send_verification_email_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """发送验证邮件的后台任务处理器

    Args:
        session: 数据库会话
        task_id: 任务 ID
        user_id: 用户 ID
        parameters: 任务参数，包含：
            - email_type: 邮件类型（"signup" 或 "email_change"）
            - to_email: 收件人邮箱
            - username: 用户名
            - token: 验证令牌

    Returns:
        dict: 任务执行结果
    """
    try:
        update_task_progress(session, task_id, 10, "获取发送参数...")

        email_type = str(parameters.get("email_type"))
        to_email = str(parameters.get("to_email"))
        username = str(parameters.get("username"))
        token = str(parameters.get("token"))

        if not all([email_type, to_email, username, token]):
            raise ValueError("Missing required parameters")

        update_task_progress(session, task_id, 50, "正在发送邮件...")

        success = False
        if email_type == "signup":
            success = send_signup_verification_email(to_email, username, token)
        elif email_type == "email_change":
            success = send_email_change_verification_email(
                to_email, username, token)
        elif email_type == "reverify":
            success = send_reverification_email(to_email, username, token)
        else:
            raise ValueError(f"Unknown email type: {email_type}")

        if not success:
            raise Exception(f"Failed to send {email_type} verification email to {to_email}")

        update_task_progress(session, task_id, 100, "邮件发送成功")
        return {"success": True, "email": to_email}

    except Exception as e:
        logger.error(f"Send verification email handler failed: {str(e)}")
        raise
