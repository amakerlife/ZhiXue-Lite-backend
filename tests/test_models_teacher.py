"""
教师模型测试

测试 app/models/teacher.py 中的业务逻辑，包括：
- login_teacher() 登录教师账号
- login_teacher_session() 通过 cookie 登录
- ExtendedTeacherAccount 类的方法
"""
import base64
import json
from unittest.mock import Mock, patch
import pytest
from requests.cookies import RequestsCookieJar
from zhixuewang.exceptions import UserOrPassError
from app.models.teacher import ExtendedTeacherAccount, login_teacher, login_teacher_session
from app.models.dataclasses import StudentScoreInfo
from app.models.exceptions import ZhixueError


def create_mock_teacher_session():
    """创建包含必要 cookie 的 mock teacher session"""
    mock_session = Mock()
    jar = RequestsCookieJar()
    jar.set("uname", base64.b64encode("teacher_user".encode()).decode(),
            domain=".zhixue.com", path="/")
    jar.set("token", "teacher_token_123", domain=".zhixue.com", path="/")
    jar.set("sessionid", "teacher_session_xyz", domain=".zhixue.com", path="/")
    mock_session.cookies = jar
    return mock_session


class TestExtendedTeacherAccount:
    """测试 ExtendedTeacherAccount 类"""

    def test_get_cookie_success(self):
        """测试成功获取 Cookie 字符串（JSON 格式，保留域名信息）"""
        mock_session = create_mock_teacher_session()

        account = ExtendedTeacherAccount(mock_session)

        cookie = account.get_cookie()
        data = json.loads(cookie)

        assert isinstance(data, list)
        cookie_map = {c["name"]: c for c in data}
        assert "token" in cookie_map
        assert cookie_map["token"]["value"] == "teacher_token_123"
        assert cookie_map["token"]["domain"] == ".zhixue.com"
        assert "sessionid" in cookie_map
        assert cookie_map["sessionid"]["value"] == "teacher_session_xyz"

    def test_get_cookie_no_session(self):
        """测试 get_session() 返回 None 时返回空 JSON 列表"""
        mock_session = create_mock_teacher_session()
        account = ExtendedTeacherAccount(mock_session)

        account.get_session = Mock(return_value=None)

        cookie = account.get_cookie()

        assert cookie == "[]"

    @patch("app.models.teacher.update_login_status")
    def test_update_login_status(self, mock_update_login_status):
        """测试更新登录状态"""
        mock_update_login_status.return_value = True
        mock_session = create_mock_teacher_session()

        account = ExtendedTeacherAccount(mock_session)
        result = account.update_login_status()

        assert result is True
        mock_update_login_status.assert_called_once_with(account)

    @patch("app.models.teacher.update_login_status")
    def test_get_exam_list_selections(self, mock_update_login_status):
        """测试获取考试列表选项"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock 第一个请求 (academicYear)
        mock_response_1 = Mock()
        mock_response_1.json.return_value = {
            "result": {
                "selection": {
                    "academicYear": [{"code": "2024-2025", "name": "2024-2025学年"}],
                    "queryTypeList": [{"code": "academicYear", "name": "按学年查"}]
                },
                "gradeList": json.dumps([{"code": "2024", "name": "2024级"}])
            }
        }

        # Mock 第二个请求 (schoolInYear)
        mock_response_2 = Mock()
        mock_response_2.json.return_value = {
            "result": {
                "selection": {
                    "schoolInYearList": [{"code": "high1", "name": "高一"}]
                }
            }
        }

        mock_session.get.side_effect = [mock_response_1, mock_response_2]

        account = ExtendedTeacherAccount(mock_session)
        account.get_token = Mock(return_value="fake_token")

        result = account.get_exam_list_selections()

        assert "academicYear" in result
        assert "queryTypeList" in result
        assert "gradeList" in result
        assert "schoolInYearList" in result
        assert isinstance(result["gradeList"], list)
        assert len(result["academicYear"]) == 1

    @patch("app.models.teacher.update_login_status")
    @patch("app.models.teacher.sleep")
    def test_get_exam_list_single_page(self, mock_sleep, mock_update_login_status):
        """测试获取考试列表（单页）"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock API 响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {
                "reportList": [
                    {
                        "data": {
                            "examId": "exam_001",
                            "examName": "期中考试",
                            "examCreateDateTime": 1234567890,
                            "gradeCode": "2024",
                            "isFinal": False
                        }
                    },
                    {
                        "data": {
                            "examId": "exam_002",
                            "examName": "期末考试",
                            "examCreateDateTime": 1234567900,
                            "gradeCode": "2024",
                            "isFinal": True
                        }
                    }
                ],
                "paperInfo": {"totalPage": 1}
            }
        }

        mock_session.get.return_value = mock_response

        account = ExtendedTeacherAccount(mock_session)
        account.get_token = Mock(return_value="fake_token")

        exams = account.get_exam_list({"queryType": "academicYear"})

        assert len(exams) == 2
        assert exams[0].id == "exam_001"
        assert exams[0].name == "期中考试"
        assert exams[1].id == "exam_002"
        assert exams[1].is_final is True

    @patch("app.models.teacher.update_login_status")
    @patch("app.models.teacher.sleep")
    def test_get_exam_list_multiple_pages(self, mock_sleep, mock_update_login_status):
        """测试获取考试列表（多页）"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock 第一页
        mock_response_page1 = Mock()
        mock_response_page1.json.return_value = {
            "result": {
                "reportList": [
                    {
                        "data": {
                            "examId": "exam_001",
                            "examName": "第一次考试",
                            "examCreateDateTime": 1234567890,
                            "gradeCode": "2024",
                            "isFinal": False
                        }
                    }
                ],
                "paperInfo": {"totalPage": 2}
            }
        }

        # Mock 第二页
        mock_response_page2 = Mock()
        mock_response_page2.json.return_value = {
            "result": {
                "reportList": [
                    {
                        "data": {
                            "examId": "exam_002",
                            "examName": "第二次考试",
                            "examCreateDateTime": 1234567900,
                            "gradeCode": "2024",
                            "isFinal": False
                        }
                    }
                ],
                "paperInfo": {"totalPage": 2}
            }
        }

        mock_session.get.side_effect = [mock_response_page1, mock_response_page2]

        account = ExtendedTeacherAccount(mock_session)
        account.get_token = Mock(return_value="fake_token")

        exams = account.get_exam_list({})

        assert len(exams) == 2
        assert exams[0].id == "exam_001"
        assert exams[1].id == "exam_002"
        # 验证发起了两次请求
        assert mock_session.get.call_count == 2

    @patch("app.models.teacher.update_login_status")
    def test_get_exam_subjects(self, mock_update_login_status):
        """测试获取考试学科列表"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock API 响应
        mock_response = Mock()
        subjects_data = [
            {
                "subjectCode": "001",
                "subjectName": "语文",
                "topicSetId": "topic_001",
                "standScore": "150",
                "subjectGroupFlag": "0",
                "sort": 1
            },
            {
                "subjectCode": "002",
                "subjectName": "数学",
                "topicSetId": "topic_002",
                "standScore": "150",
                "sort": 2
            }
        ]
        mock_response.json.return_value = {
            "result": {
                "allSubjectTopicSetListJSON": json.dumps(subjects_data)
            }
        }

        mock_session.post.return_value = mock_response

        account = ExtendedTeacherAccount(mock_session)

        subjects = account.get_exam_subjects("exam_test_001")

        assert "001" in subjects
        assert "002" in subjects
        assert subjects["001"]["name"] == "语文"
        assert subjects["001"]["score"] == "150"
        assert subjects["002"]["name"] == "数学"

    def test_calc_rank(self):
        """测试计算排名（静态方法）"""
        # 创建测试数据
        from app.models.dataclasses import Score

        student1 = StudentScoreInfo("张三", "stu_001", "001", "100001", "标签1", "一班", "180", "1", "1")
        student1.scores.append(Score(name="语文", score="95", classrank="", schoolrank="",
                               subjectcode=1, topicsetid="topic_001", standard_score="95", sort=1))
        student1.scores.append(Score(name="数学", score="85", classrank="", schoolrank="",
                               subjectcode=2, topicsetid="topic_002", standard_score="85", sort=2))

        student2 = StudentScoreInfo("李四", "stu_002", "002", "100002", "标签2", "一班", "170", "2", "2")
        student2.scores.append(Score(name="语文", score="88", classrank="", schoolrank="",
                               subjectcode=1, topicsetid="topic_001", standard_score="88", sort=1))
        student2.scores.append(Score(name="数学", score="82", classrank="", schoolrank="",
                               subjectcode=2, topicsetid="topic_002", standard_score="82", sort=2))

        student3 = StudentScoreInfo("王五", "stu_003", "003", "100003", "标签3", "二班", "190", "1", "1")
        student3.scores.append(Score(name="语文", score="98", classrank="", schoolrank="",
                               subjectcode=1, topicsetid="topic_001", standard_score="98", sort=1))
        student3.scores.append(Score(name="数学", score="92", classrank="", schoolrank="",
                               subjectcode=2, topicsetid="topic_002", standard_score="92", sort=2))

        students = [student1, student2, student3]

        ExtendedTeacherAccount.calc_rank(students)

        # 验证年级排名（语文）
        assert student3.scores[0].schoolrank == "1"  # 王五 98分 第1名
        assert student1.scores[0].schoolrank == "2"  # 张三 95分 第2名
        assert student2.scores[0].schoolrank == "3"  # 李四 88分 第3名

        # 验证班级排名（语文，一班）
        assert student1.scores[0].classrank == "1"  # 张三在一班第1名
        assert student2.scores[0].classrank == "2"  # 李四在一班第2名
        assert student3.scores[0].classrank == "1"  # 王五在二班第1名

    @patch("app.models.teacher.update_login_status")
    def test_get_student_id_by_name_success(self, mock_update_login_status):
        """测试根据姓名获取学生 ID 成功"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock API 响应
        mock_response = Mock()
        mock_response.text = '{"result":{"studentRank":[]}}'  # 不包含 <html
        mock_response.json.return_value = {
            "result": {
                "studentRank": [
                    {"userId": "stu_001", "userName": "张三"},
                    {"userId": "stu_002", "userName": "张三三"}  # 重名
                ]
            }
        }

        mock_session.post.return_value = mock_response

        account = ExtendedTeacherAccount(mock_session)

        student_ids = account.get_student_id_by_name("exam_001", "张三")

        assert len(student_ids) == 2
        assert "stu_001" in student_ids
        assert "stu_002" in student_ids

    @patch("app.models.teacher.update_login_status")
    def test_get_student_id_by_name_html_error(self, mock_update_login_status):
        """测试获取学生 ID 时遇到 HTML 错误"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock API 响应 (返回 HTML)
        mock_response = Mock()
        mock_response.text = "<html><body>Error</body></html>"

        mock_session.post.return_value = mock_response

        account = ExtendedTeacherAccount(mock_session)

        with pytest.raises(ZhixueError, match="Failed to get student id"):
            account.get_student_id_by_name("exam_001", "张三")

    @patch("app.models.teacher.update_login_status")
    def test_get_exam_detail(self, mock_update_login_status):
        """测试获取考试详情"""
        mock_update_login_status.return_value = False
        mock_session = create_mock_teacher_session()

        # Mock API 响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": [
                {
                    "examName": "期中考试",
                    "examTime": 1234567890
                }
            ]
        }

        mock_session.post.return_value = mock_response

        account = ExtendedTeacherAccount(mock_session)

        exam = account.get_exam_detail("exam_001")

        assert exam.id == "exam_001"
        assert exam.name == "期中考试"
        assert exam.create_time == 1234567890


