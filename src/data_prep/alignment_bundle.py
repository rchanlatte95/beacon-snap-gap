"""Build cross-agency alignment bundle (SLICE-1 batch 2).

Contract-Implementation Independence (CL11-F): this module does NOT import from
contracts/planner_map_contract.py. It redeclares its constants, exception class,
and builders independently; tests assert alignment.
"""

from __future__ import annotations

import csv
import bisect
import io
import itertools
import json
import math
import statistics
import zipfile
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from src.data_prep.tract_classification import (
    CLASS_HIGH_NEED,
    CLASS_INSUFFICIENT,
    CLASS_NO_GAP,
    LILA_FLAG_COLUMN,
    classify_tract,
    poverty_cut,
)

# Redeclared constants (POST-ALN-1..4, POST-GEO-1, FORBIDDEN-PRIV-1, ERRORS-BLD-1)
CONFIDENCE_NOT_RATED = "Not rated"
CONFIDENCE_LOWER = "Lower"
CONFIDENCE_MODERATE = "Moderate"
CONFIDENCE_MIN_HOUSEHOLDS = 500
CONFIDENCE_MAX_GROUP_QUARTERS_PCT = 20.0

# POST-ALN-1 (REQ-19, Z-23): SBA loans per 1,000 residents in the bottom quartile, for tracts of
# at least 1,200 residents.
SBA_RATE_PER_RESIDENTS = 1000
SBA_MIN_POPULATION = 1200

ACTION_MOBILE_AND_SBA = "Mobile Pantry Deployment + Joint SBA/CDFI Micro-Lending Outreach"
ACTION_MOBILE_PANTRY = "Mobile Pantry / Transit-Accessible Food Deployment"
ACTION_FIXED_AND_SBA = "Partner Pantry Expansion + SBA/SBDC Small-Business Outreach"
ACTION_PARTNER_PANTRY = "Partner Pantry Capacity & Hours Support"
ACTION_DATA_AUDIT = "Field Verification & Data Gap Audit"
ACTION_MONITOR = "Standard Monitoring (No Gap Flagged)"

FORBIDDEN_BLOCK_KEYS = frozenset(
    {"block_id", "geoid20", "blocks", "block_records", "borrower_name", "borrower_address"}
)

COUNTIES = {"069": "Lake", "095": "Orange", "097": "Osceola", "117": "Seminole"}
REACH_MILES = 10.0
EARTH_RADIUS_MI = 3958.8

# POST-RCH-1 (REQ-55, Z-2 2-A): reach at every 0.5-mile step from 0 to 20 miles, from block points.
REACH_STEP_MILES = 0.5
MAX_REACH_MILES = 20.0
REACH_STEPS_MILES: tuple[float, ...] = tuple(
    k * REACH_STEP_MILES for k in range(int(MAX_REACH_MILES / REACH_STEP_MILES) + 1)
)
REACH_MILES_INDEX = REACH_STEPS_MILES.index(REACH_MILES)

# POST-CUT-1 (REQ-58, Z-24 A): inclusive percentile cuts the App can choose from.
PERCENTILE_QUANTILE_N = 100
TOP_CUT_PERCENTILES: tuple[int, ...] = (50, 75, 90)  # poverty and household no-vehicle rates
SBA_CUT_PERCENTILES: tuple[int, ...] = (10, 25, 50)  # SBA loans per 1,000 residents

# POST-SRC-1 / ERRORS-BLD-2 (REQ-61): the App's source list comes from one table in the register.
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


class BundleSchemaViolation(Exception):
    """FORBIDDEN-PRIV-1 / ERRORS-BLD-1: raised on missing input/column or leaked block/borrower fields."""


def _parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "").strip()
    if s in ("", "-", "N", "(X)", "nan", "NaN", "None") or "*" in s:
        return None
    try:
        v = float(s)
        return None if math.isnan(v) or math.isinf(v) else v
    except ValueError:
        return None


def _parse_int(val: Any) -> Optional[int]:
    f = _parse_float(val)
    return int(round(f)) if f is not None else None


