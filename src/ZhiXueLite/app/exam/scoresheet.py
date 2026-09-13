"""
成绩单数据构建
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Integer, Numeric, case, cast, func, select
from sqlalchemy.sql import ColumnElement

from app.database import db
from app.database.models import School, Score, Student

SORT_COLUMNS = ("name", "school", "label", "class_name")
SUBJECT_SORT_FIELDS = ("score", "origin_score", "class_rank", "school_rank")


class InvalidSortError(ValueError):
    """sort_by 参数不合法"""


@dataclass
class SheetSubject:
    name: str
    sort: int
    is_assign: bool

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "sort": self.sort, "is_assign": self.is_assign}


@dataclass
class SheetStudent:
    student_id: str
    school_id: str
    name: str
    school: str | None
    label: str | None
    class_name: str | None
    subjects: dict[str, dict[str, str | None]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "school_id": self.school_id,
            "name": self.name,
            "school": self.school,
            "label": self.label,
            "class_name": self.class_name,
            "subjects": self.subjects,
        }


def scope_filters(exam_id: str, scope: str, school_id: str | None) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [Score.exam_id == exam_id]
    if scope == "school":
        filters.append(Score.school_id == school_id)
    return filters


def _is_postgresql() -> bool:
    return db.engine.name == "postgresql"


def numeric_rank(col):
    """排名列转数字：取前导数字（如 "2(并列)" → 2），无前导数字为 NULL。非 PostgreSQL 退化为字符串比较"""
    if _is_postgresql():
        return cast(func.substring(col, r"^\d+"), Integer)
    return col


def numeric_score(col):
    """分数列转数字：仅纯数字字符串参与比较，其余为 NULL。非 PostgreSQL 退化为字符串比较"""
    if _is_postgresql():
        return case((col.op("~")(r"^-?\d+(\.\d+)?$"), cast(col, Numeric)), else_=None)
    return col


def list_subjects(filters) -> list[SheetSubject]:
    stmt = (
        select(
            Score.subject_name,
            func.min(Score.sort).label("sort"),
            func.max(cast(Score.is_assign, Integer)).label("is_assign"),
        )
        .where(*filters)
        .group_by(Score.subject_name)
        .order_by(func.min(Score.sort), Score.subject_name)
    )
    return [
        SheetSubject(name=row.subject_name, sort=row.sort, is_assign=bool(row.is_assign))
        for row in db.session.execute(stmt).all()
    ]


def list_classes(filters) -> list[str]:
    stmt = select(Score.class_name).where(*filters).distinct().order_by(Score.class_name)
    return [name for name in db.session.scalars(stmt).all() if name is not None]


def _subject_key(subject_name: str, col):
    return func.min(case((Score.subject_name == subject_name, col), else_=None))


def _field_expr(field_name: str):
    col = getattr(Score, field_name)
    if field_name in ("class_rank", "school_rank"):
        return numeric_rank(col)
    return numeric_score(col)


def build_sort_keys(subjects: list[SheetSubject], sort_by: str | None, order: str):
    """
    返回 (select_labels, order_clauses)。

    缺省顺序复刻 Excel：各科校次、班次升序，最后按姓名。空值恒在末尾。
    """
    keys = []
    if not sort_by:
        for index, subject in enumerate(subjects):
            keys.append(_subject_key(subject.name, numeric_rank(Score.school_rank)).label(f"k{index}_school"))
            keys.append(_subject_key(subject.name, numeric_rank(Score.class_rank)).label(f"k{index}_class"))
    elif sort_by in SORT_COLUMNS:
        if sort_by == "name":
            keys.append(Student.name.label("k_name"))
        elif sort_by == "school":
            keys.append(School.name.label("k_school"))
        elif sort_by == "label":
            keys.append(Student.label.label("k_label"))
        else:
            keys.append(func.min(Score.class_name).label("k_class_name"))
    elif sort_by.startswith("subject:"):
        parts = sort_by.split(":")
        if len(parts) != 3:
            raise InvalidSortError(sort_by)
        _, subject_name, field_name = parts
        if field_name not in SUBJECT_SORT_FIELDS or subject_name not in {s.name for s in subjects}:
            raise InvalidSortError(sort_by)
        keys.append(_subject_key(subject_name, _field_expr(field_name)).label("k_subject"))
    else:
        raise InvalidSortError(sort_by)

    order_clauses = []
    for key in keys:
        order_clauses.append(key.is_(None))
        order_clauses.append(key.desc() if order == "desc" else key.asc())
    order_clauses.append(Student.name.asc())
    return keys, order_clauses


def _students_stmt(filters, class_name: str | None, query: str | None, sort_labels):
    """按 (student_id, school_id) 透视的学生查询，一行一个学生，附带排序键列"""
    stmt = (
        select(
            Score.student_id,
            Score.school_id,
            Student.name,
            Student.label,
            School.name.label("school_name"),
            func.min(Score.class_name).label("class_name"),
            *sort_labels,
        )
        .join(Student, Student.id == Score.student_id)
        .outerjoin(School, School.id == Score.school_id)
        .where(*filters)
        .group_by(Score.student_id, Score.school_id, Student.name, Student.label, School.name)
    )
    if class_name:
        stmt = stmt.where(Score.class_name == class_name)
    if query:
        stmt = stmt.where(Student.name.contains(query, autoescape=True))
    return stmt


def query_students_page(filters, class_name: str | None, query: str | None,
                        sort_labels, order_clauses, page: int, per_page: int):
    """per_page <= 0 时不加 LIMIT/OFFSET，也不单独 COUNT，total 取返回行数"""
    base = _students_stmt(filters, class_name, query, sort_labels)
    stmt = base.order_by(*order_clauses)

    if per_page > 0:
        total = db.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = db.session.execute(stmt.limit(per_page).offset((page - 1) * per_page)).all()
    else:
        rows = db.session.execute(stmt).all()
        page, total = 1, len(rows)
        per_page = max(total, 1)

    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
        "has_prev": page > 1,
        "has_next": page * per_page < total,
    }
    return rows, pagination


def load_cells(filters, student_ids: list[str] | None = None) -> dict[tuple[str, str], dict[str, dict[str, str | None]]]:
    """查出学生的全部 Score 行，按 (student_id, school_id) → subject_name 透视。student_ids 为 None 时不限学生"""
    cells: dict[tuple[str, str], dict[str, dict[str, str | None]]] = {}
    stmt = select(Score).where(*filters)
    if student_ids is not None:
        if not student_ids:
            return cells
        stmt = stmt.where(Score.student_id.in_(student_ids))
    for score in db.session.scalars(stmt).all():
        cells.setdefault((score.student_id, score.school_id), {})[score.subject_name] = {
            "score": score.score,
            "origin_score": score.origin_score,
            "class_rank": score.class_rank,
            "school_rank": score.school_rank,
        }
    return cells


def _to_students(rows, cells) -> list[SheetStudent]:
    return [
        SheetStudent(
            student_id=row.student_id,
            school_id=row.school_id,
            name=row.name,
            school=row.school_name,
            label=row.label,
            class_name=row.class_name,
            subjects=cells.get((row.student_id, row.school_id), {}),
        )
        for row in rows
    ]


def build_page(exam_id: str, scope: str, school_id: str | None, *, per_page: int, page: int = 1,
               class_name: str | None = None, query: str | None = None,
               sort_by: str | None = None, order: str = "asc"):
    """
    组合以上步骤，返回 (subjects, classes, students, pagination)。

    per_page 为 0 时不分页，单元格也不按学生过滤而是整体加载（Excel 导出）。
    sort_by 不合法时抛出 InvalidSortError。
    """
    filters = scope_filters(exam_id, scope, school_id)
    subjects = list_subjects(filters)
    classes = list_classes(filters)
    sort_labels, order_clauses = build_sort_keys(subjects, sort_by, order)
    rows, pagination = query_students_page(
        filters, class_name, query, sort_labels, order_clauses, page, per_page
    )
    student_ids = [row.student_id for row in rows] if per_page > 0 else None
    students = _to_students(rows, load_cells(filters, student_ids))
    return subjects, classes, students, pagination
