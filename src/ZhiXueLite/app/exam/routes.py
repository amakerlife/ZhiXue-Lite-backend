from pathlib import Path
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
from functools import wraps
import os
import time
from openpyxl import Workbook
from sqlalchemy import func, select
from app.database import db
from app.database.models import Exam, ExamSchool, PermissionLevel, Score, User, UserExam, ZhiXueTeacherAccount, PermissionType
from app.models.exceptions import FailedToGetTeacherAccountError
from app.models.teacher import login_teacher_session
from app.task.repository import create_task
from app.utils.paginate import paginate_query
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


def permission_required(permission_type: PermissionType, scope: str):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not has_permission(permission_type, scope):
                return jsonify({"success": False, "message": "Access Denied"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_teacher(exam_id: str, school_id: str | None = None, user: User | None = None) -> ZhiXueTeacherAccount:
    if not school_id:
        exam = db.session.scalar(select(Exam).where(Exam.id == exam_id))
        if exam is None or len(exam.schools) > 1:
            raise FailedToGetTeacherAccountError(
                f"exam {exam_id} is multi-school exam or can not be found, school_id required")
        else:
            school_id = exam.schools[0].school_id
    if user and not school_id and user.zhixue:
        school_id = user.zhixue.school_id
    if not school_id:
        raise FailedToGetTeacherAccountError(f"teacher not found for exam_id: {exam_id}")

    teacher = db.session.scalar(select(ZhiXueTeacherAccount).where(ZhiXueTeacherAccount.school_id == school_id))
    if teacher is None:
        raise FailedToGetTeacherAccountError(f"teacher not found for school_id: {school_id}")
    return teacher


def has_permission(type: PermissionType, scope: str) -> bool:
    if scope == "self":
        return current_user.has_permission(type, PermissionLevel.SELF)
    elif scope == "school":
        return current_user.has_permission(type, PermissionLevel.SCHOOL)
    elif scope == "all":
        return current_user.has_permission(type, PermissionLevel.GLOBAL)
    else:
        return False


@exam_bp.route("/list", methods=["GET"])
@login_required
@permission_required(PermissionType.VIEW_EXAM_LIST, "self")
def get_exam_list():
    """
    从数据库获取考试列表
    可选参数
    - page: 页码，默认为 1
    - per_page: 每页数量，默认为 10
    - query: 搜索关键字
    - scope: 范围，school（校内）/self（个人）/all（全部），默认为 self
    - school_id: 范围为 all 时的学校 id，默认不限制
    - start_time: 开始日期，时间戳，默认 0（不限制）
    - end_time: 结束日期，时间戳，默认 0（不限制）
    """
    page = max(1, request.args.get("page", 1, type=int))
    per_page = max(1, min(20, request.args.get("per_page", 10, type=int)))
    query = request.args.get("query", "", type=str)
    scope = request.args.get("scope", "self", type=str)
    school_id = request.args.get("school_id", "", type=str)
    start_time = request.args.get("start_time", 0, type=float)
    end_time = request.args.get("end_time", 0, type=float)

    if not has_permission(PermissionType.VIEW_EXAM_LIST, scope):
        return jsonify({"success": False, "message": "无权访问该考试数据"}), 403

    # 检查用户是否满足查询范围的要求
    if scope == "self" and current_user.zhixue is None:
        return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
    if scope == "school" and current_user.school_id is None:
        return jsonify({"success": False, "message": "请先绑定智学网账号或联系管理员分配学校"}), 401

    if scope == "self":
        stmt = select(Exam).join(UserExam).where(UserExam.zhixue_id == current_user.zhixue_account_id)
    elif scope == "school":
        # 支持联考：通过 ExamSchool 关联表查询该学校的所有考试
        stmt = select(Exam).join(ExamSchool).where(ExamSchool.school_id == current_user.school_id)
    elif scope == "all":
        stmt = select(Exam)
        if school_id:
            # 支持联考：通过 ExamSchool 关联表过滤学校
            stmt = stmt.join(ExamSchool).where(ExamSchool.school_id == school_id)
    else:
        return jsonify({"success": False, "message": "参数不合法"}), 400

    if query:
        stmt = stmt.where(Exam.name.contains(query))

    if start_time > 0 and end_time > 0 and end_time >= start_time:
        stmt = stmt.where((Exam.created_at >= start_time) & (Exam.created_at <= end_time))
    elif not (start_time == 0 and end_time == 0):
        return jsonify({"success": False, "message": "参数不合法"}), 400

    stmt = stmt.order_by(Exam.created_at.desc(), Exam.id.desc())
    paginated_exams = paginate_query(stmt, page, per_page)
    exam_list = []

    has_global_permission = current_user.has_permission(
        PermissionType.VIEW_EXAM_LIST, PermissionLevel.GLOBAL
    )
    user_school_id = current_user.school_id

    for item in paginated_exams["items"]:
        if has_global_permission:
            schools = item.get_schools_saved_status()
        elif user_school_id:
            schools = [
                {
                    "school_id": es.school_id,
                    "school_name": es.school.name if es.school else None,
                    "is_saved": es.is_saved
                }
                for es in item.schools
                if es.school_id == user_school_id
            ]
        else:
            schools = []

        exam_list.append({
            "id": item.id,
            "name": item.name,
            "created_at": item.created_at,
            "schools": schools
        })

    return jsonify({
        "success": True,
        "exams": exam_list,
        "pagination": paginated_exams["pagination"]
    }), 200


@exam_bp.route("/fetch-list-params", methods=["GET"])
@login_required
@permission_required(PermissionType.FETCH_DATA, "school")
def get_fetch_params():
    """
    获取拉取教师考试列表所需的参数
    """
    school_id = request.args.get("school_id", "", type=str)
    if school_id == "":
        school_id = current_user.school_id if current_user.school_id else ""
        if school_id == "":
            return jsonify({"success": False, "message": "参数不合法"}), 400
    else:
        if current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.GLOBAL):
            pass
        elif current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SCHOOL):
            if current_user.school_id is None or current_user.school_id != school_id:
                return jsonify({"success": False, "message": "无权访问该考试数据"}), 403
        else:
            return jsonify({"success": False, "message": "Access Denied"}), 403

    try:
        teacher_account = get_teacher("", school_id=school_id)
    except FailedToGetTeacherAccountError:
        return jsonify({"success": False, "message": "该学校暂无可用教师账号"}), 404
    teacher_account = login_teacher_session(teacher_account.cookie)
    params = teacher_account.get_exam_list_selections()
    return jsonify({
        "success": True,
        "params": params
    }), 200


