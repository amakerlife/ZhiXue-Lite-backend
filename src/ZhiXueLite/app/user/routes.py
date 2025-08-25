from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from app.models.student import login_student
from app.database import db
from app.database.models import User, School, ZhiXueStudentAccount
from datetime import datetime
from app import limiter
from flask_limiter.util import get_remote_address
from app.utils.turnstile import verify_turnstile_token

user_bp = Blueprint("user", __name__)


def get_ip_limit():
    """基于 IP 的限制"""
    return get_remote_address()


def get_user_limit():
    """基于用户的限制"""
    if current_user.is_authenticated:
        return f"user_{current_user.id}"
    return get_remote_address()


@user_bp.route("/signup", methods=["POST"])
def signup():
    """用户注册"""
    data = request.get_json()

    if not all(key in data for key in ("username", "password", "email")):
        return jsonify({"success": False, "message": "缺少必要字段"}), 400

    turnstile_token = data.get("turnstile_token")
    verification_result = verify_turnstile_token(turnstile_token, get_remote_address())
    if not verification_result.get("success", False):
        return jsonify({
            "success": False,
            "message": verification_result.get("message", "验证码验证失败")
        }), 400

    if "@" in data["username"]:
        return jsonify({"success": False, "message": "用户名不合法"}), 400
    if db.session.scalar(select(User).where(User.username == data["username"])):
        return jsonify({"success": False, "message": "用户名已被使用"}), 400
    if db.session.scalar(select(User).where(User.email == data["email"])):
        return jsonify({"success": False, "message": "邮箱已被使用"}), 400

    role = "user"
    if db.session.get(User, 1) is None:
        role = "admin"

    # 创建新用户
    user = User(
        username=data["username"],
        email=data["email"],
        role=role,
        created_at=datetime.utcnow(),
        registration_ip=get_remote_address(),
        last_login=datetime.utcnow(),
        last_login_ip=get_remote_address()
    )
    user.set_password(data["password"])

    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)

    return jsonify({"success": True, "message": "注册成功", "id": user.id}), 201


@user_bp.route("/login", methods=["POST"])
def login():
    """用户登录，支持用户名或邮箱登录

    请求参数:
    - username: 用户名或邮箱 (弃用，向下兼容)
    - login: 用户名或邮箱
    - password: 密码
    - turnstile_token: Turnstile 验证码令牌（可选）
    """
    data = request.get_json()

    login_field = data.get("login") or data.get("username")
    password = data.get("password")

    if not login_field or not password:
        return jsonify({"success": False, "message": "缺少登录凭据或密码"}), 400

    turnstile_token = data.get("turnstile_token")
    verification_result = verify_turnstile_token(turnstile_token, get_remote_address())
    if not verification_result.get("success", False):
        return jsonify({
            "success": False,
            "message": verification_result.get("message", "验证码验证失败")
        }), 400

    if "@" in login_field:
        # 邮箱
        user = db.session.scalar(select(User).where(User.email == login_field))
        if not user or not user.check_password(password):
            return jsonify({"success": False, "message": "用户名或密码错误"}), 401
    else:
        # 用户名
        user = db.session.scalar(select(User).where(User.username == login_field))
        if not user or not user.check_password(password):
            return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    if not user.is_active:
        return jsonify({"success": False, "message": "用户已被禁用"}), 403

    user.last_login = datetime.utcnow()
    user.last_login_ip = get_remote_address()
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

    user = db.get_or_404(User, user_id)
    return jsonify({"success": True, "user": user.to_dict()}), 200


@user_bp.route("/update/<int:user_id>", methods=["PUT"])
@login_required
def update_user(user_id):
    """更新用户信息"""
    if current_user.id != user_id and current_user.role != "admin":
        return jsonify({"success": False, "message": "您无权访问该页面"}), 403

    user = db.get_or_404(User, user_id)
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


def already_bound_exempt():
    """如果用户已经绑定智学网账号，则不计入限制"""
    if not current_user.is_authenticated:
        return False
    user = db.session.get(User, current_user.id)
    return bool(user and user.zhixue is not None)


