from datetime import timedelta
import os

from dotenv import load_dotenv

from app.database import db

load_dotenv()


class Config:
    # --- SQLAlchemy 配置 ---
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 5,
        "pool_timeout": 30,
    }

    # --- Flask-Login 配置 ---
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # --- Flask-Session 配置 ---
    SESSION_TYPE = "sqlalchemy"
    SESSION_SQLALCHEMY = db
    SESSION_SQLALCHEMY_TABLE = "sessions"
    SESSION_PERMANENT = True  # 设置会话为永久
    SESSION_USE_SIGNER = True  # 使用签名
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)  # 会话过期时间

    # --- 日志配置 ---
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_DIR = os.environ.get("LOG_DIR")

    # --- 其他配置 ---
    GEETEST_CAPTCHA_URL = os.environ.get("CAPTCHA_URL", "")
    FONT_PATH = os.environ.get("FONT_PATH", "")

    # 定义每个配置类必需的环境变量
    REQUIRED_ENV_VARS = []

    @classmethod
    def validate(cls):
        """验证当前配置所需的环境变量是否存在"""
        missing_vars = [var for var in cls.REQUIRED_ENV_VARS if var not in os.environ]
        if missing_vars:
            raise EnvironmentError(
                f"{cls.__name__} requires the following environment variables: {', '.join(missing_vars)}"
            )


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("DEV_SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DEV_DATABASE_URL", "")

    # 开发环境必需的环境变量
    REQUIRED_ENV_VARS = ["DEV_DATABASE_URL", "CAPTCHA_URL", "FONT_PATH"]


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get("PROD_SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.environ.get("PROD_DATABASE_URL", "")

    # 生产环境必需的环境变量
    REQUIRED_ENV_VARS = ["PROD_SECRET_KEY", "PROD_DATABASE_URL", "CAPTCHA_URL", "FONT_PATH"]


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "test-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    # SQLite 不支持连接池配置，使用空字典覆盖
    SQLALCHEMY_ENGINE_OPTIONS = {}
    # 禁用某些在测试中不需要的功能
    WTF_CSRF_ENABLED = False
    # 测试环境使用 filesystem 会话，conftest.py 会自动清理
    SESSION_TYPE = "filesystem"
    # 禁用速率限制
    RATELIMIT_ENABLED = False


config_mapping = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig
}

config_name = os.getenv("FLASK_ENV") or "default"

config = config_mapping[config_name]