"""The Ingest command: build the warehouse once from the registered sources (SLICE-3 batch 7).

Specification: contracts/warehouse_contract.py, CONTRACT_INGEST (POST-INGEST-1 to 7, POST-GLOSS-3,
ERRORS-GLOSS-2, FORBIDDEN-INGEST-1, ERRORS-INGEST-1), POST-BASE-1 and SEQ-5. Requirements:
REQ-25 to REQ-30, REQ-48, REQ-51, REQ-53, REQ-54. It composes the contracted readers, scope,
state filter, glossary builder, archive members, writer and data adapter. Runtime declarations are
independent of the contract module; tests bridge the two (CL11-F).

Run: WAREHOUSE_LOCATION=<empty directory> python -m src.warehouse.ingest --workers N
"""

import argparse
import hashlib
import json
import logging
import multiprocessing
import os
import re
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import IO, Final

import duckdb

from . import adapter, documents, office, reader, structured
from .archive import archive_members, member_source
from .glossary import DictionaryTableSpec, build_glossary_entries
from .provenance import NOT_RECORDED, sha256_file
from .registry import RegistryEntry, load_not_sources, load_registry
from .retained import CACHE_DIR, CACHE_PREFIX, MANIFEST_FILE, candidate_sources, retained_sources
from .scope import decide_scope, make_source_file
from .state_filter import (
    FILTER_NONE,
    GEO_ID_COLUMN,
    GEO_ID_TARGET_PATTERN,
    STATE_COLUMNS,
    TARGET_STATE_VALUES,
)
from .writer import WarehouseWriter

REGISTRY_FILE: Final = "data/warehouse/source_registry.toml"
MEMBER_SEPARATOR: Final = "!"
DELIMITED_READS: Final[Mapping[str, tuple[str | None, bool]]] = {
    "csv": (None, True),
    "tsv": ("\t", True),
    "dat": (None, True),
    "pl": ("|", False),
}
SHEET_FORMATS: Final = frozenset({"xlsx", "xls"})
JSON_FORMATS: Final = frozenset({"json"})
GEO_FORMATS: Final = frozenset({"geojson", "shapefile"})
PAGE_FORMATS: Final = frozenset({"pdf", "text"})
SLIDE_FORMATS: Final = frozenset({"pptx"})
RAW_COLUMN_PREFIX: Final = "c"
FILE_LOADED: Final = "loaded"
FILE_EXCLUDED: Final = "excluded"
FILE_NOT_A_SOURCE: Final = "not a source"
LOG: Final = logging.getLogger("ingest")


class IngestError(Exception):
    """ERRORS-INGEST-1: the warehouse cannot be built as specified; nothing is final."""


class GlossaryDeclarationError(Exception):
    """ERRORS-GLOSS-2: a [[glossary]] declaration is incomplete or names no registered source."""


@dataclass(frozen=True, slots=True)
class GlossaryDeclaration:
    """A registry [[glossary]] entry."""

    path: str
    part: str | None
    term: str
    definition: str


@dataclass(frozen=True, slots=True)
class Unit:
    """One scope unit: a non-archive file, or one member of an archive."""

    key: str
    entry: RegistryEntry
    path: Path  # the file, or the archive for a member
    member: str | None
    file_format: str
    reference_end: str | None
    sha256: str


@dataclass
class Part:
    """What a worker read from one unit: a staged table or document pages."""

    label: str | None
    staged: str | None = None
    columns: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    rows_in_source: int = 0
    rows_loaded: int = 0
    applied_filter: str = FILTER_NONE
    pages: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class UnitResult:
    """A worker's result for one unit."""

    key: str
    parts: list[Part]
    rejected: list[tuple[int, str, str]]


def source_path(repo_root: Path, key: str) -> Path:
    """The local file of a registry key ('cache:...' or 'repo:...')."""
    prefix, _, rel = key.partition(":")
    return repo_root / CACHE_DIR / rel if f"{prefix}:" == CACHE_PREFIX else repo_root / rel


