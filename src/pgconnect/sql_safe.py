def validate_column(name: str, allowed: set[str]) -> str:
    if name not in allowed:
        raise ValueError(f"Invalid column: {name}")
    return name


def validate_columns(names: list[str], allowed: set[str]) -> list[str]:
    return [validate_column(name, allowed) for name in names]


def validate_order(direction: str) -> str:
    order = direction.upper()
    if order not in ("ASC", "DESC"):
        raise ValueError("order must be ASC or DESC")
    return order


def validate_pagination(page: int, limit: int, max_limit: int) -> tuple[int, int]:
    page = int(page)
    limit = int(limit)

    if page < 1:
        raise ValueError("page must be >= 1")
    if limit < 1:
        raise ValueError("limit must be >= 1")
    if limit > max_limit:
        raise ValueError(f"limit must be <= {max_limit}")

    return page, limit
