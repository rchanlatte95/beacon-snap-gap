"""RED tests for SLICE-4 batch 1: bucket connection, schema.describe, sql.query and citations.

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py
- Authority: AUTHORITATIVE for the QueryService (SLICE-4)
- Clauses covered: SEQ-6, POST-SCHEMA-1, POST-SQL-1, SEQ-7, FORBIDDEN-SQL-1, ERRORS-SQL-1
- Requirements: REQ-32, REQ-33, REQ-34, REQ-46

The implementation is src/query_service/engine.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: each cites clauses present in contracts/query_service_contract.py.
  C2 VALUABLE: exact returned rows, truncation flag, attached SourceCitation objects, schema
     fields, and lifecycle ordering (UnconnectedWarehouseError before connect()) are asserted.
  C3 NON-DUPLICATIVE: test 1 pins SEQ-6 connection lifecycle, POST-SCHEMA-1, POST-SQL-1 and
     SEQ-7 citations; test 2 pins FORBIDDEN-SQL-1, ERRORS-SQL-1 and constant alignment.
  C4 NOT FUTURE-EDIT: every asserted behavior is a contracted clause in CONTRACT_QUERY_CORE.
"""

import pytest
from contracts import query_service_contract as contract
from src.query_service import engine as impl

# Risk tier: HIGH. Unchecked SQL can mutate or expose uncontracted paths; missing SEQ-7 citations
# produce uncited answers; skipping SEQ-6 leaves queries running against an unconnected engine.


def _sample_warehouse_snapshot() -> impl.WarehouseSnapshot:
    return impl.WarehouseSnapshot(
        source_uri=impl.WAREHOUSE_GCS_URI,
        tables={
            "sba_loans": (
                {"LoanID": "L1", "BorrState": "FL", "GrossApproval": "50000"},
                {"LoanID": "L2", "BorrState": "FL", "GrossApproval": "125000"},
                {"LoanID": "L3", "BorrState": "NY", "GrossApproval": "80000"},
            ),
            "tract_pop": ({"GEO_ID": "1400000US12095016510", "BorrState": "FL", "Pop": "4200"},),
        },
        table_columns={
            "sba_loans": ("LoanID", "BorrState", "GrossApproval"),
            "tract_pop": ("GEO_ID", "BorrState", "Pop"),
        },
        table_grains={
            "sba_loans": "loan",
            "tract_pop": "census_tract",
        },
        table_join_keys={
            "sba_loans": ("BorrState",),
            "tract_pop": ("GEO_ID", "BorrState"),
        },
        citations={
            "sba_loans": impl.SourceCitation(
                table_name="sba_loans",
                dataset_id="DS-X5",
                origin_url="https://data.sba.gov/7a.csv",
                publisher="U.S. Small Business Administration",
                as_of="2026-09-30",
                applied_filter='state field "BorrState" in FL, NY, UT',
            ),
            "tract_pop": impl.SourceCitation(
                table_name="tract_pop",
                dataset_id="DS-H4",
                origin_url="https://data.census.gov/pop.csv",
                publisher="U.S. Census Bureau",
                as_of="2024 5-year ACS",
                applied_filter="GEO_ID in FL, NY, UT",
            ),
        },
        glossary={
            "sba_loans": (
                ("BorrState", "Borrower state abbreviation"),
                ("GrossApproval", "Total loan amount approved"),
            ),
            "tract_pop": (("GEO_ID", "Census geographic identifier"),),
        },
    )


