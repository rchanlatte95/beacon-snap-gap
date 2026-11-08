"""The QueryService engine: read-only DuckDB over the warehouse at the configured location.

Specification: contracts/query_service_contract.py, CONTRACT_QUERY_CORE (SLICE-4 batch 1):
SEQ-6, POST-SCHEMA-1, POST-SQL-1, SEQ-7, FORBIDDEN-SQL-1, ERRORS-SQL-1, ERRORS-SQL-2.
Requirements: REQ-32, REQ-33, REQ-34, REQ-46, REQ-47, REQ-49, REQ-50, REQ-52. The warehouse
layout is the data adapter's (src/warehouse/adapter.py). Runtime declarations are independent of
the contract module; tests bridge the two (CL11-F).
"""

import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import duckdb
from src.warehouse import adapter

from .ask import SourceCitation, SqlQueryResult

DEFAULT_ROW_LIMIT: Final = 200
MAX_ROW_LIMIT: Final = 1_000
DEFAULT_TIMEOUT_SECONDS: Final = 5.0
MAX_TIMEOUT_SECONDS: Final = 15.0
NOT_RECORDED: Final = "not recorded"
KEY_GRAINS: Final[Mapping[str, str]] = {
    "geoid20": "block",
    "block_geoid": "block",
    "geoid": "tract",
    "geo_id": "tract",
    "tractfips": "tract",
    "censustract20": "tract",
    "censustract": "tract",
    "tract_geoid": "tract",
    "stcofips": "county",
    "countyfips": "county",
    "county_fips": "county",
    "county": "county",
    "statefips": "state",
    "state_fips": "state",
    "state": "state",
    "borrstate": "state",
}
GRAIN_ORDER: Final[tuple[str, ...]] = ("block", "tract", "county", "state")
_STRING_LITERAL_RE: Final = re.compile(r"'([^']|'')*'")
_FROM_JOIN_RE: Final = re.compile(
    r"\b(?:FROM|JOIN)\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?", re.IGNORECASE
)


class QueryServiceError(Exception):
    """Base of the engine's errors."""


class UnconnectedWarehouseError(QueryServiceError):
    """SEQ-6: a tool call was made before open()."""


class RejectedSqlError(QueryServiceError):
    """ERRORS-SQL-1 / FORBIDDEN-SQL-1: the statement or its limits are refused."""


class QueryTimeoutError(QueryServiceError):
    """ERRORS-SQL-2: the query ran past its time limit and was interrupted."""


@dataclass(frozen=True, slots=True)
class TableSchemaDescription:
    """One warehouse table as the schema tool describes it (REQ-33)."""

    table_name: str
    dataset_id: str
    columns: tuple[str, ...]
    grain: str
    join_keys: tuple[str, ...]
    as_of: str
    applied_filter: str
    glossary_terms: tuple[tuple[str, str], ...]


