import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Exam, UserExam, User
from app.models.student import login_student_session
from task_worker.repository import update_task_progress
from loguru import logger


def fetch_exam_list_handler(session: Session, task_id: int, user_id: int, parameters: dict[str, Any]):
    """
    拉取考试列表的任务处理器
    """
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

            progress = 50 + (i + 1) / total_exams * 49
            update_task_progress(
                session,
                task_id,
                int(progress),
                f"已处理 {i + 1}/{total_exams} 个考试"
            )

            if i != total_exams - 1:
                time.sleep(1)

        session.flush()

        update_task_progress(session, task_id, 100, "任务完成")
        return {
            "total_exams": len(processed_exams),
            "exams": processed_exams
        }

    except Exception as e:
        logger.error(f"Fetch exam list handler failed: {str(e)}")
        raise
