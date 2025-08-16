import os
import sys
from typing import cast
from flask import Flask, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_session import Session
from flask_migrate import Migrate
from app.database import db, init_db
from app.config import config
from app.utils.logger import setup_logger
import app.database.models  # 确保模型被导入以便 SQLAlchemy 可以识别它们

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

    setup_logger(app)
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

        if hasattr(e, "retry_after") and e.retry_after:
            response_data["retry_after"] = e.retry_after
            response_data["message"] = f"请求过于频繁，请在 {e.retry_after} 秒后重试"

        return jsonify(response_data), 429

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login 要求的回调函数，用于从 ID 加载用户"""
        from app.database.models import User

        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        """处理未授权访问 (未登录)"""
        return jsonify({
            "success": False,
            "message": "Authentication required."
        }), 401

    # 注册蓝图
    from app.user.routes import user_bp
    from app.exam.routes import exam_bp
    from app.teacher.routes import teacher_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(exam_bp, url_prefix="/exam")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.cli.command("init-db")
    def init_db_command():
        """清除所有数据"""
        if not app.config["DEBUG"]:
            print("This command is strongly discouraged in production environments.")
        with app.app_context():
            if input("Are you sure you want to drop ALL tables? (y/N): ").lower() == "y":
                db.drop_all()
                print("Initialized the database and created the tables.")
            else:
                print("Database initialization canceled.")

    return app
