"""Scope decision: which retained source files the warehouse loads (SLICE-3 batch 1, REQ-25, REQ-26).

Contract-Implementation Independence (CL11-F): constants, errors and records are redeclared here; nothing is imported
from contracts/warehouse_contract.py. Tests bridge the two.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

# POST-SCOPE-1: a reference period on or after this date is in scope.
SCOPE_START: Final = date(2024, 1, 1)
_DATE_PATTERN: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DECISION_LOAD: Final = "load"
DECISION_EXCLUDE: Final = "exclude"

EXCLUDE_TIME_SCOPE: Final = "time_scope"
EXCLUDE_DUPLICATE_CONTENT: Final = "duplicate_content"
EXCLUDE_DUPLICATE_FORMAT: Final = "duplicate_format"
# FORBIDDEN-SCOPE-1: the only reasons, in precedence order.
EXCLUSION_REASONS: Final = (
    EXCLUDE_TIME_SCOPE,
    EXCLUDE_DUPLICATE_CONTENT,
    EXCLUDE_DUPLICATE_FORMAT,
)

# POST-SCOPE-5: the lowest rank of a release wins; the others are duplicate_format.
FORMAT_RANK: Final[Mapping[str, int]] = {"csv": 0, "xlsx": 1, "sas": 2}


class WarehouseError(Exception):
    """Base of every error raised by the warehouse implementation."""


class InvalidSourceFileError(WarehouseError):
    """ERRORS-SCOPE-1: a source file description is outside the accepted domain."""


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    sha256: str
    format: str
    reference_end: str | None
    is_base_geography: bool
    release_id: str | None


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    path: str
    decision: str
    reason: str | None


def make_source_file(
    path: str,
    sha256: str,
    format: str,
    reference_end: str | None,
    is_base_geography: bool,
    release_id: str | None,
) -> SourceFile:
    """ERRORS-SCOPE-1: build a SourceFile or raise InvalidSourceFileError."""
    if not path:
        raise InvalidSourceFileError("ERRORS-SCOPE-1 violation: path is empty")
    if not sha256:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: sha256 is empty for {path!r}"
        )
    if format not in FORMAT_RANK:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: format {format!r} is not one of {sorted(FORMAT_RANK)} for {path!r}"
        )
    if reference_end is not None:
        if not _DATE_PATTERN.match(reference_end):
            raise InvalidSourceFileError(
                f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not YYYY-MM-DD for {path!r}"
            )
        try:
            date.fromisoformat(reference_end)
        except ValueError as exc:
            raise InvalidSourceFileError(
                f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not a real date for {path!r}"
            ) from exc
    if release_id is not None and not release_id:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: release_id is an empty string for {path!r}"
        )
    return SourceFile(
        path, sha256, format, reference_end, is_base_geography, release_id
    )


def decide_scope(files: Sequence[SourceFile]) -> tuple[ScopeDecision, ...]:
    """Decide load or exclude for every file, returned in input order (INV-SCOPE-1).

    INV-SCOPE-2: files are judged in (format rank, path) order, so the listing order changes nothing.
    """
    order = sorted(
        range(len(files)), key=lambda i: (FORMAT_RANK[files[i].format], files[i].path)
    )
    loaded_hashes: set[str] = set()
    loaded_releases: dict[str, str] = {}
    decided: dict[int, ScopeDecision] = {}
    for i in order:
        f = files[i]
        # POST-SCOPE-2 (base geography never time-scoped), POST-SCOPE-6 (unknown period never time-scoped),
        # POST-SCOPE-3 (time scope takes precedence over the duplicate rules).
        if (
            not f.is_base_geography
            and f.reference_end is not None
            and date.fromisoformat(f.reference_end) < SCOPE_START
        ):
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_TIME_SCOPE)
        elif f.sha256 in loaded_hashes:  # POST-SCOPE-4
            decided[i] = ScopeDecision(
                f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_CONTENT
            )
        elif (
            f.release_id is not None
            and f.release_id in loaded_releases
            and loaded_releases[f.release_id] != f.format
        ):  # POST-SCOPE-5
            decided[i] = ScopeDecision(
                f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_FORMAT
            )
        else:  # POST-SCOPE-1
            decided[i] = ScopeDecision(f.path, DECISION_LOAD, None)
            loaded_hashes.add(f.sha256)
            if f.release_id is not None:
                loaded_releases.setdefault(f.release_id, f.format)
    return tuple(decided[i] for i in range(len(files)))
