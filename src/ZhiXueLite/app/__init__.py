import os
from typing import cast
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_session import Session
from flask_migrate import Migrate
from app.database import db, init_db
from app.config import config
import app.user.models
import app.exam.models  # 导入模型以确保创建表

config_name = os.getenv("FLASK_ENV") or "default"


def get_user_id():
    """获取当前用户ID用于频率限制"""
    if current_user.is_authenticated:
        return f"user_{current_user.id}"
    return get_remote_address()


limiter = Limiter(
    key_func=get_user_id,
    storage_uri="memory://"
)


def create_app(config_name=config_name):
    app = Flask("ZhiXueLite-backend")

    app.config.from_object(config[config_name])

    init_db(app)
    Migrate(app, db)

    Session(app)

    limiter.init_app(app)

    # 自定义频率限制错误处理器
    @app.errorhandler(429)
    def ratelimit_handler(e):
        response_data = {
            "success": False,
            "message": "请求过于频繁，请稍后再试",
            "error": "Rate limit exceeded"
        }

        if hasattr(e, 'retry_after') and e.retry_after:
            response_data["retry_after"] = e.retry_after
            response_data["message"] = f"请求过于频繁，请在 {e.retry_after} 秒后重试"

        return jsonify(response_data), 429

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login 要求的回调函数，用于从 ID 加载用户"""
        from app.user.models import User

        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        """处理未授权访问 (未登录)"""
        return jsonify({"message": "Authentication required."}), 401

    # 注册蓝图
    from app.user.routes import user_bp
    from app.exam.routes import exam_bp

    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(exam_bp, url_prefix="/exam")

    @app.cli.command("init-db")
    def init_db_command():
        """清除所有数据并初始化数据库"""
        with cast(Flask, app).app_context():
            if input("Are you sure you want to drop all tables? (y/n): ").lower() == "y":
                db.drop_all()
                db.create_all()
                print("Initialized the database and created the tables.")
            else:
                print("Database initialization canceled.")

    return app
