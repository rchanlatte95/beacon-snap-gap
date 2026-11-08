"""Build contract, SLICE-1 planner map & Opportunities to Serve alignment engine.
Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 12).

Domain: the Build (data in, static tract file out). The App has its own contract in TypeScript
(contracts/planner-map.app.contract.ts), cross-referenced by clause ID. The shared edge is the static
tract file (IP-4); its tract-level fields are stated once, here.

Batches:
- Batch 1: tract classification (REQ-8, REQ-14). Source of the rule: Z-1 option B with driving-distance LILA.
- Batch 2: cross-agency alignment (SBA lending contrast REQ-19, no-vehicle transport gap & mobile recommendation REQ-20,
  deterministic confidence & median household income + 90% MOE REQ-22, exterior-only county borders REQ-23,
  and static bundle / privacy / non-mutation invariants REQ-1, REQ-4, REQ-9, REQ-17).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, Sequence

# --- 1. Importable constants (specification values) --------------------------------------

CLASS_HIGH_NEED = "Classic Food Desert"
CLASS_NO_GAP = "No gap flagged"
CLASS_INSUFFICIENT = "Insufficient data"
TRACT_CLASSES = (CLASS_HIGH_NEED, CLASS_NO_GAP, CLASS_INSUFFICIENT)

LILA_FLAG_COLUMN = "DD_SRAM_LILATracts_halfAnd10"
QUANTILE_N = 4
QUANTILE_METHOD = "inclusive"
POVERTY_CUT_INDEX = 2  # statistics.quantiles(..., n=4) returns Q1, Q2, Q3 at indexes 0, 1, 2.
MEDIAN_INDEX = 1  # Q2 (50th percentile) at index 1.
BOTTOM_QUARTILE_INDEX = 0  # Q1 (25th percentile) at index 0.

# REQ-19 / Z-23: SBA loans per 1,000 residents in the bottom quartile, for tracts of at least
# 1,200 residents (the Census Bureau's tract minimum, the brief's "sizable population base").
SBA_RATE_PER_RESIDENTS = 1000
SBA_MIN_POPULATION = 1200
# The static bundle's "thresholds" object carries the cut and the floor under these keys.
BUNDLE_SBA_RATE_CUT_KEY = "sba_rate_cut_per_1000"
BUNDLE_SBA_MIN_POPULATION_KEY = "sba_min_population"

MIN_PCT = 0.0
MAX_PCT = 100.0

# Counts over the committed Central Florida source data (Z-1 B, D-1, REQ-19, REQ-20).
EXPECTED_TRACT_COUNT = 490
EXPECTED_DRAWN_TRACT_COUNT = 489
EXPECTED_NOT_DRAWN_GEOID = "12095990000"
EXPECTED_POVERTY_VALUE_COUNT = 488
EXPECTED_HIGH_NEED_COUNT = 97
EXPECTED_NO_GAP_COUNT = 391
EXPECTED_INSUFFICIENT_COUNT = 2
EXPECTED_DUAL_GAP_COUNT = 26
EXPECTED_TRANSPORT_GAP_COUNT = 53
EXPECTED_TRIPLE_GAP_COUNT = 12
EXPECTED_COUNTY_COUNT = 4
EXPECTED_COUNTY_RING_COUNT = 1

# Confidence level constants (REQ-22)
CONFIDENCE_NOT_RATED = "Not rated"
CONFIDENCE_LOWER = "Lower"
CONFIDENCE_MODERATE = "Moderate"
CONFIDENCE_LEVELS = (CONFIDENCE_NOT_RATED, CONFIDENCE_LOWER, CONFIDENCE_MODERATE)
CONFIDENCE_MIN_HOUSEHOLDS = 500
CONFIDENCE_MAX_GROUP_QUARTERS_PCT = 20.0

# Recommended deployment modes (REQ-19, REQ-20, REQ-21)
ACTION_MOBILE_AND_SBA = "Mobile Pantry Deployment + Joint SBA/CDFI Micro-Lending Outreach"
ACTION_MOBILE_PANTRY = "Mobile Pantry / Transit-Accessible Food Deployment"
ACTION_FIXED_AND_SBA = "Partner Pantry Expansion + SBA/SBDC Small-Business Outreach"
ACTION_PARTNER_PANTRY = "Partner Pantry Capacity & Hours Support"
ACTION_DATA_AUDIT = "Field Verification & Data Gap Audit"
ACTION_MONITOR = "Standard Monitoring (No Gap Flagged)"

# Output paths (Z-5, REQ-17)
STATIC_TRACTS_GEOJSON_PATH = "public/data/tracts.geojson"
STATIC_BUNDLE_JSON_PATH = "public/data/planner-bundle.json"

FORBIDDEN_BLOCK_KEYS = frozenset({"block_id", "geoid20", "blocks", "block_records", "borrower_name", "borrower_address"})


# --- 2. Domain exceptions (every message names its clause) --------------------------------


class PlannerMapContractError(Exception):
    """Base of every violation raised by this contract."""


class InvalidIndicatorError(PlannerMapContractError):
    """ERRORS-CLS-1: an indicator value is outside the contracted domain."""


class ClassificationViolation(PlannerMapContractError):
    """POST-CLS-1 or POST-CLS-2: a produced class disagrees with the rule."""


class PovertyCutViolation(PlannerMapContractError):
    """POST-CLS-3: a poverty cut disagrees with the contracted computation."""


class AlignmentViolation(PlannerMapContractError):
    """POST-ALN-1, POST-ALN-2, POST-ALN-3, POST-ALN-4: cross-agency alignment or confidence mismatch."""


class CountyBoundaryViolation(PlannerMapContractError):
    """POST-GEO-1: county geometry is not a single exterior polygon ring per county."""


class BundleSchemaViolation(PlannerMapContractError):
    """FORBIDDEN-PRIV-1 or ERRORS-BLD-1: block-level record leaked or required input missing."""


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


@dataclass(frozen=True)
class TractAlignmentRecord:
    """Batch 2 validated cross-agency alignment & confidence record for one tract."""

    geoid: str
    tract_class: str
    sba_loans_total: int
    pop2020: int
    sba_gross_usd_total: float
    pct_no_vehicle: Optional[float]
    households: Optional[int]
    group_quarters_pct: Optional[float]
    median_household_income: Optional[float]
    median_household_income_moe90: Optional[float]
    is_dual_gap: bool
    is_transport_gap: bool
    is_triple_gap: bool
    confidence_level: str
    recommended_action: str


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


def expected_sba_rate(loans: int, population: int) -> float | None:
    """POST-ALN-1 oracle: SBA loans per SBA_RATE_PER_RESIDENTS residents; None when nobody lives there."""
    if population <= 0:
        return None
    return loans / population * SBA_RATE_PER_RESIDENTS


def expected_sba_rate_cut(loans: Sequence[int], populations: Sequence[int]) -> float:
    """POST-ALN-1 oracle: inclusive bottom-quartile rate over the populated tracts."""
    rates = [
        r
        for r in (expected_sba_rate(n, p) for n, p in zip(loans, populations, strict=True))
        if r is not None
    ]
    return statistics.quantiles(rates, n=QUANTILE_N, method=QUANTILE_METHOD)[BOTTOM_QUARTILE_INDEX]


def expected_no_vehicle_q75(no_vehicle_rates: Sequence[float]) -> float:
    """POST-ALN-2 oracle: inclusive 75th percentile of non-blank household no-vehicle rates."""
    return statistics.quantiles(no_vehicle_rates, n=QUANTILE_N, method=QUANTILE_METHOD)[POVERTY_CUT_INDEX]


def expected_confidence_level(
    tract_class: str,
    households: Optional[int],
    group_quarters_pct: Optional[float],
) -> str:
    """POST-ALN-4 oracle: deterministic confidence level per REQ-22."""
    if tract_class == CLASS_INSUFFICIENT:
        return CONFIDENCE_NOT_RATED
    if (households is None or households < CONFIDENCE_MIN_HOUSEHOLDS) or (
        group_quarters_pct is not None and group_quarters_pct > CONFIDENCE_MAX_GROUP_QUARTERS_PCT
    ):
        return CONFIDENCE_LOWER
    return CONFIDENCE_MODERATE


def expected_recommended_action(
    tract_class: str,
    is_dual_gap: bool,
    is_transport_gap: bool,
) -> str:
    """POST-ALN-3 oracle: deterministic cross-agency intervention recommendation per REQ-20, REQ-21."""
    if tract_class == CLASS_INSUFFICIENT:
        return ACTION_DATA_AUDIT
    if tract_class == CLASS_NO_GAP:
        return ACTION_MONITOR
    if is_transport_gap and is_dual_gap:
        return ACTION_MOBILE_AND_SBA
    if is_transport_gap:
        return ACTION_MOBILE_PANTRY
    if is_dual_gap:
        return ACTION_FIXED_AND_SBA
    return ACTION_PARTNER_PANTRY


def validate_alignment_record(
    record: TractAlignmentRecord,
    sba_rate_cut: float,
    no_vehicle_q75: float,
) -> TractAlignmentRecord:
    """POST-ALN-1, POST-ALN-2, POST-ALN-3, POST-ALN-4 validator."""
    high_need = record.tract_class == CLASS_HIGH_NEED
    rate = expected_sba_rate(record.sba_loans_total, record.pop2020)
    exp_dual = (
        high_need
        and record.pop2020 >= SBA_MIN_POPULATION
        and rate is not None
        and rate <= sba_rate_cut
    )
    exp_trans = (
        high_need
        and record.pct_no_vehicle is not None
        and record.pct_no_vehicle >= no_vehicle_q75
    )
    exp_triple = exp_dual and exp_trans
    if record.is_dual_gap != exp_dual:
        raise AlignmentViolation(
            f"POST-ALN-1 violation: tract {record.geoid} is_dual_gap={record.is_dual_gap} "
            f"expected {exp_dual} (class={record.tract_class!r}, sba_loans_total={record.sba_loans_total}, "
            f"pop2020={record.pop2020}, rate_per_1000={rate}, cut={sba_rate_cut})"
        )
    if record.is_transport_gap != exp_trans or record.is_triple_gap != exp_triple:
        raise AlignmentViolation(
            f"POST-ALN-2 violation: tract {record.geoid} transport/triple flags "
            f"({record.is_transport_gap}, {record.is_triple_gap}) expected ({exp_trans}, {exp_triple})"
        )
    exp_conf = expected_confidence_level(record.tract_class, record.households, record.group_quarters_pct)
    if record.confidence_level != exp_conf:
        raise AlignmentViolation(
            f"POST-ALN-4 violation: tract {record.geoid} confidence_level={record.confidence_level!r} "
            f"expected {exp_conf!r}"
        )
    exp_action = expected_recommended_action(record.tract_class, exp_dual, exp_trans)
    if record.recommended_action != exp_action:
        raise AlignmentViolation(
            f"POST-ALN-3 violation: tract {record.geoid} recommended_action={record.recommended_action!r} "
            f"expected {exp_action!r}"
        )
    return record


def validate_county_boundaries(counties_geojson: Mapping[str, Any]) -> Mapping[str, Any]:
    """POST-GEO-1 validator: 4 Central FL counties, each a single exterior Polygon ring with no interior clutter."""
    features = counties_geojson.get("features")
    if not isinstance(features, Sequence) or len(features) != EXPECTED_COUNTY_COUNT:
        raise CountyBoundaryViolation(
            f"POST-GEO-1 violation: expected {EXPECTED_COUNTY_COUNT} county features, got "
            f"{len(features) if isinstance(features, Sequence) else type(features).__name__}"
        )
    for feat in features:
        geom = feat.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])
        if gtype != "Polygon" or len(coords) != EXPECTED_COUNTY_RING_COUNT:
            raise CountyBoundaryViolation(
                f"POST-GEO-1 violation: county {feat.get('properties', {}).get('COUNTY')!r} "
                f"must be a single exterior Polygon ring (len=1), got type={gtype!r} rings={len(coords)}"
            )
    return counties_geojson


def validate_tract_only_payload(tract_records: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    """FORBIDDEN-PRIV-1 validator: static output holds only tract-level fields, never block or borrower records."""
    for rec in tract_records:
        leaked = FORBIDDEN_BLOCK_KEYS.intersection(rec.keys())
        if leaked:
            raise BundleSchemaViolation(
                f"FORBIDDEN-PRIV-1 violation: tract record {rec.get('geoid')!r} leaked forbidden block/individual keys {sorted(leaked)}"
            )
    return tract_records


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
    "POST-ALN-1": Clause(
        "test",
        "A tract is flagged as a dual-gap opportunity (is_dual_gap=True) iff its class is Classic Food Desert, "
        "it has at least SBA_MIN_POPULATION (1,200) residents, AND its SBA 7(a)/504 loans (DS-X5) per "
        "SBA_RATE_PER_RESIDENTS (1,000) residents are at or below the inclusive bottom-quartile cut over the "
        "populated tracts (0.9427; 26 tracts). The static bundle's thresholds carry the cut under "
        "BUNDLE_SBA_RATE_CUT_KEY and the floor under BUNDLE_SBA_MIN_POPULATION_KEY.",
        ("REQ-19",),
    ),
    "POST-ALN-2": Clause(
        "test",
        "A tract is flagged as a transport-gap priority (is_transport_gap=True) iff its class is Classic Food Desert "
        "AND its household no-vehicle rate (DS-X7b) is at or above the inclusive 75th percentile of 6.90% (53 tracts); "
        "it is a triple-gap opportunity (is_triple_gap=True) iff both is_dual_gap and is_transport_gap hold (12 tracts).",
        ("REQ-20",),
    ),
    "POST-ALN-3": Clause(
        "test",
        "Every tract receives a deterministic cross-agency recommended_action recommending mobile pantry deployment "
        "whenever is_transport_gap is True and joint SBA/CDFI outreach whenever is_dual_gap is True.",
        ("REQ-20", "REQ-21"),
    ),
    "POST-ALN-4": Clause(
        "test",
        "Every tract receives a deterministic confidence_level (Not rated when Insufficient data, Lower when "
        "households < 500 or group_quarters_pct > 20.0, Moderate otherwise) and joins median household income "
        "with its 90% margin of error (DS-X28).",
        ("REQ-22",),
    ),
    "POST-GEO-1": Clause(
        "test",
        "The county boundary output contains exactly 4 Central Florida counties, each represented as a single "
        "exterior Polygon ring (len(coordinates) == 1) with zero interior unshared-edge clutter.",
        ("REQ-23",),
    ),
    "FORBIDDEN-PRIV-1": Clause(
        "test",
        "The static Build output contains only tract-level fields and never includes block-level records or "
        "individual borrower names or addresses.",
        ("REQ-4", "REQ-17"),
    ),
    "ERRORS-BLD-1": Clause(
        "test",
        "When a required Build input file is missing or lacks a required column, the Build raises BundleSchemaViolation "
        "naming the file and column instead of writing partial output.",
        ("REQ-9",),
    ),
}
