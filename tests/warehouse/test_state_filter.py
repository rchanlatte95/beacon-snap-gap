"""RED tests for SLICE-3 batch 2: state filter for Florida, New York and Utah.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py
- Authority: AUTHORITATIVE for the warehouse (SLICE-3, the Ingest)
- Clauses covered: POST-STATE-1..4, INV-STATE-1, ERRORS-STATE-1
- Requirements: REQ-27, REQ-28, REQ-29

The implementation is src/warehouse/state_filter.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: each cites clauses present in contracts/warehouse_contract.py.
  C2 VALUABLE: expected kept rows, counts and applied_filter strings are exact, hand-derived
     values; a wrong rule changes at least one of them.
  C3 NON-DUPLICATIVE: test 1 pins the three filter paths (state column with precedence, GEO_ID,
     and no state field); test 2 pins column validation and constant alignment.
  C4 NOT FUTURE-EDIT: every asserted behavior is a contracted clause.
"""

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import state_filter as impl

# Risk tier: HIGH. A wrong state filter drops in-scope rows or leaks out-of-scope states into a
# table whose provenance says it holds only FL, NY and UT.


def test_state_filter_across_state_column_geo_id_and_unfiltered_tables():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_state_filter(), validate_state_filter_outcome()
    - Enforces: POST-STATE-1, POST-STATE-2, POST-STATE-3, POST-STATE-4, INV-STATE-1
    - Category: positive, boundary
    - Risk tier: HIGH
    - Pyramid level: Unit (pure row filter over described columns and rows)
    - Equivalence partition:
      1. STATE_COLUMNS present (with two state columns to test precedence: BorrState before State,
         and abbreviation, full name and FIPS representations in TARGET_STATE_VALUES).
      2. No STATE_COLUMNS, GEO_ID present (national row, FL 12, NY 36, UT 49 kept; GA 13 dropped).
      3. Neither present (every row kept, FILTER_NONE).
    """
    # 1. POST-STATE-1: BorrState governs over State; FL, New York and 49 kept in input order.
    sba_cols = ("LoanID", "State", "BorrState")
    sba_rows = (
        {"LoanID": "1", "State": "GA", "BorrState": "FL"},
        {"LoanID": "2", "State": "FL", "BorrState": "GA"},  # dropped: BorrState governs
        {"LoanID": "3", "State": "TX", "BorrState": "New York"},
        {"LoanID": "4", "State": "CA", "BorrState": "49"},
    )
    sba_out = impl.filter_rows_by_state(sba_cols, sba_rows)
    assert [r["LoanID"] for r in sba_out.rows] == ["1", "3", "4"], (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-1 / INV-STATE-1 violation: kept rows or their order wrong\n"
        "EXPECTED: LoanID ['1', '3', '4'] (BorrState governs over State)\n"
        f"ACTUAL: {[r['LoanID'] for r in sba_out.rows]}\n"
        "GUIDANCE: the first column in STATE_COLUMNS governs; rows keep their input order"
    )
    assert (sba_out.rows_in_source, sba_out.rows_loaded) == (4, 3), (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-4 violation: recorded row counts wrong\n"
        "EXPECTED: (4, 3)\n"
        f"ACTUAL: {(sba_out.rows_in_source, sba_out.rows_loaded)}\n"
        "GUIDANCE: rows_in_source is the input count and rows_loaded is the kept count"
    )
    assert sba_out.applied_filter == 'state field "BorrState" in FL, NY, UT', (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-1 violation: applied_filter does not name the governing column\n"
        "EXPECTED: 'state field \"BorrState\" in FL, NY, UT'\n"
        f"ACTUAL: {sba_out.applied_filter!r}\n"
        "GUIDANCE: applied_filter names the column that governed"
    )
    contract.validate_state_filter_outcome(
        sba_cols,
        sba_rows,
        contract.StateFilterOutcome(
            sba_out.rows, sba_out.rows_in_source, sba_out.rows_loaded, sba_out.applied_filter
        ),
    )

    # 2. POST-STATE-2: GEO_ID governs when no STATE_COLUMNS column is present.
    acs_cols = ("GEO_ID", "B19013_E001")
    acs_rows = (
        {"GEO_ID": "0100000US", "B19013_E001": "80734"},  # national
        {"GEO_ID": "1400000US12095016510", "B19013_E001": "24533"},  # FL tract
        {"GEO_ID": "0500000US13121", "B19013_E001": "75000"},  # GA county: dropped
        {"GEO_ID": "0400000US36", "B19013_E001": "82000"},  # NY state
        {"GEO_ID": "1400000US49035100100", "B19013_E001": "68000"},  # UT tract
    )
    acs_out = impl.filter_rows_by_state(acs_cols, acs_rows)
    assert [r["GEO_ID"] for r in acs_out.rows] == [
        "0100000US",
        "1400000US12095016510",
        "0400000US36",
        "1400000US49035100100",
    ], (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-2 violation: GEO_ID filter kept the wrong rows\n"
        "EXPECTED: national row plus FL (12), NY (36), UT (49)\n"
        f"ACTUAL: {[r['GEO_ID'] for r in acs_out.rows]}\n"
        "GUIDANCE: GEO_ID keeps 0100000US and any row with US12, US36 or US49"
    )
    assert (acs_out.rows_in_source, acs_out.rows_loaded) == (5, 4), (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-4 violation on GEO_ID table\n"
        "EXPECTED: (5, 4)\n"
        f"ACTUAL: {(acs_out.rows_in_source, acs_out.rows_loaded)}\n"
        "GUIDANCE: counts match input and kept rows"
    )
    contract.validate_state_filter_outcome(
        acs_cols,
        acs_rows,
        contract.StateFilterOutcome(
            acs_out.rows, acs_out.rows_in_source, acs_out.rows_loaded, acs_out.applied_filter
        ),
    )

    # 3. POST-STATE-3: no state column and no GEO_ID keeps every row with FILTER_NONE.
    raw_cols = ("SCRAMID", "REGION")
    raw_rows = ({"SCRAMID": "a", "REGION": "3"}, {"SCRAMID": "b", "REGION": "1"})
    raw_out = impl.filter_rows_by_state(raw_cols, raw_rows)
    assert raw_out.rows == raw_rows, (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-3 / INV-STATE-1 violation: unfiltered table lost or altered a row\n"
        f"EXPECTED: {raw_rows}\n"
        f"ACTUAL: {raw_out.rows}\n"
        "GUIDANCE: a table with no state field keeps every row unaltered"
    )
    assert raw_out.applied_filter == contract.FILTER_NONE, (
        "test_state_filter_across_state_column_geo_id_and_unfiltered_tables FAILED\n"
        "POST-STATE-3 violation: applied_filter is not FILTER_NONE\n"
        f"EXPECTED: {contract.FILTER_NONE!r}\n"
        f"ACTUAL: {raw_out.applied_filter!r}\n"
        "GUIDANCE: applied_filter is FILTER_NONE when no state field is present"
    )


def test_invalid_columns_rejected_and_constants_align():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract validate_table_columns(), STATE_COLUMNS, TARGET_STATE_VALUES,
      FILTER_NONE
    - Enforces: ERRORS-STATE-1, POST-STATE-1, POST-STATE-3
    - Category: error, invariant
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition (invalid columns): empty sequence, empty name, duplicate name.
    """
    bad_column_sets = [("empty columns", ()), ("empty name", ("A", "")), ("duplicate", ("A", "A"))]
    for label, cols in bad_column_sets:
        with pytest.raises(contract.InvalidTableError):
            contract.validate_table_columns(cols)
        try:
            impl.filter_rows_by_state(cols, ())
        except impl.InvalidTableError:
            continue
        except Exception as exc:  # noqa: BLE001 - the clause names the one allowed class
            pytest.fail(
                "test_invalid_columns_rejected_and_constants_align FAILED\n"
                f"ERRORS-STATE-1 violation for {label}: wrong error class\n"
                "EXPECTED: InvalidTableError\n"
                f"ACTUAL: {type(exc).__name__}: {exc}\n"
                "GUIDANCE: invalid columns raise InvalidTableError"
            )
        pytest.fail(
            "test_invalid_columns_rejected_and_constants_align FAILED\n"
            f"ERRORS-STATE-1 violation for {label}: accepted\n"
            "EXPECTED: InvalidTableError\n"
            "ACTUAL: returned an outcome\n"
            "GUIDANCE: empty or duplicate column names are rejected"
        )

    assert tuple(impl.STATE_COLUMNS) == contract.STATE_COLUMNS, (
        "test_invalid_columns_rejected_and_constants_align FAILED\n"
        "POST-STATE-1 violation: STATE_COLUMNS precedence differs\n"
        f"EXPECTED: {contract.STATE_COLUMNS}\n"
        f"ACTUAL: {tuple(impl.STATE_COLUMNS)}\n"
        "GUIDANCE: the state-column priority order equals the contract's"
    )
    assert frozenset(impl.TARGET_STATE_VALUES) == contract.TARGET_STATE_VALUES, (
        "test_invalid_columns_rejected_and_constants_align FAILED\n"
        "POST-STATE-1 violation: TARGET_STATE_VALUES differs\n"
        f"EXPECTED: {sorted(contract.TARGET_STATE_VALUES)}\n"
        f"ACTUAL: {sorted(impl.TARGET_STATE_VALUES)}\n"
        "GUIDANCE: the accepted FL, NY and UT values equal the contract's"
    )
    assert impl.FILTER_NONE == contract.FILTER_NONE, (
        "test_invalid_columns_rejected_and_constants_align FAILED\n"
        "POST-STATE-3 violation: FILTER_NONE differs\n"
        f"EXPECTED: {contract.FILTER_NONE!r}\n"
        f"ACTUAL: {impl.FILTER_NONE!r}\n"
        "GUIDANCE: the unfiltered sentinel equals the contract's"
    )
