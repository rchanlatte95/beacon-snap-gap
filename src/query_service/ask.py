"""The ask boundary between the App and the QueryService: the request and the 200 reply body.

Specification: contracts/query_service_contract.py, CONTRACT_QUERY_ASK (SLICE-4 batch 2, Z-26):
PRE-ASK-1, ERRORS-ASK-1, POST-ASK-1. Requirements: REQ-60, REQ-32, REQ-40. Runtime declarations
are independent of the contract module; tests bridge the two (CL11-F).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

REACH_STEP_MILES: Final = 0.5
MAX_REACH_MILES: Final = 20.0
REACH_STEPS_MILES: Final[tuple[float, ...]] = tuple(
    k * REACH_STEP_MILES for k in range(int(MAX_REACH_MILES / REACH_STEP_MILES) + 1)
)
CUT_NAMES: Final[tuple[str, ...]] = ("poverty", "no_vehicle", "sba_rate_per_1000")
ALLOWED_PERCENTILES: Final[Mapping[str, tuple[int, ...]]] = {
    "poverty": (50, 75, 90),
    "no_vehicle": (50, 75, 90),
    "sba_rate_per_1000": (10, 25, 50),
}
REQUEST_KEYS: Final = frozenset({"question", "reach_miles", "percentiles"})
CITATION_KEYS: Final[tuple[str, ...]] = (
    "table_name",
    "dataset_id",
    "origin_url",
    "publisher",
    "as_of",
    "applied_filter",
)


class AskRequestError(ValueError):
    """ERRORS-ASK-1: the ask request body is outside the contracted shape (HTTP 400)."""


@dataclass(frozen=True, slots=True)
class SourceCitation:
    """The source of one warehouse table used by a tool call (REQ-32)."""

    table_name: str
    dataset_id: str
    origin_url: str
    publisher: str
    as_of: str
    applied_filter: str


@dataclass(frozen=True, slots=True)
class SqlQueryResult:
    """One read-only query result with the citations of the tables it used (REQ-34, REQ-32)."""

    columns: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]
    row_count: int
    truncated: bool
    referenced_tables: tuple[str, ...]
    citations: tuple[SourceCitation, ...]


@dataclass(frozen=True, slots=True)
class AppliedThresholds:
    """The reach distance and cut percentiles a question is answered under (REQ-60)."""

    reach_miles: float
    poverty: int
    no_vehicle: int
    sba_rate_per_1000: int


@dataclass(frozen=True, slots=True)
class AskRequest:
    """A validated ask request (PRE-ASK-1)."""

    question: str
    thresholds: AppliedThresholds


@dataclass(frozen=True, slots=True)
class AskReply:
    """One answer, built from tool results, with its sources and tracts (POST-ASK-1)."""

    answer: str
    model: str
    results: tuple[SqlQueryResult, ...]
    tracts: tuple[str, ...]
    applied: AppliedThresholds


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def parse_ask_request(raw: object) -> AskRequest:
    """Parse a decoded JSON ask body (PRE-ASK-1).

    Raises:
        AskRequestError: ERRORS-ASK-1, naming the broken rule.
    """
    if not isinstance(raw, Mapping) or set(raw) != REQUEST_KEYS:
        keys = sorted(raw) if isinstance(raw, Mapping) else type(raw).__name__
        raise AskRequestError(
            f"ERRORS-ASK-1 violation: body keys {keys} are not {sorted(REQUEST_KEYS)}"
        )
    question = raw["question"]
    if not isinstance(question, str) or not question.strip():
        raise AskRequestError("ERRORS-ASK-1 violation: question is not a non-blank string")
    reach = raw["reach_miles"]
    if not _is_number(reach) or float(reach) not in REACH_STEPS_MILES:
        raise AskRequestError(f"ERRORS-ASK-1 violation: reach_miles {reach!r} is not a reach step")
    percentiles = raw["percentiles"]
    if not isinstance(percentiles, Mapping) or set(percentiles) != set(CUT_NAMES):
        raise AskRequestError(
            f"ERRORS-ASK-1 violation: percentiles must hold exactly {list(CUT_NAMES)}"
        )
    chosen: dict[str, int] = {}
    for name in CUT_NAMES:
        value = percentiles[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value not in ALLOWED_PERCENTILES[name]
        ):
            raise AskRequestError(
                f"ERRORS-ASK-1 violation: percentiles.{name} {value!r} is not one of "
                f"{ALLOWED_PERCENTILES[name]}"
            )
        chosen[name] = value
    return AskRequest(
        question=question.strip(),
        thresholds=AppliedThresholds(
            reach_miles=float(reach),
            poverty=chosen["poverty"],
            no_vehicle=chosen["no_vehicle"],
            sba_rate_per_1000=chosen["sba_rate_per_1000"],
        ),
    )


def reply_citations(results: tuple[SqlQueryResult, ...]) -> tuple[SourceCitation, ...]:
    """Every result's citations, the first per table, in result order (POST-ASK-1)."""
    seen: dict[str, SourceCitation] = {}
    for result in results:
        for citation in result.citations:
            seen.setdefault(citation.table_name, citation)
    return tuple(seen.values())


def column_label(name: str) -> str:
    """A result column as a reader sees it: internal field names never reach the App."""
    return name.replace("_", " ")


def reply_body(reply: AskReply) -> dict[str, object]:
    """The 200 JSON body for a reply (POST-ASK-1); result columns are labels (FORBIDDEN-ANS-1)."""
    return {
        "answer": reply.answer,
        "model": reply.model,
        "results": [
            {
                "columns": [column_label(c) for c in r.columns],
                "rows": [{column_label(k): v for k, v in row.items()} for row in r.rows],
                "row_count": r.row_count,
                "truncated": r.truncated,
                "referenced_tables": list(r.referenced_tables),
            }
            for r in reply.results
        ],
        "citations": [
            {key: getattr(c, key) for key in CITATION_KEYS} for c in reply_citations(reply.results)
        ],
        "tracts": list(reply.tracts),
        "applied": {
            "reach_miles": reply.applied.reach_miles,
            "percentiles": {name: getattr(reply.applied, name) for name in CUT_NAMES},
        },
    }
