"""Warehouse contract, SLICE-3.

Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 13, REQ-25 to REQ-31).

Domain: the Ingest (retained source files in, warehouse tables out). The QueryService has its own
contract (SLICE-4).

Batches:
- Batch 1: which files the warehouse loads and which it excludes, with the reason (REQ-25, REQ-26).
- Batch 2: the state filter for Florida, New York and Utah (REQ-27) and the source and loaded row
  counts it records (REQ-29).
- Batch 3: table provenance records with "not recorded" for absent fields (REQ-29) and local-disk
  only / unaltered retained sources (REQ-28).
- Batch 4: glossary table from loaded data dictionaries and lookup files (REQ-30), provenance
  table write sequencing (SEQ-5, REQ-29), and canonical GCS bucket storage in <gcp-project> (REQ-31).
- Batch 5: the data adapter's single configured warehouse location and table locations
  relative to it (REQ-47, REQ-48).
- Batch 6a: the warehouse writer: tables written through the adapter, relative catalog
  locations, base tables only and no views in warehouse.duckdb (REQ-48, REQ-51).
- Batch 6b: the committed source registry (exact-path matching, reference end with its basis,
  "not recorded" for unstated facts) and fail-fast reading (REQ-25, REQ-26, REQ-29).
- Batch 6c: the retained-source rule: candidate files on disk, every candidate registered as a
  source or listed as not a source with a reason, no stale entries, and cache-relative paths in
  the download manifest (REQ-25, REQ-26, REQ-48).
- Batch 6c-ii: document reading: every PDF page and every text file becomes numbered page text,
  read with the tools already on the build machine and never altered (REQ-25, REQ-28).

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Any, Literal

# --- 1. Importable constants (specification values) --------------------------------------

SCOPE_START = date(2024, 1, 1)  # REQ-25: a reference period reaches this date or later
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DECISION_LOAD = "load"
DECISION_EXCLUDE = "exclude"
DECISIONS = (DECISION_LOAD, DECISION_EXCLUDE)

EXCLUDE_TIME_SCOPE = "time_scope"
EXCLUDE_DUPLICATE_CONTENT = "duplicate_content"
EXCLUDE_DUPLICATE_FORMAT = "duplicate_format"
# REQ-26: the only reasons, in precedence order (the first that applies is the recorded reason).
EXCLUSION_REASONS = (EXCLUDE_TIME_SCOPE, EXCLUDE_DUPLICATE_CONTENT, EXCLUDE_DUPLICATE_FORMAT)

# Same release in several formats: the lowest rank is loaded, the others are duplicate_format.

# Batch 2: state filter (REQ-27, REQ-29).
# Priority order of state columns across the retained sources; the first present column governs.
STATE_COLUMNS: tuple[str, ...] = (
    "BorrState",
    "BUSINESS_STATE",
    "StateAbbr",
    "STATEABBRV",
    "EST_ST",
    "State",
)
TARGET_STATE_VALUES: frozenset[str] = frozenset(
    {"FL", "Florida", "12", "NY", "New York", "36", "UT", "Utah", "49"}
)
GEO_ID_COLUMN = "GEO_ID"
# ACS GEO_ID: national row (0100000US...) or state/county/tract in FL (12), NY (36), UT (49).
GEO_ID_TARGET_PATTERN = re.compile(r"^(0100000US.*|.*US(12|36|49).*)")
FILTER_NONE = "none (no state field)"
# Content formats; the lowest rank of a release is loaded (POST-SCOPE-5). Batch 6b extended the
# set to every format among the retained sources without changing the earlier ranks.
FORMAT_RANK: Mapping[str, int] = {
    "csv": 0,
    "tsv": 0,
    "dat": 0,
    "pl": 0,
    "xlsx": 1,
    "xls": 1,
    "sas": 2,
    "json": 3,
    "geojson": 3,
    "shapefile": 3,
    "pdf": 4,
    "text": 4,
    "pptx": 4,
}

# Batch 3: table provenance and local-disk-only sources (REQ-28, REQ-29).
NOT_RECORDED = "not recorded"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PROVENANCE_TEXT_FIELDS: tuple[str, ...] = (
    "origin_url",
    "retrieved_at",
    "publisher",
    "license",
    "as_of",
)

# Batch 4: glossary table, provenance write sequencing (SEQ-5), and canonical bucket (REQ-30, 31).
GLOSSARY_COLUMNS: tuple[str, ...] = ("source_table", "dataset_id", "term", "definition")
PROVENANCE_TABLES: tuple[str, ...] = ("files", "catalog", "sources")
WAREHOUSE_GCP_PROJECT = "<gcp-project>"
WAREHOUSE_GCS_BUCKET = "<warehouse-bucket>"
WAREHOUSE_GCS_URI = f"gs://{WAREHOUSE_GCS_BUCKET}"

# Batch 5: data adapter (REQ-47, REQ-48).
WAREHOUSE_LOCATION_ENV = "WAREHOUSE_LOCATION"  # the one configured warehouse location
WAREHOUSE_DB_FILE = "warehouse.duckdb"
PARQUET_DIR = "parquet"
TABLE_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")

# Batch 6a: warehouse writer (REQ-48, REQ-51). Base tables live inside warehouse.duckdb; every
# data table lives in its own Parquet file named by table_location().
BASE_TABLES: tuple[str, ...] = (
    "files",
    "catalog",
    "sources",
    "columns",
    "documents",
    "glossary",
    "ingest_log",  # batch 7: each row set aside while reading (REQ-54)
)
CATALOG_REQUIRED_COLUMNS: tuple[str, ...] = ("table_name", "parquet", "status")
# Batch 7 (Ingest command) and SLICE-4 reader: the columns of each base table, in order. The
# QueryService reads catalog, columns, sources and glossary by these names (POST-BASE-1).
BASE_TABLE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "files": ("path", "ds", "file_format", "sha256", "status", "reason"),
    "catalog": ("table_name", "parquet", "status", "source_file", "dataset_id"),
    "sources": (
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
        "rows_in_source",
        "rows_loaded",
    ),
    # label: a worksheet's first non-empty row, as suggested column names; "" otherwise (batch 7)
    "columns": ("table_name", "column_name", "ordinal", "column_type", "label"),
    "documents": ("source_file", "page", "text"),
    "glossary": ("source_table", "dataset_id", "term", "definition"),
    "ingest_log": ("source_file", "location", "kind", "detail"),
}

# Batch 6b: source registry and reading (REQ-25, REQ-26, REQ-29).
REGISTRY_FILE = "data/warehouse/source_registry.toml"  # relative to the repository root
READ_ENCODINGS: tuple[str, ...] = ("utf-8", "latin-1")  # tried in this order

# Batch 6c: retained-source rule (REQ-25, REQ-26, REQ-48).
MANIFEST_FILE = "data/cache/MANIFEST.jsonl"  # relative to the repository root
CACHE_DIR = "data/cache"
CANDIDATE_ROOTS: tuple[str, ...] = ("data", "docs")
EXCLUDED_DIRS: tuple[str, ...] = ("data/cache", "data/warehouse", "docs/mockups")
CACHE_PREFIX = "cache:"
REPO_PREFIX = "repo:"

# Batch 6c-ii: document reading (REQ-25, REQ-28). Poppler's tools, already on the build machine.
PDF_TEXT_COMMAND: tuple[str, ...] = ("pdftotext", "-layout", "-enc", "UTF-8")  # then <file> -
PDF_INFO_COMMAND: tuple[str, ...] = ("pdfinfo",)  # then <file>; its "Pages:" line is the count
PAGE_BREAK = "\f"  # pdftotext ends every page with a form feed
TEXT_PAGE = 1  # a text file is one page, numbered 1

# Batch 6c-iii: JSON and geographic files (REQ-25, REQ-28).
# JSON_ROOT_KEY names the table of a top-level array, or of the other top-level entries.
JSON_ROOT_KEY = ""
JSON_BLOB_COLUMN = "json"  # the one column of a file whose top level is neither object nor array
GEO_EXTENSION = "spatial"  # DuckDB's GDAL reader (ST_Read); loaded, never installed by the Ingest
GEO_ROW_ID_COLUMN = "OGC_FID"  # a row id GDAL adds; not in the source, so not loaded
GEO_GEOMETRY_COLUMN = "geom"

# Batch 6c-iv: spreadsheets and slide decks through LibreOffice (Q-1, Q-2, Q-3; REQ-25, REQ-28).
OFFICE_CONVERT_COMMAND: tuple[str, ...] = ("soffice", "--headless", "--norestore", "--convert-to")
SHEET_TARGET = "fods"  # flat OpenDocument spreadsheet: every cell carries its value type
SLIDES_TARGET = "pdf"  # a deck becomes a PDF, one page per slide, read by read_pdf_pages
NUMERIC_VALUE_TYPES: tuple[str, ...] = ("float", "percentage", "currency")

# Batch 6c-v: archive members (REQ-25, REQ-26, REQ-28).
# An unlisted member's format comes from its extension (lower case).
MEMBER_FORMAT_BY_EXTENSION: Mapping[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".dat": "dat",
    ".pl": "pl",
    ".txt": "text",
    ".md": "text",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".json": "json",
    ".geojson": "geojson",
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".shp": "shapefile",
    ".sas7bdat": "sas",
}
# Companion files of a shapefile <stem>.shp: <stem> plus one of these, or <stem>.shp...xml metadata.
SHAPEFILE_PART_EXTENSIONS: tuple[str, ...] = (".cpg", ".dbf", ".prj", ".shx", ".sbn", ".sbx")
VSIZIP_PREFIX = "/vsizip/"  # GDAL's path into an archive; shapefile members are read through it

# --- 2. Domain exceptions (every message names its clause) --------------------------------


class WarehouseContractError(Exception):
    """Base of every violation raised by this contract."""


class InvalidSourceFileError(WarehouseContractError):
    """ERRORS-SCOPE-1: a source file description is outside the contracted domain."""


class ScopeViolationError(WarehouseContractError):
    """POST-SCOPE-1..6, INV-SCOPE-1, INV-SCOPE-2 or FORBIDDEN-SCOPE-1: decisions disagree."""


class InvalidTableError(WarehouseContractError):
    """ERRORS-STATE-1: a table description is outside the contracted domain."""


class StateFilterViolationError(WarehouseContractError):
    """POST-STATE-1..4 or INV-STATE-1: the filtered rows or recorded counts disagree."""


class InvalidProvenanceInputError(WarehouseContractError):
    """ERRORS-PROV-1: a table provenance input is outside the contracted domain."""


class ProvenanceViolationError(WarehouseContractError):
    """POST-PROV-1..3, INV-PROV-1 or FORBIDDEN-PROV-1: provenance or source integrity violated."""


class InvalidGlossarySourceError(WarehouseContractError):
    """ERRORS-GLOSS-1: a dictionary/lookup source description is invalid."""


class GlossaryViolationError(WarehouseContractError):
    """POST-GLOSS-1..2, INV-GLOSS-1, FORBIDDEN-GLOSS-1 or SEQ-5: glossary or write order wrong."""


class WarehouseLocationError(WarehouseContractError):
    """ERRORS-ADAPT-1..3 or FORBIDDEN-ADAPT-1: a warehouse or table location is invalid."""


class WarehouseWriteError(WarehouseContractError):
    """ERRORS-WRITE-1 or POST-WRITE-1..2 / INV-WRITE-1: the written warehouse is wrong."""


class RegistryError(WarehouseContractError):
    """ERRORS-REG-1: a source registry entry is outside the contracted domain."""


class UnregisteredSourceError(RegistryError):
    """ERRORS-REG-2 / FORBIDDEN-REG-1: a retained file or archive member has no exact entry."""


class SourceReadError(WarehouseContractError):
    """ERRORS-READ-1: a retained source file cannot be read."""


class ManifestError(WarehouseContractError):
    """ERRORS-RET-1: a download manifest record does not name a cache-relative file."""


class ArchiveMemberError(WarehouseContractError):
    """ERRORS-ARCH-1..2: an archive member has no contracted format or cannot be opened."""


# --- 3. Immutable typed records ------------------------------------------------------------


@dataclass(frozen=True)
class Clause:
    verification: Literal["test", "execution", "tool"]
    text: str
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class SourceFile:
    """One retained source file as the scope decision sees it.

    reference_end: ISO date (YYYY-MM-DD) of the last day the data describes, or None when the
    sources do not state it.
    release_id: identifies one release published in several formats, or None.
    """

    path: str
    sha256: str
    file_format: str
    reference_end: str | None
    is_base_geography: bool
    release_id: str | None


@dataclass(frozen=True)
class ScopeDecision:
    path: str
    decision: str
    reason: str | None


@dataclass(frozen=True)
class StateFilterOutcome:
    """Batch 2 validated result of filtering one table's rows by state."""

    rows: tuple[Mapping[str, str], ...]
    rows_in_source: int
    rows_loaded: int
    applied_filter: str


