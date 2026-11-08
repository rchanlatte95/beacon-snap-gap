"""RED tests for SLICE-4 batch 4: the answer loop (REQ-36, REQ-37, REQ-38, REQ-60).

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (CONTRACT_QUERY_ANSWER)
- Clauses covered: POST-ANS-1, POST-ANS-2, POST-ANS-3, ERRORS-ANS-1, ERRORS-TOOL-1 (error result)
- Requirements: REQ-36, REQ-37, REQ-38, REQ-39, REQ-60, REQ-32, REQ-40

The implementation is src/query_service/answer.py: vertex_client(env, credentials, http_client),
Answerer(client, model, engine, tools, taxonomy_text, clock).answer(request) -> AskReply, and
ModelUnavailableError, AnswerNotGroundedError. It does not import the contract (CL11-F).

Mock fidelity (CL13): the model client is the real Google Gen AI SDK (google-genai 3.0.0) in Vertex
mode; only its HTTP transport is replaced (httpx2.MockTransport, the SDK's own transport type), so
request serialization, URL building, response parsing and error classes are the SDK's. The token
is random at runtime; no credential appears in this file.

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: expectations come from expected_system_instruction, expected_ungrounded_numbers,
  expected_reply_tracts and the engine's own results.
- C2 VALUABLE: a loop that skips the taxonomy or settings, lets the SDK run tools, invents a
  number, crashes on a tool error, or returns a partial answer on failure fails.
- C3 NON-DUPLICATIVE: tools and engine are covered elsewhere; these cover the model loop.
- C4 NOT FUTURE-EDIT: only contracted names.
"""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from contracts import query_service_contract as contract
from google.oauth2.credentials import Credentials
from tests.query_service import fixture_warehouse as fx

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="ARRANGE: the warehouse location is a POSIX path (Cloud Run)"
)

from src.query_service import answer as impl  # noqa: E402
from src.query_service import ask as ask_impl  # noqa: E402
from src.query_service import engine as engine_impl  # noqa: E402
from src.query_service import tools as tools_impl  # noqa: E402

MODEL = "gemini-fixture-flash"
ENV = {contract.PROJECT_ENV: "fixture-project", contract.LOCATION_ENV: "us-central1"}
TAXONOMY = "| Classic Food Desert | poverty at or above the cut and LILA flag 1 |"
QUESTION = "How many loans are there, and which sites are near tract 12095016510?"
BODY = {
    "question": QUESTION,
    "reach_miles": 5,
    "percentiles": {"poverty": 90, "no_vehicle": 75, "sba_rate_per_1000": 25},
}


def _call(name: str, args: dict[str, object]) -> dict[str, object]:
    return {"functionCall": {"name": name, "args": args}}


def _text(text: str) -> dict[str, object]:
    return {"text": text}


