"""RED tests for SLICE-3 batch 3: table provenance records and local-disk-only sources.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py
- Authority: AUTHORITATIVE for the warehouse (SLICE-3, the Ingest)
- Clauses covered: POST-PROV-1..3, INV-PROV-1, FORBIDDEN-PROV-1, ERRORS-PROV-1
- Requirements: REQ-28, REQ-29

The implementation is src/warehouse/provenance.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: each cites clauses present in contracts/warehouse_contract.py.
  C2 VALUABLE: exact provenance field values, exact SHA-256 digest, and exact source-file bytes
     and mtime are asserted; any wrong normalization or source mutation fails.
  C3 NON-DUPLICATIVE: test 1 pins provenance construction, NOT_RECORDED normalization, and local
     disk SHA-256 without mutating the file; test 2 pins input error boundaries and constant
     alignment.
  C4 NOT FUTURE-EDIT: every asserted behavior is a contracted clause in CONTRACT_PROVENANCE.
"""

import hashlib
from pathlib import Path

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import provenance as impl

# Risk tier: HIGH. A wrong provenance builder either invents unstated metadata or corrupts
# citations; a reader that alters local source files violates REQ-28.


def test_provenance_record_and_local_file_digest_preserve_source_and_record_not_recorded(
    tmp_path: Path,
):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_table_provenance(), validate_table_provenance(),
      validate_sources_unaltered()
    - Enforces: POST-PROV-1, POST-PROV-2, POST-PROV-3, INV-PROV-1, FORBIDDEN-PROV-1
    - Category: positive, boundary, invariant
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition:
      1. Stated provenance fields (trimmed and preserved verbatim).
      2. Absent or whitespace provenance fields (normalized to "not recorded", never blank).
      3. Local disk source file read for SHA-256 (exact digest, bytes unaltered before/after).
    """
    sample_file = tmp_path / "sample.csv"
    sample_bytes = b"GEO_ID,val\n0100000US,10\n"
    sample_file.write_bytes(sample_bytes)
    expected_digest = hashlib.sha256(sample_bytes).hexdigest()
    digest = impl.sha256_file(sample_file)
    after_bytes = sample_file.read_bytes()
    assert after_bytes == sample_bytes, (
        "test_provenance_record_and_local_file_digest_preserve_source_and_record_not_recorded "
        "FAILED\n"
        "INV-PROV-1 violation: reading a local source file altered its bytes\n"
        f"EXPECTED: {sample_bytes!r}\n"
        f"ACTUAL: {after_bytes!r}\n"
        "GUIDANCE: sha256_file reads local disk only and leaves the file unaltered"
    )
    assert digest == expected_digest, (
        "test_provenance_record_and_local_file_digest_preserve_source_and_record_not_recorded "
        "FAILED\n"
        "INV-PROV-1 violation: sha256_file digest disagrees with sample_bytes SHA-256\n"
        f"EXPECTED: {expected_digest!r}\n"
        f"ACTUAL: {digest!r}\n"
        "GUIDANCE: sha256_file returns the exact lowercase hex SHA-256 digest of the file on disk"
    )
    contract.validate_sources_unaltered({str(sample_file): digest}, {str(sample_file): digest})

    rec = impl.build_table_provenance(
        table_name=" sba_7a_2020 ",
        source_file=" cache:sba/7a.csv ",
        sha256=digest,
        applied_filter='state field "BorrState" in FL, NY, UT',
        rows_in_source=100,
        rows_loaded=25,
        origin_url=" https://data.sba.gov/7a.csv ",
        retrieved_at="2026-11-08T09:08:25Z",
        publisher="U.S. Small Business Administration",
        license_text=None,
        as_of="   ",
    )
    want = contract.expected_table_provenance(
        table_name="sba_7a_2020",
        source_file="cache:sba/7a.csv",
        sha256=digest,
        applied_filter='state field "BorrState" in FL, NY, UT',
        rows_in_source=100,
        rows_loaded=25,
        origin_url="https://data.sba.gov/7a.csv",
        retrieved_at="2026-11-08T09:08:25Z",
        publisher="U.S. Small Business Administration",
        license_text=None,
        as_of="   ",
    )
    assert (rec.license, rec.as_of) == ("not recorded", "not recorded"), (
        "test_provenance_record_and_local_file_digest_preserve_source_and_record_not_recorded "
        "FAILED\n"
        "POST-PROV-2 / FORBIDDEN-PROV-1 violation: absent fields must read 'not recorded'\n"
        "EXPECTED: ('not recorded', 'not recorded')\n"
        f"ACTUAL: {(rec.license, rec.as_of)!r}\n"
        "GUIDANCE: None or whitespace-only provenance fields normalize to NOT_RECORDED"
    )
    assert (rec.rows_in_source, rec.rows_loaded) == (100, 25), (
        "test_provenance_record_and_local_file_digest_preserve_source_and_record_not_recorded "
        "FAILED\n"
        "POST-PROV-3 violation: row counts do not match input and loaded counts\n"
        "EXPECTED: (100, 25)\n"
        f"ACTUAL: {(rec.rows_in_source, rec.rows_loaded)!r}\n"
        "GUIDANCE: rows_in_source and rows_loaded record the exact non-negative counts"
    )
    contract.validate_table_provenance(
        contract.TableProvenance(
            table_name=rec.table_name,
            source_file=rec.source_file,
            origin_url=rec.origin_url,
            retrieved_at=rec.retrieved_at,
            sha256=rec.sha256,
            publisher=rec.publisher,
            license=rec.license,
            as_of=rec.as_of,
            applied_filter=rec.applied_filter,
            rows_in_source=rec.rows_in_source,
            rows_loaded=rec.rows_loaded,
        ),
        want,
    )
    assert expected_digest == rec.sha256


def test_invalid_provenance_inputs_rejected_and_constants_align():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_table_provenance(), NOT_RECORDED,
      PROVENANCE_TEXT_FIELDS
    - Enforces: ERRORS-PROV-1, POST-PROV-2, FORBIDDEN-PROV-1
    - Category: error, boundary, invariant
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition (invalid provenance inputs):
      1. blank table_name
      2. blank source_file
      3. malformed sha256 (wrong length or uppercase/non-hex)
      4. blank applied_filter
      5. negative rows_in_source or rows_loaded
      6. rows_loaded > rows_in_source
    """
    valid_sha = "a" * 64
    base_kwargs = {
        "table_name": "tbl",
        "source_file": "cache:f.csv",
        "sha256": valid_sha,
        "applied_filter": "none (no state field)",
        "rows_in_source": 10,
        "rows_loaded": 5,
    }
    bad_cases = [
        ("blank table_name", {**base_kwargs, "table_name": "  "}),
        ("blank source_file", {**base_kwargs, "source_file": ""}),
        ("short sha256", {**base_kwargs, "sha256": "abc123"}),
        ("uppercase sha256", {**base_kwargs, "sha256": "A" * 64}),
        ("blank applied_filter", {**base_kwargs, "applied_filter": " "}),
        ("negative rows_in_source", {**base_kwargs, "rows_in_source": -1, "rows_loaded": 0}),
        ("negative rows_loaded", {**base_kwargs, "rows_loaded": -1}),
        ("rows_loaded > rows_in_source", {**base_kwargs, "rows_in_source": 5, "rows_loaded": 6}),
    ]
    for label, kwargs in bad_cases:
        with pytest.raises(contract.InvalidProvenanceInputError):
            contract.expected_table_provenance(**kwargs)  # type: ignore[arg-type]
        try:
            impl.build_table_provenance(**kwargs)  # type: ignore[arg-type]
        except impl.InvalidProvenanceInputError:
            continue
        except Exception as exc:  # noqa: BLE001 - the clause names the one allowed class
            pytest.fail(
                "test_invalid_provenance_inputs_rejected_and_constants_align FAILED\n"
                f"ERRORS-PROV-1 violation for {label}: wrong exception class\n"
                "EXPECTED: InvalidProvenanceInputError\n"
                f"ACTUAL: {type(exc).__name__}: {exc}\n"
                "GUIDANCE: invalid provenance inputs raise InvalidProvenanceInputError"
            )
        pytest.fail(
            "test_invalid_provenance_inputs_rejected_and_constants_align FAILED\n"
            f"ERRORS-PROV-1 violation for {label}: invalid input was accepted\n"
            "EXPECTED: InvalidProvenanceInputError\n"
            "ACTUAL: returned a TableProvenance\n"
            "GUIDANCE: reject blank required identifiers, bad sha256, and impossible row counts"
        )

    assert impl.NOT_RECORDED == contract.NOT_RECORDED, (
        "test_invalid_provenance_inputs_rejected_and_constants_align FAILED\n"
        "POST-PROV-2 violation: NOT_RECORDED sentinel differs\n"
        f"EXPECTED: {contract.NOT_RECORDED!r}\n"
        f"ACTUAL: {impl.NOT_RECORDED!r}\n"
        "GUIDANCE: absent provenance sentinel equals the contract's"
    )
    assert tuple(impl.PROVENANCE_TEXT_FIELDS) == contract.PROVENANCE_TEXT_FIELDS, (
        "test_invalid_provenance_inputs_rejected_and_constants_align FAILED\n"
        "FORBIDDEN-PROV-1 violation: PROVENANCE_TEXT_FIELDS differs\n"
        f"EXPECTED: {contract.PROVENANCE_TEXT_FIELDS!r}\n"
        f"ACTUAL: {tuple(impl.PROVENANCE_TEXT_FIELDS)!r}\n"
        "GUIDANCE: provenance text field tuple equals the contract's"
    )
