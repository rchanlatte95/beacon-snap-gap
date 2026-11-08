"""RED tests for SLICE-3 batch 1: which files the warehouse loads and which it excludes.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py
- Authority: AUTHORITATIVE for the warehouse (SLICE-3, the Ingest)
- Clauses covered: POST-SCOPE-1..6, INV-SCOPE-1, INV-SCOPE-2, FORBIDDEN-SCOPE-1, ERRORS-SCOPE-1
- Requirements: REQ-25, REQ-26

The implementation is src/warehouse/scope.py. It does not import the contract (CL11-F); these
tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: each cites clauses present in contracts/warehouse_contract.py.
  C2 VALUABLE: expected decisions are exact, hand-derived values; a wrong rule changes at least
     one of them.
  C3 NON-DUPLICATIVE: test 1 pins the decisions of one mixed file set; test 2 pins order
     independence and input rejection.
  C4 NOT FUTURE-EDIT: every asserted behavior is a contracted clause.
"""

import random
from datetime import date

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import scope as impl

# Risk tier: HIGH. A wrong decision silently drops a source from the warehouse or loads a
# duplicate, and every later answer cites what the warehouse holds.

# (path, sha256, file_format, reference_end, is_base_geography, release_id, expected)
CASES = [
    ("recent.csv", "hA", "csv", "2026-09-30", False, None, ("load", None)),  # POST-SCOPE-1
    ("boundary_in.csv", "hB", "csv", "2024-01-01", False, None, ("load", None)),  # on-point
    ("boundary_out.csv", "hC", "csv", "2023-12-31", False, None, ("exclude", "time_scope")),
    # POST-SCOPE-3: time scope takes precedence over duplicate content (hA is loaded above)
    ("old_dup.csv", "hA", "csv", "2019-09-30", False, None, ("exclude", "time_scope")),
    ("geo.csv", "hE", "csv", "2020-12-31", True, None, ("load", None)),  # POST-SCOPE-2
    ("geo_dup.csv", "hE", "csv", "1999-12-31", True, None, ("exclude", "duplicate_content")),
    ("sram.csv", "hG", "csv", "2025-12-31", False, "sram25", ("load", None)),  # POST-SCOPE-5
    ("sram.xlsx", "hF", "xlsx", "2025-12-31", False, "sram25", ("exclude", "duplicate_format")),
    ("sram.sas", "hK", "sas", "2025-01-01", False, "sram25", ("exclude", "duplicate_format")),
    ("unknown.xlsx", "hH", "xlsx", None, False, None, ("load", None)),  # POST-SCOPE-6
    ("same.csv", "hA", "csv", "2025-06-30", False, None, ("exclude", "duplicate_content")),
]


def _kwargs(case):
    path, sha, fmt, end, geo, rel, _ = case
    return {
        "path": path,
        "sha256": sha,
        "file_format": fmt,
        "reference_end": end,
        "is_base_geography": geo,
        "release_id": rel,
    }


def _impl_files():
    return [impl.make_source_file(**_kwargs(c)) for c in CASES]


def _contract_files():
    return [contract.validate_source_file(**_kwargs(c)) for c in CASES]


