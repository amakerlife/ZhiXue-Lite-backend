from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import select, desc
from app.database import db
from app.exam.models import Exam, UserExam
from app.utils.account.student import login_student_session
from app.task.manager import task_manager
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

    stmt = select(UserExam).where(UserExam.zhixue_username == current_user.zhixue.username).join(Exam)
    if query:
        stmt = stmt.where(Exam.name.contains(query))
    stmt = stmt.order_by(desc(Exam.created_at))

    # 执行查询并分页
    exams = db.session.scalars(stmt).all()

    # 手动分页
    total = len(exams)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_exams = exams[start:end]

    exam_list = [{"id": item.exam.id, "name": item.exam.name, "created_at": item.exam.created_at}
                 for item in paginated_exams]

    return jsonify({
        "success": True,
        "exams": exam_list,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "has_prev": page > 1,
            "has_next": end < total
        }
    }), 200


# 使用后台任务处理
@exam_bp.route("/list/fetch", methods=["GET", "POST"])
@login_required
@zhixue_account_required
def fetch_exam_list():
    """
    从源服务器拉取当前学生的考试列表（后台任务）
    """
    # 创建后台任务
    task = task_manager.create_task('fetch_exam_list', current_user.id)

    return jsonify({
        "success": True,
        "task_id": task.id,
        "message": "考试列表拉取任务已创建，请通过任务 ID 查询进度"
    }), 201


# 保留同步版本
@exam_bp.route("/list/fetch_sync", methods=["GET"])
@login_required
@zhixue_account_required
def fetch_exam_list_sync():
    """
    从源服务器拉取当前学生的考试列表（同步版本）
    """
    student_account = login_student_session(current_user.zhixue.cookie)
    current_user.zhixue.cookie = student_account.get_cookie()
    db.session.commit()

    exams = student_account.get_exams()

    # 将考试列表存入数据库
    for exam in exams:
        # 检查考试是否已存在
        existing_exam = db.session.execute(select(Exam).filter_by(id=exam.id)).scalar_one_or_none()
        if not existing_exam:
            new_exam = Exam(
                id=exam.id,
                name=exam.name,
                created_at=exam.create_time
            )
            db.session.add(new_exam)
            db.session.flush()

        # 检查用户考试记录是否已存在
        user_exam = db.session.execute(
            select(UserExam).filter_by(
                zhixue_username=current_user.zhixue.username, exam_id=exam.id
            )
        ).scalar_one_or_none()
        if not user_exam:
            new_user_exam = UserExam(
                zhixue_username=current_user.zhixue.username,
                exam_id=exam.id
            )
            db.session.add(new_user_exam)

    db.session.commit()

    stmt = select(UserExam).join(Exam).where(UserExam.zhixue_username ==
                                             current_user.zhixue.username).order_by(Exam.created_at.desc())
    result = db.session.scalars(stmt).all()
    exams = [
        {
            "id": item.exam.id,
            "name": item.exam.name,
            "created_at": item.exam.created_at,
        }
        for item in result
    ]

    return jsonify({"success": True, "exams": exams}), 200
