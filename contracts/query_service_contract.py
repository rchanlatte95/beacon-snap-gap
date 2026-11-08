"""QueryService contract, SLICE-4.

Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 13, REQ-32 to REQ-40, REQ-46; SEQ-6, SEQ-7,
SEQ-9, SEQ-10).

Domain: the QueryService and its AI tool/citation boundary over the canonical warehouse in
gs://<warehouse-bucket>. The Ingest has its own contract (contracts/warehouse_contract.py,
SLICE-3).

Batches:
- Batch 1: connect to the warehouse from the bucket without rebuilding it (REQ-46, SEQ-6),
  schema.describe (REQ-33), read-only sql.query with row/time limits (REQ-34), and attach
  SourceCitation provenance for every table used (REQ-32, SEQ-7).
- Later batches: sites.near and stats.correlate (REQ-35), core taxonomy attachment and Vertex AI
  Gemini tool-grounded answers (REQ-36, REQ-37, REQ-38, SEQ-10), and App citation chips and
  built-in wizard fallback on outage (REQ-39, REQ-40, SEQ-9).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

# --- 1. Importable constants (specification values) --------------------------------------

WAREHOUSE_GCP_PROJECT = "<gcp-project>"
WAREHOUSE_GCS_BUCKET = "<warehouse-bucket>"
WAREHOUSE_GCS_URI = f"gs://{WAREHOUSE_GCS_BUCKET}"

DEFAULT_ROW_LIMIT = 200
MAX_ROW_LIMIT = 1_000
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 15.0

FORBIDDEN_SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "ATTACH",
        "DETACH",
        "COPY",
        "EXPORT",
        "IMPORT",
        "PRAGMA",
        "INSTALL",
        "LOAD",
        "CALL",
        "SET",
        "VACUUM",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "GRANT",
        "REVOKE",
    }
)

_WORD_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_STRING_LITERAL_RE = re.compile(r"'([^']|'')*'")
_FROM_JOIN_RE = re.compile(r"\b(?:FROM|JOIN)\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?", re.IGNORECASE)


# --- 2. Domain exceptions (every message names its clause) --------------------------------


class QueryServiceContractError(Exception):
    """Base of every violation raised by this contract."""


class RejectedSqlError(QueryServiceContractError):
    """ERRORS-SQL-1 or FORBIDDEN-SQL-1: statement is not a single read-only SELECT within limits."""


class UnconnectedWarehouseError(QueryServiceContractError):
    """SEQ-6: a query or tool call was attempted before connecting to the bucket warehouse."""


class QueryServiceViolationError(QueryServiceContractError):
    """POST-SCHEMA-1, POST-SQL-1, SEQ-6, SEQ-7 or FORBIDDEN-SQL-1: output disagrees with rule."""


# --- 3. Immutable typed records ------------------------------------------------------------


@dataclass(frozen=True)
class Clause:
    verification: Literal["test", "execution", "tool"]
    text: str
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class SourceCitation:
    """REQ-32 / SEQ-7 citation attached for each warehouse table used by a tool call."""

    table_name: str
    dataset_id: str
    origin_url: str
    publisher: str
    as_of: str
    applied_filter: str


@dataclass(frozen=True)
class TableSchemaDescription:
    """REQ-33 schema.describe entry for one warehouse table."""

    table_name: str
    dataset_id: str
    columns: tuple[str, ...]
    grain: str
    join_keys: tuple[str, ...]
    as_of: str
    applied_filter: str
    glossary_terms: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SqlQueryResult:
    """REQ-34 / REQ-32 result of a read-only SELECT query with attached table citations."""

    columns: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]
    row_count: int
    truncated: bool
    referenced_tables: tuple[str, ...]
    citations: tuple[SourceCitation, ...]


# --- 4. Callable validators ----------------------------------------------------------------


def validate_readonly_sql(
    sql: str,
    *,
    row_limit: int = DEFAULT_ROW_LIMIT,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """ERRORS-SQL-1 / FORBIDDEN-SQL-1 gate: accept a single read-only SELECT within bounds."""
    if row_limit < 1 or row_limit > MAX_ROW_LIMIT:
        raise RejectedSqlError(
            f"ERRORS-SQL-1 violation: row_limit {row_limit} is outside 1..{MAX_ROW_LIMIT}"
        )
    if timeout_seconds <= 0 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise RejectedSqlError(
            f"ERRORS-SQL-1 violation: timeout_seconds {timeout_seconds} is outside "
            f"(0, {MAX_TIMEOUT_SECONDS}]"
        )
    cleaned = sql.strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if not cleaned:
        raise RejectedSqlError("ERRORS-SQL-1 violation: SQL statement is empty")
    scrubbed = _STRING_LITERAL_RE.sub("''", cleaned)
    if ";" in scrubbed:
        raise RejectedSqlError(
            "FORBIDDEN-SQL-1 / ERRORS-SQL-1 violation: multiple SQL statements are not allowed"
        )
    if "--" in scrubbed or "/*" in scrubbed:
        raise RejectedSqlError(
            "FORBIDDEN-SQL-1 / ERRORS-SQL-1 violation: SQL comments are not allowed"
        )
    tokens = [tok.upper() for tok in _WORD_RE.findall(scrubbed)]
    if not tokens or tokens[0] not in ("SELECT", "WITH"):
        raise RejectedSqlError(
            "FORBIDDEN-SQL-1 / ERRORS-SQL-1 violation: statement must begin with SELECT or WITH"
        )
    if "SELECT" not in tokens:
        raise RejectedSqlError(
            "FORBIDDEN-SQL-1 / ERRORS-SQL-1 violation: WITH query must contain a SELECT clause"
        )
    forbidden_hit = next((tok for tok in tokens if tok in FORBIDDEN_SQL_KEYWORDS), None)
    if forbidden_hit is not None:
        raise RejectedSqlError(
            f"FORBIDDEN-SQL-1 / ERRORS-SQL-1 violation: forbidden keyword {forbidden_hit!r} "
            "in read-only query"
        )
    return cleaned


def extract_referenced_tables(sql: str, known_tables: frozenset[str]) -> tuple[str, ...]:
    """Return known warehouse table names referenced in FROM or JOIN clauses, in query order."""
    scrubbed = _STRING_LITERAL_RE.sub("''", sql)
    found: list[str] = []
    for match in _FROM_JOIN_RE.finditer(scrubbed):
        candidate = match.group(1)
        if candidate in known_tables and candidate not in found:
            found.append(candidate)
    return tuple(found)


def validate_sql_query_result(
    result: SqlQueryResult,
    *,
    row_limit: int,
    known_citations: Mapping[str, SourceCitation],
) -> None:
    """POST-SQL-1 and SEQ-7 validator for SqlQueryResult."""
    if result.row_count != len(result.rows):
        raise QueryServiceViolationError(
            f"POST-SQL-1 violation: row_count {result.row_count} != len(rows) {len(result.rows)}"
        )
    if len(result.rows) > row_limit or len(result.rows) > MAX_ROW_LIMIT:
        raise QueryServiceViolationError(
            f"POST-SQL-1 violation: returned {len(result.rows)} rows exceeding limit {row_limit}"
        )
    expected_citations = tuple(
        known_citations[tbl] for tbl in result.referenced_tables if tbl in known_citations
    )
    if result.citations != expected_citations:
        raise QueryServiceViolationError(
            f"SEQ-7 violation: attached citations {result.citations!r} != "
            f"expected {expected_citations!r}"
        )


def validate_schema_description(desc: TableSchemaDescription) -> None:
    """POST-SCHEMA-1 validator for one TableSchemaDescription."""
    if (
        not desc.table_name.strip()
        or not desc.dataset_id.strip()
        or not desc.columns
        or not desc.grain.strip()
        or not desc.as_of.strip()
        or not desc.applied_filter.strip()
    ):
        raise QueryServiceViolationError(
            f"POST-SCHEMA-1 violation: incomplete TableSchemaDescription {desc!r}"
        )


# --- 5. Traceability map (every clause declares its verification method) -----------------------

CONTRACT_QUERY_CORE: Mapping[str, Clause] = {
    "SEQ-6": Clause(
        "test",
        "The QueryService connects to the canonical warehouse from WAREHOUSE_GCS_URI in read-only "
        "mode BEFORE accepting its first tool call or query, never rebuilds the warehouse, and "
        "raises UnconnectedWarehouseError if queried before connect().",
        ("REQ-46",),
    ),
    "POST-SCHEMA-1": Clause(
        "test",
        "schema.describe returns each requested warehouse table's table_name, dataset_id, "
        "columns, grain, join_keys, as_of, applied_filter and matching glossary_terms.",
        ("REQ-33",),
    ),
    "POST-SQL-1": Clause(
        "test",
        "sql.query runs a validated read-only SELECT statement against the connected warehouse "
        "and returns columns, rows capped at row_limit (<= MAX_ROW_LIMIT), row_count, truncated "
        "and referenced_tables.",
        ("REQ-34",),
    ),
    "SEQ-7": Clause(
        "test",
        "After each sql.query or schema.describe call and before returning the result, the "
        "QueryService attaches a SourceCitation (table_name, dataset_id, origin_url, publisher, "
        "as_of, applied_filter) for every referenced warehouse table.",
        ("REQ-32",),
    ),
    "FORBIDDEN-SQL-1": Clause(
        "test",
        "sql.query never executes a non-SELECT statement, multi-statement string, SQL comment, or "
        "any FORBIDDEN_SQL_KEYWORDS token, and never modifies the warehouse.",
        ("REQ-34", "REQ-46"),
    ),
    "ERRORS-SQL-1": Clause(
        "test",
        "validate_readonly_sql and sql.query raise RejectedSqlError naming the broken rule when "
        "the statement is empty, not a single SELECT/WITH..SELECT, contains a forbidden keyword "
        "or comment, or when row_limit or timeout_seconds is outside the contracted bounds.",
        ("REQ-34",),
    ),
}
