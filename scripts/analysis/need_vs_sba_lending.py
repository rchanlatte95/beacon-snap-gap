"""Test the claim that food need and SBA lending line up, by census tract.

Claim (from a dashboard user): "The population that needs food aligns with people
that need lending from SBA." The user asked to contrast need against where loans go.

The script reads repo files only and prints every number used in
docs/analysis/need-vs-sba-lending.md. It writes one file:
docs/analysis/high_need_low_lending_tracts.csv. It writes nothing under data/.

Run from any directory:
    python scripts/analysis/need_vs_sba_lending.py
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "docs/mockups/planner-map/data/records.standin.json"
SBA = ROOT / "data/external/sba-loans/sba_loans_by_tract_central_fl.csv"
NO_VEHICLE = ROOT / "data/external/census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv"
POP_ZIP = ROOT / "data/hackathon/beacon-example-datasets/Total Population.zip"
POP_MEMBER = "ACSST5Y2024.S0101-Data.csv"
OUT_CSV = ROOT / "docs/analysis/high_need_low_lending_tracts.csv"

COUNTIES = {"12095": "Orange", "12117": "Seminole", "12069": "Lake", "12097": "Osceola"}
POP_FLOOR = 2000  # residents (2020 Census). Used only for the denominator check.
# No analysis tract is under 1,000, so a 1,000 floor would drop nothing.
TOP_N = 10

NEED = {
    "pctSnap": "SNAP share (% households)",
    "pctPoverty": "Poverty rate (%)",
    "pct_no_vehicle": "No-vehicle share (% households)",
}
PERIODS = {"total": "All years", "fy2010_2019": "FY2010-2019", "fy2020_2026": "FY2020-2026"}


def load() -> tuple[pd.DataFrame, dict]:
    rec = json.loads(RECORDS.read_text(encoding="utf-8"))
    tr = pd.DataFrame(rec["tracts"])
    assert len(tr) == 490 and tr.geoid.is_unique, "records: expected 490 unique tracts"
    counts = tr.cls.value_counts().to_dict()
    assert counts == {"nogap": 391, "desert": 97, "insufficient": 2}, counts

    sba = pd.read_csv(SBA, dtype={"geoid": str})
    assert len(sba) == 490 and sba.geoid.is_unique, "SBA: expected 490 unique tracts"
    assert int(sba.loans_total.sum()) == 6994, "SBA: README says 6,994 placed loans"
    for p in ("fy2010_2019", "fy2020_2026"):
        sba[f"loans_{p}"] = sba[f"loans_7a_{p}"] + sba[f"loans_504_{p}"]
        sba[f"usd_{p}"] = sba[f"gross_usd_7a_{p}"] + sba[f"gross_usd_504_{p}"]
    sba["usd_total"] = sba["gross_usd_total"]
    assert (sba.loans_fy2010_2019 + sba.loans_fy2020_2026 == sba.loans_total).all()
    assert (sba.usd_fy2010_2019 + sba.usd_fy2020_2026 == sba.usd_total).all()

    nv = pd.read_csv(NO_VEHICLE, dtype={"geoid": str})
    assert len(nv) == 490 and nv.geoid.is_unique, "no-vehicle: expected 490 unique tracts"

    with zipfile.ZipFile(POP_ZIP) as z, z.open(POP_MEMBER) as f:
        acs = pd.read_csv(f, skiprows=[1], usecols=["GEO_ID", "S0101_C01_001E", "S0101_C01_001M"])
    acs["geoid"] = acs.GEO_ID.str[-11:]
    acs = acs[acs.geoid.str[:5].isin(COUNTIES)]
    acs = acs.rename(columns={"S0101_C01_001E": "pop_acs2024", "S0101_C01_001M": "pop_acs2024_moe"})
    assert len(acs) == 490, "ACS S0101: expected 490 Central FL tracts"

    df = (
        tr[["geoid", "name", "county", "cls", "pctSnap", "pctPoverty", "noVehiclePct", "pop2020", "households", "urban"]]
        .merge(sba, on="geoid", how="left", validate="1:1")
        .merge(nv, on="geoid", how="left", validate="1:1")
        .merge(acs[["geoid", "pop_acs2024", "pop_acs2024_moe"]], on="geoid", how="left", validate="1:1")
    )
    assert df.loans_total.notna().all() and df.pop_acs2024.notna().all()
    # The stand-in carries the same no-vehicle value; confirm the two agree.
    both = df.noVehiclePct.notna() & df.pct_no_vehicle.notna()
    assert np.allclose(df.loc[both, "noVehiclePct"], df.loc[both, "pct_no_vehicle"])
    assert (df.geoid.str[:5].map(COUNTIES) == df.county).all()
    return df, rec["povertyCut"]


def add_rates(df: pd.DataFrame, pop_col: str) -> pd.DataFrame:
    df = df.copy()
    pop = df[pop_col].where(df[pop_col] > 0)
    for p in PERIODS:
        df[f"loans_per1k_{p}"] = df[f"loans_{p}"] / pop * 1000
        df[f"usd_per1k_{p}"] = df[f"usd_{p}"] / pop * 1000
    return df


def measures() -> dict[str, str]:
    m = {}
    for p, label in PERIODS.items():
        m[f"loans_per1k_{p}"] = f"Loans per 1,000 residents, {label}"
    for p, label in PERIODS.items():
        m[f"usd_per1k_{p}"] = f"Gross $ per 1,000 residents, {label}"
    return m


def analysis_set(df: pd.DataFrame) -> pd.DataFrame:
    a = df[df.cls.isin(["desert", "nogap"]) & (df.pop2020 > 0)]
    assert a[list(NEED)].notna().all().all(), "need values missing in analysis set"
    return a


def fmt_p(p: float) -> str:
    return f"{p:.2g}" if p >= 0.0001 else f"{p:.1e}"


def corr_table(a: pd.DataFrame, cols: dict[str, str], title: str) -> pd.DataFrame:
    rows = []
    for c, label in cols.items():
        for n, nlabel in NEED.items():
            sub = a[[c, n]].dropna()
            rho, p = stats.spearmanr(sub[c], sub[n])
            r, pr = stats.pearsonr(sub[c], sub[n])
            rows.append((label, nlabel, len(sub), rho, p, r, pr))
    t = pd.DataFrame(rows, columns=["lending", "need", "n", "spearman_rho", "spearman_p", "pearson_r", "pearson_p"])
    print(f"\n## {title}\n")
    print("| Lending measure | Need measure | n | Spearman rho | p | Pearson r (side note) | p |")
    print("|---|---|---|---|---|---|---|")
    for row in t.itertuples():
        print(
            f"| {row.lending} | {row.need} | {row.n} | {row.spearman_rho:.3f} | {fmt_p(row.spearman_p)} "
            f"| {row.pearson_r:.3f} | {fmt_p(row.pearson_p)} |"
        )
    return t


def group_table(a: pd.DataFrame, cols: dict[str, str], title: str) -> None:
    d = a[a.cls == "desert"]
    g = a[a.cls == "nogap"]
    print(f"\n## {title}\n")
    print(f"Desert n = {len(d)}, nogap n = {len(g)}. Mann-Whitney U, two-sided. "
          "P(desert > nogap) = U / (n1 x n2), the chance that a random desert tract has the higher value (0.5 = no difference).\n")
    print("| Lending measure | Desert median [IQR] | Nogap median [IQR] | Desert zero-loan share | Nogap zero-loan share | U | p | P(desert > nogap) |")
    print("|---|---|---|---|---|---|---|---|")
    zero_col = "loans_total"
    for c, label in cols.items():
        x, y = d[c].dropna(), g[c].dropna()
        u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        nd, cur = (0, "$") if c.startswith("usd") else (1, "")
        q = lambda s: (f"{cur}{s.median():,.{nd}f} [{cur}{s.quantile(0.25):,.{nd}f} "
                       f"to {cur}{s.quantile(0.75):,.{nd}f}]")
        period = c.rsplit("_", 2)[-2] + "_" + c.rsplit("_", 1)[-1] if "fy" in c else "total"
        zc = f"loans_{period}" if period != "total" else zero_col
        print(
            f"| {label} | {q(x)} | {q(y)} | {(d[zc] == 0).mean():.1%} | {(g[zc] == 0).mean():.1%} "
            f"| {u:,.0f} | {fmt_p(p)} | {u / (len(x) * len(y)):.3f} |"
        )


def main() -> None:
    df, pc = load()
    df = add_rates(df, "pop2020")
    a = analysis_set(df)
    m = measures()

    print("# Food need vs SBA 7(a) and 504 lending, Central Florida tracts")
    print(f"\nTracts in files: {len(df)}. Analysis set (class desert or nogap, 2020 population > 0): {len(a)}.")
    print(f"Excluded: {', '.join(df.loc[~df.geoid.isin(a.geoid), 'geoid'] + ' (' + df.loc[~df.geoid.isin(a.geoid), 'cls'] + ')')}.")
    print(f"Placed loans in analysis set: {int(a.loans_total.sum()):,} of {int(df.loans_total.sum()):,}; "
          f"gross ${a.usd_total.sum() / 1e9:,.2f} billion of ${df.usd_total.sum() / 1e9:,.2f} billion.")
    print(f"Class rule poverty cut (from the stand-in): {pc['value']}% over {pc['tracts']} tracts.")
    print("Denominator: 2020 Census population (pop2020, sum of 2020 blocks) from the planner stand-in.")
    print(f"Tracts with zero placed loans: {(a.loans_total == 0).sum()} of {len(a)}.")
    n_tests = len(m) * len(NEED)
    print(f"Correlation tests in the main table: {n_tests}. Bonferroni threshold: {0.05 / n_tests:.4f}.")

    t = corr_table(a, m, "1. Spearman correlation, lending per 1,000 residents vs need (all 488 tracts)")
    group_table(a, m, "2. Desert (high need) vs nogap tracts")

    # 3. 2x2: need class against lending above or below the median.
    cut = a.loans_per1k_total.median()
    a = a.assign(
        need=np.where(a.cls == "desert", "high need", "low need"),
        lending=np.where(a.loans_per1k_total < cut, "low lending", "high lending"),
    )
    ct = pd.crosstab(a.need, a.lending).loc[["high need", "low need"], ["low lending", "high lending"]]
    odds, fp = stats.fisher_exact(ct.values)
    print("\n## 3. 2x2 count\n")
    print(f"High need = class desert. Low need = class nogap. Low lending = loans per 1,000 residents (all years) "
          f"below the median of the {len(a)} tracts ({cut:.2f}). High lending = at or above the median.\n")
    print("| | Low lending | High lending | Total |")
    print("|---|---|---|---|")
    for need_lvl in ct.index:
        print(f"| {need_lvl} | {ct.loc[need_lvl, 'low lending']} | {ct.loc[need_lvl, 'high lending']} | {ct.loc[need_lvl].sum()} |")
    hn_ll = a[(a.need == "high need") & (a.lending == "low lending")]
    print(f"\nHigh need, low lending: {len(hn_ll)} of {int(ct.loc['high need'].sum())} desert tracts "
          f"({len(hn_ll) / ct.loc['high need'].sum():.1%}). Low need, low lending: {ct.loc['low need', 'low lending']} of "
          f"{int(ct.loc['low need'].sum())} ({ct.loc['low need', 'low lending'] / ct.loc['low need'].sum():.1%}).")
    print(f"Fisher exact test: odds ratio {odds:.2f}, p = {fmt_p(fp)}.")
    print("High-need low-lending tracts by county: "
          + ", ".join(f"{k} {v}" for k, v in hn_ll.county.value_counts().items()) + ".")

    out = hn_ll.sort_values("loans_per1k_total")[
        ["geoid", "county", "cls", "pctSnap", "pctPoverty", "loans_per1k_total", "loans_total", "pop2020"]
    ].rename(columns={
        "pctSnap": "snap_share_pct", "pctPoverty": "poverty_rate_pct",
        "loans_per1k_total": "loans_per_1000_residents", "pop2020": "population_2020", "cls": "class",
    })
    out["loans_per_1000_residents"] = out.loans_per_1000_residents.round(3)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, lineterminator="\n")
    print(f"Wrote {OUT_CSV.relative_to(ROOT).as_posix()} ({len(out)} rows).")

    # 4. Denominator check.
    print(f"\n## 4. Denominator check\n\nTop {TOP_N} tracts by loans per 1,000 residents (all years):\n")
    print("| GEOID | County | Class | 2020 pop | ACS 2024 pop | Loans | Loans per 1,000 |")
    print("|---|---|---|---|---|---|---|")
    top = a.nlargest(TOP_N, "loans_per1k_total")
    for r in top.itertuples():
        print(f"| {r.geoid} | {r.county} | {r.cls} | {r.pop2020:,} | {r.pop_acs2024:,} | {r.loans_total} | {r.loans_per1k_total:.2f} |")
    print(f"\nTop {TOP_N}: median 2020 population {top.pop2020.median():,.0f} (all analysis tracts: {a.pop2020.median():,.0f}); "
          f"{int(top.loans_total.sum())} loans ({top.loans_total.sum() / a.loans_total.sum():.1%} of loans in the analysis set); "
          f"classes: " + ", ".join(f"{k} {v}" for k, v in top.cls.value_counts().items()) + ".")
    print(f"Analysis tracts under 1,000 residents (2020): {(a.pop2020 < 1000).sum()}. "
          f"Under {POP_FLOOR:,}: {(a.pop2020 < POP_FLOOR).sum()}.")

    key = {"loans_per1k_total": "Loans per 1,000, all years", "usd_per1k_total": "Gross $ per 1,000, all years"}
    variants = {
        "All 488 tracts, 2020 pop": a,
        f"Exclude top {TOP_N} by loans per 1,000": a[~a.geoid.isin(top.geoid)],
        f"2020 pop >= {POP_FLOOR:,}": a[a.pop2020 >= POP_FLOOR],
    }
    acs_a = add_rates(df, "pop_acs2024")
    acs_a = acs_a[acs_a.geoid.isin(a.geoid)]
    variants["ACS 2024 pop as denominator"] = acs_a
    raw = a.assign(loans_per1k_total=a.loans_total, usd_per1k_total=a.usd_total)
    variants["Raw counts and $ (no denominator)"] = raw
    print("\nSpearman rho (p) for the two all-years measures under each variant:\n")
    print("| Variant | n | Lending measure | SNAP share | Poverty rate | No-vehicle share | Desert vs nogap MWU p | P(desert > nogap) |")
    print("|---|---|---|---|---|---|---|---|")
    for vname, v in variants.items():
        for c, label in key.items():
            if vname.startswith("Raw"):
                label = label.replace(" per 1,000", " per tract")
            cells = []
            for n in NEED:
                rho, p = stats.spearmanr(v[c], v[n])
                cells.append(f"{rho:.3f} ({fmt_p(p)})")
            x, y = v.loc[v.cls == "desert", c], v.loc[v.cls == "nogap", c]
            u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
            print(f"| {vname} | {len(v)} | {label} | {' | '.join(cells)} | {fmt_p(p)} | {u / (len(x) * len(y)):.3f} |")

    # 5. County check: the geocoder missed more loans in Lake, Seminole and Osceola.
    print("\n## 5. Within-county Spearman, loans per 1,000 (all years)\n")
    print(f"County tests: {4 * len(NEED)}. Bonferroni threshold: {0.05 / (4 * len(NEED)):.4f}.\n")
    print("| County | n | Desert tracts | vs SNAP share | vs poverty rate | vs no-vehicle share |")
    print("|---|---|---|---|---|---|")
    for cty in ["Orange", "Seminole", "Lake", "Osceola"]:
        s = a[a.county == cty]
        cells = []
        for n in NEED:
            rho, p = stats.spearmanr(s.loans_per1k_total, s[n])
            cells.append(f"{rho:.3f} ({fmt_p(p)})")
        print(f"| {cty} | {len(s)} | {(s.cls == 'desert').sum()} | {' | '.join(cells)} |")

    # 5b. The only clear signal is with no-vehicle share. Check it inside urban and rural tracts
    # (USDA urban flag, carried in the stand-in). One possible reason for the signal is that
    # car-free households and business mailing addresses both cluster in urban cores.
    print("\n## 5b. No-vehicle share vs loans per 1,000 (all years), by USDA urban flag\n")
    print("| Tracts | n | Spearman rho (p) | Median loans per 1,000 |")
    print("|---|---|---|---|")
    for flag, lbl in [(1, "Urban"), (0, "Rural")]:
        s = a[a.urban == flag]
        rho, p = stats.spearmanr(s.loans_per1k_total, s.pct_no_vehicle)
        print(f"| {lbl} | {len(s)} | {rho:.3f} ({fmt_p(p)}) | {s.loans_per1k_total.median():.2f} |")

    # 6. Data quality numbers for the limits section.
    nvpos = a[a.no_vehicle_households > 0]
    rel = (nvpos.moe_no_vehicle_households / nvpos.no_vehicle_households)
    rel_pop = (a.pop_acs2024_moe / a.pop_acs2024)
    print("\n## 6. Data quality\n")
    print(f"No-vehicle households: median MOE / estimate = {rel.median():.2f}; "
          f"{(rel >= 0.5).mean():.1%} of tracts with a nonzero estimate have MOE at or above half the estimate.")
    print(f"ACS 2024 total population: median MOE / estimate = {rel_pop.median():.3f}.")
    print(f"Desert tracts with 5 or fewer placed loans (all years): {(a[a.cls == 'desert'].loans_total <= 5).sum()} of {(a.cls == 'desert').sum()}.")
    print(f"Spearman, 2020 pop vs ACS 2024 pop: {stats.spearmanr(a.pop2020, a.pop_acs2024)[0]:.3f}.")

    # Headline lines for the note.
    sig = t[t.spearman_p < 0.05 / n_tests]
    print("\n## Summary\n")
    print(f"Spearman rho range over {n_tests} tests: {t.spearman_rho.min():.3f} to {t.spearman_rho.max():.3f}. "
          f"Positive: {(t.spearman_rho > 0).sum()}. Negative: {(t.spearman_rho < 0).sum()}. "
          f"Below Bonferroni threshold: {len(sig)} ({(sig.spearman_rho > 0).sum()} positive, {(sig.spearman_rho < 0).sum()} negative).")


if __name__ == "__main__":
    main()
