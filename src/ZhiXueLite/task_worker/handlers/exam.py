import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Exam, Score, Student, UserExam, User, ZhiXueTeacherAccount
from app.models.student import login_student_session
from app.models.exceptions import FailedToGetTeacherAccountError
from app.models.teacher import login_teacher_session
from task_worker.repository import update_task_progress
from loguru import logger


def get_teacher(session: Session, exam_id: str, school_id: str | None = None) -> ZhiXueTeacherAccount:
    if not school_id:
        school_id = session.scalar(select(Exam.school_id).where(Exam.id == exam_id))
    if not school_id:
        raise FailedToGetTeacherAccountError(f"teacher not found for exam_id: {exam_id}")

    teacher = session.scalar(select(ZhiXueTeacherAccount).where(ZhiXueTeacherAccount.school_id == school_id))
    if teacher is None:
        raise FailedToGetTeacherAccountError(f"teacher not found for school_id: {school_id}")
    return teacher


def fetch_exam_list_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """拉取考试列表"""
    try:
        update_task_progress(session, task_id, 10, "正在获取用户信息...")

        # 获取用户信息
        user = session.get(User, user_id)
        if not user or not user.zhixue:
            raise ValueError("User not bound to Zhixue account")

        update_task_progress(session, task_id, 20, "正在登录智学网...")
        if not user.zhixue.cookie:
            raise ValueError("User cookie is empty")

        student_account = login_student_session(user.zhixue.cookie)
        user.zhixue.cookie = student_account.get_cookie()
        session.flush()

        update_task_progress(session, task_id, 40, "正在拉取考试数据...")
        exams = student_account.get_exams()

        update_task_progress(session, task_id, 50, "正在处理考试数据...")

        processed_exams = []
        total_exams = len(exams)

        for i, exam in enumerate(exams):
            # 检查考试是否已存在
            existing_exam = session.get(Exam, exam.id)
            if not existing_exam:
                new_exam = Exam(
                    id=exam.id,
                    name=exam.name,
                    created_at=exam.create_time,
                    school_id=user.zhixue.school_id
                )
                session.add(new_exam)
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
                processed_exams.append({
                    "id": exam.id,
                    "name": exam.name,
                    "school_id": user.zhixue.school_id,
                    "created_at": exam.create_time if isinstance(exam.create_time, (int, float)) else None
                })

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
        logger.error(f"Fetch exam list handler failed: {str(e)}")
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
    if exam and exam.is_saved and not force_refresh:
        update_task_progress(session, task_id, 100, "考试已被保存，无需重复拉取")
        return {"success": True}

    try:
        teacher_account = get_teacher(session, exam_id, school_id)
        teacher = login_teacher_session(teacher_account.cookie)
        if teacher_account.cookie != teacher.get_cookie():
            teacher_account.cookie = teacher.get_cookie()
            session.flush()

        if not exam:
            exam_v = teacher.get_exam_detail(exam_id)
            exam = Exam(
                id=exam_id,
                name=exam_v.name,
                created_at=exam_v.create_time,
                school_id=teacher_account.school_id
            )
            session.add(exam)
            session.flush()

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
                    (Score.subject_id == score.topicsetid)
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
                    session.flush()
                    continue

                new_score = Score(
                    student_id=student_score.user_id,
                    exam_id=exam_id,
                    subject_id=score.topicsetid,
                    subject_name=score.name if score.subjectcode != -1 else "总分",
                    class_name=student_score.class_name,
                    score=score.score,
                    standard_score=score.standard_score,
                    class_rank=score.classrank,
                    school_rank=score.schoolrank,
                    sort=score.sort,
                )
                session.add(new_score)

            if i % 50 == 0 or i == total_students - 1:
                session.flush()
                progress = int(50 + (i + 1) / total_students * 49)
                update_task_progress(session, task_id, progress, f"已处理 {i + 1}/{total_students} 个学生")

        exam.is_saved = True

        update_task_progress(session, task_id, 100, "任务完成")

        return {"success": True}

    except Exception as e:
        logger.error(f"Fetch exam details handler failed: {str(e)}")
        raise
