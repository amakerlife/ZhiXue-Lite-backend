
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from app.config import config

engine = None
SessionLocal = None

def init_db():
    global engine, SessionLocal
    if SessionLocal:
        return

    config_name = os.getenv("FLASK_ENV") or "default"
    app_config = config[config_name]
    engine = create_engine(app_config.SQLALCHEMY_DATABASE_URI)
    SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_session():
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return SessionLocal()
