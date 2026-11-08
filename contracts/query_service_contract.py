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
- Batch 2 (cycle 18, Z-26): the ask interface between the App and the QueryService: the request
  carries the question and the thresholds set in the App (REQ-60); the reply carries the answer, the
  model, the tool results, the citations, every tract the answer refers to, and the thresholds
  applied (REQ-32, REQ-40); an outage is a 503, never an invented answer (REQ-39, REQ-37).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from contracts.planner_map_contract import (
    REACH_STEPS_MILES,
    SBA_CUT_PERCENTILES,
    TOP_CUT_PERCENTILES,
)

# --- 1. Importable constants (specification values) --------------------------------------

WAREHOUSE_GCP_PROJECT = "<gcp-project>"
WAREHOUSE_GCS_BUCKET = "<warehouse-bucket>"
WAREHOUSE_GCS_URI = f"gs://{WAREHOUSE_GCS_BUCKET}"

DEFAULT_ROW_LIMIT = 200
MAX_ROW_LIMIT = 1_000
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 15.0

# Batch 2 / Z-26: the ask interface. Threshold values are the Build contract's
# (planner_map_contract).
ASK_PATH = "/api/ask"
ASK_REQUEST_KEYS: frozenset[str] = frozenset({"question", "reach_miles", "percentiles"})
CUT_NAMES: tuple[str, ...] = ("poverty", "no_vehicle", "sba_rate_per_1000")
ALLOWED_PERCENTILES: Mapping[str, tuple[int, ...]] = {
    "poverty": TOP_CUT_PERCENTILES,
    "no_vehicle": TOP_CUT_PERCENTILES,
    "sba_rate_per_1000": SBA_CUT_PERCENTILES,
}
ASK_STATUS_OK = 200
ASK_STATUS_BAD_REQUEST = 400
ASK_STATUS_UNAVAILABLE = 503
GEOID_PATTERN = re.compile(r"^\d{11}$")
RESULT_JSON_KEYS: tuple[str, ...] = (
    "columns",
    "rows",
    "row_count",
    "truncated",
    "referenced_tables",
)
CITATION_JSON_KEYS: tuple[str, ...] = (
    "table_name",
    "dataset_id",
    "origin_url",
    "publisher",
    "as_of",
    "applied_filter",
)

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


class AskRequestError(QueryServiceContractError):
    """ERRORS-ASK-1: the ask request body is outside the contracted shape (HTTP 400)."""


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


@dataclass(frozen=True)
class AppliedThresholds:
    """Batch 2 / REQ-60: the reach distance and cut percentiles a question is answered under."""

    reach_miles: float
    poverty: int
    no_vehicle: int
    sba_rate_per_1000: int


@dataclass(frozen=True)
class AskRequest:
    """Batch 2 / PRE-ASK-1: a validated ask request."""

    question: str
    thresholds: AppliedThresholds


@dataclass(frozen=True)
class AskReply:
    """Batch 2 / POST-ASK-1: one answer, built from tool results, with its sources and tracts."""

    answer: str
    model: str
    results: tuple[SqlQueryResult, ...]
    tracts: tuple[str, ...]
    applied: AppliedThresholds


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


def expected_ask_request(raw: object) -> AskRequest:
    """PRE-ASK-1 / ERRORS-ASK-1 oracle: parse an ask request body (already decoded from JSON).

    The body is an object with exactly ASK_REQUEST_KEYS: a non-blank question string, reach_miles
    one of REACH_STEPS_MILES (an int or float JSON number, never a boolean), and percentiles an
    object with exactly CUT_NAMES, each an integer in ALLOWED_PERCENTILES. Anything else raises
    AskRequestError naming ERRORS-ASK-1 and the broken rule.
    """
    if not isinstance(raw, Mapping) or set(raw) != ASK_REQUEST_KEYS:
        keys = sorted(raw) if isinstance(raw, Mapping) else type(raw).__name__
        raise AskRequestError(
            f"ERRORS-ASK-1 violation: body keys {keys} are not {sorted(ASK_REQUEST_KEYS)}"
        )
    question = raw["question"]
    if not isinstance(question, str) or not question.strip():
        raise AskRequestError("ERRORS-ASK-1 violation: question is not a non-blank string")
    reach = raw["reach_miles"]
    if (
        isinstance(reach, bool)
        or not isinstance(reach, int | float)
        or float(reach) not in REACH_STEPS_MILES
    ):
        raise AskRequestError(f"ERRORS-ASK-1 violation: reach_miles {reach!r} is not a reach step")
    pct = raw["percentiles"]
    if not isinstance(pct, Mapping) or set(pct) != set(CUT_NAMES):
        raise AskRequestError(
            f"ERRORS-ASK-1 violation: percentiles must hold exactly {list(CUT_NAMES)}"
        )
    for name in CUT_NAMES:
        value = pct[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value not in ALLOWED_PERCENTILES[name]
        ):
            raise AskRequestError(
                f"ERRORS-ASK-1 violation: percentiles.{name} {value!r} is "
                f"not one of {ALLOWED_PERCENTILES[name]}"
            )
    return AskRequest(
        question=question.strip(),
        thresholds=AppliedThresholds(
            reach_miles=float(reach),
            poverty=pct["poverty"],
            no_vehicle=pct["no_vehicle"],
            sba_rate_per_1000=pct["sba_rate_per_1000"],
        ),
    )


