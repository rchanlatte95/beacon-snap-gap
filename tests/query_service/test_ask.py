"""RED tests for SLICE-4 batch 2: the ask request and reply (Z-26).

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (CONTRACT_QUERY_ASK)
- Clauses covered: PRE-ASK-1, ERRORS-ASK-1 (the parser; the HTTP 400 mapping is tested with the
  endpoint in a later batch), POST-ASK-1
- Requirements: REQ-60, REQ-32, REQ-40

The implementation is src/query_service/ask.py. It does not import the contract (CL11-F).

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: expected values come from expected_ask_request and expected_reply_json.
- C2 VALUABLE: a parser that accepts a wrong threshold, or a reply that drops tracts, repeats a
  citation or changes the thresholds, fails.
- C3 NON-DUPLICATIVE: test_schema_and_sql.py covers the tools; these cover the ask boundary.
- C4 NOT FUTURE-EDIT: only the contracted names are used.
"""

from __future__ import annotations

import pytest
from contracts import query_service_contract as contract
from src.query_service import ask as impl

GOOD = {
    "question": "  Which food deserts lack SBA loans?  ",
    "reach_miles": 7.5,
    "percentiles": {"poverty": 90, "no_vehicle": 75, "sba_rate_per_1000": 10},
}
BAD = [
    ("missing key", {"question": "x", "reach_miles": 10}),
    ("extra key", {**GOOD, "model": "other"}),
    ("not an object", ["question"]),
    ("blank question", {**GOOD, "question": "   "}),
    ("question not text", {**GOOD, "question": 3}),
    ("off-step distance", {**GOOD, "reach_miles": 7.3}),
    ("distance past the range", {**GOOD, "reach_miles": 20.5}),
    ("boolean distance", {**GOOD, "reach_miles": True}),
    ("percentile not offered", {**GOOD, "percentiles": {**GOOD["percentiles"], "poverty": 80}}),
    ("boolean percentile", {**GOOD, "percentiles": {**GOOD["percentiles"], "no_vehicle": True}}),
    ("missing cut", {**GOOD, "percentiles": {"poverty": 90, "no_vehicle": 75}}),
]


def test_ask_request_is_parsed_exactly_as_contracted() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: query_service_contract PRE-ASK-1, ERRORS-ASK-1 (REQ-60, Z-26)
    - Enforces: a valid body gives the trimmed question and the thresholds; every bad body raises
      the implementation's AskRequestError naming ERRORS-ASK-1
    - Category: positive / negative / boundary (step edges, booleans, extra keys)
    - Risk tier: High; a question answered under other thresholds than the screen shows misleads
    """
    want = contract.expected_ask_request(GOOD)
    got = impl.parse_ask_request(GOOD)
    got_view = (
        got.question,
        got.thresholds.reach_miles,
        got.thresholds.poverty,
        got.thresholds.no_vehicle,
        got.thresholds.sba_rate_per_1000,
    )
    want_view = (
        want.question,
        want.thresholds.reach_miles,
        want.thresholds.poverty,
        want.thresholds.no_vehicle,
        want.thresholds.sba_rate_per_1000,
    )
    assert got_view == want_view, (
        f"PRE-ASK-1 violation: parsed {got_view}\nEXPECTED: {want_view}\n"
        "GUIDANCE: trim the question; keep the distance and the three percentiles"
    )
    for label, body in BAD:
        with pytest.raises(contract.AskRequestError):
            contract.expected_ask_request(body)
        with pytest.raises(impl.AskRequestError) as caught:
            impl.parse_ask_request(body)
        assert "ERRORS-ASK-1" in str(caught.value), (
            f"ERRORS-ASK-1 violation ({label}): the error does not name the clause: {caught.value}"
        )


def test_reply_body_carries_results_citations_tracts_and_applied_thresholds() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: query_service_contract POST-ASK-1 (REQ-60, REQ-32, REQ-40, Z-26)
    - Enforces: the 200 body equals expected_reply_json: citations first per table in result
      order, every tract kept (more than DEFAULT_ROW_LIMIT), thresholds applied echoed
    - Category: positive / boundary (repeated citation, 490 tracts)
    - Risk tier: High; the App draws the map and the chips from this body
    """
    loans = {
        "table_name": "sba_loans",
        "dataset_id": "DS-X5",
        "origin_url": "https://data.sba.gov/dataset/7a-504-foia",
        "publisher": "U.S. Small Business Administration",
        "as_of": "2026-09-30",
        "applied_filter": 'state field "BorrState" in FL, NY, UT',
    }
    pop = {
        "table_name": "tract_pop",
        "dataset_id": "DS-X24",
        "origin_url": "not recorded",
        "publisher": "U.S. Census Bureau",
        "as_of": "2020",
        "applied_filter": "none",
    }
    tracts = tuple(f"12095{n:06d}" for n in range(490))
    rows = ({"geoid": tracts[0], "loans": 3}, {"geoid": tracts[1], "loans": 0})

    def results(cls_result: type, cls_citation: type) -> tuple[object, ...]:
        return (
            cls_result(
                columns=("geoid", "loans"),
                rows=rows,
                row_count=2,
                truncated=False,
                referenced_tables=("sba_loans", "tract_pop"),
                citations=(cls_citation(**loans), cls_citation(**pop)),
            ),
            cls_result(
                columns=("n",),
                rows=({"n": 490},),
                row_count=1,
                truncated=False,
                referenced_tables=("sba_loans",),
                citations=(cls_citation(**loans),),
            ),
        )

    applied = {"reach_miles": 7.5, "poverty": 90, "no_vehicle": 75, "sba_rate_per_1000": 10}
    want = contract.expected_reply_json(
        contract.AskReply(
            answer="26 food deserts have few SBA loans.",
            model="gemini-3.8-flash",
            results=results(contract.SqlQueryResult, contract.SourceCitation),  # type: ignore[arg-type]
            tracts=tracts,
            applied=contract.AppliedThresholds(**applied),
        )
    )
    got = impl.reply_body(
        impl.AskReply(
            answer="26 food deserts have few SBA loans.",
            model="gemini-3.8-flash",
            results=results(impl.SqlQueryResult, impl.SourceCitation),
            tracts=tracts,
            applied=impl.AppliedThresholds(**applied),
        )
    )
    assert len(want["citations"]) == 2  # type: ignore[arg-type]
    assert got == want, (
        "POST-ASK-1 violation: the reply body differs from expected_reply_json\n"
        f"EXPECTED keys {sorted(want)}, citations {want['citations']}\n"
        f"ACTUAL keys {sorted(got) if isinstance(got, dict) else got!r}\n"
        "GUIDANCE: citations once per table in result order; every tract; applied thresholds"
    )
