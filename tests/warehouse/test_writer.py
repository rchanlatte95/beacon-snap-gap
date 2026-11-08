"""RED tests for SLICE-3 batch 6a: the warehouse writer.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_WRITER)
- Authority: AUTHORITATIVE for the warehouse, its data adapter and its writer (SLICE-3)
- Clauses covered: POST-WRITE-1, POST-WRITE-2, INV-WRITE-1, ERRORS-WRITE-1
- Requirements: REQ-48, REQ-51

The implementation is src/warehouse/writer.py. It does not import the contract (CL11-F);
these tests import both and read the written warehouse back with DuckDB.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites a clause present in CONTRACT_WRITER.
  C2 VALUABLE: exact rows, exact relative locations, the exact set of base tables, zero views,
     no stored build location, and a relocated read are asserted; writing an absolute catalog
     location, creating a view, or embedding the build path each fails a test.
  C3 NON-DUPLICATIVE: test 1 pins a successful write and relocation; test 2 pins the refusals
     and constant alignment.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.
"""

import shutil
from pathlib import Path

import duckdb
import pytest
from contracts import warehouse_contract as contract
from src.warehouse import adapter
from src.warehouse import writer as impl

# Risk tier: HIGH. A writer that records a build path ships a warehouse that opens only on the
# machine that built it (observations O2 to O4 in plans/warehouse-adapter.refactor.md).


def _base_tables(
    con: duckdb.DuckDBPyConnection, catalog_rows: list[tuple[str, str]]
) -> dict[str, duckdb.DuckDBPyRelation]:
    catalog = con.values(*[(name, rel, "ok") for name, rel in catalog_rows]).project(
        "col0 AS table_name, col1 AS parquet, col2 AS status"
    )
    return {
        "files": con.sql("SELECT 'cache:sba/7a.csv' AS source, 'DS-X5' AS ds"),
        "catalog": catalog,
        "sources": con.sql("SELECT 'DS-X5' AS ds, 'SBA 7(a) and 504 FOIA' AS title"),
        "columns": con.sql("SELECT 'loans' AS table_name, 0 AS ordinal, 'LoanID' AS column_name"),
        "documents": con.sql("SELECT 'DS-X5' AS ds, 1 AS page, 'text' AS text"),
        "glossary": con.sql("SELECT 'loans' AS source_table, 'LoanID' AS term, 'id' AS definition"),
        # batch 7: BASE_TABLES gained ingest_log (thin amendment, 7f1b95e)
        "ingest_log": con.sql("SELECT 'cache:sba/7a.csv' AS source_file, 'line 2' AS location"),
    }


