"""
基础功能测试

这个文件测试应用的基本功能，不涉及复杂的业务逻辑
是学习单元测试的最佳起点
"""


def test_app_exists(app):
    """
    测试应用实例是否成功创建

    参数 app 来自 conftest.py 中的 app fixture
    """
    assert app is not None


def test_app_is_testing(app):
    """
    测试应用是否处于测试模式

    验证配置是否正确加载
    """
    assert app.config["TESTING"] is True


def test_ping_endpoint(client):
    """
    测试 /ping 健康检查端点
    """
    response = client.get("/ping")

    assert response.status_code == 200

    data = response.get_json()

    assert data["success"] is True
    assert data["message"] == "pong"
    assert "timestamp" in data


def test_statistics_endpoint(client, db, regular_user, admin_user, test_school):
    """
    测试 /statistics 统计端点数据正确性
    """
    from app.database.models import School, Exam, ExamSchool
    from datetime import datetime

    school2 = School(id="school_002", name="测试二中")
    db.session.add(school2)

    exam1 = Exam(
        id="exam_001",
        name="期中考试",
        created_at=datetime.utcnow().timestamp(),
        is_saved=False
    )
    exam2 = Exam(
        id="exam_002",
        name="期末考试",
        created_at=datetime.utcnow().timestamp(),
        is_saved=False
    )
    db.session.add_all([exam1, exam2])
    db.session.commit()

    exam_school1 = ExamSchool(exam_id=exam1.id, school_id=test_school.id, is_saved=True)
    exam_school2 = ExamSchool(exam_id=exam2.id, school_id=school2.id, is_saved=False)
    db.session.add_all([exam_school1, exam_school2])
    db.session.commit()

    response = client.get("/statistics")

    assert response.status_code == 200

    data = response.get_json()

    assert data["success"] is True
    assert "statistics" in data

    stats = data["statistics"]
    assert stats["total_users"] == 2  # regular_user + admin_user
    assert stats["total_schools"] == 2  # test_school + school2
    assert stats["total_exams"] == 2  # exam1 + exam2
    assert stats["saved_exams"] == 1  # exam1
