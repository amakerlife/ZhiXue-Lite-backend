from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.utils.login_zhixue import get_session_by_captcha
from app.database import db
from app.user.models import User
from datetime import datetime
from app import limiter  # 导入 limiter

user_bp = Blueprint("user", __name__)


def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0]  # type: ignore
    else:
        ip = request.remote_addr or "127.0.0.1"
    return ip


@user_bp.route("/signup", methods=["POST"])
def signup():  # TODO: 添加验证码
    """用户注册"""
    data = request.get_json()

    if not all(key in data for key in ("username", "password", "email")):
        return jsonify({"success": False, "message": "缺少必要字段"}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"success": False, "message": "用户名已被使用"}), 400
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"success": False, "message": "邮箱已被使用"}), 400

    # 创建新用户
    user = User()
    user.username = data["username"]
    user.email = data["email"]
    user.set_password(data["password"])
    user.role = "user"
    user.created_at = datetime.utcnow()
    user.registration_ip = get_client_ip()
    user.last_login = datetime.utcnow()
    user.last_login_ip = get_client_ip()

    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)

    return jsonify({"success": True, "message": "注册成功", "id": user.id}), 201


@user_bp.route("/login", methods=["POST"])
def login():
    """用户登录"""
    data = request.get_json()

    if not all(key in data for key in ("username", "password")):
        return jsonify({"success": False, "message": "缺少必要字段"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    if not user.is_active:
        return jsonify({"success": False, "message": "用户已被禁用"}), 403

    user.last_login = datetime.utcnow()
    user.last_login_ip = get_client_ip()
    db.session.commit()

    login_user(user, remember=True)

    return jsonify({"success": True, "message": "登录成功", "user": user.to_dict()}), 200


@user_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """用户登出"""
    logout_user()
    return jsonify({"success": True, "message": "已登出"}), 200


@user_bp.route("/me", methods=["GET"])
@login_required
def get_current_user():
    """获取当前用户信息"""
    return jsonify({"success": True, "user": current_user.to_dict()}), 200


@user_bp.route("/show/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    """获取用户信息"""
    if current_user.id != user_id and current_user.role != "admin":
        return jsonify({"success": False, "message": "您无权访问该页面"}), 403

    user = User.query.get_or_404(user_id)
    return jsonify({"success": True, "user": user.to_dict()}), 200


@user_bp.route("/update/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id):
    """更新用户信息"""
    if current_user.id != user_id and current_user.role != "admin":
        return jsonify({"success": False, "message": "您无权访问该页面"}), 403

    user = User.query.get_or_404(user_id)
    data = request.get_json()

    # 只允许更新特定字段
    allowed_fields = ["email"]
    if current_user.role == "admin":
        allowed_fields.extend(["role", "is_active"])

    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])

    # 单独处理密码
    if "password" in data:
        user.set_password(data["password"])

    db.session.commit()
    return jsonify({"success": True, "message": "用户信息已更新", "user": user.to_dict()}), 200


@user_bp.route("/connect", methods=["POST"])
@login_required
@limiter.limit("2 per 20 minutes")  # 添加频率限制
def connect_zhixue():
    """绑定智学网账号"""
    data = request.get_json()

    if not all(key in data for key in ("username", "password")):
        return jsonify({"success": False, "message": "缺少必要字段"}), 400

    user = User.query.get_or_404(current_user.id)
    if user.zhixue_username:
        return jsonify({"success": False, "message": "智学网账号已绑定，请先解绑"}), 400

    zhixue_username = data["username"]
    zhixue_password = data["password"]

    try:
        get_session_by_captcha(zhixue_username, zhixue_password)
    except Exception as e:
        return jsonify({"success": False, "message": "连接智学网失败，请检查用户名密码是否正确"}), 400

    user.zhixue_username = zhixue_username
    user.zhixue_password = zhixue_password  # TODO: 存储加密后的密码
    db.session.commit()
    return jsonify({"success": True, "message": "智学网账号已绑定"}), 200


@user_bp.route("/disconnect", methods=["POST"])
@login_required
def disconnect_zhixue():
    """解绑智学网账号"""
    user = User.query.get_or_404(current_user.id)
    user.zhixue_username = None
    user.zhixue_password = None
    db.session.commit()
    return jsonify({"success": True, "message": "智学网账号已解绑"}), 200