def test_writer_stores_relative_locations_and_the_warehouse_opens_elsewhere(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract validate_written_warehouse(), validate_no_location_in_values()
    - Enforces: POST-WRITE-1, POST-WRITE-2, INV-WRITE-1
    - Category: positive, invariant (relocation)
    - Risk tier: HIGH
    - Pyramid level: Integration (writer plus DuckDB plus filesystem, through the adapter)
    - Equivalence partition: one data table written at location A, finalized, then the whole
      location copied to B and A removed.
    """
    built = tmp_path / "built_here"
    built.mkdir()
    loc_a = adapter.WarehouseLocation(root=str(built))
    con = duckdb.connect(":memory:")
    w = impl.WarehouseWriter(loc_a)

    loans = con.sql("SELECT * FROM (VALUES ('L1', 'FL'), ('L2', 'NY')) t(LoanID, BorrState)")
    rel = w.write_table("loans", loans)
    assert rel == contract.expected_table_location("loans"), (
        "test_writer_stores_relative_locations_and_the_warehouse_opens_elsewhere FAILED\n"
        "POST-WRITE-1 violation: write_table did not return the relative table location\n"
        f"EXPECTED: {contract.expected_table_location('loans')!r}\n"
        f"ACTUAL: {rel!r}\n"
        "GUIDANCE: return the location relative to the warehouse location"
    )
    parquet_file = adapter.table_path(loc_a, "loans", rel)
    rows = sorted(duckdb.read_parquet(parquet_file).fetchall())
    assert rows == [("L1", "FL"), ("L2", "NY")], (
        "test_writer_stores_relative_locations_and_the_warehouse_opens_elsewhere FAILED\n"
        "POST-WRITE-1 violation: the Parquet file does not hold the relation's rows\n"
        "EXPECTED: [('L1', 'FL'), ('L2', 'NY')]\n"
        f"ACTUAL: {rows!r}\n"
        "GUIDANCE: write the relation's rows to the file named by the table location"
    )

    w.finalize(_base_tables(con, [("loans", rel)]))

    db = duckdb.connect(str(built / contract.WAREHOUSE_DB_FILE), read_only=True)
    base = tuple(
        r[0] for r in db.execute("SELECT table_name FROM duckdb_tables() ORDER BY 1").fetchall()
    )
    views = tuple(
        r[0]
        for r in db.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()
    )
    catalog = tuple(db.execute("SELECT table_name, parquet FROM catalog").fetchall())
    contract.validate_written_warehouse(
        contract.WrittenWarehouse(base_tables=base, views=views, catalog=catalog),
        data_tables=["loans"],
    )
    text_values: list[str] = []
    for table in contract.BASE_TABLES:
        for row in db.table(table).fetchall():
            text_values += [value for value in row if isinstance(value, str)]
    contract.validate_no_location_in_values(
        text_values, contract.WarehouseLocation(root=loc_a.root)
    )
    db.close()

    moved = tmp_path / "mounted_elsewhere"
    shutil.copytree(built, moved)
    shutil.rmtree(built)
    loc_b = adapter.require_warehouse(adapter.WarehouseLocation(root=str(moved)))
    db_b = duckdb.connect(str(moved / contract.WAREHOUSE_DB_FILE), read_only=True)
    (name, rel_b) = db_b.execute("SELECT table_name, parquet FROM catalog").fetchone() or ("", "")
    count = (
        duckdb.read_parquet(adapter.table_path(loc_b, name, rel_b)).aggregate("count(*)").fetchall()
    )
    assert count == [(2,)], (
        "test_writer_stores_relative_locations_and_the_warehouse_opens_elsewhere FAILED\n"
        "INV-WRITE-1 violation: the copied warehouse does not read its table at the new location\n"
        "EXPECTED: [(2,)]\n"
        f"ACTUAL: {count!r}\n"
        "GUIDANCE: store nothing that ties the warehouse to the location it was written at"
    )


def test_writer_refuses_duplicates_and_incomplete_base_tables(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract BASE_TABLES, CATALOG_REQUIRED_COLUMNS
    - Enforces: ERRORS-WRITE-1, POST-WRITE-2
    - Category: negative, error, invariant
    - Risk tier: HIGH
    - Pyramid level: Integration (writer plus DuckDB)
    - Equivalence partition: same table twice; one base table missing; catalog missing a
      required column.
    """
    con = duckdb.connect(":memory:")
    one = con.sql("SELECT 1 AS x")

    w = impl.WarehouseWriter(adapter.WarehouseLocation(root=str(tmp_path / "dup")))
    (tmp_path / "dup").mkdir()
    w.write_table("t", one)
    with pytest.raises(impl.WarehouseWriteError):
        w.write_table("t", one)

    (tmp_path / "missing").mkdir()
    w2 = impl.WarehouseWriter(adapter.WarehouseLocation(root=str(tmp_path / "missing")))
    rel = w2.write_table("t", one)
    tables = _base_tables(con, [("t", rel)])
    del tables["glossary"]
    with pytest.raises(impl.WarehouseWriteError) as caught:
        w2.finalize(tables)
    assert "glossary" in str(caught.value), (
        "test_writer_refuses_duplicates_and_incomplete_base_tables FAILED\n"
        "ERRORS-WRITE-1 violation: missing base table not named\n"
        "EXPECTED: message naming 'glossary'\n"
        f"ACTUAL: {caught.value!s}\n"
        "GUIDANCE: name the base table that finalize did not receive"
    )

    (tmp_path / "nostatus").mkdir()
    w3 = impl.WarehouseWriter(adapter.WarehouseLocation(root=str(tmp_path / "nostatus")))
    rel3 = w3.write_table("t", one)
    tables3 = _base_tables(con, [("t", rel3)])
    tables3["catalog"] = con.sql(f"SELECT 't' AS table_name, '{rel3}' AS parquet")
    with pytest.raises(impl.WarehouseWriteError) as caught3:
        w3.finalize(tables3)
    assert "status" in str(caught3.value), (
        "test_writer_refuses_duplicates_and_incomplete_base_tables FAILED\n"
        "ERRORS-WRITE-1 violation: missing catalog column not named\n"
        "EXPECTED: message naming 'status'\n"
        f"ACTUAL: {caught3.value!s}\n"
        "GUIDANCE: name the required catalog column that is missing"
    )

    assert (tuple(impl.BASE_TABLES), tuple(impl.CATALOG_REQUIRED_COLUMNS)) == (
        contract.BASE_TABLES,
        contract.CATALOG_REQUIRED_COLUMNS,
    ), (
        "test_writer_refuses_duplicates_and_incomplete_base_tables FAILED\n"
        "POST-WRITE-2 violation: writer constants differ from the contract\n"
        f"EXPECTED: {contract.BASE_TABLES!r}, {contract.CATALOG_REQUIRED_COLUMNS!r}\n"
        f"ACTUAL: {impl.BASE_TABLES!r}, {impl.CATALOG_REQUIRED_COLUMNS!r}\n"
        "GUIDANCE: the base tables and required catalog columns equal the contract's"
    )