def _read_csv_required(path: Path, required_columns: Sequence[str]) -> list[dict[str, str]]:
    """ERRORS-BLD-1: read CSV or raise BundleSchemaViolation naming the file and column."""
    if not path.is_file():
        raise BundleSchemaViolation(
            f"ERRORS-BLD-1 violation: required input file {path.name!r} is missing at {path}"
        )
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or ())
        for col in required_columns:
            if col not in fields:
                raise BundleSchemaViolation(
                    f"ERRORS-BLD-1 violation: input file {path.name!r} is missing required column {col!r}"
                )
        return list(reader)


def _read_zip_csv_required(
    zip_path: Path,
    entry_name: str,
    required_columns: Sequence[str],
    encoding: str = "utf-8-sig",
) -> list[dict[str, str]]:
    if not zip_path.is_file():
        raise BundleSchemaViolation(
            f"ERRORS-BLD-1 violation: required zip input {zip_path.name!r} is missing at {zip_path}"
        )
    with zipfile.ZipFile(zip_path, "r") as zf:
        if entry_name not in zf.namelist():
            raise BundleSchemaViolation(
                f"ERRORS-BLD-1 violation: zip {zip_path.name!r} is missing entry {entry_name!r}"
            )
        raw = zf.read(entry_name).decode(encoding, errors="replace")
        reader = csv.DictReader(io.StringIO(raw))
        fields = set(reader.fieldnames or ())
        for col in required_columns:
            if col not in fields:
                raise BundleSchemaViolation(
                    f"ERRORS-BLD-1 violation: zip entry {entry_name!r} is missing required column {col!r}"
                )
        return list(reader)


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180.0
    a = (
        math.sin((lat2 - lat1) * p / 2.0) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def read_source_catalog(path: Path) -> list[dict[str, str]]:
    """POST-SRC-1 / ERRORS-BLD-2: the cited sources, in CITED_SOURCE_IDS order, from the catalog table.

    The table follows SOURCE_CATALOG_HEADING: a header row of SOURCE_CATALOG_COLUMNS, a separator row,
    then one row per source, up to the first line that does not start with "|".
    """
    if not path.is_file():
        raise BundleSchemaViolation(f"ERRORS-BLD-2 violation: source catalog {path} is missing")
    lines = path.read_text(encoding="utf-8").splitlines()
    if SOURCE_CATALOG_HEADING not in lines:
        raise BundleSchemaViolation(
            f"ERRORS-BLD-2 violation: {path.name} has no {SOURCE_CATALOG_HEADING!r}"
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
            f"ERRORS-BLD-2 violation: the catalog header must be {SOURCE_CATALOG_COLUMNS}, "
            f"got {cells[:1]}"
        )
    entries: dict[str, dict[str, str]] = {}
    for row in cells[2:]:
        if len(row) != len(SOURCE_CATALOG_COLUMNS) or not all(row):
            raise BundleSchemaViolation(f"ERRORS-BLD-2 violation: catalog row {row} is incomplete")
        if row[0] in entries:
            raise BundleSchemaViolation(f"ERRORS-BLD-2 violation: catalog ID {row[0]} repeats")
        entries[row[0]] = dict(zip(SOURCE_ENTRY_KEYS, row, strict=True))
    missing = [i for i in CITED_SOURCE_IDS if i not in entries]
    if missing:
        raise BundleSchemaViolation(
            f"ERRORS-BLD-2 violation: cited sources {missing} have no catalog row"
        )
    return [entries[i] for i in CITED_SOURCE_IDS]


def compute_reach(
    blocks: Sequence[tuple[float, float, int]],
    sites: Sequence[tuple[float, float]],
) -> tuple[list[Optional[float]], list[int], Optional[float]]:
    """POST-RCH-1: one tract's reach at every step of REACH_STEPS_MILES.

    `blocks` are the tract's 2020 blocks (lat, lon, pop); only populated blocks count. `sites` are the
    Second Harvest sites (lat, lon). Returns, per step, the share of block population whose nearest
    site is at most that far, the number of sites at most that far from a populated block, and the
    smallest block-to-nearest-site distance. All distances are straight-line miles.
    """
    populated = [(lat, lon, pop) for lat, lon, pop in blocks if pop > 0]
    total = sum(pop for _, _, pop in populated)
    if not populated or not sites:
        share: Optional[float] = None if total == 0 else 0.0
        return [share] * len(REACH_STEPS_MILES), [0] * len(REACH_STEPS_MILES), None
    block_nearest: list[tuple[float, int]] = []
    site_nearest = [math.inf] * len(sites)
    for lat, lon, pop in populated:
        row = [_haversine_miles(lat, lon, slat, slon) for slat, slon in sites]
        block_nearest.append((min(row), pop))
        site_nearest = [min(a, b) for a, b in zip(site_nearest, row, strict=True)]
    block_nearest.sort()
    block_miles = [d for d, _ in block_nearest]
    people_within = list(itertools.accumulate(pop for _, pop in block_nearest))
    site_miles = sorted(site_nearest)
    shares: list[Optional[float]] = []
    counts: list[int] = []
    for step in REACH_STEPS_MILES:
        n = bisect.bisect_right(block_miles, step)
        shares.append((people_within[n - 1] if n else 0) / total)
        counts.append(bisect.bisect_right(site_miles, step))
    return shares, counts, block_miles[0]


def compute_cuts(
    poverty_rates: Sequence[float],
    no_vehicle_rates: Sequence[float],
    sba_rates: Sequence[float],
) -> dict[str, dict[str, float]]:
    """POST-CUT-1: the cut at each named percentile (inclusive method, n=100, index p - 1)."""

    def at(values: Sequence[float], p: int) -> float:
        return statistics.quantiles(values, n=PERCENTILE_QUANTILE_N, method="inclusive")[p - 1]

    return {
        "poverty": {str(p): at(poverty_rates, p) for p in TOP_CUT_PERCENTILES},
        "no_vehicle": {str(p): at(no_vehicle_rates, p) for p in TOP_CUT_PERCENTILES},
        "sba_rate_per_1000": {str(p): at(sba_rates, p) for p in SBA_CUT_PERCENTILES},
    }


def compute_confidence(
    tract_class: str,
    households: Optional[int],
    group_quarters_pct: Optional[float],
    income_moe90: Optional[float],
) -> tuple[str, str]:
    """POST-ALN-4: deterministic confidence level and plain-language reason."""
    if tract_class == CLASS_INSUFFICIENT:
        return (
            CONFIDENCE_NOT_RATED,
            "Core classification indicator is blank in the source tables, so no gap class is assigned.",
        )
    if households is None or households < CONFIDENCE_MIN_HOUSEHOLDS:
        return (
            CONFIDENCE_LOWER,
            f"Fewer than {CONFIDENCE_MIN_HOUSEHOLDS} households ({households or 0}), so ACS sample estimates carry wider uncertainty.",
        )
    if group_quarters_pct is not None and group_quarters_pct > CONFIDENCE_MAX_GROUP_QUARTERS_PCT:
        return (
            CONFIDENCE_LOWER,
            f"{group_quarters_pct:.1f}% of residents live in group quarters (e.g. dorms or facilities), which ACS household rates omit.",
        )
    moe_note = (
        f" Median income 90% MOE is ±${int(round(income_moe90)):,}."
        if income_moe90 is not None
        else ""
    )
    return (
        CONFIDENCE_MODERATE,
        f"ACS 5-year tract estimate across {households:,} households.{moe_note}",
    )


def compute_recommended_action(
    tract_class: str,
    is_dual_gap: bool,
    is_transport_gap: bool,
) -> str:
    """POST-ALN-3: deterministic cross-agency intervention recommendation."""
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


def assert_tract_only_records(records: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    """FORBIDDEN-PRIV-1: reject any record containing block-level or individual borrower keys."""
    for rec in records:
        leaked = FORBIDDEN_BLOCK_KEYS.intersection(rec.keys())
        if leaked:
            raise BundleSchemaViolation(
                f"FORBIDDEN-PRIV-1 violation: tract record {rec.get('geoid')!r} leaked forbidden keys {sorted(leaked)}"
            )
    return records


def build_alignment_bundle(repo_root: Path) -> dict[str, Any]:
    """Build the complete 490-tract Opportunities to Serve alignment bundle and GeoJSON layers."""
    ext_dir = repo_root / "data" / "external"
    hack_dir = repo_root / "data" / "hackathon" / "beacon-example-datasets"

    cov_rows = _read_csv_required(
        ext_dir / "second-harvest-food-finder" / "central_fl_tract_pantry_coverage.csv",
        ("geoid", "NAME", "households", "snap_households", "pct_hh_snap", "pct_poverty", "second_harvest_sites"),
    )
    sba_rows = _read_csv_required(
        ext_dir / "sba-loans" / "sba_loans_by_tract_central_fl.csv",
        ("geoid", "loans_total", "gross_usd_total", "jobs_supported_total"),
    )
    nv_rows = _read_csv_required(
        ext_dir / "census-acs" / "acs2024_b08201_no_vehicle_central_fl_tracts.csv",
        ("geoid", "pct_no_vehicle"),
    )
    inc_rows = _read_csv_required(
        ext_dir / "census-acs" / "acs2024_s1901_median_household_income_central_fl_tracts.csv",
        ("geoid", "median_household_income", "median_household_income_moe90", "income_status"),
    )
    nri_rows = _read_csv_required(
        ext_dir / "fema-nri" / "fema_nri_central_fl_tracts.csv",
        ("TRACTFIPS", "RISK_RATNG", "SOVI_RATNG"),
    )
    site_rows = _read_csv_required(
        ext_dir / "second-harvest-food-finder" / "second_harvest_food_finder_locations.csv",
        ("storeid", "name", "address", "hours_text", "lat", "lng", "tract_geoid", "county"),
    )
    block_rows = _read_csv_required(
        ext_dir / "census-2020-blocks" / "central-fl-blocks-2020.csv",
        ("geoid20", "pop20", "lat", "lon"),
    )
    cbpp_rows = _read_csv_required(
        ext_dir / "cbpp-snap-tracker" / "cbpp_florida_snap_monthly.csv",
        ("month", "usda_total_participants"),
    )
    meal_rows = _read_csv_required(
        ext_dir / "feeding-america" / "feeding_america_map_the_meal_gap_2024_central_fl_counties.csv",
        ("county", "demographic", "food_insecurity_rate", "food_insecure_population"),
    )

    sram_zip = hack_dir / "Low Grocery Access - 1_2 or 10 miles_2025-sram-fara-data.zip"
    sram_dd_rows = _read_zip_csv_required(
        sram_zip,
        "SRAM Driving Distance Data.csv",
        ("CensusTract20", LILA_FLAG_COLUMN),
        encoding="latin-1",
    )
    sram_gen_rows = _read_zip_csv_required(
        sram_zip,
        "SRAM General Tract Characteristics Data.csv",
        ("CensusTract20", "Urban", "PCTGQTRS"),
        encoding="latin-1",
    )

    tracts_geojson_path = ext_dir / "geography" / "central_fl_tracts_2020.geojson"
    counties_geojson_path = ext_dir / "geography" / "central_fl_counties_2020.geojson"
    if not tracts_geojson_path.is_file() or not counties_geojson_path.is_file():
        raise BundleSchemaViolation("ERRORS-BLD-1 violation: required geography GeoJSON file is missing")
    # ERRORS-BLD-2: after the input checks, and before any output exists.
    sources = read_source_catalog(repo_root / "docs" / "data-sources.md")

    tracts_fc = json.loads(tracts_geojson_path.read_text(encoding="utf-8"))
    counties_fc = json.loads(counties_geojson_path.read_text(encoding="utf-8"))

    sba_by_id = {r["geoid"]: r for r in sba_rows}
    nv_by_id = {r["geoid"]: r for r in nv_rows}
    inc_by_id = {r["geoid"]: r for r in inc_rows}
    nri_by_id = {r["TRACTFIPS"]: r for r in nri_rows}
    dd_by_id = {r["CensusTract20"]: r for r in sram_dd_rows}
    gen_by_id = {r["CensusTract20"]: r for r in sram_gen_rows}
    shape_by_id = {f["properties"]["TRACTFIPS"]: f for f in tracts_fc.get("features", [])}

    site_pts = [
        (site_lat, site_lng)
        for r in site_rows
        if (site_lat := _parse_float(r["lat"])) is not None
        and (site_lng := _parse_float(r["lng"])) is not None
    ]
    pop_agg: dict[str, dict[str, Any]] = {}
    blocks_by_tract: dict[str, list[tuple[float, float, int]]] = {}
    for b in block_rows:
        g = b["geoid20"][:11]
        pop = _parse_int(b["pop20"]) or 0
        entry = pop_agg.setdefault(g, {"pop": 0, "lat_w": 0.0, "lon_w": 0.0})
        entry["pop"] += pop
        if pop > 0:
            lat = _parse_float(b["lat"]) or 0.0
            lon = _parse_float(b["lon"]) or 0.0
            entry["lat_w"] += lat * pop
            entry["lon_w"] += lon * pop
            blocks_by_tract.setdefault(g, []).append((lat, lon, pop))

    sorted_cov = sorted(cov_rows, key=lambda r: r["geoid"])
    poverty_vals = [
        v for r in sorted_cov if (v := _parse_float(r["pct_poverty"])) is not None
    ]
    cut_poverty = poverty_cut(poverty_vals)

    sba_counts = [_parse_int(sba_by_id.get(r["geoid"], {}).get("loans_total")) or 0 for r in sorted_cov]
    pops = [int(pop_agg.get(r["geoid"], {"pop": 0})["pop"]) for r in sorted_cov]
    # POST-ALN-1: inclusive bottom-quartile loans per 1,000 residents over the populated tracts.
    sba_rates = [n / p * SBA_RATE_PER_RESIDENTS for n, p in zip(sba_counts, pops, strict=True) if p > 0]
    sba_rate_cut = statistics.quantiles(sba_rates, n=4, method="inclusive")[0]

    nv_vals = [
        v for r in sorted_cov if (v := _parse_float(nv_by_id.get(r["geoid"], {}).get("pct_no_vehicle"))) is not None
    ]
    nv_q75 = statistics.quantiles(nv_vals, n=4, method="inclusive")[2]
    cuts = compute_cuts(poverty_vals, nv_vals, sba_rates)

    tracts_out: list[dict[str, Any]] = []
    for r in sorted_cov:
        g = r["geoid"]
        pct_pov = _parse_float(r["pct_poverty"])
        pct_snap = _parse_float(r["pct_hh_snap"])
        hh = _parse_int(r["households"])
        snap_hh = _parse_int(r["snap_households"])
        sites_in_tract = _parse_int(r["second_harvest_sites"]) or 0
        lila = _parse_int(dd_by_id.get(g, {}).get(LILA_FLAG_COLUMN))

        cls_res = classify_tract(geoid=g, pct_poverty=pct_pov, lila_flag=lila, cut=cut_poverty)

        sba_rec = sba_by_id.get(g, {})
        loans_total = _parse_int(sba_rec.get("loans_total")) or 0
        gross_usd = _parse_float(sba_rec.get("gross_usd_total")) or 0.0
        jobs_sup = _parse_int(sba_rec.get("jobs_supported_total")) or 0

        pct_nv = _parse_float(nv_by_id.get(g, {}).get("pct_no_vehicle"))
        gen_rec = gen_by_id.get(g, {})
        urban = _parse_int(gen_rec.get("Urban"))
        gq_pct = _parse_float(gen_rec.get("PCTGQTRS"))

        inc_rec = inc_by_id.get(g, {})
        med_inc = _parse_float(inc_rec.get("median_household_income"))
        med_inc_moe = _parse_float(inc_rec.get("median_household_income_moe90"))
        inc_status = inc_rec.get("income_status") or "unavailable"

        nri_rec = nri_by_id.get(g, {})
        nri_risk = nri_rec.get("RISK_RATNG") or None
        sovi_rating = nri_rec.get("SOVI_RATNG") or None

        pa = pop_agg.get(g, {"pop": 0, "lat_w": 0.0, "lon_w": 0.0})
        pop2020 = int(pa["pop"])
        reach_share, reach_sites, nearest_block_miles = compute_reach(
            blocks_by_tract.get(g, []), site_pts
        )
        sites_in_reach = reach_sites[REACH_MILES_INDEX]
        pantry_load = int(round(pop2020 / sites_in_reach)) if sites_in_reach > 0 and pop2020 > 0 else None
        centroid = (
            [round(pa["lon_w"] / pop2020, 4), round(pa["lat_w"] / pop2020, 4)]
            if pop2020 > 0
            else None
        )

        is_high = cls_res.tract_class == CLASS_HIGH_NEED
        sba_rate = loans_total / pop2020 * SBA_RATE_PER_RESIDENTS if pop2020 > 0 else None
        is_dual = (
            is_high
            and pop2020 >= SBA_MIN_POPULATION
            and sba_rate is not None
            and sba_rate <= sba_rate_cut
        )
        is_trans = is_high and pct_nv is not None and pct_nv >= nv_q75
        is_triple = is_dual and is_trans

        conf_level, conf_why = compute_confidence(
            tract_class=cls_res.tract_class,
            households=hh,
            group_quarters_pct=gq_pct,
            income_moe90=med_inc_moe,
        )
        rec_action = compute_recommended_action(
            tract_class=cls_res.tract_class,
            is_dual_gap=is_dual,
            is_transport_gap=is_trans,
        )

        missing_list = list(cls_res.missing_indicators)
        if pct_snap is None:
            missing_list.append("pct_hh_snap (ACS S2201)")
        if med_inc is None:
            missing_list.append(f"median_household_income ({inc_status}, ACS S1901/B19013)")
        missing_list.append("CDC PLACES social-needs measures (blank across Florida, F-1)")

        tracts_out.append(
            {
                "geoid": g,
                "name": (r["NAME"] or "").split(";")[0].strip(),
                "county": COUNTIES.get(g[2:5], "Unknown"),
                "tract_class": cls_res.tract_class,
                "drawn": g in shape_by_id,
                "households": hh,
                "snap_households": snap_hh,
                "pct_hh_snap": pct_snap,
                "pct_poverty": pct_pov,
                "lila_flag": lila,
                "sba_loans_total": loans_total,
                "sba_gross_usd_total": gross_usd,
                "sba_jobs_supported": jobs_sup,
                "pct_no_vehicle": pct_nv,
                "median_household_income": med_inc,
                "median_household_income_moe90": med_inc_moe,
                "income_status": inc_status,
                "urban": urban,
                "group_quarters_pct": gq_pct,
                "nri_risk": nri_risk,
                "social_vulnerability": sovi_rating,
                "pop2020": pop2020,
                "sites_in_tract": sites_in_tract,
                "sites_in_reach": sites_in_reach,
                "pantry_load": pantry_load,
                "reach_share": reach_share,
                "reach_sites": reach_sites,
                "nearest_block_miles": nearest_block_miles,
                "is_dual_gap": is_dual,
                "is_transport_gap": is_trans,
                "is_triple_gap": is_triple,
                "confidence_level": conf_level,
                "confidence_reason": conf_why,
                "recommended_action": rec_action,
                "missing_indicators": missing_list,
                "centroid": centroid,
            }
        )

    assert_tract_only_records(tracts_out)

    rec_by_geoid = {t["geoid"]: t for t in tracts_out}
    tract_features = []
    for feat in tracts_fc.get("features", []):
        g = feat["properties"]["TRACTFIPS"]
        t = rec_by_geoid.get(g)
        if not t:
            continue
        tract_features.append(
            {
                "type": "Feature",
                "id": int(g[2:]),
                "properties": {
                    "geoid": g,
                    "tract_class": t["tract_class"],
                    "is_dual_gap": t["is_dual_gap"],
                    "is_transport_gap": t["is_transport_gap"],
                    "is_triple_gap": t["is_triple_gap"],
                    "sba_loans_total": t["sba_loans_total"],
                    "pct_no_vehicle": t["pct_no_vehicle"],
                },
                "geometry": feat["geometry"],
            }
        )

    sites_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "storeid": s["storeid"],
                    "name": s["name"],
                    "address": s["address"],
                    "hours": s["hours_text"],
                    "county": s["county"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [_parse_float(s["lng"]) or 0.0, _parse_float(s["lat"]) or 0.0],
                },
            }
            for s in site_rows
        ],
    }

    counts = {
        "total_tracts": len(tracts_out),
        "drawn_tracts": sum(1 for t in tracts_out if t["drawn"]),
        "high_need": sum(1 for t in tracts_out if t["tract_class"] == CLASS_HIGH_NEED),
        "no_gap": sum(1 for t in tracts_out if t["tract_class"] == CLASS_NO_GAP),
        "insufficient": sum(1 for t in tracts_out if t["tract_class"] == CLASS_INSUFFICIENT),
        "dual_gap": sum(1 for t in tracts_out if t["is_dual_gap"]),
        "transport_gap": sum(1 for t in tracts_out if t["is_transport_gap"]),
        "triple_gap": sum(1 for t in tracts_out if t["is_triple_gap"]),
    }

    return {
        "thresholds": {
            "poverty_cut_q75": round(cut_poverty, 4),
            "poverty_cut_method": "inclusive",
            "sba_rate_cut_per_1000": sba_rate_cut,
            "sba_min_population": SBA_MIN_POPULATION,
            "no_vehicle_q75": round(nv_q75, 4),
            "drive_time_minutes": 30,
            "reach_steps_miles": list(REACH_STEPS_MILES),
            "cuts": cuts,
        },
        "sources": sources,
        "counts": counts,
        "snap_trend": [
            {"month": r["month"], "participants": _parse_int(r["usda_total_participants"])}
            for r in cbpp_rows
        ],
        "meal_gap": [
            {
                "county": r["county"],
                "rate": r["food_insecurity_rate"],
                "people": _parse_int(r["food_insecure_population"]),
            }
            for r in meal_rows
            if r.get("demographic") == "overall"
        ],
        "tracts": tracts_out,
        "tracts_geojson": {"type": "FeatureCollection", "features": tract_features},
        "counties_geojson": counties_fc,
        "sites_geojson": sites_fc,
    }


def write_static_bundle(repo_root: Path) -> dict[str, Any]:
    """Write public/data/tracts.geojson and public/data/planner-bundle.json (Z-5, IP-4)."""
    bundle = build_alignment_bundle(repo_root)
    out_dir = repo_root / "public" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tracts.geojson").write_text(
        json.dumps(bundle["tracts_geojson"], separators=(",", ":")), encoding="utf-8"
    )
    (out_dir / "counties.geojson").write_text(
        json.dumps(bundle["counties_geojson"], separators=(",", ":")), encoding="utf-8"
    )
    (out_dir / "sites.geojson").write_text(
        json.dumps(bundle["sites_geojson"], separators=(",", ":")), encoding="utf-8"
    )
    records_payload = {
        "thresholds": bundle["thresholds"],
        "counts": bundle["counts"],
        "snap_trend": bundle["snap_trend"],
        "meal_gap": bundle["meal_gap"],
        "sources": bundle["sources"],
        "tracts": bundle["tracts"],
    }
    (out_dir / "planner-bundle.json").write_text(
        json.dumps(records_payload, separators=(",", ":")), encoding="utf-8"
    )
    return bundle


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    b = write_static_bundle(root)
    print("Wrote public/data static bundle:", b["counts"])
