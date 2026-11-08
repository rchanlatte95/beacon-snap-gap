"""RED tests for SLICE-3 batch 4: glossary extraction and SEQ-5 provenance write order.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py
- Authority: AUTHORITATIVE for the warehouse (SLICE-3, the Ingest)
- Clauses covered: POST-GLOSS-1..2, INV-GLOSS-1, FORBIDDEN-GLOSS-1, SEQ-5, ERRORS-GLOSS-1
  (INV-STORAGE-1 is tool-verified via WAREHOUSE_GCP_PROJECT alignment)
- Requirements: REQ-28, REQ-29, REQ-30, REQ-31

The implementation is src/warehouse/glossary.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: each cites clauses present in contracts/warehouse_contract.py.
  C2 VALUABLE: exact GlossaryEntry sequences, exact skipped blank rows, and exact lifecycle write
     event ordering are asserted; any wrong extraction, dedupe or ordering fails.
  C3 NON-DUPLICATIVE: test 1 pins glossary extraction, deduplication, blank-row exclusion and
     SEQ-5 provenance write ordering; test 2 pins invalid dictionary spec rejection and constant
     alignment.
  C4 NOT FUTURE-EDIT: every asserted behavior is a contracted clause in CONTRACT_GLOSSARY.
"""

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import glossary as impl

# Risk tier: HIGH. A wrong glossary builder drops definitions or fabricates blank rows; writing
# provenance tables before data tables finishes leaves loaded tables with no provenance row.


