from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, desc
from app.database import db
from app.task.models import BackgroundTask, TaskStatus
from app.task.manager import task_manager

task_bp = Blueprint("task", __name__)


@task_bp.route("/create", methods=["POST"])
@login_required
def create_task():
    """
    创建后台任务
    """
    data = request.get_json()
    task_type = data.get('task_type')
    parameters = data.get('parameters', {})

    if not task_type:
        return jsonify({"success": False, "message": "缺少任务类型"}), 400

    if task_type not in task_manager.task_handlers:
        return jsonify({"success": False, "message": "不支持的任务类型"}), 400

    task = task_manager.create_task(task_type, current_user.id, parameters)

    return jsonify({
        "success": True,
        "task_id": task.id,
        "message": "任务已创建"
    }), 201


@task_bp.route("/status/<string:task_id>", methods=["GET"])
@login_required
def get_task_status(task_id):
    """
    获取任务状态
    """
    stmt = select(BackgroundTask).where(
        (BackgroundTask.id == task_id) & (BackgroundTask.user_id == current_user.id)
    )
    task = db.session.scalar(stmt)

    if not task:
        return jsonify({"success": False, "message": "任务不存在"}), 404

    return jsonify({
        "success": True,
        "task": task.to_dict()
    }), 200


@task_bp.route("/list", methods=["GET"])
@login_required
def get_user_tasks():
    """
    获取用户的任务列表
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    status_filter = request.args.get("status")

    stmt = select(BackgroundTask).where(BackgroundTask.user_id == current_user.id)

    if status_filter:
        try:
            status_enum = TaskStatus(status_filter)
            stmt = stmt.where(BackgroundTask.status == status_enum.value)
        except ValueError:
            return jsonify({"success": False, "message": "无效的状态值"}), 400

    stmt = stmt.order_by(desc(BackgroundTask.created_at))

    # 执行查询并分页
    tasks = db.session.scalars(stmt).all()

    # 手动分页
    total = len(tasks)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_tasks = tasks[start:end]

    task_list = [task.to_dict() for task in paginated_tasks]

    return jsonify({
        "success": True,
        "tasks": task_list,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "has_prev": page > 1,
            "has_next": end < total
        }
    }), 200


@task_bp.route("/cancel/<string:task_id>", methods=["POST"])
@login_required
def cancel_task(task_id):
    """
    取消任务（仅限待处理状态的任务）
    """
    stmt = select(BackgroundTask).where(
        (BackgroundTask.id == task_id) & (BackgroundTask.user_id == current_user.id)
    )
    task = db.session.scalar(stmt)

    if not task:
        return jsonify({"success": False, "message": "任务不存在"}), 404

    if task.status != TaskStatus.PENDING.value:
        return jsonify({"success": False, "message": "只能取消待处理的任务"}), 400

    task_manager.update_task_status(task_id, TaskStatus.FAILED, error_message="用户取消")

    return jsonify({"success": True, "message": "任务已取消"}), 200
