"""Reading of retained delimited source files with DuckDB, every value kept as text.

Specification: contracts/warehouse_contract.py, CONTRACT_REGISTRY (POST-READ-1, ERRORS-READ-1)
and CONTRACT_DOCUMENTS (POST-READ-3). Requirements: REQ-25, REQ-28, REQ-53, REQ-54. Runtime
declarations are independent of that module; tests bridge the specification and this
implementation (CL11-F).
"""

import codecs
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import duckdb

READ_ENCODINGS: Final[tuple[str, ...]] = ("utf-8", "latin-1")  # tried in this order
_CHUNK_BYTES: Final = 1 << 20


class SourceReadError(Exception):
    """ERRORS-READ-1: a retained source file cannot be read."""


@dataclass(frozen=True)
class RejectedRow:
    """Z-22: a delimited row set aside, with its 1-based file line and raw text (POST-READ-1)."""

    line: int
    error_type: str
    raw: str


def whole_file_encoding(path: Path) -> str:
    """Return the first of READ_ENCODINGS that decodes the whole file (POST-READ-1, POST-READ-3).

    The file is streamed through an incremental decoder, so a large file is never held in
    memory, and the choice is made before any row is parsed: a UTF-8 failure switches the whole
    file to Latin-1 rather than replacing or skipping bytes (Z-22).

    Raises:
        SourceReadError: ERRORS-READ-1, the path is not a readable file or no encoding fits.
    """
    if not path.is_file():
        raise SourceReadError(f"ERRORS-READ-1 violation: {str(path)!r} is not a readable file")
    for encoding in READ_ENCODINGS:
        decoder = codecs.getincrementaldecoder(encoding)()
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(_CHUNK_BYTES):
                    decoder.decode(chunk)
                decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise SourceReadError(
                f"ERRORS-READ-1 violation: {str(path)!r} could not be read: {exc}"
            ) from exc
        return encoding
    raise SourceReadError(
        f"ERRORS-READ-1 violation: {str(path)!r} is not decodable with any of {READ_ENCODINGS}"
    )


def _last_reject_scan(con: duckdb.DuckDBPyConnection) -> int:
    """Highest reject scan id on this connection, or -1 before the first stored scan."""
    try:
        row = con.execute("SELECT coalesce(max(scan_id), -1) FROM reject_scans").fetchall()
    except duckdb.CatalogException:
        return -1
    return int(row[0][0])


def read_delimited(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    *,
    delimiter: str | None = None,
    header: bool = True,
) -> tuple[duckdb.DuckDBPyRelation, str, tuple[RejectedRow, ...]]:
    """Read a delimited file as an all-VARCHAR relation of every parsable row (POST-READ-1).

    Returns the relation, the encoding used for the whole file, and one RejectedRow per row
    DuckDB could not parse. A malformed row never excludes the file (Z-22). The file is only
    read, never written (REQ-28).

    Raises:
        SourceReadError: ERRORS-READ-1, the path is missing, is not a file, cannot be decoded
            with any of READ_ENCODINGS, or DuckDB cannot open it; the message names the file.
    """
    encoding = whole_file_encoding(path)
    # All options are bound parameters; DuckDB sets malformed rows aside and records them.
    query = (
        "SELECT * FROM read_csv($path, all_varchar=true, header=$header, encoding=$encoding, "
        "sample_size=-1, ignore_errors=true, store_rejects=true, delim=$delim)"
        if delimiter is not None
        else "SELECT * FROM read_csv($path, all_varchar=true, header=$header, "
        "encoding=$encoding, sample_size=-1, ignore_errors=true, store_rejects=true)"
    )
    params: dict[str, object] = {"path": str(path), "header": header, "encoding": encoding}
    if delimiter is not None:
        params["delim"] = delimiter
    before = _last_reject_scan(con)
    try:
        relation = con.sql(query, params=params)
        relation.aggregate("count(*)").fetchall()
    except duckdb.Error as exc:
        raise SourceReadError(
            f"ERRORS-READ-1 violation: {str(path)!r} could not be read ({encoding}): {exc}"
        ) from exc
    rejected = con.execute(
        "SELECT line, error_type, csv_line FROM reject_errors WHERE scan_id > $before "
        "ORDER BY line",
        {"before": before},
    ).fetchall()
    return (
        relation,
        encoding,
        tuple(
            RejectedRow(line=int(n), error_type=str(kind), raw=str(raw))
            for n, kind, raw in rejected
        ),
    )
