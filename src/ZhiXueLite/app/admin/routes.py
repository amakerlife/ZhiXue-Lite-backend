from os import rmdir
from pathlib import Path
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import select
from app.database import db
from app.database.models import Exam, School, ZhiXueStudentAccount, User
from app.utils.paginate import paginated_json

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@login_required
def is_admin():
    if request.method == "OPTIONS":
        return

    if current_user.role != "admin":
        return jsonify({"success": False, "message": "Access Denied"}), 403


@admin_bp.route("/list/schools", methods=["GET"])
def list_schools():
    """列出所有学校"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)

    stmt = select(School)
    if query:
        stmt = stmt.where(School.name.contains(query) | School.id.contains(query))

    schools = db.session.scalars(stmt).all()
    paginated_schools = paginated_json(schools, page, per_page)
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

    users = db.session.scalars(stmt).all()
    paginated_users = paginated_json(users, page, per_page)
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

    stmt = select(ZhiXueStudentAccount)
    if query:
        stmt = stmt.where(ZhiXueStudentAccount.username.contains(query))

    zhixue_accounts = db.session.scalars(stmt).all()
    paginated_accounts = paginated_json(zhixue_accounts, page, per_page)
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

    stmt = select(Exam).order_by(Exam.created_at.desc())
    if query:
        stmt = stmt.where(Exam.name.contains(query) | Exam.id.contains(query))

    exams = db.session.scalars(stmt).all()
    paginated_exams = paginated_json(exams, page, per_page)
    exam_list = [
        {
            "id": exam.id,
            "name": exam.name,
            "is_saved": exam.is_saved,
            "school": exam.school.name,
            "created_at": exam.created_at
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
    user = db.get_or_404(User, user_id)
    data = request.get_json()

    allowed_fields = ["email", "is_active", "permissions"]

    for field in allowed_fields:
        if field in data:
            if field == "email":
                existing_user = db.session.scalar(select(User).where(User.email == data[field], User.id != user_id))
                if existing_user:
                    return jsonify({"success": False, "message": "邮箱已被其他用户使用"}), 400
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

    if "permissions" in data:
        if data["permissions"][4] == "1":
            return jsonify({"success": False, "message": "不可为导出成绩单赋个人权限"}), 400

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
                rmdir(item)

        return jsonify({"success": True, "message": "缓存已清除"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": "清除缓存失败", "error": str(e)}), 500