@dataclass(frozen=True)
class TableProvenance:
    """Batch 3 validated provenance record for one warehouse table (REQ-29)."""

    table_name: str
    source_file: str
    origin_url: str
    retrieved_at: str
    sha256: str
    publisher: str
    license: str
    as_of: str
    applied_filter: str
    rows_in_source: int
    rows_loaded: int


@dataclass(frozen=True)
class GlossaryEntry:
    """Batch 4 validated glossary entry from a data dictionary or lookup table (REQ-30)."""

    source_table: str
    dataset_id: str
    term: str
    definition: str


@dataclass(frozen=True)
class DictionaryTableSpec:
    """Description of one loaded dictionary or lookup table to extract glossary rows from."""

    source_table: str
    dataset_id: str
    term_column: str
    definition_column: str
    rows: tuple[Mapping[str, str], ...]


@dataclass(frozen=True)
class WarehouseLocation:
    """Batch 5 validated warehouse location: an absolute, normalized POSIX directory path."""

    root: str


@dataclass(frozen=True)
class WrittenWarehouse:
    """Batch 6a observed shape of a written warehouse file (base tables, views, catalog)."""

    base_tables: tuple[str, ...]
    views: tuple[str, ...]
    catalog: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RegistryMember:
    """Batch 6b scope facts for one member of a series archive, matched by exact name."""

    name: str
    file_format: str
    reference_end: str | None
    reference_basis: str


@dataclass(frozen=True)
class RegistryEntry:
    """Batch 6b facts for one retained source file, matched by exact path."""

    path: str
    ds: str
    group: str
    file_format: str
    reference_end: str | None
    reference_basis: str
    is_base_geography: bool
    release_id: str | None
    publisher: str
    license: str
    as_of: str
    members: tuple[RegistryMember, ...]


@dataclass(frozen=True)
class NotASource:
    """Batch 6c: a candidate file the registry lists as not a source, with the reason."""

    path: str
    reason: str


@dataclass(frozen=True)
class RetainedSources:
    """Batch 6c: candidates split into registered sources and listed non-sources."""

    sources: tuple[str, ...]
    not_sources: tuple[NotASource, ...]


@dataclass(frozen=True)
class DocumentPage:
    """Batch 6c-ii: one page of a retained document, numbered from 1."""

    page: int
    text: str


@dataclass(frozen=True)
class RejectedRow:
    """Z-22: a delimited row the reader set aside, with its 1-based file line and raw text."""

    line: int
    error_type: str
    raw: str


@dataclass(frozen=True)
class JsonTable:
    """Batch 6c-iii: one table read from a JSON file; every cell is text or None."""

    key: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]


@dataclass(frozen=True)
class SheetTable:
    """Batch 6c-iv: one worksheet, its rows in order, every cell text or None."""

    sheet: str
    rows: tuple[tuple[str | None, ...], ...]


@dataclass(frozen=True)
class ArchiveMember:
    """Batch 6c-v: one source member of a retained archive, with its format and reference end."""

    name: str
    file_format: str
    reference_end: str | None


# --- 4. Callable validators ----------------------------------------------------------------


def validate_source_file(
    *,
    path: str,
    sha256: str,
    file_format: str,
    reference_end: str | None,
    is_base_geography: bool,
    release_id: str | None,
) -> SourceFile:
    """ERRORS-SCOPE-1 gate: build a SourceFile or raise InvalidSourceFileError."""
    if not path:
        raise InvalidSourceFileError("ERRORS-SCOPE-1 violation: path is empty")
    if not sha256:
        raise InvalidSourceFileError(f"ERRORS-SCOPE-1 violation: sha256 is empty for {path!r}")
    if file_format not in FORMAT_RANK:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: file_format {file_format!r} is not one of "
            f"{sorted(FORMAT_RANK)} for {path!r}"
        )
    if reference_end is not None:
        if not DATE_PATTERN.match(reference_end):
            raise InvalidSourceFileError(
                f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not YYYY-MM-DD "
                f"for {path!r}"
            )
        try:
            date.fromisoformat(reference_end)
        except ValueError as exc:
            raise InvalidSourceFileError(
                f"ERRORS-SCOPE-1 violation: reference_end {reference_end!r} is not a real date "
                f"for {path!r}"
            ) from exc
    if release_id is not None and not release_id:
        raise InvalidSourceFileError(
            f"ERRORS-SCOPE-1 violation: release_id is an empty string for {path!r}"
        )
    return SourceFile(path, sha256, file_format, reference_end, is_base_geography, release_id)


def expected_scope_decisions(files: Sequence[SourceFile]) -> tuple[ScopeDecision, ...]:
    """POST-SCOPE-1 to POST-SCOPE-6, INV-SCOPE-1, INV-SCOPE-2 oracle.

    Files are judged in (format rank, path) order so the result does not depend on input order;
    decisions are returned in input order. For each file, the first rule that applies wins:
    1. time_scope: not base geography, reference_end known, and before SCOPE_START.
    2. duplicate_content: the sha256 of an already loaded file.
    3. duplicate_format: the release_id of an already loaded file of another format.
    4. otherwise load.
    """
    order = sorted(
        range(len(files)), key=lambda i: (FORMAT_RANK[files[i].file_format], files[i].path)
    )
    loaded_hashes: set[str] = set()
    loaded_releases: dict[str, str] = {}
    decided: dict[int, ScopeDecision] = {}
    for i in order:
        f = files[i]
        out_of_time = (
            not f.is_base_geography
            and f.reference_end is not None
            and date.fromisoformat(f.reference_end) < SCOPE_START
        )
        same_release_other_format = (
            f.release_id is not None
            and f.release_id in loaded_releases
            and loaded_releases[f.release_id] != f.file_format
        )
        if out_of_time:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_TIME_SCOPE)
        elif f.sha256 in loaded_hashes:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_CONTENT)
        elif same_release_other_format:
            decided[i] = ScopeDecision(f.path, DECISION_EXCLUDE, EXCLUDE_DUPLICATE_FORMAT)
        else:
            decided[i] = ScopeDecision(f.path, DECISION_LOAD, None)
            loaded_hashes.add(f.sha256)
            if f.release_id is not None:
                loaded_releases.setdefault(f.release_id, f.file_format)
    return tuple(decided[i] for i in range(len(files)))


