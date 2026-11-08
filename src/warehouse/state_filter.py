"""Filter warehouse rows to Florida, New York and Utah (SLICE-3 batch 2).

Specification: contracts/warehouse_contract.py, CONTRACT_STATE_FILTER.
Requirements: REQ-27, REQ-28, REQ-29. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

STATE_COLUMNS: Final = (
    "BorrState",
    "BUSINESS_STATE",
    "StateAbbr",
    "STATEABBRV",
    "EST_ST",
    "State",
)
TARGET_STATE_VALUES: Final = frozenset(
    {"FL", "Florida", "12", "NY", "New York", "36", "UT", "Utah", "49"}
)
GEO_ID_COLUMN: Final = "GEO_ID"
GEO_ID_TARGET_PATTERN: Final = re.compile(r"^(0100000US.*|.*US(12|36|49).*)")
FILTER_NONE: Final = "none (no state field)"


class InvalidTableError(Exception):
    """ERRORS-STATE-1: column names are empty or duplicated."""


@dataclass(frozen=True, slots=True)
class StateFilterOutcome:
    """Kept rows in source order, their counts, and the governing filter description."""

    rows: tuple[Mapping[str, str], ...]
    rows_in_source: int
    rows_loaded: int
    applied_filter: str


def validate_table_columns(columns: Sequence[str]) -> tuple[str, ...]:
    """Return non-empty, unique column names without changing their order.

    PRE: columns is a sequence of strings.
    POST: return the names as a tuple (ERRORS-STATE-1 validation boundary).
    INV: the supplied sequence is not modified.

    Raises:
        InvalidTableError: Propagates for an empty sequence, empty name, or duplicate name.
    """
    if not columns or any(not column for column in columns):
        raise InvalidTableError("ERRORS-STATE-1 violation: column names must be non-empty")
    if len(set(columns)) != len(columns):
        raise InvalidTableError("ERRORS-STATE-1 violation: column names must be unique")
    return tuple(columns)


def filter_rows_by_state(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> StateFilterOutcome:
    """Keep the rows selected by the highest-priority available state field.

    PRE: columns contains non-empty, unique names; rows contains string-valued mappings.
    POST: apply STATE_COLUMNS precedence, then GEO_ID, or keep all rows (POST-STATE-1..3).
    POST: report input and kept counts and the governing filter (POST-STATE-4).
    INV: preserve kept rows and input order without mutating the input (INV-STATE-1).

    Raises:
        InvalidTableError: Propagates from column validation (ERRORS-STATE-1).
    """
    column_names = validate_table_columns(columns)
    state_column = next((name for name in STATE_COLUMNS if name in column_names), None)
    if state_column is not None:
        # POST-STATE-1: precedence is specification order, not source column order.
        selected = tuple(row for row in rows if row.get(state_column, "") in TARGET_STATE_VALUES)
        applied_filter = f'state field "{state_column}" in FL, NY, UT'
    elif GEO_ID_COLUMN in column_names:
        # POST-STATE-2: use the specified ACS pattern only in the absence of a state column.
        selected = tuple(
            row for row in rows if GEO_ID_TARGET_PATTERN.match(row.get(GEO_ID_COLUMN, ""))
        )
        applied_filter = "GEO_ID national row or state/county/tract in FL (12), NY (36), UT (49)"
    else:
        # POST-STATE-3: sources with no state field retain every row.
        selected = tuple(rows)
        applied_filter = FILTER_NONE
    # POST-STATE-4 / INV-STATE-1: selection preserves row contents and order; no source writes.
    return StateFilterOutcome(selected, len(rows), len(selected), applied_filter)