class TestLoginTeacher:
    """测试 login_teacher 函数"""

    @patch("app.models.teacher.get_session_by_captcha")
    @patch("app.models.teacher.ExtendedTeacherAccount")
    def test_login_teacher_success(self, mock_account_class, mock_get_session):
        """测试成功登录教师账号"""
        # Mock session
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.id = "teacher_001"
        mock_account_instance.name = "李老师"
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance
        mock_account_instance.set_advanced_info.return_value = mock_account_instance

        result = login_teacher("teacher_user", "password123", "changyan")

        mock_get_session.assert_called_once_with("teacher_user", "password123", "changyan")
        mock_account_class.assert_called_once_with(mock_session)
        mock_account_instance.set_base_info.assert_called_once()
        mock_account_instance.set_advanced_info.assert_called_once()
        assert result == mock_account_instance

    @patch("app.models.teacher.get_session_by_captcha")
    def test_login_teacher_wrong_credentials(self, mock_get_session):
        """测试使用错误凭证登录"""
        mock_get_session.side_effect = UserOrPassError("用户名或密码错误")

        with pytest.raises(UserOrPassError):
            login_teacher("wrong_user", "wrong_pass", "changyan")


class TestLoginTeacherSession:
    """测试 login_teacher_session 函数"""

    @patch("app.models.teacher.decrypt", side_effect=lambda x: x)
    @patch("app.models.teacher.set_user_session")
    @patch("app.models.teacher.ExtendedTeacherAccount")
    def test_login_teacher_session_success(self, mock_account_class, mock_set_session, mock_decrypt):
        """测试通过 cookie 成功登录"""
        # Mock session
        mock_session = Mock()
        mock_set_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.id = "teacher_001"
        mock_account_instance.name = "李老师"
        mock_account_instance.update_login_status.return_value = False  # 未更新
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance
        mock_account_instance.set_advanced_info.return_value = mock_account_instance

        result = login_teacher_session("fake_cookie_string")

        mock_decrypt.assert_called_once_with("fake_cookie_string")
        mock_set_session.assert_called_once_with("fake_cookie_string")
        mock_account_class.assert_called_once_with(mock_session)
        mock_account_instance.update_login_status.assert_called_once()
        mock_account_instance.set_base_info.assert_called_once()
        mock_account_instance.set_advanced_info.assert_called_once()
        assert result == mock_account_instance

    @patch("app.models.teacher.encrypt", side_effect=lambda x: f"encrypted:{x}")
    @patch("app.models.teacher.decrypt", side_effect=lambda x: x)
    @patch("flask.has_app_context")
    @patch("app.database.db")
    @patch("app.database.models.ZhiXueTeacherAccount")
    @patch("app.models.teacher.set_user_session")
    @patch("app.models.teacher.ExtendedTeacherAccount")
    def test_login_teacher_session_update_cookie_in_db(
        self, mock_account_class, mock_set_session, mock_zhixue_account_class,
        mock_db, mock_has_app_context, mock_decrypt, mock_encrypt
    ):
        """测试登录状态更新时保存新 cookie 到数据库"""
        # Mock session
        mock_session = Mock()
        mock_set_session.return_value = mock_session

        # Mock account
        mock_account_instance = Mock()
        mock_account_instance.id = "teacher_001"
        mock_account_instance.name = "李老师"
        mock_account_instance.update_login_status.return_value = True  # 已更新
        mock_account_instance.get_cookie.return_value = "new_teacher_cookie"
        mock_account_class.return_value = mock_account_instance
        mock_account_instance.set_base_info.return_value = mock_account_instance
        mock_account_instance.set_advanced_info.return_value = mock_account_instance

        # Mock Flask 上下文
        mock_has_app_context.return_value = True

        # Mock 数据库中的教师账号
        mock_db_account = Mock()
        mock_db.session.get.return_value = mock_db_account

        result = login_teacher_session("old_cookie_string")

        assert result == mock_account_instance

        # 验证更新了数据库中的 cookie（已加密）
        assert mock_db_account.cookie == "encrypted:new_teacher_cookie"
        mock_db.session.commit.assert_called_once()
