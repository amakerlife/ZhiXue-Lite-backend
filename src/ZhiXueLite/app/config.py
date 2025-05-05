from datetime import timedelta
import os

from app.database import db


class Config:
    # --- SQLAlchemy 配置 ---
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "postgresql://postgres@localhost:5432/ZhiXueLite"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,  # 连接池大小
        "max_overflow": 20,  # 超出pool_size的连接数
        "pool_timeout": 30,  # 从连接池获取连接的超时时间
        "pool_recycle": 1800,  # 连接在池中的最大生存时间(秒)
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # --- Flask-Login 配置 ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # --- Flask-Session 配置 ---
    SESSION_TYPE = "sqlalchemy"
    SESSION_SQLALCHEMY = db
    SESSION_SQLALCHEMY_TABLE = "sessions"
    SESSION_PERMANENT = True  # 设置会话为永久
    SESSION_USE_SIGNER = True  # 使用签名
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)  # 会话过期时间
