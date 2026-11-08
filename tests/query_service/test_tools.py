"""RED tests for SLICE-4 batch 3: the sites_near and stats_correlate tools (REQ-35).

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (CONTRACT_QUERY_TOOLS)
- Clauses covered: POST-TOOL-1, POST-TOOL-2, ERRORS-TOOL-1
- Requirements: REQ-35, REQ-32

The implementation is src/query_service/tools.py: WarehouseTools(engine) with sites_near,
stats_correlate and known_geoids, and ToolArgumentError. It does not import the contract (CL11-F).

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: rows come from expected_sites_near and expected_correlation over the fixture's values.
- C2 VALUABLE: a tool that measures from a tract centre instead of its populated blocks, drops a
  site at the inclusive edge, keeps non-numeric rows, or crashes on bad arguments fails.
- C3 NON-DUPLICATIVE: test_schema_and_sql.py covers the engine; these cover the two tools.
- C4 NOT FUTURE-EDIT: only contracted names.
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

from src.query_service import engine as engine_impl  # noqa: E402
from src.query_service import tools as impl  # noqa: E402


@pytest.fixture
def tools(tmp_path: Path) -> impl.WarehouseTools:
    root = fx.build_warehouse(tmp_path / "warehouse")
    eng = engine_impl.WarehouseQueryEngine({contract.ENGINE_LOCATION_ENV: str(root)})
    eng.open()
    return impl.WarehouseTools(eng)


def _view(result: object) -> tuple[object, ...]:
    r = result
    return (
        r.columns,  # type: ignore[attr-defined]
        tuple(tuple(row[c] for c in r.columns) for row in r.rows),  # type: ignore[attr-defined]
        r.truncated,  # type: ignore[attr-defined]
    )


def test_sites_near_a_point_and_a_tract_match_the_block_based_oracle(
    tools: impl.WarehouseTools,
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-TOOL-1 (REQ-35, REQ-32; Z-2 2-A)
    - Enforces: point and tract origins; populated blocks only; inclusive distance; order by
      distance then storeid; sites and blocks tables referenced and cited
    - Category: positive / boundary (exact edge distance, empty tract)
    - Risk tier: High; "nearby" must mean the same as on the map
    """
    sites = fx.fixture_sites()
    a = fx.populated_blocks(fx.TRACT_A)
    edge = contract.expected_miles(a[0][0], a[0][1], sites[1].lat, sites[1].lon)
    cases = [
        ({"geoid": fx.TRACT_A, "miles": edge}, a, edge),
        ({"geoid": fx.TRACT_A, "miles": 20.0}, a, 20.0),
        ({"lat": 28.54, "lon": -81.38, "miles": 1.0}, ((28.54, -81.38),), 1.0),
        ({"geoid": fx.TRACT_EMPTY, "miles": 20.0}, (), 20.0),
    ]
    for args, origins, miles in cases:
        got = tools.sites_near(**args)  # type: ignore[arg-type]
        want_rows = contract.expected_sites_near(origins, miles, sites)
        want = (contract.SITES_NEAR_COLUMNS, want_rows, False)
        assert _view(got) == want, (
            f"POST-TOOL-1 violation for {args}: {_view(got)}\nEXPECTED: {want}"
        )
        if origins:
            assert set(got.referenced_tables) >= {"second_harvest_sites"}, got.referenced_tables
            assert [c.table_name for c in got.citations] == list(got.referenced_tables), (
                "POST-TOOL-1 / SEQ-7 violation: each referenced table must be cited once, in order"
            )
    many = fx.populated_blocks(fx.TRACT_C)
    assert len(many) > contract.MAX_ROW_LIMIT, "ARRANGE: TRACT_C must span more than one page"
    paged = tools.sites_near(geoid=fx.TRACT_C, miles=1.0)
    assert _view(paged) == (
        contract.SITES_NEAR_COLUMNS,
        contract.expected_sites_near(many, 1.0, sites),
        False,
    ), f"POST-TOOL-1 violation: blocks past the first page were left out: {_view(paged)}"
    assert [r["storeid"] for r in paged.rows] == ["S3"]
    at_edge = tools.sites_near(geoid=fx.TRACT_A, miles=edge)
    assert "S2" in [row["storeid"] for row in at_edge.rows], (
        "POST-TOOL-1 violation: a site exactly at the distance is within it"
    )


def test_stats_correlate_counts_only_numeric_pairs_and_refuses_bad_arguments(
    tools: impl.WarehouseTools,
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-TOOL-2, ERRORS-TOOL-1 (REQ-35)
    - Enforces: Pearson over numeric pairs only, n and excluded, the query's citations; every
      contracted bad argument raises ToolArgumentError naming ERRORS-TOOL-1
    - Category: positive / negative / boundary (blank value, two-column rule)
    - Risk tier: High; question 4 of the completion promise is a correlation
    """
    sql = "SELECT pct_poverty, sba_loans_total FROM tract_coverage"
    got = tools.stats_correlate(sql)
    pairs = tuple((t[1] or None, t[2]) for t in fx.TRACTS)
    want = contract.expected_correlation(pairs)
    row = got.rows[0]
    assert got.columns == contract.CORRELATION_COLUMNS
    assert (row["n"], row["coefficient"], row["method"], row["excluded"]) == (
        want.n,
        want.coefficient,
        want.method,
        want.excluded,
    ), f"POST-TOOL-2 violation: {row}\nEXPECTED: {want}"
    assert got.referenced_tables == ("tract_coverage",)
    assert [c.dataset_id for c in got.citations] == ["DS-X12"]

    big = tools.stats_correlate("SELECT i AS a, 2 * i + (i % 7) AS b FROM range(2500) t(i)")
    want_big = contract.expected_correlation(tuple((i, 2 * i + i % 7) for i in range(2500)))
    big_row = big.rows[0]
    assert (big_row["n"], big_row["coefficient"], big.truncated) == (
        want_big.n,
        want_big.coefficient,
        False,
    ), f"POST-TOOL-2 violation: rows past the first page were left out: {big_row}"

    bad_calls = [
        lambda: tools.sites_near(miles=5.0),
        lambda: tools.sites_near(geoid=fx.TRACT_A, lat=28.5, lon=-81.4, miles=5.0),
        lambda: tools.sites_near(geoid=fx.TRACT_A, miles=0.0),
        lambda: tools.sites_near(geoid=fx.TRACT_A, miles=contract.MAX_NEAR_MILES + 0.5),
        lambda: tools.sites_near(lat=91.0, lon=0.0, miles=1.0),
        lambda: tools.sites_near(lat=0.0, lon=181.0, miles=1.0),
        lambda: tools.sites_near(geoid="99999999999", miles=1.0),
        lambda: tools.stats_correlate("SELECT pct_poverty FROM tract_coverage"),
    ]
    for i, call in enumerate(bad_calls):
        with pytest.raises(impl.ToolArgumentError) as caught:
            call()
        assert "ERRORS-TOOL-1" in str(caught.value), (
            f"ERRORS-TOOL-1 violation (case {i}): {caught.value}"
        )
    assert tools.known_geoids == frozenset(t[0] for t in fx.TRACTS)