@exam_bp.route("/list/fetch", methods=["GET", "POST"])
@login_required
@permission_required(PermissionType.FETCH_DATA, "self")
@limiter.limit("3 per 20 minutes", key_func=get_user_limit)
@limiter.limit("10/day", key_func=get_user_limit)
def fetch_exam_list():
    """
    从源服务器拉取考试列表
    可选参数
    - query_type: 查询类型，self/school_id，默认为 self
    - school_id: 学校 ID，默认为空（当前用户自身考试列表）
    可选请求体参数
    - params: 拉取参数，格式见 /exam/fetch-list-params 接口返回值
    """
    query_type = request.args.get("query_type", "self", type=str)
    school_id = request.args.get("school_id", "", type=str)
    params = request.get_json().get("params", {})
    if query_type == "self":
        if current_user.zhixue is None:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        task = create_task(
            task_type="fetch_student_exam_list",
            user_id=current_user.id,
            timeout=180
        )
        return jsonify({
            "success": True,
            "task_id": task.uuid,
            "message": "考试列表拉取任务已创建，请通过任务 ID 查询进度"
        }), 202

    else:
        if not school_id:
            school_id = current_user.school_id if current_user.school_id else ""
        if school_id == "":
            return jsonify({"success": False, "message": "参数不合法"}), 400
        if current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.GLOBAL):
            pass
        elif current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SCHOOL):
            if current_user.school_id is None or current_user.school_id != school_id:
                return jsonify({"success": False, "message": "无权访问该考试数据"}), 403
        else:
            return jsonify({"success": False, "message": "Access Denied"}), 403

        task = create_task(
            task_type="fetch_school_exam_list",
            user_id=current_user.id,
            parameters={"school_id": school_id, "query_parameters": params},
            timeout=300
        )
        return jsonify({
            "success": True,
            "task_id": task.uuid,
            "message": "考试列表拉取任务已创建，请通过任务 ID 查询进度"
        }), 202


