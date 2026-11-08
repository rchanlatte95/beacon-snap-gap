"""The QueryService HTTP endpoint (SLICE-4 batch 5): POST /api/ask.

Specification: contracts/query_service_contract.py, CONTRACT_QUERY_HTTP and CONTRACT_QUERY_ASK:
POST-HTTP-1, ERRORS-HTTP-1, SEQ-11, ERRORS-ASK-1, ERRORS-ASK-2, ERRORS-ASK-3. Standard library only
(jev at Ketema's direction). Runtime declarations are independent of the contract module; tests
bridge the two (CL11-F).

Run: python -m src.query_service.server, with WAREHOUSE_LOCATION, QUERY_SERVICE_MODEL,
GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION and PORT set.
"""

import json
import logging
import os
import sys
import threading
from collections.abc import Callable, Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Final

from .answer import (
    TAXONOMY_PATH,
    Answerer,
    AnswerNotGroundedError,
    ModelUnavailableError,
    vertex_client,
)
from .ask import AskReply, AskRequest, AskRequestError, parse_ask_request, reply_body
from .engine import WarehouseQueryEngine
from .tools import WarehouseTools

ASK_PATH: Final = "/api/ask"
MAX_BODY_BYTES: Final = 16_384
MODEL_ENV: Final = "QUERY_SERVICE_MODEL"
REPO_ROOT: Final = Path(__file__).resolve().parents[2]
LOG: Final = logging.getLogger("query_service")
# Answered once at startup at the App's default settings, so these replies come from the cache
# (Ketema: "cache that too"). Every answer still comes from the model and the warehouse.
WARM_SETTINGS: Final = {
    "reach_miles": 10,
    "percentiles": {"poverty": 75, "no_vehicle": 75, "sba_rate_per_1000": 25},
}
WARM_QUESTIONS: Final = (
    # The six baseline questions (requirements section 8, SLICE-4).
    "How many Classic Food Desert tracts are in Orange County, and how many of them had 10 or "
    "fewer SBA loans?",
    "Which five lenders approved the most SBA 7(a) loans in Florida with an approval date in 2024 "
    "or later?",
    "Among the Classic Food Desert tracts, which five have the highest FEMA hurricane expected "
    "annual loss?",
    "Across the 490 Central Florida tracts, how strongly is poverty rate correlated with SBA loan "
    "count?",
    "Where did the median income for tract 12095016510 come from, and how reliable is it?",
    "How many people lost SNAP in Seminole County?",
    # The App's quick-question buttons (src/viewContent.ts).
    "All three gaps in Orange County",
    "Food deserts with no pantry and few SBA loans",
    "Places with missing data",
    "Food deserts with no pantry in Orange County",
    "Where should a mobile pantry go in Osceola?",
    "Food deserts with few SBA loans in Orange County",
    "Food deserts with few SBA loans in Osceola",
)


def warm_cache(answer: Callable[[AskRequest], AskReply]) -> None:
    """Answer WARM_QUESTIONS once so their replies are cached; a failure is logged, not fatal."""
    for question in WARM_QUESTIONS:
        try:
            answer(parse_ask_request({"question": question, **WARM_SETTINGS}))
            LOG.info("cache warmed: %s", question)
        except (ModelUnavailableError, AnswerNotGroundedError) as exc:
            LOG.warning("cache warm failed for %r: %s", question, exc)


def make_server(
    answer: Callable[[AskRequest], AskReply], host: str, port: int
) -> ThreadingHTTPServer:
    """An HTTP server that answers POST ASK_PATH with answer (POST-HTTP-1, ERRORS-HTTP-1)."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: HTTPStatus, body: Mapping[str, object]) -> None:
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _refuse_method(self) -> None:
            if self.path == ASK_PATH:
                self._send(HTTPStatus.METHOD_NOT_ALLOWED, {"error": f"use POST on {ASK_PATH}"})
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": f"no resource at {self.path}"})

        do_GET = do_PUT = do_DELETE = do_PATCH = _refuse_method  # noqa: N815

        def do_POST(self) -> None:
            if self.path != ASK_PATH:
                self._send(HTTPStatus.NOT_FOUND, {"error": f"no resource at {self.path}"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._send(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"ERRORS-ASK-1 violation: body over {MAX_BODY_BYTES} bytes"},
                )
                self.close_connection = True
                return
            try:
                request = parse_ask_request(json.loads(self.rfile.read(length) or b"null"))
            except json.JSONDecodeError as exc:
                self._send(
                    HTTPStatus.BAD_REQUEST, {"error": f"ERRORS-ASK-1 violation: not JSON: {exc}"}
                )
                return
            except AskRequestError as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            try:
                reply = answer(request)
            except (ModelUnavailableError, AnswerNotGroundedError) as exc:
                self.log_message("ask refused: %s", exc)
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
                return
            self._send(HTTPStatus.OK, reply_body(reply))

    return ThreadingHTTPServer((host, port), Handler)


def main(env: Mapping[str, str]) -> int:
    """Open the engine and read the taxonomy, then serve (SEQ-11); exit non-zero on failure."""
    try:
        engine = WarehouseQueryEngine(env)
        engine.open()
        tools = WarehouseTools(engine)
        taxonomy = (REPO_ROOT / TAXONOMY_PATH).read_text(encoding="utf-8")
        answerer = Answerer(
            client=vertex_client(env),
            model=env[MODEL_ENV],
            engine=engine,
            tools=tools,
            taxonomy_text=taxonomy,
        )
        server = make_server(answerer.answer, "0.0.0.0", int(env.get("PORT", "8080")))  # noqa: S104 - Cloud Run
    except Exception:
        LOG.exception("SEQ-11 violation: the QueryService cannot start")
        return 1
    LOG.info("QueryService listening on port %s", server.server_address[1])
    threading.Thread(target=warm_cache, args=(answerer.answer,), daemon=True).start()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    sys.exit(main(os.environ))
