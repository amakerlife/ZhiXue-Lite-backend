from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import select, desc
from app.database import db
from app.database.models import BackgroundTask, Exam, UserExam
from app.task.repository import create_task
from app.utils.paginate import paginated_json
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

    stmt = select(UserExam).where(UserExam.zhixue_id == current_user.zhixue.id).join(Exam)
    if query:
        stmt = stmt.where(Exam.name.contains(query))

    exams = db.session.scalars(stmt.order_by(desc(Exam.created_at))).all()

    paginated_exams = paginated_json(exams, page, per_page)
    exam_list = [{"id": item.exam.id, "name": item.exam.name, "created_at": item.exam.created_at}
                 for item in paginated_exams["items"]]

    return jsonify({
        "success": True,
        "exams": exam_list,
        "pagination": paginated_exams["pagination"]
    }), 200


@exam_bp.route("/list/fetch", methods=["GET", "POST"])
@login_required
@zhixue_account_required
def fetch_exam_list():
    """
    从源服务器拉取当前学生的考试列表
    """
    task = create_task(
        task_type="fetch_exam_list",
        user_id=current_user.id,
        timeout=1
    )
    return jsonify({
        "success": True,
        "task_id": task.uuid,
        "message": "考试列表拉取任务已创建，请通过任务 ID 查询进度"
    }), 202
