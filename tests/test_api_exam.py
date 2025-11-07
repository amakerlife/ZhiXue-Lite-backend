"""
考试 API 测试

测试考试列表端点，包括分页、权限、查询过滤等功能
"""
import time
from datetime import datetime
import pytest
from app.database.models import User, School, ZhiXueStudentAccount, Exam, ExamSchool, UserExam


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
        password="encrypted_password",
        realname="张三",
        cookie="fake_cookie",
        school_id=school.id
    )
    db.session.add(account)
    db.session.commit()
    return account


@pytest.fixture
def test_user(db, zhixue_account):
    """创建有智学网账号的测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True,
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


def test_exam_list_self_scope_default(client, test_user, sample_exams):
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


def test_exam_list_pagination(client, test_user, sample_exams):
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


def test_exam_list_search_query(client, test_user, sample_exams, db):
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


# ===== 下面是一些更高级的测试，我们稍后一起完成 =====

@pytest.mark.parametrize("page,per_page,expected_items,expected_pages,has_prev,has_next", [
    (1, 2, 2, 3, False, True),   # 第一页：2 条数据，共 3 页，无上一页，有下一页
    (2, 2, 2, 3, True, True),    # 第二页：2 条数据，共 3 页，有上一页，有下一页
    (3, 2, 1, 3, True, False),   # 第三页：1 条数据，共 3 页，有上一页，无下一页
    (1, 10, 5, 1, False, False), # 单页：5 条数据，共 1 页，无上一页，无下一页
])
def test_exam_list_pagination_scenarios(
    client, test_user, sample_exams,
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
    # 在 sample_exams 中，我们只为前 5 个考试创建了 ExamSchool 关联
    assert len(data["exams"]) == 5
