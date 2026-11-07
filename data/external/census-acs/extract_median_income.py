"""Extract Census household income for the planner mock-up, without changing the app."""

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CACHE = ROOT / "data/cache/census-income"
BASE = "https://www2.census.gov/programs-surveys/acs/summary_file"
CHECKSUMS = {
    2024: "b25a176b0e6c339b6f3a2a0d3d8446bf06f5f080b4395993ec9a8313efb1c229",
    2023: "c9007017b7bb29ba758c77612ec9a4a0b897a4ed931d527754629866f580a110",
}


def bulk_income(year):
    name = f"acsdt5y{year}-b19013.dat"
    path = CACHE / name
    if not path.exists():
        url = f"{BASE}/{year}/table-based-SF/data/5YRData/{name}"
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != CHECKSUMS[year]:
            raise ValueError(f"Publisher file changed: {url}. Review before use.")
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != CHECKSUMS[year]:
        raise ValueError(f"Cached file checksum differs: {path}")
    return {
        row["GEO_ID"]: row
        for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter="|")
    }


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    tracts = json.loads(
        (ROOT / "docs/mockups/planner-map/data/records.standin.json").read_text(encoding="utf-8")
    )["tracts"]
    ids = [tract["geoid"] for tract in tracts]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate frontend GEOIDs")
    with zipfile.ZipFile(ROOT / "data/hackathon/beacon-example-datasets/Household Income, Median.zip") as archive:
        source = {
            row["GEO_ID"]: row
            for row in csv.DictReader(
                io.StringIO(archive.read("ACSST5Y2024.S1901-Data.csv").decode("utf-8-sig"))
            )
            if row["GEO_ID"].startswith("1400000US")
        }
    current = bulk_income(2024)
    prior = bulk_income(2023)
    rows = []
    for tract in sorted(tracts, key=lambda row: row["geoid"]):
        geoid = "1400000US" + tract["geoid"]
        census = source[geoid]
        check = current[geoid]
        estimate = census["S1901_C01_012E"].replace(",", "")
        moe = census["S1901_C01_012M"].replace(",", "")
        median, margin, lower_bound = "", "", ""
        if estimate.isdigit():
            status = "published"
            median, margin = int(estimate), int(moe)
            if (median, margin) != (int(check["B19013_E001"]), int(check["B19013_M001"])):
                raise ValueError(f"S1901 and B19013 differ: {geoid}")
        elif estimate.endswith("+") and estimate[:-1].isdigit():
            status = "lower_bound"
            lower_bound = int(estimate[:-1])
            if (check["B19013_E001"], check["B19013_M001"]) != (str(lower_bound + 1), "-333333333"):
                raise ValueError(f"Income bound differs: {geoid}")
        elif estimate == "-" and moe == "**":
            status = "unavailable"
            if (check["B19013_E001"], check["B19013_M001"]) != ("-666666666", "-222222222"):
                raise ValueError(f"Missing income codes differ: {geoid}")
        else:
            raise ValueError(f"Review income symbols for {geoid}: {estimate!r}, {moe!r}")
        households = int(census["S1901_C01_001E"].replace(",", ""))
        if households != tract["households"]:
            raise ValueError(f"Household counts differ: {geoid}")
        prior_median, prior_margin, prior_period, prior_dollars = "", "", "", ""
        previous = prior.get(geoid)
        if status == "unavailable" and households > 0 and previous:
            prior_e, prior_m = int(previous["B19013_E001"]), int(previous["B19013_M001"])
            if prior_e > 0 and prior_m >= 0:
                prior_median, prior_margin = prior_e, prior_m
                prior_period, prior_dollars = "2019-2023", 2023
        rows.append({
            "geoid": tract["geoid"],
            "name": tract["name"],
            "county": tract["county"],
            "drawn": int(tract["drawn"]),
            "frontend_class": tract["cls"],
            "households": households,
            "period": "2020-2024",
            "dollar_year": 2024,
            "median_household_income": median,
            "median_household_income_moe90": margin,
            "median_household_income_lower_bound": lower_bound,
            "income_status": status,
            "raw_estimate": census["S1901_C01_012E"],
            "raw_moe": census["S1901_C01_012M"],
            "prior_median_household_income": prior_median,
            "prior_median_household_income_moe90": prior_margin,
            "prior_period": prior_period,
            "prior_dollar_year": prior_dollars,
        })
    counties = []
    for geoid, county in sorted({(r["geoid"][:5], r["county"]) for r in rows}):
        census = current["0500000US" + geoid]
        counties.append({
            "county_geoid": geoid,
            "county": county,
            "period": "2020-2024",
            "dollar_year": 2024,
            "median_household_income": int(census["B19013_E001"]),
            "median_household_income_moe90": int(census["B19013_M001"]),
        })
    write_csv("acs2024_s1901_median_household_income_central_fl_tracts.csv", rows)
    write_csv("acs2024_b19013_median_household_income_central_fl_counties.csv", counties)
    print(f"Verified {len(rows)} frontend GEOIDs against S1901 and Census B19013.")
    print("2020-2024 income status:", dict(Counter(r["income_status"] for r in rows)))
    print("2019-2023 alternatives:", sum(r["prior_median_household_income"] != "" for r in rows))
    print("County context rows:", len(counties))


if __name__ == "__main__":
    main()
