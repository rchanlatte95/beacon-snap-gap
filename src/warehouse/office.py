"""Spreadsheets and slide decks, converted by LibreOffice and read by their typed contents.

Specification: contracts/warehouse_contract.py, CONTRACT_DOCUMENTS (SLICE-3 batch 6c-iv).
Requirements: REQ-25, REQ-28, REQ-53; Ketema's Q-1, Q-2 (one date format, YYYY-MM-DD) and Q-3.
Runtime declarations are independent of that module; tests bridge the specification and this
implementation (CL11-F).
"""

import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .documents import DocumentPage, read_pdf_pages
from .reader import SourceReadError

OFFICE_CONVERT_COMMAND: Final[tuple[str, ...]] = (
    "soffice",
    "--headless",
    "--norestore",
    "--convert-to",
)
SHEET_TARGET: Final = "fods"
SLIDES_TARGET: Final = "pdf"
NUMERIC_VALUE_TYPES: Final[tuple[str, ...]] = ("float", "percentage", "currency")
_CONVERT_TIMEOUT_SECONDS: Final = 600
_DATE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_OFFICE: Final = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_TABLE: Final = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_TEXT: Final = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_ROW_GROUPS: Final = {
    f"{_TABLE}table-header-rows",
    f"{_TABLE}table-rows",
    f"{_TABLE}table-row-group",
}
_CELLS: Final = {f"{_TABLE}table-cell", f"{_TABLE}covered-table-cell"}

__all__ = [
    "NUMERIC_VALUE_TYPES",
    "OFFICE_CONVERT_COMMAND",
    "SHEET_TARGET",
    "SLIDES_TARGET",
    "SheetTable",
    "SourceReadError",
    "read_sheets",
    "read_slides",
]


@dataclass(frozen=True)
class SheetTable:
    """One worksheet, its rows in order, every cell text or None (POST-READ-6)."""

    sheet: str
    rows: tuple[tuple[str | None, ...], ...]


