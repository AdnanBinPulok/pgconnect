import pytest
import pgconnect
from pgconnect.sql_safe import (
    validate_column,
    validate_columns,
    validate_order,
    validate_pagination,
    DEFAULT_MAX_LIMIT,
)


ALLOWED = {"id", "name", "email"}


@pytest.mark.parametrize("payload", [
    "id OR 1=1--",
    "id; DROP TABLE users--",
    "(SELECT password FROM admin)",
])
def test_validate_column_rejects_injection(payload):
    with pytest.raises(ValueError, match="Invalid column"):
        validate_column(payload, ALLOWED)


def test_validate_columns_rejects_invalid_entry():
    with pytest.raises(ValueError, match="Invalid column"):
        validate_columns(["name", "name) OR 1=1--"], ALLOWED)


@pytest.mark.parametrize("payload", [
    "ASC; DELETE FROM users--",
    "DESC; DROP TABLE users--",
    "INVALID",
])
def test_validate_order_rejects_injection(payload):
    with pytest.raises(ValueError, match="order must be ASC or DESC"):
        validate_order(payload)


def test_validate_order_accepts_asc_desc():
    assert validate_order("asc") == "ASC"
    assert validate_order("desc") == "DESC"


def test_validate_pagination_rejects_invalid_values():
    with pytest.raises(ValueError, match="page must be >= 1"):
        validate_pagination(0, 10)
    with pytest.raises(ValueError, match="limit must be >= 1"):
        validate_pagination(1, 0)
    with pytest.raises(ValueError, match=f"limit must be <= {DEFAULT_MAX_LIMIT}"):
        validate_pagination(1, DEFAULT_MAX_LIMIT + 1)


def test_validate_pagination_coerces_numeric_strings():
    page, limit = validate_pagination("2", "25")
    assert page == 2
    assert limit == 25


def _make_table():
    return pgconnect.Table(
        name="users",
        connection=pgconnect.Connection(
            host="localhost",
            port=5432,
            user="user",
            password="pass",
            database="db",
        ),
        columns=[
            pgconnect.Column(name="id", type=pgconnect.DataType.SERIAL().primary_key()),
            pgconnect.Column(name="name", type=pgconnect.DataType.VARCHAR()),
            pgconnect.Column(name="email", type=pgconnect.DataType.VARCHAR()),
        ],
    )


@pytest.mark.asyncio
async def test_build_where_clause_rejects_malicious_keys():
    table = _make_table()
    with pytest.raises(ValueError, match="Invalid column"):
        await table._build_where_clause({"id OR 1=1--": 1})


@pytest.mark.asyncio
async def test_select_rejects_malicious_columns():
    table = _make_table()
    with pytest.raises(ValueError, match="Invalid column"):
        await table.select("(SELECT 1)", id=1)


@pytest.mark.asyncio
async def test_get_page_rejects_malicious_order_by():
    table = _make_table()
    with pytest.raises(ValueError, match="Invalid column"):
        await table.get_page(1, 10, order_by="id; DROP TABLE users--")


@pytest.mark.asyncio
async def test_get_page_rejects_malicious_order():
    table = _make_table()
    with pytest.raises(ValueError, match="order must be ASC or DESC"):
        await table.get_page(1, 10, order_by="id", order="ASC; DELETE FROM users--")


@pytest.mark.asyncio
async def test_search_rejects_malicious_by_columns():
    table = _make_table()
    with pytest.raises(ValueError, match="Invalid column"):
        await table.search(by=["name) OR 1=1--"], keyword="anything")


@pytest.mark.asyncio
async def test_count_search_rejects_malicious_by_columns():
    table = _make_table()
    with pytest.raises(ValueError, match="Invalid column"):
        await table.count_search(by=["name) OR 1=1--"], keyword="anything")
