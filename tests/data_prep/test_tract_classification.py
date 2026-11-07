"""RED tests for SLICE-1 batch 1: Build tract classification.

CONTRACT AUTHORITY RECORD:
- File: contracts/planner_map_contract.py
- Authority: AUTHORITATIVE for the Build (SLICE-1 planner map)
- PRE clauses: 1 (PRE-CLS-1)
- POST clauses: 3 (POST-CLS-1, POST-CLS-2, POST-CLS-3)
- ERRORS clauses: 1 (ERRORS-CLS-1)

EQUIVALENCE PARTITION RECORD (PRE-CLS-1, POST-CLS-1, POST-CLS-2, ERRORS-CLS-1):
- pct_poverty valid interior / on-boundary: 0.0, 17.025 (on cut), 17.024 (off cut), 100.0
- pct_poverty blank: None -> Insufficient data naming 'pct_poverty'
- pct_poverty invalid: -0.1, 100.1, float('nan'), True -> InvalidIndicatorError
- DD_SRAM_LILATracts_halfAnd10 valid: 0, 1; blank: None -> Insufficient data; invalid: 2, -1, True

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
- C1 VALID: cites PRE-CLS-1, POST-CLS-1, POST-CLS-2, POST-CLS-3, ERRORS-CLS-1 in contracts/planner_map_contract.py
- C2 VALUABLE: exact class and exact unrounded cut asserted; a wrong implementation fails
- C3 NON-DUPLICATIVE: test 1 covers cut + positive/boundary classification; test 2 covers blanks + invalid inputs
- C4 NOT FUTURE-EDIT: exercises only the contracted batch-1 classification boundary
"""

from __future__ import annotations

import pytest

from contracts import planner_map_contract as contract
from src.data_prep import tract_classification as impl


