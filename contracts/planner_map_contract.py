"""Build contract, SLICE-1 planner map. Authority: requirements/REQUIREMENT_MANIFEST.md.

Domain: the Build (data in, static tract file out). The App has its own contract in TypeScript
(contracts/planner-map.app.contract.ts), cross-referenced by clause ID. The shared edge is the static
tract file (IP-4); its tract-level fields are stated once, here.

Batch 1: tract classification (REQ-8, REQ-14). Source of the rule: Z-1 option B with driving-distance LILA.

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

# --- 1. Importable constants (specification values) --------------------------------------

CLASS_HIGH_NEED = "Classic Food Desert"
CLASS_NO_GAP = "No gap flagged"
CLASS_INSUFFICIENT = "Insufficient data"
TRACT_CLASSES = (CLASS_HIGH_NEED, CLASS_NO_GAP, CLASS_INSUFFICIENT)

LILA_FLAG_COLUMN = "DD_SRAM_LILATracts_halfAnd10"
QUANTILE_N = 4
QUANTILE_METHOD = "inclusive"
POVERTY_CUT_INDEX = 2  # statistics.quantiles(..., n=4) returns Q1, Q2, Q3 at indexes 0, 1, 2.

MIN_PCT = 0.0
MAX_PCT = 100.0

# Counts over the committed Central Florida source data (Z-1 B, D-1). A test recomputes them.
EXPECTED_TRACT_COUNT = 490
EXPECTED_POVERTY_VALUE_COUNT = 488
EXPECTED_HIGH_NEED_COUNT = 97
EXPECTED_NO_GAP_COUNT = 391
EXPECTED_INSUFFICIENT_COUNT = 2


# --- 2. Domain exceptions (every message names its clause) --------------------------------


class PlannerMapContractError(Exception):
    """Base of every violation raised by this contract."""


class InvalidIndicatorError(PlannerMapContractError):
    """ERRORS-CLS-1: an indicator value is outside the contracted domain."""


class ClassificationViolation(PlannerMapContractError):
    """POST-CLS-1 or POST-CLS-2: a produced class disagrees with the rule."""


class PovertyCutViolation(PlannerMapContractError):
    """POST-CLS-3: a poverty cut disagrees with the contracted computation."""


# --- 3. Immutable typed records ------------------------------------------------------------


@dataclass(frozen=True)
class Clause:
    verification: Literal["test", "execution", "tool"]
    text: str
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class TractIndicators:
    """The two Z-1 inputs for one tract. None means the source value is blank."""

    geoid: str
    pct_poverty: Optional[float]
    lila_flag: Optional[int]


@dataclass(frozen=True)
class TractClassification:
    geoid: str
    tract_class: str
    missing_indicators: tuple[str, ...]


# --- 4. Pure callable validators (the executable statement of accepted and rejected input) --


def validate_indicators(indicators: TractIndicators) -> TractIndicators:
    """PRE-CLS-1 / ERRORS-CLS-1. Return the indicators unchanged, or raise InvalidIndicatorError."""
    rate = indicators.pct_poverty
    if rate is not None:
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or math.isnan(rate):
            raise InvalidIndicatorError(
                f"ERRORS-CLS-1 violation: tract {indicators.geoid} pct_poverty {rate!r} is not a number or None"
            )
        if not MIN_PCT <= rate <= MAX_PCT:
            raise InvalidIndicatorError(
                f"PRE-CLS-1 violation: tract {indicators.geoid} pct_poverty {rate} is outside {MIN_PCT} to {MAX_PCT}"
            )
    flag = indicators.lila_flag
    if flag is not None and (isinstance(flag, bool) or flag not in (0, 1)):
        raise InvalidIndicatorError(
            f"PRE-CLS-1 violation: tract {indicators.geoid} {LILA_FLAG_COLUMN} {flag!r} is not 0, 1 or None"
        )
    return indicators


def expected_poverty_cut(rates: Sequence[float]) -> float:
    """POST-CLS-3 oracle: the 75th percentile of the poverty rates, inclusive method, unrounded."""
    return statistics.quantiles(rates, n=QUANTILE_N, method=QUANTILE_METHOD)[POVERTY_CUT_INDEX]


def validate_poverty_cut(cut: float, rates: Sequence[float]) -> float:
    """POST-CLS-3. Return cut if it equals the contracted computation over rates, else raise."""
    expected = expected_poverty_cut(rates)
    if not math.isclose(cut, expected, rel_tol=0.0, abs_tol=1e-9):
        raise PovertyCutViolation(
            f"POST-CLS-3 violation: poverty cut {cut!r} is not the {QUANTILE_METHOD} Q3 {expected!r} "
            f"of {len(rates)} rates (a rounded or differently computed cut is refused)"
        )
    return cut


def expected_classification(indicators: TractIndicators, cut: float) -> TractClassification:
    """POST-CLS-1 and POST-CLS-2 oracle: the one class the rule allows for these indicators."""
    validate_indicators(indicators)
    missing = []
    if indicators.pct_poverty is None:
        missing.append("pct_poverty")
    if indicators.lila_flag is None:
        missing.append(LILA_FLAG_COLUMN)
    if missing:
        return TractClassification(indicators.geoid, CLASS_INSUFFICIENT, tuple(missing))
    if indicators.pct_poverty >= cut and indicators.lila_flag == 1:
        return TractClassification(indicators.geoid, CLASS_HIGH_NEED, ())
    return TractClassification(indicators.geoid, CLASS_NO_GAP, ())


def validate_classification(
    indicators: TractIndicators, cut: float, produced: TractClassification
) -> TractClassification:
    """POST-CLS-1 / POST-CLS-2. Return produced if it equals the rule's only answer, else raise."""
    expected = expected_classification(indicators, cut)
    if produced.geoid != indicators.geoid:
        raise ClassificationViolation(
            f"POST-CLS-1 violation: classification is for tract {produced.geoid}, expected {indicators.geoid}"
        )
    if produced.tract_class not in TRACT_CLASSES:
        raise ClassificationViolation(
            f"POST-CLS-1 violation: tract {indicators.geoid} class {produced.tract_class!r} is not one of {TRACT_CLASSES}"
        )
    if expected.missing_indicators and produced.tract_class != CLASS_INSUFFICIENT:
        raise ClassificationViolation(
            f"POST-CLS-2 violation: tract {indicators.geoid} is missing {expected.missing_indicators} "
            f"but was classed {produced.tract_class!r}, not {CLASS_INSUFFICIENT!r}"
        )
    if produced.tract_class != expected.tract_class:
        raise ClassificationViolation(
            f"POST-CLS-1 violation: tract {indicators.geoid} (pct_poverty {indicators.pct_poverty}, "
            f"lila_flag {indicators.lila_flag}, cut {cut}) expected {expected.tract_class!r}, "
            f"got {produced.tract_class!r}"
        )
    if tuple(produced.missing_indicators) != expected.missing_indicators:
        raise ClassificationViolation(
            f"POST-CLS-2 violation: tract {indicators.geoid} missing indicators "
            f"{tuple(produced.missing_indicators)} differ from {expected.missing_indicators}"
        )
    return produced


