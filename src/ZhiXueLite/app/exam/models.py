from app.database import db


class Student(db.Model):
    __tablename__ = "students"

    student_id = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    student_name = db.Column(db.String(50), nullable=False)
    student_label = db.Column(db.String(50), nullable=False)
    student_no = db.Column(db.String(50), nullable=False)


class Exam(db.Model):
    __tablename__ = "exams"

    exam_id = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    exam_name = db.Column(db.String(255), nullable=False)


class UserExam(db.Model):
    __tablename__ = "user_exams"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    zhixue_username = db.Column(db.String(50), nullable=False)
    exam_id = db.Column(db.String(50), db.ForeignKey('exams.exam_id'), nullable=False)
    exam_name = db.Column(db.String(255), db.ForeignKey('exams.exam_name'), nullable=False)

    exam = db.relationship("Exam", backref="user_exams")


class Subject(db.Model):
    __tablename__ = "subjects"

    subject_id = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    subject_name = db.Column(db.String(20), nullable=False)


class Score(db.Model):
    __tablename__ = "scores"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(50), db.ForeignKey('students.student_id'), nullable=False)
    exam_id = db.Column(db.String(50), db.ForeignKey('exams.exam_id'), nullable=False)
    subject_id = db.Column(db.String(50), db.ForeignKey('subjects.subject_id'), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)

    score = db.Column(db.Float, nullable=True)  # 为空时表示原始数据无成绩，下同
    class_rank = db.Column(db.Integer, nullable=True)
    school_rank = db.Column(db.Integer, nullable=True)
    score_status = db.Column(db.String(20), nullable=True, default="ok")  # 状态，ok 正常，错误状态待发掘

    student = db.relationship("Student", backref="scores")
    exam = db.relationship("Exam", backref="scores")
    subject = db.relationship("Subject", backref="scores")
