from datetime import timedelta
import os

class Config:
    # PostgreSQL连接配置
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "postgresql://postgres@localhost:5432/ZhiXueLite"

    # 连接池配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,  # 连接池大小
        "max_overflow": 20,  # 超出pool_size的连接数
        "pool_timeout": 30,  # 从连接池获取连接的超时时间
        "pool_recycle": 1800,  # 连接在池中的最大生存时间(秒)
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    SECRET_KEY = os.environ.get("SECRET_KEY")

    REMEMBER_COOKIE_DURATION = timedelta(days=30)
