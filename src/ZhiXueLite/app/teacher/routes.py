from functools import wraps
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select
from app.database import db
from app.models.zhixuedb import ZhiXueTeacher
from app.models.teacher import login_teacher
teacher_bp = Blueprint("teacher", __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"success": False, "message": "权限不足"}), 403
        return f(*args, **kwargs)
    return decorated_function


@teacher_bp.route("/list", methods=["GET"])
@login_required
@admin_required
def get_teacher_list():
    """获取教师账号列表"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)

    stmt = select(ZhiXueTeacher)
    if query:
        stmt = stmt.where(ZhiXueTeacher.username.contains(query) | ZhiXueTeacher.school.name.contains(query))

    teachers = db.session.scalars(stmt).all()

    total = len(teachers)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_teachers = teachers[start:end]

    teacher_list = [{
        "username": teacher.username,
        "school_name": teacher.school.name,
    } for teacher in paginated_teachers]

    return jsonify({
        "success": True,
        "teachers": teacher_list,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "has_prev": page > 1,
            "has_next": end < total
        }
    }), 200


@teacher_bp.route("/add", methods=["POST"])
@login_required
@admin_required
def add_teacher():
    """添加教师账号"""
    data = request.get_json()

    if not all(key in data for key in ("username", "password")):
        return jsonify({"success": False, "message": "缺少必要字段"}), 400

    existing_teacher = db.session.scalar(select(ZhiXueTeacher).where(ZhiXueTeacher.username == data["username"]))
    if existing_teacher:
        return jsonify({"success": False, "message": "该教师账号已存在"}), 400

    try:
        teacher_account = login_teacher(
            data["username"],
            data["password"],
            data.get("login_method", "changyan")
        )

        # 创建教师记录
        teacher = ZhiXueTeacher(
            username=data["username"],
            password=data["password"],
            cookie=teacher_account.get_cookie(),
            school_id=teacher_account.school.id,
            school_name=teacher_account.school.name,
            login_method=data.get("login_method", "changyan"),
        )

        db.session.add(teacher)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "教师账号添加成功",
            "teacher": {
                "username": teacher.username,
                "school_name": teacher.school.name,
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "教师账号验证失败，请检查用户名密码"}), 400


@teacher_bp.route("/<int:teacher_id>", methods=["PUT"])
@login_required
@admin_required
def update_teacher(teacher_id):
    """更新教师账号"""
    teacher = db.get_or_404(ZhiXueTeacher, teacher_id)
    data = request.get_json()

    allowed_fields = ["password", "login_method", "is_active"]

    for field in allowed_fields:
        if field in data:
            setattr(teacher, field, data[field])

    # 如果更新了密码或登录方式，需要重新验证
    if "password" in data:
        try:
            teacher_account = login_teacher(
                teacher.username,
                teacher.password,
                teacher.login_method
            )
            teacher.cookie = teacher_account.get_cookie()
        except Exception as e:
            return jsonify({"success": False, "message": "教师账号验证失败"}), 400

    db.session.commit()
    return jsonify({"success": True, "message": "教师账号更新成功"}), 200


@teacher_bp.route("/<int:teacher_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_teacher(teacher_id):
    """删除教师账号"""
    teacher = db.get_or_404(ZhiXueTeacher, teacher_id)

    db.session.delete(teacher)
    db.session.commit()

    return jsonify({"success": True, "message": "教师账号删除成功"}), 200


@teacher_bp.route("/<int:teacher_id>", methods=["GET"])
@login_required
@admin_required
def get_teacher_detail(teacher_id):
    """获取教师账号详情"""
    teacher = db.get_or_404(ZhiXueTeacher, teacher_id)

    teacher_detail = {
        "username": teacher.username,
        "school_name": teacher.school.name,
        "login_method": teacher.login_method,
    }

    return jsonify({"success": True, "teacher": teacher_detail}), 200