"""Build tract classification (SLICE-1 batch 1).

Contract-Implementation Independence (CL11-F): this module does NOT import from
contracts/planner_map_contract.py. It redeclares its constants, exception class,
and record independently; tests assert alignment.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence

# Redeclared constants (POST-CLS-1, POST-CLS-2, POST-CLS-3, PRE-CLS-1)
CLASS_HIGH_NEED = "Classic Food Desert"
CLASS_NO_GAP = "No gap flagged"
CLASS_INSUFFICIENT = "Insufficient data"
TRACT_CLASSES = (CLASS_HIGH_NEED, CLASS_NO_GAP, CLASS_INSUFFICIENT)

LILA_FLAG_COLUMN = "DD_SRAM_LILATracts_halfAnd10"
QUANTILE_N = 4
QUANTILE_METHOD = "inclusive"
POVERTY_CUT_INDEX = 2

MIN_PCT = 0.0
MAX_PCT = 100.0


class InvalidIndicatorError(Exception):
    """PRE-CLS-1 / ERRORS-CLS-1: raised when a tract indicator is outside the domain."""


@dataclass(frozen=True)
class TractClassification:
    """POST-CLS-1 / POST-CLS-2: classification result for one tract."""

    geoid: str
    tract_class: str
    missing_indicators: tuple[str, ...]


def poverty_cut(rates: Sequence[float]) -> float:
    """POST-CLS-3: unrounded inclusive 75th percentile of non-blank poverty rates."""
    return statistics.quantiles(rates, n=QUANTILE_N, method=QUANTILE_METHOD)[POVERTY_CUT_INDEX]


def classify_tract(
    geoid: str,
    pct_poverty: Optional[float],
    lila_flag: Optional[int],
    cut: float,
) -> TractClassification:
    """PRE-CLS-1, POST-CLS-1, POST-CLS-2, ERRORS-CLS-1: classify one tract."""
    # PRE-CLS-1 / ERRORS-CLS-1: validate pct_poverty domain
    if pct_poverty is not None:
        if isinstance(pct_poverty, bool) or not isinstance(pct_poverty, (int, float)) or math.isnan(pct_poverty):
            raise InvalidIndicatorError(
                f"ERRORS-CLS-1 violation: tract {geoid} pct_poverty {pct_poverty!r} is not a finite number or None"
            )
        if not MIN_PCT <= pct_poverty <= MAX_PCT:
            raise InvalidIndicatorError(
                f"PRE-CLS-1 violation: tract {geoid} pct_poverty {pct_poverty} is outside {MIN_PCT} to {MAX_PCT}"
            )
    # PRE-CLS-1 / ERRORS-CLS-1: validate lila_flag domain
    if lila_flag is not None and (isinstance(lila_flag, bool) or lila_flag not in (0, 1)):
        raise InvalidIndicatorError(
            f"PRE-CLS-1 violation: tract {geoid} {LILA_FLAG_COLUMN} {lila_flag!r} is not 0, 1 or None"
        )

    # POST-CLS-2: any blank indicator yields Insufficient data naming every blank indicator
    missing: list[str] = []
    if pct_poverty is None:
        missing.append("pct_poverty")
    if lila_flag is None:
        missing.append(LILA_FLAG_COLUMN)
    if missing:
        return TractClassification(geoid=geoid, tract_class=CLASS_INSUFFICIENT, missing_indicators=tuple(missing))

    # POST-CLS-1: High need iff pct_poverty >= cut and lila_flag == 1
    if pct_poverty >= cut and lila_flag == 1:
        return TractClassification(geoid=geoid, tract_class=CLASS_HIGH_NEED, missing_indicators=())
    return TractClassification(geoid=geoid, tract_class=CLASS_NO_GAP, missing_indicators=())
