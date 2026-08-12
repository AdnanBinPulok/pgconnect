import json
import pytest
import pgconnect
from pgconnect.Filters import Filters
from pgconnect.jsonb_path import (
    validate_json_path_segment,
    validate_json_path,
    build_json_path_expr,
)


def test_build_json_path_expr_dict_and_list():
    assert build_json_path_expr("metadata", "role") == "metadata->>'role'"
    assert build_json_path_expr("metadata", ["meta", "city"]) == "metadata->'meta'->>'city'"
    assert build_json_path_expr("metadata", 0) == "metadata->>0"
    assert build_json_path_expr("metadata", [1, "name"]) == "metadata->1->>'name'"
    assert build_json_path_expr("metadata", "active", as_text=False) == "metadata->'active'"


@pytest.mark.parametrize("payload", [
    "role'; DROP TABLE users--",
    "role' OR '1'='1",
    "meta->city",
    "",
    "has-dash",
    "has space",
])
def test_validate_json_path_rejects_injection_keys(payload):
    with pytest.raises(ValueError, match="Invalid JSON path"):
        validate_json_path_segment(payload)


@pytest.mark.parametrize("payload", [-1, True, False, 1.5, None, ["role"]])
def test_validate_json_path_rejects_bad_segments(payload):
    with pytest.raises(ValueError):
        validate_json_path_segment(payload)


def test_validate_json_path_rejects_empty_list():
    with pytest.raises(ValueError, match="empty"):
        validate_json_path([])


def test_json_equal_parameterizes_value():
    params = []
    sql = Filters.Json("role", Filters.Equal("admin'; DROP--")).to_sql("metadata", params)
    assert sql == "metadata->>'role' = $1"
    assert params == ["admin'; DROP--"]


def test_json_nested_path_and_numeric():
    params = []
    sql = Filters.Json(["meta", "city"], Filters.Equal("Dhaka")).to_sql("metadata", params)
    assert sql == "metadata->'meta'->>'city' = $1"
    assert params == ["Dhaka"]

    params = []
    sql = Filters.Json("score", Filters.GreaterThan(10)).to_sql("metadata", params)
    assert sql == "(metadata->>'score')::numeric > $1"
    assert params == [10]


def test_json_array_index_path():
    params = []
    sql = Filters.Json(0, Filters.Equal("admin")).to_sql("metadata", params)
    assert sql == "metadata->>0 = $1"
    assert params == ["admin"]

    params = []
    sql = Filters.Json([1, "name"], Filters.Equal("b")).to_sql("metadata", params)
    assert sql == "metadata->1->>'name' = $1"
    assert params == ["b"]


def test_json_rejects_injection_path():
    with pytest.raises(ValueError):
        Filters.Json("role'; DROP--", Filters.Equal("x")).to_sql("metadata", [])


def test_json_contains_dict_and_list():
    params = []
    sql = Filters.JsonContains({"role": "admin"}).to_sql("metadata", params)
    assert sql == "metadata @> $1::jsonb"
    assert params == [json.dumps({"role": "admin"})]

    params = []
    sql = Filters.JsonContains(["admin"]).to_sql("metadata", params)
    assert sql == "metadata @> $1::jsonb"
    assert params == [json.dumps(["admin"])]


def test_json_has_key_ops_parameterize_keys():
    params = []
    sql = Filters.JsonHasKey("role'; DROP--").to_sql("metadata", params)
    assert sql == "metadata ? $1"
    assert params == ["role'; DROP--"]

    params = []
    sql = Filters.JsonHasAnyKey(["role", "email"]).to_sql("metadata", params)
    assert sql == "metadata ?| $1::text[]"
    assert params == [["role", "email"]]

    params = []
    sql = Filters.JsonHasAllKeys(["role", "score"]).to_sql("metadata", params)
    assert sql == "metadata ?& $1::text[]"
    assert params == [["role", "score"]]


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
            pgconnect.Column(name="metadata", type=pgconnect.DataType.JSONB()),
        ],
    )


@pytest.mark.asyncio
async def test_build_where_clause_accepts_json_filters():
    table = _make_table()
    where_clause, params = await table._build_where_clause({
        "metadata": Filters.Json("role", Filters.Equal("admin")),
    })
    assert where_clause == "metadata->>'role' = $1"
    assert params == ["admin"]


@pytest.mark.asyncio
async def test_build_where_clause_rejects_invalid_column_with_json_filter():
    table = _make_table()
    with pytest.raises(ValueError, match="Invalid column"):
        await table._build_where_clause({
            "not_a_column": Filters.JsonContains({"a": 1}),
        })