def test_glossary_extraction_deduplication_and_seq5_provenance_write_order():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_glossary_entries(), validate_glossary_entries(),
      validate_ingest_write_sequence()
    - Enforces: POST-GLOSS-1, POST-GLOSS-2, INV-GLOSS-1, FORBIDDEN-GLOSS-1, SEQ-5
    - Category: positive, boundary, invariant, integration (SEQ-5)
    - Risk tier: HIGH
    - Pyramid level: Unit / Integration (SEQ-5 lifecycle path)
    - Equivalence partition:
      1. Valid dictionary rows with surrounding whitespace (trimmed and kept in order).
      2. Duplicate (source_table, term, definition) row (deduplicated keeping first).
      3. Blank or whitespace-only term or definition (skipped; never emitted or fabricated).
      4. SEQ-5 lifecycle path: run_ingest_manifest writes data tables and glossary first, then
         files, catalog and sources, and only then emits report_success.
    """
    sba_rows = (
        {"Field Name": " BorrState ", "Definition": " Borrower state abbreviation "},
        {"Field Name": "BorrState", "Definition": "Borrower state abbreviation"},  # duplicate
        {"Field Name": "GrossApproval", "Definition": "   "},  # blank definition: skipped
        {"Field Name": "", "Definition": "No field name"},  # blank term: skipped
        {"Field Name": "JobsSupported", "Definition": "Total jobs supported by the loan"},
    )
    nri_rows = (
        {"Field_Name": "RISK_SCORE", "Field_Alias": "National Risk Index - Score - Composite"},
    )
    impl_specs = (
        impl.DictionaryTableSpec(
            source_table="sba_7a_dict",
            dataset_id="DS-X5",
            term_column="Field Name",
            definition_column="Definition",
            rows=sba_rows,
        ),
        impl.DictionaryTableSpec(
            source_table="fema_nri_dict",
            dataset_id="DS-X17",
            term_column="Field_Name",
            definition_column="Field_Alias",
            rows=nri_rows,
        ),
    )
    contract_specs = (
        contract.DictionaryTableSpec(
            source_table="sba_7a_dict",
            dataset_id="DS-X5",
            term_column="Field Name",
            definition_column="Definition",
            rows=sba_rows,
        ),
        contract.DictionaryTableSpec(
            source_table="fema_nri_dict",
            dataset_id="DS-X17",
            term_column="Field_Name",
            definition_column="Field_Alias",
            rows=nri_rows,
        ),
    )
    got = impl.build_glossary_entries(impl_specs)
    assert [(e.source_table, e.dataset_id, e.term, e.definition) for e in got] == [
        ("sba_7a_dict", "DS-X5", "BorrState", "Borrower state abbreviation"),
        ("sba_7a_dict", "DS-X5", "JobsSupported", "Total jobs supported by the loan"),
        (
            "fema_nri_dict",
            "DS-X17",
            "RISK_SCORE",
            "National Risk Index - Score - Composite",
        ),
    ], (
        "test_glossary_extraction_deduplication_and_seq5_provenance_write_order FAILED\n"
        "POST-GLOSS-1 / POST-GLOSS-2 / INV-GLOSS-1 / FORBIDDEN-GLOSS-1 violation: glossary rows "
        "disagree\n"
        "EXPECTED: 3 trimmed, deduplicated entries with blank term/definition rows excluded\n"
        f"ACTUAL: {got!r}\n"
        "GUIDANCE: keep non-empty trimmed (term, definition) rows in input order without duplicates"
    )
    contract.validate_glossary_entries(
        contract_specs,
        tuple(
            contract.GlossaryEntry(e.source_table, e.dataset_id, e.term, e.definition) for e in got
        ),
    )

    # SEQ-5 lifecycle path: run_ingest_write_plan executes the parent ingest write lifecycle and
    # returns the ordered event log.
    events = impl.run_ingest_write_plan(
        data_tables=("sba_foia_7a_fy2020_present_asof_260930", "census_pop_co_est2025_alldata"),
        dictionary_specs=impl_specs,
    )
    contract.validate_ingest_write_sequence(events)
    assert events == (
        "load_table:sba_foia_7a_fy2020_present_asof_260930",
        "load_table:census_pop_co_est2025_alldata",
        "load_table:glossary",
        "files",
        "catalog",
        "sources",
        "report_success",
    ), (
        "test_glossary_extraction_deduplication_and_seq5_provenance_write_order FAILED\n"
        "SEQ-5 violation: provenance tables were not written after data/glossary tables and "
        "before report_success\n"
        "EXPECTED: load_table:* then files, catalog, sources, then report_success\n"
        f"ACTUAL: {events!r}\n"
        "GUIDANCE: write files, catalog and sources after all tables load and before report_success"
    )


def test_invalid_glossary_specs_rejected_and_constants_align():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_glossary_entries(), GLOSSARY_COLUMNS,
      PROVENANCE_TABLES, WAREHOUSE_GCP_PROJECT
    - Enforces: ERRORS-GLOSS-1, POST-GLOSS-1, SEQ-5, INV-STORAGE-1
    - Category: error, boundary, invariant
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition (invalid DictionaryTableSpec):
      1. blank source_table
      2. blank dataset_id
      3. blank term_column
      4. blank definition_column
      5. row missing declared term_column or definition_column key
    """
    valid_row = ({"Field": "X", "Desc": "Y"},)
    bad_specs = [
        (
            "blank source_table",
            (" ", "DS-X5", "Field", "Desc", valid_row),
        ),
        (
            "blank dataset_id",
            ("tbl", "", "Field", "Desc", valid_row),
        ),
        (
            "blank term_column",
            ("tbl", "DS-X5", "  ", "Desc", valid_row),
        ),
        (
            "blank definition_column",
            ("tbl", "DS-X5", "Field", "", valid_row),
        ),
        (
            "missing term_column in row",
            ("tbl", "DS-X5", "Field", "Desc", ({"Other": "X", "Desc": "Y"},)),
        ),
        (
            "missing definition_column in row",
            ("tbl", "DS-X5", "Field", "Desc", ({"Field": "X"},)),
        ),
    ]
    for label, args in bad_specs:
        c_spec = (contract.DictionaryTableSpec(*args),)
        with pytest.raises(contract.InvalidGlossarySourceError):
            contract.expected_glossary_entries(c_spec)
        i_spec = (impl.DictionaryTableSpec(*args),)
        try:
            impl.build_glossary_entries(i_spec)
        except impl.InvalidGlossarySourceError:
            continue
        except Exception as exc:  # noqa: BLE001 - the clause names the one allowed class
            pytest.fail(
                "test_invalid_glossary_specs_rejected_and_constants_align FAILED\n"
                f"ERRORS-GLOSS-1 violation for {label}: wrong exception class\n"
                "EXPECTED: InvalidGlossarySourceError\n"
                f"ACTUAL: {type(exc).__name__}: {exc}\n"
                "GUIDANCE: invalid dictionary specs raise InvalidGlossarySourceError"
            )
        pytest.fail(
            "test_invalid_glossary_specs_rejected_and_constants_align FAILED\n"
            f"ERRORS-GLOSS-1 violation for {label}: invalid spec was accepted\n"
            "EXPECTED: InvalidGlossarySourceError\n"
            "ACTUAL: returned glossary entries\n"
            "GUIDANCE: reject blank identifiers and rows missing the declared columns"
        )

    assert tuple(impl.GLOSSARY_COLUMNS) == contract.GLOSSARY_COLUMNS, (
        "test_invalid_glossary_specs_rejected_and_constants_align FAILED\n"
        "POST-GLOSS-1 violation: GLOSSARY_COLUMNS differs\n"
        f"EXPECTED: {contract.GLOSSARY_COLUMNS!r}\n"
        f"ACTUAL: {tuple(impl.GLOSSARY_COLUMNS)!r}\n"
        "GUIDANCE: glossary column tuple equals the contract's"
    )
    assert tuple(impl.PROVENANCE_TABLES) == contract.PROVENANCE_TABLES, (
        "test_invalid_glossary_specs_rejected_and_constants_align FAILED\n"
        "SEQ-5 violation: PROVENANCE_TABLES differs\n"
        f"EXPECTED: {contract.PROVENANCE_TABLES!r}\n"
        f"ACTUAL: {tuple(impl.PROVENANCE_TABLES)!r}\n"
        "GUIDANCE: provenance table tuple equals the contract's"
    )
    assert impl.WAREHOUSE_GCP_PROJECT == contract.WAREHOUSE_GCP_PROJECT, (
        "test_invalid_glossary_specs_rejected_and_constants_align FAILED\n"
        "INV-STORAGE-1 violation: WAREHOUSE_GCP_PROJECT differs\n"
        f"EXPECTED: {contract.WAREHOUSE_GCP_PROJECT!r}\n"
        f"ACTUAL: {impl.WAREHOUSE_GCP_PROJECT!r}\n"
        "GUIDANCE: canonical GCS project constant equals the contract's"
    )
