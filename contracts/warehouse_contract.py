"""Warehouse contract, SLICE-3.

Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 13, REQ-25 to REQ-31).

Domain: the Ingest (retained source files in, warehouse tables out). The QueryService has its own
contract (SLICE-4).

Batches:
- Batch 1: which files the warehouse loads and which it excludes, with the reason (REQ-25, REQ-26).
- Batch 2: the state filter for Florida, New York and Utah (REQ-27) and the source and loaded row
  counts it records (REQ-29).
- Later batches: local disk only and unaltered sources (REQ-28), remaining provenance fields
  (REQ-29), glossary (REQ-30), publish to the bucket (REQ-31).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

# --- 1. Importable constants (specification values) --------------------------------------

SCOPE_START = date(2024, 1, 1)  # REQ-25: a reference period reaches this date or later
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DECISION_LOAD = "load"
DECISION_EXCLUDE = "exclude"
DECISIONS = (DECISION_LOAD, DECISION_EXCLUDE)

EXCLUDE_TIME_SCOPE = "time_scope"
EXCLUDE_DUPLICATE_CONTENT = "duplicate_content"
EXCLUDE_DUPLICATE_FORMAT = "duplicate_format"
# REQ-26: the only reasons, in precedence order (the first that applies is the recorded reason).
EXCLUSION_REASONS = (EXCLUDE_TIME_SCOPE, EXCLUDE_DUPLICATE_CONTENT, EXCLUDE_DUPLICATE_FORMAT)

# Same release in several formats: the lowest rank is loaded, the others are duplicate_format.

# Batch 2: state filter (REQ-27, REQ-29).
# Priority order of state columns across the retained sources; the first present column governs.
STATE_COLUMNS: tuple[str, ...] = (
    "BorrState",
    "BUSINESS_STATE",
    "StateAbbr",
    "STATEABBRV",
    "EST_ST",
    "State",
)
TARGET_STATE_VALUES: frozenset[str] = frozenset(
    {"FL", "Florida", "12", "NY", "New York", "36", "UT", "Utah", "49"}
)
GEO_ID_COLUMN = "GEO_ID"
# ACS GEO_ID: national row (0100000US...) or state/county/tract in FL (12), NY (36), UT (49).
GEO_ID_TARGET_PATTERN = re.compile(r"^(0100000US.*|.*US(12|36|49).*)")
FILTER_NONE = "none (no state field)"
FORMAT_RANK: Mapping[str, int] = {"csv": 0, "xlsx": 1, "sas": 2}


# --- 2. Domain exceptions (every message names its clause) --------------------------------


class WarehouseContractError(Exception):
    """Base of every violation raised by this contract."""


class InvalidSourceFileError(WarehouseContractError):
    """ERRORS-SCOPE-1: a source file description is outside the contracted domain."""


class ScopeViolationError(WarehouseContractError):
    """POST-SCOPE-1..6, INV-SCOPE-1, INV-SCOPE-2 or FORBIDDEN-SCOPE-1: decisions disagree."""


class InvalidTableError(WarehouseContractError):
    """ERRORS-STATE-1: a table description is outside the contracted domain."""


class StateFilterViolationError(WarehouseContractError):
    """POST-STATE-1..4 or INV-STATE-1: the filtered rows or recorded counts disagree."""


# --- 3. Immutable typed records ------------------------------------------------------------


@dataclass(frozen=True)
class Clause:
    verification: Literal["test", "execution", "tool"]
    text: str
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class SourceFile:
    """One retained source file as the scope decision sees it.

    reference_end: ISO date (YYYY-MM-DD) of the last day the data describes, or None when the
    sources do not state it.
    release_id: identifies one release published in several formats, or None.
    """

    path: str
    sha256: str
    file_format: str
    reference_end: str | None
    is_base_geography: bool
    release_id: str | None


@dataclass(frozen=True)
class ScopeDecision:
    path: str
    decision: str
    reason: str | None


@dataclass(frozen=True)
class StateFilterOutcome:
    """Batch 2 validated result of filtering one table's rows by state."""

    rows: tuple[Mapping[str, str], ...]
    rows_in_source: int
    rows_loaded: int
    applied_filter: str


# --- 4. Callable validators ----------------------------------------------------------------


def validate_source_file(
    *,
    path: str,
    sha256: str,
    file_format: str,
    reference_end: str | None,
    is_base_geography: bool,
    release_id: str | None,
) -> SourceFile:
    """ERRORS-SCOPE-1 gate: build a SourceFile or raise InvalidSourceFileError."""
    if not path:
        raise InvalidSourceFileError("ERRORS-SCOPE-1 violation: path is empty")
    if not sha256:
        raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: sha256 is empty for {path!r}")
    if file_format not in FORMAT_RANK:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: file_format {file_format!r} is not one of "
            f"{sorted(FORMAT_RANK)} for {path!r}"
        )
    if reference_end is not None:
        if not DATE_PATTERN.match(reference_end):
            raise InvalidSourceFileError(
                f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not YYYY-MM-DD "
                f"for {path!r}"
            )
        try:
            date.fromisoformat(reference_end)
        except ValueError as exc:
            raise InvalidSourceFileError(
                f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not a real date "
                f"for {path!r}"
            ) from exc
    if release_id is not None and not release_id:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: release_id is an empty string for {path!r}"
        )
    return SourceFile(path, sha256, file_format, reference_end, is_base_geography, release_id)