def test_poverty_cut_and_boundary_classification() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract (POST-CLS-1, POST-CLS-3, PRE-CLS-1)
    - Enforces: POST-CLS-3 (inclusive Q3, unrounded) and POST-CLS-1 (three-class rule at the cut boundary)
    - Category: boundary
    - Risk tier: High — a wrong cut or boundary flips which tracts a food bank planner sees as high need
    """
    assert impl.CLASS_HIGH_NEED == contract.CLASS_HIGH_NEED, (
        f"test_poverty_cut_and_boundary_classification FAILED\n"
        f"POST-CLS-1 violation: CLASS_HIGH_NEED mismatch between contract and implementation\n"
        f"EXPECTED: {contract.CLASS_HIGH_NEED!r}\n"
        f"ACTUAL: {impl.CLASS_HIGH_NEED!r}\n"
        f"GUIDANCE: Redeclared class names must equal the contract's class names"
    )
    assert impl.CLASS_NO_GAP == contract.CLASS_NO_GAP, (
        f"POST-CLS-1 violation: CLASS_NO_GAP mismatch: expected {contract.CLASS_NO_GAP!r}, got {impl.CLASS_NO_GAP!r}"
    )
    assert impl.CLASS_INSUFFICIENT == contract.CLASS_INSUFFICIENT, (
        f"POST-CLS-2 violation: CLASS_INSUFFICIENT mismatch: expected {contract.CLASS_INSUFFICIENT!r}, got {impl.CLASS_INSUFFICIENT!r}"
    )
    assert impl.LILA_FLAG_COLUMN == contract.LILA_FLAG_COLUMN, (
        f"PRE-CLS-1 violation: LILA_FLAG_COLUMN mismatch: expected {contract.LILA_FLAG_COLUMN!r}, got {impl.LILA_FLAG_COLUMN!r}"
    )

    # POST-CLS-3: inclusive Q3 of [1,2,3,4,5,6] is 4.75 (exclusive gives 5.25; rounding to 1 decimal gives 4.8).
    sample_rates = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    cut = impl.poverty_cut(sample_rates)
    contract.validate_poverty_cut(cut, sample_rates)
    assert cut == 4.75, (
        f"test_poverty_cut_and_boundary_classification FAILED\n"
        f"POST-CLS-3 violation: poverty cut is not the unrounded inclusive 75th percentile\n"
        f"EXPECTED: 4.75\n"
        f"ACTUAL: {cut!r}\n"
        f"GUIDANCE: Compute the 75th percentile with the inclusive quantile method and do not round it"
    )

    # POST-CLS-1 on-point and off-point around the cut (17.025).
    cases = [
        ("12095000100", 17.025, 1, contract.CLASS_HIGH_NEED),
        ("12095000200", 17.024, 1, contract.CLASS_NO_GAP),
        ("12095000300", 40.0, 0, contract.CLASS_NO_GAP),
        ("12095000400", 0.0, 0, contract.CLASS_NO_GAP),
        ("12095000500", 100.0, 1, contract.CLASS_HIGH_NEED),
    ]
    for geoid, pct_poverty, lila_flag, expected_class in cases:
        produced = impl.classify_tract(geoid=geoid, pct_poverty=pct_poverty, lila_flag=lila_flag, cut=17.025)
        contract.validate_classification(
            contract.TractIndicators(geoid, pct_poverty, lila_flag),
            17.025,
            contract.TractClassification(produced.geoid, produced.tract_class, produced.missing_indicators),
        )
        assert produced.tract_class == expected_class and produced.missing_indicators == (), (
            f"test_poverty_cut_and_boundary_classification FAILED\n"
            f"POST-CLS-1 violation: wrong class for tract {geoid} (pct_poverty={pct_poverty}, lila_flag={lila_flag})\n"
            f"EXPECTED: class={expected_class!r}, missing_indicators=()\n"
            f"ACTUAL: class={produced.tract_class!r}, missing_indicators={produced.missing_indicators!r}\n"
            f"GUIDANCE: A tract with both indicators present is {contract.CLASS_HIGH_NEED!r} iff pct_poverty >= cut and lila_flag == 1"
        )


def test_missing_indicators_and_invalid_inputs() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: planner_map_contract (POST-CLS-2, PRE-CLS-1, ERRORS-CLS-1)
    - Enforces: POST-CLS-2 (blank indicator -> Insufficient data naming each blank) and ERRORS-CLS-1 (out-of-domain raises)
    - Category: negative / error
    - Risk tier: High — silent coercion of a blank or bad indicator hides missing evidence (INV-05, REQ-5, REQ-8)
    """
    # POST-CLS-2: blanks become Insufficient data, never No gap flagged, and name each blank indicator.
    blank_cases = [
        ("12095016515", None, 1, ("pct_poverty",)),
        ("12095990000", None, None, ("pct_poverty", contract.LILA_FLAG_COLUMN)),
        ("12095000600", 25.0, None, (contract.LILA_FLAG_COLUMN,)),
    ]
    for geoid, pct_poverty, lila_flag, expected_missing in blank_cases:
        produced = impl.classify_tract(geoid=geoid, pct_poverty=pct_poverty, lila_flag=lila_flag, cut=17.025)
        contract.validate_classification(
            contract.TractIndicators(geoid, pct_poverty, lila_flag),
            17.025,
            contract.TractClassification(produced.geoid, produced.tract_class, produced.missing_indicators),
        )
        assert produced.tract_class == contract.CLASS_INSUFFICIENT, (
            f"test_missing_indicators_and_invalid_inputs FAILED\n"
            f"POST-CLS-2 violation: tract {geoid} with blank indicator was not classed {contract.CLASS_INSUFFICIENT!r}\n"
            f"EXPECTED: {contract.CLASS_INSUFFICIENT!r}\n"
            f"ACTUAL: {produced.tract_class!r}\n"
            f"GUIDANCE: Any blank indicator must produce {contract.CLASS_INSUFFICIENT!r}, never {contract.CLASS_NO_GAP!r}"
        )
        assert produced.missing_indicators == expected_missing, (
            f"test_missing_indicators_and_invalid_inputs FAILED\n"
            f"POST-CLS-2 violation: tract {geoid} did not name every blank indicator\n"
            f"EXPECTED: {expected_missing!r}\n"
            f"ACTUAL: {produced.missing_indicators!r}\n"
            f"GUIDANCE: Record each blank indicator name in missing_indicators"
        )

    # PRE-CLS-1 / ERRORS-CLS-1: out-of-domain values raise InvalidIndicatorError citing the clause and tract.
    invalid_cases = [
        ("12095000700", -0.1, 0, "PRE-CLS-1"),
        ("12095000800", 100.1, 1, "PRE-CLS-1"),
        ("12095000900", float("nan"), 0, "ERRORS-CLS-1"),
        ("12095001000", 20.0, 2, "PRE-CLS-1"),
        ("12095001100", 20.0, True, "PRE-CLS-1"),
    ]
    for geoid, pct_poverty, lila_flag, expected_clause in invalid_cases:
        with pytest.raises(impl.InvalidIndicatorError) as exc_info:
            impl.classify_tract(geoid=geoid, pct_poverty=pct_poverty, lila_flag=lila_flag, cut=17.025)
        msg = str(exc_info.value)
        assert expected_clause in msg and geoid in msg, (
            f"test_missing_indicators_and_invalid_inputs FAILED\n"
            f"ERRORS-CLS-1 violation: exception message for tract {geoid} did not cite {expected_clause} and the tract\n"
            f"EXPECTED: substring {expected_clause!r} and {geoid!r}\n"
            f"ACTUAL: {msg!r}\n"
            f"GUIDANCE: Raise InvalidIndicatorError naming the violated clause and the tract geoid"
        )
