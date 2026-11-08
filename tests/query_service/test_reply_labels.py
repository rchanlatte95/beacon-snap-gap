"""RED test: the reply shows result columns as words (FORBIDDEN-ANS-1, the App's answer table).

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (column_label, expected_reply_json, FORBIDDEN-ANS-1)
- Requirements: REQ-36, REQ-40

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: expected_reply_json and column_label exist in the contract.
- C2 VALUABLE: a reply that sends snake_case column names or row keys to the App fails.
- C3 NON-DUPLICATIVE: test_http checks the reply over HTTP with fixture columns that have no
  underscore; this checks the label rule itself.
- C4 NOT FUTURE-EDIT: reply_body builds these fields today.
"""

from __future__ import annotations

from contracts import query_service_contract as contract
from src.query_service import ask as impl


def test_reply_sends_result_columns_as_words() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: FORBIDDEN-ANS-1, POST-ASK-1 (REQ-36, REQ-40)
    - Enforces: result columns and row keys in the reply body are column_label of the names
    - Category: negative
    - Risk tier: High; the App shows these as table headers
    """
    result = impl.SqlQueryResult(
        columns=("county", "loans_total"),
        rows=({"county": "Orange", "loans_total": "3"},),
        row_count=1,
        truncated=False,
        referenced_tables=(),
        citations=(),
    )
    reply = impl.AskReply(
        answer="Orange has 3 loans.",
        model="m",
        results=(result,),
        tracts=(),
        applied=impl.AppliedThresholds(10.0, 75, 75, 25),
    )
    body = impl.reply_body(reply)
    want = contract.expected_reply_json(reply)  # type: ignore[arg-type]
    assert body["results"] == want["results"], (
        f"FORBIDDEN-ANS-1 violation: result columns {body['results']}\n"
        f"EXPECTED: {want['results']}\n"
        "GUIDANCE: send result columns and row keys as words, not internal field names"
    )