def validate_scope_decisions(
    files: Sequence[SourceFile], decisions: Sequence[ScopeDecision]
) -> None:
    """Raise ScopeViolationError naming the clause when decisions disagree with the oracle."""
    if len(decisions) != len(files):
        raise ScopeViolationError(
            f"INV-SCOPE-1 violation: {len(files)} files but {len(decisions)} decisions"
        )
    for f, d in zip(files, decisions, strict=True):
        if d.path != f.path:
            raise ScopeViolationError(
                f"INV-SCOPE-1 violation: decision for {d.path!r} sits where {f.path!r} belongs"
            )
        if d.decision not in DECISIONS:
            raise ScopeViolationError(
                f"FORBIDDEN-SCOPE-1 violation: {d.path!r} decision {d.decision!r} "
                f"is not one of {DECISIONS}"
            )
        if d.decision == DECISION_EXCLUDE and d.reason not in EXCLUSION_REASONS:
            raise ScopeViolationError(
                f"FORBIDDEN-SCOPE-1 violation: {d.path!r} excluded for {d.reason!r}, "
                f"not one of {EXCLUSION_REASONS}"
            )
        if d.decision == DECISION_LOAD and d.reason is not None:
            raise ScopeViolationError(
                f"FORBIDDEN-SCOPE-1 violation: {d.path!r} is loaded but carries reason {d.reason!r}"
            )
    for f, got, want in zip(files, decisions, expected_scope_decisions(files), strict=True):
        if got != want:
            raise ScopeViolationError(
                f"POST-SCOPE violation: {f.path!r} decided {got.decision}/{got.reason}, "
                f"the rule gives {want.decision}/{want.reason}"
            )


def validate_table_columns(columns: Sequence[str]) -> tuple[str, ...]:
    """ERRORS-STATE-1 gate: column names are non-empty and unique."""
    if not columns:
        raise InvalidTableError("ERRORS-STATE-1 violation: columns is empty")
    seen: set[str] = set()
    for col in columns:
        if not col:
            raise InvalidTableError("ERRORS-STATE-1 violation: an empty column name is not allowed")
        if col in seen:
            raise InvalidTableError(f"ERRORS-STATE-1 violation: duplicate column {col!r}")
        seen.add(col)
    return tuple(columns)


def expected_state_filter(
    columns: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> StateFilterOutcome:
    """POST-STATE-1 to POST-STATE-4, INV-STATE-1 oracle."""
    cols = validate_table_columns(columns)
    col_set = set(cols)
    state_col = next((c for c in STATE_COLUMNS if c in col_set), None)
    if state_col is not None:
        kept = tuple(r for r in rows if r.get(state_col, "") in TARGET_STATE_VALUES)
        applied = f'state field "{state_col}" in FL, NY, UT'
    elif GEO_ID_COLUMN in col_set:
        kept = tuple(r for r in rows if bool(GEO_ID_TARGET_PATTERN.match(r.get(GEO_ID_COLUMN, ""))))
        applied = "GEO_ID national row or state/county/tract in FL (12), NY (36), UT (49)"
    else:
        kept = tuple(rows)
        applied = FILTER_NONE
    return StateFilterOutcome(
        rows=kept, rows_in_source=len(rows), rows_loaded=len(kept), applied_filter=applied
    )


def validate_state_filter_outcome(
    columns: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    outcome: StateFilterOutcome,
) -> None:
    """Raise StateFilterViolationError naming the clause when outcome disagrees with the oracle."""
    want = expected_state_filter(columns, rows)
    if outcome.rows_in_source != want.rows_in_source or outcome.rows_loaded != len(outcome.rows):
        raise StateFilterViolationError(
            f"POST-STATE-4 violation: counts ({outcome.rows_in_source}, {outcome.rows_loaded}) "
            f"disagree with ({want.rows_in_source}, {len(outcome.rows)})"
        )
    if outcome.applied_filter != want.applied_filter:
        raise StateFilterViolationError(
            f"POST-STATE violation: applied_filter {outcome.applied_filter!r} != "
            f"{want.applied_filter!r}"
        )
    if outcome.rows != want.rows:
        raise StateFilterViolationError(
            "POST-STATE / INV-STATE-1 violation: kept rows or their order disagree with the rule"
        )


def expected_table_provenance(
    *,
    table_name: str,
    source_file: str,
    sha256: str,
    applied_filter: str,
    rows_in_source: int,
    rows_loaded: int,
    origin_url: str | None = None,
    retrieved_at: str | None = None,
    publisher: str | None = None,
    license_text: str | None = None,
    as_of: str | None = None,
) -> TableProvenance:
    """POST-PROV-1..3, FORBIDDEN-PROV-1, ERRORS-PROV-1 oracle for one table's provenance record."""
    if not table_name.strip():
        raise InvalidProvenanceInputError("ERRORS-PROV-1 violation: table_name is empty")
    if not source_file.strip():
        raise InvalidProvenanceInputError("ERRORS-PROV-1 violation: source_file is empty")
    if not SHA256_PATTERN.match(sha256):
        raise InvalidProvenanceInputError(
            f"ERRORS-PROV-1 violation: sha256 {sha256!r} is not 64 lowercase hex characters"
        )
    if not applied_filter.strip():
        raise InvalidProvenanceInputError("ERRORS-PROV-1 violation: applied_filter is empty")
    if rows_in_source < 0 or rows_loaded < 0 or rows_loaded > rows_in_source:
        raise InvalidProvenanceInputError(
            f"ERRORS-PROV-1 violation: invalid row counts ({rows_in_source}, {rows_loaded})"
        )

    def _norm(value: str | None) -> str:
        if value is None or not value.strip():
            return NOT_RECORDED
        return value.strip()

    return TableProvenance(
        table_name=table_name.strip(),
        source_file=source_file.strip(),
        origin_url=_norm(origin_url),
        retrieved_at=_norm(retrieved_at),
        sha256=sha256,
        publisher=_norm(publisher),
        license=_norm(license_text),
        as_of=_norm(as_of),
        applied_filter=applied_filter.strip(),
        rows_in_source=rows_in_source,
        rows_loaded=rows_loaded,
    )


def validate_table_provenance(
    record: TableProvenance,
    expected: TableProvenance,
) -> None:
    """Raise ProvenanceViolationError naming the clause when record disagrees with expected."""
    for field_name in PROVENANCE_TEXT_FIELDS:
        actual_val = getattr(record, field_name)
        if not actual_val.strip():
            raise ProvenanceViolationError(
                f"FORBIDDEN-PROV-1 violation: {field_name} is blank; absent fields read "
                f"{NOT_RECORDED!r}"
            )
    if (record.rows_in_source, record.rows_loaded) != (
        expected.rows_in_source,
        expected.rows_loaded,
    ):
        raise ProvenanceViolationError(
            f"POST-PROV-3 violation: counts {(record.rows_in_source, record.rows_loaded)} != "
            f"{(expected.rows_in_source, expected.rows_loaded)}"
        )
    if record != expected:
        raise ProvenanceViolationError(
            f"POST-PROV-1 / POST-PROV-2 violation: provenance record {record!r} != {expected!r}"
        )


def validate_sources_unaltered(
    before_hashes: Mapping[str, str],
    after_hashes: Mapping[str, str],
) -> None:
    """INV-PROV-1 gate: verify every retained source file on disk is present and byte-identical."""
    if set(before_hashes) != set(after_hashes):
        raise ProvenanceViolationError(
            "INV-PROV-1 violation: retained source file set changed during ingest"
        )
    for path, digest in before_hashes.items():
        if after_hashes[path] != digest:
            raise ProvenanceViolationError(
                f"INV-PROV-1 violation: retained source file {path!r} was modified during ingest"
            )


def expected_glossary_entries(
    specs: Sequence[DictionaryTableSpec],
) -> tuple[GlossaryEntry, ...]:
    """POST-GLOSS-1, POST-GLOSS-2, INV-GLOSS-1, FORBIDDEN-GLOSS-1, ERRORS-GLOSS-1 oracle."""
    entries: list[GlossaryEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for spec in specs:
        if (
            not spec.source_table.strip()
            or not spec.dataset_id.strip()
            or not spec.term_column.strip()
            or not spec.definition_column.strip()
        ):
            raise InvalidGlossarySourceError(
                "ERRORS-GLOSS-1 violation: source_table, dataset_id, term_column and "
                "definition_column must be non-empty"
            )
        src_tbl = spec.source_table.strip()
        ds_id = spec.dataset_id.strip()
        for row in spec.rows:
            if spec.term_column not in row or spec.definition_column not in row:
                raise InvalidGlossarySourceError(
                    f"ERRORS-GLOSS-1 violation: row in {src_tbl!r} is missing "
                    f"{spec.term_column!r} or {spec.definition_column!r}"
                )
            term = row[spec.term_column].strip()
            defn = row[spec.definition_column].strip()
            if not term or not defn:
                continue
            key = (src_tbl, term, defn)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                GlossaryEntry(
                    source_table=src_tbl,
                    dataset_id=ds_id,
                    term=term,
                    definition=defn,
                )
            )
    return tuple(entries)


def validate_glossary_entries(
    specs: Sequence[DictionaryTableSpec],
    actual: Sequence[GlossaryEntry],
) -> None:
    """Raise GlossaryViolationError naming the clause when actual glossary entries disagree."""
    for entry in actual:
        if not entry.term.strip() or not entry.definition.strip():
            raise GlossaryViolationError(
                f"FORBIDDEN-GLOSS-1 violation: glossary entry {entry!r} has blank term or "
                "definition"
            )
    want = expected_glossary_entries(specs)
    if tuple(actual) != want:
        raise GlossaryViolationError(
            f"POST-GLOSS-1 / POST-GLOSS-2 / INV-GLOSS-1 violation: got {len(actual)} entries, "
            f"expected {len(want)} matching oracle order and contents"
        )


def validate_ingest_write_sequence(events: Sequence[str]) -> None:
    """SEQ-5 gate: files, catalog and sources tables are written AFTER data tables and BEFORE ok."""
    data_indices = [i for i, e in enumerate(events) if e.startswith("load_table:")]
    prov_indices = [i for i, e in enumerate(events) if e in PROVENANCE_TABLES]
    done_indices = [i for i, e in enumerate(events) if e == "report_success"]
    if set(PROVENANCE_TABLES) - set(events) or len(done_indices) != 1:
        raise GlossaryViolationError(
            "SEQ-5 violation: Ingest must write files, catalog and sources and report_success once"
        )
    if data_indices and min(prov_indices) <= max(data_indices):
        raise GlossaryViolationError(
            "SEQ-5 violation: provenance tables written before all data tables finished loading"
        )
    if max(prov_indices) >= done_indices[0]:
        raise GlossaryViolationError(
            "SEQ-5 violation: report_success emitted before files, catalog and sources were written"
        )


def validate_warehouse_location(env: Mapping[str, str]) -> WarehouseLocation:
    """POST-ADAPT-1 / ERRORS-ADAPT-1 oracle: the location comes only from WAREHOUSE_LOCATION."""
    raw = env.get(WAREHOUSE_LOCATION_ENV)
    if raw is None or not raw.strip():
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-1 violation: {WAREHOUSE_LOCATION_ENV} is unset or empty"
        )
    path = PurePosixPath(raw.strip())
    if not path.is_absolute():
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-1 violation: {WAREHOUSE_LOCATION_ENV} {raw!r} is not an absolute path"
        )
    if ".." in path.parts:
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-1 violation: {WAREHOUSE_LOCATION_ENV} {raw!r} contains '..'"
        )
    return WarehouseLocation(root=str(path))


