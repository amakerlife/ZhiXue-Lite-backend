"""
get_teacher() 辅助函数测试

测试 app/exam/routes.py 中的 get_teacher() 函数，包括：
- 正常获取教师账号
- 多学校考试需要 school_id
- 考试不存在的错误处理
- 学校没有教师账号的错误处理
"""
import pytest
from app.database.models import Exam, ExamSchool, School, ZhiXueTeacherAccount
from app.exam.routes import get_teacher
from app.models.exceptions import FailedToGetTeacherAccountError
from datetime import datetime
import time


@pytest.fixture
def multi_school_exam(db):
    """创建多学校联考"""
    # 创建两个学校
    school1 = School(id="school_multi_001", name="联考学校 1")
    school2 = School(id="school_multi_002", name="联考学校 2")
    db.session.add_all([school1, school2])

    # 创建联考
    exam = Exam(
        id="exam_multi",
        name="联考测试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    # 关联两个学校
    exam_school1 = ExamSchool(exam_id=exam.id, school_id=school1.id, is_saved=True)
    exam_school2 = ExamSchool(exam_id=exam.id, school_id=school2.id, is_saved=True)
    db.session.add_all([exam_school1, exam_school2])
    db.session.commit()

    return exam


@pytest.fixture
def single_school_exam(db, test_school):
    """创建单学校考试"""
    exam = Exam(
        id="exam_single",
        name="单校考试",
        created_at=int(time.time() * 1000)
    )
    db.session.add(exam)
    db.session.commit()

    exam_school = ExamSchool(exam_id=exam.id, school_id=test_school.id, is_saved=True)
    db.session.add(exam_school)
    db.session.commit()

    return exam


def test_get_teacher_success_with_school_id(db, test_school, test_teacher_account):
    """测试成功获取教师账号（提供 school_id）"""
    teacher = get_teacher("", school_id=test_school.id)

    assert teacher.id == test_teacher_account.id
    assert teacher.school_id == test_school.id


def test_get_teacher_success_single_school_exam(db, single_school_exam, test_teacher_account):
    """测试单学校考试自动获取 school_id"""
    teacher = get_teacher(single_school_exam.id)

    assert teacher.id == test_teacher_account.id


def test_get_teacher_multi_school_exam_without_school_id(db, multi_school_exam):
    """测试多学校考试但不提供 school_id 会报错"""
    with pytest.raises(FailedToGetTeacherAccountError, match="multi-school exam"):
        get_teacher(multi_school_exam.id)


def test_get_teacher_exam_not_found(db):
    """测试考试不存在时报错"""
    with pytest.raises(FailedToGetTeacherAccountError, match="can not be found"):
        get_teacher("non_existent_exam")


def test_get_teacher_no_teacher_for_school(db, test_school):
    """测试学校没有教师账号时报错"""
    # 创建另一个没有教师账号的学校
    school_no_teacher = School(id="school_no_teacher", name="无教师学校")
    db.session.add(school_no_teacher)
    db.session.commit()

    with pytest.raises(FailedToGetTeacherAccountError, match="teacher not found for school_id"):
        get_teacher("", school_id=school_no_teacher.id)
