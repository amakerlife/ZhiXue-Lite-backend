from loguru import logger
import requests
import os
from flask import current_app


def verify_turnstile_token(token: str, remote_ip: str = "") -> dict:
    """
    验证 Cloudflare Turnstile 令牌

    Args:
        token: 前端提交的 Turnstile 令牌
        remote_ip: 用户的 IP 地址（可选）

    Returns:
        dict: 验证结果，包含 success 字段和其他信息
    """
    # 检查是否启用 Turnstile
    turnstile_enabled = os.getenv("TURNSTILE_ENABLED", "true").lower() == "true"
    if not turnstile_enabled:
        return {
            "success": True,
            "message": "验证码已禁用"
        }
    
    if not token or token == "disabled":
        if not turnstile_enabled:
            return {"success": True, "message": "验证码已禁用"}
        return {
            "success": False,
            "error-codes": ["missing-input-response"],
            "message": "缺少验证码令牌"
        }

    secret_key = os.getenv("CLOUDFLARE_TURNSTILE_SECRET_KEY")
    if not secret_key:
        logger.critical("CLOUDFLARE_TURNSTILE_SECRET_KEY not configured")
        return {
            "success": False,
            "message": "Internal Server Error"
        }

    data = {
        "secret": secret_key,
        "response": token,
    }

    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            timeout=10
        )

        if response.status_code != 200:
            current_app.logger.error(f"Turnstile API returned status {response.status_code}")
            return {
                "success": False,
                "message": "Service Unavailable"
            }

        result = response.json()

        if not result.get("success", False):
            error_codes = result.get("error-codes", [])
            current_app.logger.warning(f"Turnstile verification failed: {error_codes}")

            if "timeout-or-duplicate" in error_codes:
                result["message"] = "验证码已过期，请重新验证"
            elif "invalid-input-response" in error_codes:
                result["message"] = "无效的验证码，请重新验证"
            elif "bad-request" in error_codes:
                result["message"] = "验证请求格式错误"
            else:
                result["message"] = "验证码验证失败，请重试"

        return result

    except requests.RequestException as e:
        current_app.logger.error(f"Turnstile verification request failed: {str(e)}")
        return {
            "success": False,
            "message": "Network Error"
        }
    except ValueError as e:
        current_app.logger.error(f"Turnstile response parsing failed: {str(e)}")
        return {
            "success": False,
            "message": "Internal Server Error"
        }