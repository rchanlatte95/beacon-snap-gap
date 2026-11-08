"""Structured sources: JSON files as tables and geographic files as DuckDB relations.

Specification: contracts/warehouse_contract.py, CONTRACT_DOCUMENTS (SLICE-3 batch 6c-iii).
Requirements: REQ-25, REQ-28. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import duckdb

from .reader import SourceReadError, whole_file_encoding

JSON_ROOT_KEY: Final = ""
JSON_BLOB_COLUMN: Final = "json"
GEO_EXTENSION: Final = "spatial"
GEO_ROW_ID_COLUMN: Final = "OGC_FID"
GEO_GEOMETRY_COLUMN: Final = "geom"

__all__ = [
    "GEO_EXTENSION",
    "GEO_GEOMETRY_COLUMN",
    "GEO_ROW_ID_COLUMN",
    "JSON_BLOB_COLUMN",
    "JSON_ROOT_KEY",
    "JsonTable",
    "SourceReadError",
    "read_geo",
    "read_json_tables",
]


@dataclass(frozen=True)
class JsonTable:
    """One table read from a JSON file; every cell is text or None (POST-READ-4)."""

    key: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]


def _cell(raw: object, std: object) -> str | None:
    """A scalar as written in the file, a nested value as compact JSON, null as None."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "true" if raw else "false"
    if isinstance(raw, str):
        return raw
    return json.dumps(std, ensure_ascii=False, separators=(",", ":"))


def _is_table(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _table(
    key: str, raw_rows: list[dict[str, object]], std_rows: list[dict[str, object]]
) -> JsonTable:
    columns: list[str] = []
    for row in raw_rows:
        columns.extend(k for k in row if k not in columns)
    return JsonTable(
        key=key,
        columns=tuple(columns),
        rows=tuple(
            tuple(_cell(r.get(c), s.get(c)) for c in columns)
            for r, s in zip(raw_rows, std_rows, strict=True)
        ),
    )


def read_json_tables(path: Path) -> tuple[JsonTable, ...]:
    """Read a JSON file into tables without dropping an entry or rewriting a value (POST-READ-4).

    Numbers keep their written text through the standard parser's parse_float and parse_int
    hooks; a second, ordinary parse supplies nested values for compact JSON text.

    Raises:
        SourceReadError: ERRORS-READ-3, the file is missing, undecodable or not valid JSON.
    """
    encoding = whole_file_encoding(path)
    text = path.read_text(encoding=encoding)
    try:
        raw = json.loads(text, parse_float=str, parse_int=str, parse_constant=str)
        std = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceReadError(
            f"ERRORS-READ-3 violation: {str(path)!r} is not valid JSON: {exc}"
        ) from exc
    if _is_table(raw):
        return (_table(JSON_ROOT_KEY, raw, std),)
    if isinstance(raw, dict):
        tables = [_table(k, raw[k], std[k]) for k in raw if _is_table(raw[k])]
        rest = [k for k in raw if not _is_table(raw[k])]
        if rest:
            tables.append(
                JsonTable(
                    key=JSON_ROOT_KEY,
                    columns=tuple(rest),
                    rows=(tuple(_cell(raw[k], std[k]) for k in rest),),
                )
            )
        return tuple(tables)
    return (JsonTable(key=JSON_ROOT_KEY, columns=(JSON_BLOB_COLUMN,), rows=((text,),)),)


def read_geo(con: duckdb.DuckDBPyConnection, source: str) -> duckdb.DuckDBPyRelation:
    """Read every feature of a geographic file or /vsizip/ member path (POST-READ-5).

    Attribute columns are cast to VARCHAR, the geometry keeps its GEOMETRY type, and the GDAL
    row id is left out. Columns are selected through DuckDB's expression API, so no source
    column name is ever spliced into SQL text.

    Raises:
        SourceReadError: ERRORS-READ-4, the spatial extension cannot be loaded or GDAL cannot
            open the source; the message names the source.
    """
    try:
        con.load_extension(GEO_EXTENSION)
        relation = con.sql("SELECT * FROM ST_Read($source)", params={"source": source})
        varchar = duckdb.sqltype("VARCHAR")
        projected = relation.project(
            *(
                duckdb.ColumnExpression(name)
                if name == GEO_GEOMETRY_COLUMN
                else duckdb.ColumnExpression(name).cast(varchar).alias(name)
                for name in relation.columns
                if name != GEO_ROW_ID_COLUMN
            )
        )
        projected.aggregate("count(*)").fetchall()
    except duckdb.Error as exc:
        raise SourceReadError(
            f"ERRORS-READ-4 violation: {source!r} could not be read with {GEO_EXTENSION}: {exc}"
        ) from exc
    return projected
