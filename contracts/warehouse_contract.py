"""Warehouse contract, SLICE-3. Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 13, REQ-25 to REQ-31).

Domain: the Ingest (retained source files in, warehouse tables out). The QueryService has its own contract (SLICE-4).

Batches:
- Batch 1: which files the warehouse loads and which it excludes, with the reason (REQ-25, REQ-26).
- Later batches: state filter (REQ-27), local disk only and unaltered sources (REQ-28), provenance (REQ-29),
  glossary (REQ-30), publish to the bucket (REQ-31).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping, Optional, Sequence

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
FORMAT_RANK: Mapping[str, int] = {"csv": 0, "xlsx": 1, "sas": 2}


# --- 2. Domain exceptions (every message names its clause) --------------------------------


class WarehouseContractError(Exception):
    """Base of every violation raised by this contract."""


class InvalidSourceFileError(WarehouseContractError):
    """ERRORS-SCOPE-1: a source file description is outside the contracted domain."""


class ScopeViolation(WarehouseContractError):
    """POST-SCOPE-1 to POST-SCOPE-6, INV-SCOPE-1, INV-SCOPE-2 or FORBIDDEN-SCOPE-1: decisions disagree with the rule."""


# --- 3. Immutable typed records ------------------------------------------------------------


@dataclass(frozen=True)
class Clause:
    verification: Literal["test", "execution", "tool"]
    text: str
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class SourceFile:
    """One retained source file as the scope decision sees it.

    reference_end: ISO date (YYYY-MM-DD) of the last day the data describes, or None when the sources do not state it.
    release_id: identifies one release published in several formats, or None.
    """

    path: str
    sha256: str
    format: str
    reference_end: Optional[str]
    is_base_geography: bool
    release_id: Optional[str]


@dataclass(frozen=True)
class ScopeDecision:
    path: str
    decision: str
    reason: Optional[str]


# --- 4. Callable validators ----------------------------------------------------------------


def validate_source_file(
    path: str,
    sha256: str,
    format: str,
    reference_end: Optional[str],
    is_base_geography: bool,
    release_id: Optional[str],
) -> SourceFile:
    """ERRORS-SCOPE-1 gate: build a SourceFile or raise InvalidSourceFileError."""
    if not path:
        raise InvalidSourceFileError("ERRORS-SCOPE-1 violation: path is empty")
    if not sha256:
        raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: sha256 is empty for {path!r}")
    if format not in FORMAT_RANK:
        raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: format {format!r} is not one of {sorted(FORMAT_RANK)} for {path!r}")
    if reference_end is not None:
        if not DATE_PATTERN.match(reference_end):
            raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not YYYY-MM-DD for {path!r}")
        try:
            date.fromisoformat(reference_end)
        except ValueError as exc:
            raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not a real date for {path!r}") from exc
    if release_id is not None and not release_id:
        raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: release_id is an empty string for {path!r}")
    return SourceFile(path, sha256, format, reference_end, is_base_geography, release_id)


def expected_scope_decisions(files: Sequence[SourceFile]) -> tuple[ScopeDecision, ...]:
    """POST-SCOPE-1 to POST-SCOPE-6, INV-SCOPE-1, INV-SCOPE-2 oracle.

    Files are judged in (format rank, path) order so the result does not depend on input order; decisions are
    returned in input order. For each file, the first rule that applies wins:
    1. time_scope: not base geography, reference_end known, and before SCOPE_START.
    2. duplicate_content: the sha256 of an already loaded file.
    3. duplicate_format: the release_id of an already loaded file of another format.
    4. otherwise load.
    """
    order = sorted(range(len(files)), key=lambda i: (FORMAT_RANK[files[i].format], files[i].path))
    loaded_hashes: set[str] = set()
    loaded_releases: dict[str, str] = {}
    decided: dict[int, ScopeDecision] = {}
    for i in order:
        f = files[i]
        if not f.is_base_geography and f.reference_end is not None and date.fromisoformat(f.reference_end) < SCOPE_START:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_TIME_SCOPE)
        elif f.sha256 in loaded_hashes:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_CONTENT)
        elif f.release_id is not None and f.release_id in loaded_releases and loaded_releases[f.release_id] != f.format:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_FORMAT)
        else:
            decided[i] = ScopeDecision(f.path, DECISION_LOAD, None)
            loaded_hashes.add(f.sha256)
            if f.release_id is not None:
                loaded_releases.setdefault(f.release_id, f.format)
    return tuple(decided[i] for i in range(len(files)))


def validate_scope_decisions(files: Sequence[SourceFile], decisions: Sequence[ScopeDecision]) -> None:
    """Raise ScopeViolation naming the clause when decisions disagree with the oracle."""
    if len(decisions) != len(files):
        raise ScopeViolation(f"INV-SCOPE-1 violation: {len(files)} files but {len(decisions)} decisions")
    for f, d in zip(files, decisions, strict=True):
        if d.path != f.path:
            raise ScopeViolation(f"INV-SCOPE-1 violation: decision for {d.path!r} sits where {f.path!r} belongs")
        if d.decision not in DECISIONS:
            raise ScopeViolation(f"FORBIDDEN-SCOPE-1 violation: {d.path!r} decision {d.decision!r} is not one of {DECISIONS}")
        if d.decision == DECISION_EXCLUDE and d.reason not in EXCLUSION_REASONS:
            raise ScopeViolation(f"FORBIDDEN-SCOPE-1 violation: {d.path!r} excluded for {d.reason!r}, not one of {EXCLUSION_REASONS}")
        if d.decision == DECISION_LOAD and d.reason is not None:
            raise ScopeViolation(f"FORBIDDEN-SCOPE-1 violation: {d.path!r} is loaded but carries reason {d.reason!r}")
    for f, got, want in zip(files, decisions, expected_scope_decisions(files), strict=True):
        if got != want:
            raise ScopeViolation(
                f"POST-SCOPE violation: {f.path!r} decided {got.decision}/{got.reason}, the rule gives {want.decision}/{want.reason}"
            )


# --- 5. Traceability map (every clause declares its verification method) -----------------------

CONTRACT_SCOPE: Mapping[str, Clause] = {
    "POST-SCOPE-1": Clause("test", "A file that is not base geography and whose reference_end is on or after 2024-01-01 is loaded, unless a duplicate rule excludes it.", ("REQ-25",)),
    "POST-SCOPE-2": Clause("test", "A base-geography file is never excluded for time_scope, whatever its reference_end.", ("REQ-25",)),
    "POST-SCOPE-3": Clause("test", "A file that is not base geography and whose reference_end is before 2024-01-01 is excluded with reason time_scope, even when a duplicate rule also applies.", ("REQ-25", "REQ-26")),
    "POST-SCOPE-4": Clause("test", "Of files with the same sha256, the first in (format rank, path) order is loaded and every other is excluded with reason duplicate_content.", ("REQ-26",)),
    "POST-SCOPE-5": Clause("test", "Of files sharing a release_id in different formats, the lowest format rank is loaded and the others are excluded with reason duplicate_format.", ("REQ-26",)),
    "POST-SCOPE-6": Clause("test", "A file whose reference_end is unknown is never excluded for time_scope; the sources do not state its period, so REQ-26 gives no reason to exclude it.", ("REQ-25", "REQ-26")),
    "INV-SCOPE-1": Clause("test", "Every input file receives exactly one decision, returned in the input order.", ("REQ-26",)),
    "INV-SCOPE-2": Clause("test", "The decisions do not depend on the order in which the files are listed.", ("REQ-26",)),
    "FORBIDDEN-SCOPE-1": Clause("test", "A decision is load with no reason, or exclude with exactly one reason from time_scope, duplicate_content, duplicate_format; no other reason exists.", ("REQ-26",)),
    "ERRORS-SCOPE-1": Clause("test", "validate_source_file raises InvalidSourceFileError for an empty path or sha256, an unknown format, a reference_end that is not a real YYYY-MM-DD date, or an empty release_id.", ("REQ-25",)),
}
