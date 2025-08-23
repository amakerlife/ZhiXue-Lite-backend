from pathlib import Path
from typing import cast
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
import os
import time
from openpyxl import Workbook
from sqlalchemy import select, desc
from app.database import db
from app.database.models import Exam, Score, UserExam, Student
from app.task.repository import create_task
from app.utils.paginate import paginated_json
from app import limiter
from flask_limiter.util import get_remote_address

exam_bp = Blueprint("exam", __name__)


def get_ip_limit():
    """基于 IP 的限制"""
    return get_remote_address()


def get_user_limit():
    """基于用户的限制"""
    if current_user.is_authenticated:
        return f"user_{current_user.id}"
    return get_remote_address()


def zhixue_account_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.zhixue:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        return f(*args, **kwargs)
    return decorated_function


def admin_or_special_user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"success": False, "message": "权限不足，仅管理员可使用此功能"}), 403
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

    stmt = select(UserExam).where(UserExam.zhixue_id == current_user.zhixue_account_id).join(Exam)
    if query:
        stmt = stmt.where(Exam.name.contains(query))

    exams = db.session.scalars(stmt.order_by(desc(Exam.created_at))).all()

    paginated_exams = paginated_json(exams, page, per_page)
    exam_list = []
    for item in paginated_exams["items"]:
        exam_list.append({
            "id": item.exam.id,
            "name": item.exam.name,
            "created_at": item.exam.created_at,
            "is_saved": item.exam.is_saved
        })

    return jsonify({
        "success": True,
        "exams": exam_list,
        "pagination": paginated_exams["pagination"]
    }), 200


@exam_bp.route("/list/fetch", methods=["GET", "POST"])
@login_required
@zhixue_account_required
@limiter.limit("3 per 20 minutes",
               key_func=get_user_limit,
               deduct_when=lambda response: response.status_code == 403
               )
@limiter.limit("10/day",
               key_func=get_user_limit,
               deduct_when=lambda response: response.status_code == 403
               )
def fetch_exam_list():
    """
    从源服务器拉取当前学生的考试列表
    """
    task = create_task(
        task_type="fetch_exam_list",
        user_id=current_user.id,
        timeout=180
    )
    return jsonify({
        "success": True,
        "task_id": task.uuid,
        "message": "考试列表拉取任务已创建，请通过任务 ID 查询进度"
    }), 202


@exam_bp.route("/<string:exam_id>", methods=["GET"])
@login_required
@zhixue_account_required
@limiter.limit("5 per 20 minutes",
               key_func=get_user_limit,
               deduct_when=lambda response: response.status_code == 403
               )
@limiter.limit("30/day",
               key_func=get_user_limit,
               deduct_when=lambda response: response.status_code == 403
               )
def get_exam_info(exam_id):
    """
    获取指定考试的基本信息
    """
    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在或未被保存"}), 404

    return jsonify({
        "success": True,
        "exam": {
            "id": exam.id,
            "name": exam.name,
            "school_id": exam.school_id,
            "is_saved": exam.is_saved,
            "created_at": exam.created_at
        }
    }), 200


@exam_bp.route("/fetch/<string:exam_id>", methods=["GET", "POST"])
@login_required
@zhixue_account_required
def fetch_exam(exam_id):
    """
    拉取指定考试的详细信息
    """
    force_refresh = request.args.get("force_refresh", "false").lower() == "true"

    task = create_task(
        task_type="fetch_exam_details",
        user_id=current_user.id,
        parameters={"exam_id": exam_id, "force_refresh": force_refresh},
        timeout=180
    )
    return jsonify({
        "success": True,
        "task_id": task.uuid,
        "message": "考试详情拉取任务已创建，请通过任务 ID 查询进度"
    }), 202


@exam_bp.route("/score/<string:exam_id>", methods=["GET"])
@login_required
@zhixue_account_required
def get_user_exam_score(exam_id):
    """
    获取用户在指定考试中的分数和详细信息
    """
    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在或未被保存"}), 404

    stmt = select(Score).where(Score.exam_id == exam_id, Score.student_id == current_user.zhixue_account_id).order_by(Score.sort)
    raw_scores = db.session.scalars(stmt).all()
    scores = []
    for raw_score in raw_scores:
        scores.append({
            "subject_id": raw_score.subject_id,
            "subject_name": raw_score.subject_name,
            "score": raw_score.score,
            "standard_score": raw_score.standard_score,
            "class_rank": raw_score.class_rank,
            "school_rank": raw_score.school_rank,
            "sort": raw_score.sort,
        })

    return jsonify({
        "success": True,
        "id": exam.id,
        "name": exam.name,
        "school_id": exam.school_id,
        "is_saved": exam.is_saved,
        "created_at": exam.created_at,
        "scores": scores
    }), 200


@exam_bp.route("/scoresheet/<string:exam_id>", methods=["GET"])
@login_required
@admin_or_special_user_required
def generate_scoresheet(exam_id):
    """
    生成指定考试的成绩单 Excel 文件
    仅管理员可使用
    """
    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在"}), 404

    if not exam.is_saved:
        return jsonify({"success": False, "message": "考试数据尚未保存，请先拉取考试详情"}), 400

    stmt = select(Score).where(Score.exam_id == exam_id).join(Student)
    scores_data = db.session.scalars(stmt).all()

    if not scores_data:
        return jsonify({"success": False, "message": "该考试暂无成绩数据"}), 404

    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("Failed to create worksheet")
    ws.title = "成绩单"

    student_dict = {}
    subject_info = {}

    for score in scores_data:
        student_id = score.student_id
        if student_id not in student_dict:
            student_dict[student_id] = {
                "name": score.student.name,
                "label": score.student.label,
                "class_name": score.class_name,
                "subjects": {}
            }

        subject_name = score.subject_name
        if subject_name not in subject_info:
            subject_info[subject_name] = score.sort

        student_dict[student_id]["subjects"][subject_name] = {
            "score": score.score,
            "standard_score": score.standard_score,
            "class_rank": score.class_rank,
            "school_rank": score.school_rank
        }

    subject_names = sorted(subject_info.keys(), key=lambda x: subject_info[x])

    titles = ["姓名", "标签", "班级"]
    for subject_name in subject_names:
        titles.extend([
            f"{subject_name}成绩",
            f"{subject_name}班次",
            f"{subject_name}校次"
        ])
    ws.append(titles)

    for student_id, student_info in student_dict.items():
        row = [
            student_info["name"],
            student_info["label"],
            student_info["class_name"]
        ]

        for subject_name in subject_names:
            subject_data = student_info["subjects"].get(subject_name, {})
            row.extend([
                subject_data.get("score", ""),
                subject_data.get("class_rank", ""),
                subject_data.get("school_rank", "")
            ])

        ws.append(row)

    cache_dir = Path(__file__).parents[4] / "cache"
    os.makedirs(cache_dir, exist_ok=True)

    filename = f"scoresheet_{exam_id}_{int(time.time())}.xlsx"
    file_path = os.path.join(cache_dir, filename)

    wb.save(file_path)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"{exam.name}_成绩单.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
