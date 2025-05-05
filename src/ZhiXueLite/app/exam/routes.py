from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.database import db
from app.exam.models import Student, Exam, Subject, Score
from app.utils.account.teacher import ExtendedTeacherAccount

exam_bp = Blueprint("exam", __name__)

@exam_bp.route("/list", methods=["GET"])
@login_required
def get_exam_list():
    """
    获取当前学生的考试列表
    """
    exams = Exam.query.all() ???
    exam_list = [{"exam_id": exam.exam_id, "exam_name": exam.exam_name} for exam in exams]
    return jsonify({"exams": exam_list}), 200