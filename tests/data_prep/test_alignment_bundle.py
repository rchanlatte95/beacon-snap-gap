"""RED tests for SLICE-1 batch 2: Build cross-agency alignment, confidence, recommendations,
exterior county boundaries, and static bundle privacy/schema.

CONTRACT AUTHORITY RECORD:
- File: contracts/planner_map_contract.py
- Authority: AUTHORITATIVE for the Build (SLICE-1 planner map & Opportunities to Serve)
- POST clauses in batch 2: POST-ALN-1, POST-ALN-2, POST-ALN-3, POST-ALN-4, POST-GEO-1
- FORBIDDEN clauses in batch 2: FORBIDDEN-PRIV-1
- ERRORS clauses in batch 2: ERRORS-BLD-1

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: cites POST-ALN-1..4, POST-GEO-1, FORBIDDEN-PRIV-1, ERRORS-BLD-1 in contracts/planner_map_contract.py
- C2 VALUABLE: asserts exact Central Florida cohort counts (97, 391, 2, 50, 53, 29, 4 counties x 1 ring) and exact failure exception
- C3 NON-DUPLICATIVE: test 1 covers full 490-tract dataset alignment/confidence/geometry; test 2 covers missing-input error & privacy guard
- C4 NOT FUTURE-EDIT: exercises only the contracted batch-2 Build pipeline
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contracts import planner_map_contract as contract
from src.data_prep import alignment_bundle as impl

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_build_alignment_bundle_exact_cohorts_and_exterior_counties() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract (POST-ALN-1, POST-ALN-2, POST-ALN-3, POST-ALN-4, POST-GEO-1, FORBIDDEN-PRIV-1)
    - Enforces: exact 490-tract cohort counts (97 high need, 50 dual-gap, 53 transport-gap, 29 triple-gap, 2 insufficient),
      deterministic confidence & recommendations, median household income + 90% MOE join, and single-ring exterior county polygons
    - Category: integration / positive / boundary
    - Risk tier: High — drives the KPI cohort strip, map overlays, and AI action wizard
    """
    bundle = impl.build_alignment_bundle(REPO_ROOT)

    assert len(bundle["tracts"]) == contract.EXPECTED_TRACT_COUNT, (
        f"test_build_alignment_bundle_exact_cohorts_and_exterior_counties FAILED\n"
        f"POST-CLS-1 violation: wrong tract count\n"
        f"EXPECTED: {contract.EXPECTED_TRACT_COUNT}\n"
        f"ACTUAL: {len(bundle['tracts'])}\n"
        f"GUIDANCE: Build bundle must include all 490 Central Florida tracts"
    )

    contract.validate_tract_only_payload(bundle["tracts"])
    contract.validate_county_boundaries(bundle["counties_geojson"])

    sba_med = bundle["thresholds"]["sba_loans_median"]
    nv_q75 = bundle["thresholds"]["no_vehicle_q75"]
    assert sba_med == 10.0 and pytest.approx(nv_q75, abs=1e-6) == 6.9, (
        f"POST-ALN-1 / POST-ALN-2 violation: unexpected thresholds sba_med={sba_med}, nv_q75={nv_q75}"
    )

    dual_count = 0
    trans_count = 0
    triple_count = 0
    high_count = 0
    nogap_count = 0
    insuff_count = 0

    for t in bundle["tracts"]:
        rec = contract.TractAlignmentRecord(
            geoid=t["geoid"],
            tract_class=t["tract_class"],
            sba_loans_total=t["sba_loans_total"],
            sba_gross_usd_total=t["sba_gross_usd_total"],
            pct_no_vehicle=t["pct_no_vehicle"],
            households=t["households"],
            group_quarters_pct=t["group_quarters_pct"],
            median_household_income=t["median_household_income"],
            median_household_income_moe90=t["median_household_income_moe90"],
            is_dual_gap=t["is_dual_gap"],
            is_transport_gap=t["is_transport_gap"],
            is_triple_gap=t["is_triple_gap"],
            confidence_level=t["confidence_level"],
            recommended_action=t["recommended_action"],
        )
        contract.validate_alignment_record(rec, sba_median=sba_med, no_vehicle_q75=nv_q75)
        if rec.tract_class == contract.CLASS_HIGH_NEED:
            high_count += 1
        elif rec.tract_class == contract.CLASS_NO_GAP:
            nogap_count += 1
        elif rec.tract_class == contract.CLASS_INSUFFICIENT:
            insuff_count += 1
        if rec.is_dual_gap:
            dual_count += 1
        if rec.is_transport_gap:
            trans_count += 1
        if rec.is_triple_gap:
            triple_count += 1

    assert (high_count, nogap_count, insuff_count) == (
        contract.EXPECTED_HIGH_NEED_COUNT,
        contract.EXPECTED_NO_GAP_COUNT,
        contract.EXPECTED_INSUFFICIENT_COUNT,
    ), (
        f"POST-CLS-1 violation: class counts {(high_count, nogap_count, insuff_count)} != "
        f"{(contract.EXPECTED_HIGH_NEED_COUNT, contract.EXPECTED_NO_GAP_COUNT, contract.EXPECTED_INSUFFICIENT_COUNT)}"
    )
    assert dual_count == contract.EXPECTED_DUAL_GAP_COUNT, (
        f"POST-ALN-1 violation: dual_count={dual_count}, expected {contract.EXPECTED_DUAL_GAP_COUNT}"
    )
    assert trans_count == contract.EXPECTED_TRANSPORT_GAP_COUNT, (
        f"POST-ALN-2 violation: trans_count={trans_count}, expected {contract.EXPECTED_TRANSPORT_GAP_COUNT}"
    )
    assert triple_count == contract.EXPECTED_TRIPLE_GAP_COUNT, (
        f"POST-ALN-2 violation: triple_count={triple_count}, expected {contract.EXPECTED_TRIPLE_GAP_COUNT}"
    )


def test_missing_input_file_and_forbidden_block_keys(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract (ERRORS-BLD-1, FORBIDDEN-PRIV-1)
    - Enforces: ERRORS-BLD-1 (missing required input file raises BundleSchemaViolation naming the file)
      and FORBIDDEN-PRIV-1 (block or borrower keys are rejected)
    - Category: negative / error
    - Risk tier: High — prevents silent fallback on missing data (CL9) and prevents individual/block leakage (REQ-4, REQ-17)
    """
    with pytest.raises(impl.BundleSchemaViolation) as exc_info:
        impl.build_alignment_bundle(tmp_path)
    msg = str(exc_info.value)
    assert "ERRORS-BLD-1" in msg and "central_fl_tract_pantry_coverage.csv" in msg, (
        f"test_missing_input_file_and_forbidden_block_keys FAILED\n"
        f"ERRORS-BLD-1 violation: missing input file did not raise BundleSchemaViolation naming clause and file\n"
        f"EXPECTED: substring 'ERRORS-BLD-1' and 'central_fl_tract_pantry_coverage.csv'\n"
        f"ACTUAL: {msg!r}\n"
        f"GUIDANCE: Fail fast with BundleSchemaViolation naming ERRORS-BLD-1 and the missing input file"
    )

    with pytest.raises(impl.BundleSchemaViolation) as priv_exc:
        impl.assert_tract_only_records([{"geoid": "12095016510", "borrower_name": "Jane Doe"}])
    assert "FORBIDDEN-PRIV-1" in str(priv_exc.value), (
        f"FORBIDDEN-PRIV-1 violation: leaked borrower_name did not cite FORBIDDEN-PRIV-1: {priv_exc.value}"
    )