@exam_bp.route("/<string:exam_id>", methods=["GET"])
@login_required
@permission_required(PermissionType.VIEW_EXAM_DATA, "self")
def get_exam_info(exam_id):
    """
    获取指定考试的基本信息
    """
    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在或未被保存"}), 404

    if current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.GLOBAL):
        pass
    elif current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.SCHOOL):
        if current_user.school_id is None or current_user.school_id not in exam.get_school_ids():
            return jsonify({"success": False, "message": "无权访问该考试"}), 403
    elif current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.SELF):
        if current_user.zhixue is None:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        stmt = select(UserExam).where(
            (UserExam.exam_id == exam_id) &
            (UserExam.zhixue_id == current_user.zhixue_account_id)
        )
        if not db.session.scalar(stmt):
            return jsonify({"success": False, "message": "无权访问该考试或用户暂无该考试记录"}), 403

    # 根据权限返回不同的学校列表
    is_multi_school = len(exam.schools) > 1
    if current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.GLOBAL):
        # GLOBAL 权限：返回所有学校信息
        schools = exam.get_schools_saved_status()
    elif current_user.school_id:
        # 有默认学校：只返回该学校信息
        schools = [
            {
                "school_id": es.school_id,
                "school_name": es.school.name if es.school else None,
                "is_saved": es.is_saved
            }
            for es in exam.schools
            if es.school_id == current_user.school_id
        ]
    else:
        # 无学校信息：返回空列表
        schools = []

    return jsonify({
        "success": True,
        "exam": {
            "id": exam.id,
            "name": exam.name,
            "is_multi_school": is_multi_school,
            "created_at": exam.created_at,
            "schools": schools
        }
    }), 200


@exam_bp.route("/<string:exam_id>/fetch", methods=["GET", "POST"])
@login_required
@permission_required(PermissionType.FETCH_DATA, "self")
@limiter.limit("5 per 20 minutes", key_func=get_user_limit)
@limiter.limit("30/day", key_func=get_user_limit)
def fetch_exam(exam_id):
    """
    拉取指定考试的详细信息
    可选参数
    - force_refresh: 是否强制刷新，默认为 false
    - school_id: 考试所属学校 ID，默认为空（若考试已保存则自动获取，否则为当前用户所在学校）
    """
    force_refresh = request.args.get("force_refresh", "false").lower() == "true"
    school_id = request.args.get("school_id", "", type=str)

    if not current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SCHOOL):
        if current_user.zhixue is None:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        stmt = select(UserExam).where(
            (UserExam.exam_id == exam_id) &
            (UserExam.zhixue_id == current_user.zhixue_account_id)
        )
        if not db.session.scalar(stmt):
            return jsonify({"success": False, "message": "无权拉取该考试数据"}), 403
        school_id = current_user.school_id

    if school_id and not current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.GLOBAL):
        if current_user.school_id is None or (school_id and current_user.school_id != school_id):
            return jsonify({"success": False, "message": "无权访问该考试数据"}), 403

    if force_refresh:
        if current_user.has_permission(PermissionType.REFETCH_EXAM_DATA, PermissionLevel.GLOBAL):
            pass
        elif current_user.has_permission(PermissionType.REFETCH_EXAM_DATA, PermissionLevel.SCHOOL):
            if current_user.school_id is None or (school_id and current_user.school_id != school_id):
                return jsonify({"success": False, "message": "无权使用强制刷新功能"}), 403
        elif current_user.has_permission(PermissionType.REFETCH_EXAM_DATA, PermissionLevel.SELF):
            if current_user.zhixue is None:
                return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
            stmt = select(UserExam).where(
                (UserExam.exam_id == exam_id) &
                (UserExam.zhixue_id == current_user.zhixue_account_id)
            )
            if not db.session.scalar(stmt):
                return jsonify({"success": False, "message": "无权使用强制刷新功能"}), 403
        else:
            return jsonify({"success": False, "message": "Access Denied"}), 403

    if school_id == "" and current_user.has_permission(PermissionType.FETCH_DATA, PermissionLevel.SELF):
        school_id = current_user.school_id

    task = create_task(
        task_type="fetch_exam_details",
        user_id=current_user.id,
        parameters={"exam_id": exam_id, "force_refresh": force_refresh, "school_id": school_id},
        timeout=300
    )
    return jsonify({
        "success": True,
        "task_id": task.uuid,
        "message": "考试详情拉取任务已创建，请通过任务 ID 查询进度"
    }), 202


