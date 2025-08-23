from dataclasses import dataclass, field


@dataclass
class Score():
    name: str
    score: str
    classrank: str
    schoolrank: str
    subjectcode: int  # -1 for 总分
    topicsetid: str
    standard_score: str
    sort: int = 1


@dataclass
class StudentScoreInfo():
    username: str
    user_id: str
    studentno: str
    usernum: str
    label: str
    class_name: str
    all_score: str
    class_rank: str
    school_rank: str
    scores: list[Score] = field(default_factory=list)

    def add_subject_score(
        self,
        subject_name: str,
        score: str,
        class_rank: str,
        school_rank: str,
        subject_code: int,
        topicsetid: str,
        standard_score: str,
        sort: int = 1
    ):
        self.scores.append(Score(
            subject_name,
            score,
            class_rank,
            school_rank,
            subject_code,
            topicsetid,
            standard_score,
            sort
        ))
