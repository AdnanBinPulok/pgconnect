from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional, Union
import json

from .jsonb_path import JsonPath, build_json_path_expr


@dataclass
class Between:
    from_value: Optional[Any] = None
    to_value: Optional[Any] = None
    
    def to_sql(self, field_name: str, params: list) -> str:
        if self.from_value is not None and self.to_value is not None:
            params.extend([self.from_value, self.to_value])
            return f"{field_name} BETWEEN ${len(params)-1} AND ${len(params)}"
        elif self.from_value is not None:
            params.append(self.from_value)
            return f"{field_name} >= ${len(params)}"
        elif self.to_value is not None:
            params.append(self.to_value)
            return f"{field_name} <= ${len(params)}"
        raise ValueError("Either from_value or to_value must be provided")

@dataclass
class Like:
    pattern: str
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(f"%{self.pattern}%")
        return f"{field_name} ILIKE ${len(params)}"

@dataclass
class In:
    values: list
    
    def __post_init__(self):
        # Convert to list and remove duplicates
        self.values = list(dict.fromkeys(self.values))
        
        # Convert string numbers to integers
        if all(str(v).isdigit() for v in self.values):
            self.values = [int(v) for v in self.values]
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.extend(self.values)
        placeholders = [f"${len(params)-len(self.values)+i+1}" for i in range(len(self.values))]
        
        if all(isinstance(v, int) for v in self.values):
            # Cast both the field and array elements to INTEGER for comparison
            return f"CAST({field_name} AS INTEGER) IN (SELECT UNNEST(ARRAY[{','.join(placeholders)}]::INTEGER[]))"
        else:
            return f"{field_name} IN ({','.join(placeholders)})"

@dataclass
class Increment:
    value: Union[int, float]
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(self.value)
        return f"{field_name} + ${len(params)}"

@dataclass
class Decrement:
    value: Union[int, float]
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(self.value)
        return f"{field_name} - ${len(params)}"
    

@dataclass
class Equal:
    value: Any
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(self.value)
        return f"{field_name} = ${len(params)}"
    

@dataclass
class NotEqual:
    value: Any
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(self.value)
        return f"{field_name} != ${len(params)}"
    

@dataclass
class GreaterThan:
    value: Any
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(self.value)
        return f"{field_name} > ${len(params)}"
    
@dataclass
class LessThan:
    value: Any
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.append(self.value)
        return f"{field_name} < ${len(params)}"
    

@dataclass
class NotIn:
    values: list
    
    def __post_init__(self):
        # Convert to list and remove duplicates
        self.values = list(dict.fromkeys(self.values))
        
        # Convert string numbers to integers
        if all(str(v).isdigit() for v in self.values):
            self.values = [int(v) for v in self.values]
    
    def to_sql(self, field_name: str, params: list) -> str:
        params.extend(self.values)
        placeholders = [f"${len(params)-len(self.values)+i+1}" for i in range(len(self.values))]
        
        if all(isinstance(v, int) for v in self.values):
            # Cast both the field and array elements to INTEGER for comparison
            return f"CAST({field_name} AS INTEGER) NOT IN (SELECT UNNEST(ARRAY[{','.join(placeholders)}]::INTEGER[]))"
        else:
            return f"{field_name} NOT IN ({','.join(placeholders)})"

@dataclass
class IsNull:
    def to_sql(self, field_name: str, params: list) -> str:
        return f"{field_name} IS NULL"
    
@dataclass
class IsNotNull:
    def to_sql(self, field_name: str, params: list) -> str:
        return f"{field_name} IS NOT NULL"

@dataclass
class IsTrue:
    def to_sql(self, field_name: str, params: list) -> str:
        return f"{field_name} IS TRUE"
    
@dataclass
class IsFalse:
    def to_sql(self, field_name: str, params: list) -> str:
        return f"{field_name} IS FALSE"


_JSON_NESTED_OPS = (
    Between, Like, In, Equal, NotEqual, GreaterThan, LessThan, NotIn,
    IsNull, IsNotNull, IsTrue, IsFalse,
)
_JSON_NUMERIC_OPS = (GreaterThan, LessThan, Between)


@dataclass
class Json:
    """
    Filter a JSONB column by path using another Filters operator.

    Usage:
        await table.get(metadata=Filters.Json("role", Filters.Equal("admin")))
        # → metadata->>'role' = $1

        await table.get(metadata=Filters.Json(["meta", "city"], Filters.Equal("Dhaka")))
        # → metadata->'meta'->>'city' = $1

        await table.get(metadata=Filters.Json(0, Filters.Equal("admin")))
        # → metadata->>0 = $1

        await table.get(metadata=Filters.Json([1, "name"], Filters.Equal("b")))
        # → metadata->1->>'name' = $1

        await table.get(metadata=Filters.Json("score", Filters.GreaterThan(10)))
        # → (metadata->>'score')::numeric > $1
    """
    path: JsonPath
    op: Any

    def to_sql(self, field_name: str, params: list) -> str:
        if not isinstance(self.op, _JSON_NESTED_OPS):
            raise ValueError(f"Unsupported JSON filter operator: {type(self.op).__name__}")

        as_text = not isinstance(self.op, (IsTrue, IsFalse))
        expr = build_json_path_expr(field_name, self.path, as_text=as_text)

        if isinstance(self.op, _JSON_NUMERIC_OPS):
            expr = f"({expr})::numeric"

        return self.op.to_sql(expr, params)


