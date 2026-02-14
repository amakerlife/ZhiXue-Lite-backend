from pathlib import Path
from shutil import rmtree
from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user, login_user
from sqlalchemy import select
from app.database import db
from app.database.models import Exam, School, ZhiXueStudentAccount, User
from app.utils.paginate import paginate_query
from loguru import logger

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@login_required
def is_admin():
    if request.method == "OPTIONS":
        return

    if request.endpoint == "admin.exit_su" and session.get("su_mode"):
        return

    if current_user.role != "admin":
        return jsonify({"success": False, "message": "Access Denied"}), 403


@admin_bp.route("/list/schools", methods=["GET"])
def list_schools():
    """列出所有学校"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)

    stmt = select(School).order_by(School.id.asc())
    if query:
        stmt = stmt.where(School.name.contains(query) | School.id.contains(query))
    paginated_schools = paginate_query(stmt, page, per_page)
    school_list = [{"id": school.id, "name": school.name} for school in paginated_schools["items"]]

    return jsonify({
        "success": True,
        "schools": school_list,
        "pagination": paginated_schools["pagination"]
    }), 200


@admin_bp.route("/list/users", methods=["GET"])
def list_users():
    """列出所有用户"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)

    stmt = select(User).order_by(User.id.asc())
    if query:
        stmt = stmt.where(User.username.contains(query))
    paginated_users = paginate_query(stmt, page, per_page)
    user_list = [user.to_dict_all() for user in paginated_users["items"]]

    return jsonify({
        "success": True,
        "users": user_list,
        "pagination": paginated_users["pagination"]
    }), 200


@admin_bp.route("/list/zhixue_accounts", methods=["GET"])
def list_zhixue_accounts():
    """列出所有智学网学生账户"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)

    stmt = select(ZhiXueStudentAccount).order_by(ZhiXueStudentAccount.id.asc())
    if query:
        stmt = stmt.where(ZhiXueStudentAccount.username.contains(query))
    paginated_accounts = paginate_query(stmt, page, per_page)
    account_list = [account.to_dict_all() for account in paginated_accounts["items"]]

    return jsonify({
        "success": True,
        "zhixue_accounts": account_list,
        "pagination": paginated_accounts["pagination"]
    }), 200


@admin_bp.route("/list/exams", methods=["GET"])
def list_exams():
    """列出所有考试"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)

    stmt = select(Exam).order_by(Exam.created_at.desc(), Exam.id.desc())
    if query:
        stmt = stmt.where(Exam.name.contains(query) | Exam.id.contains(query))
    paginated_exams = paginate_query(stmt, page, per_page)
    exam_list = [
        {
            "id": exam.id,
            "name": exam.name,
            "created_at": exam.created_at,
            "schools": exam.get_schools_saved_status()
        } for exam in paginated_exams["items"]]

    return jsonify({
        "success": True,
        "exams": exam_list,
        "pagination": paginated_exams["pagination"]
    }), 200


@admin_bp.route("/zhixue/<string:zhixue_username>/users", methods=["GET"])
def list_users_by_zhixue(zhixue_username):
    """根据智学网账号列出绑定的用户"""
    # page = request.args.get("page", 1, type=int)
    # per_page = request.args.get("per_page", 10, type=int)

    zhixue_account = db.session.scalar(select(ZhiXueStudentAccount).where(
        ZhiXueStudentAccount.username == zhixue_username))
    if zhixue_account is None:
        return jsonify({"success": False, "message": "智学网账号未绑定"}), 400

    binded_users = zhixue_account.users if zhixue_account.users else []
    result = []
    for user in binded_users:
        result.append({"username": user.username})
    result = {"total": len(result), "users": result}

    return jsonify({"success": True, "binding_info": result}), 200


@admin_bp.route("/zhixue/<string:zhixue_username>/unbind/<string:username>", methods=["POST"])
def unbind_user(zhixue_username, username):
    """根据智学网账号和用户名解绑用户"""
    zhixue_account = db.session.scalar(select(ZhiXueStudentAccount).where(
        ZhiXueStudentAccount.username == zhixue_username))
    if zhixue_account is None:
        return jsonify({"success": False, "message": "智学网账号未绑定"}), 400

    user = db.session.scalar(select(User).where(User.username == username))
    if user is None:
        return jsonify({"success": False, "message": "用户不存在"}), 404

    if zhixue_account.users is None or user not in zhixue_account.users:
        return jsonify({"success": False, "message": "用户未绑定该智学网账号"}), 400

    user.zhixue = None
    db.session.commit()

    return jsonify({"success": True, "message": "已解绑该智学网账号"}), 200


