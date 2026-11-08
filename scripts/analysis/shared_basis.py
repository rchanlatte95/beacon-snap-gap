"""Test the shared-basis candidates for the "Common ground" summary (task N1).

Questions:
1. Which tracts have each Appendix A small-business gap type (Capital Access, Entrepreneurship
   Infrastructure, Credit Access, Underinvestment)?
2. How much do these gap types overlap with the Classic Food Desert class, and how much of that
   overlap is left after the shared poverty input is held constant?
3. Do desert tracts have fewer or more SNAP retailers (DS-H8) per resident than nogap tracts?
4. Does the mortgage denial rate (DS-H9) follow poverty and SNAP share?

The script reads repo files only and prints every number used in docs/analysis/shared-basis.md
and findings F-4 to F-6. It writes one file: docs/analysis/tract_gap_types.csv. It writes
nothing under data/. Method and denominators follow scripts/analysis/need_vs_sba_lending.py (T0).

Run from any directory:
    python -I scripts/analysis/shared_basis.py
"""

from __future__ import annotations

import json
import re
import statistics
import zipfile
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
HACK = ROOT / "data/hackathon/beacon-example-datasets"
RECORDS = ROOT / "docs/mockups/planner-map/data/records.standin.json"
SBA = ROOT / "data/external/sba-loans/sba_loans_by_tract_central_fl.csv"
INCOME = ROOT / "data/external/census-acs/acs2024_s1901_median_household_income_central_fl_tracts.csv"
INCOME_ZIP, INCOME_MEMBER = HACK / "Household Income, Median.zip", "ACSST5Y2024.S1901-Data.csv"
LABOR_ZIP, LABOR_MEMBER = HACK / "Employed and Unemployed, 16+ Labor Force.zip", "ACSDT5Y2024.B23025-Data.csv"
HMDA = HACK / "mortgage_denials_originations_by_tract.xlsx"
RETAILERS = HACK / "SNAP_Retailer_Location_data.csv"
TRACTS_GEOJSON = ROOT / "data/external/geography/central_fl_tracts_2020.geojson"
OUT_CSV = ROOT / "docs/analysis/tract_gap_types.csv"

COUNTIES = {"12095": "Orange", "12117": "Seminole", "12069": "Lake", "12097": "Osceola"}
RETAILER_COUNTY_NAMES = {"ORANGE", "SEMINOLE", "LAKE", "OSCEOLA"}

# Thresholds chosen by this analysis (stated in the note; a human must approve them, H-5).
QUANTILE_METHOD = "inclusive"  # statistics.quantiles(n=4, method="inclusive"), as in the class rule.
MIN_APPLICATIONS = 20  # HMDA: fewer originated + denied applications than this = insufficient data.
POP_FLOOR = 2000  # Sensitivity only: the S5 stand-in floor and the T0 check.

GAP_TYPES = {
    "capital_access_gap": "Capital Access Gap",
    "entrepreneurship_infrastructure_gap": "Entrepreneurship Infrastructure Gap",
    "credit_access_gap": "Credit Access Gap",
    "underinvestment_gap": "Underinvestment Gap",
}
YES, NO, INSUF = "yes", "no", "insufficient data"
FULL_LINE = {"Supermarket", "Super Store"}
CHAIN_OTHER = re.compile(r"^(walgreen|cvs|dollar ?tree|dollar general|family dollar)", re.I)


# --- helpers ------------------------------------------------------------------------------


def fmt_p(p: float) -> str:
    return f"{p:.2g}" if p >= 0.0001 else f"{p:.1e}"


def quartiles(values: pd.Series) -> list[float]:
    """Q1, Q2, Q3 by the inclusive method, over the non-missing values."""
    v = [float(x) for x in values.dropna()]
    return statistics.quantiles(v, n=4, method=QUANTILE_METHOD)


def cond(series: pd.Series, test) -> pd.Series:
    """Three-valued condition: True, False, or None when the input is missing."""
    return series.map(lambda x: None if pd.isna(x) else bool(test(x)))


def and3(*parts: pd.Series) -> pd.Series:
    def f(vals):
        if any(v is False for v in vals):
            return False
        if any(v is None for v in vals):
            return None
        return True
    return pd.Series([f(v) for v in zip(*parts)], index=parts[0].index, dtype=object)


def or3(*parts: pd.Series) -> pd.Series:
    def f(vals):
        if any(v is True for v in vals):
            return True
        if any(v is None for v in vals):
            return None
        return False
    return pd.Series([f(v) for v in zip(*parts)], index=parts[0].index, dtype=object)


def label(s: pd.Series) -> pd.Series:
    return s.map(lambda v: INSUF if v is None else (YES if v else NO))


def iqr(s: pd.Series, nd: int = 2) -> str:
    return f"{s.median():.{nd}f} [{s.quantile(0.25):.{nd}f} to {s.quantile(0.75):.{nd}f}]"