def expected_reply_citations(results: tuple[SqlQueryResult, ...]) -> tuple[SourceCitation, ...]:
    """POST-ASK-1 oracle: every result's citations, first per table_name, in result order."""
    seen: dict[str, SourceCitation] = {}
    for result in results:
        for citation in result.citations:
            seen.setdefault(citation.table_name, citation)
    return tuple(seen.values())


def expected_reply_json(reply: AskReply) -> dict[str, object]:
    """POST-ASK-1 oracle: the exact 200 body for a reply (the App's ask shape)."""
    return {
        "answer": reply.answer,
        "model": reply.model,
        "results": [
            {
                "columns": list(r.columns),
                "rows": [dict(row) for row in r.rows],
                "row_count": r.row_count,
                "truncated": r.truncated,
                "referenced_tables": list(r.referenced_tables),
            }
            for r in reply.results
        ],
        "citations": [
            {key: getattr(c, key) for key in CITATION_JSON_KEYS}
            for c in expected_reply_citations(reply.results)
        ],
        "tracts": list(reply.tracts),
        "applied": {
            "reach_miles": reply.applied.reach_miles,
            "percentiles": {name: getattr(reply.applied, name) for name in CUT_NAMES},
        },
    }


def validate_ask_reply(
    reply: AskReply, request: AskRequest, known_geoids: frozenset[str]
) -> AskReply:
    """POST-ASK-1 validator: applied thresholds echo the request; tracts are unique known GEOIDs."""
    if reply.applied != request.thresholds:
        raise QueryServiceViolationError(
            f"POST-ASK-1 violation: applied {reply.applied!r} differs "
            f"from the request {request.thresholds!r}"
        )
    if not reply.answer.strip() or not reply.model.strip():
        raise QueryServiceViolationError("POST-ASK-1 violation: answer and model must be non-blank")
    bad = [g for g in reply.tracts if not GEOID_PATTERN.match(g) or g not in known_geoids]
    if bad or len(set(reply.tracts)) != len(reply.tracts):
        raise QueryServiceViolationError(
            f"POST-ASK-1 violation: tracts must be unique known GEOIDs; bad {bad[:5]}, "
            f"{len(reply.tracts) - len(set(reply.tracts))} repeated"
        )
    return reply


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

CONTRACT_QUERY_ASK: Mapping[str, Clause] = {
    "PRE-ASK-1": Clause(
        "test",
        f"POST {ASK_PATH} takes a JSON object with exactly question, reach_miles and percentiles, "
        "parsed as expected_ask_request: a non-blank question, a "
        "reach step from the Build contract, and "
        "one allowed percentile for each of the three cuts (Z-26).",
        ("REQ-60",),
    ),
    "ERRORS-ASK-1": Clause(
        "test",
        "A body outside PRE-ASK-1 gets HTTP 400 with a JSON error "
        "naming ERRORS-ASK-1 and the broken rule; "
        "the model is not called.",
        ("REQ-60",),
    ),
    "POST-ASK-1": Clause(
        "test",
        "A 200 body equals expected_reply_json: the answer, the "
        "model, the tool results, the citations of "
        "every result (first per table, REQ-40), every tract the "
        "answer refers to as a unique known GEOID "
        "(not limited by SQL row limits, Z-26), and the "
        "thresholds applied, which equal the request's "
        "(validate_ask_reply, REQ-60).",
        ("REQ-60", "REQ-32", "REQ-40"),
    ),
    "ERRORS-ASK-2": Clause(
        "test",
        "When Vertex AI fails or does not answer in time, the "
        "reply is HTTP 503 with a JSON error naming "
        "ERRORS-ASK-2; the service never returns a 200 without an answer built from tool results.",
        ("REQ-39", "REQ-37"),
    ),
}
