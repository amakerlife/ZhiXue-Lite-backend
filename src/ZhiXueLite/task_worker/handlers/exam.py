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


def get_teacher(session: Session, exam_id: str):
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
        return {
            "total_exams": len(processed_exams),
            "exams": processed_exams
        }

    except Exception as e:
        logger.error(f"Fetch exam list handler failed: {str(e)}")
        raise


def fetch_exam_details_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """拉取考试分数详情"""
    exam_id = parameters.get("exam_id", None)
    if exam_id is None:
        raise ValueError("Missing exam_id parameter")

    stmt = select(Exam).where(Exam.id == exam_id)
    exam = session.scalar(stmt)
    if not exam:
        raise ValueError(f"Exam not found: {exam_id}")

    try:
        teacher_account = get_teacher(session, exam_id)
        teacher = login_teacher_session(teacher_account.cookie)
        student_scores = teacher.get_exam_scores(exam_id)
        subjects = teacher.get_exam_subjects(exam_id)
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
                        user_num=student_score.usernum
                    )
                    session.add(new_student)
                    session.flush()

                new_score = Score(
                    student_id=student_score.user_id,
                    exam_id=exam_id,
                    subject_id=score.topicsetid,
                    class_name=student_score.class_name,
                    score=score.score,
                    class_rank=score.classrank,
                    school_rank=score.schoolrank,
                )
                session.add(new_score)

            if i % 50 == 0 or i == total_students - 1:
                session.flush()
                progress = int(50 + (i + 1) / total_students * 49)
                update_task_progress(session, task_id, progress, f"已处理 {i + 1}/{total_students} 个学生")

        exam.is_saved = True

        update_task_progress(session, task_id, 100, "任务完成")

    except Exception as e:
        logger.error(f"Fetch exam details handler failed: {str(e)}")
        raise