@user_bp.route("/zhixue/bind", methods=["POST"])
@login_required
@limiter.limit("3 per 20 minutes",
               key_func=get_ip_limit,
               exempt_when=already_bound_exempt,
               deduct_when=lambda response: response.status_code == 403
               )
@limiter.limit("2 per 20 minutes",
               key_func=get_user_limit,
               exempt_when=already_bound_exempt,
               deduct_when=lambda response: response.status_code == 403
               )
# @limiter.limit("500/day",
#                key_func=lambda: "all",
#                deduct_when=lambda response: response.status_code == 403
#                )
def connect_zhixue():
    """绑定智学网账号"""
    data = request.get_json()

    if not all(key in data for key in ("username", "password")):
        return jsonify({"success": False, "message": "缺少必要字段"}), 400

    turnstile_token = data.get("turnstile_token")
    verification_result = verify_turnstile_token(turnstile_token, get_remote_address())
    if not verification_result.get("success", False):
        return jsonify({
            "success": False,
            "message": verification_result.get("message", "验证码验证失败")
        }), 400

    user = db.get_or_404(User, current_user.id)
    if user.zhixue:
        return jsonify({"success": False, "message": "智学网账号已绑定，请先解绑"}), 400

    zhixue_username = data["username"]
    zhixue_password = data["password"]

    zhixue_record = db.session.scalar(select(ZhiXueStudentAccount).where(
        ZhiXueStudentAccount.username == zhixue_username))
    if zhixue_record and zhixue_password == zhixue_record.password:
        user.zhixue = zhixue_record
        db.session.commit()
        return jsonify({"success": True, "message": "智学网账号已绑定"}), 200

    try:
        zhixue_account = login_student(zhixue_username, zhixue_password)
    except Exception as e:
        return jsonify({"success": False, "message": "连接智学网失败，请检查用户名密码是否正确"}), 403

    # 添加智学网账号信息到数据库
    if zhixue_record:
        zhixue_record.password = zhixue_password
        zhixue_record.cookie = zhixue_account.get_cookie()
        zhixue_record.realname = zhixue_account.name
    else:
        if not db.session.get(School, zhixue_account.clazz.school.id):
            school_record = School(
                id=zhixue_account.clazz.school.id,
                name=zhixue_account.clazz.school.name
            )
            db.session.add(school_record)
            db.session.flush()
        zhixue_record = ZhiXueStudentAccount(
            id=zhixue_account.id,
            username=zhixue_username,
            password=zhixue_password,  # TODO: 存储加密后的密码
            realname=zhixue_account.name,
            cookie=zhixue_account.get_cookie(),
            school_id=zhixue_account.clazz.school.id
        )
        db.session.add(zhixue_record)

    user.zhixue = zhixue_record

    db.session.commit()
    return jsonify({"success": True, "message": "智学网账号已绑定"}), 200


@user_bp.route("/zhixue/unbind", methods=["POST"])
@login_required
def disconnect_zhixue():
    """解绑智学网账号"""
    user = db.get_or_404(User, current_user.id)
    user.zhixue = None
    db.session.commit()
    return jsonify({"success": True, "message": "智学网账号已解绑"}), 200


@user_bp.route("/zhixue/binding_info", methods=["GET"])
@login_required
def get_binding_info():
    """获取智学网账号绑定状况"""
    user = db.get_or_404(User, current_user.id)
    if not user.zhixue:
        return jsonify({"success": False, "message": "智学网账号未绑定"}), 400

    stmt = select(ZhiXueStudentAccount).where(ZhiXueStudentAccount.id == user.zhixue.id)
    zhixue_account = db.session.scalar(stmt)
    if zhixue_account is None:
        return jsonify({"success": False, "message": "智学网账号未绑定"}), 400

    binded_users = zhixue_account.users if zhixue_account.users else []

    result = []
    for user in binded_users:
        result.append({"username": user.username})

    return jsonify({"success": True, "binding_info": result}), 200