class Script:
    """Replies to each Vertex request with the next scripted part; records every request."""

    def __init__(self, parts: list[dict[str, object] | int]) -> None:
        self.parts = list(parts)
        self.requests: list[tuple[str, dict[str, object]]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append((str(request.url), json.loads(request.content)))
        part = self.parts.pop(0)
        if isinstance(part, int):
            return httpx2.Response(
                part, json={"error": {"code": part, "message": "fixture", "status": "UNAVAILABLE"}}
            )
        return httpx2.Response(
            200, json={"candidates": [{"content": {"role": "model", "parts": [part]}}]}
        )


@pytest.fixture
def parts(tmp_path: Path) -> Callable[..., tuple[impl.Answerer, Script]]:
    root = fx.build_warehouse(tmp_path / "warehouse")
    eng = engine_impl.WarehouseQueryEngine({contract.ENGINE_LOCATION_ENV: str(root)})
    eng.open()
    tools = tools_impl.WarehouseTools(eng)

    def make(
        script: Script, clock: Callable[[], float] | None = None
    ) -> tuple[impl.Answerer, Script]:
        client = impl.vertex_client(
            ENV,
            credentials=Credentials(token=secrets.token_urlsafe(16)),
            http_client=httpx2.Client(transport=httpx2.MockTransport(script)),
        )
        kwargs = {} if clock is None else {"clock": clock}
        answerer = impl.Answerer(
            client=client, model=MODEL, engine=eng, tools=tools, taxonomy_text=TAXONOMY, **kwargs
        )
        return answerer, script

    make.engine = eng  # type: ignore[attr-defined]
    return make


def _request() -> ask_impl.AskRequest:
    return ask_impl.parse_ask_request(BODY)


def _applied() -> contract.AppliedThresholds:
    return contract.AppliedThresholds(5.0, 90, 75, 25)


def test_loop_sends_taxonomy_and_settings_runs_tools_itself_and_returns_a_cited_reply(
    parts,
) -> None:  # type: ignore[no-untyped-def]
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-ANS-1, POST-ANS-3, ERRORS-TOOL-1 (REQ-36, REQ-38, REQ-60, REQ-32, REQ-40)
    - Enforces: Vertex URL with the configured model; the exact system instruction; exactly
      TOOL_NAMES declared; the service runs each call and sends its result back; a tool error goes
      back to the model as an error result; the reply holds every result, tracts and settings
    - Category: integration / positive
    - Risk tier: High; this is the AI answer the App shows
    """
    script = Script(
        [
            _call("sql_query", {"sql": "DROP TABLE sba_loans"}),
            _call("sql_query", {"sql": "SELECT count(*) AS n FROM sba_loans"}),
            _call("sites_near", {"geoid": fx.TRACT_A, "miles": 5}),
            _text("There are 20 loans. Tract 12095016510 has 1 site nearby: Pantry One."),
        ]
    )
    answerer, script = parts(script)
    reply = answerer.answer(_request())

    want_instruction = contract.expected_system_instruction(TAXONOMY, _applied())
    for url, body in script.requests:
        assert url.endswith(f"/publishers/google/models/{MODEL}:generateContent"), url
        assert "aiplatform.googleapis.com" in url, f"POST-ANS-1 violation: not Vertex AI: {url}"
        instruction = "".join(p["text"] for p in body["systemInstruction"]["parts"])
        assert instruction == want_instruction, "POST-ANS-1 violation: system instruction"
        declared = {d["name"] for t in body["tools"] for d in t["functionDeclarations"]}
        assert declared == set(contract.TOOL_NAMES), f"POST-ANS-1 violation: tools {declared}"
    # Each request carries the whole conversation, so the last one holds every tool response once.
    responses = [
        p["functionResponse"]
        for c in script.requests[-1][1]["contents"]
        for p in c["parts"]
        if "functionResponse" in p
    ]
    assert [r["name"] for r in responses] == ["sql_query", "sql_query", "sites_near"]
    first = json.dumps(responses[0]["response"])
    assert "error" in first, f"ERRORS-TOOL-1 violation: no error result: {first}"
    assert "FORBIDDEN-SQL-1" in first, f"ERRORS-TOOL-1 violation: clause not named: {first}"
    assert "20" in json.dumps(responses[1]["response"]), (
        "POST-ANS-1 violation: result not sent back"
    )

    assert reply.answer == "There are 20 loans. Tract 12095016510 has 1 site nearby: Pantry One."
    assert reply.model == MODEL
    assert [r.columns for r in reply.results] == [("n",), contract.SITES_NEAR_COLUMNS], (
        "POST-ANS-3 violation: results of every successful call, in call order"
    )
    assert reply.results[0].rows == ({"n": 20},)
    view = tuple(
        contract.SqlQueryResult(
            r.columns, r.rows, r.row_count, r.truncated, r.referenced_tables, ()
        )
        for r in reply.results
    )
    assert reply.tracts == contract.expected_reply_tracts(
        reply.answer, view, frozenset(t[0] for t in fx.TRACTS)
    ), f"POST-ANS-3 violation: tracts {reply.tracts}"
    applied = reply.applied
    assert (
        applied.reach_miles,
        applied.poverty,
        applied.no_vehicle,
        applied.sba_rate_per_1000,
    ) == (
        5.0,
        90,
        75,
        25,
    )


def test_an_ungrounded_number_gets_one_correction_then_fails(parts) -> None:  # type: ignore[no-untyped-def]
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-ANS-2 (REQ-37)
    - Enforces: a number no tool returned triggers CORRECTION_TEMPLATE once; a grounded retry is
      returned; a second ungrounded answer raises AnswerNotGroundedError naming ERRORS-ASK-3
    - Category: negative / boundary
    - Risk tier: High; an invented number must never reach the App
    """
    sql = {"sql": "SELECT count(*) AS n FROM sba_loans"}
    answerer, script = parts(
        Script(
            [_call("sql_query", sql), _text("There are 37 loans."), _text("There are 20 loans.")]
        )
    )
    reply = answerer.answer(_request())
    assert reply.answer == "There are 20 loans."
    texts = [
        p["text"] for c in script.requests[-1][1]["contents"] for p in c["parts"] if "text" in p
    ]
    assert contract.CORRECTION_TEMPLATE.format(numbers="37") in texts, (
        f"POST-ANS-2 violation: no correction naming 37 in {texts}"
    )
    assert contract.expected_ungrounded_numbers(
        "There are 37 loans.", ({"n": 20},), (QUESTION,)
    ) == ("37",)

    answerer, _ = parts(
        Script([_call("sql_query", sql), _text("There are 37 loans."), _text("Still 41 loans.")])
    )
    with pytest.raises(impl.AnswerNotGroundedError) as caught:
        answerer.answer(_request())
    assert "ERRORS-ASK-3" in str(caught.value)


def test_vertex_errors_and_the_deadline_end_the_answer_and_the_last_call_answers(parts) -> None:  # type: ignore[no-untyped-def]
    """
    CONTRACT TRACEABILITY:
    - Contract: ERRORS-ANS-1, POST-ANS-4 (REQ-39, REQ-37, Z-31)
    - Enforces: a Vertex 503 or passing ANSWER_DEADLINE_SECONDS raise ModelUnavailableError naming
      ERRORS-ASK-2; the MAX_TOOL_ROUNDS-th request sets function calling mode FINAL_CALL_MODE and
      its answer is returned, never an error
    - Category: negative / error / boundary
    - Risk tier: High; the App falls back only when the service says it cannot answer
    """
    answerer, script = parts(Script([503] * (contract.CALL_RETRIES + 1)))
    with pytest.raises(impl.ModelUnavailableError) as down:
        answerer.answer(_request())
    assert "ERRORS-ASK-2" in str(down.value)
    assert len(script.requests) == contract.CALL_RETRIES + 1, (
        f"ERRORS-ANS-1 violation: {len(script.requests)} attempts, expected one retry"
    )

    answerer, script = parts(Script([504, _text("No figure.")]))
    reply = answerer.answer(_request())
    assert reply.answer == "No figure.", f"ERRORS-ANS-1 violation: the retry gave {reply.answer!r}"
    assert impl.CALL_TIMEOUT_SECONDS == contract.CALL_TIMEOUT_SECONDS, (
        "ERRORS-ANS-1 violation: the per-call timeout differs from the contract"
    )

    loop = [_call("sql_query", {"sql": "SELECT 1 AS n"})] * (contract.MAX_TOOL_ROUNDS - 1)
    answerer, script = parts(Script([*loop, _text("There is 1.")]))
    reply = answerer.answer(_request())
    assert reply.answer == "There is 1.", f"POST-ANS-4 violation: no answer: {reply.answer!r}"
    assert len(script.requests) == contract.MAX_TOOL_ROUNDS, (
        f"POST-ANS-4 violation: {len(script.requests)} model requests"
    )
    modes = [
        b.get("toolConfig", {}).get("functionCallingConfig", {}).get("mode")
        for _, b in script.requests
    ]
    assert modes[-1] == contract.FINAL_CALL_MODE, f"POST-ANS-4 violation: last mode {modes[-1]}"
    assert contract.FINAL_CALL_MODE not in modes[:-1], f"POST-ANS-4 violation: modes {modes}"
    last_turn = script.requests[-1][1]["contents"][-1]
    assert last_turn["role"] == "user", f"POST-ANS-4 violation: last turn {last_turn['role']}"
    assert [p.get("text") for p in last_turn["parts"]] == [contract.FINAL_ANSWER_PROMPT], (
        f"POST-ANS-4 violation: the final request must end with FINAL_ANSWER_PROMPT: {last_turn}"
    )

    ticks = iter([0.0, 1.0, contract.ANSWER_DEADLINE_SECONDS + 0.1, 100.0, 100.0, 100.0])
    answerer, _ = parts(
        Script([_call("sql_query", {"sql": "SELECT 1 AS n"}), _text("1"), _text("1")]),
        clock=lambda: next(ticks),
    )
    with pytest.raises(impl.ModelUnavailableError) as late:
        answerer.answer(_request())
    assert "ERRORS-ASK-2" in str(late.value)


def test_answers_never_show_sql_or_internal_names(parts) -> None:  # type: ignore[no-untyped-def]
    """
    CONTRACT TRACEABILITY:
    - Contract: FORBIDDEN-ANS-1 (REQ-36, REQ-40)
    - Enforces: an answer with SQL or an internal identifier gets SCHEMA_CORRECTION_TEMPLATE once;
      a clean retry is returned as is; a retry that still leaks is returned scrubbed
    - Category: negative / boundary
    - Risk tier: High; the App must never show the warehouse's SQL or schema to a reader
    """
    sql = {"sql": "SELECT count(*) AS n FROM sba_loans"}
    leaky = "I ran SELECT count(*) FROM sba_loans and sba_loans_all_years shows 20 loans."
    answerer, script = parts(
        Script([_call("sql_query", sql), _text(leaky), _text("There are 20.")])
    )
    reply = answerer.answer(_request())
    assert reply.answer == "There are 20.", f"FORBIDDEN-ANS-1 violation: {reply.answer!r}"
    prompt = script.requests[-1][1]["contents"][-1]["parts"][0]["text"]
    want = contract.SCHEMA_CORRECTION_TEMPLATE.format(
        names=", ".join(contract.expected_leaks(leaky))
    )
    assert prompt == want, f"FORBIDDEN-ANS-1 violation: correction {prompt!r}"

    stubborn = "Rows from sba_loans_all_years:\n```sql\nSELECT 1\n```\nThere are 20 loans."
    answerer, _ = parts(Script([_call("sql_query", sql), _text(stubborn), _text(stubborn)]))
    reply = answerer.answer(_request())
    assert reply.answer == contract.expected_scrubbed_answer(stubborn), (
        f"FORBIDDEN-ANS-1 violation: returned {reply.answer!r}"
    )
    assert contract.expected_leaks(reply.answer) == (), "FORBIDDEN-ANS-1 violation: still leaks"
