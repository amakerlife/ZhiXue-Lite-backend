"""
考试模型测试
"""
import time
from app.database.models import School, Exam, ExamSchool


def test_create_school(db):
    """
    测试创建学校
    """
    school = School(
        id="school_001",
        name="测试中学"
    )
    db.session.add(school)
    db.session.commit()

    saved_school = db.session.get(School, "school_001")
    assert saved_school is not None
    assert saved_school.name == "测试中学"


def test_create_exam(db):
    """
    测试创建考试
    """
    exam = Exam(
        id="exam_001",
        name="期中考试",
        created_at=int(time.time()) * 1000
    )

    db.session.add(exam)
    db.session.commit()

    saved_exam = db.session.get(Exam, "exam_001")
    assert saved_exam is not None
    assert saved_exam.name == "期中考试"
    assert saved_exam.created_at > 0


def test_exam_school_relationship(db):
    """
    测试考试和学校的多对多关系
    """
    school1 = School(id="school_001", name="第一中学")
    school2 = School(id="school_002", name="第二中学")
    db.session.add_all([school1, school2])

    exam = Exam(
        id="exam_001",
        name="联考",
        created_at=int(time.time()) * 1000
    )
    db.session.add(exam)
    db.session.commit()

    exam_school1 = ExamSchool(
        exam_id="exam_001",
        school_id="school_001",
        is_saved=True
    )
    exam_school2 = ExamSchool(
        exam_id="exam_001",
        school_id="school_002",
        is_saved=False
    )
    db.session.add_all([exam_school1, exam_school2])
    db.session.commit()

    saved_exam = db.session.get(Exam, "exam_001")
    assert len(saved_exam.schools) == 2

    school_ids = saved_exam.get_school_ids()
    assert "school_001" in school_ids
    assert "school_002" in school_ids


def test_exam_is_saved_for_school(db):
    """
    测试 Exam.is_saved_for_school() 方法
    """
    school1 = School(id="school_001", name="第一中学")
    school2 = School(id="school_002", name="第二中学")
    db.session.add_all([school1, school2])

    exam = Exam(id="exam_001", name="测试考试", created_at=int(time.time()) * 1000)
    db.session.add(exam)
    db.session.commit()

    exam_school1 = ExamSchool(exam_id="exam_001", school_id="school_001", is_saved=True)
    exam_school2 = ExamSchool(exam_id="exam_001", school_id="school_002", is_saved=False)
    db.session.add_all([exam_school1, exam_school2])
    db.session.commit()

    saved_exam = db.session.get(Exam, "exam_001")

    assert saved_exam.is_saved_for_school("school_001") is True
    assert saved_exam.is_saved_for_school("school_002") is False
    assert saved_exam.is_saved_for_school("school_999") is False


def test_exam_get_schools_saved_status(db):
    """
    测试 Exam.get_schools_saved_status() 方法
    """
    school1 = School(id="school_001", name="第一中学")
    school2 = School(id="school_002", name="第二中学")
    db.session.add_all([school1, school2])

    exam = Exam(id="exam_001", name="测试考试", created_at=int(time.time()) * 1000)
    db.session.add(exam)
    db.session.commit()

    exam_school1 = ExamSchool(exam_id="exam_001", school_id="school_001", is_saved=True)
    exam_school2 = ExamSchool(exam_id="exam_001", school_id="school_002", is_saved=False)
    db.session.add_all([exam_school1, exam_school2])
    db.session.commit()

    saved_exam = db.session.get(Exam, "exam_001")
    status_list = saved_exam.get_schools_saved_status()

    assert len(status_list) == 2
    assert isinstance(status_list, list)
    assert isinstance(status_list[0], dict)

    status_dict = {item["school_id"]: item for item in status_list}
    assert status_dict["school_001"]["is_saved"] is True
    assert status_dict["school_001"]["school_name"] == "第一中学"
    assert status_dict["school_002"]["is_saved"] is False
    assert status_dict["school_002"]["school_name"] == "第二中学"


def test_exam_school_unique_constraint(db):
    """
    测试 ExamSchool 的唯一性约束
    """
    school = School(id="school_001", name="测试中学")
    exam = Exam(id="exam_001", name="测试考试", created_at=int(time.time()) * 1000)
    db.session.add_all([school, exam])
    db.session.commit()

    exam_school1 = ExamSchool(exam_id="exam_001", school_id="school_001")
    db.session.add(exam_school1)
    db.session.commit()

    exam_school2 = ExamSchool(exam_id="exam_001", school_id="school_001")
    db.session.add(exam_school2)

    from sqlalchemy.exc import IntegrityError
    import pytest

    with pytest.raises(IntegrityError):
        db.session.commit()
