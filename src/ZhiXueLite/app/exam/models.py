from typing import Optional, List
from sqlalchemy import String, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(50))
    no: Mapped[str] = mapped_column(String(50))

    scores: Mapped[List["Score"]] = relationship("Score", back_populates="student")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[float] = mapped_column(Float)

    user_exams: Mapped[List["UserExam"]] = relationship("UserExam", back_populates="exam")
    scores: Mapped[List["Score"]] = relationship("Score", back_populates="exam")


class UserExam(Base):
    __tablename__ = "user_exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zhixue_username: Mapped[str] = mapped_column(String(50))
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey('exams.id'))

    exam: Mapped["Exam"] = relationship("Exam", back_populates="user_exams")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, unique=True)
    name: Mapped[str] = mapped_column(String(20))

    scores: Mapped[List["Score"]] = relationship("Score", back_populates="subject")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey('students.id'))
    exam_id: Mapped[str] = mapped_column(String(50), ForeignKey('exams.id'))
    subject_id: Mapped[str] = mapped_column(String(50), ForeignKey('subjects.id'))
    class_name: Mapped[str] = mapped_column(String(50))

    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 为空时表示原始数据无成绩，下同
    class_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    school_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="ok")  # 状态，ok 正常，错误状态待发掘

    student: Mapped["Student"] = relationship("Student", back_populates="scores")
    exam: Mapped["Exam"] = relationship("Exam", back_populates="scores")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="scores")
