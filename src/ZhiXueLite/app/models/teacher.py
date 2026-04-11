import json
import re
from time import sleep
from typing import Any, Tuple

from loguru import logger
from zhixuewang.teacher import TeacherAccount
from zhixuewang.models import Exam

from app.utils.answersheet import draw_answersheet
from app.models.exceptions import ZhixueError
from app.models.dataclasses import Score, StudentScoreInfo
from app.utils.crypto import decrypt, encrypt
from app.utils.login_zhixue import get_session_by_captcha, set_user_session, update_login_status


class ExtendedTeacherAccount(TeacherAccount):

    def update_login_status(self) -> bool:
        """
        更新登录状态，如果更新了则保存新 cookie 到数据库（仅在 Flask 上下文中）

        Returns:
            bool: 是否更新了 session
        """
        return update_login_status(self)

    def get_cookie(self) -> str:
        """
        获取 Cookie 字符串（JSON 格式）
        """
        if not self.get_session():
            return "[]"
        cookies = []
        for cookie in self.get_session().cookies:
            cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path
            })
        return json.dumps(cookies)

    def get_exam_list_selections(self) -> dict[str, str]:  # TODO: 针对不同学期等配置的差异化响应
        """
        获取考试列表选项

        Returns:
            dict: 考试列表选项
        """
        self.update_login_status()
        r = self.get_session().get(
            "https://www.zhixue.com/api-teacher/api/reportlist",
            headers={"token": self.get_token()},
            params={"queryType": "academicYear"}
        )
        data = r.json()["result"]
        selections = data["selection"]
        selections["gradeList"] = json.loads(data["gradeList"])
        r = self.get_session().get(
            "https://www.zhixue.com/api-teacher/api/reportlist",
            headers={"token": self.get_token()},
            params={"queryType": "schoolInYear"}
        )
        data = r.json()["result"]
        selections["schoolInYearList"] = data["selection"]["schoolInYearList"]
        return selections

    def get_exam_list(self, params: dict[str, str | int] = {}) -> list[Exam]:
        """
        获取教师考试列表

        Args:
            params: 请求参数

        Returns:
            list: 教师考试列表
        """
        self.update_login_status()
        exams = []
        current_page = 1
        pages = 1
        params["pageIndex"] = current_page
        while True:
            if (current_page > pages):
                break
            r = self.get_session().get(  # FIXME: 此处应为 get 请求，参数应放到 args 里
                "https://www.zhixue.com/api-teacher/api/reportlist",
                params=params,
                headers={"token": self.get_token()},
            )
            for exam in r.json()["result"]["reportList"]:
                exam_data = exam["data"]
                exams.append(Exam(
                    id=exam_data["examId"],
                    name=exam_data["examName"],
                    create_time=exam_data["examCreateDateTime"],
                    grade_code=exam_data["gradeCode"],
                    is_final=exam_data["isFinal"],
                ))
            pages = r.json()["result"]["paperInfo"]["totalPage"]
            current_page += 1
            params["pageIndex"] = current_page
            sleep(0.5)
        return exams

    def get_exam_subjects(self, examid: str) -> dict[
        str, dict[str, Any]
    ]:
        """
        获得指定考试学科列表（校级报告接口）

        Args:
            examid: 考试 ID

        Returns:
            dict: 指定考试学科列表
        """
        self.update_login_status()
        r = self.get_session().post(
            "https://www.zhixue.com/api-teacher/api/studentScore/getAllSubjectStudentRank",
            data={
                "examId": examid,
                "pageIndexInt": 1,
                "version": "V3",
            }
        )
        subjects = json.loads(r.json()["result"]["allSubjectTopicSetListJSON"])
        subjectslist = {}
        for subject in subjects:
            sort_value = subject.get("sort", 1)
            assign_status = subject.get("assignStatus")
            if not isinstance(assign_status, bool):
                raise ZhixueError(
                    f"Invalid assignStatus type: exam_id={examid}, subject_code={subject.get('subjectCode')}, "
                    f"value={assign_status}, type={type(assign_status).__name__}"
                )
            subjectslist[str(subject["subjectCode"])] = {
                "id": subject["topicSetId"],
                "name": subject["subjectName"],
                "score": str(subject["standScore"]),
                "is_group": str(subject.get("subjectGroupFlag", "0")),
                "sort": sort_value,
                "assignStatus": assign_status
            }
        return subjectslist

    @staticmethod
    def calc_rank(student_list: list[StudentScoreInfo]):
        """
        计算排名

        Args:
            student_list: 学生成绩列表
        """
        def parse_score(score_str):
            if isinstance(score_str, (int, float)):
                return float(score_str)
            score_str = str(score_str)

            # 提取数字
            if "剔除" in score_str:
                numbers = re.findall(r"-?\d+\.?\d*", score_str)
                if numbers:
                    try:
                        return float(numbers[0])
                    except ValueError:
                        return -1
                return -1

            # 直接转换
            try:
                return float(score_str)
            except (ValueError, TypeError):
                return -1

        # 按科目分组
        subject_scores: dict[str, list[Tuple[StudentScoreInfo, Score]]] = {}
        for student in student_list:
            for score in student.scores:
                if score.name not in subject_scores:
                    subject_scores[score.name] = []
                subject_scores[score.name].append((student, score))

        for subject_name, scores in subject_scores.items():
            # 按班级分组
            class_groups: dict[str, list[Tuple[StudentScoreInfo, Score]]] = {}
            for student, score_obj in scores:
                if student.class_name not in class_groups:
                    class_groups[student.class_name] = []
                class_groups[student.class_name].append((student, score_obj))

            # 计算年级排名
            sorted_scores = sorted(
                scores, key=lambda x: parse_score(x[1].score), reverse=True)
            current_rank = 1
            prev_score = None
            for i, (student, score_obj) in enumerate(sorted_scores):
                current_score = parse_score(score_obj.score)
                if current_score == -1:
                    score_obj.schoolrank = str(len(sorted_scores))
                else:
                    # 同分最高名次：只有当分数不同时才更新排名
                    # 例如：100, 100, 100, 99 → 1, 1, 1, 4
                    if prev_score is not None and current_score != prev_score:
                        current_rank = i + 1
                    score_obj.schoolrank = str(current_rank)
                prev_score = current_score

            # 计算班级排名
            for class_name, class_scores in class_groups.items():
                sorted_class_scores = sorted(
                    class_scores, key=lambda x: parse_score(x[1].score), reverse=True)
                current_rank = 1
                prev_score = None
                for i, (student, score_obj) in enumerate(sorted_class_scores):
                    current_score = parse_score(score_obj.score)
                    if current_score == -1:
                        score_obj.classrank = str(len(sorted_class_scores))
                    else:
                        # 同分最高名次：只有当分数不同时才更新排名
                        # 例如：100, 100, 100, 99 → 1, 1, 1, 4
                        if prev_score is not None and current_score != prev_score:
                            current_rank = i + 1
                        score_obj.classrank = str(current_rank)
                    prev_score = current_score

    def get_exam_scores(self, examid: str) -> list[StudentScoreInfo]:
        """
        获得成绩单

        Args:
            examid: 考试 ID

        Returns:
            list: 成绩单
        """
        def calculate_total_score(scores_list: list) -> str:
            """
            计算总分

            Args:
                scores_list: 各科成绩列表（不包括总分）

            Returns:
                str: 计算出的总分
            """
            total = 0.0
            valid_count = 0

            for score_obj in scores_list:
                if score_obj.subjectcode == -1:  # 跳过总分项
                    continue

                # 解析分数
                score_str = str(score_obj.score)
                if score_str and score_str != "-":
                    try:
                        # 处理可能包含"剔除"等文本的分数
                        numbers = re.findall(r"-?\d+\.?\d*", score_str)
                        if numbers:
                            total += float(numbers[0])
                            valid_count += 1
                    except (ValueError, IndexError):
                        pass  # 跳过无效成绩

            if valid_count == 0:
                return "-"

            return str(total)

        subjects = self.get_exam_subjects(examid)
        r = self.get_session().post(
            "https://www.zhixue.com/api-teacher/api/studentScore/getAllSubjectStudentRank",
            data={
                "examId": examid,
                "pageIndexInt": 1,
                "version": "V3",
            }
        )
        pages = r.json()["result"]["paperInfo"]["totalPage"]
        students_list = []
        need_calc_rank = False

        r = self.get_session().post(
            "https://www.zhixue.com/api-teacher/api/studentScore/studentExamScore",
            data={"examId": examid}
        )
        try:
            total_score = r.json()["result"]["schoolExamArchive"]["standardScore"]
        except KeyError:
            total_score = -1

        for page in range(1, pages + 1):
            r = self.get_session().post(
                "https://www.zhixue.com/api-teacher/api/studentScore/getAllSubjectStudentRank",
                data={
                    "examId": examid,
                    "pageIndexInt": page,
                }
            )
            data = r.json()["result"]
            for student in data["studentRank"]:
                student_info = StudentScoreInfo(student["userName"], student["userId"], student["studentNo"],
                                                student["userNum"], student["studentLabel"], student["className"],
                                                student["allScore"], student["classRank"], student["schoolRank"])

                # 先添加各科成绩
                for score_info in student["scoreInfos"]:
                    subject_name = subjects[score_info["subjectCode"]]["name"]
                    subject_sort = subjects[score_info["subjectCode"]]["sort"]
                    student_info.add_subject_score(
                        subject_name, score_info["score"], score_info["classRank"],
                        score_info["schoolRank"], score_info["subjectCode"],
                        subjects[score_info["subjectCode"]]["id"],
                        subjects[score_info["subjectCode"]]["score"],
                        subjects[score_info["subjectCode"]]["assignStatus"],
                        sort=int(subject_sort),
                        is_calculated=False,
                        origin_score=score_info["assignScore"] if "assignScore" in score_info else "",
                    )

                # 处理总分
                is_total_calculated = False
                total_score_value = student["allScore"]
                total_class_rank = student["classRank"]
                total_school_rank = student["schoolRank"]

                # 检查 allScore 是否为无效值
                if student["allScore"] in ["-", "", None]:
                    # 计算总分
                    calculated_score = calculate_total_score(student_info.scores)
                    total_score_value = calculated_score
                    is_total_calculated = True
                    # 总分排名将在后续的 calc_rank 中计算

                # 添加总分
                student_info.add_subject_score(
                    "总分", total_score_value, total_class_rank, total_school_rank,
                    -1, "0", str(total_score), False,
                    sort=-1,
                    is_calculated=is_total_calculated
                )

                if "-" in student["schoolRank"] or "-" in student["classRank"] or is_total_calculated:
                    need_calc_rank = True

                students_list.append(student_info)
            sleep(0.5)
        if need_calc_rank:
            self.calc_rank(students_list)
        return students_list

    def get_answersheet_data(self, subjectid: str, stuid: str) -> Tuple[
        dict[str, str],
        dict[int, list[dict[str, int | list[int]]]],
        dict[int, dict[str, str]],
        dict[int, dict[str,
                       str |
                       float |
                       list[dict[str, int | float | list[dict[str, float | str]]]]
                       ]],
        list[str],
        str,
        bool
    ]:
        """
        获取答题卡数据
        Args:
            subjectid: 学科 ID
            stuid: 学生 ID
        Returns:
            Tuple: 题号对应情况, 每页位置信息, 客观题答案, 作答及批改详情, 原卷链接, 纸张类型，是否为绝对坐标
        """
        self.update_login_status()
        r = self.get_session().post(
            "https://www.zhixue.com/api-classreport/class/student/getNewCheckSheet/",
            data={
                "topicSetId": subjectid,
                "userId": stuid,
            },
            headers={"token": self.get_token()},
        )

        try:
            data = r.json()["result"]
            data["sheetDatas"] = json.loads(data["sheetDatas"])
        except Exception:
            raise ZhixueError(
                f"{r.text} with params: topicSetId: {subjectid}, userId: {stuid}")

        topic_mapping = data["markingTopicDetail"]  # 题号对应情况
        page_positions = {}  # 每页位置信息
        is_absolute = False  # 是否为绝对坐标
        page_index_origin = 0
        for page in data["sheetDatas"]["answerSheetLocationDTO"]["pageSheets"]:
            page_index = page["pageIndex"]
            for section in page["sections"]:
                out_left = section["contents"]["position"]["left"]
                out_top = section["contents"]["position"]["top"]
                flag = False
                use_outside_position = False
                for content in section["contents"]["branch"]:
                    position = content["position"]
                    if position == "":
                        use_outside_position = True
                        break
                    if page_index not in page_positions:
                        page_positions[page_index] = []
                    if (flag or position["left"] <= 0 or position["top"] <= 0 or position["left"] < out_left or
                            position["top"] < out_top):
                        position["left"] += out_left
                        position["top"] += out_top
                        flag = True
                    page_positions[page_index].append({
                        "height": position["height"],
                        "left": position["left"],
                        "top": position["top"],
                        "width": position["width"],
                        "ixList": content["ixList"]
                    })
                if use_outside_position:
                    is_absolute = True
                    page_index = page_index_origin
                    if page_index not in page_positions:
                        page_positions[page_index] = []
                    position = section["contents"]["position"]
                    page_positions[page_index].append({
                        "height": position["height"],
                        "left": position["left"],
                        "top": position["top"],
                        "width": position["width"],
                        "ixList": section["contents"]["branch"][0]["ixList"]
                    })
            page_index_origin += 1
        # 客观题答案
        objective_answer = {}
        for item in data["objectAnswer"]:
            topic_sort = item["topicSort"]
            objective_answer[topic_sort] = {
                "answer": item["answer"],
                "standardAnswer": item["standardAnswer"]
            }

        # 作答及批改详情（所有题目）
        answer_details = {}
        for record in data["sheetDatas"]["userAnswerRecordDTO"]["answerRecordDetails"]:
            topic_number = record["topicNumber"]
            answer_details[topic_number] = {
                "answer": record["answer"],
                "score": record["score"],
                "standardScore": record["standardScore"],
                "subTopics": []
            }
            for subtopic in record.get("subTopics", []):
                answer_details[topic_number]["subTopics"].append({
                    "subTopicIndex": subtopic["subTopicIndex"],
                    "score": subtopic["score"],
                    "teacherMarkingRecords": [{
                        "score": teacher["score"],
                        "teacherName": teacher.get("teacherName")
                    } for teacher in subtopic.get("teacherMarkingRecords", [])]
                })

        sheet_images = data["sheetImages"]  # 原卷链接
        paper_type = json.loads(data["answerSheetLocation"])["paperType"]  # 纸张类型

        return topic_mapping, page_positions, objective_answer, answer_details, sheet_images, paper_type, is_absolute

    def process_answersheet(self, subjectid: str, stuid: str):
        """
        处理答题卡

        Args:
            subjectid: 学科 ID
            stuid: 学生 ID
        """
        try:
            topic_mapping, page_positions, objective_answer, answer_details, sheet_images, paper_type, is_absolute \
                = self.get_answersheet_data(subjectid, stuid)
        except Exception as e:
            logger.error(f"Failed to get answersheet data: {e}")
            raise ZhixueError("Failed to get answersheet data")
        try:
            image = draw_answersheet(topic_mapping, page_positions, objective_answer,
                                     answer_details, sheet_images, paper_type, is_absolute)
        except Exception as e:
            logger.error(f"Failed to draw answersheet: {e}")
            raise ZhixueError("Failed to draw answersheet")
        return image

    def get_student_id_by_name(self, examid: str, stuname: str) -> list[str]:
        """
        根据学生姓名和 examid 获取学生 ID

        Args:
            examid: 考试 ID
            stuname: 学生姓名
        Returns:
            list[str]: 学生 ID 列表
        """
        self.update_login_status()
        r = self.get_session().post(
            "https://www.zhixue.com/api-teacher/api/studentScore/getAllSubjectStudentRank/",
            data={
                "examId": examid,
                "searchValue": stuname,
            }
        )
        if "<html" in r.text:
            logger.warning("Failed to get student id")
            raise ZhixueError("Failed to get student id")
        students = r.json()["result"]["studentRank"]
        data = []
        for student in students:
            data.append(student["userId"])
        return data

    def get_exam_detail(self, examid: str) -> Exam:
        """
        获取某个考试的简单详细情况

        Args:
            exam_id (str): 为需要查询考试的 id
        Return:
            Exam
        """
        self.update_login_status()
        r = self.get_session().post(
            "https://www.zhixue.com/api-classreport/class/examInfo/",
            data={
                "examId": examid,
            }
        )
        data = r.json()["result"][0]
        exam = Exam(
            id=examid,
            name=data["examName"],
            create_time=data["examTime"],
        )
        return exam


