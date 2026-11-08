"""The answer loop: Vertex AI Gemini with the QueryService's tools (REQ-36, REQ-37, REQ-38, REQ-60).

Specification: contracts/query_service_contract.py, CONTRACT_QUERY_ANSWER (SLICE-4 batch 4):
POST-ANS-1, POST-ANS-2, POST-ANS-3, ERRORS-ANS-1. The model is called through the Google Gen AI
SDK in Vertex AI mode with the service's own identity; automatic function calling is off, so this
module runs every tool call and keeps every result. Runtime declarations are independent of the
contract module; tests bridge the two (CL11-F).
"""

import json
import logging
import math
import re
import threading
import time
from collections.abc import Callable, Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final

import google.auth.credentials
import httpx2
from google import genai
from google.genai import errors, types

from .ask import AppliedThresholds, AskReply, AskRequest, SqlQueryResult
from .engine import QueryServiceError, WarehouseQueryEngine
from .tools import CORRELATION_CAVEATS, ToolArgumentError, WarehouseTools

LOG: Final = logging.getLogger("query_service")
PROJECT_ENV: Final = "GOOGLE_CLOUD_PROJECT"
LOCATION_ENV: Final = "GOOGLE_CLOUD_LOCATION"
MAX_TOOL_ROUNDS: Final = 4
ANSWER_DEADLINE_SECONDS: Final = 45.0
CALL_TIMEOUT_SECONDS: Final = 12.0
CALL_RETRIES: Final = 1
MAX_DESCRIBE_TABLES: Final = 10
GLOSSARY_PAGE_TERMS: Final = 200
TAXONOMY_PATH: Final = "docs/taxonomy.md"
SYSTEM_PREAMBLE: Final = (
    "You answer questions about Central Florida public data for food bank planners and small "
    "business lenders. Use only the tools. Every number you state must come from a tool result, "
    "the question or the current settings. If the data does not hold the answer, say so. Name no "
    "source that a tool did not return. You have at most 3 tool rounds, so run a sql_query in "
    "your first round when the table index below names a likely table, and put several "
    "independent calls in one round. Answer in plain sentences only: no Markdown, backticks, "
    "asterisks, headings, bullet symbols or table names; name places and figures in words."
)
CORRECTION_TEMPLATE: Final = (
    "These numbers in your answer came from no tool result: {numbers}. Answer again using only "
    "numbers from tool results, or say that the data does not hold them."
)
FINAL_ANSWER_PROMPT: Final = (
    "Answer the question now from the tool results above. Do not call any tool. If they do not "
    "hold the answer, say so."
)
NUMBER_PATTERN: Final = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?![\w])")
TRACT_PREFIX: Final = "1400000US"
_TRACT_IN_TEXT: Final = re.compile(r"\d{11}")


class ModelUnavailableError(Exception):
    """ERRORS-ASK-2: Vertex AI failed, timed out, or the answer passed its deadline or rounds."""


class AnswerNotGroundedError(Exception):
    """ERRORS-ASK-3: the answer kept a number that no tool result, question or setting holds."""


def vertex_client(
    env: Mapping[str, str],
    *,
    credentials: google.auth.credentials.Credentials | None = None,
    http_client: httpx2.Client | None = None,
) -> genai.Client:
    """A Gen AI client for Vertex AI in the configured project and location (REQ-38).

    With no credentials the SDK uses Application Default Credentials, which on Cloud Run are the
    service's own identity; no API key is used.

    Raises:
        KeyError: SEQ-11, the project or location is not configured.
    """
    for name in (PROJECT_ENV, LOCATION_ENV):
        if not env.get(name):
            raise KeyError(f"SEQ-11 violation: {name} is not set")
    options = types.HttpOptions(timeout=int(CALL_TIMEOUT_SECONDS * 1000), httpx_client=http_client)
    return genai.Client(
        vertexai=True,
        project=env[PROJECT_ENV],
        location=env[LOCATION_ENV],
        credentials=credentials,
        http_options=options,
    )


def system_instruction(taxonomy_text: str, applied: AppliedThresholds, index_json: str) -> str:
    """The instruction sent with every question: preamble, taxonomy, table index, settings."""
    return (
        f"{SYSTEM_PREAMBLE}\n\n## Core taxonomy ({TAXONOMY_PATH})\n{taxonomy_text.strip()}\n\n"
        f"## Warehouse table index (schema_describe without table_names)\n{index_json}\n\n"
        + settings_text(applied)
    )


def settings_text(applied: AppliedThresholds) -> str:
    """The App's current settings, as the model reads them (REQ-60)."""
    return (
        "## Current settings\n"
        f"Reach distance: {applied.reach_miles:g} miles, straight-line.\n"
        f"Poverty cut: the {applied.poverty}th percentile.\n"
        f"No-vehicle cut: the {applied.no_vehicle}th percentile.\n"
        f"SBA loans per 1,000 residents cut: the {applied.sba_rate_per_1000}th percentile."
    )


