from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Exam, ExamSchool, Score, Student, UserExam, User, ZhiXueTeacherAccount
from app.models.student import login_student_session
from app.models.exceptions import FailedToGetTeacherAccountError
from app.models.teacher import login_teacher_session
from app.utils.crypto import decrypt, encrypt
from task_worker.repository import update_task_progress
from loguru import logger


def get_teacher(session: Session, exam_id: str, school_id: str | None = None) -> ZhiXueTeacherAccount:
    if not school_id:
        exam = session.scalar(select(Exam).where(Exam.id == exam_id))
        if exam is None or len(exam.schools) > 1:
            raise FailedToGetTeacherAccountError(
                f"exam {exam_id} is multi-school exam or can not be found, school_id required")
        else:
            school_id = exam.schools[0].school_id
    if not school_id:
        raise FailedToGetTeacherAccountError(f"teacher not found for exam_id: {exam_id}")

    teacher = session.scalar(select(ZhiXueTeacherAccount).where(ZhiXueTeacherAccount.school_id == school_id))
    if teacher is None:
        raise FailedToGetTeacherAccountError(f"teacher not found for school_id: {school_id}")
    return teacher


def fetch_student_exam_list_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """拉取学生考试列表"""
    try:
        update_task_progress(session, task_id, 10, "正在获取用户信息...")

        # 获取用户信息
        user = session.get(User, user_id)
        if not user or not user.zhixue:
            raise ValueError("User not bound to Zhixue account")

        update_task_progress(session, task_id, 20, "正在登录智学网...")
        if not user.zhixue.cookie:
            raise ValueError("User cookie is empty")

        student_account = login_student_session(user.zhixue.cookie, user.zhixue.is_parent)
        if decrypt(user.zhixue.cookie) != student_account.get_cookie():
            user.zhixue.cookie = encrypt(student_account.get_cookie())
            session.flush()

        update_task_progress(session, task_id, 40, "正在拉取考试数据...")
        exams = student_account.get_exams()

        update_task_progress(session, task_id, 50, "正在处理考试数据...")

        total_exams = len(exams)

        for i, exam in enumerate(exams):
            # 检查考试是否已存在
            existing_exam = session.get(Exam, exam.id)
            if not existing_exam:
                # 创建新考试记录（支持联考，不再强制 school_id）
                new_exam = Exam(
                    id=exam.id,
                    name=exam.name,
                    created_at=exam.create_time,
                )
                session.add(new_exam)
                session.flush()

            # 检查/创建 ExamSchool 关联（联考）
            stmt = select(ExamSchool).where(
                (ExamSchool.exam_id == exam.id) & (ExamSchool.school_id == user.school_id)
            )
            exam_school = session.scalar(stmt)
            if not exam_school:
                exam_school = ExamSchool(
                    exam_id=exam.id,
                    school_id=user.school_id,
                    is_saved=False
                )
                session.add(exam_school)
                session.flush()

            # 检查用户考试记录是否已存在
            stmt = select(UserExam).where(
                (UserExam.zhixue_id == user.zhixue.id) &
                (UserExam.exam_id == exam.id)
            )
            user_exam = session.scalar(stmt)

            if not user_exam:
                new_user_exam = UserExam(
                    zhixue_id=user.zhixue.id,
                    exam_id=exam.id
                )
                session.add(new_user_exam)

            if i % 20 == 0 or i == total_exams - 1:
                progress = 50 + (i + 1) / total_exams * 49
                update_task_progress(
                    session,
                    task_id,
                    int(progress),
                    f"已处理 {i + 1}/{total_exams} 个考试"
                )

        session.flush()

        update_task_progress(session, task_id, 100, "任务完成")
        return {"success": True}

    except Exception as e:
        logger.error(f"Fetch student exam list handler failed: {str(e)}")
        raise