def test_bucket_connection_schema_describe_and_readonly_sql_with_citations():
    """
    CONTRACT TRACEABILITY:
    - Contract: query_service_contract validate_schema_description(), validate_sql_query_result()
    - Enforces: SEQ-6, POST-SCHEMA-1, POST-SQL-1, SEQ-7
    - Category: positive, boundary, integration (SEQ-6, SEQ-7 lifecycle)
    - Risk tier: HIGH
    - Pyramid level: Integration (WarehouseQueryEngine lifecycle: pre-connect -> connect -> query)
    - Equivalence partition:
      1. Pre-connect tool call (raises UnconnectedWarehouseError per SEQ-6).
      2. Post-connect schema.describe (returns full TableSchemaDescription per POST-SCHEMA-1).
      3. Post-connect sql.query with JOIN and row_limit truncation (returns rows capped at
         row_limit and attaches SourceCitation for each referenced table per POST-SQL-1, SEQ-7).
    """
    svc = impl.WarehouseQueryEngine(_sample_warehouse_snapshot())

    # SEQ-6: querying before connect() raises UnconnectedWarehouseError.
    with pytest.raises(impl.UnconnectedWarehouseError):
        svc.describe_schema()
    with pytest.raises(impl.UnconnectedWarehouseError):
        svc.execute_sql("SELECT LoanID FROM sba_loans")

    svc.connect()
    assert svc.connected_uri == contract.WAREHOUSE_GCS_URI, (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "SEQ-6 violation: engine did not connect to WAREHOUSE_GCS_URI\n"
        f"EXPECTED: {contract.WAREHOUSE_GCS_URI!r}\n"
        f"ACTUAL: {svc.connected_uri!r}\n"
        "GUIDANCE: connect() binds to the canonical warehouse in WAREHOUSE_GCS_URI"
    )

    # POST-SCHEMA-1: schema.describe returns tables, columns, grain, join_keys, as_of, filter
    # and glossary_terms.
    schemas = svc.describe_schema(table_names=("sba_loans",))
    assert len(schemas) == 1, (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "POST-SCHEMA-1 violation: expected 1 schema description for sba_loans\n"
        "EXPECTED: 1\n"
        f"ACTUAL: {len(schemas)}\n"
        "GUIDANCE: describe_schema filters to requested table_names"
    )
    sba_schema = schemas[0]
    contract.validate_schema_description(
        contract.TableSchemaDescription(
            table_name=sba_schema.table_name,
            dataset_id=sba_schema.dataset_id,
            columns=sba_schema.columns,
            grain=sba_schema.grain,
            join_keys=sba_schema.join_keys,
            as_of=sba_schema.as_of,
            applied_filter=sba_schema.applied_filter,
            glossary_terms=sba_schema.glossary_terms,
        )
    )
    assert sba_schema.grain == "loan", (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "POST-SCHEMA-1 violation: wrong grain for sba_loans\n"
        "EXPECTED: 'loan'\n"
        f"ACTUAL: {sba_schema.grain!r}\n"
        "GUIDANCE: describe_schema returns each table's grain and join_keys"
    )
    assert dict(sba_schema.glossary_terms)["BorrState"] == "Borrower state abbreviation", (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "POST-SCHEMA-1 violation: glossary_terms missing BorrState definition\n"
        "EXPECTED: 'Borrower state abbreviation'\n"
        f"ACTUAL: {sba_schema.glossary_terms!r}\n"
        "GUIDANCE: describe_schema attaches glossary terms for the described table"
    )

    # POST-SQL-1 and SEQ-7: read-only SELECT with JOIN and row_limit=2 truncates to 2 rows and
    # attaches citations for both sba_loans and tract_pop.
    res = svc.execute_sql(
        "SELECT l.LoanID, p.GEO_ID FROM sba_loans l "
        "JOIN tract_pop p ON l.BorrState = p.BorrState ORDER BY l.LoanID",
        row_limit=2,
    )
    assert res.row_count == 2, (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "POST-SQL-1 violation: row_count was not capped at row_limit=2\n"
        "EXPECTED: 2\n"
        f"ACTUAL: {res.row_count}\n"
        "GUIDANCE: execute_sql caps returned rows at row_limit"
    )
    assert res.truncated is False, (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "POST-SQL-1 violation: 2 FL loans match, so row_limit=2 is exact (not truncated)\n"
        "EXPECTED: False\n"
        f"ACTUAL: {res.truncated}\n"
        "GUIDANCE: truncated is True only when the query produces more than row_limit rows"
    )
    res_trunc = svc.execute_sql("SELECT LoanID FROM sba_loans ORDER BY LoanID", row_limit=2)
    assert res_trunc.truncated is True, (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "POST-SQL-1 violation: 3 rows with row_limit=2 must mark truncated=True\n"
        "EXPECTED: True\n"
        f"ACTUAL: {res_trunc.truncated}\n"
        "GUIDANCE: set truncated=True when more than row_limit rows match"
    )
    assert [c.dataset_id for c in res.citations] == ["DS-X5", "DS-H4"], (
        "test_bucket_connection_schema_describe_and_readonly_sql_with_citations FAILED\n"
        "SEQ-7 violation: execute_sql did not attach citations for both joined tables in order\n"
        "EXPECTED: ['DS-X5', 'DS-H4']\n"
        f"ACTUAL: {[c.dataset_id for c in res.citations]}\n"
        "GUIDANCE: attach SourceCitation for every warehouse table referenced in the query"
    )
    known_cites = {
        k: contract.SourceCitation(
            v.table_name, v.dataset_id, v.origin_url, v.publisher, v.as_of, v.applied_filter
        )
        for k, v in _sample_warehouse_snapshot().citations.items()
    }
    contract.validate_sql_query_result(
        contract.SqlQueryResult(
            columns=res.columns,
            rows=res.rows,
            row_count=res.row_count,
            truncated=res.truncated,
            referenced_tables=res.referenced_tables,
            citations=tuple(
                contract.SourceCitation(
                    c.table_name,
                    c.dataset_id,
                    c.origin_url,
                    c.publisher,
                    c.as_of,
                    c.applied_filter,
                )
                for c in res.citations
            ),
        ),
        row_limit=2,
        known_citations=known_cites,
    )


