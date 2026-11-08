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
- Batch 3 (cycle 17, PR #18 refactor): reach per distance step from block points (REQ-55, Z-2 2-A), gap cuts per
  percentile (REQ-58, Z-24 A) and the source catalog read from docs/data-sources.md (REQ-61).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

# --- 1. Importable constants (specification values) --------------------------------------

CLASS_HIGH_NEED = "Classic Food Desert"
CLASS_NO_GAP = "No gap flagged"
CLASS_INSUFFICIENT = "Insufficient data"
TRACT_CLASSES = (CLASS_HIGH_NEED, CLASS_NO_GAP, CLASS_INSUFFICIENT)

LILA_FLAG_COLUMN = "DD_SRAM_LILATracts_halfAnd10"
QUANTILE_N = 4
QUANTILE_METHOD: Literal["inclusive", "exclusive"] = "inclusive"
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

# Batch 3 / REQ-55 (Z-2 2-A): reach per distance step, straight-line from each populated 2020 block point.
EARTH_RADIUS_MILES = 3958.8
REACH_STEP_MILES = 0.5
MAX_REACH_MILES = 20.0
DEFAULT_REACH_MILES = 10.0
REACH_STEPS_MILES: tuple[float, ...] = tuple(
    k * REACH_STEP_MILES for k in range(int(MAX_REACH_MILES / REACH_STEP_MILES) + 1)
)
BUNDLE_REACH_STEPS_KEY = "reach_steps_miles"  # thresholds: the 41 distances, in order
BUNDLE_REACH_SHARE_KEY = "reach_share"  # tract: share of block population within each step, or None
BUNDLE_REACH_SITES_KEY = (
    "reach_sites"  # tract: distinct sites within each step of a populated block
)
BUNDLE_NEAREST_BLOCK_MILES_KEY = (
    "nearest_block_miles"  # tract: smallest block-to-nearest-site distance, or None
)

# Batch 3 / REQ-58 (Z-24 A): cuts at named percentiles, inclusive method, one computation in the Build.
PERCENTILE_QUANTILE_N = 100  # statistics.quantiles(..., n=100)[p - 1] is the p-th percentile
TOP_CUT_PERCENTILES: tuple[int, ...] = (50, 75, 90)  # poverty and household no-vehicle
SBA_CUT_PERCENTILES: tuple[int, ...] = (10, 25, 50)  # SBA loans per 1,000 residents
DEFAULT_POVERTY_PERCENTILE = 75
DEFAULT_NO_VEHICLE_PERCENTILE = 75
DEFAULT_SBA_PERCENTILE = 25
BUNDLE_CUTS_KEY = "cuts"  # thresholds: {cut name: {str(percentile): cut value}}
CUT_POVERTY = "poverty"
CUT_NO_VEHICLE = "no_vehicle"
CUT_SBA_RATE = "sba_rate_per_1000"

# Batch 3 / REQ-61: the source catalog, one table in docs/data-sources.md, copied into the bundle.
SOURCE_CATALOG_DOC_PATH = "docs/data-sources.md"
SOURCE_CATALOG_HEADING = "## 9. App source catalog"
SOURCE_CATALOG_COLUMNS: tuple[str, ...] = (
    "ID",
    "Label",
    "Publisher",
    "Period",
    "URL",
    "Method",
    "Limits",
)
SOURCE_ENTRY_KEYS: tuple[str, ...] = (
    "id",
    "label",
    "publisher",
    "period",
    "url",
    "method",
    "limits",
)
BUNDLE_SOURCES_KEY = "sources"  # bundle top level: entries in CITED_SOURCE_IDS order
CITED_SOURCE_IDS: tuple[str, ...] = (
    "DS-H1",
    "DS-H2",
    "DS-H6",
    "DS-X5",
    "DS-X7b",
    "DS-X28",
    "DS-X12",
    "DS-X24",
    "DS-X16b",
    "DS-X15b",
    "DS-H7",
    "DS-X3b",
    "DS-X9b",
)

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

FORBIDDEN_BLOCK_KEYS = frozenset(
    {"block_id", "geoid20", "blocks", "block_records", "borrower_name", "borrower_address"}
)


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
    pct_poverty: float | None
    lila_flag: int | None


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
    pct_no_vehicle: float | None
    households: int | None
    group_quarters_pct: float | None
    median_household_income: float | None
    median_household_income_moe90: float | None
    is_dual_gap: bool
    is_transport_gap: bool
    is_triple_gap: bool
    confidence_level: str
    recommended_action: str


@dataclass(frozen=True)
class ReachRecord:
    """Batch 3 / POST-RCH-1: one tract's reach at every step of REACH_STEPS_MILES."""

    share: tuple[float | None, ...]
    sites: tuple[int, ...]
    nearest_block_miles: float | None


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
    if (
        indicators.pct_poverty is not None
        and indicators.pct_poverty >= cut
        and indicators.lila_flag == 1
    ):
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
    return statistics.quantiles(no_vehicle_rates, n=QUANTILE_N, method=QUANTILE_METHOD)[
        POVERTY_CUT_INDEX
    ]


def expected_confidence_level(
    tract_class: str,
    households: int | None,
    group_quarters_pct: float | None,
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
        high_need and record.pct_no_vehicle is not None and record.pct_no_vehicle >= no_vehicle_q75
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
    exp_conf = expected_confidence_level(
        record.tract_class, record.households, record.group_quarters_pct
    )
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


def validate_tract_only_payload(
    tract_records: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    """FORBIDDEN-PRIV-1 validator: static output holds only tract-level fields, never block or borrower records."""
    for rec in tract_records:
        leaked = FORBIDDEN_BLOCK_KEYS.intersection(rec.keys())
        if leaked:
            raise BundleSchemaViolation(
                f"FORBIDDEN-PRIV-1 violation: tract record {rec.get('geoid')!r} leaked forbidden block/individual keys {sorted(leaked)}"
            )
    return tract_records


def expected_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """POST-RCH-1 oracle: haversine straight-line miles on a sphere of EARTH_RADIUS_MILES, this exact formula."""
    p = math.pi / 180.0
    a = (
        math.sin((lat2 - lat1) * p / 2.0) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def expected_reach(
    blocks: Sequence[tuple[float, float, int]],
    sites: Sequence[tuple[str, float, float]],
) -> ReachRecord:
    """POST-RCH-1 oracle: a tract's reach from its 2020 blocks (lat, lon, pop) and the sites (id, lat, lon).

    Only blocks with pop > 0 count. A block is within a step when its distance to its nearest site is at most
    the step (inclusive). A site counts at a step when it is within the step of at least one populated block.
    With no populated block, or no site, every share is None (no population) or 0.0, every site count is 0,
    and nearest_block_miles is None.
    """
    populated = [(lat, lon, pop) for lat, lon, pop in blocks if pop > 0]
    total = sum(pop for _, _, pop in populated)
    if not populated or not sites:
        share: float | None = None if total == 0 else 0.0
        return ReachRecord(
            share=tuple(share for _ in REACH_STEPS_MILES),
            sites=tuple(0 for _ in REACH_STEPS_MILES),
            nearest_block_miles=None,
        )
    block_nearest = [
        (min(expected_distance_miles(lat, lon, slat, slon) for _, slat, slon in sites), pop)
        for lat, lon, pop in populated
    ]
    site_nearest = [
        min(expected_distance_miles(lat, lon, slat, slon) for lat, lon, _ in populated)
        for _, slat, slon in sites
    ]
    return ReachRecord(
        share=tuple(
            sum(pop for d, pop in block_nearest if d <= step) / total for step in REACH_STEPS_MILES
        ),
        sites=tuple(sum(1 for d in site_nearest if d <= step) for step in REACH_STEPS_MILES),
        nearest_block_miles=min(d for d, _ in block_nearest),
    )


def expected_percentile_cut(values: Sequence[float], percentile: int) -> float:
    """POST-CUT-1 oracle: the inclusive p-th percentile (statistics.quantiles n=100, index p - 1)."""
    return statistics.quantiles(values, n=PERCENTILE_QUANTILE_N, method=QUANTILE_METHOD)[
        percentile - 1
    ]


def expected_cuts(
    poverty_rates: Sequence[float],
    no_vehicle_rates: Sequence[float],
    sba_rates: Sequence[float],
) -> dict[str, dict[str, float]]:
    """POST-CUT-1 oracle: the bundle's thresholds.cuts object.

    Inputs are the same value sets as the fixed rule: non-blank poverty rates, non-blank household no-vehicle
    rates, and SBA loans per 1,000 residents over the populated tracts (expected_sba_rate not None).
    """
    return {
        CUT_POVERTY: {
            str(p): expected_percentile_cut(poverty_rates, p) for p in TOP_CUT_PERCENTILES
        },
        CUT_NO_VEHICLE: {
            str(p): expected_percentile_cut(no_vehicle_rates, p) for p in TOP_CUT_PERCENTILES
        },
        CUT_SBA_RATE: {str(p): expected_percentile_cut(sba_rates, p) for p in SBA_CUT_PERCENTILES},
    }


def expected_source_catalog(markdown: str) -> tuple[dict[str, str], ...]:
    """POST-SRC-1 / ERRORS-BLD-2 oracle: the bundle's sources list, read from the catalog table.

    The table follows the line SOURCE_CATALOG_HEADING: a header row of exactly SOURCE_CATALOG_COLUMNS, a
    separator row, then one row per source, ending at the first line that does not start with "|". Cells are
    trimmed and contain no "|". Returns one entry (SOURCE_ENTRY_KEYS) per CITED_SOURCE_IDS, in that order.
    Raises BundleSchemaViolation (ERRORS-BLD-2) when the heading or header is missing or wrong, a row has the
    wrong cell count or an empty cell, an ID repeats, or a cited ID has no row.
    """
    lines = markdown.splitlines()
    if SOURCE_CATALOG_HEADING not in lines:
        raise BundleSchemaViolation(
            f"ERRORS-BLD-2 violation: {SOURCE_CATALOG_DOC_PATH} has no {SOURCE_CATALOG_HEADING!r}"
        )
    table: list[str] = []
    for line in lines[lines.index(SOURCE_CATALOG_HEADING) + 1 :]:
        if line.startswith("|"):
            table.append(line)
        elif table:
            break
    cells = [[c.strip() for c in row.strip().strip("|").split("|")] for row in table]
    if len(cells) < 2 or tuple(cells[0]) != SOURCE_CATALOG_COLUMNS:
        raise BundleSchemaViolation(
            f"ERRORS-BLD-2 violation: the catalog header must be {SOURCE_CATALOG_COLUMNS}, got {cells[:1]}"
        )
    rows: dict[str, dict[str, str]] = {}
    for row in cells[2:]:
        if len(row) != len(SOURCE_CATALOG_COLUMNS) or not all(row):
            raise BundleSchemaViolation(f"ERRORS-BLD-2 violation: catalog row {row} is incomplete")
        if row[0] in rows:
            raise BundleSchemaViolation(f"ERRORS-BLD-2 violation: catalog ID {row[0]} repeats")
        rows[row[0]] = dict(zip(SOURCE_ENTRY_KEYS, row, strict=True))
    missing = [i for i in CITED_SOURCE_IDS if i not in rows]
    if missing:
        raise BundleSchemaViolation(
            f"ERRORS-BLD-2 violation: cited sources {missing} have no catalog row"
        )
    return tuple(rows[i] for i in CITED_SOURCE_IDS)


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
    "POST-RCH-1": Clause(
        "test",
        f"The bundle's thresholds carry {BUNDLE_REACH_STEPS_KEY} equal to REACH_STEPS_MILES (0 to 20 miles by 0.5), "
        f"and every tract carries {BUNDLE_REACH_SHARE_KEY}, {BUNDLE_REACH_SITES_KEY} and "
        f"{BUNDLE_NEAREST_BLOCK_MILES_KEY} equal to expected_reach over its 2020 blocks and the Second Harvest "
        "sites (Z-2 2-A). The value at index k is for step k, so the App only indexes and never measures.",
        ("REQ-55",),
    ),
    "POST-CUT-1": Clause(
        "test",
        f"The bundle's thresholds carry {BUNDLE_CUTS_KEY} equal to expected_cuts over the fixed rule's value sets. "
        "The cuts at the default percentiles (75, 75, 25) equal the fixed cuts the tract flags use "
        f"(poverty_cut_q75, no_vehicle_q75, {BUNDLE_SBA_RATE_CUT_KEY}).",
        ("REQ-58",),
    ),
    "POST-SRC-1": Clause(
        "test",
        f"The bundle's top-level {BUNDLE_SOURCES_KEY} equals expected_source_catalog({SOURCE_CATALOG_DOC_PATH}): "
        "one entry per cited source, in CITED_SOURCE_IDS order, copied from the catalog table.",
        ("REQ-61",),
    ),
    "ERRORS-BLD-2": Clause(
        "test",
        "When the source catalog is missing, malformed, repeats an ID or lacks a cited ID, the Build raises "
        "BundleSchemaViolation naming ERRORS-BLD-2 and writes no bundle.",
        ("REQ-61", "REQ-9"),
    ),
}