@exam_bp.route("/<string:exam_id>/score", methods=["GET"])
@login_required
@permission_required(PermissionType.VIEW_EXAM_DATA, "self")
def get_user_exam_score(exam_id):
    """
    获取指定考试中的分数和详细信息。

    Args:
        exam_id (str): 路径参数，考试 ID
        student_id (str, optional): 查询参数，学生 ID，默认为当前用户绑定的智学网账号
        student_name (str, optional): 查询参数，学生姓名，不可与 student_id 同时指定，且使用时必须指定学校 ID
        school_id (str, optional): 查询参数，学校 ID，默认为当前用户所在学校
    """
    student_id = request.args.get("student_id", None)
    student_name = request.args.get("student_name", None)
    school_id = request.args.get("school_id", None)

    if student_id is not None and student_name is not None:
        return jsonify({"success": False, "message": "不可同时指定学生 ID 和姓名"}), 400

    if student_name and school_id is None:
        return jsonify({"success": False, "message": "使用学生姓名查询时必须指定学校 ID"}), 400

    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在或未被保存"}), 404

    if school_id and school_id not in exam.get_school_ids():
        return jsonify({"success": False, "message": "该学校未参与此次考试"}), 400

    if current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.GLOBAL):
        pass
    elif current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.SCHOOL):
        if current_user.school_id is None or current_user.school_id not in exam.get_school_ids():
            return jsonify({"success": False, "message": "无权访问该考试"}), 403
    elif current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.SELF):
        if current_user.zhixue is None:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        stmt = select(UserExam).where(
            (UserExam.exam_id == exam_id) &
            (UserExam.zhixue_id == current_user.zhixue_account_id)
        )
        if not db.session.scalar(stmt):
            return jsonify({"success": False, "message": "无权访问该考试或用户暂无该考试记录"}), 403

    if student_name is not None:
        try:
            teacher_account = get_teacher(exam_id, school_id=school_id)
            teacher = login_teacher_session(teacher_account.cookie)
            student_ids = teacher.get_student_id_by_name(exam_id, student_name)
            if len(student_ids) == 0:
                return jsonify({"success": False, "message": "未找到该学生"}), 404
            elif len(student_ids) > 1:
                return jsonify({"success": False, "message": f"匹配到多个学生：{', '.join(student_ids)}"}), 400
            student_id = student_ids[0]
        except Exception:
            return jsonify({"success": False, "message": "获取学生 ID 失败"}), 500

    if student_id is None:
        student_id = current_user.zhixue_account_id

    if school_id is None:
        if current_user.school_id is None:
            return jsonify({"success": False, "message": "请指定学校 ID"}), 400
        school_id = str(current_user.school_id)

    # 构建成绩数据
    stmt = select(Score).where(
        (Score.exam_id == exam_id) &
        (Score.student_id == student_id) &
        (Score.school_id == school_id)
    ).order_by(Score.sort)
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
            "is_calculated": raw_score.is_calculated,  # 总分是否为计算得到
        })

    # 每科班校内总参考人数，仅支持 PostgreSQL，本地测试环境暂时无法使用
    school_results = class_results = []
    if db.engine.name == "postgresql" and len(raw_scores) > 0:
        stmt = (select(Score.subject_id, func.count(Score.id).label("participant_count"))).where(
            (Score.exam_id == exam_id) &
            (Score.school_id == school_id) &
            (Score.score.op("~")("^-?\\d+(\\.\\d+)?$"))  # 数字，包括负数整数和小数，不统计剔除
        ).group_by(Score.subject_id)
        school_results = db.session.execute(stmt).all()
        stmt = (select(Score.subject_id, func.count(Score.id).label("participant_count"))).where(
            (Score.exam_id == exam_id) &
            (Score.class_name == raw_scores[0].class_name) &
            (Score.score.op("~")("^-?\\d+(\\.\\d+)?$"))
        ).group_by(Score.subject_id)
        class_results = db.session.execute(stmt).all()
    school_participant_counts = {row.subject_id: row.participant_count for row in school_results}
    class_participant_counts = {row.subject_id: row.participant_count for row in class_results}
    for score in scores:
        score["school_participant_count"] = school_participant_counts.get(score["subject_id"], -1)  # -1 for unknown
        score["class_participant_count"] = class_participant_counts.get(score["subject_id"], -1)

    # 参考学校
    is_multi_school = len(exam.schools) > 1
    if current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.GLOBAL):
        # GLOBAL 权限：返回所有参考学校
        schools = exam.get_schools_saved_status()
    elif school_id:
        # 指定了 school_id：只返回该学校信息
        schools = [
            {
                "school_id": es.school_id,
                "school_name": es.school.name if es.school else None,
                "is_saved": es.is_saved
            }
            for es in exam.schools
            if es.school_id == school_id
        ]
    else:
        # 无学校信息：返回空列表
        schools = []

    return jsonify({
        "success": True,
        "id": exam.id,
        "name": exam.name,
        "created_at": exam.created_at,
        "student_id": student_id,
        "scores": scores,
        "is_multi_school": is_multi_school,
        "schools": schools
    }), 200


