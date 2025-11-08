"""
BackgroundTask 模型测试

测试后台任务模型的功能：
- 任务创建和基本属性
- 任务状态枚举值
- UUID 唯一性
- 与用户的关联关系
"""
from datetime import datetime
from app.database.models import BackgroundTask, TaskStatus, User


# 任务基础功能测试

def test_create_background_task(db):
    """
    测试创建后台任务并验证数据持久化

    流程：
    1. 创建测试用户
    2. 创建关联到用户的后台任务
    3. 验证任务属性正确保存
    4. 验证任务自动生成 UUID
    """
    # 创建一个用户
    user = User(
        username="taskuser",
        email="task@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建后台任务
    task = BackgroundTask(
        task_type="fetch_exam_list",
        status=TaskStatus.PENDING.value,
        user_id=user.id,
        parameters='{"exam_id": "test_exam"}',
        progress=0
    )
    db.session.add(task)
    db.session.commit()

    # 验证任务创建成功
    saved_task = db.session.query(BackgroundTask).filter_by(user_id=user.id).first()
    assert saved_task is not None
    assert saved_task.task_type == "fetch_exam_list"
    assert saved_task.status == TaskStatus.PENDING.value
    assert saved_task.user_id == user.id
    assert saved_task.parameters == '{"exam_id": "test_exam"}'
    assert saved_task.progress == 0
    assert saved_task.uuid is not None  # UUID 自动生成


# 任务状态枚举测试

def test_task_status_values(db):
    """
    测试任务状态枚举值的正确性

    验证所有预定义状态值都是正确的字符串常量
    """
    # 验证所有状态值都是字符串
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.PROCESSING.value == "processing"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLING.value == "cancelling"
    assert TaskStatus.CANCELLED.value == "cancelled"


# UUID 唯一性测试

def test_task_has_unique_uuid(db):
    """
    测试每个任务都有唯一的 UUID

    验证：
    1. 任务创建时自动生成 UUID
    2. 不同任务的 UUID 不同
    3. UUID 格式正确
    """
    user = User(
        username="uuiduser",
        email="uuid@example.com",
        role="user",
        permissions="10110",
        created_at=datetime.utcnow(),
        email_verified=True
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # 创建两个任务
    task1 = BackgroundTask(
        task_type="test_task",
        status=TaskStatus.PENDING.value,
        user_id=user.id
    )
    task2 = BackgroundTask(
        task_type="test_task",
        status=TaskStatus.PENDING.value,
        user_id=user.id
    )

    db.session.add_all([task1, task2])
    db.session.commit()

    # 验证 UUID 唯一性
    assert task1.uuid is not None
    assert task2.uuid is not None
    assert task1.uuid != task2.uuid
    # 验证 UUID 格式（应该是字符串）
    assert isinstance(task1.uuid, str)
    assert isinstance(task2.uuid, str)
