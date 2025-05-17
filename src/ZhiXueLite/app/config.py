from datetime import timedelta
import os

from app.database import db


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

    # --- 其他配置 ---
    GEETEST_CAPTCHA_URL = os.environ["CAPTCHA_URL"]


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("DEV_SECRET_KEY") or "dev"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DEV_DATABASE_URL") or \
        "sqlite:///data.db"


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ["PROD_SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI = os.environ["PROD_DATABASE_URL"]


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