def _convert(path: Path, target: str, outdir: Path, clause: str) -> Path:
    """Convert path with LibreOffice into outdir and return the written file, or stop."""
    command = [*OFFICE_CONVERT_COMMAND, target, "--outdir", str(outdir), str(path)]
    try:
        done = subprocess.run(  # noqa: S603 - fixed contracted command, path is a retained file
            command, capture_output=True, text=True, timeout=_CONVERT_TIMEOUT_SECONDS, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise SourceReadError(
            f"{clause} violation: {str(path)!r} could not be converted: {exc}"
        ) from exc
    written = outdir / f"{path.stem}.{target}"
    if done.returncode != 0 or not written.is_file():
        raise SourceReadError(
            f"{clause} violation: {str(path)!r} could not be converted to {target}: "
            f"exit {done.returncode}: {done.stderr.strip()[:300]}"
        )
    return written


def _text(element: ET.Element) -> str:
    """Text of one paragraph, with ODF's encoded spaces, tabs and line breaks restored."""
    parts = [element.text or ""]
    for child in element:
        if child.tag == f"{_TEXT}s":
            parts.append(" " * int(child.get(f"{_TEXT}c", "1")))
        elif child.tag == f"{_TEXT}tab":
            parts.append("\t")
        elif child.tag == f"{_TEXT}line-break":
            parts.append("\n")
        else:
            parts.append(_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _cell_text(cell: ET.Element) -> str | None:
    """POST-READ-6: the stored text of one typed cell; ERRORS-READ-5 for an uncontracted type."""
    value_type = cell.get(f"{_OFFICE}value-type")
    text = "\n".join(_text(p) for p in cell.findall(f"{_TEXT}p"))
    if value_type is None:
        return text or None
    if value_type in NUMERIC_VALUE_TYPES:
        return cell.get(f"{_OFFICE}value")
    if value_type == "date":
        stored = cell.get(f"{_OFFICE}date-value") or ""
        day, _, clock = stored.partition("T")
        if clock.strip("0:.") != "":  # midnight is all zeros
            raise SourceReadError(
                f"ERRORS-READ-5 violation: date cell {stored!r} has a time of day; "
                "the one date format is YYYY-MM-DD"
            )
        if not _DATE.match(day):
            raise SourceReadError(f"ERRORS-READ-5 violation: date cell {stored!r} is not a date")
        return day
    if value_type == "boolean":
        return cell.get(f"{_OFFICE}boolean-value")
    if value_type == "string":
        return text
    raise SourceReadError(
        f"ERRORS-READ-5 violation: cell type {value_type!r} has no contracted text form"
    )


def _rows(container: ET.Element) -> Iterator[ET.Element]:
    """Every row of a sheet, in order, including rows inside header and grouped row blocks."""
    for child in container:
        if child.tag == f"{_TABLE}table-row":
            yield child
        elif child.tag in _ROW_GROUPS:
            yield from _rows(child)


def _sheet(table: ET.Element, path: Path) -> SheetTable:
    """Read one worksheet: repeats expanded, trailing empties dropped, rows padded (POST-READ-6)."""
    name = table.get(f"{_TABLE}name", "")
    rows: list[list[str | None]] = []
    pending_rows = 0
    for row_number, row in enumerate(_rows(table), 1):
        values: list[str | None] = []
        pending_cells = 0
        for column, cell in enumerate((c for c in row if c.tag in _CELLS), 1):
            try:
                value = _cell_text(cell)
            except SourceReadError as exc:
                raise SourceReadError(
                    f"{exc} (file {str(path)!r}, sheet {name!r}, row {row_number}, column {column})"
                ) from exc
            repeat = int(cell.get(f"{_TABLE}number-columns-repeated", "1"))
            if value is None:
                pending_cells += repeat
            else:
                values.extend([None] * pending_cells)
                pending_cells = 0
                values.extend([value] * repeat)
        repeat_rows = int(row.get(f"{_TABLE}number-rows-repeated", "1"))
        if not values:
            pending_rows += repeat_rows
            continue
        rows.extend([] for _ in range(pending_rows))
        pending_rows = 0
        rows.extend(list(values) for _ in range(repeat_rows))
    width = max((len(r) for r in rows), default=0)
    return SheetTable(sheet=name, rows=tuple(tuple(r + [None] * (width - len(r))) for r in rows))


def read_sheets(path: Path) -> tuple[SheetTable, ...]:
    """Read every worksheet of a .xls or .xlsx workbook by typed cell (POST-READ-6).

    Operational ceiling: the converted flat file is parsed whole in memory; a workbook whose
    flat ODS does not fit in memory needs a streaming parse (upgrade trigger: a memory error).

    Raises:
        SourceReadError: ERRORS-READ-5, the file is missing, LibreOffice is missing or fails, a
            date cell has a time of day, or a cell type has no contracted text form; the message
            names the file and, for a cell, its sheet, row and column.
    """
    if not path.is_file():
        raise SourceReadError(f"ERRORS-READ-5 violation: {str(path)!r} is not a readable file")
    with tempfile.TemporaryDirectory() as tmp:
        flat = _convert(path, SHEET_TARGET, Path(tmp), "ERRORS-READ-5")
        try:
            root = ET.parse(flat).getroot()  # noqa: S314 - LibreOffice's own output of a local file
        except ET.ParseError as exc:
            raise SourceReadError(
                f"ERRORS-READ-5 violation: {str(path)!r} converted to unreadable XML: {exc}"
            ) from exc
    spreadsheet = root.find(f"{_OFFICE}body/{_OFFICE}spreadsheet")
    if spreadsheet is None:
        raise SourceReadError(f"ERRORS-READ-5 violation: {str(path)!r} holds no spreadsheet")
    # POST-READ-6: only worksheets. Chart data tables sit deeper, inside drawings; a direct child
    # with a table-source is LibreOffice's cache of an external link, not a sheet of this workbook.
    return tuple(
        _sheet(t, path)
        for t in spreadsheet.findall(f"{_TABLE}table")
        if t.find(f"{_TABLE}table-source") is None
    )


def read_slides(path: Path) -> tuple[DocumentPage, ...]:
    """Read a .pptx deck as one page per slide, numbered from 1 (POST-READ-7).

    Raises:
        SourceReadError: ERRORS-READ-6, the file is missing or LibreOffice is missing, fails or
            writes no PDF; PDF reading errors propagate as ERRORS-READ-2.
    """
    if not path.is_file():
        raise SourceReadError(f"ERRORS-READ-6 violation: {str(path)!r} is not a readable file")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = _convert(path, SLIDES_TARGET, Path(tmp), "ERRORS-READ-6")
        return read_pdf_pages(pdf)
