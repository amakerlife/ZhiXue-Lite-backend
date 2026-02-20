"""
考试 API 测试

测试考试列表端点，包括分页、权限、查询过滤等功能
"""
import time
from datetime import datetime
from unittest.mock import patch, Mock
import pytest
from app.database.models import User, School, ZhiXueStudentAccount, ZhiXueTeacherAccount, Exam, ExamSchool, UserExam, Student, Score
from app.utils.crypto import encrypt


@pytest.fixture
def school(db):
    """创建测试学校"""
    school = School(id="school_001", name="测试中学")
    db.session.add(school)
    db.session.commit()
    return school


@pytest.fixture
def zhixue_account(db, school):
    """创建测试智学网账号"""
    account = ZhiXueStudentAccount(
        id="zx_001",
        username="zxuser",
        password=encrypt("encrypted_password"),
        realname="张三",
        cookie=encrypt("fake_cookie"),
        school_id=school.id
    )
    db.session.add(account)
    db.session.commit()
    return account


@pytest.fixture
def user_with_zhixue(db, zhixue_account):
    """创建绑定了智学网账号的测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
        is_active=True,
        zhixue_account_id=zhixue_account.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_user(db):
    """创建管理员用户"""
    admin = User(
        username="admin",
        email="admin@example.com",
        role="admin",
        permissions="33333",
        created_at=datetime.utcnow(),
        email_verified=True
    )
    admin.set_password("adminpass")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def teacher_account(db, school):
    """创建测试教师账号"""
    teacher = ZhiXueTeacherAccount(
        id="teacher_001",
        username="teacher_user",
        password=encrypt("teacher_password"),
        realname="李老师",
        cookie=encrypt("fake_teacher_cookie"),
        school_id=school.id
    )
    db.session.add(teacher)
    db.session.commit()
    return teacher


@pytest.fixture
def school_admin(db, school):
    """创建具有 SCHOOL 级别 FETCH_DATA 权限的用户"""
    user = User(
        username="schooladmin",
        email="schooladmin@example.com",
        role="user",
        permissions="22222",  # 所有 SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_exams(db, school, zhixue_account):
    """创建一些示例考试数据

    创建 15 个考试，用于测试分页功能：
    - 前 5 个：属于 testuser（通过 UserExam 关联）
    - 全部：属于 school_001（通过 ExamSchool 关联）
    """
    exams = []
    current_time = int(time.time() * 1000)

    for i in range(1, 16):
        exam = Exam(
            id=f"exam_{i:03d}",
            name=f"第 {i} 次考试",
            created_at=current_time + i * 1000  # 每个考试间隔 1 秒
        )
        db.session.add(exam)
        exams.append(exam)

    db.session.commit()

    # 为前 5 个考试创建 ExamSchool 关联
    for i in range(5):
        exam_school = ExamSchool(
            exam_id=exams[i].id,
            school_id=school.id,
            is_saved=True
        )
        db.session.add(exam_school)

    # 为前 5 个考试创建 UserExam 关联（这些考试属于 testuser）
    for i in range(5):
        user_exam = UserExam(
            zhixue_id=zhixue_account.id,
            exam_id=exams[i].id
        )
        db.session.add(user_exam)

    db.session.commit()
    return exams


def login_user(client, username="testuser", password="password123"):
    """辅助函数：登录用户并返回响应"""
    response = client.post("/user/login", json={
        "login": username,
        "password": password
    })
    assert response.status_code == 200
    return response


def test_exam_list_requires_login(client):
    """
    测试未登录用户无法访问考试列表
    """
    response = client.get("/exam/list")

    assert response.status_code == 401


def test_exam_list_requires_permission(client, db):
    """
    测试没有权限的用户无法访问考试列表
    """
    # 创建一个没有 VIEW_EXAM_LIST 权限的用户
    user = User(
        username="noperm",
        email="noperm@example.com",
        role="user",
        permissions="00000",  # 所有权限都是 DENIED
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="noperm", password="password123")
    response = client.get("/exam/list")
    assert response.status_code == 403


def test_exam_list_self_scope_default(client, user_with_zhixue, sample_exams):
    """
    测试默认的 self scope 考试列表

    默认情况下，scope=self，应该只返回该用户的考试
    """
    login_user(client)

    response = client.get("/exam/list")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["exams"]) == 5
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["pages"] == 1


def test_exam_list_pagination(client, user_with_zhixue, sample_exams):
    """
    测试分页功能

    测试 page 和 per_page 参数是否正确工作
    """
    login_user(client)

    # 第一页，每页 2 条
    response = client.get("/exam/list?page=1&per_page=2")

    assert response.status_code == 200

    data = response.get_json()
    assert len(data["exams"]) == 2
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["pages"] == 3
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["has_next"] is True


def test_exam_list_search_query(client, user_with_zhixue, sample_exams, db):
    """
    测试搜索功能
    """
    login_user(client)

    exam = db.session.get(Exam, "exam_001")
    exam.name = "期末重要考试"
    db.session.commit()

    response = client.get("/exam/list?query=重要")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["exams"]) == 1
    assert data["exams"][0]["name"] == "期末重要考试"


@pytest.mark.parametrize("page,per_page,expected_items,expected_pages,has_prev,has_next", [
    (1, 2, 2, 3, False, True),   # 第一页：2 条数据，共 3 页，无上一页，有下一页
    (2, 2, 2, 3, True, True),    # 第二页：2 条数据，共 3 页，有上一页，有下一页
    (3, 2, 1, 3, True, False),   # 第三页：1 条数据，共 3 页，有上一页，无下一页
    (1, 10, 5, 1, False, False),  # 单页：5 条数据，共 1 页，无上一页，无下一页
])
def test_exam_list_pagination_scenarios(
    client, user_with_zhixue, sample_exams,
    page, per_page, expected_items, expected_pages, has_prev, has_next
):
    """
    参数化测试：测试分页的各种边界情况

    这个测试会运行 4 次，测试不同的分页参数组合
    """
    login_user(client)

    response = client.get(f"/exam/list?page={page}&per_page={per_page}")
    assert response.status_code == 200

    data = response.get_json()
    assert len(data["exams"]) == expected_items
    assert data["pagination"]["pages"] == expected_pages
    assert data["pagination"]["has_prev"] == has_prev
    assert data["pagination"]["has_next"] == has_next


def test_exam_list_school_scope(client, db, school, sample_exams):
    """
    测试 school scope 考试列表

    具有 SCHOOL 权限的用户可以查看校内所有考试
    """
    # 创建一个有 SCHOOL 权限的用户
    user = User(
        username="schooluser",
        email="school@example.com",
        role="user",
        permissions="22222",  # 所有 SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id  # 手动分配学校
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser", password="password123")

    response = client.get("/exam/list?scope=school")
    assert response.status_code == 200
    data = response.get_json()

    # school scope 应该返回该学校的所有考试（通过 ExamSchool 关联的）
    # 在 sample_exams 中，只为前 5 个考试创建了 ExamSchool 关联
    assert len(data["exams"]) == 5


def test_exam_list_global_scope_all_exams(client, db, school, sample_exams):
    """测试 GLOBAL 权限使用 scope=all 查看所有考试"""
    # 创建 GLOBAL 权限用户（需要关联学校才能通过基础检查）
    user = User(
        username="globaluser",
        email="global@example.com",
        role="user",
        permissions="33333",  # 所有 GLOBAL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id  # GLOBAL 用户也需要基础身份关联
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="globaluser", password="password123")

    response = client.get("/exam/list?scope=all&per_page=20")
    assert response.status_code == 200
    data = response.get_json()

    # scope=all 应该返回所有考试（15 个）
    assert data["success"] is True
    assert len(data["exams"]) == 15
    assert data["pagination"]["total"] == 15


def test_exam_list_global_scope_filter_by_school(client, db, school, sample_exams):
    """测试 GLOBAL 权限使用 scope=all 并按学校过滤"""
    # 创建 GLOBAL 权限用户
    user = User(
        username="globaluser",
        email="global@example.com",
        role="user",
        permissions="33333",
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id  # 需要基础身份关联
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="globaluser", password="password123")

    response = client.get(f"/exam/list?scope=all&school_id={school.id}")
    assert response.status_code == 200
    data = response.get_json()

    # 只返回该学校的考试（5 个，在 sample_exams 中创建了 ExamSchool）
    assert data["success"] is True
    assert len(data["exams"]) == 5


def test_exam_list_time_filter_valid(client, user_with_zhixue, sample_exams):
    """测试使用有效的时间范围过滤"""
    login_user(client)

    # 使用时间戳过滤
    start = int(time.time() * 1000)  # 当前时间
    end = start + 100000  # 未来时间

    response = client.get(f"/exam/list?start_time={start}&end_time={end}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


def test_exam_list_time_filter_invalid_only_start(client, user_with_zhixue, sample_exams):
    """测试只提供 start_time（不合法）"""
    login_user(client)

    start = int(time.time() * 1000)

    response = client.get(f"/exam/list?start_time={start}&end_time=0")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "参数不合法" in data["message"]


def test_exam_list_time_filter_invalid_only_end(client, user_with_zhixue, sample_exams):
    """测试只提供 end_time（不合法）"""
    login_user(client)

    end = int(time.time() * 1000)

    response = client.get(f"/exam/list?start_time=0&end_time={end}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "参数不合法" in data["message"]


def test_exam_list_invalid_scope(client, user_with_zhixue, sample_exams):
    """测试使用不合法的 scope 参数"""
    login_user(client)

    response = client.get("/exam/list?scope=invalid_scope")

    # 不合法的 scope 会先被权限检查拦截（403），而不是参数验证（400）
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False


def test_exam_list_school_scope_requires_school_id(client, db, sample_exams):
    """测试 SCHOOL 权限但没有 school_id 会被装饰器拦截"""
    # 创建一个 SCHOOL 权限用户，但不分配 manual_school_id
    user = User(
        username="schooluser_no_school",
        email="schooluser_no_school@example.com",
        role="user",
        permissions="22222",  # SCHOOL 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=None,  # 没有学校
        zhixue_account_id=None  # 也没有智学网账号
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser_no_school", password="password123")

    response = client.get("/exam/list?scope=school")

    # 没有 school_id 的用户会在装饰器层被拦截（403），而不是进入路由验证（401）
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False


# fetch-list-params 测试


@patch("app.exam.routes.login_teacher_session")
@patch("app.exam.routes.get_teacher")
def test_fetch_list_params_success(mock_get_teacher, mock_login_teacher, client, school_admin, teacher_account):
    """测试成功获取考试列表拉取参数"""
    mock_get_teacher.return_value = teacher_account

    mock_teacher_session = Mock()
    mock_teacher_session.get_exam_list_selections.return_value = {
        "academicYear": [
            {"code": "2024-2025", "name": "2024-2025学年"},
            {"code": "2023-2024", "name": "2023-2024学年"}
        ],
        "queryTypeList": [
            {"code": "academicYear", "name": "按学年查"},
            {"code": "schoolInYear", "name": "按级别查"}
        ],
        "examTypeList": [
            {"code": "", "name": "全部"},
            {"code": "weeklyExam", "name": "周考"},
            {"code": "monthlyExam", "name": "月考"}
        ]
    }
    mock_login_teacher.return_value = mock_teacher_session

    login_user(client, username="schooladmin", password="password123")

    response = client.get(f"/exam/fetch-list-params?school_id={school_admin.school_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "params" in data
    assert "academicYear" in data["params"]
    assert "examTypeList" in data["params"]

    mock_get_teacher.assert_called_once_with("", school_id=school_admin.school_id)
    mock_login_teacher.assert_called_once_with(teacher_account.cookie)
    mock_teacher_session.get_exam_list_selections.assert_called_once()


def test_fetch_list_params_requires_login(client):
    """测试未登录无法获取拉取参数"""
    response = client.get("/exam/fetch-list-params")
    assert response.status_code == 401


def test_fetch_list_params_requires_permission(client, user_with_zhixue):
    """测试普通用户（SELF 权限）无法获取拉取参数"""
    login_user(client)
    response = client.get("/exam/fetch-list-params")
    assert response.status_code == 403


@patch("app.exam.routes.get_teacher")
def test_fetch_list_params_no_teacher_account(mock_get_teacher, client, school_admin):
    """测试学校无可用教师账号时的错误处理"""
    from app.models.exceptions import FailedToGetTeacherAccountError

    mock_get_teacher.side_effect = FailedToGetTeacherAccountError("teacher not found for exam")

    login_user(client, username="schooladmin", password="password123")
    response = client.get(f"/exam/fetch-list-params?school_id={school_admin.school_id}")

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "该学校暂无可用教师账号" in data["message"]


@patch("app.exam.routes.login_teacher_session")
@patch("app.exam.routes.get_teacher")
def test_fetch_list_params_global_permission_other_school(
    mock_get_teacher, mock_login_teacher, client, db, school, teacher_account
):
    """测试 GLOBAL 权限用户查询其他学校的参数"""
    # 创建一个 GLOBAL 权限用户（需要基础身份关联）
    user = User(
        username="globaluser",
        email="global@example.com",
        role="user",
        permissions="33333",  # 所有 GLOBAL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id  # 需要基础身份关联
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建另一个学校
    other_school = School(id="other_school_001", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    mock_get_teacher.return_value = teacher_account
    mock_teacher_session = Mock()
    mock_teacher_session.get_exam_list_selections.return_value = {"academicYear": []}
    mock_login_teacher.return_value = mock_teacher_session

    login_user(client, username="globaluser", password="password123")

    # GLOBAL 权限可以查询任何学校
    response = client.get(f"/exam/fetch-list-params?school_id={other_school.id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


@patch("app.exam.routes.login_teacher_session")
@patch("app.exam.routes.get_teacher")
def test_fetch_list_params_school_permission_other_school_denied(
    mock_get_teacher, mock_login_teacher, client, db, teacher_account
):
    """测试 SCHOOL 权限用户查询其他学校的参数被拒绝"""
    # 创建用户所属的学校
    user_school = School(id="user_school_001", name="用户学校")
    db.session.add(user_school)
    db.session.commit()

    # 创建一个 SCHOOL 权限用户
    user = User(
        username="schooluser",
        email="schooluser@example.com",
        role="user",
        permissions="22222",  # 所有 SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=user_school.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建另一个学校
    other_school = School(id="other_school_002", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    login_user(client, username="schooluser", password="password123")

    # SCHOOL 权限无法查询其他学校
    response = client.get(f"/exam/fetch-list-params?school_id={other_school.id}")

    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "无权访问该考试数据" in data["message"]


def test_fetch_list_params_no_school_id_param_error(client, db):
    """测试未提供 school_id 且用户也没有关联学校会被装饰器拦截"""
    # 创建 SCHOOL 权限用户，但没有关联学校
    user = User(
        username="schooluser_no_school",
        email="schooluser_no_school@example.com",
        role="user",
        permissions="22222",  # SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=None,
        zhixue_account_id=None
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser_no_school", password="password123")

    response = client.get("/exam/fetch-list-params")

    # 装饰器 @permission_required(FETCH_DATA, "school") 会检查 school_id
    # 没有 school_id 返回 403，不会进入路由内部参数验证（400）
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False


# list/fetch 测试


@patch("app.exam.routes.create_task")
def test_fetch_exam_list_self_success(mock_create_task, client, user_with_zhixue):
    """测试成功拉取个人考试列表"""
    mock_task = Mock()
    mock_task.uuid = "task-uuid-12345"
    mock_create_task.return_value = mock_task

    login_user(client)

    response = client.post("/exam/list/fetch?query_type=self", json={})

    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True
    assert data["task_id"] == "task-uuid-12345"
    assert "任务已创建" in data["message"]

    mock_create_task.assert_called_once()
    call_kwargs = mock_create_task.call_args[1]
    assert call_kwargs["task_type"] == "fetch_student_exam_list"
    assert call_kwargs["user_id"] == user_with_zhixue.id
    assert call_kwargs["timeout"] == 180


def test_fetch_exam_list_self_requires_zhixue(client, db):
    """测试未绑定智学网账号无法拉取个人考试列表"""
    user = User(
        username="nozhixue",
        email="nozhixue@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id=None
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="nozhixue", password="password123")

    response = client.post("/exam/list/fetch?query_type=self", json={})

    data = response.get_json()

    # 接受 401 或 403（可能被权限装饰器或其他中间件拦截）
    assert response.status_code in [401, 403]
    assert data["success"] is False


@patch("app.exam.routes.create_task")
def test_fetch_exam_list_school_success(mock_create_task, client, school_admin, school):
    """测试成功拉取学校考试列表（query_type=school_id 模式）"""
    mock_task = Mock()
    mock_task.uuid = "task-uuid-67890"
    mock_create_task.return_value = mock_task

    login_user(client, username="schooladmin", password="password123")

    # 关键：必须指定 query_type 为非 "self" 的值，否则默认走 self 模式
    response = client.post(
        f"/exam/list/fetch?query_type=school&school_id={school.id}",
        json={"params": {}}
    )

    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True
    assert data["task_id"] == "task-uuid-67890"
    assert "任务已创建" in data["message"]

    mock_create_task.assert_called_once()
    call_kwargs = mock_create_task.call_args[1]
    assert call_kwargs["task_type"] == "fetch_school_exam_list"
    assert call_kwargs["parameters"]["school_id"] == school.id
    assert call_kwargs["parameters"]["query_parameters"] == {}
    assert call_kwargs["timeout"] == 300


def test_fetch_exam_list_requires_login(client):
    """测试未登录无法拉取考试列表"""
    response = client.post("/exam/list/fetch", json={})
    assert response.status_code == 401


def test_fetch_exam_list_requires_permission(client, db):
    """测试没有 FETCH_DATA 权限的用户无法拉取考试列表"""
    user = User(
        username="nofetch",
        email="nofetch@example.com",
        role="user",
        permissions="10010",  # VIEW_EXAM_LIST=1, FETCH_DATA=0
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="nofetch", password="password123")
    response = client.post("/exam/list/fetch", json={})
    assert response.status_code == 403


@patch("app.exam.routes.create_task")
def test_fetch_exam_list_school_no_school_id_param_error(mock_create_task, client, db):
    """测试 query_type=school 但用户没有关联学校会被装饰器拦截"""
    # 创建 SCHOOL 权限用户，但没有关联学校
    user = User(
        username="schooluser_no_school",
        email="schooluser_no_school@example.com",
        role="user",
        permissions="22222",  # SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=None,
        zhixue_account_id=None
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser_no_school", password="password123")

    response = client.post("/exam/list/fetch?query_type=school", json={"params": {}})

    # 装饰器 @permission_required(FETCH_DATA, "self") 会检查 zhixue 或 manual_school
    # 两者都没有时返回 403，不会进入路由内部参数验证（400）
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False


@patch("app.exam.routes.create_task")
def test_fetch_exam_list_school_global_permission_other_school(mock_create_task, client, db, school):
    """测试 GLOBAL 权限用户拉取其他学校考试列表"""
    # 创建 GLOBAL 权限用户（需要基础身份关联）
    user = User(
        username="globaluser",
        email="global@example.com",
        role="user",
        permissions="33333",  # 所有 GLOBAL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id  # 需要基础身份关联
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建另一个学校
    other_school = School(id="other_school_003", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    mock_task = Mock()
    mock_task.uuid = "task-global-123"
    mock_create_task.return_value = mock_task

    login_user(client, username="globaluser", password="password123")

    # GLOBAL 权限可以拉取任何学校的考试列表
    response = client.post(
        f"/exam/list/fetch?query_type=school&school_id={other_school.id}",
        json={"params": {}}
    )

    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True
    assert data["task_id"] == "task-global-123"


@patch("app.exam.routes.create_task")
def test_fetch_exam_list_school_school_permission_other_school_denied(mock_create_task, client, db):
    """测试 SCHOOL 权限用户拉取其他学校考试列表被拒绝"""
    # 创建用户所属的学校
    user_school = School(id="user_school_002", name="用户学校")
    db.session.add(user_school)
    db.session.commit()

    # 创建 SCHOOL 权限用户
    user = User(
        username="schooluser",
        email="schooluser@example.com",
        role="user",
        permissions="22222",  # SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=user_school.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建另一个学校
    other_school = School(id="other_school_004", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    login_user(client, username="schooluser", password="password123")

    # SCHOOL 权限无法拉取其他学校的考试列表
    response = client.post(
        f"/exam/list/fetch?query_type=school&school_id={other_school.id}",
        json={"params": {}}
    )

    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert "无权访问该考试数据" in data["message"]


# /<exam_id> 测试


def test_get_exam_info_success(client, user_with_zhixue, sample_exams):
    """测试成功获取考试基本信息（SELF 权限，用户有该考试）"""
    login_user(client)

    # 使用 sample_exams 中的第一个考试（已通过 UserExam 关联）
    exam_id = "exam_001"
    response = client.get(f"/exam/{exam_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["exam"]["id"] == exam_id
    assert data["exam"]["name"] == "第 1 次考试"
    assert "created_at" in data["exam"]
    assert "is_multi_school" in data["exam"]
    assert "schools" in data["exam"]


def test_get_exam_info_not_found(client, user_with_zhixue):
    """测试访问不存在的考试"""
    login_user(client)

    response = client.get("/exam/non_existent_exam")

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "考试不存在" in data["message"]


def test_get_exam_info_requires_login(client):
    """测试未登录无法访问考试信息"""
    response = client.get("/exam/exam_001")
    assert response.status_code == 401


def test_get_exam_info_requires_permission(client, db):
    """测试没有 VIEW_EXAM_DATA 权限的用户无法访问考试信息"""
    user = User(
        username="noperm",
        email="noperm@example.com",
        role="user",
        permissions="00000",  # 所有权限都是 DENIED
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="noperm", password="password123")
    response = client.get("/exam/exam_001")
    assert response.status_code == 403


def test_get_exam_info_self_permission_requires_zhixue(client, db):
    """测试 SELF 权限用户未绑定智学网账号时无法访问考试"""
    # 创建一个学校
    school = School(id="school_test", name="测试学校")
    db.session.add(school)
    db.session.commit()

    # 创建一个考试
    exam = Exam(
        id="exam_test_zhixue",
        name="测试考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    user = User(
        username="nozhixue",
        email="nozhixue@example.com",
        role="user",
        permissions="11110",  # 有 VIEW_EXAM_DATA SELF 权限 (第4位是1)
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id=None,  # 未绑定智学网账号
        manual_school_id=school.id  # 分配手动学校，可以通过装饰器检查
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="nozhixue", password="password123")
    response = client.get(f"/exam/{exam.id}")

    assert response.status_code == 401
    data = response.get_json()
    assert "请先绑定智学网账号" in data["message"]


def test_get_exam_info_self_permission_no_user_exam(client, user_with_zhixue, sample_exams):
    """测试 SELF 权限用户访问不属于自己的考试"""
    login_user(client)

    # exam_010 不在 UserExam 关联中（sample_exams 只为前 5 个考试创建了关联）
    response = client.get("/exam/exam_010")

    assert response.status_code == 403
    data = response.get_json()
    assert "无权访问该考试" in data["message"]


def test_get_exam_info_school_permission_success(client, db, school, sample_exams):
    """测试 SCHOOL 权限用户访问本校考试成功"""
    user = User(
        username="schooluser",
        email="schooluser@example.com",
        role="user",
        permissions="22222",  # 所有 SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=school.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser", password="password123")

    # exam_001 属于 school_001（通过 ExamSchool 关联）
    response = client.get("/exam/exam_001")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["exam"]["id"] == "exam_001"


def test_get_exam_info_school_permission_denied(client, db, sample_exams):
    """测试 SCHOOL 权限用户访问其他学校考试被拒绝"""
    # 创建另一个学校
    other_school = School(id="school_002", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    user = User(
        username="schooluser2",
        email="schooluser2@example.com",
        role="user",
        permissions="22222",  # 所有 SCHOOL 级权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=other_school.id  # 属于 school_002
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser2", password="password123")

    # exam_001 属于 school_001，不属于 school_002
    response = client.get("/exam/exam_001")

    assert response.status_code == 403
    data = response.get_json()
    assert "无权访问该考试" in data["message"]


def test_get_exam_info_global_permission(client, admin_user, sample_exams):
    """测试 GLOBAL 权限用户可以访问任何考试"""
    login_user(client, username="admin", password="adminpass")

    response = client.get("/exam/exam_001")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["exam"]["id"] == "exam_001"


def test_get_exam_info_multi_school(client, db, admin_user):
    """测试联考场景（一个考试关联多个学校）"""
    # 创建两个学校
    school1 = School(id="school_ms_001", name="联考学校 1")
    school2 = School(id="school_ms_002", name="联考学校 2")
    db.session.add_all([school1, school2])
    db.session.commit()

    # 创建联考
    exam = Exam(
        id="exam_multi_school",
        name="联考测试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 关联两个学校
    exam_school1 = ExamSchool(exam_id=exam.id, school_id=school1.id, is_saved=True)
    exam_school2 = ExamSchool(exam_id=exam.id, school_id=school2.id, is_saved=False)
    db.session.add_all([exam_school1, exam_school2])
    db.session.commit()

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam.id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["exam"]["is_multi_school"] is True
    # GLOBAL 权限应该返回所有学校
    assert len(data["exam"]["schools"]) == 2


# /<exam_id>/score 测试


@pytest.fixture
def exam_with_scores(db, school, zhixue_account):
    """创建带有成绩数据的考试"""
    # 创建考试
    exam = Exam(
        id="exam_with_scores",
        name="有成绩的考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 关联学校
    exam_school = ExamSchool(exam_id=exam.id, school_id=school.id, is_saved=True)
    db.session.add(exam_school)

    # 关联用户考试
    user_exam = UserExam(zhixue_id=zhixue_account.id, exam_id=exam.id)
    db.session.add(user_exam)
    db.session.commit()

    # 创建学生
    student1 = Student(
        id=zhixue_account.id,  # 使用 zhixue_account 的 ID
        name="张三",
        label="标签1",
        no="001",
        number="100001"
    )
    student2 = Student(
        id="student_002",
        name="李四",
        label="标签2",
        no="002",
        number="100002"
    )
    db.session.add_all([student1, student2])
    db.session.commit()

    # 为学生1（zhixue_account 对应的学生）创建成绩
    scores = [
        Score(
            student_id=student1.id,
            exam_id=exam.id,
            school_id=school.id,
            subject_id="subject_001",
            subject_name="语文",
            class_name="一班",
            sort=1,
            score="95",
            standard_score="95",
            class_rank="1",
            school_rank="1"
        ),
        Score(
            student_id=student1.id,
            exam_id=exam.id,
            school_id=school.id,
            subject_id="subject_002",
            subject_name="数学",
            class_name="一班",
            sort=2,
            score="90",
            standard_score="90",
            class_rank="2",
            school_rank="3"
        ),
    ]

    # 为学生2创建成绩
    scores.extend([
        Score(
            student_id=student2.id,
            exam_id=exam.id,
            school_id=school.id,
            subject_id="subject_001",
            subject_name="语文",
            class_name="一班",
            sort=1,
            score="88",
            standard_score="88",
            class_rank="5",
            school_rank="10"
        ),
    ])

    db.session.add_all(scores)
    db.session.commit()

    return exam


def test_get_exam_score_success_self(client, user_with_zhixue, exam_with_scores):
    """测试成功获取自己的考试成绩（SELF 权限，不指定 student_id）"""
    login_user(client)

    response = client.get(f"/exam/{exam_with_scores.id}/score")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["id"] == exam_with_scores.id
    assert data["name"] == "有成绩的考试"
    assert data["student_id"] == user_with_zhixue.zhixue_account_id
    assert len(data["scores"]) == 2  # 语文和数学两门课
    # 检查成绩按 sort 排序
    assert data["scores"][0]["subject_name"] == "语文"
    assert data["scores"][0]["score"] == "95"
    assert data["scores"][1]["subject_name"] == "数学"
    assert data["scores"][1]["score"] == "90"


def test_get_exam_score_by_student_id(client, db, admin_user, exam_with_scores, school):
    """测试通过 student_id 查询成绩（GLOBAL 权限）"""
    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?student_id=student_002&school_id={school.id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["student_id"] == "student_002"
    assert len(data["scores"]) == 1  # 只有语文一门课
    assert data["scores"][0]["subject_name"] == "语文"
    assert data["scores"][0]["score"] == "88"


@patch("app.exam.routes.login_teacher_session")
@patch("app.exam.routes.get_teacher")
def test_get_exam_score_by_student_name(mock_get_teacher, mock_login_teacher, client, admin_user, exam_with_scores, teacher_account, school):
    """测试通过 student_name 查询成绩（需要 mock 教师账号）"""
    mock_get_teacher.return_value = teacher_account

    mock_teacher_session = Mock()
    mock_teacher_session.get_student_id_by_name.return_value = ["student_002"]
    mock_login_teacher.return_value = mock_teacher_session

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?student_name=李四&school_id={school.id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["student_id"] == "student_002"

    mock_get_teacher.assert_called_once()
    mock_teacher_session.get_student_id_by_name.assert_called_once_with(exam_with_scores.id, "李四")


def test_get_exam_score_both_id_and_name_error(client, admin_user, exam_with_scores, school):
    """测试同时指定 student_id 和 student_name 返回错误"""
    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?student_id=student_002&student_name=李四")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "不可同时指定" in data["message"]


def test_get_exam_score_name_without_school_id(client, admin_user, exam_with_scores):
    """测试使用 student_name 但不指定 school_id 返回错误"""
    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?student_name=李四")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "必须指定学校 ID" in data["message"]


def test_get_exam_score_exam_not_found(client, user_with_zhixue):
    """测试访问不存在的考试"""
    login_user(client)

    response = client.get("/exam/non_existent/score")

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "考试不存在" in data["message"]


def test_get_exam_score_requires_login(client, exam_with_scores):
    """测试未登录无法访问成绩"""
    response = client.get(f"/exam/{exam_with_scores.id}/score")
    assert response.status_code == 401


def test_get_exam_score_requires_permission(client, db, exam_with_scores):
    """测试没有 VIEW_EXAM_DATA 权限无法访问"""
    user = User(
        username="noperm",
        email="noperm@example.com",
        role="user",
        permissions="00000",
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="noperm", password="password123")
    response = client.get(f"/exam/{exam_with_scores.id}/score")
    assert response.status_code == 403


@patch("app.exam.routes.login_teacher_session")
@patch("app.exam.routes.get_teacher")
def test_get_exam_score_student_not_found(mock_get_teacher, mock_login_teacher, client, admin_user, exam_with_scores, teacher_account, school):
    """测试通过 student_name 查询但未找到学生"""
    mock_get_teacher.return_value = teacher_account

    mock_teacher_session = Mock()
    mock_teacher_session.get_student_id_by_name.return_value = []  # 返回空列表
    mock_login_teacher.return_value = mock_teacher_session

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?student_name=不存在的学生&school_id={school.id}")

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "未找到该学生" in data["message"]


@patch("app.exam.routes.login_teacher_session")
@patch("app.exam.routes.get_teacher")
def test_get_exam_score_multiple_students_found(mock_get_teacher, mock_login_teacher, client, admin_user, exam_with_scores, teacher_account, school):
    """测试通过 student_name 查询但匹配到多个学生"""
    mock_get_teacher.return_value = teacher_account

    mock_teacher_session = Mock()
    mock_teacher_session.get_student_id_by_name.return_value = ["student_001", "student_002"]  # 多个匹配
    mock_login_teacher.return_value = mock_teacher_session

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?student_name=张&school_id={school.id}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "匹配到多个学生" in data["message"]


def test_get_exam_score_invalid_school_id(client, db, admin_user, exam_with_scores):
    """测试指定的 school_id 不在考试的学校列表中"""
    # 创建另一个学校
    other_school = School(id="other_school", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/score?school_id={other_school.id}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "该学校未参与此次考试" in data["message"]


def test_get_exam_score_no_data(client, user_with_zhixue, db, school, zhixue_account):
    """测试考试存在但没有成绩数据"""
    # 创建一个没有成绩的考试
    exam = Exam(
        id="exam_no_scores",
        name="没有成绩的考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    exam_school = ExamSchool(exam_id=exam.id, school_id=school.id, is_saved=True)
    user_exam = UserExam(zhixue_id=zhixue_account.id, exam_id=exam.id)
    db.session.add_all([exam_school, user_exam])
    db.session.commit()

    # 创建学生但不创建成绩
    student = Student(
        id=zhixue_account.id,
        name="张三",
        label="标签1",
        no="001",
        number="100001"
    )
    db.session.add(student)
    db.session.commit()

    login_user(client)

    response = client.get(f"/exam/{exam.id}/score")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["scores"]) == 0  # 没有成绩


# /<exam_id>/fetch 测试


@patch("app.exam.routes.create_task")
def test_fetch_exam_details_task_created(mock_create_task, client, user_with_zhixue, sample_exams):
    """测试成功创建拉取考试详情任务"""
    mock_task = Mock()
    mock_task.uuid = "task-exam-details-123"
    mock_create_task.return_value = mock_task

    login_user(client)

    response = client.post(f"/exam/exam_001/fetch", json={})

    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True
    assert data["task_id"] == "task-exam-details-123"
    assert "任务已创建" in data["message"]

    mock_create_task.assert_called_once()
    call_kwargs = mock_create_task.call_args[1]
    assert call_kwargs["task_type"] == "fetch_exam_details"
    assert call_kwargs["user_id"] == user_with_zhixue.id
    assert call_kwargs["timeout"] == 300


@patch("app.exam.routes.create_task")
def test_fetch_exam_details_force_refresh(mock_create_task, client, user_with_zhixue, sample_exams):
    """测试强制刷新功能（需要额外权限）"""
    mock_task = Mock()
    mock_task.uuid = "task-force-refresh-123"
    mock_create_task.return_value = mock_task

    # 修改用户权限，添加 REFETCH_EXAM_DATA 权限
    user_with_zhixue.permissions = "11110"  # REFETCH_EXAM_DATA=1
    from app.database import db as _db
    _db.session.commit()

    login_user(client)

    response = client.post(f"/exam/exam_001/fetch?force_refresh=true", json={})

    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True

    # 检查参数中包含 force_refresh
    call_kwargs = mock_create_task.call_args[1]
    assert call_kwargs["parameters"]["force_refresh"] is True


def test_fetch_exam_details_requires_login(client):
    """测试未登录无法拉取考试详情"""
    response = client.post("/exam/exam_001/fetch", json={})
    assert response.status_code == 401


def test_fetch_exam_details_requires_permission(client, db):
    """测试没有 FETCH_DATA 权限无法拉取"""
    user = User(
        username="nofetch",
        email="nofetch@example.com",
        role="user",
        permissions="10010",  # FETCH_DATA=0
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="nofetch", password="password123")
    response = client.post("/exam/exam_001/fetch", json={})
    assert response.status_code == 403


# /<exam_id>/scoresheet 测试 (导出成绩单)


def test_export_scoresheet_success(client, user_with_zhixue, exam_with_scores, school):
    """测试成功导出成绩单（Excel 文件）"""
    # 修改用户权限以允许导出
    user_with_zhixue.permissions = "10111"  # EXPORT_SCORE_SHEET=1
    from app.database import db as _db
    _db.session.commit()

    login_user(client)

    response = client.get(f"/exam/{exam_with_scores.id}/scoresheet?school_id={school.id}")

    assert response.status_code == 200
    assert response.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # 检查文件下载头
    assert "attachment" in response.headers.get("Content-Disposition", "")


def test_export_scoresheet_requires_permission(client, user_with_zhixue, exam_with_scores, school):
    """测试没有 EXPORT_SCORE_SHEET 权限无法导出"""
    # user_with_zhixue 默认权限不包括导出
    login_user(client)

    response = client.get(f"/exam/{exam_with_scores.id}/scoresheet?school_id={school.id}")

    assert response.status_code == 403


def test_export_scoresheet_exam_not_found(client, admin_user, school):
    """测试导出不存在的考试"""
    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/non_existent/scoresheet?school_id={school.id}")

    assert response.status_code == 404


def test_export_scoresheet_no_data(client, user_with_zhixue, db, school, zhixue_account):
    """测试考试没有成绩数据时导出"""
    # 创建一个没有成绩的考试
    exam = Exam(
        id="exam_no_scores_sheet",
        name="没有成绩的考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    exam_school = ExamSchool(exam_id=exam.id, school_id=school.id, is_saved=True)
    user_exam = UserExam(zhixue_id=zhixue_account.id, exam_id=exam.id)
    db.session.add_all([exam_school, user_exam])
    db.session.commit()

    # 修改权限以允许导出
    user_with_zhixue.permissions = "10111"
    from app.database import db as _db
    _db.session.commit()

    login_user(client)

    response = client.get(f"/exam/{exam.id}/scoresheet?school_id={school.id}")

    assert response.status_code == 404
    data = response.get_json()
    assert "该考试暂无成绩数据" in data["message"]


# /teacher/add 测试


@patch("app.teacher.routes.login_teacher")
def test_teacher_add_success(mock_login_teacher, client, admin_user, db):
    """测试成功添加教师账号（需要 mock）"""
    # Mock 教师登录成功
    mock_teacher_account = Mock()
    mock_teacher_account.id = "teacher_new_001"
    mock_teacher_account.name = "王老师"
    mock_teacher_account.school = Mock()
    mock_teacher_account.school.id = "school_new_001"
    mock_teacher_account.school.name = "新学校"
    mock_teacher_account.get_cookie.return_value = "new_teacher_cookie"
    mock_login_teacher.return_value = mock_teacher_account

    login_user(client, username="admin", password="adminpass")

    response = client.post("/teacher/add", json={
        "username": "newteacher",
        "password": "teacher_password",
        "login_method": "changyan"
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert "teacher" in data
    assert data["teacher"]["id"] == "teacher_new_001"

    mock_login_teacher.assert_called_once_with("newteacher", "teacher_password", "changyan")


def test_teacher_add_requires_admin(client, user_with_zhixue):
    """测试非管理员无法添加教师账号"""
    login_user(client)

    response = client.post("/teacher/add", json={
        "username": "newteacher",
        "password": "password",
        "login_method": "zhixue"
    })

    assert response.status_code == 403


@patch("app.teacher.routes.login_teacher")
def test_teacher_add_invalid_credentials(mock_login_teacher, client, admin_user):
    """测试使用无效凭证添加教师账号"""
    from zhixuewang.exceptions import UserOrPassError

    mock_login_teacher.side_effect = UserOrPassError("用户名或密码错误")

    login_user(client, username="admin", password="adminpass")

    response = client.post("/teacher/add", json={
        "username": "invalid",
        "password": "wrong",
        "login_method": "zhixue"
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_teacher_add_missing_fields(client, admin_user):
    """测试缺少必要字段"""
    login_user(client, username="admin", password="adminpass")

    response = client.post("/teacher/add", json={
        "username": "incomplete"
        # 缺少 password 和 login_method
    })

    assert response.status_code == 400


# /ping 测试


def test_ping_endpoint(client):
    """测试健康检查端点"""
    response = client.get("/ping")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "pong"
    assert "timestamp" in data


# /<exam_id>/subject/<subject_id>/answersheet 测试（答题卡）
# 注意：答题卡生成比较复杂，我们主要测试权限和基本流程


def test_answersheet_requires_login(client, exam_with_scores):
    """测试未登录无法获取答题卡"""
    response = client.get(f"/exam/{exam_with_scores.id}/subject/subject_001/answersheet")
    assert response.status_code == 401


def test_answersheet_exam_not_found(client, user_with_zhixue):
    """测试访问不存在的考试的答题卡"""
    login_user(client)

    response = client.get("/exam/non_existent/subject/subject_001/answersheet")

    assert response.status_code == 404


# 补充测试：force_refresh、scoresheet、answersheet 边界场景


@patch("app.exam.routes.create_task")
def test_fetch_exam_details_self_no_zhixue(mock_create_task, client, db, sample_exams):
    """测试 SELF 权限用户没有智学网账号无法拉取"""
    user = User(
        username="nozhixue",
        email="nozhixue@example.com",
        role="user",
        permissions="10110",  # SELF 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id=None
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="nozhixue", password="password123")

    response = client.post(f"/exam/exam_001/fetch", json={})

    assert response.status_code == 403  # 装饰器会拦截 SELF 权限但没有账号的用户


@patch("app.exam.routes.create_task")
def test_fetch_exam_details_force_refresh_no_permission(mock_create_task, client, user_with_zhixue, sample_exams):
    """测试强制刷新但没有 REFETCH_EXAM_DATA 权限"""
    # user_with_zhixue 默认权限 "10110" 没有 REFETCH_EXAM_DATA (位置 1)
    login_user(client)

    response = client.post(f"/exam/exam_001/fetch?force_refresh=true", json={})

    assert response.status_code == 403
    data = response.get_json()
    assert "Access Denied" in data["message"]


@patch("app.exam.routes.create_task")
def test_fetch_exam_details_force_refresh_with_permission(mock_create_task, client, db, sample_exams):
    """测试有 REFETCH_EXAM_DATA 权限可以强制刷新"""
    mock_task = Mock()
    mock_task.uuid = "task-force-123"
    mock_create_task.return_value = mock_task

    # 修改用户权限添加 REFETCH_EXAM_DATA (11110)
    user = User(
        username="refetch_user",
        email="refetch@example.com",
        role="user",
        permissions="11110",  # 添加 REFETCH_EXAM_DATA SELF 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id="zx_refetch"
    )
    user.set_password("password123")

    # 创建智学网账号
    zhixue = ZhiXueStudentAccount(
        id="zx_refetch",
        username="refetch_zx",
        password=encrypt("pass"),
        realname="用户",
        cookie=encrypt("cookie"),
        school_id="school_001"
    )
    db.session.add_all([user, zhixue])

    # 创建 UserExam 关联
    user_exam = UserExam(zhixue_id="zx_refetch", exam_id="exam_001")
    db.session.add(user_exam)
    db.session.commit()

    login_user(client, username="refetch_user", password="password123")

    response = client.post(f"/exam/exam_001/fetch?force_refresh=true", json={})

    assert response.status_code == 202
    data = response.get_json()
    assert data["success"] is True

    # 验证参数中包含 force_refresh
    call_kwargs = mock_create_task.call_args[1]
    assert call_kwargs["parameters"]["force_refresh"] is True


# scoresheet 边界场景测试


def test_export_scoresheet_school_scope_no_school_id(client, db, exam_with_scores, school):
    """测试导出成绩单但用户没有 school_id（装饰器拦截）"""
    # 创建没有 school_id 的用户
    user = User(
        username="no_school_user",
        email="noschool@example.com",
        role="user",
        permissions="10111",  # 有 EXPORT_SCORE_SHEET SELF 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=None,
        zhixue_account_id=None
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="no_school_user", password="password123")

    response = client.get(f"/exam/{exam_with_scores.id}/scoresheet?scope=school")

    # 没有 school_id 和 zhixue 的用户会在装饰器层被拦截（403）
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False


def test_export_scoresheet_exam_not_saved(client, db, admin_user, school):
    """测试导出未保存的考试成绩单"""
    # 创建未保存的考试
    exam = Exam(
        id="exam_not_saved",
        name="未保存考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 创建 ExamSchool 但 is_saved=False
    exam_school = ExamSchool(exam_id=exam.id, school_id=school.id, is_saved=False)
    db.session.add(exam_school)
    db.session.commit()

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam.id}/scoresheet?school_id={school.id}")

    assert response.status_code == 400
    data = response.get_json()
    assert "考试数据尚未保存" in data["message"]


def test_export_scoresheet_school_not_in_exam(client, admin_user, exam_with_scores, db):
    """测试导出学校不在考试中的成绩单"""
    # 创建另一个学校
    other_school = School(id="other_school_export", name="��他学校")
    db.session.add(other_school)
    db.session.commit()

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam_with_scores.id}/scoresheet?school_id={other_school.id}")

    assert response.status_code == 400
    data = response.get_json()
    assert "该学校未参与此次考试" in data["message"]


def test_export_scoresheet_self_permission_scope_all_denied(client, db, exam_with_scores):
    """测试 SELF 权限用户无法使用 scope=all"""
    user = User(
        username="selfuser",
        email="self@example.com",
        role="user",
        permissions="10111",  # SELF 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id="zx_self",
        manual_school_id="school_001"
    )
    user.set_password("password123")

    zhixue = ZhiXueStudentAccount(
        id="zx_self",
        username="self_zx",
        password=encrypt("pass"),
        realname="用户",
        cookie=encrypt("cookie"),
        school_id="school_001"
    )
    db.session.add_all([user, zhixue])

    # 添加 UserExam 关联
    user_exam = UserExam(zhixue_id="zx_self", exam_id=exam_with_scores.id)
    db.session.add(user_exam)
    db.session.commit()

    login_user(client, username="selfuser", password="password123")

    response = client.get(f"/exam/{exam_with_scores.id}/scoresheet?scope=all")

    assert response.status_code == 403
    data = response.get_json()
    assert "无权访问该考试" in data["message"]


# answersheet 边界场景测试


def test_answersheet_both_id_and_name_error(client, user_with_zhixue, exam_with_scores):
    """测试同时指定 student_id 和 student_name 返回错误"""
    login_user(client)

    response = client.get(
        f"/exam/{exam_with_scores.id}/subject/subject_001/answersheet?student_id=stu_001&student_name=张三")

    assert response.status_code == 400
    data = response.get_json()
    assert "不可同时指定" in data["message"]


def test_answersheet_name_without_school_id(client, user_with_zhixue, exam_with_scores):
    """测试使用 student_name 但不指定 school_id"""
    login_user(client)

    response = client.get(f"/exam/{exam_with_scores.id}/subject/subject_001/answersheet?student_name=张三")

    assert response.status_code == 400
    data = response.get_json()
    assert "必须指定学校 ID" in data["message"]


def test_answersheet_multi_school_exam_no_school_id(client, user_with_zhixue, db):
    """测试联考必须指定 school_id"""
    # 创建两个学校
    school1 = School(id="school_ms_1", name="学校1")
    school2 = School(id="school_ms_2", name="学校2")
    db.session.add_all([school1, school2])

    # 创建联考
    exam = Exam(
        id="exam_multi_answersheet",
        name="联考",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 关联两个学校
    exam_school1 = ExamSchool(exam_id=exam.id, school_id=school1.id, is_saved=True)
    exam_school2 = ExamSchool(exam_id=exam.id, school_id=school2.id, is_saved=True)
    db.session.add_all([exam_school1, exam_school2])

    # 添加 UserExam
    user_exam = UserExam(zhixue_id=user_with_zhixue.zhixue_account_id, exam_id=exam.id)
    db.session.add(user_exam)
    db.session.commit()

    login_user(client)

    response = client.get(f"/exam/{exam.id}/subject/subject_001/answersheet")

    assert response.status_code == 400
    data = response.get_json()
    assert "该考试为联考，必须指定学校 ID" in data["message"]


def test_answersheet_self_permission_other_student_denied(client, user_with_zhixue, exam_with_scores):
    """测试 SELF 权限用户无法查看其他学生答题卡"""
    login_user(client)

    response = client.get(f"/exam/{exam_with_scores.id}/subject/subject_001/answersheet?student_id=other_student")

    assert response.status_code == 403
    data = response.get_json()
    assert "只能查看自己的成绩" in data["message"]


def test_answersheet_self_permission_cannot_use_name(client, user_with_zhixue, exam_with_scores, school):
    """测试 SELF 权限用户无法使用学生姓名查询"""
    login_user(client)

    response = client.get(
        f"/exam/{exam_with_scores.id}/subject/subject_001/answersheet?student_name=张三&school_id={school.id}")

    assert response.status_code == 403
    data = response.get_json()
    assert "无权使用学生姓名查询成绩" in data["message"]


# get_exam_score 边界场景测试


def test_get_exam_score_school_permission_denied(client, db, exam_with_scores):
    """测试 SCHOOL 权限用户访问其他学校考试成绩被拒绝"""
    # 创建另一个学校
    other_school = School(id="school_score_002", name="其他学校")
    db.session.add(other_school)
    db.session.commit()

    # 创建 SCHOOL 权限用户
    user = User(
        username="schooluser_score",
        email="schoolscore@example.com",
        role="user",
        permissions="22222",  # SCHOOL 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=other_school.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="schooluser_score", password="password123")

    response = client.get(f"/exam/{exam_with_scores.id}/score")

    assert response.status_code == 403
    data = response.get_json()
    assert "无权访问该考试" in data["message"]


def test_get_exam_score_self_no_user_exam(client, db, exam_with_scores):
    """测试 SELF 权限用户访问没有 UserExam 记录的考试"""
    # 创建用户但不创建 UserExam 关联
    user = User(
        username="no_exam_user",
        email="noexam@example.com",
        role="user",
        permissions="11110",  # SELF 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id="zx_no_exam",
        manual_school_id="school_001"
    )
    user.set_password("password123")

    zhixue = ZhiXueStudentAccount(
        id="zx_no_exam",
        username="no_exam_zx",
        password=encrypt("pass"),
        realname="用户",
        cookie=encrypt("cookie"),
        school_id="school_001"
    )
    db.session.add_all([user, zhixue])
    db.session.commit()

    login_user(client, username="no_exam_user", password="password123")

    response = client.get(f"/exam/{exam_with_scores.id}/score")

    assert response.status_code == 403
    data = response.get_json()
    assert "无权访问该考试" in data["message"]


# get_exam_info 边界场景测试


def test_get_exam_info_no_school_returns_empty_list(client, db, admin_user):
    """测试用户没有 school_id 时返回空学校列表"""
    # 修改 admin_user 去掉 school_id
    admin_user.manual_school_id = None
    db.session.commit()

    # 创建考试
    exam = Exam(
        id="exam_no_school_list",
        name="测试考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 创建学校关联
    school = School(id="school_test_empty", name="测试学校")
    db.session.add(school)
    db.session.commit()

    exam_school = ExamSchool(exam_id=exam.id, school_id=school.id, is_saved=True)
    db.session.add(exam_school)
    db.session.commit()

    login_user(client, username="admin", password="adminpass")

    response = client.get(f"/exam/{exam.id}")

    # GLOBAL 权限应该返回所有学校，不管用户有没有 school_id
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["exam"]["schools"]) == 1  # GLOBAL 权限返回所有学校


@pytest.fixture
def multi_school_exam(db):
    """创建联考测试数据（一个考试关联多个学校）"""
    # 创建三个学校
    school1 = School(id="school_multi_001", name="联考学校 A")
    school2 = School(id="school_multi_002", name="联考学校 B")
    school3 = School(id="school_multi_003", name="联考学校 C")
    db.session.add_all([school1, school2, school3])
    db.session.commit()

    # 创建联考
    exam = Exam(
        id="exam_multi_schools",
        name="联考测试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 关联三个学校
    exam_school1 = ExamSchool(exam_id=exam.id, school_id=school1.id, is_saved=True)
    exam_school2 = ExamSchool(exam_id=exam.id, school_id=school2.id, is_saved=False)
    exam_school3 = ExamSchool(exam_id=exam.id, school_id=school3.id, is_saved=True)
    db.session.add_all([exam_school1, exam_school2, exam_school3])
    db.session.commit()

    return {
        "exam": exam,
        "schools": [school1, school2, school3],
        "exam_schools": [exam_school1, exam_school2, exam_school3]
    }


def test_exam_list_multi_school_global_sees_all_schools(client, db, multi_school_exam):
    """
    测试 GLOBAL 权限用户在考试列表中可以看到联考的所有学校信息

    验证：
    - 返回所有 3 个学校
    - 包含正确的学校 ID、名称和保存状态
    """
    # 创建 GLOBAL 权限用户
    user = User(
        username="global_multi_user",
        email="global_multi@example.com",
        role="user",
        permissions="33333",  # GLOBAL 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id=multi_school_exam["schools"][0].id  # 需要基础身份关联
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="global_multi_user", password="password123")

    response = client.get("/exam/list?scope=all")
    assert response.status_code == 200
    data = response.get_json()

    # 找到联考
    exam_data = next(
        (e for e in data["exams"] if e["id"] == "exam_multi_schools"),
        None
    )
    assert exam_data is not None

    # GLOBAL 权限应该看到所有 3 个学校
    assert len(exam_data["schools"]) == 3

    # 验证学校 ID
    school_ids = [s["school_id"] for s in exam_data["schools"]]
    assert "school_multi_001" in school_ids
    assert "school_multi_002" in school_ids
    assert "school_multi_003" in school_ids


def test_exam_list_multi_school_school_permission_sees_own_school_only(client, db, multi_school_exam):
    """
    测试 SCHOOL 权限用户在考试列表中只能看到自己学校的信息

    验证：
    - 只返回用户所属学校的信息
    - 不泄露其他学校的 ID、名称或保存状态
    """
    # 创建 SCHOOL 权限用户（属于 school_multi_002）
    user = User(
        username="school_multi_user",
        email="school_multi@example.com",
        role="user",
        permissions="22222",  # SCHOOL 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id="school_multi_002"
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="school_multi_user", password="password123")

    response = client.get("/exam/list?scope=school")
    assert response.status_code == 200
    data = response.get_json()

    # 找到联考
    exam_data = next(
        (e for e in data["exams"] if e["id"] == "exam_multi_schools"),
        None
    )
    assert exam_data is not None

    # SCHOOL 权限应该只看到自己学校（school_multi_002）
    assert len(exam_data["schools"]) == 1
    assert exam_data["schools"][0]["school_id"] == "school_multi_002"
    assert exam_data["schools"][0]["school_name"] == "联考学校 B"
    assert exam_data["schools"][0]["is_saved"] is False


def test_exam_list_multi_school_self_permission_sees_own_school_only(client, db, multi_school_exam):
    """
    测试 SELF 权限用户在考试列表中只能看到自己学校的信息

    验证：
    - 即使用户参与了联考，也只能看到自己学校的信息
    - 不泄露其他参与学校的任何信息
    """
    # 创建智学网账号（属于 school_multi_001）
    zhixue_account = ZhiXueStudentAccount(
        id="zx_multi_001",
        username="zx_multi_user",
        password=encrypt("password"),
        realname="联考学生",
        cookie=encrypt("cookie"),
        school_id="school_multi_001"
    )
    db.session.add(zhixue_account)
    db.session.commit()

    # 创建 SELF 权限用户
    user = User(
        username="self_multi_user",
        email="self_multi@example.com",
        role="user",
        permissions="11111",  # SELF 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        zhixue_account_id=zhixue_account.id
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建 UserExam 关联
    user_exam = UserExam(zhixue_id=zhixue_account.id, exam_id="exam_multi_schools")
    db.session.add(user_exam)
    db.session.commit()

    login_user(client, username="self_multi_user", password="password123")

    response = client.get("/exam/list?scope=self")
    assert response.status_code == 200
    data = response.get_json()

    # 找到联考
    exam_data = next(
        (e for e in data["exams"] if e["id"] == "exam_multi_schools"),
        None
    )
    assert exam_data is not None

    # SELF 权限应该只看到自己学校（school_multi_001）
    assert len(exam_data["schools"]) == 1
    assert exam_data["schools"][0]["school_id"] == "school_multi_001"
    assert exam_data["schools"][0]["school_name"] == "联考学校 A"
    assert exam_data["schools"][0]["is_saved"] is True


def test_exam_list_schools_filter_consistency_with_exam_detail(client, db, multi_school_exam):
    """
    测试考试列表的学校过滤与考试详情 API 保持一致

    验证：
    - /exam/list 返回的学校信息
    - 与 /exam/{exam_id} 返回的学校信息一致
    """
    user = User(
        username="consistency_test_user",
        email="consistency@example.com",
        role="user",
        permissions="22222",  # SCHOOL 权限
        created_at=datetime.utcnow(),
        email_verified=True,
        manual_school_id="school_multi_003"
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    login_user(client, username="consistency_test_user", password="password123")

    list_response = client.get("/exam/list?scope=school")
    assert list_response.status_code == 200
    list_data = list_response.get_json()

    # 找到联考
    list_exam = next(
        (e for e in list_data["exams"] if e["id"] == "exam_multi_schools"),
        None
    )
    assert list_exam is not None

    # 获取考试详情
    detail_response = client.get(f"/exam/{multi_school_exam['exam'].id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.get_json()

    # 验证学校信息一致
    assert len(list_exam["schools"]) == len(detail_data["exam"]["schools"])
    assert list_exam["schools"][0]["school_id"] == detail_data["exam"]["schools"][0]["school_id"]
    assert list_exam["schools"][0]["school_name"] == detail_data["exam"]["schools"][0]["school_name"]
    assert list_exam["schools"][0]["is_saved"] == detail_data["exam"]["schools"][0]["is_saved"]