@dataclass
class JsonContains:
    """
    JSONB containment filter using @>.

    Usage:
        # dict / object
        await table.get(metadata=Filters.JsonContains({"role": "admin"}))
        # → metadata @> $1::jsonb

        # list / array
        await table.get(metadata=Filters.JsonContains(["admin"]))
        # → metadata @> $1::jsonb
    """
    value: Any

    def to_sql(self, field_name: str, params: list) -> str:
        params.append(json.dumps(self.value))
        return f"{field_name} @> ${len(params)}::jsonb"


@dataclass
class JsonHasKey:
    """
    Check whether a JSONB object has a key using ?.

    Usage:
        await table.get(metadata=Filters.JsonHasKey("role"))
        # → metadata ? $1
    """
    key: str

    def to_sql(self, field_name: str, params: list) -> str:
        if not isinstance(self.key, str) or self.key == "":
            raise ValueError(f"Invalid JSON key: {self.key!r}")
        params.append(self.key)
        return f"{field_name} ? ${len(params)}"


@dataclass
class JsonHasAnyKey:
    """
    Check whether a JSONB object has any of the given keys using ?|.

    Usage:
        await table.get(metadata=Filters.JsonHasAnyKey(["role", "email"]))
        # → metadata ?| $1::text[]
    """
    keys: List[str]

    def to_sql(self, field_name: str, params: list) -> str:
        if not self.keys or not all(isinstance(k, str) and k for k in self.keys):
            raise ValueError("JsonHasAnyKey requires a non-empty list of non-empty strings")
        params.append(list(self.keys))
        return f"{field_name} ?| ${len(params)}::text[]"


@dataclass
class JsonHasAllKeys:
    """
    Check whether a JSONB object has all of the given keys using ?&.

    Usage:
        await table.get(metadata=Filters.JsonHasAllKeys(["role", "score"]))
        # → metadata ?& $1::text[]
    """
    keys: List[str]

    def to_sql(self, field_name: str, params: list) -> str:
        if not self.keys or not all(isinstance(k, str) and k for k in self.keys):
            raise ValueError("JsonHasAllKeys requires a non-empty list of non-empty strings")
        params.append(list(self.keys))
        return f"{field_name} ?& ${len(params)}::text[]"


class Filters:
    @staticmethod
    def Between(from_value: Any = None, to_value: Any = None) -> Between:
        if from_value is None and to_value is None:
            raise ValueError("Either from_value or to_value must be provided")
        return Between(from_value, to_value)
    
    @staticmethod
    def Like(pattern: str) -> Like:
        return Like(pattern)
    
    @staticmethod
    def In(values: list) -> In:
        return In(values)
    
    @staticmethod
    def Increment(value: Union[int, float]) -> Increment:
        return Increment(value)
    
    @staticmethod
    def Decrement(value: Union[int, float]) -> Decrement:
        return Decrement(value)
    
    @staticmethod
    def Equal(value: Any) -> Equal:
        return Equal(value)
    
    @staticmethod
    def NotEqual(value: Any) -> NotEqual:
        return NotEqual(value)
    
    @staticmethod
    def GreaterThan(value: Any) -> GreaterThan:
        return GreaterThan(value)
    
    @staticmethod
    def LessThan(value: Any) -> LessThan:
        return LessThan(value)
    
    @staticmethod
    def NotIn(values: list) -> NotIn:
        return NotIn(values)

    @staticmethod
    def IsNull() -> IsNull:
        return IsNull()
    
    @staticmethod
    def IsNotNull() -> IsNotNull:
        return IsNotNull()
    
    @staticmethod
    def IsTrue() -> IsTrue:
        return IsTrue()
    
    @staticmethod
    def IsFalse() -> IsFalse:
        return IsFalse()

    @staticmethod
    def Json(path: JsonPath, op: Any) -> Json:
        """
        Filter a JSONB column by path using another Filters operator.

        Usage:
            await table.get(metadata=Filters.Json("role", Filters.Equal("admin")))
            await table.get(metadata=Filters.Json(["meta", "city"], Filters.Equal("Dhaka")))
            await table.get(metadata=Filters.Json(0, Filters.Equal("admin")))
            await table.get(metadata=Filters.Json([1, "name"], Filters.Equal("b")))
            await table.get(metadata=Filters.Json("score", Filters.GreaterThan(10)))
        """
        return Json(path, op)

    @staticmethod
    def JsonContains(value: Any) -> JsonContains:
        """
        JSONB containment filter using @>.

        Usage:
            await table.get(metadata=Filters.JsonContains({"role": "admin"}))
            await table.get(metadata=Filters.JsonContains(["admin"]))
        """
        return JsonContains(value)

    @staticmethod
    def JsonHasKey(key: str) -> JsonHasKey:
        """
        Check whether a JSONB object has a key using ?.

        Usage:
            await table.get(metadata=Filters.JsonHasKey("role"))
        """
        return JsonHasKey(key)

    @staticmethod
    def JsonHasAnyKey(keys: List[str]) -> JsonHasAnyKey:
        """
        Check whether a JSONB object has any of the given keys using ?|.

        Usage:
            await table.get(metadata=Filters.JsonHasAnyKey(["role", "email"]))
        """
        return JsonHasAnyKey(keys)

    @staticmethod
    def JsonHasAllKeys(keys: List[str]) -> JsonHasAllKeys:
        """
        Check whether a JSONB object has all of the given keys using ?&.

        Usage:
            await table.get(metadata=Filters.JsonHasAllKeys(["role", "score"]))
        """
        return JsonHasAllKeys(keys)