def _decimals(text: str) -> list[Decimal]:
    found = []
    for match in NUMBER_PATTERN.finditer(text):
        try:
            found.append(Decimal(match.group(0).replace(",", "")))
        except InvalidOperation:
            continue
    return found


def _payload_numbers(value: object) -> set[Decimal]:
    if isinstance(value, Mapping):
        return set().union(*(_payload_numbers(v) for v in value.values()))
    if isinstance(value, list | tuple):
        return set().union(*(_payload_numbers(v) for v in value))
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, int | float):
        return {Decimal(str(value))} if math.isfinite(value) else set()
    return set(_decimals(str(value)))


def ungrounded_numbers(
    answer: str, payloads: list[object], allowed_texts: tuple[str, ...]
) -> tuple[str, ...]:
    """Numbers written in the answer that no tool payload, question or setting holds (REQ-37).

    A written number is grounded by an equal number, or by a tool number that rounds half-up to it
    at the written decimal places; a percentage may also be a tool share times 100.
    """
    pool: set[Decimal] = (
        set().union(*(_payload_numbers(p) for p in payloads)) if payloads else set()
    )
    allowed = {n for t in allowed_texts for n in _decimals(t)}
    bad: list[str] = []
    for match in NUMBER_PATTERN.finditer(answer):
        written = match.group(0)
        try:
            value = Decimal(written.replace(",", ""))
        except InvalidOperation:
            continue
        exponent = value.as_tuple().exponent
        places = Decimal(1).scaleb(exponent if isinstance(exponent, int) else 0)
        candidates = pool | (
            {v * 100 for v in pool} if answer[match.end() : match.end() + 1] == "%" else set()
        )
        grounded = (
            value in pool
            or value in allowed
            or any(c.quantize(places, rounding=ROUND_HALF_UP) == value for c in candidates)
        )
        if not grounded and written not in bad:
            bad.append(written)
    return tuple(bad)


def reply_tracts(
    answer: str, results: tuple[SqlQueryResult, ...], known: frozenset[str]
) -> tuple[str, ...]:
    """Known tract GEOIDs in the results' cells, then in the answer, in first-seen order."""
    seen: dict[str, None] = {}
    for result in results:
        for row in result.rows:
            for column in result.columns:
                cell = row.get(column)
                geoid = ("" if cell is None else str(cell)).removeprefix(TRACT_PREFIX)
                if geoid in known:
                    seen.setdefault(geoid, None)
    for match in _TRACT_IN_TEXT.finditer(answer):
        if match.group(0) in known:
            seen.setdefault(match.group(0), None)
    return tuple(seen)


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)


def _result_payload(result: SqlQueryResult) -> dict[str, object]:
    return {
        "columns": list(result.columns),
        "rows": [_json_safe(dict(r)) for r in result.rows],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "referenced_tables": list(result.referenced_tables),
    }


def _schema(properties: dict[str, types.Schema], required: list[str]) -> types.Schema:
    return types.Schema(type=types.Type.OBJECT, properties=properties, required=required)


_STRING = types.Schema(type=types.Type.STRING)
_NUMBER = types.Schema(type=types.Type.NUMBER)
TOOL_DECLARATIONS: Final = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="schema_describe",
            description="Describe warehouse tables. With no table_names: an index of every table "
            "(name, dataset, grain, as-of date, column and glossary-term counts). With "
            f"table_names (1 to {MAX_DESCRIBE_TABLES}): their columns, grain, join keys, as-of "
            f"dates and glossary terms, {GLOSSARY_PAGE_TERMS} terms at a time from "
            "glossary_offset; glossary_next_offset gives the next page.",
            parameters=_schema(
                {
                    "table_names": types.Schema(type=types.Type.ARRAY, items=_STRING),
                    "glossary_offset": types.Schema(type=types.Type.INTEGER),
                },
                [],
            ),
        ),
        types.FunctionDeclaration(
            name="sql_query",
            description="Run one read-only DuckDB SELECT over the warehouse tables. Results are "
            "capped at row_limit rows (default 200, at most 1000); page with LIMIT and OFFSET.",
            parameters=_schema(
                {"sql": _STRING, "row_limit": types.Schema(type=types.Type.INTEGER)}, ["sql"]
            ),
        ),
        types.FunctionDeclaration(
            name="sites_near",
            description="Second Harvest sites within miles (at most 20) of a point (lat, lon) or "
            "of a tract's populated blocks (geoid, 11 digits). Give geoid or lat and lon.",
            parameters=_schema(
                {"geoid": _STRING, "lat": _NUMBER, "lon": _NUMBER, "miles": _NUMBER}, ["miles"]
            ),
        ),
        types.FunctionDeclaration(
            name="stats_correlate",
            description="Pearson correlation of the two columns of one read-only SELECT, over "
            "every row whose two values are numbers.",
            parameters=_schema({"sql": _STRING}, ["sql"]),
        ),
    ]
)


