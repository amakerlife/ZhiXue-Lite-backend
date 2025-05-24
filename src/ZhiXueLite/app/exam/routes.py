from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.utils.account.student import login_student, login_student_session
from app.database import db
from app.exam.models import Student, Exam, UserExam, Subject, Score

exam_bp = Blueprint("exam", __name__)


def zhixue_account_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.zhixue:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        return f(*args, **kwargs)
    return decorated_function


@exam_bp.route("/list", methods=["GET"])
@login_required
@zhixue_account_required
def get_exam_list():
    """
    从数据库获取当前学生的考试列表
    可选参数
    - page: 页码，默认为 1
    - per_page: 每页数量，默认为 10
    - query: 搜索关键字
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    query = request.args.get("query", "", type=str)
    exams = UserExam.query.filter_by(zhixue_username=current_user.zhixue.username).join(Exam)
    if query:
        exams = exams.filter(Exam.name.contains(query))
    exams = exams.order_by(Exam.created_at.desc())
    pagination = exams.paginate(page=page, per_page=per_page, error_out=False)
    exams = pagination.items
    exam_list = [{"id": item.exam.id, "name": item.exam.name} for item in exams]
    return jsonify({
        "success": True,
        "exams": exam_list,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_prev": pagination.has_prev,
            "has_next": pagination.has_next
        }
    }), 200


# TODO: 后台任务处理
@exam_bp.route("/list/fetch", methods=["GET"])
@login_required
@zhixue_account_required
def fetch_exam_list():
    """
    从源服务器拉取当前学生的考试列表
    """
    student_account = login_student_session(current_user.zhixue.cookie)
    current_user.zhixue.cookie = student_account.get_cookie()
    db.session.commit()

    exams = student_account.get_exams()

    # 将考试列表存入数据库
    for exam in exams:
        # 检查考试是否已存在
        existing_exam = Exam.query.filter_by(id=exam.id).first()
        if not existing_exam:
            new_exam = Exam()
            new_exam.id = exam.id
            new_exam.name = exam.name
            new_exam.created_at = exam.create_time
            db.session.add(new_exam)
            db.session.commit()

        # 检查用户考试记录是否已存在
        user_exam = UserExam.query.filter_by(
            zhixue_username=current_user.zhixue.username, exam_id=exam.id
        ).first()
        if not user_exam:
            new_user_exam = UserExam()
            new_user_exam.zhixue_username = current_user.zhixue.username
            new_user_exam.exam_id = exam.id
            db.session.add(new_user_exam)
            db.session.commit()

    result = UserExam.query.filter_by(zhixue_username=current_user.zhixue.username).join(Exam).order_by(Exam.created_at.desc()).all()
    exams = [
        {
            "id": item.exam.id,
            "name": item.exam.name,
            "created_at": item.exam.created_at,
        }
        for item in result
    ]

    return jsonify({"success": True, "exams": exams}), 200
