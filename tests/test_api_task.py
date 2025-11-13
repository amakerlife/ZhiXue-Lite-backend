"""
Task API 测试

测试任务相关的 API 端点：
- GET /task/status/<uuid> - 获取任务状态
- GET /task/list - 获取任务列表
- POST /task/cancel/<uuid> - 取消任务
"""
from datetime import datetime
import uuid
import pytest
from app.database.models import User, BackgroundTask, TaskStatus


@pytest.fixture
def other_user(db):
    """创建另一个测试用户（用于测试权限隔离）"""
    user = User(
        username="otheruser",
        email="other@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_tasks(db, regular_user):
    """创建一些示例任务

    创建 5 个任务，不同状态：
    - 2 个 PENDING
    - 1 个 PROCESSING
    - 1 个 COMPLETED
    - 1 个 FAILED
    """
    tasks = [
        BackgroundTask(
            task_type="fetch_user_exam_list",
            status=TaskStatus.PENDING.value,
            user_id=regular_user.id,
            parameters='{"exam_id": "exam_001"}',
            progress=0
        ),
        BackgroundTask(
            task_type="fetch_school_exam_list",
            status=TaskStatus.PENDING.value,
            user_id=regular_user.id,
            parameters='{"exam_id": "exam_002"}',
            progress=0
        ),
        BackgroundTask(
            task_type="fetch_school_exam_detail",
            status=TaskStatus.PROCESSING.value,
            user_id=regular_user.id,
            parameters='{"exam_id": "exam_003"}',
            progress=50,
            progress_message="正在处理..."
        ),
        BackgroundTask(
            task_type="fetch_exam_detail",
            status=TaskStatus.COMPLETED.value,
            user_id=regular_user.id,
            parameters='{"exam_id": "exam_004"}',
            progress=100,
            result='{"success": true}'
        ),
        BackgroundTask(
            task_type="fetch_exam_detail",
            status=TaskStatus.FAILED.value,
            user_id=regular_user.id,
            parameters='{"exam_id": "exam_005"}',
            progress=0,
            error_message="网络错误"
        ),
    ]

    db.session.add_all(tasks)
    db.session.commit()
    return tasks


def login_user(client, username="testuser", password="password123"):
    """辅助函数：登录用户"""
    response = client.post("/user/login", json={
        "login": username,
        "password": password
    })
    assert response.status_code == 200
    return response


def test_get_task_status_success(client, regular_user, sample_tasks):
    """测试成功获取任务状态"""
    login_user(client)

    task = sample_tasks[0]
    response = client.get(f"/task/status/{task.uuid}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["task"]["id"] == task.uuid
    assert data["task"]["status"] == TaskStatus.PENDING.value


def test_get_task_status_not_found(client, regular_user):
    """测试获取不存在的任务"""
    login_user(client)

    non_existent_uuid = str(uuid.uuid4())
    response = client.get(f"/task/status/{non_existent_uuid}")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "任务不存在"


def test_get_task_status_other_user(client, regular_user, other_user, sample_tasks):
    """测试无法获取其他用户的任务（权限隔离）"""
    login_user(client, "otheruser", "password123")

    response = client.get(f"/task/status/{sample_tasks[0].uuid}")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "任务不存在"


def test_get_task_status_requires_login(client, sample_tasks):
    """测试未登录无法获取任务状态"""
    task = sample_tasks[0]
    response = client.get(f"/task/status/{task.uuid}")
    assert response.status_code == 401


def test_get_task_list_success(client, regular_user, sample_tasks):
    """测试成功获取任务列表"""
    login_user(client)

    response = client.get("/task/list")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["tasks"]) == 5
    assert "pagination" in data


def test_get_task_list_pagination(client, regular_user, sample_tasks):
    """测试任务列表分页"""
    login_user(client)

    response = client.get("/task/list?page=1&per_page=2")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["tasks"]) == 2
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["pages"] == 3


def test_get_task_list_filter_by_status(client, regular_user, sample_tasks):
    """测试按状态过滤任务列表"""
    login_user(client)

    response = client.get("/task/list?status=pending")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["tasks"]) == 2
    for task in data["tasks"]:
        assert task["status"] == TaskStatus.PENDING.value


def test_get_task_list_invalid_status(client, regular_user):
    """测试无效的状态值"""
    login_user(client)

    response = client.get("/task/list?status=invalid_status")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "无效的状态值"


def test_cancel_pending_task_success(client, regular_user, sample_tasks):
    """测试成功取消 PENDING 状态的任务"""
    login_user(client)

    task = sample_tasks[0]
    assert task.status == TaskStatus.PENDING.value

    response = client.post(f"/task/cancel/{task.uuid}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "任务已取消"


def test_cancel_processing_task_success(client, regular_user, sample_tasks):
    """测试成功取消 PROCESSING 状态的任务"""
    login_user(client)

    task = sample_tasks[2]
    assert task.status == TaskStatus.PROCESSING.value

    response = client.post(f"/task/cancel/{task.uuid}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "已发送取消请求，请稍后刷新"


def test_cancel_task_not_pending(client, regular_user, sample_tasks):
    """测试无法取消非 PENDING 状态的任务"""
    login_user(client)

    task = sample_tasks[3]
    assert task.status == TaskStatus.COMPLETED.value

    response = client.post(f"/task/cancel/{task.uuid}")

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "当前任务不支持取消"


def test_cancel_task_not_found(client, regular_user):
    """测试取消不存在的任务"""
    login_user(client)

    non_existent_uuid = str(uuid.uuid4())
    response = client.post(f"/task/cancel/{non_existent_uuid}")

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "任务不存在"


def test_cancel_task_other_user(client, regular_user, other_user, sample_tasks):
    """测试无法取消其他用户的任务"""
    login_user(client, "otheruser", "password123")

    response = client.post(f"/task/cancel/{sample_tasks[0].uuid}")

    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["message"] == "任务不存在"