def point_in_ring(x: float, y: float, ring: list) -> bool:
    """Ray casting (even-odd) for one closed ring of [lon, lat] points."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygon(x: float, y: float, rings: list) -> bool:
    """Polygon with holes: inside the outer ring and outside every hole (even-odd over rings)."""
    inside = False
    for ring in rings:
        if point_in_ring(x, y, ring):
            inside = not inside
    return inside


# --- loading ------------------------------------------------------------------------------


def load_records() -> tuple[pd.DataFrame, dict]:
    rec = json.loads(RECORDS.read_text(encoding="utf-8"))
    tr = pd.DataFrame(rec["tracts"])
    assert len(tr) == 490 and tr.geoid.is_unique
    assert tr.cls.value_counts().to_dict() == {"nogap": 391, "desert": 97, "insufficient": 2}
    return tr[["geoid", "county", "cls", "pctSnap", "pctPoverty", "lilaDD", "urban", "pop2020", "households"]], rec["povertyCut"]


def load_sba() -> pd.DataFrame:
    sba = pd.read_csv(SBA, dtype={"geoid": str})
    assert len(sba) == 490 and sba.geoid.is_unique and int(sba.loans_total.sum()) == 6994
    return sba[["geoid", "loans_total"]]


def load_labor() -> pd.DataFrame:
    with zipfile.ZipFile(LABOR_ZIP) as z, z.open(LABOR_MEMBER) as f:
        lab = pd.read_csv(f, skiprows=[1], dtype={"GEO_ID": str})
    lab["geoid"] = lab.GEO_ID.str[-11:]
    lab = lab[lab.geoid.str[:5].isin(COUNTIES)].copy()
    assert len(lab) == 490 and lab.geoid.is_unique, "B23025: expected 490 Central FL tracts"
    out = pd.DataFrame({
        "geoid": lab.geoid,
        "pop16": pd.to_numeric(lab.B23025_001E, errors="coerce"),
        "labor_force": pd.to_numeric(lab.B23025_002E, errors="coerce"),
        "civ_labor_force": pd.to_numeric(lab.B23025_003E, errors="coerce"),
        "employed": pd.to_numeric(lab.B23025_004E, errors="coerce"),
        "unemployed": pd.to_numeric(lab.B23025_005E, errors="coerce"),
        "unemployed_moe": pd.to_numeric(lab.B23025_005M, errors="coerce"),
        "labor_force_moe": pd.to_numeric(lab.B23025_002M, errors="coerce"),
    })
    clf = out.civ_labor_force.where(out.civ_labor_force > 0)
    out["unemployment_rate"] = out.unemployed / clf * 100
    out["employment_pop_ratio"] = out.employed / out.pop16.where(out.pop16 > 0) * 100
    out["employed_share_of_clf"] = out.employed / clf * 100
    return out


def load_income() -> tuple[pd.DataFrame, dict]:
    inc = pd.read_csv(INCOME, dtype={"geoid": str})
    assert len(inc) == 490 and inc.geoid.is_unique
    # A lower-bound value ("250,000+") is kept at its bound. It is far above any median, so the
    # at-or-above-median test is known for that tract.
    inc["median_household_income"] = inc.median_household_income.fillna(inc.median_household_income_lower_bound)
    # Cross-check against the hackathon DS-H3 zip.
    with zipfile.ZipFile(INCOME_ZIP) as z, z.open(INCOME_MEMBER) as f:
        h3 = pd.read_csv(f, skiprows=[1], usecols=["GEO_ID", "S1901_C01_012E"], dtype=str)
    h3["geoid"] = h3.GEO_ID.str[-11:]
    h3 = h3[h3.geoid.str[:5].isin(COUNTIES)]
    chk = inc.merge(h3, on="geoid", how="left", validate="1:1")
    pub = chk[chk.income_status == "published"]
    agree = (pd.to_numeric(pub.S1901_C01_012E, errors="coerce") == pub.median_household_income).sum()
    info = {
        "status": inc.income_status.value_counts().to_dict(),
        "h3_rows": len(h3),
        "published_agree": int(agree),
        "published_n": len(pub),
        "rel_moe_median": float((inc.median_household_income_moe90 / inc.median_household_income).median()),
    }
    return inc[["geoid", "median_household_income", "income_status", "median_household_income_moe90"]], info


def load_hmda() -> tuple[pd.DataFrame, dict]:
    readme = pd.read_excel(HMDA, sheet_name="README", header=None)[0].dropna().tolist()
    m = pd.read_excel(HMDA, sheet_name="Data", dtype={"census_tract": str, "county_fips": str})
    info = {"sheets": pd.ExcelFile(HMDA).sheet_names, "rows_all": len(m),
            "areas_fl": m[m.area.str.startswith("Central FL")].area.value_counts().to_dict(),
            "readme_source": next(s for s in readme if s.startswith("FFIEC")),
            "readme_quality": next(s for s in readme if s.startswith("538 applications"))}
    m = m[m.county_fips.isin(COUNTIES)].copy()
    assert m.census_tract.is_unique
    m["denial_rate_check"] = m.mortgage_denials / (m.mortgage_denials + m.mortgages_originated)
    info["max_rate_diff"] = float((m.denial_rate_check - m.denial_rate).abs().max())
    info["apps_total_check"] = bool((m.total_applications == m.mortgage_denials + m.mortgages_originated).all())
    info["rows_4cty"] = len(m)
    m = m.rename(columns={"census_tract": "geoid"})
    return m[["geoid", "mortgages_originated", "mortgage_denials", "total_applications", "denial_rate_check"]], info


def load_retailers(tract_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    r = pd.read_csv(RETAILERS, dtype=str, encoding="utf-8-sig")
    info = {"rows": len(r), "columns": list(r.columns)}
    fl = r[r.State == "FL"].copy()
    info["fl"] = len(fl)
    fl["lat"] = pd.to_numeric(fl.Latitude, errors="coerce")
    fl["lon"] = pd.to_numeric(fl.Longitude, errors="coerce")
    info["fl_no_coords"] = int(fl[["lat", "lon"]].isna().any(axis=1).sum())

    gj = json.loads(TRACTS_GEOJSON.read_text(encoding="utf-8"))
    polys = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        parts = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for rings in parts:
            xs = [p[0] for p in rings[0]]
            ys = [p[1] for p in rings[0]]
            polys.append((feat["properties"]["TRACTFIPS"], rings, min(xs), max(xs), min(ys), max(ys)))
    info["polygons"] = len(polys)
    info["geojson_tracts"] = len({p[0] for p in polys})
    assert {p[0] for p in polys} <= tract_ids

    hits = []
    multi = 0
    for row in fl.dropna(subset=["lat", "lon"]).itertuples():
        found = [g for g, rings, x0, x1, y0, y1 in polys
                 if x0 <= row.lon <= x1 and y0 <= row.lat <= y1 and point_in_polygon(row.lon, row.lat, rings)]
        if len(set(found)) > 1:
            multi += 1
        if found:
            hits.append((row.Record_ID, found[0]))
    info["multi_match"] = multi
    joined = fl.merge(pd.DataFrame(hits, columns=["Record_ID", "geoid"]), on="Record_ID", how="inner")
    info["in_tracts"] = len(joined)
    info["county_field_4cty"] = int(fl.County.isin(RETAILER_COUNTY_NAMES).sum())
    info["pip_and_county_field"] = int(joined.County.isin(RETAILER_COUNTY_NAMES).sum())
    info["county_field_outside"] = info["county_field_4cty"] - info["pip_and_county_field"]
    info["pip_other_county_field"] = joined.loc[~joined.County.isin(RETAILER_COUNTY_NAMES), "County"].value_counts().to_dict()
    info["types"] = joined.Store_Type.value_counts().to_dict()
    info["types_national"] = r.Store_Type.value_counts().to_dict()
    other = joined[joined.Store_Type == "Other"]
    info["other_chain"] = int(other.Store_Name.str.match(CHAIN_OTHER).sum())
    info["other_n"] = len(other)
    info["incentive"] = joined.Incentive_Program.value_counts().to_dict()
    info["grantee"] = int(joined.Grantee_Name.notna().sum())
    info["date_columns"] = [c for c in r.columns if re.search(r"date|year|auth|period", c, re.I)]

    joined["full_line"] = joined.Store_Type.isin(FULL_LINE)
    per = joined.groupby("geoid").agg(retailers=("Record_ID", "size"), retailers_full_line=("full_line", "sum")).reset_index()
    return per, joined, info


# --- main ---------------------------------------------------------------------------------


def main() -> None:
    tr, pc = load_records()
    sba = load_sba()
    lab = load_labor()
    inc, inc_info = load_income()
    hm, hm_info = load_hmda()
    per, joined, ri = load_retailers(set(tr.geoid))

    df = (tr.merge(sba, on="geoid", how="left", validate="1:1")
          .merge(lab, on="geoid", how="left", validate="1:1")
          .merge(inc, on="geoid", how="left", validate="1:1")
          .merge(hm, on="geoid", how="left", validate="1:1")
          .merge(per, on="geoid", how="left", validate="1:1"))
    assert len(df) == 490
    df["retailers"] = df.retailers.fillna(0).astype(int)
    df["retailers_full_line"] = df.retailers_full_line.fillna(0).astype(int)
    pop = df.pop2020.where(df.pop2020 > 0)
    df["sba_loans_per_1000"] = df.loans_total / pop * 1000
    df["retailers_per_1000"] = df.retailers / pop * 1000
    df["full_line_per_1000"] = df.retailers_full_line / pop * 1000
    df["other_types_per_1000"] = (df.retailers - df.retailers_full_line) / pop * 1000
    df["hmda_ok"] = df.total_applications >= MIN_APPLICATIONS
    df["denial_rate"] = df.denial_rate_check.where(df.hmda_ok)

    A = df.cls.isin(["desert", "nogap"]) & (df.pop2020 > 0)
    a = df[A]
    assert len(a) == 488

    print("# Shared basis for the Common ground summary: Appendix A gap types, SNAP retailers, mortgage denials")
    print(f"\nTracts: {len(df)}. Analysis set (class desert or nogap, 2020 population > 0): {len(a)} "
          f"(desert {int((a.cls == 'desert').sum())}, nogap {int((a.cls == 'nogap').sum())}).")
    print(f"Quartile method for every cut: Python statistics.quantiles(n=4, method='{QUANTILE_METHOD}'), "
          f"over the analysis tracts that have a value.")

    # --- Inputs and cuts -------------------------------------------------------------------
    sba_q = quartiles(a.sba_loans_per_1000)
    pov_q = quartiles(a.pctPoverty)
    unemp_q = quartiles(a.unemployment_rate)
    lf_q = quartiles(a.labor_force)
    inc_q = quartiles(a.median_household_income)
    emp_q = quartiles(a.employment_pop_ratio)
    emp2_q = quartiles(a.employed_share_of_clf)
    den_q = quartiles(a.denial_rate)
    den_all_q = quartiles(a.denial_rate_check)
    assert abs(pov_q[2] - pc["value"]) < 1e-9, "poverty Q3 must equal the class-rule cut"

    print("\n## 0. Inputs and cuts\n")
    print("| Input | Source | Analysis tracts with a value | Q1 | Median | Q3 | Cut used |")
    print("|---|---|---|---|---|---|---|")
    rows = [
        ("SBA 7(a)+504 loans per 1,000 residents, all years", "DS-X5 / pop2020", a.sba_loans_per_1000, sba_q,
         f"bottom quartile: <= {sba_q[0]:.3f}; at or above median: >= {sba_q[1]:.3f}"),
        ("Poverty rate (%)", "DS-H2 (stand-in)", a.pctPoverty, pov_q, f"top quartile: >= {pov_q[2]:.3f}"),
        ("Unemployment rate (% of civilian labor force)", "DS-H5 B23025 005/003", a.unemployment_rate, unemp_q,
         f"top quartile: >= {unemp_q[2]:.3f}"),
        ("Labor force, 16+ (persons)", "DS-H5 B23025_002", a.labor_force, lf_q, f"sizable: >= median {lf_q[1]:,.0f}"),
        ("Median household income ($)", "DS-X28 file (S1901)", a.median_household_income, inc_q,
         f"at or above median: >= {inc_q[1]:,.0f}"),
        ("Employment-population ratio (% of 16+)", "DS-H5 B23025 004/001", a.employment_pop_ratio, emp_q,
         f"at or above median: >= {emp_q[1]:.3f}"),
        (f"Mortgage denial rate, tracts with >= {MIN_APPLICATIONS} applications", "DS-H9", a.denial_rate, den_q,
         f"top quartile: >= {den_q[2]:.4f}"),
    ]
    for name, src, s, q, cut in rows:
        print(f"| {name} | {src} | {s.notna().sum()} | {q[0]:,.3f} | {q[1]:,.3f} | {q[2]:,.3f} | {cut} |")
    print(f"\nPoverty Q3 equals the class-rule cut in the stand-in ({pc['value']}%).")
    print(f"Median household income: file status counts {inc_info['status']}. The lower-bound tract is kept at its bound "
          f"($250,000). DS-H3 zip cross-check: {inc_info['published_agree']} of {inc_info['published_n']} published values "
          f"are equal ({inc_info['h3_rows']} DS-H3 rows in the four counties).")
    print(f"HMDA (DS-H9): sheets {hm_info['sheets']}; {hm_info['rows_all']:,} data rows in all areas; "
          f"Central FL areas {hm_info['areas_fl']}. Rows in the four counties: {hm_info['rows_4cty']}. "
          f"Recomputed denials / (denials + originations) against the file's denial_rate: max difference "
          f"{hm_info['max_rate_diff']:.1e}. total_applications = originated + denied in every row: {hm_info['apps_total_check']}.")
    print(f"README source line: {hm_info['readme_source']}")
    print(f"README data quality line: {hm_info['readme_quality']}")
    print(f"Four-county tracts with no HMDA row: {', '.join(df.loc[df.total_applications.isna(), 'geoid'])}.")
    print(f"Analysis tracts with no HMDA row: {int(a.total_applications.isna().sum())} "
          f"({', '.join(a.loc[a.total_applications.isna(), 'geoid'])}). "
          f"With 1 to {MIN_APPLICATIONS - 1} applications: {int(((a.total_applications > 0) & (a.total_applications < MIN_APPLICATIONS)).sum())}. "
          f"Median applications per tract: {a.total_applications.median():.0f}.")
    print(f"Analysis tracts with civilian labor force 0 (no unemployment rate): {int(a.unemployment_rate.isna().sum())}. "
          f"With no median income: {int(a.median_household_income.isna().sum())} "
          f"({', '.join(a.loc[a.median_household_income.isna(), 'geoid'])}).")

    # --- 1. Gap types ----------------------------------------------------------------------
    sba_low = cond(df.sba_loans_per_1000, lambda x: x <= sba_q[0])
    sba_mid = cond(df.sba_loans_per_1000, lambda x: x >= sba_q[1])
    pov_hi = cond(df.pctPoverty, lambda x: x >= pov_q[2])
    unemp_hi = cond(df.unemployment_rate, lambda x: x >= unemp_q[2])
    lf_big = cond(df.labor_force, lambda x: x >= lf_q[1])
    inc_mid = cond(df.median_household_income, lambda x: x >= inc_q[1])
    emp_mid = cond(df.employment_pop_ratio, lambda x: x >= emp_q[1])
    den_hi = cond(df.denial_rate, lambda x: x >= den_q[2])

    g = {
        "capital_access_gap": and3(sba_low, lf_big),
        "entrepreneurship_infrastructure_gap": and3(or3(pov_hi, unemp_hi), sba_low),
        "credit_access_gap": and3(den_hi, sba_mid),
        "underinvestment_gap": and3(inc_mid, emp_mid, sba_low),
    }
    # Sensitivity variants.
    pop_big = cond(df.pop2020, lambda x: x >= POP_FLOOR)
    emp2_mid = cond(df.employed_share_of_clf, lambda x: x >= emp2_q[1])
    den_all_hi = cond(df.denial_rate_check, lambda x: x >= den_all_q[2])
    county_den_q3 = {c: quartiles(a.loc[a.county == c, "denial_rate"])[2] for c in COUNTIES.values()}
    den_cty_hi = pd.Series([None if pd.isna(v) else bool(v >= county_den_q3[c])
                            for v, c in zip(df.denial_rate, df.county)], index=df.index)
    variants = {
        f"Capital Access Gap, sizable = 2020 population >= {POP_FLOOR:,}": and3(sba_low, pop_big),
        "Capital Access Gap, no size condition": and3(sba_low),
        "Entrepreneurship Infrastructure Gap, poverty only (no unemployment)": and3(pov_hi, sba_low),
        "Credit Access Gap, no application floor": and3(den_all_hi, sba_mid),
        "Credit Access Gap, denial-rate Q3 within each county": and3(den_cty_hi, sba_mid),
        "Underinvestment Gap, employment = employed / civilian labor force": and3(inc_mid, emp2_mid, sba_low),
    }
    insuff = df.cls == "insufficient"
    for k in g:
        g[k] = pd.Series([None if bad else v for v, bad in zip(g[k], insuff)], index=df.index, dtype=object)
        df[k] = label(g[k])
    for k in variants:
        variants[k] = pd.Series([None if bad else v for v, bad in zip(variants[k], insuff)], index=df.index, dtype=object)

    a = df[A]
    print("\n## 1. Appendix A gap types (488 analysis tracts)\n")
    print("Logic: a tract is 'no' when any known condition fails; 'insufficient data' when no known condition fails "
          "but at least one cannot be checked; 'yes' when all conditions hold. The 2 class-insufficient tracts are "
          "'insufficient data' for every type.\n")
    print("| Gap type | Rule as coded | Yes | No | Insufficient data |")
    print("|---|---|---|---|---|")
    rules = {
        "capital_access_gap": f"loans per 1,000 <= {sba_q[0]:.3f} AND labor force >= {lf_q[1]:,.0f}",
        "entrepreneurship_infrastructure_gap": f"(poverty >= {pov_q[2]:.3f}% OR unemployment >= {unemp_q[2]:.3f}%) AND loans per 1,000 <= {sba_q[0]:.3f}",
        "credit_access_gap": f"denial rate >= {den_q[2]:.4f} (>= {MIN_APPLICATIONS} applications) AND loans per 1,000 >= {sba_q[1]:.3f}",
        "underinvestment_gap": f"income >= ${inc_q[1]:,.0f} AND employment-population ratio >= {emp_q[1]:.3f}% AND loans per 1,000 <= {sba_q[0]:.3f}",
    }
    for k, nm in GAP_TYPES.items():
        vc = a[k].value_counts()
        print(f"| {nm} | {rules[k]} | {vc.get(YES, 0)} | {vc.get(NO, 0)} | {vc.get(INSUF, 0)} |")
    n_types = sum((a[k] == YES).astype(int) for k in GAP_TYPES)
    print("\nTracts by number of gap types: " + ", ".join(f"{i}: {int((n_types == i).sum())}" for i in range(5)) + ".")
    nlow = int(sba_low[A].isin([True]).sum())
    print(f"Tracts with SBA loans per 1,000 in the bottom quartile: {nlow} of {len(a)} ({nlow / len(a):.1%}).")

    # --- 2. Overlap with Classic Food Desert -----------------------------------------------
    top = a.pctPoverty >= pov_q[2]
    print("\n## 2. Overlap with Classic Food Desert\n")
    print(f"Top poverty quartile (poverty >= {pov_q[2]:.3f}%): {int(top.sum())} tracts "
          f"(desert {int((top & (a.cls == 'desert')).sum())}, nogap {int((top & (a.cls == 'nogap')).sum())}). "
          f"Every desert tract is in it by the class rule: {bool((a[a.cls == 'desert'].pctPoverty >= pov_q[2]).all())}. "
          f"Inside it, desert = LILA flag 1 and nogap = LILA flag 0: "
          f"{bool(((a[top].cls == 'desert') == (a[top].lilaDD == 1)).all())}.")
    n_fisher = 2 * len(GAP_TYPES)
    print(f"Fisher exact tests in this section: {n_fisher}. Bonferroni threshold: {0.05 / n_fisher:.4f}. "
          "Shares use tracts with yes or no (insufficient data excluded).\n")
    print("| Gap type | Scope | Desert yes / known | Desert share | Nogap yes / known | Nogap share | Odds ratio | Fisher p |")
    print("|---|---|---|---|---|---|---|---|")
    overlap = {}

    def fisher_row(name: str, scope: str, s: pd.Series) -> tuple:
        d = s[a.cls == "desert"]
        n = s[a.cls == "nogap"]
        d = d[d.isin([YES, NO])]
        n = n[n.isin([YES, NO])]
        t = [[int((d == YES).sum()), int((d == NO).sum())], [int((n == YES).sum()), int((n == NO).sum())]]
        odds, p = stats.fisher_exact(t)
        dsh, nsh = t[0][0] / len(d), t[1][0] / len(n)
        print(f"| {name} | {scope} | {t[0][0]} / {len(d)} | {dsh:.1%} | {t[1][0]} / {len(n)} | {nsh:.1%} | "
              f"{odds:.2f} | {fmt_p(p)} |")
        return t, dsh, nsh, odds, p

    for k, nm in GAP_TYPES.items():
        overlap[(k, "all")] = fisher_row(nm, "All 488 tracts", a[k])
        overlap[(k, "top")] = fisher_row(nm, f"Top poverty quartile ({int(top.sum())})", a.loc[top, k].reindex(a.index))

    d_eig = a[a.cls == "desert"]
    same = ((d_eig.entrepreneurship_infrastructure_gap == YES) == sba_low[d_eig.index].isin([True])).all()
    print(f"\nIn desert tracts, Entrepreneurship Infrastructure Gap = yes exactly when loans per 1,000 is in the bottom "
          f"quartile: {bool(same)}. So its desert overlap is the desert share of bottom-quartile lending: "
          f"{int(sba_low[d_eig.index].isin([True]).sum())} of {len(d_eig)}.")
    nog = a[a.cls == "nogap"]
    print(f"Nogap tracts meeting the poverty-or-unemployment part: {int(or3(pov_hi, unemp_hi)[nog.index].isin([True]).sum())} "
          f"of {len(nog)} (by poverty {int(pov_hi[nog.index].isin([True]).sum())}, by unemployment only "
          f"{int((pov_hi[nog.index].isin([False]) & unemp_hi[nog.index].isin([True])).sum())}).")
    eig_all = a.entrepreneurship_infrastructure_gap == YES
    print(f"Entrepreneurship Infrastructure Gap tracts: {int(eig_all.sum())}; of these, desert {int((eig_all & (a.cls == 'desert')).sum())} "
          f"({(eig_all & (a.cls == 'desert')).sum() / eig_all.sum():.1%}).")

    print("\n### 2b. Sensitivity of the gap-type counts to threshold choices\n")
    print("| Variant | Yes | Insufficient data | Desert yes / known (share) | Nogap yes / known (share) | Fisher p (all 488) |")
    print("|---|---|---|---|---|---|")
    for vn, s in variants.items():
        lab_s = label(s)[A]
        d = lab_s[a.cls == "desert"]
        n = lab_s[a.cls == "nogap"]
        d, n = d[d != INSUF], n[n != INSUF]
        t = [[int((d == YES).sum()), int((d == NO).sum())], [int((n == YES).sum()), int((n == NO).sum())]]
        _, p = stats.fisher_exact(t)
        print(f"| {vn} | {int((lab_s == YES).sum())} | {int((lab_s == INSUF).sum())} | {t[0][0]} / {len(d)} "
              f"({t[0][0] / len(d):.1%}) | {t[1][0]} / {len(n)} ({t[1][0] / len(n):.1%}) | {fmt_p(p)} |")
    print("County denial-rate Q3: " + ", ".join(f"{c} {v:.4f}" for c, v in county_den_q3.items()) + ".")

    # --- 3. SNAP retailers ----------------------------------------------------------------
    print("\n## 3. SNAP retailers (DS-H8)\n")
    print(f"File rows: {ri['rows']:,}. Columns: {', '.join(ri['columns'])}.")
    print(f"Columns whose name suggests a date or period: {ri['date_columns'] or 'none'}.")
    print(f"Florida rows: {ri['fl']:,} (missing coordinates: {ri['fl_no_coords']}). Tract polygons: {ri['polygons']} "
          f"({ri['geojson_tracts']} tracts). Points in more than one polygon: {ri['multi_match']}.")
    print(f"Florida retailers inside a tract polygon: {ri['in_tracts']:,}. Florida rows whose County field is one of "
          f"the four counties: {ri['county_field_4cty']:,}. Inside a polygon and County field one of the four: "
          f"{ri['pip_and_county_field']:,}. County field one of the four but inside no polygon: {ri['county_field_outside']}. Inside a polygon with another County field: {ri['pip_other_county_field']}.")
    print(f"Store types inside the four counties: {ri['types']}.")
    print(f"Store types nationally: {ri['types_national']}.")
    print(f"'Other' type inside the four counties: {ri['other_n']}, of which {ri['other_chain']} have a name that starts "
          f"with Walgreens, CVS, Dollar Tree, Dollar General or Family Dollar.")
    print(f"Incentive_Program values inside the four counties: {ri['incentive']}. Grantee_Name filled: {ri['grantee']}.")
    ins = int(df.loc[insuff, "retailers"].sum())
    print(f"Retailers in the 2 class-insufficient tracts: {ins}. Retailers in the analysis set: {int(a.retailers.sum()):,}.")

    d, n = a[a.cls == "desert"], a[a.cls == "nogap"]
    meas = {"retailers_per_1000": "All SNAP retailers per 1,000 residents",
            "full_line_per_1000": "Supermarkets and super stores per 1,000",
            "other_types_per_1000": "All other store types per 1,000"}
    n_ret = len(meas) + 1
    print(f"\nMann-Whitney U, two-sided; P(desert > nogap) = U / (n1 x n2). Tests in this table: {n_ret}. "
          f"Bonferroni threshold: {0.05 / n_ret:.4f}.\n")
    print("| Measure | Desert median [IQR] | Nogap median [IQR] | Mann-Whitney p | P(desert > nogap) |")
    print("|---|---|---|---|---|")
    ret_res = {}
    for c, nm in meas.items():
        u, p = stats.mannwhitneyu(d[c], n[c], alternative="two-sided")
        ret_res[c] = (d[c].median(), n[c].median(), p, u / (len(d) * len(n)))
        print(f"| {nm} | {iqr(d[c])} | {iqr(n[c])} | {fmt_p(p)} | {u / (len(d) * len(n)):.3f} |")
    zt = [[int((d.retailers == 0).sum()), int((d.retailers > 0).sum())],
          [int((n.retailers == 0).sum()), int((n.retailers > 0).sum())]]
    zo, zp = stats.fisher_exact(zt)
    print(f"| Tracts with zero SNAP retailers | {zt[0][0]} of {len(d)} ({zt[0][0] / len(d):.1%}) | "
          f"{zt[1][0]} of {len(n)} ({zt[1][0] / len(n):.1%}) | Fisher p {fmt_p(zp)} | odds ratio {zo:.2f} |")
    fl_d = (d.retailers_full_line == 0).mean()
    fl_n = (n.retailers_full_line == 0).mean()
    print(f"\nTracts with no supermarket or super store: desert {int((d.retailers_full_line == 0).sum())} ({fl_d:.1%}), "
          f"nogap {int((n.retailers_full_line == 0).sum())} ({fl_n:.1%}).")
    print(f"Retailers: desert tracts {int(d.retailers.sum())} for {int(d.pop2020.sum()):,} residents "
          f"({d.retailers.sum() / d.pop2020.sum() * 1000:.2f} per 1,000); nogap {int(n.retailers.sum()):,} for "
          f"{int(n.pop2020.sum()):,} ({n.retailers.sum() / n.pop2020.sum() * 1000:.2f} per 1,000).")
    for c in ["pctSnap", "pctPoverty"]:
        rho, p = stats.spearmanr(a.retailers_per_1000, a[c])
        print(f"Spearman, retailers per 1,000 vs {c}: rho {rho:.3f} (p = {fmt_p(p)}), n = {len(a)}.")
    print(f"USDA urban flag: desert tracts urban {int(d.urban.sum())} of {len(d)}; nogap urban {int(n.urban.sum())} of {len(n)}.")
    du, nu = d[d.urban == 1], n[n.urban == 1]
    for c, nm in meas.items():
        u, p = stats.mannwhitneyu(du[c], nu[c], alternative="two-sided")
        print(f"Urban tracts only, {nm}: desert median {du[c].median():.2f} (n = {len(du)}), nogap {nu[c].median():.2f} "
              f"(n = {len(nu)}); Mann-Whitney p = {fmt_p(p)}; P(desert > nogap) = {u / (len(du) * len(nu)):.3f}.")

    # --- 4. Mortgage denial rate ----------------------------------------------------------
    print("\n## 4. Mortgage denial rate (DS-H9)\n")
    m = a[a.denial_rate.notna()]
    print(f"Tracts with >= {MIN_APPLICATIONS} applications: {len(m)} (desert {int((m.cls == 'desert').sum())}, "
          f"nogap {int((m.cls == 'nogap').sum())}). Denial rate over these tracts: median {m.denial_rate.median():.4f}; "
          f"pooled {m.mortgage_denials.sum() / m.total_applications.sum():.4f} "
          f"({int(m.mortgage_denials.sum()):,} denials of {int(m.total_applications.sum()):,}).\n")
    print("| Compared with | n | Spearman rho | p | Pearson r (side note) | p |")
    print("|---|---|---|---|---|---|")
    mort = {}
    for c, nm in [("pctPoverty", "Poverty rate"), ("pctSnap", "SNAP share"), ("sba_loans_per_1000", "SBA loans per 1,000"),
                  ("median_household_income", "Median household income")]:
        s = m[["denial_rate", c]].dropna()
        rho, p = stats.spearmanr(s.denial_rate, s[c])
        r, pr = stats.pearsonr(s.denial_rate, s[c])
        mort[c] = (rho, p)
        print(f"| {nm} | {len(s)} | {rho:.3f} | {fmt_p(p)} | {r:.3f} | {fmt_p(pr)} |")
    md, mn = m[m.cls == "desert"].denial_rate, m[m.cls == "nogap"].denial_rate
    u, p = stats.mannwhitneyu(md, mn, alternative="two-sided")
    print(f"\nDesert median [IQR] {iqr(md, 4)}; nogap {iqr(mn, 4)}; Mann-Whitney p = {fmt_p(p)}; "
          f"P(desert > nogap) = {u / (len(md) * len(mn)):.3f}.")
    mt = m.pctPoverty >= pov_q[2]
    md2, mn2 = m[mt & (m.cls == "desert")].denial_rate, m[mt & (m.cls == "nogap")].denial_rate
    u2, p2 = stats.mannwhitneyu(md2, mn2, alternative="two-sided")
    print(f"Inside the top poverty quartile: desert median {md2.median():.4f} (n = {len(md2)}), nogap {mn2.median():.4f} "
          f"(n = {len(mn2)}); Mann-Whitney p = {fmt_p(p2)}.")
    print(f"As percentages: all tracts desert median {md.median():.1%}, nogap {mn.median():.1%}; top poverty quartile "
          f"nogap {mn2.median():.1%}. Tests in this section (4 Spearman, 2 Mann-Whitney): 6. Bonferroni threshold: {0.05 / 6:.4f}.")
    rho_all, p_all = stats.spearmanr(a.denial_rate_check.dropna(), a.loc[a.denial_rate_check.notna(), "pctPoverty"])
    print(f"Check without the application floor ({int(a.denial_rate_check.notna().sum())} tracts): Spearman with poverty "
          f"rho {rho_all:.3f} (p = {fmt_p(p_all)}).")
    hi_den = m.denial_rate >= den_q[2]
    print(f"Top-quartile denial-rate tracts: {int(hi_den.sum())}; desert {int((hi_den & (m.cls == 'desert')).sum())} of "
          f"{int((m.cls == 'desert').sum())} ({(hi_den & (m.cls == 'desert')).sum() / (m.cls == 'desert').sum():.1%}), "
          f"nogap {int((hi_den & (m.cls == 'nogap')).sum())} of {int((m.cls == 'nogap').sum())} "
          f"({(hi_den & (m.cls == 'nogap')).sum() / (m.cls == 'nogap').sum():.1%}).")
    print(f"Of the top-quartile denial-rate tracts, {int((hi_den & sba_mid[m.index].isin([True])).sum())} have SBA loans per "
          f"1,000 at or above the median (Credit Access Gap).")

    # --- 5. Data quality ------------------------------------------------------------------
    print("\n## 5. Data quality\n")
    up = a[a.unemployed > 0]
    rel_u = up.unemployed_moe / up.unemployed
    print(f"Unemployed persons (B23025_005): median MOE / estimate = {rel_u.median():.2f} over {len(up)} tracts with a "
          f"nonzero estimate; {(rel_u >= 0.5).mean():.1%} have MOE at or above half the estimate. "
          f"Tracts with an estimate of 0: {int((a.unemployed == 0).sum())}.")
    print(f"Labor force (B23025_002): median MOE / estimate = {(a.labor_force_moe / a.labor_force).median():.3f}.")
    print(f"Median household income: median MOE / estimate = {inc_info['rel_moe_median']:.3f}.")
    print(f"Denial-rate tracts with 20 to 49 applications: {int(((m.total_applications >= 20) & (m.total_applications < 50)).sum())}.")
    print(f"Desert tracts with 0 SNAP retailers: {zt[0][0]}; with 1: {int((d.retailers == 1).sum())}.")
    print(f"Unemployment top-quartile tracts: {int(unemp_hi[A].isin([True]).sum())}; of these also top-quartile poverty: "
          f"{int((unemp_hi[A].isin([True]) & pov_hi[A].isin([True])).sum())}.")
    rho_pu, p_pu = stats.spearmanr(a.pctPoverty, a.unemployment_rate, nan_policy="omit")
    print(f"Spearman, poverty vs unemployment rate: rho {rho_pu:.3f} (p = {fmt_p(p_pu)}).")

    # --- Output CSV -----------------------------------------------------------------------
    out = df[["geoid", "county", "cls"] + list(GAP_TYPES) + [
        "pop2020", "loans_total", "sba_loans_per_1000", "pctPoverty", "pctSnap", "lilaDD",
        "labor_force", "civ_labor_force", "unemployment_rate", "employment_pop_ratio",
        "median_household_income", "income_status", "mortgages_originated", "mortgage_denials",
        "total_applications", "denial_rate_check", "retailers", "retailers_full_line", "retailers_per_1000"]].copy()
    out["cls"] = out.cls.map({"desert": "Classic Food Desert", "nogap": "No gap flagged", "insufficient": "Insufficient data"})
    out = out.rename(columns={
        "cls": "food_class", "pop2020": "population_2020", "loans_total": "sba_loans_all_years",
        "pctPoverty": "poverty_rate_pct", "pctSnap": "snap_share_pct", "lilaDD": "lila_driving_flag",
        "unemployment_rate": "unemployment_rate_pct", "employment_pop_ratio": "employment_population_ratio_pct",
        "denial_rate_check": "mortgage_denial_rate", "total_applications": "mortgage_applications",
        "retailers": "snap_retailers", "retailers_full_line": "snap_supermarkets_superstores",
        "retailers_per_1000": "snap_retailers_per_1000"})
    for c in ["sba_loans_per_1000", "unemployment_rate_pct", "employment_population_ratio_pct", "snap_retailers_per_1000"]:
        out[c] = out[c].round(3)
    out["mortgage_denial_rate"] = out.mortgage_denial_rate.round(4)
    for c in ["labor_force", "civ_labor_force", "median_household_income", "mortgages_originated", "mortgage_denials",
              "mortgage_applications"]:
        out[c] = out[c].astype("Int64")
    out = out.sort_values("geoid")
    out.to_csv(OUT_CSV, index=False, lineterminator="\n")
    print(f"\nWrote {OUT_CSV.relative_to(ROOT).as_posix()} ({len(out)} rows).")


if __name__ == "__main__":
    main()
