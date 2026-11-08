"""RED tests for SLICE-4 batch 5: the HTTP endpoint and service startup.

CONTRACT AUTHORITY RECORD:
- File: contracts/query_service_contract.py (CONTRACT_QUERY_HTTP, CONTRACT_QUERY_ASK)
- Clauses covered: POST-HTTP-1, ERRORS-HTTP-1, SEQ-11 (and ERRORS-ASK-1, ERRORS-ASK-2,
  ERRORS-ASK-3 at the HTTP boundary)
- Requirements: REQ-39, REQ-60, REQ-40, REQ-46, REQ-36

The implementation is src/query_service/server.py: make_server(answer, host, port) returning a
standard-library ThreadingHTTPServer, and a module entry point (python -m src.query_service.server).
It does not import the contract (CL11-F). The answer function is the real Answerer over the real
Google Gen AI SDK with only its HTTP transport replaced (see test_answer.py).

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: statuses and error clause names come from the contract.
- C2 VALUABLE: a server that calls the model on a bad body, returns 200 on an outage, or starts
  without a warehouse fails.
- C3 NON-DUPLICATIVE: the loop is covered in test_answer.py; these cover the HTTP mapping.
- C4 NOT FUTURE-EDIT: only contracted names.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import pytest
from contracts import query_service_contract as contract
from google.oauth2.credentials import Credentials
from tests.query_service import fixture_warehouse as fx
from tests.query_service.test_answer import BODY, ENV, MODEL, TAXONOMY, Script, _call, _text

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="ARRANGE: the warehouse location is a POSIX path (Cloud Run)"
)

from src.query_service import answer as answer_impl  # noqa: E402
from src.query_service import ask as ask_impl  # noqa: E402
from src.query_service import engine as engine_impl  # noqa: E402
from src.query_service import server as impl  # noqa: E402
from src.query_service import tools as tools_impl  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


class Recorder:
    """Wraps the real answer function and keeps each reply and call count."""

    def __init__(self, answerer: answer_impl.Answerer) -> None:
        self.answerer = answerer
        self.calls = 0
        self.replies: list[ask_impl.AskReply] = []

    def __call__(self, request: ask_impl.AskRequest) -> ask_impl.AskReply:
        self.calls += 1
        reply = self.answerer.answer(request)
        self.replies.append(reply)
        return reply


@pytest.fixture
def serve(tmp_path: Path) -> Iterator[Callable[[Script], tuple[str, Recorder]]]:
    root = fx.build_warehouse(tmp_path / "warehouse")
    eng = engine_impl.WarehouseQueryEngine({contract.ENGINE_LOCATION_ENV: str(root)})
    eng.open()
    tools = tools_impl.WarehouseTools(eng)
    servers = []

    def start(script: Script) -> tuple[str, Recorder]:
        client = answer_impl.vertex_client(
            ENV,
            credentials=Credentials(token=secrets.token_urlsafe(16)),
            http_client=httpx2.Client(transport=httpx2.MockTransport(script)),
        )
        recorder = Recorder(
            answer_impl.Answerer(
                client=client, model=MODEL, engine=eng, tools=tools, taxonomy_text=TAXONOMY
            )
        )
        server = impl.make_server(recorder, "127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}", recorder

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _post(url: str, data: bytes, method: str = "POST") -> tuple[int, dict[str, object], str]:
    # the URL is always the local test server (http://127.0.0.1)
    req = urllib.request.Request(  # noqa: S310
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - local test server
            return (
                resp.status,
                json.loads(resp.read() or b"{}"),
                resp.headers.get("Content-Type", ""),
            )
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}"), err.headers.get("Content-Type", "")


def test_ask_returns_the_reply_body_and_maps_failures_to_their_statuses(serve) -> None:  # type: ignore[no-untyped-def]
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-HTTP-1, ERRORS-HTTP-1 (REQ-60, REQ-40, REQ-39)
    - Enforces: 200 with the exact reply body; 400 naming ERRORS-ASK-1 without calling the model
      for a bad, non-JSON or oversized body; 503 naming ERRORS-ASK-2 on a Vertex outage and
      ERRORS-ASK-3 on an ungrounded answer; 404 for another path; 405 for another method
    - Category: integration / positive / negative
    - Risk tier: High; the App maps these statuses to what the Viewer sees
    """
    base, rec = serve(
        Script(
            [
                _call("sql_query", {"sql": "SELECT count(*) AS n FROM sba_loans"}),
                _text("There are 20 loans."),
            ]
        )
    )
    status, body, ctype = _post(base + contract.ASK_PATH, json.dumps(BODY).encode())
    assert status == contract.ASK_STATUS_OK, f"POST-HTTP-1 violation: status {status} {body}"
    assert ctype.startswith("application/json")
    assert body == ask_impl.reply_body(rec.replies[0]), "POST-HTTP-1 violation: body"

    for label, data in (
        ("not JSON", b"{nope"),
        ("bad body", json.dumps({**BODY, "reach_miles": 7.3}).encode()),
        ("too large", b'{"question": "' + b"x" * contract.MAX_BODY_BYTES + b'"}'),
    ):
        calls = rec.calls
        status, body, _ = _post(base + contract.ASK_PATH, data)
        assert (status, "ERRORS-ASK-1" in str(body.get("error"))) == (400, True), (
            f"ERRORS-HTTP-1 violation ({label}): {status} {body}"
        )
        assert rec.calls == calls, f"ERRORS-HTTP-1 violation ({label}): the model was called"

    assert _post(base + "/api/other", json.dumps(BODY).encode())[0] == 404
    assert _post(base + contract.ASK_PATH, None, method="GET")[0] == 405

    down, _ = serve(Script([503]))
    status, body, _ = _post(down + contract.ASK_PATH, json.dumps(BODY).encode())
    assert (status, "ERRORS-ASK-2" in str(body.get("error"))) == (
        contract.ASK_STATUS_UNAVAILABLE,
        True,
    ), body

    sql = {"sql": "SELECT count(*) AS n FROM sba_loans"}
    vague, _ = serve(Script([_call("sql_query", sql), _text("37 loans."), _text("41 loans.")]))
    status, body, _ = _post(vague + contract.ASK_PATH, json.dumps(BODY).encode())
    assert (status, "ERRORS-ASK-3" in str(body.get("error"))) == (
        contract.ASK_STATUS_UNAVAILABLE,
        True,
    ), body


def test_service_without_a_warehouse_exits_non_zero_naming_the_failure() -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: SEQ-11 (REQ-46, REQ-36; CL9)
    - Enforces: with no WAREHOUSE_LOCATION the process exits non-zero before serving, and its
      error output names SEQ-11
    - Category: negative / lifecycle
    - Risk tier: High; a service that starts without its warehouse would answer from nothing
    """
    env = {k: v for k, v in os.environ.items() if k != contract.ENGINE_LOCATION_ENV}
    env |= {"PORT": "0", contract.MODEL_ENV: MODEL, **ENV}
    done = subprocess.run(
        [sys.executable, "-m", "src.query_service.server"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode != 0, f"SEQ-11 violation: exit code {done.returncode}"
    assert "SEQ-11" in done.stderr, f"SEQ-11 violation: stderr {done.stderr[-300:]!r}"