def test_scope_decisions_for_a_mixed_file_set():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_scope_decisions()
    - Enforces: POST-SCOPE-1, POST-SCOPE-2, POST-SCOPE-3, POST-SCOPE-4, POST-SCOPE-5,
      POST-SCOPE-6, INV-SCOPE-1, FORBIDDEN-SCOPE-1
    - Category: positive, boundary, negative
    - Risk tier: HIGH
    - Pyramid level: Unit (pure decision over described files)
    - Equivalence partition (reference_end): on-point 2024-01-01 loads; off-point 2023-12-31
      excludes; interior 2026-09-30 loads; unknown loads. One representative per class.
    """
    decisions = impl.decide_scope(_impl_files())

    assert len(decisions) == len(CASES), (
        "test_scope_decisions_for_a_mixed_file_set FAILED\n"
        "INV-SCOPE-1 violation: not one decision per file\n"
        f"EXPECTED: {len(CASES)} decisions in input order\n"
        f"ACTUAL: {len(decisions)} decisions\n"
        "GUIDANCE: every described file receives exactly one decision, in the order given"
    )
    for case, got in zip(CASES, decisions, strict=True):
        path, expected = case[0], case[6]
        assert got.path == path, (
            "test_scope_decisions_for_a_mixed_file_set FAILED\n"
            "INV-SCOPE-1 violation: decision out of order\n"
            f"EXPECTED: decision for {path!r} at this position\n"
            f"ACTUAL: decision for {got.path!r}\n"
            "GUIDANCE: decisions follow the input order"
        )
        assert (got.decision, got.reason) == expected, (
            "test_scope_decisions_for_a_mixed_file_set FAILED\n"
            f"POST-SCOPE violation for {path!r} "
            "(clauses POST-SCOPE-1 to POST-SCOPE-6, FORBIDDEN-SCOPE-1)\n"
            f"EXPECTED: {expected}\n"
            f"ACTUAL: {(got.decision, got.reason)}\n"
            "GUIDANCE: time scope first, then duplicate content, then duplicate format; "
            "base geography skips time scope; an unknown period loads"
        )

    # The contract oracle must agree with the implementation on the same files.
    contract_decisions = tuple(
        contract.ScopeDecision(d.path, d.decision, d.reason) for d in decisions
    )
    contract.validate_scope_decisions(_contract_files(), contract_decisions)


def _bad(**overrides):
    base = {
        "path": "a.csv",
        "sha256": "h",
        "file_format": "csv",
        "reference_end": None,
        "is_base_geography": False,
        "release_id": None,
    }
    return {**base, **overrides}


_BAD_INPUTS = [
    ("empty path", _bad(path="")),
    ("empty sha256", _bad(sha256="")),
    ("unknown file_format", _bad(path="a.parquet", file_format="parquet")),
    ("date not YYYY-MM-DD", _bad(reference_end="24-01-01")),
    ("date not a real day", _bad(reference_end="2024-13-01")),
    ("empty release_id", _bad(release_id="")),
]


def test_order_independence_and_invalid_input_rejection():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_scope_decisions(), validate_source_file(),
      SCOPE_START, EXCLUSION_REASONS, FORMAT_RANK
    - Enforces: INV-SCOPE-2, ERRORS-SCOPE-1
    - Category: invariant, error
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition (invalid input): one representative per rejected class
      (six classes in _BAD_INPUTS).
    """
    # INV-SCOPE-2: the listing order does not change any decision.
    files = _impl_files()
    baseline = {d.path: (d.decision, d.reason) for d in impl.decide_scope(files)}
    rng = random.Random(2024)  # noqa: S311 - seeded shuffle of test inputs, not a secret
    for round_no in range(25):
        shuffled = files[:]
        rng.shuffle(shuffled)
        got = {d.path: (d.decision, d.reason) for d in impl.decide_scope(shuffled)}
        assert got == baseline, (
            "test_order_independence_and_invalid_input_rejection FAILED\n"
            f"INV-SCOPE-2 violation in shuffle {round_no}: a decision changed with the order\n"
            f"EXPECTED: {baseline}\n"
            f"ACTUAL: {got}\n"
            "GUIDANCE: the outcome for each file depends on the file set, never on its position"
        )

    # ERRORS-SCOPE-1: invalid descriptions raise the declared error, as the contract validator does.
    for label, kwargs in _BAD_INPUTS:
        with pytest.raises(contract.InvalidSourceFileError):
            contract.validate_source_file(**kwargs)
        try:
            impl.make_source_file(**kwargs)
        except impl.InvalidSourceFileError:
            continue
        except Exception as exc:  # noqa: BLE001 - the clause names the one allowed class
            pytest.fail(
                "test_order_independence_and_invalid_input_rejection FAILED\n"
                f"ERRORS-SCOPE-1 violation for {label}: wrong error class\n"
                "EXPECTED: InvalidSourceFileError\n"
                f"ACTUAL: {type(exc).__name__}: {exc}\n"
                "GUIDANCE: an invalid file description is rejected with the declared error"
            )
        pytest.fail(
            "test_order_independence_and_invalid_input_rejection FAILED\n"
            f"ERRORS-SCOPE-1 violation for {label}: accepted\n"
            "EXPECTED: InvalidSourceFileError\n"
            "ACTUAL: a source file was built\n"
            "GUIDANCE: an invalid file description is rejected, never carried forward"
        )

    # Contract constants and the implementation's own copies agree (CL11-F bridge).
    assert impl.SCOPE_START == contract.SCOPE_START == date(2024, 1, 1), (
        "test_order_independence_and_invalid_input_rejection FAILED\n"
        "POST-SCOPE-1 violation: scope start differs\n"
        f"EXPECTED: {contract.SCOPE_START}\n"
        f"ACTUAL: {impl.SCOPE_START}\n"
        "GUIDANCE: the implementation's scope start equals the contract's"
    )
    assert tuple(impl.EXCLUSION_REASONS) == contract.EXCLUSION_REASONS, (
        "test_order_independence_and_invalid_input_rejection FAILED\n"
        "FORBIDDEN-SCOPE-1 violation: reason list differs\n"
        f"EXPECTED: {contract.EXCLUSION_REASONS}\n"
        f"ACTUAL: {tuple(impl.EXCLUSION_REASONS)}\n"
        "GUIDANCE: the reasons and their precedence equal the contract's"
    )
    assert dict(impl.FORMAT_RANK) == dict(contract.FORMAT_RANK), (
        "test_order_independence_and_invalid_input_rejection FAILED\n"
        "POST-SCOPE-5 violation: format ranks differ\n"
        f"EXPECTED: {dict(contract.FORMAT_RANK)}\n"
        f"ACTUAL: {dict(impl.FORMAT_RANK)}\n"
        "GUIDANCE: the preferred-format order equals the contract's"
    )
