from flask import Flask, jsonify
from flask_login import LoginManager
from app.database import init_db
from app.config import Config
import app.models  # 导入模型以确保创建表


def create_app(config_class=Config):
    app = Flask("ZhiXueLite-backend")
    app.config.from_object(config_class)

    init_db(app)

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
    app.register_blueprint(user_bp, url_prefix="/user")

    return app
