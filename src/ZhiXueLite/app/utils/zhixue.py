from datetime import datetime
import os
import time
from typing import Dict, List, Tuple, cast

from loguru import logger
from openpyxl import Workbook

from ZhiXueLite.app.utils.config_loader import config
from ZhiXueLite.app.utils.login import login_student, login_teacher, update_login_status
from app.models import (
    FailedToGetStudentAccountError,
    StudentScoreInfo,
    ZhixueError,
    LoginCaptchaError,
    FailedToGetTeacherAccountError
)
from ZhiXueLite.account.student import ExtendedStudentAccount
from ZhiXueLite.account.teacher import ExtendedTeacherAccount

TEACHER_USERNAMES = config.teachers.teacher_accounts
TEACHER_PASSWORDS = config.teachers.teacher_passwords

class ZhixueManager:
    """智学网账号与考试数据管理类"""

    def __init__(self):
        self.stu_list = cast(Dict[int, ExtendedStudentAccount], dict(load_data("stu_list")))
        self.tch_list = cast(Dict[str, ExtendedTeacherAccount], dict(load_data("tch_list")))
        self.exam_scores = cast(Dict[str, List[StudentScoreInfo]], dict(load_data("exam_scores")))
        self.tch_exam_map = cast(Dict[str, ExtendedTeacherAccount], dict(load_data("tch_exam_map")))

        for teacher_account in TEACHER_USERNAMES:  # TODO: 自动维护（删除）不在配置文件中的账号
            for tch_school in self.tch_list:
                if self.tch_list[tch_school].username == teacher_account:
                    break
            else:
                tch_account = login_teacher(
                    teacher_account,
                    TEACHER_PASSWORDS[TEACHER_USERNAMES.index(teacher_account)]
                )
                tch_school = tch_account.school.id
                self.tch_list[tch_school] = tch_account
                logger.success(
                    f"Successfully initialized teacher account: {teacher_account}")
        save_data("tch_list", self.tch_list)

    def get_student_account(self, qqid: int) -> ExtendedStudentAccount:
        """
        获得 QQ 号对应的学生账号

        Args:
            qqid(int): QQ 号

        Returns:
            ExtendedStudentAccount: 学生账号
            bool: 是否存在
        """
        if qqid in self.stu_list:
            update_login_status(self.stu_list[qqid])
            save_data("stu_list", self.stu_list)
            return self.stu_list[qqid]
        raise FailedToGetStudentAccountError("User not logged in.")


zxdata = ZhixueManager()


def require_teacher_account(func):
    def wrapper(qqid, examid, *args, **kwargs):
        stu_school = zxdata.stu_list[qqid].clazz.school.id
        if stu_school not in zxdata.tch_list:
            raise FailedToGetTeacherAccountError("No valid teacher account.")
        update_login_status(zxdata.tch_list[stu_school])
        save_data("tch_list", zxdata.tch_list)
        zxdata.tch_exam_map[examid] = zxdata.tch_list[stu_school]
        save_data("tch_exam_map", zxdata.tch_exam_map)
        return func(qqid, examid, *args, **kwargs)
    return wrapper


def login_stu(qqid: int, username: str, password: str) -> Tuple[int, str]:
    """
    登录学生账号
    状态码：
    0: 登录成功
    1: 登录失败
    2: 已登录其他账号
    3: 被其他 QQ 号登录
    4: 验证码异常

    Args:
        qqid: QQ 号
        username: 学生账号
        password: 学生密码

    Returns:
        Tuple[int, str]: 登录状态码，已被登录的学生姓名
    """
    if qqid in zxdata.stu_list:
        return 2, zxdata.stu_list[qqid].username
    try:
        stu = login_student(username, password)
    except Exception as e:
        logger.error(f"Failed to login student {username}: {e}")
        if Exception == LoginCaptchaError:
            return 4, ""
        return 1, ""
    for qqid_, stu_ in zxdata.stu_list.items():
        if stu_.id == stu.id:
            return 3, str(qqid_)
    zxdata.stu_list[qqid] = stu
    save_data("stu_list", zxdata.stu_list)
    return 0, stu.clazz.name


def logout_stu(qqid: int) -> Tuple[bool, str]:
    """
    登出学生账号

    Args:
        qqid: QQ 号

    Returns:
        bool: 登出是否成功
        str: 学生账号
    """
    if qqid in zxdata.stu_list:
        username = zxdata.stu_list[qqid].username
        del zxdata.stu_list[qqid]
        save_data("stu_list", zxdata.stu_list)
        return True, username
    return False, ""


def get_user_info(qqid: int) -> str:
    """
    获得用户详细信息

    Args:
        qqid: QQ 号

    Returns:
        str: 用户详细信息
    """
    stu = zxdata.get_student_account(qqid)
    return f"已登录的学生账号：{stu.name}({stu.clazz.school.name}：{stu.clazz.name} {stu.id})"


def get_exams(qqid: int, page=1) -> str:
    """
    获取考试列表

    Args:
        qqid: QQ 号
        page: 页码

    Returns:
        str: 考试列表
    """
    stu = zxdata.get_student_account(qqid)
    exams = stu.get_exams()
    returns = ""
    for i in range((page - 1) * 10, min(page * 10, len(exams))):
        returns += f"{i + 1}. {exams[i].name}: {exams[i].id}\n"
    if not returns:
        returns = "所选页码无效或无考试信息"
    return returns


