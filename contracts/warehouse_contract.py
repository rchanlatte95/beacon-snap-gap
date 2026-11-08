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

The implementation MUST NOT import this module (CL11-F). Tests import both and compare.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Literal

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
FORMAT_RANK: Mapping[str, int] = {"csv": 0, "xlsx": 1, "sas": 2}

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
