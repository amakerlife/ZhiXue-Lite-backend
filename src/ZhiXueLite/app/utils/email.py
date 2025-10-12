import os
import smtplib
from loguru import logger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


def is_email_verification_enabled() -> bool:
    """检查是否启用邮件验证功能"""
    return os.getenv("EMAIL_VERIFICATION_ENABLED", "false").lower() == "true"


def get_smtp_config() -> dict:
    """获取 SMTP 配置"""
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "starttls": os.getenv("SMTP_STARTTLS", "true").lower() == "true",
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_name": os.getenv("SMTP_FROM_NAME", "ZhiXue Lite"),
    }


def send_email(to_email: str, subject: str, text_content: Optional[str] = None, html_content: Optional[str] = None) -> bool:
    """发送邮件

    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        html_content: HTML 格式的邮件内容（可选）
        text_content: 纯文本格式的邮件内容（可选）

    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    if not is_email_verification_enabled():
        logger.warning("Email verification is disabled, skipping email send")
        return False

    config = get_smtp_config()

    # 验证必要配置
    if not all([config["host"], config["username"], config["password"]]):
        logger.error("SMTP configuration is incomplete")
        return False

    try:
        # 创建邮件消息
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{config['from_name']} <{config['username']}>"
        message["To"] = to_email

        # 添加纯文本内容
        if text_content:
            part1 = MIMEText(text_content, "plain", "utf-8")
            message.attach(part1)

        # 添加 HTML 内容
        if html_content:
            part2 = MIMEText(html_content, "html", "utf-8")
            message.attach(part2)

        if config["starttls"]:
            # 使用 STARTTLS 模式
            server = smtplib.SMTP(config["host"], config["port"])
            server.starttls()
        else:
            # 使用 SSL/TLS 模式
            server = smtplib.SMTP_SSL(config["host"], config["port"])

        try:
            server.login(config["username"], config["password"])
            server.send_message(message)
            logger.info(f"Email sent successfully to {to_email}")
            return True
        finally:
            server.quit()

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False


def send_signup_verification_email(to_email: str, username: str, token: str) -> bool:
    """发送邮箱注册验证邮件

    Args:
        to_email: 收件人邮箱
        username: 用户名
        token: 验证令牌

    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    frontend_url = os.getenv("FRONTEND_URLS", "").split(",")[0]
    verification_link = f"{frontend_url}/verify-email?token={token}"

    subject = "验证您的 ZhiXue Lite 账户"

    text_content = f"""
    欢迎加入 ZhiXue Lite！

    你好，{username}！

    感谢你注册 ZhiXue Lite 账户。请访问以下链接验证你的邮箱地址：

    {verification_link}

    注意：此验证链接将在 24 小时后过期。

    如果你没有注册 ZhiXue Lite 账户，请忽略此邮件。

    © ZhiXue Lite. All rights reserved.
    """

    return send_email(to_email, subject, text_content=text_content)


def send_email_change_verification_email(to_email: str, username: str, token: str) -> bool:
    """发送邮箱变更验证邮件

    Args:
        to_email: 收件人邮箱
        username: 用户名
        token: 验证令牌

    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    frontend_url = os.getenv("FRONTEND_URLS", "").split(",")[0]
    verification_link = f"{frontend_url}/verify-email?token={token}"

    subject = "验证您的新邮箱地址 - ZhiXue Lite"

    text_content = f"""
    你好，{username}！

    你请求将 ZhiXue Lite 账户的邮箱地址更改为此邮箱。请访问以下链接验证你的新邮箱地址：

    {verification_link}

    注意：此验证链接将在 24 小时后过期。

    如果你没有请求更改邮箱地址，请忽略此邮件。

    © ZhiXue Lite. All rights reserved.
    """

    return send_email(to_email, subject, text_content=text_content)
