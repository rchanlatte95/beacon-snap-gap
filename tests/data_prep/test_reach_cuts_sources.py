"""RED tests for SLICE-1 batch 3 (cycle 17, PR #18 refactor).

Build reach per step, cuts per percentile, and the source list.

CONTRACT AUTHORITY RECORD:
- File: contracts/planner_map_contract.py
- Clauses covered: POST-RCH-1, POST-CUT-1, POST-SRC-1, ERRORS-BLD-2
- Requirements: REQ-55, REQ-58, REQ-61, REQ-9 (Z-2 2-A, Z-24 A;
  grids chosen by jev at Ketema's direction)

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: every assertion compares the Build's output with a contract oracle or constant.
- C2 VALUABLE: one reach definition for card, map and AI; adjustable cuts that
  reproduce the fixed rule; one source list.
- C3 NON-DUPLICATIVE: test_alignment_bundle.py covers the fixed flags; these
  cover the new bundle fields only.
- C4 NOT FUTURE-EDIT: exercises only the contracted bundle keys.
"""

from __future__ import annotations

import csv
import shutil
from collections import defaultdict
from pathlib import Path

import pytest
from contracts import planner_map_contract as contract
from src.data_prep import alignment_bundle as impl

REPO_ROOT = Path(__file__).resolve().parents[2]
EXT = REPO_ROOT / "data" / "external"


def _blocks_by_tract() -> dict[str, list[tuple[float, float, int]]]:
    out: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
    with (EXT / "census-2020-blocks" / "central-fl-blocks-2020.csv").open(
        encoding="utf-8", newline=""
    ) as fh:
        for r in csv.DictReader(fh):
            pop = int(r["pop20"] or 0)
            lat = float(r["lat"]) if r["lat"] else 0.0
            lon = float(r["lon"]) if r["lon"] else 0.0
            out[r["geoid20"][:11]].append((lat, lon, pop))
    return out


def _sites() -> list[tuple[str, float, float]]:
    path = EXT / "second-harvest-food-finder" / "second_harvest_food_finder_locations.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            (r["storeid"], float(r["lat"]), float(r["lng"]))
            for r in csv.DictReader(fh)
            if r["lat"] and r["lng"]
        ]


@pytest.fixture(scope="module")
def bundle() -> dict[str, object]:
    return impl.build_alignment_bundle(REPO_ROOT)


def test_every_tract_carries_reach_at_every_step_from_its_blocks(bundle: dict[str, object]) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract POST-RCH-1 (REQ-55, Z-2 2-A)
    - Enforces: thresholds.reach_steps_miles is the 41-step grid, and each tract's
      reach_share, reach_sites and
      nearest_block_miles equal expected_reach over its 2020 blocks and the Second Harvest sites
    - Category: integration / positive / boundary (step 0 and the inclusive step edge)
    - Risk tier: High; the card, map, shortlist and AI all read these values
    """
    thresholds = bundle["thresholds"]
    assert isinstance(thresholds, dict)
    assert thresholds.get(contract.BUNDLE_REACH_STEPS_KEY) == list(contract.REACH_STEPS_MILES), (
        f"POST-RCH-1 violation: thresholds.{contract.BUNDLE_REACH_STEPS_KEY} is "
        f"{thresholds.get(contract.BUNDLE_REACH_STEPS_KEY)!r}\n"
        f"EXPECTED: {list(contract.REACH_STEPS_MILES)!r}\n"
        "GUIDANCE: write the 0 to 20 mile grid by 0.5 into the bundle thresholds"
    )
    blocks = _blocks_by_tract()
    sites = _sites()
    tracts = bundle["tracts"]
    assert isinstance(tracts, list)
    wrong: list[str] = []
    for t in tracts:
        want = contract.expected_reach(blocks.get(t["geoid"], []), sites)
        got = (
            t.get(contract.BUNDLE_REACH_SHARE_KEY),
            t.get(contract.BUNDLE_REACH_SITES_KEY),
            t.get(contract.BUNDLE_NEAREST_BLOCK_MILES_KEY),
        )
        if got != (list(want.share), list(want.sites), want.nearest_block_miles):
            wrong.append(t["geoid"])
    assert not wrong, (
        f"POST-RCH-1 violation: {len(wrong)} of {len(tracts)} tracts differ from "
        f"expected_reach, first {wrong[:3]}\n"
        "EXPECTED: reach_share, reach_sites and nearest_block_miles equal "
        "expected_reach for every tract\n"
        "GUIDANCE: compute per populated block its nearest-site distance with "
        "the contract's haversine; "
        "never measure from the tract centre"
    )


def test_cuts_at_every_named_percentile_reproduce_the_fixed_rule(bundle: dict[str, object]) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract POST-CUT-1 (REQ-58, Z-24 A)
    - Enforces: thresholds.cuts equals expected_cuts over the fixed rule's value
      sets, and the default
      percentiles give exactly the cuts the tract flags use
    - Category: integration / positive / boundary (lowest and highest named percentile)
    - Risk tier: High; every adjustable group count depends on these cuts
    """
    thresholds = bundle["thresholds"]
    tracts = bundle["tracts"]
    assert isinstance(thresholds, dict)
    assert isinstance(tracts, list)
    poverty = [t["pct_poverty"] for t in tracts if t["pct_poverty"] is not None]
    no_vehicle = [t["pct_no_vehicle"] for t in tracts if t["pct_no_vehicle"] is not None]
    sba = [
        r
        for t in tracts
        if (r := contract.expected_sba_rate(t["sba_loans_total"], t["pop2020"])) is not None
    ]
    want = contract.expected_cuts(poverty, no_vehicle, sba)
    got = thresholds.get(contract.BUNDLE_CUTS_KEY)
    assert got == want, (
        f"POST-CUT-1 violation: thresholds.{contract.BUNDLE_CUTS_KEY} is {got!r}\n"
        f"EXPECTED: {want!r}\n"
        "GUIDANCE: statistics.quantiles(values, n=100, method='inclusive')[p - 1] "
        "for each named percentile"
    )
    defaults = (
        got[contract.CUT_POVERTY][str(contract.DEFAULT_POVERTY_PERCENTILE)],
        got[contract.CUT_NO_VEHICLE][str(contract.DEFAULT_NO_VEHICLE_PERCENTILE)],
        got[contract.CUT_SBA_RATE][str(contract.DEFAULT_SBA_PERCENTILE)],
    )
    fixed = (
        thresholds["poverty_cut_q75"],
        thresholds["no_vehicle_q75"],
        thresholds[contract.BUNDLE_SBA_RATE_CUT_KEY],
    )
    assert defaults == fixed, (
        f"POST-CUT-1 violation: default-percentile cuts {defaults} differ from "
        f"the fixed cuts {fixed}\n"
        "GUIDANCE: the 75th, 75th and 25th percentiles must equal the cuts the flags use"
    )


