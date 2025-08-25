import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import config

engine = None
SessionLocal = None


def init_db():
    global engine, SessionLocal
    if SessionLocal:
        return

    app_config = config
    engine = create_engine(
        app_config.SQLALCHEMY_DATABASE_URI,
        **app_config.SQLALCHEMY_ENGINE_OPTIONS
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session():
    """获取数据库会话的上下文管理器"""
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