def _snake(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def table_name(ds: str, path: str, member: str | None, part: str | None) -> str:
    """'<ds>_<file stem>[_<member stem>][_<part>]' in snake case (POST-INGEST-2)."""
    stem = PurePosixPath(path.split(":", 1)[-1]).stem
    pieces = [ds, stem, PurePosixPath(member).stem if member else "", part or ""]
    name = "_".join(p for p in (_snake(x) for x in pieces) if p)
    return name if name and not name[0].isdigit() else f"t_{name}"


def unique_names(names: Sequence[str]) -> list[str]:
    """Number repeats '<name>_2', '<name>_3', ..., skipping names already taken."""
    taken: set[str] = set()
    counts: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        counts[name] = counts.get(name, 0) + 1
        candidate = name if counts[name] == 1 else f"{name}_{counts[name]}"
        while candidate in taken:
            counts[name] += 1
            candidate = f"{name}_{counts[name]}"
        taken.add(candidate)
        out.append(candidate)
    return out


def load_glossary_declarations(
    registry: Mapping[str, object], entries: Sequence[RegistryEntry]
) -> tuple[GlossaryDeclaration, ...]:
    """Validate the registry's [[glossary]] array (ERRORS-GLOSS-2)."""
    paths = {e.path for e in entries}
    raw_list = registry.get("glossary", []) or []
    if not isinstance(raw_list, list):
        raise GlossaryDeclarationError("ERRORS-GLOSS-2 violation: [[glossary]] is not an array")
    out: list[GlossaryDeclaration] = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            raise GlossaryDeclarationError(f"ERRORS-GLOSS-2 violation: {raw!r} is not a table")
        path, part = raw.get("path"), raw.get("part")
        term, definition = raw.get("term"), raw.get("definition")
        if not isinstance(path, str) or path not in paths:
            raise GlossaryDeclarationError(
                f"ERRORS-GLOSS-2 violation: glossary path {path!r} is not a registered source"
            )
        for key, value in (("term", term), ("definition", definition)):
            if not isinstance(value, str) or not value.strip():
                raise GlossaryDeclarationError(
                    f"ERRORS-GLOSS-2 violation: glossary entry for {path!r} has no {key}"
                )
        if part is not None and (not isinstance(part, str) or not part.strip()):
            raise GlossaryDeclarationError(
                f"ERRORS-GLOSS-2 violation: glossary entry for {path!r} has an empty part"
            )
        out.append(GlossaryDeclaration(path, part, str(term).strip(), str(definition).strip()))
    return tuple(out)


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _state_filter(rel: duckdb.DuckDBPyRelation) -> tuple[duckdb.DuckDBPyRelation, str]:
    """The contracted state filter as a DuckDB predicate, so large files never leave DuckDB."""
    state = next((c for c in STATE_COLUMNS if c in rel.columns), None)
    if state is not None:
        values = ", ".join(_literal(v) for v in sorted(TARGET_STATE_VALUES))
        return rel.filter(f"{_quote(state)} IN ({values})"), f'state field "{state}" in FL, NY, UT'
    if GEO_ID_COLUMN in rel.columns:
        pattern = _literal(GEO_ID_TARGET_PATTERN.pattern)
        predicate = f"regexp_matches(CAST({_quote(GEO_ID_COLUMN)} AS VARCHAR), {pattern})"
        return (
            rel.filter(predicate),
            "GEO_ID national row or state/county/tract in FL (12), NY (36), UT (49)",
        )
    return rel, FILTER_NONE


def _count(rel: duckdb.DuckDBPyRelation) -> int:
    return int(rel.aggregate("count(*)").fetchall()[0][0])


def _stage(
    rel: duckdb.DuckDBPyRelation, staging: Path, label: str | None, labels: list[str]
) -> Part:
    kept, applied = _state_filter(rel)
    target = Path(tempfile.mkstemp(suffix=".parquet", dir=staging)[1])
    kept.write_parquet(str(target))
    staged = duckdb.connect().read_parquet(str(target))
    return Part(
        label=label,
        staged=str(target),
        columns=list(rel.columns),
        types=[str(t) for t in staged.types],
        labels=labels or [""] * len(rel.columns),
        rows_in_source=_count(rel),
        rows_loaded=_count(staged),
        applied_filter=applied,
    )


def _text_table(
    con: duckdb.DuckDBPyConnection, columns: Sequence[str], rows: Sequence[Sequence[str | None]]
) -> duckdb.DuckDBPyRelation:
    name = f"t_{os.getpid()}_{id(rows)}"
    con.execute(f"CREATE TEMP TABLE {name} ({', '.join(f'{_quote(c)} VARCHAR' for c in columns)})")
    if rows:
        width = len(columns)
        placeholders = ", ".join("?" for _ in columns)
        # the table name is generated here; values are bound parameters
        con.executemany(
            f"INSERT INTO {name} VALUES ({placeholders})",  # noqa: S608
            [tuple(r) + (None,) * (width - len(r)) for r in rows],
        )
    return con.table(name)


if sys.platform == "win32":
    import msvcrt

    def _lock(lock: IO[str]) -> None:
        # LK_LOCK gives up after about 10 seconds; a conversion can take longer, so try again.
        while True:
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            except OSError:
                continue
            return

    def _unlock(lock: IO[str]) -> None:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(lock: IO[str]) -> None:
        fcntl.flock(lock, fcntl.LOCK_EX)

    def _unlock(lock: IO[str]) -> None:
        fcntl.flock(lock, fcntl.LOCK_UN)


def _office[T](staging: Path, read: Callable[[Path], T], source: Path) -> T:
    """Run one LibreOffice conversion at a time across worker processes.

    Concurrent soffice runs share one user profile and fail; a file lock in the staging
    directory serializes only the conversions, so other formats still read in parallel.
    """
    with (staging / "office.lock").open("w") as lock:
        _lock(lock)
        try:
            return read(source)
        finally:
            _unlock(lock)


def read_unit(args: tuple[str, str, str | None, str, str]) -> UnitResult:
    """Worker: read one unit into staged Parquet tables or document pages (POST-INGEST-2, 3)."""
    key, path_text, member, file_format, staging_text = args
    staging = Path(staging_text)
    con = duckdb.connect()
    with tempfile.TemporaryDirectory(dir=staging) as work:
        path = Path(path_text)
        source = path
        if member is not None:
            source_text = member_source(path, member, Path(work))
            source = Path(source_text)
        parts: list[Part] = []
        rejected: list[tuple[int, str, str]] = []
        if file_format in DELIMITED_READS:
            delimiter, header = DELIMITED_READS[file_format]
            rel, _, bad = reader.read_delimited(con, source, delimiter=delimiter, header=header)
            rejected = [(r.line, r.error_type, r.raw) for r in bad]
            parts.append(_stage(rel, staging, None, []))
        elif file_format in SHEET_FORMATS:
            for sheet in _office(staging, office.read_sheets, source):
                width = max((len(r) for r in sheet.rows), default=0)
                if width == 0:
                    continue
                columns = [f"{RAW_COLUMN_PREFIX}{i}" for i in range(1, width + 1)]
                first = next((r for r in sheet.rows if any(c not in (None, "") for c in r)), ())
                labels = [("" if c is None else str(c)) for c in first] + [""] * (
                    width - len(first)
                )
                rel = _text_table(con, columns, sheet.rows)
                parts.append(_stage(rel, staging, sheet.sheet, labels))
        elif file_format in JSON_FORMATS:
            for table in structured.read_json_tables(source):
                if not table.columns:
                    continue
                rel = _text_table(con, list(table.columns), table.rows)
                label = table.key or None
                parts.append(_stage(rel, staging, label, []))
        elif file_format in GEO_FORMATS:
            geo_source = (
                str(source)
                if member is None or not member.lower().endswith(".shp")
                else source_text
            )
            parts.append(_stage(structured.read_geo(con, geo_source), staging, None, []))
        elif file_format in PAGE_FORMATS:
            pages = (
                documents.read_pdf_pages(source)
                if file_format == "pdf"
                else documents.read_text_pages(source)[0]
            )
            parts.append(Part(label=None, pages=[(p.page, p.text) for p in pages]))
        elif file_format in SLIDE_FORMATS:
            slides = _office(staging, office.read_slides, source)
            parts.append(Part(label=None, pages=[(p.page, p.text) for p in slides]))
        else:
            raise IngestError(
                f"ERRORS-INGEST-1 violation: {key!r} has format {file_format!r}, "
                "which has no reader"
            )
    return UnitResult(key, parts, rejected)


def _units(repo_root: Path, entries: Sequence[RegistryEntry], sources: Sequence[str]) -> list[Unit]:
    by_path = {e.path: e for e in entries}
    out: list[Unit] = []
    for entry in entries:  # registry order
        if entry.path not in sources:
            continue
        path = source_path(repo_root, entry.path)
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for m in archive_members(path, entry):
                    digest = hashlib.sha256(archive.read(m.name)).hexdigest()
                    out.append(
                        Unit(
                            f"{entry.path}{MEMBER_SEPARATOR}{m.name}",
                            entry,
                            path,
                            m.name,
                            m.file_format,
                            m.reference_end,
                            digest,
                        )
                    )
        else:
            out.append(
                Unit(
                    entry.path,
                    by_path[entry.path],
                    path,
                    None,
                    entry.file_format,
                    entry.reference_end,
                    sha256_file(path),
                )
            )
    return out


def _manifest_origins(repo_root: Path) -> dict[str, tuple[str, str]]:
    origins: dict[str, tuple[str, str]] = {}
    manifest = repo_root / MANIFEST_FILE
    if not manifest.is_file():
        return origins
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        rel = record.get("path")
        if record.get("status") != "ok" or not isinstance(rel, str) or not rel:
            continue
        url, ts = record.get("url"), record.get("ts")
        origins[f"{CACHE_PREFIX}{PurePosixPath(rel)}"] = (
            url if isinstance(url, str) and url.strip() else NOT_RECORDED,
            ts if isinstance(ts, str) and ts.strip() else NOT_RECORDED,
        )
    return origins


def _relation(
    con: duckdb.DuckDBPyConnection,
    spec: Sequence[tuple[str, str]],
    rows: Sequence[Sequence[object]],
) -> duckdb.DuckDBPyRelation:
    name = f"b_{id(rows)}"
    con.execute(f"CREATE TEMP TABLE {name} ({', '.join(f'{_quote(c)} {t}' for c, t in spec)})")
    if rows:
        placeholders = ", ".join("?" for _ in spec)
        # the table name is generated here; values are bound parameters
        con.executemany(f"INSERT INTO {name} VALUES ({placeholders})", [tuple(r) for r in rows])  # noqa: S608
    return con.table(name)


def run(repo_root: Path, env: Mapping[str, str], workers: int) -> dict[str, int]:  # noqa: PLR0912, PLR0915 - one ordered build
    """Build the warehouse at WAREHOUSE_LOCATION and return counts (POST-INGEST-1 to 7).

    Raises:
        IngestError: ERRORS-INGEST-1.
        GlossaryDeclarationError: ERRORS-GLOSS-2, before any reading.
    """
    location = adapter.warehouse_location(env)
    root = Path(location.root)
    if (root / adapter.WAREHOUSE_DB_FILE).exists():
        raise IngestError(
            f"ERRORS-INGEST-1 violation: a warehouse already exists at {location.root!r}; it is "
            "built once (REQ-31)"
        )
    registry_path = repo_root / REGISTRY_FILE
    raw_registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    entries = load_registry(registry_path)
    declarations = load_glossary_declarations(raw_registry, entries)
    not_sources = load_not_sources(registry_path, entries)
    try:
        retained = retained_sources(candidate_sources(repo_root), entries, not_sources)
    except Exception as exc:
        raise IngestError(f"ERRORS-INGEST-1 violation: {exc}") from exc
    units = _units(repo_root, entries, retained.sources)
    decisions = decide_scope(
        [
            make_source_file(
                path=u.key,
                sha256=u.sha256,
                file_format=u.file_format,
                reference_end=u.reference_end,
                is_base_geography=u.entry.is_base_geography,
                release_id=u.entry.release_id,
            )
            for u in units
        ]
    )
    loaded = [u for u, d in zip(units, decisions, strict=True) if d.decision == "load"]

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ingest-") as staging:
        jobs = [(u.key, str(u.path), u.member, u.file_format, staging) for u in loaded]
        if workers > 1:
            context = multiprocessing.get_context("spawn")
            with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
                results = list(pool.map(read_unit, jobs))
        else:
            results = [read_unit(job) for job in jobs]
        by_key = {r.key: r for r in results}

        # Names: registry order, then member, part and reading order (POST-INGEST-2).
        planned: list[tuple[Unit, Part]] = [
            (u, p) for u in loaded for p in by_key[u.key].parts if p.staged is not None
        ]
        names = unique_names(
            [table_name(u.entry.ds, u.entry.path, u.member, p.label) for u, p in planned]
        )
        named = sorted(zip(names, planned, strict=True), key=lambda x: x[0])

        con = duckdb.connect()
        writer_location = location
        writer = WarehouseWriter(writer_location)
        origins = _manifest_origins(repo_root)
        catalog, sources, columns, glossary_specs = [], [], [], []
        table_of: dict[tuple[str, str | None], tuple[str, Part, Unit]] = {}
        for name, (unit, part) in named:
            relative = writer.write_table(name, con.read_parquet(part.staged or ""))
            catalog.append((name, relative, "ok", unit.key, unit.entry.ds))
            archive_key = unit.key.split(MEMBER_SEPARATOR, 1)[0]
            url, ts = origins.get(archive_key, (NOT_RECORDED, NOT_RECORDED))
            file_sha = unit.sha256 if unit.member is None else sha256_file(unit.path)
            sources.append(
                (
                    name,
                    unit.entry.ds,
                    unit.key,
                    url,
                    ts,
                    file_sha,
                    unit.entry.publisher,
                    unit.entry.license,
                    unit.entry.as_of,
                    part.applied_filter,
                    part.rows_in_source,
                    part.rows_loaded,
                )
            )
            for i, (col, typ, label) in enumerate(
                zip(part.columns, part.types, part.labels, strict=True), 1
            ):
                columns.append((name, col, i, typ, label))
            table_of[(unit.key, part.label)] = (name, part, unit)

        for decl in declarations:
            hit = table_of.get((decl.path, decl.part))
            if hit is None:
                raise IngestError(
                    f"ERRORS-INGEST-1 violation: glossary source {decl.path!r} part {decl.part!r} "
                    "was not loaded as a table"
                )
            name, part, unit = hit
            staged = con.read_parquet(part.staged or "")
            raw_rows = staged.fetchall()
            if any(part.labels):
                header = next(
                    i for i, r in enumerate(raw_rows) if any(c not in (None, "") for c in r)
                )
                keys = part.labels
                body = raw_rows[header + 1 :]
            else:
                keys = part.columns
                body = raw_rows
            rows = [
                {k: ("" if v is None else str(v)) for k, v in zip(keys, r, strict=True)}
                for r in body
            ]
            glossary_specs.append(
                DictionaryTableSpec(name, unit.entry.ds, decl.term, decl.definition, tuple(rows))
            )
        glossary = [
            (g.source_table, g.dataset_id, g.term, g.definition)
            for g in build_glossary_entries(glossary_specs)
        ]

        log_rows: list[tuple[str, str, str, str]] = []
        documents_rows: list[tuple[str, int, str]] = []
        for unit in loaded:
            result = by_key[unit.key]
            for line, kind, raw in result.rejected:
                LOG.warning("set aside %s line %d: %s: %s", unit.key, line, kind, raw)
                log_rows.append((unit.key, f"line {line}", kind, raw))
            for part in result.parts:
                documents_rows.extend((unit.key, page, text) for page, text in part.pages)

        files: list[tuple[str, str, str, str, str, str]] = []
        set_aside = {u.key: len(by_key[u.key].rejected) for u in loaded}
        members_of: dict[str, int] = {}
        for unit, decision in zip(units, decisions, strict=True):
            if unit.member is not None:
                members_of[unit.entry.path] = members_of.get(unit.entry.path, 0) + 1
            if decision.decision == "load":
                n = set_aside[unit.key]
                reason = f"{n} rows set aside" if n else ""
                files.append(
                    (unit.key, unit.entry.ds, unit.file_format, unit.sha256, FILE_LOADED, reason)
                )
            else:
                files.append(
                    (
                        unit.key,
                        unit.entry.ds,
                        unit.file_format,
                        unit.sha256,
                        FILE_EXCLUDED,
                        str(decision.reason),
                    )
                )
        for path, count in members_of.items():
            entry = next(e for e in entries if e.path == path)
            zpath = source_path(repo_root, path)
            files.append(
                (
                    path,
                    entry.ds,
                    entry.file_format,
                    sha256_file(zpath),
                    FILE_LOADED,
                    f"{count} members",
                )
            )
        for ns in retained.not_sources:
            files.append(
                (
                    ns.path,
                    NOT_RECORDED,
                    NOT_RECORDED,
                    sha256_file(source_path(repo_root, ns.path)),
                    FILE_NOT_A_SOURCE,
                    ns.reason,
                )
            )

        text = "VARCHAR"
        base = {
            "files": _relation(
                con,
                [(c, text) for c in ("path", "ds", "file_format", "sha256", "status", "reason")],
                files,
            ),
            "catalog": _relation(
                con,
                [
                    (c, text)
                    for c in ("table_name", "parquet", "status", "source_file", "dataset_id")
                ],
                catalog,
            ),
            "sources": _relation(
                con,
                [
                    (c, text)
                    for c in (
                        "table_name",
                        "dataset_id",
                        "source_file",
                        "origin_url",
                        "retrieved_at",
                        "sha256",
                        "publisher",
                        "license",
                        "as_of",
                        "applied_filter",
                    )
                ]
                + [("rows_in_source", "BIGINT"), ("rows_loaded", "BIGINT")],
                sources,
            ),
            "columns": _relation(
                con,
                [
                    ("table_name", text),
                    ("column_name", text),
                    ("ordinal", "INTEGER"),
                    ("column_type", text),
                    ("label", text),
                ],
                columns,
            ),
            "documents": _relation(
                con, [("source_file", text), ("page", "INTEGER"), ("text", text)], documents_rows
            ),
            "glossary": _relation(
                con,
                [(c, text) for c in ("source_table", "dataset_id", "term", "definition")],
                glossary,
            ),
            "ingest_log": _relation(
                con, [(c, text) for c in ("source_file", "location", "kind", "detail")], log_rows
            ),
        }
        writer.finalize(base)  # SEQ-5: base tables after every data table
    counts = {"tables": len(catalog), "documents": len(documents_rows), "set_aside": len(log_rows)}
    LOG.info("warehouse built at %s: %s", location.root, counts)
    return counts


def main(argv: Sequence[str] | None = None) -> int:
    """Command line: build the warehouse at WAREHOUSE_LOCATION; exit 1 naming any failure."""
    parser = argparse.ArgumentParser(prog="python -m src.warehouse.ingest")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    try:
        run(args.repo, os.environ, max(1, args.workers))
    except (IngestError, GlossaryDeclarationError, adapter.WarehouseLocationError) as exc:
        LOG.error("%s", exc)  # noqa: TRY400 - the message names the clause; no traceback needed
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    sys.exit(main())
