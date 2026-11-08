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
from contracts.warehouse_contract import (
    BASE_TABLE_COLUMNS,
    NOT_RECORDED,
    WAREHOUSE_DB_FILE,
    WAREHOUSE_LOCATION_ENV,
)

# --- 1. Importable constants (specification values) --------------------------------------

WAREHOUSE_GCP_PROJECT = "<gcp-project>"
WAREHOUSE_GCS_BUCKET = "<warehouse-bucket>"
WAREHOUSE_GCS_URI = f"gs://{WAREHOUSE_GCS_BUCKET}"

DEFAULT_ROW_LIMIT = 200
MAX_ROW_LIMIT = 1_000
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 15.0

# Batch 1 redo: the engine reads the warehouse through the data adapter (SLICE-3). The base-table
# names and columns are the warehouse contract's (BASE_TABLE_COLUMNS, POST-BASE-1).
ENGINE_LOCATION_ENV = WAREHOUSE_LOCATION_ENV
ENGINE_DB_FILE = WAREHOUSE_DB_FILE
ENGINE_BASE_COLUMNS = BASE_TABLE_COLUMNS
# Geographic key column names (lowercase) and the level each identifies (POST-SCHEMA-1).
KEY_GRAINS: Mapping[str, str] = {
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
GRAIN_ORDER: tuple[str, ...] = ("block", "tract", "county", "state")

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
    """SEQ-6: a query or tool call was attempted before open()."""


class QueryTimeoutError(QueryServiceContractError):
    """ERRORS-SQL-2: a query ran past its time limit and was interrupted."""


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


def expected_grain_and_keys(columns: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """POST-SCHEMA-1 oracle (jev at Ketema's direction, 0.62: derived at describe time).

    join_keys are the table's columns whose lowercase name is in KEY_GRAINS, in column order; the
    grain is the most specific level among them (GRAIN_ORDER), or NOT_RECORDED when none.
    """
    keys = tuple(c for c in columns if c.lower() in KEY_GRAINS)
    levels = {KEY_GRAINS[k.lower()] for k in keys}
    grain = next((g for g in GRAIN_ORDER if g in levels), NOT_RECORDED)
    return grain, keys


def expected_table_citation(sources_row: Mapping[str, object]) -> SourceCitation:
    """SEQ-7 oracle: a table's citation from its row in the sources base table."""
    return SourceCitation(
        table_name=str(sources_row["table_name"]),
        dataset_id=str(sources_row["dataset_id"]),
        origin_url=str(sources_row["origin_url"]),
        publisher=str(sources_row["publisher"]),
        as_of=str(sources_row["as_of"]),
        applied_filter=str(sources_row["applied_filter"]),
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
        "WarehouseQueryEngine(env).open() takes the warehouse "
        "location only from WAREHOUSE_LOCATION "
        "through the data adapter (REQ-47), opens WAREHOUSE_DB_FILE there read-only, creates one "
        "TEMP view per catalog row over its Parquet file at the "
        "location, then limits file access to "
        "the location, disables other external access and locks the configuration. It never writes "
        "or rebuilds the warehouse (the files' SHA-256 are "
        "unchanged). Before open(), every tool call "
        "raises UnconnectedWarehouseError; a missing or invalid location propagates the adapter's "
        "error.",
        ("REQ-46", "REQ-47", "REQ-49", "REQ-50", "REQ-52"),
    ),
    "POST-SCHEMA-1": Clause(
        "test",
        "describe_schema(table_names=None) returns, for each requested catalog table (all when "
        "None, in catalog order), its table_name and dataset_id from the catalog, its columns in "
        "ordinal order from the columns base table, grain and join_keys equal to "
        "expected_grain_and_keys(columns), as_of and applied_filter from its sources row, and its "
        "glossary rows as (term, definition) pairs. An unknown table name raises RejectedSqlError.",
        ("REQ-33",),
    ),
    "POST-SQL-1": Clause(
        "test",
        "execute_sql(sql, row_limit, timeout_seconds) runs the statement only when DuckDB's parser "
        "finds exactly one SELECT statement; it returns columns, at most row_limit rows as "
        "dictionaries, row_count = len(rows), truncated True exactly when more rows exist, and "
        "referenced_tables = extract_referenced_tables(sql, catalog table names).",
        ("REQ-34", "REQ-49", "REQ-50"),
    ),
    "SEQ-7": Clause(
        "test",
        "Before execute_sql returns, the result carries expected_table_citation of each referenced "
        "table's sources row, in referenced_tables order.",
        ("REQ-32",),
    ),
    "FORBIDDEN-SQL-1": Clause(
        "test",
        "execute_sql never runs a statement other than one SELECT (no COPY, ATTACH, CREATE, "
        "INSERT, SET, PRAGMA or multiple statements), never reads a file outside the warehouse "
        "location (for example read_csv of /etc/hosts fails), and never changes the warehouse.",
        ("REQ-34", "REQ-46", "REQ-50"),
    ),
    "ERRORS-SQL-1": Clause(
        "test",
        "validate_readonly_sql and execute_sql raise RejectedSqlError naming the broken rule when "
        "the statement is empty, is not exactly one SELECT, reads outside the location, fails in "
        "DuckDB, or when row_limit or timeout_seconds is outside the contracted bounds.",
        ("REQ-34",),
    ),
    "ERRORS-SQL-2": Clause(
        "test",
        "A query still running at timeout_seconds is interrupted and raises QueryTimeoutError "
        "naming ERRORS-SQL-2; the engine answers the next query normally.",
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
