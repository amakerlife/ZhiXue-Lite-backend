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

# TODO: 持久化智学网 session


@exam_bp.route("/list", methods=["GET"])  # TODO: 添加分页
@login_required
@zhixue_account_required
def get_exam_list():
    """
    从数据库获取当前学生的考试列表
    """
    exams = UserExam.query.filter_by(zhixue_username=current_user.zhixue.username).all()
    exam_list = [{"exam_id": item.exam.id, "exam_name": item.exam.name} for item in exams]
    return jsonify({"success": True, "exams": exam_list}), 200


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

    # 按 userexam.exam.created_at 降序排列考试列表
    result = UserExam.query.filter_by(zhixue_username=current_user.zhixue.username).all()
    exams = [
        {
            "id": item.exam.id,
            "name": item.exam.name,
            "created_at": item.exam.created_at,
        }
        for item in result
    ]

    return jsonify({"success": True, "exams": exams}), 200