@require_teacher_account
def get_rank_by_stu_code(qqid: int, examid: str) -> str:
    """
    通过 qqid 获得排名

    Args:
        qqid: QQ 号
        examid: 考试 ID

    Returns:
        str: 排名信息
    """
    stu = zxdata.get_student_account(qqid)
    stu_school = zxdata.stu_list[qqid].clazz.school.id
    if examid not in zxdata.exam_scores:
        update_login_status(zxdata.tch_list[stu_school])
        save_data("tch_list", zxdata.tch_list)
        tch = zxdata.tch_list[stu_school]
        zxdata.exam_scores[examid] = tch.get_exam_scores(examid)
        save_data("exam_scores", zxdata.exam_scores)
    students_scores_list = zxdata.exam_scores[examid]
    returns = ""
    for student in students_scores_list:
        if student.user_id == stu.id:
            for subject in student.scores:
                returns += f"{subject}: {student.scores[subject].score} (班次 {student.scores[subject].classrank}" \
                    f"/校次 {student.scores[subject].schoolrank})\n"
            return returns
    return "未找到该学生"


# @require_teacher_account
def get_valid_teacher(qqid: int, examid: str) -> ExtendedTeacherAccount:  # TODO: 有多个可用的教师账号，返回列表
    """
    获取某场考试可用的教师账号

    Returns:
        ExtendedTeacherAccount: 教师账号
    """
    # stu_school = stu_list[qqid].clazz.school.id
    # tch = tch_list[stu_school]
    if examid in zxdata.tch_exam_map:
        return zxdata.tch_exam_map[examid]
    for tch in zxdata.tch_list.values():
        try:
            update_login_status(tch)
            save_data("tch_list", zxdata.tch_list)
            subjects = tch.get_exam_subjects(examid)
            if subjects:
                zxdata.tch_exam_map[examid] = tch
                save_data("tch_exam_map", zxdata.tch_exam_map)
                return tch
        except Exception:
            pass
    raise FailedToGetTeacherAccountError("No valid teacher account.")


def fetch_exam_scores(qqid: int, examid: str, force=False) -> Tuple[Dict, List]:
    """
    自动选择合适教师账号，获取考试成绩

    Args:
        qqid: QQ 号
        examid: 考试 ID
        force: 是否忽略缓存强制获取

    Returns:
        Dict: 科目列表
        List: 学生成绩列表
    """
    tch = get_valid_teacher(qqid, examid)
    subjects = tch.get_exam_subjects(examid)
    if examid in zxdata.exam_scores and not force:
        students_scores_list = zxdata.exam_scores[examid]
    else:
        students_scores_list = tch.get_exam_scores(examid)
        zxdata.exam_scores[examid] = students_scores_list
        save_data("exam_scores", zxdata.exam_scores)
    return subjects, students_scores_list


def get_scoresheet(qqid: int, examid: str) -> str:
    """
    获取成绩单

    Args:
        qqid: QQ 号
        examid: 考试 ID

    Returns:
        str: Excel 文件路径
    """
    wb = Workbook()
    ws = wb.create_sheet(title="成绩单", index=0)
    subjects_list, students_scores_list = fetch_exam_scores(qqid, examid)
    titles = ["姓名", "标签", "班级", "总分", "总分班次", "总分校次"]
    for subject_code in subjects_list:
        subject_name = subjects_list[subject_code]["name"]
        titles.extend([subject_name + "成绩", subject_name +
                      "班次", subject_name + "校次"])
    ws.append(titles)
    for student in students_scores_list:
        row = [student.username, student.label, student.class_name,
               student.scores["总分"].score, student.scores["总分"].classrank, student.scores["总分"].schoolrank]
        for subject_code in subjects_list:
            subject_name = subjects_list[subject_code]["name"]
            row.extend([student.scores[subject_name].score, student.scores[subject_name].classrank,
                        student.scores[subject_name].schoolrank])
        ws.append(row)
    file_name = f"./.zx/cache/scores_{examid}_{time.time()}.xlsx"
    wb.save(file_name)
    return file_name


def get_answersheet_by_stuid(qqid: int, stu_id: str, examid: str) -> List[str]:
    """
    通过 student_id 获取答题卡

    Args:
        qqid: QQ 号
        stu_id: 学生 ID
        examid: 考试 ID

    Returns:
        List[str]: 图片路径列表
    """
    tch = get_valid_teacher(qqid, examid)
    subject_list = tch.get_exam_subjects(examid)
    images = []
    for subject_code in subject_list:
        subject_id = subject_list[subject_code]["id"]
        file_name = f"./.zx/cache/answersheet_{subject_id}_{stu_id}.png"
        if not os.path.exists(file_name):
            try:
                image = tch.process_answersheet(subject_id, stu_id)
            except ZhixueError as e:
                logger.warning(f"Failed to get answersheet: {e}")
                continue
            image.save(file_name)
        images.append(file_name)
    return images


def get_answersheet_by_stuname(stu_name: str, qqid: int, examid: str) -> List[str]:
    """
    通过 学生姓名 获取答题卡
    """
    tch = get_valid_teacher(qqid, examid)
    stu_id = tch.get_stuid_by_stuname(examid, stu_name)
    return get_answersheet_by_stuid(qqid, stu_id, examid)


def get_answersheet_by_qqid(qqid: int, examid: str):
    """通过 QQ 号获取答题卡"""
    stu = zxdata.get_student_account(qqid)
    return get_answersheet_by_stuid(qqid, stu.id, examid)


def get_supported_schools() -> List[str]:
    """
    获取教师缓存中支持的学校

    Returns:
        List[str]: 学校名称列表
    """
    school_names = []
    for tch in zxdata.tch_list.values():
        school_names.append(tch.school.name)
    return school_names
