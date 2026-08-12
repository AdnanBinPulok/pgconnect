import re
from typing import List, Union

JsonPathSegment = Union[str, int]
JsonPath = Union[str, int, List[JsonPathSegment]]

_SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_json_path_segment(segment: JsonPathSegment) -> JsonPathSegment:
    """
    Validate one JSON path segment (object key or array index).

    Usage:
        validate_json_path_segment("role")   # -> "role"
        validate_json_path_segment(0)        # -> 0
        validate_json_path_segment("a; DROP")  # raises ValueError
    """
    if isinstance(segment, bool):
        raise ValueError(f"Invalid JSON path segment: {segment!r}")

    if isinstance(segment, int):
        if segment < 0:
            raise ValueError(f"Invalid JSON path index: {segment}")
        return segment

    if isinstance(segment, str):
        if not segment or not _SAFE_KEY.match(segment):
            raise ValueError(f"Invalid JSON path key: {segment!r}")
        return segment

    raise ValueError(f"Invalid JSON path segment type: {type(segment).__name__}")


def validate_json_path(path: JsonPath) -> List[JsonPathSegment]:
    """
    Normalize and validate a JSON path into a list of safe segments.

    Usage:
        validate_json_path("role")              # -> ["role"]
        validate_json_path(["meta", "city"])    # -> ["meta", "city"]
        validate_json_path([1, "name"])         # -> [1, "name"]
        validate_json_path(0)                   # -> [0]
    """
    if isinstance(path, (str, int)) and not isinstance(path, bool):
        segments = [path]
    elif isinstance(path, list):
        if not path:
            raise ValueError("JSON path cannot be empty")
        segments = path
    else:
        raise ValueError(f"Invalid JSON path: {path!r}")

    return [validate_json_path_segment(segment) for segment in segments]


def _quote_key(key: str) -> str:
    # Keys are already whitelist-validated; quote for SQL identifier-style literals.
    return "'" + key.replace("'", "''") + "'"


def build_json_path_expr(column: str, path: JsonPath, as_text: bool = True) -> str:
    """
    Build a safe JSONB path expression for a validated column name.

    Intermediate segments use -> ; final segment uses ->> when as_text=True.

    Usage:
        build_json_path_expr("metadata", "role")
        # -> metadata->>'role'

        build_json_path_expr("metadata", ["meta", "city"])
        # -> metadata->'meta'->>'city'

        build_json_path_expr("metadata", [1, "name"])
        # -> metadata->1->>'name'

        build_json_path_expr("metadata", 0)
        # -> metadata->>0
    """
    segments = validate_json_path(path)
    expr = column

    for index, segment in enumerate(segments):
        is_last = index == len(segments) - 1
        op = "->>" if (is_last and as_text) else "->"

        if isinstance(segment, int):
            expr = f"{expr}{op}{segment}"
        else:
            expr = f"{expr}{op}{_quote_key(segment)}"

    return expr