# --- 5. Traceability map: every clause declares exactly one verification method ----------------

CONTRACT_PLANNER_MAP_CLASSIFICATION = {
    "PRE-CLS-1": Clause(
        "test",
        "Each tract's pct_poverty is a number from 0 to 100 or blank, and its "
        f"{LILA_FLAG_COLUMN} is 0, 1 or blank. Anything else is refused.",
        ("REQ-8", "REQ-14"),
    ),
    "POST-CLS-1": Clause(
        "test",
        f"A tract is {CLASS_HIGH_NEED!r} when pct_poverty is at or above the poverty cut AND {LILA_FLAG_COLUMN} "
        f"is 1; otherwise {CLASS_NO_GAP!r}, unless an indicator is blank (POST-CLS-2). Every tract gets exactly "
        "one of the three classes.",
        ("REQ-14",),
    ),
    "POST-CLS-2": Clause(
        "test",
        f"A tract with a blank pct_poverty or a blank {LILA_FLAG_COLUMN} is {CLASS_INSUFFICIENT!r}, never "
        f"{CLASS_NO_GAP!r}, and the classification names each blank indicator.",
        ("REQ-8",),
    ),
    "POST-CLS-3": Clause(
        "test",
        f"The poverty cut is the unrounded {QUANTILE_METHOD}-method 75th percentile "
        f"(statistics.quantiles n={QUANTILE_N}) of the pct_poverty values of the tracts that have one.",
        ("REQ-14",),
    ),
    "ERRORS-CLS-1": Clause(
        "test",
        "A value outside the PRE-CLS-1 domain raises InvalidIndicatorError naming the tract and the clause; "
        "the Build does not coerce it, drop the tract, or class it.",
        ("REQ-8", "REQ-9"),
    ),
}
