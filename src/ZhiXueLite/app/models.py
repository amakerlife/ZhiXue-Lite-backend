from dataclasses import field
from typing import Dict
from pydantic import BaseModel


class ZhixueError(Exception):
    pass


class LoginCaptchaError(Exception):
    pass


class FailedToGetTeacherAccountError(Exception):
    pass


class FailedToGetStudentAccountError(Exception):
    pass


class CommandError(Exception):
    pass


class ConfigError(Exception):
    pass


class Score(BaseModel):
    name: str
    score: str
    classrank: str
    schoolrank: str
    subjectcode: int


class StudentScoreInfo(BaseModel):
    username: str
    user_id: str
    label: str
    class_name: str
    all_score: str
    class_rank: str
    school_rank: str
    scores: Dict[str, Score] = field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        self.scores = {
            "总分": Score(name="总分", score=self.all_score,
                        classrank=self.class_rank,
                        schoolrank=self.school_rank, subjectcode=-1)
        }

    def add_subject_score(
        self,
        subject_name: str,
        score: str,
        class_rank: str,
        school_rank: str,
        subject_code: int
    ):
        self.scores[subject_name] = Score(
            name=subject_name,
            score=score,
            classrank=class_rank,
            schoolrank=school_rank,
            subjectcode=subject_code
        )