@exam_bp.route("/<string:exam_id>/scoresheet", methods=["GET"])
@login_required
@permission_required(PermissionType.EXPORT_SCORE_SHEET, "self")
def generate_scoresheet(exam_id):
    """
    生成指定考试的成绩单 Excel 文件
    """
    scope = request.args.get("scope", "school", type=str)  # school or all
    school_id = request.args.get("school_id", "", type=str)

    if (scope == "school" and school_id == "" and current_user.school_id is None):
        return jsonify({"success": False, "message": "用户未绑定学校，无法导出成绩单"}), 400
    if scope == "school" and school_id == "":
        school_id = str(current_user.school_id)

    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在或未被保存"}), 404
    if scope == "school" and school_id not in exam.get_school_ids():
        return jsonify({"success": False, "message": "该学校未参与此次考试"}), 400

    if (scope == "school" and not exam.is_saved_for_school(school_id)):
        return jsonify({"success": False, "message": "考试数据尚未保存，请先拉取考试详情"}), 400

    if current_user.has_permission(PermissionType.EXPORT_SCORE_SHEET, PermissionLevel.GLOBAL):
        pass
    elif current_user.has_permission(PermissionType.EXPORT_SCORE_SHEET, PermissionLevel.SCHOOL):
        if scope == "all" or school_id != current_user.school_id:
            return jsonify({"success": False, "message": "无权访问该考试"}), 403
    elif current_user.has_permission(PermissionType.EXPORT_SCORE_SHEET, PermissionLevel.SELF):
        if scope == "all":
            return jsonify({"success": False, "message": "无权访问该考试"}), 403
        if current_user.zhixue is None:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        stmt = select(UserExam).where(
            (UserExam.exam_id == exam_id) &
            (UserExam.zhixue_id == current_user.zhixue_account_id)
        )
        if not db.session.scalar(stmt):
            return jsonify({"success": False, "message": "无权访问该考试或用户暂无该考试记录"}), 403

    stmt = select(Score).where(Score.exam_id == exam_id)
    if scope == "school":
        stmt = stmt.where(Score.school_id == school_id)
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
                "school": score.school.name if score.school else None,
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

    def parse_rank_value(rank_value):
        """
        解析排名值，提取其中的数字部分
        """
        if rank_value is None or rank_value == "":
            return float('inf')

        if isinstance(rank_value, (int, float)):
            return float(rank_value)

        # 如果是字符串，尝试提取数字
        if isinstance(rank_value, str):
            import re
            match = re.match(r'^(\d+)', rank_value.strip())
            if match:
                return float(match.group(1))

        return float('inf')

    # 排序学生数据：按照每个科目的年级排名、班级排名升序，最后按姓名升序
    def get_sort_key(item):
        student_id, student_info = item
        sort_key = []

        for subject_name in subject_names:
            subject_data = student_info["subjects"].get(subject_name, {})
            school_rank = subject_data.get("school_rank")
            class_rank = subject_data.get("class_rank")

            # 解析排名值为数字
            school_rank_num = parse_rank_value(school_rank)
            class_rank_num = parse_rank_value(class_rank)

            # 升序排序
            sort_key.extend([school_rank_num, class_rank_num])

        sort_key.append(student_info["name"])

        return sort_key

    student_list = sorted(student_dict.items(), key=get_sort_key)

    titles = ["姓名", "学校", "标签", "班级"]
    for subject_name in subject_names:
        titles.extend([
            f"{subject_name}成绩",
            f"{subject_name}班次",
            f"{subject_name}校次"
        ])
    ws.append(titles)

    for student_id, student_info in student_list:
        row = [
            student_info["name"],
            student_info["school"],
            student_info["label"],
            student_info["class_name"]
        ]

        for subject_name in subject_names:
            subject_data = student_info["subjects"].get(subject_name, {})
            score = subject_data.get("score")
            class_rank = subject_data.get("class_rank")
            school_rank = subject_data.get("school_rank")

            row.extend([
                score if score is not None else None,
                class_rank if class_rank is not None else None,
                school_rank if school_rank is not None else None
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


@exam_bp.route("/<string:exam_id>/subject/<string:subject_id>/answersheet", methods=["GET"])
@login_required
@permission_required(PermissionType.VIEW_EXAM_DATA, "self")
def generate_answersheet(exam_id, subject_id):
    """
    生成指定用户指定考试中指定科目的答题卡
    """
    student_id = request.args.get("student_id", None)
    student_name = request.args.get("student_name", None)
    school_id = request.args.get("school_id", None)

    if student_id is not None and student_name is not None:
        return jsonify({"success": False, "message": "不可同时指定学生 ID 和姓名"}), 400

    if student_name and school_id is None:
        return jsonify({"success": False, "message": "使用学生姓名查询时必须指定学校 ID"}), 400

    stmt = select(Exam).where(Exam.id == exam_id)
    exam = db.session.scalar(stmt)
    if not exam:
        return jsonify({"success": False, "message": "考试不存在或未被保存"}), 404

    if len(exam.schools) > 1 and school_id is None:
        return jsonify({"success": False, "message": "该考试为联考，必须指定学校 ID"}), 400

    if current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.GLOBAL):
        pass
    elif current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.SCHOOL):
        if current_user.school_id is None or current_user.school_id not in exam.get_school_ids():
            return jsonify({"success": False, "message": "无权访问该考试"}), 403
    elif current_user.has_permission(PermissionType.VIEW_EXAM_DATA, PermissionLevel.SELF):
        if current_user.zhixue is None:
            return jsonify({"success": False, "message": "请先绑定智学网账号"}), 401
        stmt = select(UserExam).where(
            (UserExam.exam_id == exam_id) &
            (UserExam.zhixue_id == current_user.zhixue_account_id)
        )
        if not db.session.scalar(stmt):
            return jsonify({"success": False, "message": "无权访问该考试或用户暂无该考试记录"}), 403
        if student_id is not None and student_id != current_user.zhixue_account_id:
            return jsonify({"success": False, "message": "权限不足，只能查看自己的成绩"}), 403
        if student_name is not None:
            return jsonify({"success": False, "message": "无权使用学生姓名查询成绩"}), 403

    if student_name is not None:
        try:
            teacher_account = get_teacher(exam_id, school_id=school_id)
            teacher = login_teacher_session(teacher_account.cookie)
            student_ids = teacher.get_student_id_by_name(exam_id, student_name)
            if len(student_ids) == 0:
                return jsonify({"success": False, "message": "未找到该学生"}), 404
            elif len(student_ids) > 1:
                return jsonify({"success": False, "message": f"匹配到多个学生：{', '.join(student_ids)}"}), 400
            student_id = student_ids[0]
        except Exception:
            return jsonify({"success": False, "message": "获取学生 ID 失败"}), 500

    student_id = current_user.zhixue_account_id if not student_id else student_id

    cache_dir = Path(__file__).parents[4] / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    filename = f"answersheet_{exam_id}_{subject_id}_{student_id}.png"
    file_path = os.path.join(cache_dir, filename)

    if os.path.exists(file_path):
        return send_file(
            file_path,
            download_name=f"answersheet_{exam_id}_{subject_id}_{student_id}.png",
            mimetype="image/png"
        )

    try:
        teacher_account = get_teacher(exam_id, school_id=school_id)
        teacher = login_teacher_session(teacher_account.cookie)
        image = teacher.process_answersheet(subject_id, student_id)
    except Exception as e:
        return jsonify({"success": False, "message": "Unknown error occurred"}), 500

    image.save(file_path)

    return send_file(
        file_path,
        download_name=f"answersheet_{exam_id}_{subject_id}_{student_id}.png",
        mimetype="image/png"
    )
