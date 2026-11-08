"""Skeleton HTTP server for the App's ask call (ASK_PATH, SLICE-4 batch 2, Z-26).

Run: python -m src.query_service.server (HOST, default 127.0.0.1; PORT, default 8081;
Cloud Run needs HOST=0.0.0.0). It checks the request with parse_ask_request and sends 400 for
a bad body. The Gemini step (REQ-36 to REQ-38, SEQ-10) is not built yet, so answer() raises
AskUnavailableError and every valid question gets 503. The App then shows its built-in fallback
(REQ-39). A 503 never carries an invented answer (REQ-37).
"""

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

from src.query_service.ask import (
    AskReply,
    AskRequest,
    AskRequestError,
    parse_ask_request,
    reply_body,
)

ASK_PATH: Final = "/api/ask"
DEFAULT_HOST: Final = "127.0.0.1"
DEFAULT_PORT: Final = 8081
MAX_BODY_BYTES: Final = 16_384

# Gemini on Vertex AI. answer() reads these when the Gemini step is built.
GEMINI_MODEL_ENV: Final = "GEMINI_MODEL"
GCP_PROJECT_ENV: Final = "GOOGLE_CLOUD_PROJECT"
GCP_LOCATION_ENV: Final = "GOOGLE_CLOUD_LOCATION"


class AskUnavailableError(RuntimeError):
    """The answer step cannot run, so the reply is 503 (REQ-39)."""


def answer(request: AskRequest) -> AskReply:
    """Answer one question from warehouse tool results through Gemini (REQ-36 to REQ-38).

    Not built yet. The planned steps: open the warehouse engine, give Gemini the taxonomy
    (docs/taxonomy.md) and the tools, run the read-only SQL it asks for under
    request.thresholds, and build the AskReply from those results.
    """
    raise AskUnavailableError("The Gemini answer step is not built yet")


class AskHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != ASK_PATH:
            self._send(HTTPStatus.NOT_FOUND, {"error": f"Only POST {ASK_PATH} is served"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "The request is too large"})
            return
        try:
            request = parse_ask_request(json.loads(self.rfile.read(length) or b"null"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": f"The body is not JSON: {exc}"})
            return
        except AskRequestError as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        try:
            reply = answer(request)
        except AskUnavailableError as exc:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
            return
        self._send(HTTPStatus.OK, reply_body(reply))

    def _send(self, status: HTTPStatus, body: dict[str, object]) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    host = os.environ.get("HOST", DEFAULT_HOST)
    server = ThreadingHTTPServer((host, port), AskHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