def grain_and_keys(columns: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """Join keys are the geographic key columns; the grain is the most specific level among them."""
    keys = tuple(c for c in columns if c.lower() in KEY_GRAINS)
    levels = {KEY_GRAINS[k.lower()] for k in keys}
    return next((g for g in GRAIN_ORDER if g in levels), NOT_RECORDED), keys


def referenced_tables(sql: str, known: frozenset[str]) -> tuple[str, ...]:
    """Known table names after FROM or JOIN, in query order, ignoring string literals."""
    found: list[str] = []
    for match in _FROM_JOIN_RE.finditer(_STRING_LITERAL_RE.sub("''", sql)):
        name = match.group(1)
        if name in known and name not in found:
            found.append(name)
    return tuple(found)


def _sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class WarehouseQueryEngine:
    """Answers schema and SELECT tool calls over one read-only warehouse."""

    def __init__(self, env: Mapping[str, str]) -> None:
        self._env = dict(env)
        self._con: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.Lock()
        self._tables: tuple[str, ...] = ()
        self._catalog: dict[str, str] = {}
        self._by_source: dict[str, str] = {}
        self._columns: dict[str, tuple[str, ...]] = {}
        self._citations: dict[str, SourceCitation] = {}
        self._glossary: dict[str, tuple[tuple[str, str], ...]] = {}

    def open(self) -> None:
        """Open the warehouse read-only and lock file access to its location (SEQ-6).

        Raises:
            WarehouseLocationError: from the adapter, when the location is missing or invalid.
        """
        location = adapter.require_warehouse(adapter.warehouse_location(self._env))
        con = duckdb.connect(str(Path(location.root) / adapter.WAREHOUSE_DB_FILE), read_only=True)
        catalog = con.execute(
            "SELECT table_name, parquet, dataset_id, source_file FROM catalog ORDER BY rowid"
        ).fetchall()
        for name, relative, _, _ in catalog:
            path = adapter.table_path(location, name, relative)
            # name passed the adapter's table-name pattern; the path is quoted as a literal.
            con.execute(
                f'CREATE TEMP VIEW "{name}" AS SELECT * FROM read_parquet({_sql_text(path)})'  # noqa: S608
            )
        self._tables = tuple(str(r[0]) for r in catalog)
        self._by_source = {str(r[3]): str(r[0]) for r in catalog}
        self._catalog = {str(r[0]): str(r[2]) for r in catalog}
        columns: dict[str, list[tuple[int, str]]] = {}
        for table, column, ordinal in con.execute(
            "SELECT table_name, column_name, ordinal FROM columns"
        ).fetchall():
            columns.setdefault(str(table), []).append((int(ordinal), str(column)))
        self._columns = {t: tuple(c for _, c in sorted(cs)) for t, cs in columns.items()}
        self._citations = {
            str(r[0]): SourceCitation(*(str(v) for v in r))
            for r in con.execute(
                "SELECT table_name, dataset_id, origin_url, publisher, as_of, applied_filter "
                "FROM sources"
            ).fetchall()
        }
        glossary: dict[str, list[tuple[str, str]]] = {}
        for table, term, definition in con.execute(
            "SELECT source_table, term, definition FROM glossary ORDER BY rowid"
        ).fetchall():
            glossary.setdefault(str(table), []).append((str(term), str(definition)))
        self._glossary = {t: tuple(g) for t, g in glossary.items()}
        root = location.root.rstrip("/") + "/"
        con.execute(f"SET allowed_directories = [{_sql_text(root)}]")
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
        self._con = con

    def _connection(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            raise UnconnectedWarehouseError("SEQ-6 violation: the warehouse is not open")
        return self._con

    @property
    def table_names(self) -> tuple[str, ...]:
        """The catalog's tables, in catalog order."""
        self._connection()
        return self._tables

    def table_for_source(self, source_file: str) -> str:
        """The catalog table loaded from a registry path (POST-BASE-1 source_file).

        Raises:
            UnconnectedWarehouseError: SEQ-6, before open().
            RejectedSqlError: ERRORS-SQL-1, no catalog table came from that file.
        """
        self._connection()
        name = self._by_source.get(source_file)
        if name is None:
            raise RejectedSqlError(
                f"ERRORS-SQL-1 violation: no warehouse table from {source_file!r}"
            )
        return name

    def describe_schema(
        self, table_names: tuple[str, ...] | None = None
    ) -> tuple[TableSchemaDescription, ...]:
        """Describe catalog tables (POST-SCHEMA-1).

        Raises:
            UnconnectedWarehouseError: SEQ-6, before open().
            RejectedSqlError: ERRORS-SQL-1, an unknown table name.
        """
        self._connection()
        names = self._tables if table_names is None else table_names
        unknown = [n for n in names if n not in self._catalog]
        if unknown:
            raise RejectedSqlError(f"ERRORS-SQL-1 violation: unknown tables {unknown}")
        out: list[TableSchemaDescription] = []
        for name in names:
            cols = self._columns.get(name, ())
            grain, keys = grain_and_keys(cols)
            cite = self._citations.get(name)
            out.append(
                TableSchemaDescription(
                    table_name=name,
                    dataset_id=self._catalog[name],
                    columns=cols,
                    grain=grain,
                    join_keys=keys,
                    as_of=cite.as_of if cite else NOT_RECORDED,
                    applied_filter=cite.applied_filter if cite else NOT_RECORDED,
                    glossary_terms=self._glossary.get(name, ()),
                )
            )
        return tuple(out)

    def execute_sql(
        self,
        sql: str,
        row_limit: int = DEFAULT_ROW_LIMIT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> SqlQueryResult:
        """Run exactly one SELECT within limits and cite its tables (POST-SQL-1, SEQ-7).

        Raises:
            UnconnectedWarehouseError: SEQ-6, before open().
            RejectedSqlError: ERRORS-SQL-1 / FORBIDDEN-SQL-1, a refused statement or limit.
            QueryTimeoutError: ERRORS-SQL-2, the time limit was reached.
        """
        con = self._connection()
        if not 1 <= row_limit <= MAX_ROW_LIMIT:
            raise RejectedSqlError(
                f"ERRORS-SQL-1 violation: row_limit {row_limit} is outside 1..{MAX_ROW_LIMIT}"
            )
        if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise RejectedSqlError(
                f"ERRORS-SQL-1 violation: timeout_seconds {timeout_seconds} is outside "
                f"(0, {MAX_TIMEOUT_SECONDS}]"
            )
        if not sql.strip():
            raise RejectedSqlError("ERRORS-SQL-1 violation: the statement is empty")
        with self._lock:
            try:
                statements = con.extract_statements(sql)
            except duckdb.Error as exc:
                raise RejectedSqlError(f"ERRORS-SQL-1 violation: unparsable SQL: {exc}") from exc
            kinds = [s.type for s in statements]
            if kinds != [duckdb.StatementType.SELECT]:
                raise RejectedSqlError(
                    f"FORBIDDEN-SQL-1 violation: only one SELECT is allowed, got "
                    f"{[str(k).rsplit('.', 1)[-1] for k in kinds]}"
                )
            timed_out = threading.Event()

            def _stop() -> None:
                timed_out.set()
                con.interrupt()

            timer = threading.Timer(timeout_seconds, _stop)
            timer.start()
            try:
                cursor = con.execute(sql)
                names = tuple(d[0] for d in cursor.description or ())
                fetched = cursor.fetchmany(row_limit + 1)
            except duckdb.InterruptException as exc:
                raise QueryTimeoutError(
                    f"ERRORS-SQL-2 violation: the query passed {timeout_seconds} s and was stopped"
                ) from exc
            except duckdb.Error as exc:
                if timed_out.is_set():
                    raise QueryTimeoutError(
                        f"ERRORS-SQL-2 violation: the query passed {timeout_seconds} s and was "
                        "stopped"
                    ) from exc
                raise RejectedSqlError(f"ERRORS-SQL-1 violation: DuckDB refused it: {exc}") from exc
            finally:
                timer.cancel()
        rows = tuple(dict(zip(names, r, strict=True)) for r in fetched[:row_limit])
        used = referenced_tables(sql, frozenset(self._tables))
        return SqlQueryResult(
            columns=names,
            rows=rows,
            row_count=len(rows),
            truncated=len(fetched) > row_limit,
            referenced_tables=used,
            citations=tuple(self._citations[t] for t in used if t in self._citations),
        )