def test_sources_come_from_the_catalog_table(bundle: dict[str, object]) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract POST-SRC-1 (REQ-61)
    - Enforces: bundle.sources equals expected_source_catalog(docs/data-sources.md),
      in CITED_SOURCE_IDS order
    - Category: integration / positive
    - Risk tier: Medium; a typed copy of the sources drifts from the register
    """
    doc = (REPO_ROOT / contract.SOURCE_CATALOG_DOC_PATH).read_text(encoding="utf-8")
    try:
        want = list(contract.expected_source_catalog(doc))
    except contract.BundleSchemaViolation as exc:
        pytest.fail(
            f"POST-SRC-1 violation: the catalog cannot be read: {exc}\n"
            f"GUIDANCE: add {contract.SOURCE_CATALOG_HEADING!r} to "
            f"{contract.SOURCE_CATALOG_DOC_PATH} with columns "
            f"{contract.SOURCE_CATALOG_COLUMNS} and one row per cited source "
            "(move them from src/dataSources.ts)"
        )
    got = bundle.get(contract.BUNDLE_SOURCES_KEY)
    assert got == want, (
        f"POST-SRC-1 violation: bundle.{contract.BUNDLE_SOURCES_KEY} differs from the catalog\n"
        f"EXPECTED first: {want[:1]!r}\n"
        f"ACTUAL first: {got[:1] if isinstance(got, list) else got!r}\n"
        "GUIDANCE: the Build parses the catalog table and writes the cited entries in order"
    )


@pytest.mark.parametrize(
    ("label", "catalog"),
    [
        ("no heading", "# Data sources appendix\n"),
        (
            "cited ID missing",
            f"{contract.SOURCE_CATALOG_HEADING}\n\n| "
            + " | ".join(contract.SOURCE_CATALOG_COLUMNS)
            + " |\n"
            "|---|---|---|---|---|---|---|\n| DS-H1 | a | b | c | https://x | d | e |\n",
        ),
    ],
)
def test_a_bad_catalog_stops_the_build_and_writes_nothing(
    tmp_path: Path, label: str, catalog: str
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract ERRORS-BLD-2 (REQ-61, REQ-9)
    - Enforces: a missing heading or a missing cited ID raises BundleSchemaViolation
      naming ERRORS-BLD-2,
      and no bundle file is written
    - Category: negative / error
    - Risk tier: High; a partial source list must never ship silently (CL9)
    """
    try:
        (tmp_path / "data").symlink_to(REPO_ROOT / "data", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"ARRANGE: this platform cannot create a directory symlink ({exc})")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "data-sources.md").write_text(catalog, encoding="utf-8")
    shutil.copy(REPO_ROOT / "docs" / "taxonomy.md", tmp_path / "docs" / "taxonomy.md")
    with pytest.raises(impl.BundleSchemaViolation) as caught:
        impl.write_static_bundle(tmp_path)
    assert "ERRORS-BLD-2" in str(caught.value), (
        f"ERRORS-BLD-2 violation ({label}): the error does not name the clause: {caught.value}"
    )
    written = (
        sorted(p.name for p in (tmp_path / "public").rglob("*"))
        if (tmp_path / "public").exists()
        else []
    )
    assert written == [], f"ERRORS-BLD-2 violation ({label}): files were written: {written}"
