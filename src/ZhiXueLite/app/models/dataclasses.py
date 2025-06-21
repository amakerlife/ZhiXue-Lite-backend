from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Score():
    name: str
    score: str
    classrank: str
    schoolrank: str
    subjectcode: int


@dataclass
class StudentScoreInfo():
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
            "总分": Score("总分", self.all_score, self.class_rank,
                        self.school_rank, -1)
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
            subject_name,
            score,
            class_rank,
            school_rank,
            subject_code
        )
