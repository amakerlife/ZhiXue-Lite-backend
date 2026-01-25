import os
from datetime import datetime
from flask import Flask, jsonify, request, json
from flask_cors import CORS
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user, logout_user
from flask_session import Session
from flask_migrate import Migrate
from sqlalchemy import distinct, func, select
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from app.database import db, init_db
from app.config import config
from app.utils.email import is_email_verification_enabled
from app.utils.logger import setup_logger
import app.database.models  # 确保模型被导入以便 SQLAlchemy 可以识别它们
from app.database.models import User, School, Exam, ExamSchool


def get_user_id():
    """获取当前用户ID用于频率限制"""
    if current_user.is_authenticated:
        return f"user_{current_user.id}"
    return get_remote_address()


limiter = Limiter(
    key_func=get_user_id,
    storage_uri=config.RATELIMIT_STORAGE_URI or "memory://",
    enabled=config.RATELIMIT_ENABLED,
)


def create_app():
    app = Flask("ZhiXueLite-backend")
    app.config.from_object(config)

    # 验证当前配置所需的环境变量
    config.validate()

    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

    # 配置CORS
    frontend_urls = os.getenv("FRONTEND_URLS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    CORS(app,
         origins=frontend_urls,
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

    setup_logger(app)
    init_db(app)
    Migrate(app, db)

    Session(app)

    if limiter.enabled and config.RATELIMIT_STORAGE_URI == "memory://" and app.config["APP_ENV"] == "production":
        app.logger.warning(
            "Using in-memory rate limit storage in production is not recommended. "
            "That may lead to unexpected behavior when running multiple instances of the application. "
            "Consider using Redis.")
    limiter.init_app(app)

    # 初始化缓存
    cache = Cache(app, config={
        "CACHE_TYPE": "SimpleCache",
        "CACHE_DEFAULT_TIMEOUT": 600  # 10 分钟
    })

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

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        """Return JSON instead of HTML for HTTP errors."""
        response = e.get_response()
        response.data = json.dumps({
            "success": False,
            "code": e.code,
            "message": e.name,
            # "message": e.description,
        })
        response.content_type = "application/json"
        return response

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login 要求的回调函数，用于从 ID 加载用户

        su 模式：
        - 如果 session 中有 su_mode 标记，加载被 su 的用户
        - 否则正常加载当前登录用户
        """
        from flask import session as flask_session
        from app.database.models import User

        if flask_session.get("su_mode"):
            su_user_id = flask_session.get("su_user_id")
            if su_user_id:
                return db.session.get(User, int(su_user_id))

        # 正常模式：加载当前登录用户
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        """处理未授权访问 (未登录)"""
        return jsonify({
            "success": False,
            "message": "Authentication required."
        }), 401

    @app.before_request
    def check_user_active():
        """检查用户是否被封禁"""
        if request.method == "OPTIONS":
            return

        if request.endpoint in ["user.login", "user.signup", "ping", "get_statistics"]:
            return

        if current_user.is_authenticated and not current_user.is_active:
            logout_user()
            return jsonify({
                "success": False,
                "message": "Your account has been banned. Please contact the administrator.",
                "code": "account_banned"
            }), 403

    @app.before_request
    def check_user_verified():
        """检查用户是否验证邮箱"""
        if not is_email_verification_enabled():
            return

        if request.method == "OPTIONS":
            return

        if request.endpoint in ["user.login", "user.signup", "user.get_current_user", "user.get_binding_info", "user.verify_email", "user.resend_verification_email", "user.update_current_user", "admin.exit_su", "ping", "get_statistics"]:
            return

        if current_user.is_authenticated and not current_user.email_verified:
            return jsonify({
                "success": False,
                "message": "Email verification required. Please verify your email to access this resource.",
                "code": "email_not_verified"
            }), 403

    # 注册蓝图
    from app.user.routes import user_bp
    from app.exam.routes import exam_bp
    from app.teacher.routes import teacher_bp
    from app.admin.routes import admin_bp
    from app.task.routes import task_bp

    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(exam_bp, url_prefix="/exam")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(task_bp, url_prefix="/task")

    @app.route("/ping", methods=["GET"])
    def ping():
        """健康检查端点"""
        return jsonify({
            "success": True,
            "message": "pong",
            "timestamp": datetime.utcnow().isoformat()
        }), 200

    @app.route("/statistics", methods=["GET"])
    def get_statistics():
        """获取系统统计信息"""
        cached_stats = cache.get("statistics_data")
        if cached_stats is not None:
            return jsonify({
                "success": True,
                "statistics": cached_stats
            }), 200

        total_users = db.session.scalar(select(func.count(User.id)))
        total_schools = db.session.scalar(select(func.count(School.id)))
        total_exams = db.session.scalar(select(func.count(Exam.id)))
        saved_exams = db.session.scalar(
            select(func.count(distinct(ExamSchool.exam_id)))
            .where(ExamSchool.is_saved.is_(True))
        )

        stats_data = {
            "total_users": total_users or 0,
            "total_schools": total_schools or 0,
            "total_exams": total_exams or 0,
            "saved_exams": saved_exams or 0
        }
        cache.set("statistics_data", stats_data, timeout=300)

        return jsonify({
            "success": True,
            "statistics": stats_data
        }), 200

    @app.cli.command("init-db")
    def init_db_command():
        """清除所有数据"""
        if app.config["APP_ENV"] == "production":
            print("This command is strongly discouraged in production environments.")
        with app.app_context():
            if input("Are you sure you want to drop ALL tables? (y/N): ").lower() == "y":
                db.drop_all()
                print("Initialized the database and created the tables.")
            else:
                print("Database initialization canceled.")

    return app