@admin_bp.route("/user/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    """管理员更新用户信息"""
    # TODO: 限制传入字段类型
    user = db.get_or_404(User, user_id)
    data = request.get_json()

    allowed_fields = ["email", "is_active", "permissions", "manual_school_id", "email_verified"]

    for field in allowed_fields:
        if field in data:
            if field == "email":
                existing_user = db.session.scalar(select(User).where(User.email == data[field], User.id != user_id))
                if existing_user:
                    return jsonify({"success": False, "message": "邮箱已被其他用户使用"}), 400
            if field == "permissions":
                if not isinstance(data[field], str) or len(data[field]) != 5 or not all(c in "0123" for c in data[field]):
                    return jsonify({"success": False, "message": "权限格式无效"}), 400
            if field == "manual_school_id":
                # 验证：已绑定智学网账号的用户不能手动分配学校
                if user.zhixue_account_id is not None:
                    return jsonify({"success": False, "message": "该用户已绑定智学网账号，无法手动分配学校"}), 400
                # 验证学校存在性（如果不是清空操作）
                if data[field] is not None:
                    school = db.session.get(School, data[field])
                    if not school:
                        return jsonify({"success": False, "message": "学校不存在"}), 404
            setattr(user, field, data[field])

    if "password" in data:
        user.set_password(data["password"])

    if "role" in data:
        role = data["role"]
        if role not in ["admin", "user"]:
            return jsonify({"success": False, "message": "无效的角色"}), 400
        permissions = "10110"
        if role == "admin":
            permissions = "33333"
        user.permissions = permissions
        user.role = role

    db.session.commit()
    return jsonify({"success": True, "message": "用户信息已更新", "user": user.to_dict()}), 200


# TODO: DELETE /admin/cache/exams; DELETE /admin/cache/exams/{exam_id} etc
@admin_bp.route("/cache", methods=["DELETE"])
def clear_cache():
    """清除缓存"""
    cache_dir = Path(__file__).parents[4] / "cache"

    try:
        for item in cache_dir.glob("*"):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                rmtree(item)

        return jsonify({"success": True, "message": "缓存已清除"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": "清除缓存失败", "error": str(e)}), 500


@admin_bp.route("/su/<string:username>", methods=["POST"])
def switch_user(username):
    """管理员切换用户"""
    if session.get("su_mode"):
        return jsonify({"success": False, "message": "已处于 su 模式，请先退出"}), 400

    if username == current_user.username:
        return jsonify({"success": False, "message": "无法切换到自己"}), 400

    target_user = db.session.scalar(select(User).where(User.username == username))
    if target_user is None:
        return jsonify({"success": False, "message": "目标用户不存在"}), 404

    if target_user.is_active is False:
        return jsonify({"success": False, "message": "目标用户已被封禁，无法切换"}), 400

    # 保存原管理员信息（必须在 login_user 之前）
    admin_username = current_user.username
    session["su_mode"] = True
    session["original_user_id"] = current_user.id
    session["su_user_id"] = target_user.id

    login_user(target_user)

    logger.info(f"管理员 {admin_username} 切换到用户 {target_user.username}")

    return jsonify({
        "success": True,
        "message": f"已切换到用户 {target_user.username}",
        "user": target_user.to_dict()
    }), 200


@admin_bp.route("/su/exit", methods=["POST"])
def exit_su():
    """退出 su 模式，恢复管理员身份"""
    if not session.get("su_mode"):
        return jsonify({"success": False, "message": "当前不在 su 模式"}), 400

    original_user_id = session.get("original_user_id")
    if not original_user_id:
        return jsonify({"success": False, "message": "数据异常"}), 500

    admin_user = db.session.get(User, original_user_id)
    if admin_user is None:
        return jsonify({"success": False, "message": "原账户不存在"}), 404

    logger.info(f"管理员 {admin_user.username} 退出 su 模式")

    session.pop("su_user_id", None)
    session.pop("su_mode", None)
    session.pop("original_user_id", None)

    login_user(admin_user)

    return jsonify({
        "success": True,
        "message": "已退出 su 模式",
        "user": admin_user.to_dict()
    }), 200