def expected_table_location(table_name: str) -> str:
    """POST-ADAPT-2 / ERRORS-ADAPT-3 oracle: the relative location of one table's Parquet file."""
    if not TABLE_NAME_PATTERN.match(table_name):
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-3 violation: table name {table_name!r} does not match "
            f"{TABLE_NAME_PATTERN.pattern}"
        )
    return f"{PARQUET_DIR}/{table_name}.parquet"


def expected_table_path(location: WarehouseLocation, table_name: str, relative: str) -> str:
    """POST-ADAPT-3 / FORBIDDEN-ADAPT-1 oracle: join a relative table location to the location."""
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise WarehouseLocationError(
            f"FORBIDDEN-ADAPT-1 violation: table {table_name!r} has location {relative!r}, which "
            f"is not relative to the warehouse location {location.root!r}"
        )
    return str(PurePosixPath(location.root) / rel)


def validate_written_warehouse(written: WrittenWarehouse, *, data_tables: Sequence[str]) -> None:
    """POST-WRITE-2 oracle: base tables only, no views, every catalog location relative."""
    if tuple(sorted(written.base_tables)) != tuple(sorted(BASE_TABLES)):
        raise WarehouseWriteError(
            f"POST-WRITE-2 violation: base tables {sorted(written.base_tables)} != "
            f"{sorted(BASE_TABLES)}"
        )
    if written.views:
        raise WarehouseWriteError(
            f"POST-WRITE-2 violation: warehouse holds views {list(written.views)}; a view embeds "
            "a location"
        )
    catalog = dict(written.catalog)
    if sorted(catalog) != sorted(data_tables):
        raise WarehouseWriteError(
            f"POST-WRITE-2 violation: catalog lists {sorted(catalog)}, "
            f"written {sorted(data_tables)}"
        )
    for name, rel in catalog.items():
        if rel != expected_table_location(name):
            raise WarehouseWriteError(
                f"POST-WRITE-2 violation: catalog location {rel!r} for {name!r} is not "
                f"{expected_table_location(name)!r}"
            )


def validate_no_location_in_values(values: Sequence[str], location: WarehouseLocation) -> None:
    """INV-WRITE-1 oracle: no stored text value contains the warehouse location it was built at."""
    for value in values:
        if location.root in value:
            raise WarehouseWriteError(
                f"INV-WRITE-1 violation: stored value {value[:120]!r} contains the build location "
                f"{location.root!r}"
            )


def _reference(where: str, raw: Mapping[str, object]) -> tuple[str | None, str]:
    end = raw.get("reference_end")
    basis = raw.get("reference_basis")
    if end is None:
        return None, NOT_RECORDED
    if not isinstance(end, str) or not DATE_PATTERN.match(end):
        raise RegistryError(f"ERRORS-REG-1 violation: {where} reference_end {end!r} is not a date")
    try:
        date.fromisoformat(end)
    except ValueError as exc:
        raise RegistryError(
            f"ERRORS-REG-1 violation: {where} reference_end {end!r} is not a real date"
        ) from exc
    if not isinstance(basis, str) or not basis.strip():
        raise RegistryError(
            f"ERRORS-REG-1 violation: {where} has reference_end but no reference_basis"
        )
    return end, basis.strip()


def _text(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else NOT_RECORDED


def validate_registry(data: Mapping[str, object]) -> tuple[RegistryEntry, ...]:
    """POST-REG-1 / ERRORS-REG-1 oracle over a parsed registry ({"source": [ ... ]})."""
    sources = data.get("source")
    if not isinstance(sources, list) or not sources:
        raise RegistryError("ERRORS-REG-1 violation: the registry has no [[source]] entries")
    entries: list[RegistryEntry] = []
    seen: set[str] = set()
    for raw in sources:
        path = raw.get("path") if isinstance(raw, dict) else None
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"ERRORS-REG-1 violation: entry {raw!r} has no path")
        if path in seen:
            raise RegistryError(f"ERRORS-REG-1 violation: path {path!r} is listed twice")
        seen.add(path)
        for key in ("ds", "group"):
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                raise RegistryError(f"ERRORS-REG-1 violation: entry {path!r} has no {key}")
        fmt = raw.get("file_format")
        if fmt not in FORMAT_RANK:
            raise RegistryError(
                f"ERRORS-REG-1 violation: entry {path!r} file_format {fmt!r} is not one of "
                f"{sorted(FORMAT_RANK)}"
            )
        end, basis = _reference(f"entry {path!r}", raw)
        release = raw.get("release_id")
        if release is not None and (not isinstance(release, str) or not release.strip()):
            raise RegistryError(f"ERRORS-REG-1 violation: entry {path!r} has an empty release_id")
        members: list[RegistryMember] = []
        names: set[str] = set()
        for m in raw.get("member", []) or []:
            name = m.get("name") if isinstance(m, dict) else None
            if not isinstance(name, str) or not name or name in names:
                raise RegistryError(
                    f"ERRORS-REG-1 violation: entry {path!r} member name {name!r} is empty or "
                    "repeated"
                )
            names.add(name)
            mfmt = m.get("file_format")
            if mfmt not in FORMAT_RANK:
                raise RegistryError(
                    f"ERRORS-REG-1 violation: member {name!r} of {path!r} file_format {mfmt!r} "
                    "is unknown"
                )
            mend, mbasis = _reference(f"member {name!r} of {path!r}", m)
            members.append(RegistryMember(name, str(mfmt), mend, mbasis))
        entries.append(
            RegistryEntry(
                path=path,
                ds=str(raw["ds"]).strip(),
                group=str(raw["group"]).strip(),
                file_format=str(fmt),
                reference_end=end,
                reference_basis=basis,
                is_base_geography=raw.get("base_geography") is True,
                release_id=release if isinstance(release, str) else None,
                publisher=_text(raw, "publisher"),
                license=_text(raw, "license"),
                as_of=_text(raw, "as_of"),
                members=tuple(members),
            )
        )
    return tuple(entries)


def expected_registry_entry(entries: Sequence[RegistryEntry], path: str) -> RegistryEntry:
    """POST-REG-2 / ERRORS-REG-2 / FORBIDDEN-REG-1 oracle: exact path equality, nothing else."""
    for entry in entries:
        if entry.path == path:
            return entry
    raise UnregisteredSourceError(
        f"ERRORS-REG-2 violation: retained file {path!r} has no exact entry in {REGISTRY_FILE}"
    )


def expected_member_scope(entry: RegistryEntry, member: str) -> tuple[str, str | None]:
    """POST-REG-2 / ERRORS-REG-2 oracle: (file_format, reference_end) for an archive member.

    An entry that lists members requires an exact listing for each member. An entry without
    listed members gives every member the entry's reference end and the format of the member's
    extension (MEMBER_FORMAT_BY_EXTENSION); an unknown extension is ERRORS-ARCH-1.
    """
    if not entry.members:
        ext = PurePosixPath(member).suffix.lower()
        if ext not in MEMBER_FORMAT_BY_EXTENSION:
            raise ArchiveMemberError(
                f"ERRORS-ARCH-1 violation: member {member!r} of {entry.path!r} has extension "
                f"{ext!r}, which has no contracted format"
            )
        return MEMBER_FORMAT_BY_EXTENSION[ext], entry.reference_end
    for m in entry.members:
        if m.name == member:
            return m.file_format, m.reference_end
    raise UnregisteredSourceError(
        f"ERRORS-REG-2 violation: member {member!r} of {entry.path!r} has no exact entry in "
        f"{REGISTRY_FILE}"
    )