class Answerer:
    """Answers one question at a time with the model and the tools."""

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        engine: WarehouseQueryEngine,
        tools: WarehouseTools,
        taxonomy_text: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._model = model
        self._engine = engine
        self._tools = tools
        self._taxonomy = taxonomy_text
        self._clock = clock
        self._index_cache: str | None = None
        # Answer cache (Ketema: "Cache cache cache"): the warehouse is read-only for the life of
        # the process, so a successful answer to the same question and settings stays correct.
        self._answers: dict[tuple[object, ...], AskReply] = {}
        self._answers_lock = threading.Lock()

    def _index_json(self) -> str:
        """The table index for the instruction (Z-31), built once from the open engine."""
        if self._index_cache is None:
            self._index_cache = json.dumps(self._schema_payload({}), separators=(",", ":"))
        return self._index_cache

    def _schema_payload(self, args: Mapping[str, object]) -> list[dict[str, object]]:
        """The schema_describe payload: an index, or detail with the glossary paged (POST-TOOL-3).

        Raises:
            ToolArgumentError: ERRORS-TOOL-1, table_names or glossary_offset out of range.
            RejectedSqlError: ERRORS-SQL-1, an unknown table name (from the engine).
        """
        raw = args.get("table_names")
        offset_arg = args.get("glossary_offset")
        if raw is None:
            if offset_arg is not None:
                raise ToolArgumentError(
                    "ERRORS-TOOL-1 violation: glossary_offset needs table_names"
                )
            return [
                {
                    "table_name": d.table_name,
                    "dataset_id": d.dataset_id,
                    "grain": d.grain,
                    "as_of": d.as_of,
                    "column_count": len(d.columns),
                    "glossary_term_count": len(d.glossary_terms),
                }
                for d in self._engine.describe_schema()
            ]
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_DESCRIBE_TABLES:
            raise ToolArgumentError(
                f"ERRORS-TOOL-1 violation: table_names must list 1 to {MAX_DESCRIBE_TABLES} tables"
            )
        offset = 0 if offset_arg is None else offset_arg
        if (
            isinstance(offset, bool)
            or not isinstance(offset, int | float)
            or offset < 0
            or offset != int(offset)
        ):
            raise ToolArgumentError(
                f"ERRORS-TOOL-1 violation: glossary_offset {offset!r} is not a non-negative integer"
            )
        start = int(offset)
        end = start + GLOSSARY_PAGE_TERMS
        return [
            {
                "table_name": d.table_name,
                "dataset_id": d.dataset_id,
                "columns": list(d.columns),
                "grain": d.grain,
                "join_keys": list(d.join_keys),
                "as_of": d.as_of,
                "applied_filter": d.applied_filter,
                "glossary_terms": [list(t) for t in d.glossary_terms[start:end]],
                "glossary_term_count": len(d.glossary_terms),
                "glossary_next_offset": end if end < len(d.glossary_terms) else None,
            }
            for d in self._engine.describe_schema(table_names=tuple(str(n) for n in raw))
        ]

    def _run(self, name: str, args: Mapping[str, object]) -> tuple[object, SqlQueryResult | None]:
        """Run one tool call; return its payload for the model and its result for the reply."""
        if name == "schema_describe":
            return self._schema_payload(args), None
        if name == "sql_query":
            limit = args.get("row_limit")
            result = self._engine.execute_sql(
                str(args.get("sql", "")),
                **({"row_limit": int(limit)} if isinstance(limit, int | float) else {}),
            )
            return _result_payload(result), result
        if name == "sites_near":
            miles = args.get("miles")
            lat, lon = args.get("lat"), args.get("lon")
            result = self._tools.sites_near(
                geoid=str(args["geoid"]) if args.get("geoid") is not None else None,
                lat=float(lat) if isinstance(lat, int | float) else None,
                lon=float(lon) if isinstance(lon, int | float) else None,
                miles=float(miles) if isinstance(miles, int | float) else math.nan,
            )
            return _result_payload(result), result
        if name == "stats_correlate":
            result = self._tools.stats_correlate(str(args.get("sql", "")))
            return {**_result_payload(result), "caveats": list(CORRELATION_CAVEATS)}, result
        raise ToolArgumentError(f"ERRORS-TOOL-1 violation: unknown tool {name!r}")

    def _tool_turn(
        self,
        calls: list[types.FunctionCall],
        payloads: list[object],
        results: list[SqlQueryResult],
    ) -> types.Content:
        """Run each call; a refused call goes back to the model as an error (ERRORS-TOOL-1)."""
        parts = []
        for call in calls:
            name = call.name or ""
            try:
                payload, result = self._run(name, call.args or {})
            except (QueryServiceError, ToolArgumentError, ValueError) as exc:
                parts.append(
                    types.Part.from_function_response(name=name, response={"error": str(exc)})
                )
                continue
            payloads.append(payload)
            if result is not None:
                results.append(result)
            parts.append(
                types.Part.from_function_response(
                    name=name, response={"result": json.loads(json.dumps(payload))}
                )
            )
        return types.Content(role="user", parts=parts)

    @staticmethod
    def cache_key(request: AskRequest) -> tuple[object, ...]:
        """The question, case and spacing folded, with the settings it was answered under."""
        t = request.thresholds
        question = " ".join(request.question.lower().split()).rstrip("?.! ")
        return (question, t.reach_miles, t.poverty, t.no_vehicle, t.sba_rate_per_1000)

    def answer(self, request: AskRequest) -> AskReply:
        """A cached answer for the same question and settings, or a fresh one (then cached)."""
        key = self.cache_key(request)
        with self._answers_lock:
            hit = self._answers.get(key)
        if hit is not None:
            return hit
        reply = self._answer_fresh(request)
        with self._answers_lock:
            self._answers[key] = reply
        return reply

    def _answer_fresh(self, request: AskRequest) -> AskReply:  # noqa: PLR0912, PLR0915 - one loop
        """Answer one question under its thresholds.

        Raises:
            ModelUnavailableError: ERRORS-ASK-2, Vertex AI failed or the answer ran out of time
                or rounds.
            AnswerNotGroundedError: ERRORS-ASK-3, an ungrounded number survived one correction.
        """
        start = self._clock()
        instruction = system_instruction(self._taxonomy, request.thresholds, self._index_json())
        config = types.GenerateContentConfig(
            system_instruction=instruction,
            tools=[TOOL_DECLARATIONS],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        )
        # Z-31: the last allowed model call answers from the results it has (POST-ANS-4).
        final_config = types.GenerateContentConfig(
            system_instruction=instruction,
            tools=[TOOL_DECLARATIONS],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.NONE
                )
            ),
        )
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=request.question)])
        ]
        allowed = (request.question, settings_text(request.thresholds))
        payloads: list[object] = []
        results: list[SqlQueryResult] = []
        requests_made = 0
        corrected = False
        prompted = False
        while True:
            if self._clock() - start > ANSWER_DEADLINE_SECONDS:
                raise ModelUnavailableError(
                    f"ERRORS-ASK-2 violation: no answer within {ANSWER_DEADLINE_SECONDS} s"
                )
            final = requests_made >= MAX_TOOL_ROUNDS - 1
            if final and not prompted:
                prompted = True
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=FINAL_ANSWER_PROMPT)])
                )
            response = None
            for attempt in range(CALL_RETRIES + 1):
                try:
                    response = self._client.models.generate_content(
                        model=self._model,
                        contents=contents,
                        config=final_config if final else config,
                    )
                    break
                except (errors.APIError, httpx2.HTTPError) as exc:
                    if attempt == CALL_RETRIES:
                        raise ModelUnavailableError(
                            f"ERRORS-ASK-2 violation: Vertex AI failed: {exc}"
                        ) from exc
                    LOG.warning("Vertex call failed, retrying once: %s", exc)
            if response is None:
                raise ModelUnavailableError("ERRORS-ASK-2 violation: Vertex AI gave no reply")
            requests_made += 1
            calls = response.function_calls or []
            if calls:
                if final:
                    raise ModelUnavailableError(
                        "ERRORS-ASK-2 violation: the model gave no final answer"
                    )
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)
                contents.append(self._tool_turn(calls, payloads, results))
                continue
            text = (response.text or "").strip()
            if not text:
                raise ModelUnavailableError("ERRORS-ASK-2 violation: the model returned no answer")
            bad = ungrounded_numbers(text, payloads, allowed)
            if bad:
                if corrected:
                    raise AnswerNotGroundedError(
                        f"ERRORS-ASK-3 violation: numbers {list(bad)} came from no tool result"
                    )
                corrected = True
                if response.candidates and response.candidates[0].content:
                    contents.append(response.candidates[0].content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=CORRECTION_TEMPLATE.format(numbers=", ".join(bad)))],
                    )
                )
                continue
            done = tuple(results)
            return AskReply(
                answer=text,
                model=self._model,
                results=done,
                tracts=reply_tracts(text, done, self._tools.known_geoids),
                applied=request.thresholds,
            )
