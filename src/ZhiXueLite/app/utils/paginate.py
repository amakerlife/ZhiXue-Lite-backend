def paginate(items, page, per_page):
    if not isinstance(items, list):
        raise ValueError("Items must be a list.")

    if page < 1 or per_page < 1:
        raise ValueError("Page and per_page must be greater than 0.")

    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = items[start:end]

    return paginated_items, len(items), end


def paginated_json(items, page, per_page):
    """将数据转换为分页的 JSON 格式"""
    paginated_items, total, end = paginate(items, page, per_page)
    return {
        "items": paginated_items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "has_prev": page > 1,
            "has_next": end < total
        },
    }