def expected_scope_decisions(files: Sequence[SourceFile]) -> tuple[ScopeDecision, ...]:
    """POST-SCOPE-1 to POST-SCOPE-6, INV-SCOPE-1, INV-SCOPE-2 oracle.

    Files are judged in (format rank, path) order so the result does not depend on input order;
    decisions are returned in input order. For each file, the first rule that applies wins:
    1. time_scope: not base geography, reference_end known, and before SCOPE_START.
    2. duplicate_content: the sha256 of an already loaded file.
    3. duplicate_format: the release_id of an already loaded file of another format.
    4. otherwise load.
    """
    order = sorted(
        range(len(files)), key=lambda i: (FORMAT_RANK[files[i].file_format], files[i].path)
    )
    loaded_hashes: set[str] = set()
    loaded_releases: dict[str, str] = {}
    decided: dict[int, ScopeDecision] = {}
    for i in order:
        f = files[i]
        out_of_time = (
            not f.is_base_geography
            and f.reference_end is not None
            and date.fromisoformat(f.reference_end) < SCOPE_START
        )
        same_release_other_format = (
            f.release_id is not None
            and f.release_id in loaded_releases
            and loaded_releases[f.release_id] != f.file_format
        )
        if out_of_time:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_TIME_SCOPE)
        elif f.sha256 in loaded_hashes:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_CONTENT)
        elif same_release_other_format:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_FORMAT)
        else:
            decided[i] = ScopeDecision(f.path, DECISION_LOAD, None)
            loaded_hashes.add(f.sha256)
            if f.release_id is not None:
                loaded_releases.setdefault(f.release_id, f.file_format)
    return tuple(decided[i] for i in range(len(files)))


def validate_scope_decisions(
    files: Sequence[SourceFile], decisions: Sequence[ScopeDecision]
) -> None:
    """Raise ScopeViolationError naming the clause when decisions disagree with the oracle."""
    if len(decisions) != len(files):
        raise ScopeViolationError(
            f"INV-SCOPE-1 violation: {len(files)} files but {len(decisions)} decisions"
        )
    for f, d in zip(files, decisions, strict=True):
        if d.path != f.path:
            raise ScopeViolationError(
                f"INV-SCOPE-1 violation: decision for {d.path!r} sits where {f.path!r} belongs"
            )
        if d.decision not in DECISIONS:
            raise ScopeViolationError(
                f"FORBIDDEN-SCOPE-1 violation: {d.path!r} decision {d.decision!r} "
                f"is not one of {DECISIONS}"
            )
        if d.decision == DECISION_EXCLUDE and d.reason not in EXCLUSION_REASONS:
            raise ScopeViolationError(
                f"FORBIDDEN-SCOPE-1 violation: {d.path!r} excluded for {d.reason!r}, "
                f"not one of {EXCLUSION_REASONS}"
            )
        if d.decision == DECISION_LOAD and d.reason is not None:
            raise ScopeViolationError(
                f"FORBIDDEN-SCOPE-1 violation: {d.path!r} is loaded but carries reason {d.reason!r}"
            )
    for f, got, want in zip(files, decisions, expected_scope_decisions(files), strict=True):
        if got != want:
            raise ScopeViolationError(
                f"POST-SCOPE violation: {f.path!r} decided {got.decision}/{got.reason}, "
                f"the rule gives {want.decision}/{want.reason}"
            )


def validate_table_columns(columns: Sequence[str]) -> tuple[str, ...]:
    """ERRORS-STATE-1 gate: column names are non-empty and unique."""
    if not columns:
        raise InvalidTableError("ERRORS-STATE-1 violation: columns is empty")
    seen: set[str] = set()
    for col in columns:
        if not col:
            raise InvalidTableError("ERRORS-STATE-1 violation: an empty column name is not allowed")
        if col in seen:
            raise InvalidTableError(f"ERRORS-STATE-1 violation: duplicate column {col!r}")
        seen.add(col)
    return tuple(columns)


