import json
import re
from time import sleep
from typing import Tuple

from loguru import logger
from zhixuewang.teacher import TeacherAccount

from app.utils.answersheet import draw_answersheet
from app.models.exceptions import ZhixueError
from app.models.dataclasses import Score, StudentScoreInfo
from app.utils.login_zhixue import get_session_by_captcha, set_user_session, update_login_status


class ExtendedTeacherAccount(TeacherAccount):

    def update_login_status(self):
        """
        更新登录状态
        """
        update_login_status(self)

    def get_cookie(self) -> str:
        """
        获取 Cookie 字符串
        """
        if not self.get_session():
            return ""
        cookie_items = []
        for name, value in self.get_session().cookies.items():
            cookie_items.append(f"{name}={value}")
        return "; ".join(cookie_items)

    def get_exam_subjects(self, examid: str) -> dict[
        str, dict[str, str]
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
            subjectslist[str(subject["subjectCode"])] = {
                "id": subject["topicSetId"], "name": subject["subjectName"]}
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
                student_info.add_subject_score("总分", student["allScore"], student["classRank"], student["schoolRank"],
                                               -1, "0")
                if "-" in student["schoolRank"] or "-" in student["classRank"]:
                    need_calc_rank = True
                for score_info in student["scoreInfos"]:
                    subject_name = subjects[score_info["subjectCode"]]["name"]
                    student_info.add_subject_score(subject_name, score_info["score"], score_info["classRank"],
                                                   score_info["schoolRank"], score_info["subjectCode"],
                                                   subjects[score_info["subjectCode"]]["id"])
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
        str
    ]:
        """
        获取答题卡数据
        Args:
            subjectid: 学科 ID
            stuid: 学生 ID
        Returns:
            Tuple: 题号对应情况, 每页位置信息, 客观题答案, 作答及批改详情, 原卷链接, 纸张类型
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
        page_index_origin = 0
        for page in data["sheetDatas"]["answerSheetLocationDTO"]["pageSheets"]:
            page_index = page["pageIndex"]
            page_positions[page_index] = []
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
                    page_index = page_index_origin
                    if page_index not in page_positions:
                        page_positions[page_index] = []
                    position = section["contents"]["position"]
                    if (position["left"] <= 0 or position["top"] <= 0 or position["left"] < out_left or
                            position["top"] < out_top):
                        position["left"] += out_left
                        position["top"] += out_top
                    page_positions[page_index].append({
                        "height": position["height"],
                        "left": position["left"],
                        "top": position["top"],
                        "width": position["width"],
                        "ixList": section["contents"]["branch"][0]["ixList"]
                    })
                    # logger.debug(f"Page {page_index}: {page_positions[page_index]}")
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
        paper_type = json.loads(data["answerSheetLocation"])[
            "paperType"]  # 纸张类型

        return topic_mapping, page_positions, objective_answer, answer_details, sheet_images, paper_type

    def process_answersheet(self, subjectid: str, stuid: str):
        """
        处理答题卡

        Args:
            subjectid: 学科 ID
            stuid: 学生 ID
        """
        try:
            topic_mapping, page_positions, objective_answer, answer_details, sheet_images, paper_type \
                = self.get_answersheet_data(subjectid, stuid)
        except Exception as e:
            logger.error(f"Failed to get answersheet data: {e}")
            raise ZhixueError("Failed to get answersheet data")
        try:
            image = draw_answersheet(topic_mapping, page_positions, objective_answer,
                                     answer_details, sheet_images, paper_type)
        except Exception as e:
            logger.error(f"Failed to draw answersheet: {e}")
            raise ZhixueError("Failed to draw answersheet")
        return image

    def get_stuid_by_stuname(self, examid: str, stuname: str) -> str:  # XXX: 适配无法获取的情况
        """
        根据学生姓名和 examid 获取学生 ID

        Args:
            examid: 考试 ID
            stuname: 学生姓名
        Returns:
            str: 学生 ID
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
        # TODO: 支持多个学生，进行选择
        data = r.json()["result"]["studentRank"][0]["userId"]
        return data


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
        cookie (str): Cookie 字符串

    Returns:
        ExtendedTeacherAccount: 教师账号
    """
    session = set_user_session(cookie)
    account = ExtendedTeacherAccount(session)
    account.update_login_status()
    return account.set_base_info().set_advanced_info()
