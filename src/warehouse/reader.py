"""Fail-fast reading of retained delimited source files with DuckDB, every value kept as text.

Specification: contracts/warehouse_contract.py, CONTRACT_REGISTRY (POST-READ-1, ERRORS-READ-1).
Requirements: REQ-25, REQ-28. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

from pathlib import Path
from typing import Final

import duckdb

READ_ENCODINGS: Final[tuple[str, ...]] = ("utf-8", "latin-1")  # tried in this order


class SourceReadError(Exception):
    """ERRORS-READ-1: a retained source file cannot be read."""


def read_delimited(
    con: duckdb.DuckDBPyConnection,
    path: Path,
    *,
    delimiter: str | None = None,
    header: bool = True,
) -> tuple[duckdb.DuckDBPyRelation, str]:
    """Read a delimited file as an all-VARCHAR relation and report the encoding (POST-READ-1).

    The file is only read, never written (REQ-28). Each encoding is tried in READ_ENCODINGS
    order; the rows are scanned once here so a decoding or parsing failure surfaces now rather
    than when the relation is first used.

    Raises:
        SourceReadError: ERRORS-READ-1, the path is not a readable file or no encoding in
            READ_ENCODINGS reads it; the message names the file and the reader's error.
    """
    if not path.is_file():
        raise SourceReadError(f"ERRORS-READ-1 violation: {str(path)!r} is not a readable file")
    failures: list[str] = []
    # DuckDB's relational read_csv accepts only UTF-8; its read_csv table function decodes
    # every encoding in READ_ENCODINGS. All options are bound parameters.
    query = (
        "SELECT * FROM read_csv($path, all_varchar=true, header=$header, "
        "encoding=$encoding, sample_size=-1, delim=$delim)"
        if delimiter is not None
        else "SELECT * FROM read_csv($path, all_varchar=true, header=$header, "
        "encoding=$encoding, sample_size=-1)"
    )
    for encoding in READ_ENCODINGS:
        params: dict[str, object] = {"path": str(path), "header": header, "encoding": encoding}
        if delimiter is not None:
            params["delim"] = delimiter
        try:
            relation = con.sql(query, params=params)
            relation.aggregate("count(*)").fetchall()
        except duckdb.Error as exc:
            failures.append(f"{encoding}: {exc}")
            continue
        return relation, encoding
    raise SourceReadError(
        f"ERRORS-READ-1 violation: {str(path)!r} could not be read: {'; '.join(failures)}"
    )
