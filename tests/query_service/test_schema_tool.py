"""RED tests for the schema_describe tool payload the model receives (REQ-33).

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (CONTRACT_QUERY_TOOLS)
- Clauses covered: POST-TOOL-3, ERRORS-TOOL-1 (the schema_describe argument errors)
- Requirements: REQ-33, REQ-35

Execution finding behind POST-TOOL-3: on the real warehouse the payload of schema_describe with no
table names was 1,971,984 characters, and the next Vertex call failed with 429 or 504.

The implementation is src/query_service/answer.py (Answerer); it does not import the contract
(CL11-F). Mock fidelity (CL13): the real Google Gen AI SDK in Vertex mode with only its HTTP
transport replaced (httpx2.MockTransport), as in test_answer.py. The token is random at runtime.

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: POST-TOOL-3 and ERRORS-TOOL-1 exist; expectations come from expected_schema_payload
  over the engine's own describe_schema output.
- C2 VALUABLE: a payload that sends every column or glossary term at once, pages at the wrong
  offset, drops a key, or accepts an out-of-contract argument fails.
- C3 NON-DUPLICATIVE: test_schema_and_sql.py covers the engine's describe_schema (POST-SCHEMA-1);
  these cover what the tool sends the model.
- C4 NOT FUTURE-EDIT: the loop already answers schema_describe calls; these bound that path.
"""

from __future__ import annotations

import json
import os
import secrets
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
ENV = {contract.PROJECT_ENV: "fixture-project", contract.LOCATION_ENV: "global"}
BODY = {
    "question": "Which tables hold SBA loans?",
    "reach_miles": 5,
    "percentiles": {"poverty": 90, "no_vehicle": 75, "sba_rate_per_1000": 25},
}
# One term past a full page: the boundary between a page with a next offset and the last page.
GLOSSARY_TERMS = contract.GLOSSARY_PAGE_TERMS + 1