def _is_skipped_member(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return name.endswith("/") or any(p == "__MACOSX" or p.startswith(".") for p in parts)


def _is_shapefile_part(name: str, shapefiles: set[str]) -> bool:
    path = PurePosixPath(name)
    stem = str(path.with_suffix(""))
    if path.suffix.lower() in SHAPEFILE_PART_EXTENSIONS and f"{stem}.shp".lower() in shapefiles:
        return True
    lowered = name.lower()
    return lowered.endswith(".xml") and any(lowered.startswith(f"{s}.") for s in shapefiles)


def expected_archive_members(
    names: Sequence[str], entry: RegistryEntry
) -> tuple[ArchiveMember, ...]:
    """POST-ARCH-1 / ERRORS-ARCH-1 oracle over an archive's member names, in archive order."""
    kept = [n for n in names if not _is_skipped_member(n)]
    shapefiles = {n.lower() for n in kept if n.lower().endswith(".shp")}
    out: list[ArchiveMember] = []
    for name in kept:
        if _is_shapefile_part(name, shapefiles):
            continue
        fmt, end = expected_member_scope(entry, name)
        out.append(ArchiveMember(name=name, file_format=fmt, reference_end=end))
    return tuple(out)


def expected_cache_key(record: Mapping[str, object]) -> str:
    """POST-RET-1 / ERRORS-RET-1 oracle: the candidate key of an 'ok' manifest record."""
    path = record.get("path")
    if not isinstance(path, str) or not path:
        raise ManifestError(f"ERRORS-RET-1 violation: manifest record {record!r} has no path")
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ManifestError(
            f"ERRORS-RET-1 violation: manifest path {path!r} is not relative to {CACHE_DIR}"
        )
    return f"{CACHE_PREFIX}{rel}"


def validate_not_sources(
    data: Mapping[str, object], entries: Sequence[RegistryEntry]
) -> tuple[NotASource, ...]:
    """POST-REG-3 / ERRORS-REG-3 oracle over a parsed registry's [[not_a_source]] listings."""
    listed = data.get("not_a_source", [])
    if not isinstance(listed, list):
        raise RegistryError("ERRORS-REG-3 violation: not_a_source is not a list")
    sources = {e.path for e in entries}
    seen: set[str] = set()
    out: list[NotASource] = []
    for raw in listed:
        path = raw.get("path") if isinstance(raw, dict) else None
        reason = raw.get("reason") if isinstance(raw, dict) else None
        if not isinstance(path, str) or not path.strip():
            raise RegistryError(f"ERRORS-REG-3 violation: not_a_source {raw!r} has no path")
        if not isinstance(reason, str) or not reason.strip():
            raise RegistryError(f"ERRORS-REG-3 violation: not_a_source {path!r} has no reason")
        if path in seen or path in sources:
            raise RegistryError(
                f"ERRORS-REG-3 violation: {path!r} is listed twice or also registered as a source"
            )
        seen.add(path)
        out.append(NotASource(path, reason.strip()))
    return tuple(out)


def expected_retained(
    candidates: Sequence[str],
    entries: Sequence[RegistryEntry],
    not_sources: Sequence[NotASource],
) -> RetainedSources:
    """POST-RET-2 / ERRORS-RET-2 oracle: every candidate is registered or listed; none is stale."""
    registered = {e.path for e in entries}
    listed = {n.path: n for n in not_sources}
    cand = set(candidates)
    for path in sorted(cand):
        if path not in registered and path not in listed:
            raise UnregisteredSourceError(
                f"ERRORS-RET-2 violation: candidate {path!r} is neither a registered source nor "
                f"listed as not a source in {REGISTRY_FILE}"
            )
    for path in sorted((registered | set(listed)) - cand):
        raise RegistryError(
            f"ERRORS-RET-2 violation: {REGISTRY_FILE} names {path!r}, which is not a candidate file"
        )
    return RetainedSources(
        sources=tuple(sorted(cand & registered)),
        not_sources=tuple(listed[p] for p in sorted(cand & set(listed))),
    )


def expected_pdf_pages(pdftotext_stdout: str, page_count: int) -> tuple[DocumentPage, ...]:
    """POST-READ-2 / ERRORS-READ-2 oracle: one page per PDF page, blank pages kept."""
    chunks = pdftotext_stdout.split(PAGE_BREAK)
    if chunks and chunks[-1] == "":
        chunks = chunks[:-1]
    if len(chunks) != page_count:
        raise SourceReadError(
            f"ERRORS-READ-2 violation: pdftotext gave {len(chunks)} pages, pdfinfo {page_count}"
        )
    return tuple(DocumentPage(page=i, text=t) for i, t in enumerate(chunks, 1))


def expected_text_pages(raw: bytes) -> tuple[tuple[DocumentPage, ...], str]:
    """POST-READ-3 / ERRORS-READ-1 oracle: a text file is one page, decoded without loss."""
    for encoding in READ_ENCODINGS:
        try:
            return (DocumentPage(page=TEXT_PAGE, text=raw.decode(encoding)),), encoding
        except UnicodeDecodeError:
            continue
    raise SourceReadError("ERRORS-READ-1 violation: text file is not decodable")


def _json_cell(raw: object, std: object) -> str | None:
    """A scalar as written in the file; a nested value as compact JSON text; null as None."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "true" if raw else "false"
    if isinstance(raw, str):
        return raw
    return json.dumps(std, ensure_ascii=False, separators=(",", ":"))


def _is_table(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _json_table(key: str, raw_rows: list[Any], std_rows: list[Any]) -> JsonTable:
    columns: list[str] = []
    for row in raw_rows:
        columns.extend(k for k in row if k not in columns)
    rows = tuple(
        tuple(_json_cell(r.get(c), s.get(c)) for c in columns)
        for r, s in zip(raw_rows, std_rows, strict=True)
    )
    return JsonTable(key=key, columns=tuple(columns), rows=rows)


def expected_json_tables(text: str) -> tuple[JsonTable, ...]:
    """POST-READ-4 / ERRORS-READ-3 oracle over a JSON file's text."""
    try:
        raw = json.loads(text, parse_float=str, parse_int=str, parse_constant=str)
        std = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceReadError(f"ERRORS-READ-3 violation: not valid JSON: {exc}") from exc
    if _is_table(raw):
        return (_json_table(JSON_ROOT_KEY, raw, std),)
    if isinstance(raw, dict):
        tables = [_json_table(k, raw[k], std[k]) for k in raw if _is_table(raw[k])]
        rest = [k for k in raw if not _is_table(raw[k])]
        if rest:
            tables.append(
                JsonTable(
                    key=JSON_ROOT_KEY,
                    columns=tuple(rest),
                    rows=(tuple(_json_cell(raw[k], std[k]) for k in rest),),
                )
            )
        return tuple(tables)
    return (JsonTable(key=JSON_ROOT_KEY, columns=(JSON_BLOB_COLUMN,), rows=((text,),)),)


def validate_geo_columns(columns: Sequence[str], types: Sequence[str]) -> None:
    """POST-READ-5 oracle: attribute columns VARCHAR, one GEOMETRY column, no GDAL row id."""
    if GEO_ROW_ID_COLUMN in columns:
        raise SourceReadError(
            f"POST-READ-5 violation: {GEO_ROW_ID_COLUMN} is a GDAL row id, not a source column"
        )
    for name, kind in zip(columns, types, strict=True):
        wanted_geometry = name == GEO_GEOMETRY_COLUMN
        if wanted_geometry != kind.startswith("GEOMETRY") or (
            not wanted_geometry and kind != "VARCHAR"
        ):
            raise SourceReadError(
                f"POST-READ-5 violation: column {name!r} has type {kind!r}; attributes are "
                f"VARCHAR and {GEO_GEOMETRY_COLUMN!r} is the only GEOMETRY column"
            )


def expected_sheet_cell(
    value_type: str | None,
    *,
    value: str | None = None,
    date_value: str | None = None,
    boolean_value: str | None = None,
    text: str = "",
) -> str | None:
    """POST-READ-6 / ERRORS-READ-5 oracle: the stored text of one typed spreadsheet cell."""
    if value_type is None:
        return text or None
    if value_type in NUMERIC_VALUE_TYPES:
        return value
    if value_type == "date" and date_value is not None:
        day, _, clock = date_value.partition("T")
        if clock.strip("0:.") != "":  # midnight is all zeros: 00:00, 00:00:00, 00:00:00.000
            raise SourceReadError(
                f"ERRORS-READ-5 violation: date cell {date_value!r} has a time of day; "
                "the one date format is YYYY-MM-DD"
            )
        if not DATE_PATTERN.match(day):
            raise SourceReadError(
                f"ERRORS-READ-5 violation: date cell {date_value!r} is not a date"
            )
        return day
    if value_type == "boolean" and boolean_value is not None:
        return boolean_value
    if value_type == "string":
        return text
    raise SourceReadError(
        f"ERRORS-READ-5 violation: cell type {value_type!r} has no contracted text form"
    )


# --- 5. Traceability map (every clause declares its verification method) -----------------------

CONTRACT_SCOPE: Mapping[str, Clause] = {
    "POST-SCOPE-1": Clause(
        "test",
        "A file that is not base geography and whose reference_end is on or after 2024-01-01 "
        "is loaded, unless a duplicate rule excludes it.",
        ("REQ-25",),
    ),
    "POST-SCOPE-2": Clause(
        "test",
        "A base-geography file is never excluded for time_scope, whatever its reference_end.",
        ("REQ-25",),
    ),
    "POST-SCOPE-3": Clause(
        "test",
        "A file that is not base geography and whose reference_end is before 2024-01-01 is "
        "excluded with reason time_scope, even when a duplicate rule also applies.",
        ("REQ-25", "REQ-26"),
    ),
    "POST-SCOPE-4": Clause(
        "test",
        "Of files with the same sha256, the first in (format rank, path) order is loaded and "
        "every other is excluded with reason duplicate_content.",
        ("REQ-26",),
    ),
    "POST-SCOPE-5": Clause(
        "test",
        "Of files sharing a release_id in different formats, the lowest format rank is loaded "
        "and the others are excluded with reason duplicate_format.",
        ("REQ-26",),
    ),
    "POST-SCOPE-6": Clause(
        "test",
        "A file whose reference_end is unknown is never excluded for time_scope; the sources do "
        "not state its period, so REQ-26 gives no reason to exclude it.",
        ("REQ-25", "REQ-26"),
    ),
    "INV-SCOPE-1": Clause(
        "test",
        "Every input file receives exactly one decision, returned in the input order.",
        ("REQ-26",),
    ),
    "INV-SCOPE-2": Clause(
        "test",
        "The decisions do not depend on the order in which the files are listed.",
        ("REQ-26",),
    ),
    "FORBIDDEN-SCOPE-1": Clause(
        "test",
        "A decision is load with no reason, or exclude with exactly one reason from time_scope, "
        "duplicate_content, duplicate_format; no other reason exists.",
        ("REQ-26",),
    ),
    "ERRORS-SCOPE-1": Clause(
        "test",
        "validate_source_file raises InvalidSourceFileError for an empty path or sha256, an "
        "unknown file_format, a reference_end that is not a real YYYY-MM-DD date, or an empty "
        "release_id.",
        ("REQ-25",),
    ),
}


CONTRACT_STATE_FILTER: Mapping[str, Clause] = {
    "POST-STATE-1": Clause(
        "test",
        "When a table has one or more columns from STATE_COLUMNS, the first in STATE_COLUMNS "
        "governs and only rows whose value in that column is in TARGET_STATE_VALUES are kept.",
        ("REQ-27",),
    ),
    "POST-STATE-2": Clause(
        "test",
        "When a table has no column from STATE_COLUMNS and has GEO_ID, only rows matching "
        "GEO_ID_TARGET_PATTERN (national row or FL 12, NY 36, UT 49) are kept.",
        ("REQ-27",),
    ),
    "POST-STATE-3": Clause(
        "test",
        "When a table has neither a column from STATE_COLUMNS nor GEO_ID, every row is kept "
        "and applied_filter is FILTER_NONE.",
        ("REQ-27",),
    ),
    "POST-STATE-4": Clause(
        "test",
        "rows_in_source equals the input row count and rows_loaded equals the kept row count.",
        ("REQ-27", "REQ-29"),
    ),
    "INV-STATE-1": Clause(
        "test",
        "Kept rows appear in their input order and each kept row is unaltered.",
        ("REQ-27", "REQ-28"),
    ),
    "ERRORS-STATE-1": Clause(
        "test",
        "validate_table_columns raises InvalidTableError when columns is empty, contains an "
        "empty name, or contains duplicate names.",
        ("REQ-27",),
    ),
}


CONTRACT_PROVENANCE: Mapping[str, Clause] = {
    "POST-PROV-1": Clause(
        "test",
        "Every loaded table has a TableProvenance record carrying table_name, source_file, "
        "origin_url, retrieved_at, sha256, publisher, license, as_of, applied_filter, "
        "rows_in_source and rows_loaded.",
        ("REQ-29",),
    ),
    "POST-PROV-2": Clause(
        "test",
        "When any of origin_url, retrieved_at, publisher, license or as_of is None or whitespace, "
        'the recorded field value is "not recorded" (NOT_RECORDED).',
        ("REQ-29",),
    ),
    "POST-PROV-3": Clause(
        "test",
        "rows_in_source and rows_loaded are non-negative integers with "
        "rows_loaded <= rows_in_source.",
        ("REQ-29",),
    ),
    "INV-PROV-1": Clause(
        "test",
        "Reading a retained source file from local disk computes its SHA-256 and leaves the file's "
        "bytes unaltered.",
        ("REQ-28", "REQ-29"),
    ),
    "FORBIDDEN-PROV-1": Clause(
        "test",
        "No provenance text field is empty or whitespace-only, and no unstated value is inferred "
        'in place of "not recorded".',
        ("REQ-29",),
    ),
    "ERRORS-PROV-1": Clause(
        "test",
        "Building a TableProvenance record raises InvalidProvenanceInputError when table_name, "
        "source_file or applied_filter is blank, sha256 is not 64 lowercase hex characters, or "
        "row counts are negative or rows_loaded > rows_in_source.",
        ("REQ-29",),
    ),
}


CONTRACT_GLOSSARY: Mapping[str, Clause] = {
    "POST-GLOSS-1": Clause(
        "test",
        "Every row in a DictionaryTableSpec with a non-empty trimmed term and definition produces "
        "a GlossaryEntry carrying source_table, dataset_id, term and definition.",
        ("REQ-30",),
    ),
    "POST-GLOSS-2": Clause(
        "test",
        "Duplicate (source_table, term, definition) triples are deduplicated keeping the first "
        "occurrence in input order.",
        ("REQ-30",),
    ),
    "INV-GLOSS-1": Clause(
        "test",
        "Glossary entries preserve the exact trimmed term and definition text from the loaded "
        "dictionary or lookup rows in input order without altering input mappings.",
        ("REQ-28", "REQ-30"),
    ),
    "FORBIDDEN-GLOSS-1": Clause(
        "test",
        "Rows with an empty or whitespace-only term or definition are never emitted into the "
        "glossary table, and no definition is fabricated when a row lacks one.",
        ("REQ-29", "REQ-30"),
    ),
    "SEQ-5": Clause(
        "test",
        "The Ingest writes the files, catalog and sources provenance tables AFTER every data and "
        "glossary table is loaded and BEFORE it reports success.",
        ("REQ-29", "REQ-30"),
    ),
    "ERRORS-GLOSS-1": Clause(
        "test",
        "build_glossary_entries raises InvalidGlossarySourceError when source_table, dataset_id, "
        "term_column or definition_column is blank, or when a row lacks the declared term_column "
        "or definition_column key.",
        ("REQ-30",),
    ),
    "INV-STORAGE-1": Clause(
        "tool",
        "The Operator builds the warehouse once and keeps the canonical copy in private Google "
        "Cloud Storage bucket WAREHOUSE_GCS_BUCKET (WAREHOUSE_GCS_URI) in project "
        "WAREHOUSE_GCP_PROJECT.",
        ("REQ-31",),
    ),
}


CONTRACT_ADAPTER: Mapping[str, Clause] = {
    "POST-ADAPT-1": Clause(
        "test",
        "warehouse_location(env) returns the warehouse location taken only from the "
        "WAREHOUSE_LOCATION variable, as an absolute normalized POSIX path; no other variable "
        "and no default supplies it.",
        ("REQ-47",),
    ),
    "ERRORS-ADAPT-1": Clause(
        "test",
        "warehouse_location raises WarehouseLocationError naming WAREHOUSE_LOCATION when it is "
        "unset, empty or whitespace, not an absolute path, or contains '..'.",
        ("REQ-47",),
    ),
    "ERRORS-ADAPT-2": Clause(
        "test",
        "require_warehouse(location) raises WarehouseLocationError naming the location and the "
        "missing item when the location directory or its warehouse.duckdb file does not exist, "
        "and returns the location unchanged when both exist.",
        ("REQ-47",),
    ),
    "POST-ADAPT-2": Clause(
        "test",
        "table_location(table_name) returns 'parquet/<table_name>.parquet', a location relative "
        "to the warehouse location.",
        ("REQ-48",),
    ),
    "ERRORS-ADAPT-3": Clause(
        "test",
        "table_location raises WarehouseLocationError when table_name does not match "
        "TABLE_NAME_PATTERN.",
        ("REQ-48",),
    ),
    "POST-ADAPT-3": Clause(
        "test",
        "table_path(location, table_name, relative) returns the warehouse location joined with the "
        "relative table location, so the same catalog resolves under any warehouse location.",
        ("REQ-47", "REQ-48"),
    ),
    "FORBIDDEN-ADAPT-1": Clause(
        "test",
        "table_path never resolves an empty, absolute, backslashed or '..' table location; it "
        "raises WarehouseLocationError naming the table and the warehouse location.",
        ("REQ-48",),
    ),
}


CONTRACT_WRITER: Mapping[str, Clause] = {
    "POST-WRITE-1": Clause(
        "test",
        "WarehouseWriter.write_table(table_name, relation) writes the relation's rows to the "
        "Parquet file at table_path(location, table_name, table_location(table_name)) and returns "
        "table_location(table_name).",
        ("REQ-48",),
    ),
    "POST-WRITE-2": Clause(
        "test",
        "WarehouseWriter.finalize(base_tables) writes warehouse.duckdb holding exactly BASE_TABLES "
        "as tables and no views, with one catalog row per written data table whose parquet value "
        "equals table_location(table_name).",
        ("REQ-48", "REQ-51"),
    ),
    "INV-WRITE-1": Clause(
        "test",
        "No text value in any base table of the written warehouse contains the location it was "
        "written at, so the warehouse opens unchanged when copied to another location.",
        ("REQ-48",),
    ),
    "ERRORS-WRITE-1": Clause(
        "test",
        "WarehouseWriter raises WarehouseWriteError when a table name is written twice in one "
        "build, when finalize is missing a BASE_TABLES table, or when the catalog base table "
        "lacks a CATALOG_REQUIRED_COLUMNS column.",
        ("REQ-48",),
    ),
    "POST-BASE-1": Clause(
        "test",
        "The Ingest writes each base table with exactly the columns of BASE_TABLE_COLUMNS, in "
        "order: one catalog and one sources row per data table, whose source_file is the "
        "registry path of the file it came from (for example 'repo:data/external/...'); sources "
        "holds the table's provenance with its registry ID as dataset_id and NOT_RECORDED for an "
        "unstated field; one columns row per data table column (ordinal from 1); and glossary "
        "rows as GLOSSARY_COLUMNS.",
        ("REQ-29", "REQ-30", "REQ-48"),
    ),
}


CONTRACT_REGISTRY: Mapping[str, Clause] = {
    "POST-REG-1": Clause(
        "test",
        "load_registry returns one RegistryEntry per [[source]] entry, with reference_end and its "
        "reference_basis, and NOT_RECORDED for an unstated publisher, license, as_of or basis.",
        ("REQ-25", "REQ-29"),
    ),
    "ERRORS-REG-1": Clause(
        "test",
        "load_registry raises RegistryError naming the entry when the registry has no entries, an "
        "entry lacks path, ds or group, a path is listed twice, a file_format is not in "
        "FORMAT_RANK, a reference_end is not a real date or has no reference_basis, a release_id "
        "is empty, or a member name is empty or repeated.",
        ("REQ-25", "REQ-29"),
    ),
    "POST-REG-2": Clause(
        "test",
        "registry_entry(entries, path) returns the entry whose path equals the retained file's "
        "path; member_scope(entry, member) returns the member's own facts when the entry lists "
        "members, and otherwise the entry's reference end with the format of the member's "
        "extension (MEMBER_FORMAT_BY_EXTENSION).",
        ("REQ-25", "REQ-26"),
    ),
    "ERRORS-REG-2": Clause(
        "test",
        "registry_entry raises UnregisteredSourceError naming the file when no entry has its exact "
        "path, and member_scope raises it naming the member when the entry lists members but not "
        "this one; the Ingest stops rather than loading or excluding an unregistered source.",
        ("REQ-25", "REQ-26"),
    ),
    "FORBIDDEN-REG-1": Clause(
        "test",
        "A registry entry never matches a file or member by substring, prefix, case-insensitive "
        "comparison or pattern; only exact equality matches.",
        ("REQ-26",),
    ),
    "POST-READ-1": Clause(
        "test",
        "read_delimited(con, path, delimiter=..., header=...) returns a DuckDB relation of every "
        "parsable row, all columns VARCHAR; the encoding used, the first of READ_ENCODINGS that "
        "decodes the whole file, so a Latin-1 fallback is reported and never mixed with UTF-8; and "
        "one RejectedRow per unparsable row, with its file line, error type and raw text. A "
        "malformed row never excludes the file (Z-22).",
        ("REQ-25", "REQ-28", "REQ-53", "REQ-54"),
    ),
    "ERRORS-READ-1": Clause(
        "test",
        "read_delimited raises SourceReadError naming the file and the reader's message only when "
        "the file is missing, is not a file, or cannot be read with any of READ_ENCODINGS; a "
        "malformed row is not a reason to raise (Z-22).",
        ("REQ-25", "REQ-53"),
    ),
}


CONTRACT_RETAINED: Mapping[str, Clause] = {
    "POST-RET-1": Clause(
        "test",
        "candidate_sources(repo_root) returns, sorted and without duplicates, 'cache:<path>' for "
        "every MANIFEST_FILE path whose latest record has status 'ok', and 'repo:<path>' for every "
        "file under CANDIDATE_ROOTS except files under EXCLUDED_DIRS, hidden files and files "
        "under hidden or __pycache__ directories.",
        ("REQ-25",),
    ),
    "ERRORS-RET-1": Clause(
        "test",
        "candidate_sources raises ManifestError naming the record when an 'ok' manifest record "
        "has no path, an absolute path, or a path containing '..'.",
        ("REQ-25", "REQ-48"),
    ),
    "POST-REG-3": Clause(
        "test",
        "load_not_sources returns one NotASource per [[not_a_source]] listing in the registry, "
        "with its path and reason.",
        ("REQ-25", "REQ-26"),
    ),
    "ERRORS-REG-3": Clause(
        "test",
        "load_not_sources raises RegistryError naming the listing when it has no path or no "
        "reason, repeats a path, or names a path also registered as a source.",
        ("REQ-25", "REQ-26"),
    ),
    "POST-RET-2": Clause(
        "test",
        "retained_sources(candidates, entries, not_sources) returns the candidates with an exact "
        "registry entry as sources and the candidates listed as not a source with their reasons.",
        ("REQ-25", "REQ-26"),
    ),
    "ERRORS-RET-2": Clause(
        "test",
        "retained_sources raises UnregisteredSourceError naming a candidate that is neither "
        "registered nor listed, and RegistryError naming a registry entry or listing that names "
        "no candidate; the Ingest stops in both cases.",
        ("REQ-25", "REQ-26"),
    ),
}

CONTRACT_DOCUMENTS: Mapping[str, Clause] = {
    "POST-READ-2": Clause(
        "test",
        "read_pdf_pages(path) runs PDF_TEXT_COMMAND and returns one DocumentPage per page that "
        "PDF_INFO_COMMAND reports, numbered from 1 in order, blank pages kept with their own "
        "text, each page's text exactly as pdftotext wrote it between PAGE_BREAK characters.",
        ("REQ-25", "REQ-28"),
    ),
    "ERRORS-READ-2": Clause(
        "test",
        "read_pdf_pages raises SourceReadError naming the file when the file is missing, a "
        "command is missing or exits non-zero, or the page count from pdftotext differs from "
        "pdfinfo's; it never returns fewer pages than the PDF has.",
        ("REQ-25",),
    ),
    "POST-READ-3": Clause(
        "test",
        "read_text_pages(path) returns one DocumentPage numbered TEXT_PAGE with the file's text "
        "decoded by the first of READ_ENCODINGS that decodes it without error, and that encoding; "
        "no byte is replaced or dropped, and the reported encoding is what the Ingest logs for the "
        "file (Z-22). An undecodable or missing file raises SourceReadError (ERRORS-READ-1).",
        ("REQ-25", "REQ-28", "REQ-53", "REQ-54"),
    ),
    "POST-READ-4": Clause(
        "test",
        "read_json_tables(path) returns, in file order, one JsonTable per top-level array of "
        "objects (keyed by its name, or JSON_ROOT_KEY for a top-level array), with one column per "
        "object key in first-seen order; and, when the top level is an object with other entries, "
        "one JSON_ROOT_KEY table holding those entries as one row, so no entry is dropped. A "
        "scalar keeps its text as written in the file, a nested value is compact JSON text, null "
        "is None; any other top level is one JSON_BLOB_COLUMN row with the file's text.",
        ("REQ-25", "REQ-28"),
    ),
    "ERRORS-READ-3": Clause(
        "test",
        "read_json_tables raises SourceReadError naming the file when it is missing, cannot be "
        "decoded with READ_ENCODINGS, or is not valid JSON.",
        ("REQ-25",),
    ),
    "POST-READ-5": Clause(
        "test",
        "read_geo(con, source) returns a DuckDB relation of every feature that ST_Read (the "
        "GEO_EXTENSION reader) returns for source, a file path or a GDAL /vsizip/ member path, "
        "with every attribute column VARCHAR, the geometry as GEO_GEOMETRY_COLUMN of type "
        "GEOMETRY, and without GEO_ROW_ID_COLUMN.",
        ("REQ-25", "REQ-28"),
    ),
    "ERRORS-READ-4": Clause(
        "test",
        "read_geo raises SourceReadError naming the source when GEO_EXTENSION cannot be loaded or "
        "GDAL cannot open the source; it never returns an empty relation for an unreadable source.",
        ("REQ-25",),
    ),
    "POST-READ-6": Clause(
        "test",
        "read_sheets(path) converts a .xls or .xlsx workbook with OFFICE_CONVERT_COMMAND to "
        "SHEET_TARGET and returns one SheetTable per worksheet, in workbook order and named as in "
        "the workbook (chart data tables are not worksheets), each cell as expected_sheet_cell "
        "gives it: a date as YYYY-MM-DD, a number from its stored value, text as written, an empty "
        "cell as None; repeated cells and rows expanded, trailing empty rows and columns "
        "dropped, and every row padded with None to the sheet's width.",
        ("REQ-25", "REQ-28"),
    ),
    "ERRORS-READ-5": Clause(
        "test",
        "read_sheets raises SourceReadError naming the file and, for a cell, its sheet, row and "
        "column, when the file is missing, LibreOffice is missing or fails, a date cell has a time "
        "of day other than midnight, or a cell's type has no contracted text form (Q-2: one date "
        "format, always).",
        ("REQ-25", "REQ-53"),
    ),
    "POST-READ-7": Clause(
        "test",
        "read_slides(path) converts a .pptx deck with OFFICE_CONVERT_COMMAND to SLIDES_TARGET and "
        "returns read_pdf_pages of that PDF: one DocumentPage per slide, numbered from 1.",
        ("REQ-25", "REQ-28"),
    ),
    "ERRORS-READ-6": Clause(
        "test",
        "read_slides raises SourceReadError naming the file when it is missing or LibreOffice is "
        "missing, fails, or writes no PDF; PDF reading errors propagate as ERRORS-READ-2.",
        ("REQ-25",),
    ),
    "POST-ARCH-1": Clause(
        "test",
        "archive_members(path, entry) returns one ArchiveMember per source member of a retained "
        "zip archive, in archive order, with member_scope's format and reference end; "
        "directories, __MACOSX and hidden entries are skipped, and a shapefile's companion files "
        "(SHAPEFILE_PART_EXTENSIONS and its .xml metadata) belong to its .shp, not listed alone.",
        ("REQ-25", "REQ-26"),
    ),
    "ERRORS-ARCH-1": Clause(
        "test",
        "archive_members raises ArchiveMemberError naming the archive and member when an "
        "unlisted member's extension is not in MEMBER_FORMAT_BY_EXTENSION, and SourceReadError "
        "naming the archive when it is missing or not a zip archive.",
        ("REQ-25",),
    ),
    "POST-ARCH-2": Clause(
        "test",
        "member_source(path, member, workdir) returns the reader's source for a member: for a "
        "shapefile, VSIZIP_PREFIX + the archive path + '/' + the member name, read in place; for "
        "any other format, a file in workdir whose bytes equal the member's bytes (REQ-28).",
        ("REQ-25", "REQ-28"),
    ),
    "ERRORS-ARCH-2": Clause(
        "test",
        "member_source raises ArchiveMemberError naming the archive and member when the member "
        "is not in the archive or cannot be extracted.",
        ("REQ-25",),
    ),
}


# =============================================================================================
# Batch 7 (cycle 19): the Ingest command. Judgement calls by jev at Ketema's direction (highest
# rated): table names '<ds>_<file stem>[_<member stem>][_<sheet or key>]' (0.50); worksheets
# kept as raw cells with the first non-empty row recorded as labels (0.62); native geometry
# (0.63); glossary dictionaries declared in the registry (0.83); rows set aside logged to stderr
# and to the ingest_log table with per-file counts (0.85); origin from the download manifest
# (0.83); a process pool that stages Parquet for the one writer (0.89).
# =============================================================================================

INGEST_MODULE = "src.warehouse.ingest"  # run as: python -m src.warehouse.ingest --workers N
MANIFEST_FILE = "data/cache/MANIFEST.jsonl"
MEMBER_SEPARATOR = "!"  # source key of an archive member: '<archive path>!<member name>'
DELIMITED_READS: Mapping[str, tuple[str | None, bool]] = {  # format -> (delimiter, header)
    "csv": (None, True),
    "tsv": ("\t", True),
    "dat": (None, True),
    "pl": ("|", False),
}
SHEET_FORMATS: frozenset[str] = frozenset({"xlsx", "xls"})
JSON_FORMATS: frozenset[str] = frozenset({"json"})
GEO_FORMATS: frozenset[str] = frozenset({"geojson", "shapefile"})
PAGE_FORMATS: frozenset[str] = frozenset({"pdf", "text"})
SLIDE_FORMATS: frozenset[str] = frozenset({"pptx"})
RAW_COLUMN_PREFIX = "c"  # worksheet columns are c1..cN
FILE_LOADED = "loaded"
FILE_EXCLUDED = "excluded"
FILE_NOT_A_SOURCE = "not a source"


class IngestError(WarehouseContractError):
    """ERRORS-INGEST-1: the Ingest cannot build the warehouse as specified; nothing is final."""


class GlossaryDeclarationError(WarehouseContractError):
    """ERRORS-GLOSS-2: a [[glossary]] declaration is incomplete or names no registered source."""


@dataclass(frozen=True)
class GlossaryDeclaration:
    """A registry [[glossary]] entry: the dictionary part of a source and its two columns."""

    path: str
    part: str | None  # a worksheet, JSON key or archive member; None for the whole file
    term: str
    definition: str


def validate_glossary_declarations(
    data: Mapping[str, object], entries: Sequence[RegistryEntry]
) -> tuple[GlossaryDeclaration, ...]:
    """POST-GLOSS-3 / ERRORS-GLOSS-2 oracle over the registry's [[glossary]] array."""
    paths = {e.path for e in entries}
    raw_list = data.get("glossary", []) or []
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


def _snake(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def expected_table_name(ds: str, path: str, member: str | None, part: str | None) -> str:
    """POST-INGEST-2 oracle: a table's name before repeats are numbered."""
    stem = PurePosixPath(path.split(":", 1)[-1]).stem
    pieces = [ds, stem, PurePosixPath(member).stem if member else "", part or ""]
    name = "_".join(p for p in (_snake(x) for x in pieces) if p)
    return name if name and not name[0].isdigit() else f"t_{name}"


def expected_unique_names(names: Sequence[str]) -> tuple[str, ...]:
    """POST-INGEST-2 oracle: the k-th use of a name (k >= 2) becomes '<name>_<k>', skipping any
    name already taken, in input order."""
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
    return tuple(out)


def expected_sheet_columns(rows: Sequence[Sequence[str | None]]) -> tuple[str, ...]:
    """POST-INGEST-2 oracle: a worksheet's raw column names c1..cN, N its widest row."""
    width = max((len(r) for r in rows), default=0)
    return tuple(f"{RAW_COLUMN_PREFIX}{i}" for i in range(1, width + 1))


def expected_sheet_labels(rows: Sequence[Sequence[str | None]]) -> tuple[str, ...]:
    """POST-INGEST-5 oracle: the first row with a non-empty cell, as text, padded to the width."""
    width = max((len(r) for r in rows), default=0)
    first = next((r for r in rows if any(c not in (None, "") for c in r)), ())
    return tuple(("" if c is None else str(c)) for c in first) + ("",) * (width - len(first))


def expected_origin(
    source_key: str, manifest_records: Sequence[Mapping[str, object]]
) -> tuple[str, str]:
    """POST-INGEST-4 oracle: (origin_url, retrieved_at) of a source from the download manifest.

    The archive's key is used for an archive member. The last 'ok' record whose cache key
    (expected_cache_key) equals it gives its url and ts; otherwise both are NOT_RECORDED.
    """
    key = source_key.split(MEMBER_SEPARATOR, 1)[0]
    found = (NOT_RECORDED, NOT_RECORDED)
    for record in manifest_records:
        if record.get("status") == "ok" and expected_cache_key(record) == key:
            url, ts = record.get("url"), record.get("ts")
            found = (
                url if isinstance(url, str) and url.strip() else NOT_RECORDED,
                ts if isinstance(ts, str) and ts.strip() else NOT_RECORDED,
            )
    return found


CONTRACT_INGEST: Mapping[str, Clause] = {
    "POST-INGEST-1": Clause(
        "test",
        "run(repo_root, env, workers) builds the warehouse at WAREHOUSE_LOCATION. Scope "
        "(expected_scope_decisions) is decided over units: each retained non-archive file, and "
        "each member of a retained zip archive (expected_archive_members), keyed "
        "'<archive>!<member>', with the member's format and "
        "reference end, the SHA-256 of its bytes "
        "and the entry's base geography and release_id. The files table has one row per unit and "
        "one per archive and non-source: status FILE_LOADED with an empty reason or '<n> rows set "
        "aside', FILE_EXCLUDED with the scope reason, FILE_NOT_A_SOURCE with the registry's "
        "reason, and for an archive FILE_LOADED with reason '<n> members'; ds and file_format "
        "from the registry (NOT_RECORDED for a non-source) and the SHA-256.",
        ("REQ-25", "REQ-26", "REQ-28"),
    ),
    "POST-INGEST-2": Clause(
        "test",
        "Every loaded delimited file (DELIMITED_READS), worksheet (SHEET_FORMATS, columns "
        "expected_sheet_columns, raw cells), JSON table (JSON_FORMATS) and geographic file "
        "(GEO_FORMATS, geometry kept) becomes one data table; archive members are read as their "
        "member format through member_source. Names are expected_unique_names of "
        "expected_table_name in registry order, then member, part and reading order. Rows equal "
        "the reader's rows after expected_state_filter. A worksheet with no cell gives no table.",
        ("REQ-25", "REQ-27", "REQ-28", "REQ-48"),
    ),
    "POST-INGEST-3": Clause(
        "test",
        "Every page of a loaded PAGE_FORMATS or SLIDE_FORMATS file is one documents row "
        "(source key, page from 1, text); such files give no data table.",
        ("REQ-25",),
    ),
    "POST-INGEST-4": Clause(
        "test",
        "Each data table has one catalog row (status 'ok') and one sources row per POST-BASE-1: "
        "origin_url and retrieved_at from expected_origin, publisher, license and as_of from the "
        "registry, the source file's SHA-256 (the archive's for a member), the applied filter and "
        "the row counts before and after the state filter.",
        ("REQ-29",),
    ),
    "POST-INGEST-5": Clause(
        "test",
        "Each data table column has one columns row (ordinal from 1, DuckDB type, label "
        "expected_sheet_labels for a worksheet and '' otherwise).",
        ("REQ-29", "REQ-33"),
    ),
    "POST-GLOSS-3": Clause(
        "test",
        "The glossary holds build_glossary_entries over each declared dictionary part "
        "(validate_glossary_declarations): rows after the label row, keyed by label for a "
        "worksheet and by column name otherwise, source_table the part's table name.",
        ("REQ-30",),
    ),
    "ERRORS-GLOSS-2": Clause(
        "test",
        "A [[glossary]] declaration naming no registered source, or with a blank term, definition "
        "or part, raises GlossaryDeclarationError naming ERRORS-GLOSS-2 before any reading.",
        ("REQ-30",),
    ),
    "POST-INGEST-6": Clause(
        "test",
        "Each row a reader set aside is one ingest_log row (source key, 'line <n>', its error "
        "type, its raw text) and one stderr log line naming the file and line (REQ-53, REQ-54).",
        ("REQ-53", "REQ-54"),
    ),
    "POST-INGEST-7": Clause(
        "test",
        "The warehouse is the same for any workers >= 1: the files are read in parallel worker "
        "processes that stage Parquet, and one writer registers the staged tables in name order "
        "and writes the base tables last (SEQ-5).",
        ("REQ-51",),
    ),
    "FORBIDDEN-INGEST-1": Clause(
        "test",
        "The Ingest opens no network connection and changes no source file (their SHA-256 are "
        "the same after the run).",
        ("REQ-28",),
    ),
    "ERRORS-INGEST-1": Clause(
        "test",
        "An unregistered candidate (ERRORS-RET-2), an unreadable file, a loaded format with no "
        "reader, or an existing warehouse at the location raises IngestError naming "
        "ERRORS-INGEST-1 and the file; no warehouse.duckdb is written.",
        ("REQ-25", "REQ-31", "REQ-51"),
    ),
}
