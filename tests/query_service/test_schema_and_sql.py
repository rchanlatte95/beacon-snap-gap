"""RED tests for SLICE-4 batch 1 (redone): the DuckDB engine over the warehouse through the adapter.

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (CONTRACT_QUERY_CORE)
- Clauses covered: SEQ-6, POST-SCHEMA-1, POST-SQL-1, SEQ-7, FORBIDDEN-SQL-1, ERRORS-SQL-1,
  ERRORS-SQL-2
- Requirements: REQ-32, REQ-33, REQ-34, REQ-46, REQ-47, REQ-49, REQ-50, REQ-52
- Base tables: contracts/warehouse_contract.py BASE_TABLE_COLUMNS (POST-BASE-1)

The implementation is src/query_service/engine.py. It does not import the contract (CL11-F).
The warehouse is a real one, written with src/warehouse/writer.py at a tmp location.

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: expected values come from the contract oracles (expected_grain_and_keys,
  expected_table_citation, extract_referenced_tables) and constants.
- C2 VALUABLE: an engine that writes, reads outside the location, accepts a second statement,
  misses truncation, drops citations or hangs fails.
- C3 NON-DUPLICATIVE: test 1 is the read path; test 2 is the refusal path.
- C4 NOT FUTURE-EDIT: only contracted names.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

import duckdb
import pytest
from contracts import query_service_contract as contract
from src.warehouse import adapter
from src.warehouse.writer import WarehouseWriter

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="ARRANGE: the warehouse location is a POSIX path (Cloud Run)"
)

from src.query_service import engine as impl  # noqa: E402

SBA_ROWS = [(f"L{i}", "FL" if i % 3 else "NY", str(1000 * i)) for i in range(1, 251)]
POP_ROWS = [("1400000US12095016510", "4200"), ("1400000US12095016600", "3100")]
SOURCES = {
    "sba_loans": (
        "DS-X5",
        "data/external/sba-loans/foia.csv",
        "https://data.sba.gov/dataset/7a-504-foia",
        "U.S. Small Business Administration",
        "2026-09-30",
        'state field "BorrState" in FL, NY, UT',
    ),
    "tract_pop": (
        "DS-X24",
        "data/external/census-2020-blocks/central-fl-blocks-2020.csv",
        contract.NOT_RECORDED,
        "U.S. Census Bureau",
        "2020",
        "none",
    ),
}


def _rel(con: duckdb.DuckDBPyConnection, cols: Sequence[str], rows: Sequence[tuple[object, ...]]):
    placeholders = ", ".join("?" for _ in cols)
    con.execute(
        f"CREATE TEMP TABLE t_{len(cols)}_{id(rows)} ({', '.join(f'{c} VARCHAR' for c in cols)})"
    )
    name = f"t_{len(cols)}_{id(rows)}"
    if rows:
        # name and placeholders come from this test's fixed columns, never from input
        insert = f"INSERT INTO {name} VALUES ({placeholders})"  # noqa: S608
        con.executemany(insert, [tuple(map(_text, r)) for r in rows])
    return con.table(name)


def _text(v: object) -> object:
    return None if v is None else str(v)


def _build(root: Path) -> Path:
    loc = adapter.warehouse_location({contract.ENGINE_LOCATION_ENV: str(root)})
    con = duckdb.connect()
    writer = WarehouseWriter(loc)
    data = {
        "sba_loans": (("LoanID", "BorrState", "GrossApproval"), SBA_ROWS),
        "tract_pop": (("GEO_ID", "Pop"), POP_ROWS),
    }
    parquet = {
        name: writer.write_table(name, _rel(con, cols, rows)) for name, (cols, rows) in data.items()
    }
    base = contract.ENGINE_BASE_COLUMNS
    catalog = [(n, parquet[n], "ok", SOURCES[n][1], SOURCES[n][0]) for n in data]
    sources = [
        (
            n,
            s[0],
            s[1],
            s[2],
            "2026-11-01",
            "0" * 64,
            s[3],
            "CC BY 4.0",
            s[4],
            s[5],
            len(data[n][1]),
            len(data[n][1]),
        )
        for n, s in SOURCES.items()
    ]
    columns = [
        (n, c, i, "VARCHAR", "") for n, (cols, _) in data.items() for i, c in enumerate(cols, 1)
    ]
    glossary = [
        ("sba_loans", "DS-X5", "BorrState", "Borrower state"),
        ("sba_loans", "DS-X5", "GrossApproval", "Approved amount"),
    ]
    rows_by_base = {
        "catalog": catalog,
        "sources": sources,
        "columns": columns,
        "glossary": glossary,
        "files": [],
        "documents": [],
        "ingest_log": [],
    }
    writer.finalize({name: _rel(con, base[name], rows_by_base[name]) for name in base})
    return root


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def warehouse(tmp_path: Path) -> Path:
    return _build(tmp_path / "warehouse")


def test_engine_opens_read_only_describes_tables_and_answers_select_with_citations(
    warehouse: Path,
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: SEQ-6, POST-SCHEMA-1, POST-SQL-1, SEQ-7
      (REQ-46, REQ-47, REQ-49, REQ-33, REQ-34, REQ-32)
    - Enforces: no tool call before open(); describe_schema fields from the base tables; one SELECT
      with truncation at row_limit; citations of each referenced table in order
    - Category: integration / positive / boundary (row_limit edge, NOT_RECORDED origin)
    - Risk tier: High; every AI answer is built from these results
    """
    before = _hashes(warehouse)
    eng = impl.WarehouseQueryEngine({contract.ENGINE_LOCATION_ENV: str(warehouse)})
    with pytest.raises(impl.UnconnectedWarehouseError):
        eng.describe_schema()
    with pytest.raises(impl.UnconnectedWarehouseError):
        eng.execute_sql("SELECT 1")
    eng.open()

    schemas = eng.describe_schema()
    assert [s.table_name for s in schemas] == ["sba_loans", "tract_pop"], (
        "POST-SCHEMA-1 violation: catalog order"
    )
    loans = eng.describe_schema(table_names=("sba_loans",))[0]
    grain, keys = contract.expected_grain_and_keys(("LoanID", "BorrState", "GrossApproval"))
    got = (
        loans.dataset_id,
        loans.columns,
        loans.grain,
        loans.join_keys,
        loans.as_of,
        loans.applied_filter,
        loans.glossary_terms,
    )
    want = (
        "DS-X5",
        ("LoanID", "BorrState", "GrossApproval"),
        grain,
        keys,
        "2026-09-30",
        'state field "BorrState" in FL, NY, UT',
        (("BorrState", "Borrower state"), ("GrossApproval", "Approved amount")),
    )
    assert got == want, f"POST-SCHEMA-1 violation: {got}\nEXPECTED: {want}"
    assert (loans.grain, loans.join_keys) == ("state", ("BorrState",))
    with pytest.raises(impl.RejectedSqlError):
        eng.describe_schema(table_names=("nope",))

    sql = (
        "SELECT l.LoanID, p.Pop FROM sba_loans l JOIN tract_pop p "
        "ON l.BorrState = 'FL' ORDER BY l.LoanID"
    )
    res = eng.execute_sql(sql, row_limit=200)
    total = sum(1 for r in SBA_ROWS if r[1] == "FL") * len(POP_ROWS)
    assert res.columns == ("LoanID", "Pop"), f"POST-SQL-1 violation: columns {res.columns}"
    assert (res.row_count, len(res.rows), res.truncated) == (200, 200, total > 200), (
        f"POST-SQL-1 violation: row_count {res.row_count}, truncated {res.truncated}, total {total}"
    )
    exact = eng.execute_sql("SELECT count(*) AS n FROM sba_loans", row_limit=1)
    assert (exact.rows, exact.truncated) == (({"n": 250},), False), (
        f"POST-SQL-1 violation: {exact.rows} {exact.truncated}"
    )
    names = frozenset({"sba_loans", "tract_pop"})
    assert res.referenced_tables == contract.extract_referenced_tables(sql, names)
    want_cites = tuple(
        contract.expected_table_citation(
            {
                "table_name": n,
                "dataset_id": SOURCES[n][0],
                "origin_url": SOURCES[n][2],
                "publisher": SOURCES[n][3],
                "as_of": SOURCES[n][4],
                "applied_filter": SOURCES[n][5],
            }
        )
        for n in res.referenced_tables
    )
    got_cites = tuple(
        (c.table_name, c.dataset_id, c.origin_url, c.publisher, c.as_of, c.applied_filter)
        for c in res.citations
    )
    assert got_cites == tuple(
        (c.table_name, c.dataset_id, c.origin_url, c.publisher, c.as_of, c.applied_filter)
        for c in want_cites
    ), f"SEQ-7 violation: citations {got_cites}"
    assert _hashes(warehouse) == before, "SEQ-6 violation: the warehouse files changed"


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "SELECT 1; SELECT 2",
        "COPY (SELECT 1) TO '/tmp/x.csv'",
        "CREATE TABLE x AS SELECT 1",
        "INSERT INTO sba_loans VALUES ('L0','FL','1')",
        "SET threads = 1",
        "PRAGMA version",
        "ATTACH ':memory:' AS other",
        "SELECT * FROM read_csv('/etc/hosts')",
        "SELECT nosuchcolumn FROM sba_loans",
    ],
)
def test_engine_refuses_everything_but_one_select_inside_the_location(
    warehouse: Path, sql: str
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: FORBIDDEN-SQL-1, ERRORS-SQL-1, ERRORS-SQL-2 (REQ-34, REQ-46, REQ-50)
    - Enforces: each refused statement raises RejectedSqlError naming its clause; files unchanged;
      a long query is interrupted with QueryTimeoutError and the engine keeps working; limits
      are checked
    - Category: negative / error / boundary
    - Risk tier: High; model-written SQL is untrusted input
    """
    before = _hashes(warehouse)
    eng = impl.WarehouseQueryEngine({contract.ENGINE_LOCATION_ENV: str(warehouse)})
    eng.open()
    with pytest.raises(impl.RejectedSqlError) as caught:
        eng.execute_sql(sql)
    assert "ERRORS-SQL-1" in str(caught.value) or "FORBIDDEN-SQL-1" in str(caught.value), (
        f"ERRORS-SQL-1 violation: {sql!r} refused without naming a clause: {caught.value}"
    )
    for bad in (
        {"row_limit": 0},
        {"row_limit": contract.MAX_ROW_LIMIT + 1},
        {"timeout_seconds": 0},
        {"timeout_seconds": contract.MAX_TIMEOUT_SECONDS + 1},
    ):
        with pytest.raises(impl.RejectedSqlError):
            eng.execute_sql("SELECT 1", **bad)  # type: ignore[arg-type]
    with pytest.raises(impl.QueryTimeoutError) as slow:
        eng.execute_sql("SELECT sum(i) FROM range(100000000000) t(i)", timeout_seconds=0.3)
    assert "ERRORS-SQL-2" in str(slow.value)
    assert eng.execute_sql("SELECT 41 + 1 AS n").rows == ({"n": 42},), (
        "ERRORS-SQL-2 violation: engine unusable"
    )
    assert _hashes(warehouse) == before, "FORBIDDEN-SQL-1 violation: the warehouse files changed"
