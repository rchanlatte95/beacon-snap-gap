"""RED tests: no metadata, file, environment or injected queries in execute_sql (FORBIDDEN-SQL-2).

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (METADATA_SQL_PATTERN, FORBIDDEN-SQL-2)
- Requirements: REQ-34, REQ-40, REQ-50

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: FORBIDDEN-SQL-2 exists; the refused statements match METADATA_SQL_PATTERN.
- C2 VALUABLE: an engine that lists tables, reads raw files, reads the environment or runs a
  nested query string fails; one that refuses a catalog query fails the positive case.
- C3 NON-DUPLICATIVE: test_schema_and_sql.py covers FORBIDDEN-SQL-1 (statement kinds, files outside
  the location); these cover what a single SELECT may read.
- C4 NOT FUTURE-EDIT: execute_sql runs these today.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from contracts import query_service_contract as contract
from tests.query_service import fixture_warehouse as fx

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="ARRANGE: the warehouse location is a POSIX path (Cloud Run)"
)

from src.query_service import engine as impl  # noqa: E402

REFUSED = (
    "SELECT table_name FROM information_schema.tables",
    "SELECT * FROM duckdb_tables()",
    "SELECT * FROM catalog",
    "SELECT c.column_name FROM sba_loans s JOIN columns c ON true",
    "SELECT * FROM read_parquet('parquet/sba_loans.parquet')",
    "SELECT getenv('HOME')",
    "SELECT current_setting('allowed_directories')",
    "SELECT * FROM query('SELECT * FROM catalog')",
)


@pytest.mark.parametrize("sql", REFUSED)
def test_execute_sql_refuses_metadata_files_and_injection(tmp_path: Path, sql: str) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: FORBIDDEN-SQL-2 (REQ-34, REQ-40, REQ-50)
    - Enforces: a statement METADATA_SQL_PATTERN matches raises RejectedSqlError naming
      FORBIDDEN-SQL-2, and no rows are returned
    - Category: negative / security (one representative per refused kind)
    - Risk tier: High; schema, raw files and the environment must never reach a reader
    """
    assert contract.METADATA_SQL_PATTERN.search(sql), f"ARRANGE: {sql!r} must match the pattern"
    eng = impl.WarehouseQueryEngine(
        {contract.ENGINE_LOCATION_ENV: str(fx.build_warehouse(tmp_path / "w"))}
    )
    eng.open()
    with pytest.raises(impl.RejectedSqlError) as refused:
        eng.execute_sql(sql)
    assert "FORBIDDEN-SQL-2" in str(refused.value), (
        f"FORBIDDEN-SQL-2 violation: {sql!r} was refused for another reason: {refused.value}"
    )


def test_execute_sql_still_answers_a_catalog_query(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: FORBIDDEN-SQL-2, POST-SQL-1 (REQ-34)
    - Enforces: a SELECT over a catalog table, with columns named like base tables, still runs
    - Category: positive / boundary
    - Risk tier: High; the guard must not block the answering query
    """
    eng = impl.WarehouseQueryEngine(
        {contract.ENGINE_LOCATION_ENV: str(fx.build_warehouse(tmp_path / "w"))}
    )
    eng.open()
    sql = "SELECT count(*) AS files FROM sba_loans"
    assert not contract.METADATA_SQL_PATTERN.search(sql), "ARRANGE: the query must not match"
    result = eng.execute_sql(sql)
    assert result.rows == ({"files": len(fx.LOANS)},), f"POST-SQL-1 violation: {result.rows}"
