from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, desc
from app.database import db
from app.database.models import BackgroundTask, TaskStatus
from app.utils.paginate import paginated_json
from . import repository as task_repo


task_bp = Blueprint("task", __name__)


@task_bp.route("/status/<string:task_uuid>", methods=["GET"])
@login_required
def get_task_status(task_uuid):
    """
    获取任务状态
    """
    stmt = select(BackgroundTask).where(
        (BackgroundTask.uuid == task_uuid) & (BackgroundTask.user_id == current_user.id)
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

    tasks = db.session.scalars(stmt.order_by(desc(BackgroundTask.created_at))).all()

    paginated_tasks = paginated_json(tasks, page, per_page)
    task_list = [task.to_dict() for task in paginated_tasks["items"]]

    return jsonify({
        "success": True,
        "tasks": task_list,
        "pagination": paginated_tasks["pagination"]
    }), 200


@task_bp.route("/cancel/<string:task_uuid>", methods=["POST"])
@login_required
def cancel_task(task_uuid):
    """
    取消任务（仅限待处理状态的任务）
    """
    stmt = select(BackgroundTask).where(
        (BackgroundTask.uuid == task_uuid) & (BackgroundTask.user_id == current_user.id)
    )
    task = db.session.scalar(stmt)

    if not task:
        return jsonify({"success": False, "message": "任务不存在"}), 404

    if task.status != TaskStatus.PENDING.value:
        return jsonify({"success": False, "message": "只能取消待处理的任务"}), 400

    task_repo.update_task_status(task_uuid, TaskStatus.FAILED, error_message="用户取消")

    return jsonify({"success": True, "message": "任务已取消"}), 200