class Script:
    """Replies to each Vertex request with the next scripted part; records every request body."""

    def __init__(self, parts: list[dict[str, object]]) -> None:
        self.parts = list(parts)
        self.bodies: list[dict[str, object]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        part = self.parts.pop(0)
        return httpx2.Response(
            200, json={"candidates": [{"content": {"role": "model", "parts": [part]}}]}
        )


def _call(args: dict[str, object]) -> dict[str, object]:
    return {"functionCall": {"name": "schema_describe", "args": args}}


def _responses(script: Script) -> list[dict[str, object]]:
    # Each request repeats the whole conversation, so the last one holds every tool response once.
    last = script.bodies[-1]["contents"]
    assert isinstance(last, list)
    return [
        p["functionResponse"]["response"]
        for c in last
        for p in c["parts"]
        if "functionResponse" in p
    ]


def _answer(
    tmp_path: Path, calls: list[dict[str, object]]
) -> tuple[engine_impl.WarehouseQueryEngine, Script]:
    root = fx.build_warehouse(tmp_path / "warehouse", glossary_terms=GLOSSARY_TERMS)
    eng = engine_impl.WarehouseQueryEngine({contract.ENGINE_LOCATION_ENV: str(root)})
    eng.open()
    script = Script([*(_call(a) for a in calls), {"text": "The SBA loans table holds them."}])
    client = impl.vertex_client(
        ENV,
        credentials=Credentials(token=secrets.token_urlsafe(16)),
        http_client=httpx2.Client(transport=httpx2.MockTransport(script)),
    )
    answerer = impl.Answerer(
        client=client,
        model=MODEL,
        engine=eng,
        tools=tools_impl.WarehouseTools(eng),
        taxonomy_text="| Classic Food Desert | fixture |",
    )
    answerer.answer(ask_impl.parse_ask_request(BODY))
    return eng, script


def _as_contract(described: tuple[object, ...]) -> tuple[contract.TableSchemaDescription, ...]:
    return tuple(
        contract.TableSchemaDescription(
            d.table_name,  # type: ignore[attr-defined]
            d.dataset_id,  # type: ignore[attr-defined]
            tuple(d.columns),  # type: ignore[attr-defined]
            d.grain,  # type: ignore[attr-defined]
            tuple(d.join_keys),  # type: ignore[attr-defined]
            d.as_of,  # type: ignore[attr-defined]
            d.applied_filter,  # type: ignore[attr-defined]
            tuple(tuple(t) for t in d.glossary_terms),  # type: ignore[attr-defined]
        )
        for d in described
    )


def test_schema_tool_sends_an_index_then_detail_with_the_glossary_paged(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-TOOL-3 (REQ-33)
    - Enforces: no table_names gives the index of every catalog table; table_names gives full
      descriptions with glossary terms GLOSSARY_PAGE_TERMS at a time from glossary_offset, with
      the next offset, and None on the last page
    - Category: integration / boundary (a full page, then the one remaining term)
    - Risk tier: High; an oversized payload makes every question fail at Vertex
    - Partition: no names | names, offset 0 (full page, next 200) | names, offset 200 (last page)
    """
    eng, script = _answer(
        tmp_path,
        [
            {},
            {"table_names": ["sba_loans"]},
            {"table_names": ["sba_loans"], "glossary_offset": contract.GLOSSARY_PAGE_TERMS},
        ],
    )
    every = _as_contract(eng.describe_schema())
    loans = _as_contract(eng.describe_schema(table_names=("sba_loans",)))
    want = [
        contract.expected_schema_payload(every, detailed=False),
        contract.expected_schema_payload(loans, detailed=True),
        contract.expected_schema_payload(
            loans, detailed=True, glossary_offset=contract.GLOSSARY_PAGE_TERMS
        ),
    ]
    got = [r.get("result") for r in _responses(script)]
    for i, label in enumerate(("index", "first glossary page", "last glossary page")):
        assert got[i] == want[i], (
            f"POST-TOOL-3 violation: the {label} payload differs from expected_schema_payload\n"
            f"EXPECTED: {json.dumps(want[i])[:600]}\n"
            f"ACTUAL: {json.dumps(got[i])[:600]}\n"
            "GUIDANCE: without table names send only the table index; with table names send "
            "the full descriptions with one page of glossary terms and the next offset"
        )


@pytest.mark.parametrize(
    ("args", "label"),
    [
        ({"table_names": []}, "empty table_names"),
        (
            {"table_names": ["sba_loans"] * (contract.MAX_DESCRIBE_TABLES + 1)},
            "more than MAX_DESCRIBE_TABLES names",
        ),
        ({"table_names": ["sba_loans"], "glossary_offset": -1}, "a negative glossary_offset"),
        ({"table_names": ["sba_loans"], "glossary_offset": 1.5}, "a fractional glossary_offset"),
        ({"glossary_offset": 0}, "glossary_offset without table_names"),
    ],
)
def test_schema_tool_refuses_arguments_outside_its_contract(
    tmp_path: Path, args: dict[str, object], label: str
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: ERRORS-TOOL-1 (REQ-33, REQ-35)
    - Enforces: schema_describe raises ToolArgumentError naming ERRORS-TOOL-1 for each refused
      argument class, and the error reaches the model as an error result, never as a crash
    - Category: negative (one representative per refused class)
    - Risk tier: Medium; an unbounded request rebuilds the oversized payload
    """
    _, script = _answer(tmp_path, [args])
    (response,) = _responses(script)
    text = json.dumps(response)
    message = (
        f"ERRORS-TOOL-1 violation: {label} was not refused\n"
        "EXPECTED: an error result naming ERRORS-TOOL-1\n"
        f"ACTUAL: {text[:400]}\n"
        "GUIDANCE: refuse schema_describe arguments outside the contracted ranges"
    )
    assert "error" in response, message
    assert "ERRORS-TOOL-1" in str(response["error"]), message