def expected_state_filter(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> StateFilterOutcome:
    """POST-STATE-1 to POST-STATE-4, INV-STATE-1 oracle."""
    cols = validate_table_columns(columns)
    col_set = set(cols)
    state_col = next((c for c in STATE_COLUMNS if c in col_set), None)
    if state_col is not None:
        kept = tuple(r for r in rows if r.get(state_col, "") in TARGET_STATE_VALUES)
        applied = f'state field "{state_col}" in FL, NY, UT'
    elif GEO_ID_COLUMN in col_set:
        kept = tuple(r for r in rows if bool(GEO_ID_TARGET_PATTERN.match(r.get(GEO_ID_COLUMN, ""))))
        applied = "GEO_ID national row or state/county/tract in FL (12), NY (36), UT (49)"
    else:
        kept = tuple(rows)
        applied = FILTER_NONE
    return StateFilterOutcome(
        rows=kept, rows_in_source=len(rows), rows_loaded=len(kept), applied_filter=applied
    )


def validate_state_filter_outcome(
    columns: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    outcome: StateFilterOutcome,
) -> None:
    """Raise StateFilterViolationError naming the clause when outcome disagrees with the oracle."""
    want = expected_state_filter(columns, rows)
    if outcome.rows_in_source != want.rows_in_source or outcome.rows_loaded != len(outcome.rows):
        raise StateFilterViolationError(
            f"POST-STATE-4 violation: counts ({outcome.rows_in_source}, {outcome.rows_loaded}) "
            f"disagree with ({want.rows_in_source}, {len(outcome.rows)})"
        )
    if outcome.applied_filter != want.applied_filter:
        raise StateFilterViolationError(
            f"POST-STATE violation: applied_filter {outcome.applied_filter!r} != "
            f"{want.applied_filter!r}"
        )
    if outcome.rows != want.rows:
        raise StateFilterViolationError(
            "POST-STATE / INV-STATE-1 violation: kept rows or their order disagree with the rule"
        )


# --- 5. Traceability map (every clause declares its verification method) -----------------------

CONTRACT_SCOPE: Mapping[str, Clause] = {
    "POST-SCOPE-1": Clause(
        "test",
        "A file that is not base geography and whose reference_end is on or after 2024-01-01 "
        "is loaded, unless a duplicate rule excludes it.",
        ("REQ-25",),
    ),
    "POST-SCOPE-2": Clause(
        "test",
        "A base-geography file is never excluded for time_scope, whatever its reference_end.",
        ("REQ-25",),
    ),
    "POST-SCOPE-3": Clause(
        "test",
        "A file that is not base geography and whose reference_end is before 2024-01-01 is "
        "excluded with reason time_scope, even when a duplicate rule also applies.",
        ("REQ-25", "REQ-26"),
    ),
    "POST-SCOPE-4": Clause(
        "test",
        "Of files with the same sha256, the first in (format rank, path) order is loaded and "
        "every other is excluded with reason duplicate_content.",
        ("REQ-26",),
    ),
    "POST-SCOPE-5": Clause(
        "test",
        "Of files sharing a release_id in different formats, the lowest format rank is loaded "
        "and the others are excluded with reason duplicate_format.",
        ("REQ-26",),
    ),
    "POST-SCOPE-6": Clause(
        "test",
        "A file whose reference_end is unknown is never excluded for time_scope; the sources do "
        "not state its period, so REQ-26 gives no reason to exclude it.",
        ("REQ-25", "REQ-26"),
    ),
    "INV-SCOPE-1": Clause(
        "test",
        "Every input file receives exactly one decision, returned in the input order.",
        ("REQ-26",),
    ),
    "INV-SCOPE-2": Clause(
        "test",
        "The decisions do not depend on the order in which the files are listed.",
        ("REQ-26",),
    ),
    "FORBIDDEN-SCOPE-1": Clause(
        "test",
        "A decision is load with no reason, or exclude with exactly one reason from time_scope, "
        "duplicate_content, duplicate_format; no other reason exists.",
        ("REQ-26",),
    ),
    "ERRORS-SCOPE-1": Clause(
        "test",
        "validate_source_file raises InvalidSourceFileError for an empty path or sha256, an "
        "unknown file_format, a reference_end that is not a real YYYY-MM-DD date, or an empty "
        "release_id.",
        ("REQ-25",),
    ),
}


CONTRACT_STATE_FILTER: Mapping[str, Clause] = {
    "POST-STATE-1": Clause(
        "test",
        "When a table has one or more columns from STATE_COLUMNS, the first in STATE_COLUMNS "
        "governs and only rows whose value in that column is in TARGET_STATE_VALUES are kept.",
        ("REQ-27",),
    ),
    "POST-STATE-2": Clause(
        "test",
        "When a table has no column from STATE_COLUMNS and has GEO_ID, only rows matching "
        "GEO_ID_TARGET_PATTERN (national row or FL 12, NY 36, UT 49) are kept.",
        ("REQ-27",),
    ),
    "POST-STATE-3": Clause(
        "test",
        "When a table has neither a column from STATE_COLUMNS nor GEO_ID, every row is kept "
        "and applied_filter is FILTER_NONE.",
        ("REQ-27",),
    ),
    "POST-STATE-4": Clause(
        "test",
        "rows_in_source equals the input row count and rows_loaded equals the kept row count.",
        ("REQ-27", "REQ-29"),
    ),
    "INV-STATE-1": Clause(
        "test",
        "Kept rows appear in their input order and each kept row is unaltered.",
        ("REQ-27", "REQ-28"),
    ),
    "ERRORS-STATE-1": Clause(
        "test",
        "validate_table_columns raises InvalidTableError when columns is empty, contains an "
        "empty name, or contains duplicate names.",
        ("REQ-27",),
    ),
}
