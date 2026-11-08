"""RED tests for SLICE-3 batch 5: the data adapter's location and relative table locations.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_ADAPTER)
- Authority: AUTHORITATIVE for the warehouse and its data adapter (SLICE-3)
- Clauses covered: POST-ADAPT-1..3, ERRORS-ADAPT-1..3, FORBIDDEN-ADAPT-1
- Requirements: REQ-47, REQ-48

The implementation is src/warehouse/adapter.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites a clause present in CONTRACT_ADAPTER.
  C2 VALUABLE: exact locations and paths are asserted; a default location, a second variable,
     a relative path accepted, or an absolute table location resolved each fails a test.
  C3 NON-DUPLICATIVE: test 1 pins where the location comes from and that the warehouse exists;
     test 2 pins the relative table location and how it resolves under any location.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.
"""

from pathlib import Path

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import adapter as impl

# Risk tier: HIGH. A wrong location rule ships a warehouse that opens only on the machine that
# built it, which is the defect observed in O2 to O4 of plans/warehouse-adapter.refactor.md.


def test_location_comes_only_from_the_configured_variable_and_must_hold_a_warehouse(
    tmp_path: Path,
):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract validate_warehouse_location()
    - Enforces: POST-ADAPT-1, ERRORS-ADAPT-1, ERRORS-ADAPT-2
    - Category: positive, negative, boundary
    - Risk tier: HIGH
    - Pyramid level: Unit (environment mapping) plus filesystem (tmp_path) for ERRORS-ADAPT-2
    - Equivalence partition (configured value): absolute with trailing slash (valid, normalized);
      unset; whitespace; relative; contains '..'. Decoy variables present in every case.
    """
    decoys = {"WAREHOUSE_DIR": "/decoy/a", "DATA_ROOT": "/decoy/b", "HOME": "/decoy/home"}
    # The location rule reads text only, so no directory is needed. A fixed POSIX path is
    # absolute on every platform; a Windows tmp_path (drive letter) is never a POSIX absolute path.
    location = "/srv/beacon/warehouse"
    env = {**decoys, contract.WAREHOUSE_LOCATION_ENV: f"{location}/"}
    got = impl.warehouse_location(env)
    want = contract.validate_warehouse_location(env)
    assert got.root == want.root == location, (
        "test_location_comes_only_from_the_configured_variable_and_must_hold_a_warehouse FAILED\n"
        "POST-ADAPT-1 violation: location not taken from WAREHOUSE_LOCATION as a normalized path\n"
        f"EXPECTED: {location!r} (contract oracle {want.root!r})\n"
        f"ACTUAL: {got.root!r}\n"
        "GUIDANCE: only WAREHOUSE_LOCATION supplies the location; normalize it; ignore others"
    )

    bad_envs = [
        ("unset", dict(decoys)),
        ("whitespace", {**decoys, contract.WAREHOUSE_LOCATION_ENV: "   "}),
        ("relative", {**decoys, contract.WAREHOUSE_LOCATION_ENV: "data/cache/warehouse"}),
        ("dot-dot", {**decoys, contract.WAREHOUSE_LOCATION_ENV: f"{location}/../escape"}),
    ]
    for label, bad in bad_envs:
        with pytest.raises(contract.WarehouseLocationError):
            contract.validate_warehouse_location(bad)
        with pytest.raises(impl.WarehouseLocationError) as caught:
            impl.warehouse_location(bad)
        assert contract.WAREHOUSE_LOCATION_ENV in str(caught.value), (
            "test_location_comes_only_from_the_configured_variable_and_must_hold_a_warehouse "
            "FAILED\n"
            f"ERRORS-ADAPT-1 violation for {label}: error does not name the variable\n"
            f"EXPECTED: message containing {contract.WAREHOUSE_LOCATION_ENV!r}\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: the error names the configured variable so an operator can fix it"
        )

    missing_dir = impl.WarehouseLocation(root=str(tmp_path / "absent"))
    with pytest.raises(impl.WarehouseLocationError) as caught_dir:
        impl.require_warehouse(missing_dir)
    # The adapter quotes the location with !r, which doubles each backslash of a Windows path.
    named = (missing_dir.root, missing_dir.root.replace("\\", "\\\\"))
    assert any(form in str(caught_dir.value) for form in named), (
        "test_location_comes_only_from_the_configured_variable_and_must_hold_a_warehouse FAILED\n"
        "ERRORS-ADAPT-2 violation: missing location not named\n"
        f"EXPECTED: message containing {missing_dir.root!r}\n"
        f"ACTUAL: {caught_dir.value!s}\n"
        "GUIDANCE: name the location that does not exist"
    )

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    no_db = impl.WarehouseLocation(root=str(empty_dir))
    with pytest.raises(impl.WarehouseLocationError) as caught_db:
        impl.require_warehouse(no_db)
    assert contract.WAREHOUSE_DB_FILE in str(caught_db.value), (
        "test_location_comes_only_from_the_configured_variable_and_must_hold_a_warehouse FAILED\n"
        "ERRORS-ADAPT-2 violation: missing warehouse file not named\n"
        f"EXPECTED: message containing {contract.WAREHOUSE_DB_FILE!r}\n"
        f"ACTUAL: {caught_db.value!s}\n"
        "GUIDANCE: name the missing item inside the location"
    )

    (empty_dir / contract.WAREHOUSE_DB_FILE).write_bytes(b"")
    assert impl.require_warehouse(no_db) == no_db, (
        "test_location_comes_only_from_the_configured_variable_and_must_hold_a_warehouse FAILED\n"
        "ERRORS-ADAPT-2 violation: a location holding the warehouse file came back changed\n"
        f"EXPECTED: {no_db!r}\n"
        "ACTUAL: a different value\n"
        "GUIDANCE: return the same location when the directory and warehouse file exist"
    )


def test_table_locations_are_relative_and_resolve_under_any_location():
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_table_location(), expected_table_path()
    - Enforces: POST-ADAPT-2, ERRORS-ADAPT-3, POST-ADAPT-3, FORBIDDEN-ADAPT-1
    - Category: positive, negative, invariant (relocation)
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition: valid table names; invalid names (empty, uppercase/hyphen, leading
      digit, slash); relative locations under two different warehouse locations; forbidden
      locations (empty, absolute, '..' prefix, embedded '..', backslash).
    """
    for name in ("glossary", "sba_foia_7a_fy2020_present_asof_260930", "_x1"):
        got = impl.table_location(name)
        want = contract.expected_table_location(name)
        assert got == want == f"parquet/{name}.parquet", (
            "test_table_locations_are_relative_and_resolve_under_any_location FAILED\n"
            f"POST-ADAPT-2 violation for {name!r}: wrong relative table location\n"
            f"EXPECTED: {want!r}\n"
            f"ACTUAL: {got!r}\n"
            "GUIDANCE: a table lives at parquet/<table_name>.parquet relative to the location"
        )

    for bad_name in ("", "Bad-Name", "9table", "a/b"):
        with pytest.raises(contract.WarehouseLocationError):
            contract.expected_table_location(bad_name)
        with pytest.raises(impl.WarehouseLocationError):
            impl.table_location(bad_name)

    built = impl.WarehouseLocation(root="/Users/someone/built/warehouse")
    mounted = impl.WarehouseLocation(root="/mnt/warehouse")
    rel = "parquet/glossary.parquet"
    for loc in (built, mounted):
        got_path = impl.table_path(loc, "glossary", rel)
        want_path = contract.expected_table_path(
            contract.WarehouseLocation(root=loc.root), "glossary", rel
        )
        assert got_path == want_path == f"{loc.root}/{rel}", (
            "test_table_locations_are_relative_and_resolve_under_any_location FAILED\n"
            "POST-ADAPT-3 violation: relative location not joined to the warehouse location\n"
            f"EXPECTED: {want_path!r}\n"
            f"ACTUAL: {got_path!r}\n"
            "GUIDANCE: the same catalog name resolves under whichever location is configured"
        )

    for bad_rel in (
        "",
        "/Users/someone/built/warehouse/parquet/glossary.parquet",
        "../glossary.parquet",
        "parquet/../../etc/passwd",
        "parquet\\glossary.parquet",
    ):
        with pytest.raises(contract.WarehouseLocationError):
            contract.expected_table_path(
                contract.WarehouseLocation(root=mounted.root), "glossary", bad_rel
            )
        with pytest.raises(impl.WarehouseLocationError) as caught:
            impl.table_path(mounted, "glossary", bad_rel)
        message = str(caught.value)
        for needle in ("glossary", mounted.root):
            assert needle in message, (
                "test_table_locations_are_relative_and_resolve_under_any_location FAILED\n"
                f"FORBIDDEN-ADAPT-1 violation for {bad_rel!r}: error does not name {needle!r}\n"
                f"EXPECTED: message naming 'glossary' and {mounted.root!r}\n"
                f"ACTUAL: {message!r}\n"
                "GUIDANCE: refuse non-relative table locations and say which table and location"
            )

    assert (
        impl.WAREHOUSE_LOCATION_ENV,
        impl.WAREHOUSE_DB_FILE,
        impl.PARQUET_DIR,
        impl.TABLE_NAME_PATTERN.pattern,
    ) == (
        contract.WAREHOUSE_LOCATION_ENV,
        contract.WAREHOUSE_DB_FILE,
        contract.PARQUET_DIR,
        contract.TABLE_NAME_PATTERN.pattern,
    ), (
        "test_table_locations_are_relative_and_resolve_under_any_location FAILED\n"
        "POST-ADAPT-1 / POST-ADAPT-2 violation: adapter constants differ from the contract\n"
        f"EXPECTED: {contract.WAREHOUSE_LOCATION_ENV!r}, {contract.WAREHOUSE_DB_FILE!r}, "
        f"{contract.PARQUET_DIR!r}, {contract.TABLE_NAME_PATTERN.pattern!r}\n"
        f"ACTUAL: {impl.WAREHOUSE_LOCATION_ENV!r}, {impl.WAREHOUSE_DB_FILE!r}, "
        f"{impl.PARQUET_DIR!r}, {impl.TABLE_NAME_PATTERN.pattern!r}\n"
        "GUIDANCE: the adapter's variable, file, directory and name rule equal the contract's"
    )