def fetch_exam_details_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """拉取考试分数详情"""
    exam_id = parameters.get("exam_id", None)
    force_refresh = parameters.get("force_refresh", False)
    school_id = parameters.get("school_id", None)
    if exam_id is None:
        raise ValueError("Missing exam_id parameter")

    stmt = select(Exam).where(Exam.id == exam_id)
    exam = session.scalar(stmt)
    if not exam and not school_id:
        raise ValueError(f"Exam not found: {exam_id}")

    # 检查该学校的考试是否已保存
    if exam and school_id:
        stmt = select(ExamSchool).where(
            (ExamSchool.exam_id == exam_id) & (ExamSchool.school_id == school_id)
        )
        exam_school = session.scalar(stmt)
        if exam_school and exam_school.is_saved and not force_refresh:
            update_task_progress(session, task_id, 100, "该学校考试数据已被保存，无需重复拉取")
            return {"success": True}

    try:
        update_task_progress(session, task_id, 10, "正在获取可用账号...")
        stmt = select(User).where(User.id == user_id)
        user = session.scalar(stmt)
        teacher_account = get_teacher(session, exam_id, school_id)
        # 确保 school_id 存在
        if not school_id:
            school_id = teacher_account.school_id

        teacher = login_teacher_session(teacher_account.cookie)
        if decrypt(teacher_account.cookie) != teacher.get_cookie():
            teacher_account.cookie = encrypt(teacher.get_cookie())
            actual_method = teacher.get_session().cookies.get("login_method") or teacher_account.login_method
            if teacher_account.login_method != actual_method:
                teacher_account.login_method = actual_method
            session.flush()

        if not exam:
            # 创建考试记录
            exam_v = teacher.get_exam_detail(exam_id)
            exam = Exam(
                id=exam_id,
                name=exam_v.name,
                created_at=exam_v.create_time,
            )
            session.add(exam)
            session.flush()

        # 检查/创建 ExamSchool 关联（联考）
        stmt = select(ExamSchool).where(
            (ExamSchool.exam_id == exam_id) & (ExamSchool.school_id == school_id)
        )
        exam_school = session.scalar(stmt)
        if not exam_school:
            exam_school = ExamSchool(
                exam_id=exam_id,
                school_id=school_id,
                is_saved=False
            )
            session.add(exam_school)
            session.flush()

        update_task_progress(session, task_id, 30, "正在拉取考试成绩...")
        student_scores = teacher.get_exam_scores(exam_id)
        total_students = len(student_scores)

        for i, student_score in enumerate(student_scores):
            for score in student_score.scores:
                stmt = select(Student).where(Student.id == student_score.user_id)
                student = session.scalar(stmt)
                if not student:
                    new_student = Student(
                        id=student_score.user_id,
                        name=student_score.username,
                        label=student_score.label,
                        no=student_score.studentno,
                        number=student_score.usernum
                    )
                    session.add(new_student)
                    session.flush()

                stmt = select(Score).where(
                    (Score.student_id == student_score.user_id) &
                    (Score.exam_id == exam_id) &
                    (Score.subject_id == score.topicsetid) &
                    (Score.school_id == school_id)
                )
                existing_score = session.scalar(stmt)
                if existing_score and not force_refresh:
                    continue
                elif existing_score:
                    existing_score.score = score.score
                    existing_score.standard_score = score.standard_score
                    existing_score.class_rank = score.classrank
                    existing_score.school_rank = score.schoolrank
                    existing_score.sort = score.sort
                    existing_score.is_calculated = score.is_calculated
                    # 如果 legacy 数据 school_id 为 None，则补全 school_id
                    if existing_score.school_id is None:
                        existing_score.school_id = school_id
                    session.flush()
                    continue

                new_score = Score(
                    student_id=student_score.user_id,
                    exam_id=exam_id,
                    school_id=school_id,
                    subject_id=score.topicsetid,
                    subject_name=score.name if score.subjectcode != -1 else "总分",
                    class_name=student_score.class_name,
                    score=score.score,
                    standard_score=score.standard_score,
                    class_rank=score.classrank,
                    school_rank=score.schoolrank,
                    sort=score.sort,
                    is_calculated=score.is_calculated
                )
                session.add(new_score)

            if i % 50 == 0 or i == total_students - 1:
                session.flush()
                progress = int(50 + (i + 1) / total_students * 49)
                update_task_progress(session, task_id, progress, f"已处理 {i + 1}/{total_students} 个学生")

        exam_school.is_saved = True

        update_task_progress(session, task_id, 100, "任务完成")

        return {"success": True}

    except Exception as e:
        logger.exception("Fetch exam details handler failed")
        raise


def fetch_school_exam_list_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """拉取学校考试列表"""
    try:
        school_id = parameters.get("school_id", None)
        query_parameters = parameters.get("query_parameters", {})

        update_task_progress(session, task_id, 10, "正在获取可用账号...")
        teacher_account = get_teacher(session, "", school_id)
        teacher = login_teacher_session(teacher_account.cookie)
        if decrypt(teacher_account.cookie) != teacher.get_cookie():
            teacher_account.cookie = encrypt(teacher.get_cookie())
            actual_method = teacher.get_session().cookies.get("login_method") or teacher_account.login_method
            if teacher_account.login_method != actual_method:
                teacher_account.login_method = actual_method
            session.flush()

        update_task_progress(session, task_id, 30, "正在拉取考试数据...")
        exams = teacher.get_exam_list(query_parameters)

        total_exams = len(exams)

        for i, exam in enumerate(exams):
            # 检查考试是否已存在
            existing_exam = session.get(Exam, exam.id)
            if not existing_exam:
                # 创建新考试记录（支持联考）
                new_exam = Exam(
                    id=exam.id,
                    name=exam.name,
                    created_at=exam.create_time,
                )
                session.add(new_exam)
                session.flush()

            # 检查/创建 ExamSchool 关联（联考）
            stmt = select(ExamSchool).where(
                (ExamSchool.exam_id == exam.id) & (ExamSchool.school_id == school_id)
            )
            exam_school = session.scalar(stmt)
            if not exam_school:
                exam_school = ExamSchool(
                    exam_id=exam.id,
                    school_id=school_id,
                    is_saved=False
                )
                session.add(exam_school)
                session.flush()

            if i % 20 == 0 or i == total_exams - 1:
                progress = 50 + (i + 1) / total_exams * 49
                update_task_progress(
                    session,
                    task_id,
                    int(progress),
                    f"已处理 {i + 1}/{total_exams} 个考试"
                )

        session.flush()

        update_task_progress(session, task_id, 100, "任务完成")
        return {"success": True}

    except Exception as e:
        logger.error(f"Fetch school exam list handler failed: {str(e)}")
        raise
