"""Document reading: every page of a retained PDF, and every text file, as numbered text.

Specification: contracts/warehouse_contract.py, CONTRACT_DOCUMENTS (SLICE-3 batch 6c-ii).
Requirements: REQ-25, REQ-28, REQ-53, REQ-54. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .reader import SourceReadError, whole_file_encoding

PDF_TEXT_COMMAND: Final[tuple[str, ...]] = ("pdftotext", "-layout", "-enc", "UTF-8")
PDF_INFO_COMMAND: Final[tuple[str, ...]] = ("pdfinfo",)
PAGE_BREAK: Final = "\f"  # pdftotext ends every page with a form feed
_PAGES_LABEL: Final = "Pages:"
TEXT_PAGE: Final = 1  # a text file is one page, numbered 1

__all__ = [
    "PAGE_BREAK",
    "PDF_INFO_COMMAND",
    "PDF_TEXT_COMMAND",
    "TEXT_PAGE",
    "DocumentPage",
    "SourceReadError",
    "read_pdf_pages",
    "read_text_pages",
]


@dataclass(frozen=True)
class DocumentPage:
    """One page of a retained document, numbered from 1 (POST-READ-2)."""

    page: int
    text: str


def read_text_pages(path: Path) -> tuple[tuple[DocumentPage, ...], str]:
    """Return a text file as one page numbered TEXT_PAGE, and the encoding used (POST-READ-3).

    The whole file is decoded by the first of the reader's encodings that fits it, so no byte
    is replaced or dropped (Z-22); the caller logs the encoding.

    Raises:
        SourceReadError: ERRORS-READ-1, the file is missing or cannot be read.
    """
    encoding = whole_file_encoding(path)
    return (DocumentPage(page=TEXT_PAGE, text=path.read_text(encoding=encoding)),), encoding


def _run(command: list[str], path: Path) -> str:
    """Run a Poppler command on path and return its stdout, or stop naming the file."""
    try:
        done = subprocess.run(  # noqa: S603 - fixed contracted command, path is a retained file
            command, capture_output=True, text=True, encoding="utf-8", check=False
        )
    except FileNotFoundError as exc:
        raise SourceReadError(
            f"ERRORS-READ-2 violation: {str(path)!r} could not be read: command "
            f"{command[0]!r} is not on PATH ({exc})"
        ) from exc
    if done.returncode != 0:
        raise SourceReadError(
            f"ERRORS-READ-2 violation: {str(path)!r} could not be read: {command[0]} exited "
            f"{done.returncode}: {done.stderr.strip()[:300]}"
        )
    return done.stdout


def _page_count(info: str, path: Path) -> int:
    for line in info.splitlines():
        if line.startswith(_PAGES_LABEL):
            value = line[len(_PAGES_LABEL) :].strip()
            if value.isdigit():
                return int(value)
    raise SourceReadError(
        f"ERRORS-READ-2 violation: {str(path)!r}: {PDF_INFO_COMMAND[0]} reported no page count"
    )


def read_pdf_pages(path: Path) -> tuple[DocumentPage, ...]:
    """Return one page per PDF page, numbered from 1, blank pages kept (POST-READ-2).

    Raises:
        SourceReadError: ERRORS-READ-2, the file is missing, a command is missing or fails, or
            pdftotext's page count differs from pdfinfo's; the message names the file.
    """
    if not path.is_file():
        raise SourceReadError(f"ERRORS-READ-2 violation: {str(path)!r} is not a readable file")
    count = _page_count(_run([*PDF_INFO_COMMAND, str(path)], path), path)
    chunks = _run([*PDF_TEXT_COMMAND, str(path), "-"], path).split(PAGE_BREAK)
    if chunks and chunks[-1] == "":
        chunks = chunks[:-1]
    if len(chunks) != count:
        raise SourceReadError(
            f"ERRORS-READ-2 violation: {str(path)!r}: pdftotext gave {len(chunks)} pages, "
            f"{PDF_INFO_COMMAND[0]} reports {count}"
        )
    return tuple(DocumentPage(page=i, text=text) for i, text in enumerate(chunks, 1))
