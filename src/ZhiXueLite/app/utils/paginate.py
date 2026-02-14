from sqlalchemy import func, select
from app.database import db


def paginate_query(stmt, page, per_page):
    """数据库级别分页，stmt 应已包含 where/order_by 条件"""
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery()))

    stmt = stmt.limit(per_page).offset((page - 1) * per_page)
    items = db.session.scalars(stmt).all()

    return {
        "items": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "has_prev": page > 1,
            "has_next": page * per_page < total
        },
    }
