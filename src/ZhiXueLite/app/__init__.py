from flask import Flask, jsonify
from flask_login import LoginManager
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from app.database import db, init_db
from app.config import config
import app.user.models
import app.exam.models  # 导入模型以确保创建表

# 初始化 Limiter
limiter = Limiter(  # 在create_app外部或作为全局变量初始化，以便在蓝图中使用
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379",
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",
)

def create_app(config_name="default"):
    app = Flask("ZhiXueLite-backend")
    app.config.from_object(config[config_name])

    limiter.init_app(app)

    init_db(app)
    Migrate(app, db)  # 初始化 Migrate

    Session(app)

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login 要求的回调函数，用于从 ID 加载用户"""
        from app.user.models import User
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        """处理未授权访问 (未登录)"""
        return jsonify({"message": "Authentication required."}), 401

    # 注册蓝图
    from app.user.routes import user_bp
    from app.exam.routes import exam_bp
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(exam_bp, url_prefix="/exam")

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify(message="请求过于频繁，请稍后再试。", error="rate_limit_exceeded"), 429

    @app.cli.command("init-db")
    def init_db_command():
        """清除所有数据并初始化数据库"""
        with app.app_context():
            if input("Are you sure you want to drop all tables? (y/n): ").lower() == "y":
                db.drop_all()
                db.create_all()
                print("Initialized the database and created the tables.")
            else:
                print("Database initialization canceled.")

    return app