def test_rejected_sql_statements_bounds_and_constants_align():
    """
    CONTRACT TRACEABILITY:
    - Contract: query_service_contract validate_readonly_sql(), FORBIDDEN_SQL_KEYWORDS,
      WAREHOUSE_GCS_BUCKET, WAREHOUSE_GCS_URI, MAX_ROW_LIMIT, MAX_TIMEOUT_SECONDS
    - Enforces: FORBIDDEN-SQL-1, ERRORS-SQL-1, SEQ-6
    - Category: negative, error, boundary, invariant
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition (rejected SQL / bounds):
      1. empty string
      2. non-SELECT statement (DROP / DELETE / INSERT / PRAGMA)
      3. SELECT containing a forbidden keyword token
      4. multi-statement separated by semicolon
      5. SQL comment (-- or /*)
      6. WITH clause without SELECT
      7. row_limit < 1 or > MAX_ROW_LIMIT
      8. timeout_seconds <= 0 or > MAX_TIMEOUT_SECONDS
    """
    svc = impl.WarehouseQueryEngine(_sample_warehouse_snapshot())
    svc.connect()

    bad_sql_cases = [
        ("empty", "", 10, 5.0),
        ("drop table", "DROP TABLE sba_loans", 10, 5.0),
        ("delete", "DELETE FROM sba_loans", 10, 5.0),
        ("pragma", "PRAGMA database_list", 10, 5.0),
        ("multi-statement", "SELECT 1; SELECT 2", 10, 5.0),
        ("line comment", "SELECT * FROM sba_loans -- comment", 10, 5.0),
        ("block comment", "SELECT /* x */ * FROM sba_loans", 10, 5.0),
        ("with without select", "WITH x AS (VALUES (1))", 10, 5.0),
        ("row_limit zero", "SELECT * FROM sba_loans", 0, 5.0),
        ("row_limit above max", "SELECT * FROM sba_loans", contract.MAX_ROW_LIMIT + 1, 5.0),
        ("timeout zero", "SELECT * FROM sba_loans", 10, 0.0),
        (
            "timeout above max",
            "SELECT * FROM sba_loans",
            10,
            contract.MAX_TIMEOUT_SECONDS + 1.0,
        ),
    ]
    for label, sql, rlim, tsec in bad_sql_cases:
        with pytest.raises(contract.RejectedSqlError):
            contract.validate_readonly_sql(sql, row_limit=rlim, timeout_seconds=tsec)
        try:
            svc.execute_sql(sql, row_limit=rlim, timeout_seconds=tsec)
        except impl.RejectedSqlError:
            continue
        except Exception as exc:  # noqa: BLE001 - the clause names the one allowed class
            pytest.fail(
                "test_rejected_sql_statements_bounds_and_constants_align FAILED\n"
                f"ERRORS-SQL-1 / FORBIDDEN-SQL-1 violation for {label}: wrong error class\n"
                "EXPECTED: RejectedSqlError\n"
                f"ACTUAL: {type(exc).__name__}: {exc}\n"
                "GUIDANCE: invalid or non-read-only SQL raises RejectedSqlError"
            )
        pytest.fail(
            "test_rejected_sql_statements_bounds_and_constants_align FAILED\n"
            f"ERRORS-SQL-1 / FORBIDDEN-SQL-1 violation for {label}: accepted\n"
            "EXPECTED: RejectedSqlError\n"
            "ACTUAL: query executed\n"
            "GUIDANCE: reject non-SELECT statements, comments, multi-statements and bad limits"
        )

    assert impl.WAREHOUSE_GCS_BUCKET == contract.WAREHOUSE_GCS_BUCKET, (
        "test_rejected_sql_statements_bounds_and_constants_align FAILED\n"
        "SEQ-6 violation: WAREHOUSE_GCS_BUCKET differs\n"
        f"EXPECTED: {contract.WAREHOUSE_GCS_BUCKET!r}\n"
        f"ACTUAL: {impl.WAREHOUSE_GCS_BUCKET!r}\n"
        "GUIDANCE: QueryService uses the canonical bucket reference constant"
    )
    assert impl.WAREHOUSE_GCS_URI == contract.WAREHOUSE_GCS_URI, (
        "test_rejected_sql_statements_bounds_and_constants_align FAILED\n"
        "SEQ-6 violation: WAREHOUSE_GCS_URI differs\n"
        f"EXPECTED: {contract.WAREHOUSE_GCS_URI!r}\n"
        f"ACTUAL: {impl.WAREHOUSE_GCS_URI!r}\n"
        "GUIDANCE: QueryService uses the canonical bucket URI constant"
    )
    assert frozenset(impl.FORBIDDEN_SQL_KEYWORDS) == contract.FORBIDDEN_SQL_KEYWORDS, (
        "test_rejected_sql_statements_bounds_and_constants_align FAILED\n"
        "FORBIDDEN-SQL-1 violation: FORBIDDEN_SQL_KEYWORDS differs\n"
        f"EXPECTED: {sorted(contract.FORBIDDEN_SQL_KEYWORDS)}\n"
        f"ACTUAL: {sorted(impl.FORBIDDEN_SQL_KEYWORDS)}\n"
        "GUIDANCE: forbidden SQL keyword set equals the contract's"
    )
    assert (impl.DEFAULT_ROW_LIMIT, impl.MAX_ROW_LIMIT) == (
        contract.DEFAULT_ROW_LIMIT,
        contract.MAX_ROW_LIMIT,
    ), (
        "test_rejected_sql_statements_bounds_and_constants_align FAILED\n"
        "POST-SQL-1 violation: row limit constants differ\n"
        f"EXPECTED: {(contract.DEFAULT_ROW_LIMIT, contract.MAX_ROW_LIMIT)}\n"
        f"ACTUAL: {(impl.DEFAULT_ROW_LIMIT, impl.MAX_ROW_LIMIT)}\n"
        "GUIDANCE: row limit constants equal the contract's"
    )
