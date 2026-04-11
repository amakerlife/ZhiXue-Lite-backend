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
    is_assign: bool  # 是否赋分科目
    sort: int = 1
    is_calculated: bool = False  # 总分是否为计算得到
    origin_score: str = ""  # 原始分，仅赋分科目存在


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
        is_assign: bool,
        sort: int = 1,
        is_calculated: bool = False,
        origin_score: str = "",
    ):
        self.scores.append(Score(
            subject_name,
            score,
            class_rank,
            school_rank,
            subject_code,
            topicsetid,
            standard_score,
            is_assign,
            sort,
            is_calculated,
            origin_score
        ))
