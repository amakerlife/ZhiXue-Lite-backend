from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import select
from app.database import db
from app.models.zhixuedb import School, ZhiXueUser
from app.user.models import User
from app.utils.paginate import paginated_json

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@login_required
def is_admin():
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

    stmt = select(User)
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

    stmt = select(ZhiXueUser)
    if query:
        stmt = stmt.where(ZhiXueUser.username.contains(query))

    zhixue_accounts = db.session.scalars(stmt).all()
    paginated_accounts = paginated_json(zhixue_accounts, page, per_page)
    account_list = [user.to_dict_all() for user in paginated_accounts["items"]]

    return jsonify({
        "success": True,
        "zhixue_accounts": account_list,
        "pagination": paginated_accounts["pagination"]
    }), 200