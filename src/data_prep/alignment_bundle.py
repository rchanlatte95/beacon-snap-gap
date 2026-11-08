"""Build cross-agency alignment bundle (SLICE-1 batch 2).

Contract-Implementation Independence (CL11-F): this module does NOT import from
contracts/planner_map_contract.py. It redeclares its constants, exception class,
and builders independently; tests assert alignment.
"""

from __future__ import annotations

import csv
import io
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
        (r["storeid"], _parse_float(r["lat"]) or 0.0, _parse_float(r["lng"]) or 0.0)
        for r in site_rows
    ]
    pop_agg: dict[str, dict[str, Any]] = {}
    for b in block_rows:
        g = b["geoid20"][:11]
        pop = _parse_int(b["pop20"]) or 0
        entry = pop_agg.setdefault(g, {"pop": 0, "sites": set(), "lat_w": 0.0, "lon_w": 0.0})
        entry["pop"] += pop
        if pop > 0:
            lat = _parse_float(b["lat"]) or 0.0
            lon = _parse_float(b["lon"]) or 0.0
            entry["lat_w"] += lat * pop
            entry["lon_w"] += lon * pop
            for sid, slat, slon in site_pts:
                if _haversine_miles(lat, lon, slat, slon) <= REACH_MILES:
                    entry["sites"].add(sid)

    sorted_cov = sorted(cov_rows, key=lambda r: r["geoid"])
    poverty_vals = [
        v for r in sorted_cov if (v := _parse_float(r["pct_poverty"])) is not None
    ]
    cut_poverty = poverty_cut(poverty_vals)

    sba_counts = [_parse_int(sba_by_id.get(r["geoid"], {}).get("loans_total")) or 0 for r in sorted_cov]
    sba_median = float(statistics.median(sba_counts))

    nv_vals = [
        v for r in sorted_cov if (v := _parse_float(nv_by_id.get(r["geoid"], {}).get("pct_no_vehicle"))) is not None
    ]
    nv_q75 = statistics.quantiles(nv_vals, n=4, method="inclusive")[2]

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

        pa = pop_agg.get(g, {"pop": 0, "sites": set(), "lat_w": 0.0, "lon_w": 0.0})
        pop2020 = int(pa["pop"])
        sites_in_reach = len(pa["sites"])
        pantry_load = int(round(pop2020 / sites_in_reach)) if sites_in_reach > 0 and pop2020 > 0 else None
        centroid = (
            [round(pa["lon_w"] / pop2020, 4), round(pa["lat_w"] / pop2020, 4)]
            if pop2020 > 0
            else None
        )

        is_high = cls_res.tract_class == CLASS_HIGH_NEED
        is_dual = is_high and loans_total <= sba_median
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
            "sba_loans_median": sba_median,
            "no_vehicle_q75": round(nv_q75, 4),
            "drive_time_minutes": 30,
        },
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
