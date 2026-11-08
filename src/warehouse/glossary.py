"""Extract warehouse glossary entries and order ingest provenance writes (SLICE-3 batch 4).

Specification: contracts/warehouse_contract.py, CONTRACT_GLOSSARY.
Requirements: REQ-28, REQ-29, REQ-30, REQ-31. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

GLOSSARY_COLUMNS: Final[tuple[str, ...]] = ("source_table", "dataset_id", "term", "definition")
PROVENANCE_TABLES: Final[tuple[str, ...]] = ("files", "catalog", "sources")
WAREHOUSE_GCP_PROJECT: Final = "<gcp-project>"


class InvalidGlossarySourceError(Exception):
    """ERRORS-GLOSS-1: a dictionary/lookup source description is invalid."""


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    """Validated glossary entry from a loaded data dictionary or lookup table (POST-GLOSS-1..2)."""

    source_table: str
    dataset_id: str
    term: str
    definition: str


@dataclass(frozen=True, slots=True)
class DictionaryTableSpec:
    """Description of one loaded dictionary or lookup table to extract glossary rows from."""

    source_table: str
    dataset_id: str
    term_column: str
    definition_column: str
    rows: tuple[Mapping[str, str], ...]


def build_glossary_entries(
    specs: Sequence[DictionaryTableSpec],
) -> tuple[GlossaryEntry, ...]:
    """Extract trimmed, deduplicated glossary entries from loaded dictionary and lookup tables.

    PRE: specs contains DictionaryTableSpec instances describing loaded dictionary tables.
    POST: returns GlossaryEntry tuples with blank rows skipped and duplicates removed
        (POST-GLOSS-1, POST-GLOSS-2, FORBIDDEN-GLOSS-1).
    INV: preserves input order and exact trimmed strings without mutating input mappings
        (INV-GLOSS-1).

    Raises:
        InvalidGlossarySourceError: Propagates when spec metadata is blank or a row lacks the
            declared term or definition column (ERRORS-GLOSS-1).
    """
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
        source_table = spec.source_table.strip()
        dataset_id = spec.dataset_id.strip()
        for row in spec.rows:
            if spec.term_column not in row or spec.definition_column not in row:
                raise InvalidGlossarySourceError(
                    f"ERRORS-GLOSS-1 violation: row in {source_table!r} is missing "
                    f"{spec.term_column!r} or {spec.definition_column!r}"
                )
            term = row[spec.term_column].strip()
            definition = row[spec.definition_column].strip()
            # FORBIDDEN-GLOSS-1: skip rows with blank term or definition; never fabricate.
            if not term or not definition:
                continue
            # POST-GLOSS-2: deduplicate by (source_table, term, definition) keeping first.
            key = (source_table, term, definition)
            if key in seen:
                continue
            seen.add(key)
            # POST-GLOSS-1 / INV-GLOSS-1: preserve exact trimmed text in input order.
            entries.append(
                GlossaryEntry(
                    source_table=source_table,
                    dataset_id=dataset_id,
                    term=term,
                    definition=definition,
                )
            )
    return tuple(entries)


def run_ingest_write_plan(
    *,
    data_tables: Sequence[str],
    dictionary_specs: Sequence[DictionaryTableSpec],
) -> tuple[str, ...]:
    """Execute the ingest write sequence: data tables, glossary, provenance tables, then success.

    PRE: data_tables lists loaded table names; dictionary_specs lists dictionary sources.
    POST: validates dictionary_specs via build_glossary_entries and returns the ordered event log
        with files, catalog and sources written AFTER all data and glossary tables and BEFORE
        report_success (SEQ-5).
    INV: inputs are not mutated.

    Raises:
        InvalidGlossarySourceError: Propagates if dictionary_specs is invalid (ERRORS-GLOSS-1).
    """
    build_glossary_entries(dictionary_specs)
    events: list[str] = [f"load_table:{tbl}" for tbl in data_tables]
    events.append("load_table:glossary")
    # SEQ-5: write files, catalog and sources after every data and glossary table is loaded.
    events.extend(PROVENANCE_TABLES)
    events.append("report_success")
    return tuple(events)
