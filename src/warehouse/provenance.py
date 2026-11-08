"""Build warehouse table provenance records and read local source digests (SLICE-3 batch 3).

Specification: contracts/warehouse_contract.py, CONTRACT_PROVENANCE.
Requirements: REQ-28, REQ-29. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

NOT_RECORDED: Final = "not recorded"
SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
PROVENANCE_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "origin_url",
    "retrieved_at",
    "publisher",
    "license",
    "as_of",
)
_CHUNK_BYTES: Final = 65_536


class InvalidProvenanceInputError(Exception):
    """ERRORS-PROV-1: table provenance input is outside the contracted domain."""


@dataclass(frozen=True, slots=True)
class TableProvenance:
    """Validated provenance record for one warehouse table (POST-PROV-1..3)."""

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


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of a local source file without modifying it.

    PRE: path points to an existing readable file on local disk.
    POST: returns a 64-character lowercase hexadecimal SHA-256 digest.
    INV: opens the file read-only on local disk and leaves its bytes unaltered (INV-PROV-1).
    """
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_BYTES):
            hasher.update(chunk)
    return hasher.hexdigest()


def _normalize_optional_field(value: str | None) -> str:
    if value is None or not value.strip():
        return NOT_RECORDED
    return value.strip()


def build_table_provenance(
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
    """Validate and construct a TableProvenance record for a loaded warehouse table.

    PRE: required identifiers and row counts are provided as keyword arguments.
    POST: returns TableProvenance with absent optional fields set to NOT_RECORDED (POST-PROV-1..3).
    INV: never emits empty/whitespace provenance strings or infers missing values
        (FORBIDDEN-PROV-1).

    Raises:
        InvalidProvenanceInputError: Propagates when required fields, sha256, or row counts are
            invalid (ERRORS-PROV-1).
    """
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
    # POST-PROV-1..3 / FORBIDDEN-PROV-1: trim stated strings, normalize absent to NOT_RECORDED.
    return TableProvenance(
        table_name=table_name.strip(),
        source_file=source_file.strip(),
        origin_url=_normalize_optional_field(origin_url),
        retrieved_at=_normalize_optional_field(retrieved_at),
        sha256=sha256,
        publisher=_normalize_optional_field(publisher),
        license=_normalize_optional_field(license_text),
        as_of=_normalize_optional_field(as_of),
        applied_filter=applied_filter.strip(),
        rows_in_source=rows_in_source,
        rows_loaded=rows_loaded,
    )