def login_teacher(username: str, password: str, method: str = "changyan") -> ExtendedTeacherAccount:
    """
    登录教师账号

    Args:
        username (str): 用户名
        password (str): 密码

    Returns:
        ExtendedTeacherAccount: 教师账号
    """
    session = get_session_by_captcha(username, password, method)
    return ExtendedTeacherAccount(session).set_base_info().set_advanced_info()


def login_teacher_session(cookie: str) -> ExtendedTeacherAccount:
    """
    通过 session 登录教师账号

    Args:
        cookie (str): Cookie 字符串（JSON 格式，已加密）

    Returns:
        ExtendedTeacherAccount: 教师账号
    """
    cookie = decrypt(cookie)
    session = set_user_session(cookie)
    account = ExtendedTeacherAccount(session)
    updated = account.update_login_status()
    teacher_account = account.set_base_info().set_advanced_info()
    if updated:
        try:
            # 检查是否在 Flask 上下文中，如果是则更新数据库中的 cookie
            from flask import has_app_context
            if has_app_context():
                from app.database import db
                from app.database.models import ZhiXueTeacherAccount
                account = db.session.get(ZhiXueTeacherAccount, teacher_account.id)
                if account:
                    account.cookie = encrypt(teacher_account.get_cookie())
                    actual_method = teacher_account.get_session().cookies.get("login_method") or account.login_method
                    if account.login_method != actual_method:
                        account.login_method = actual_method
                    db.session.commit()
        except ImportError:
            pass

    return teacher_account
