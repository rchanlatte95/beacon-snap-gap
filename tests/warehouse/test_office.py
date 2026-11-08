"""RED tests for SLICE-3 batch 6c-iv: spreadsheets and slide decks through LibreOffice.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_DOCUMENTS)
- Authority: AUTHORITATIVE for the warehouse and its Ingest (SLICE-3)
- Clauses covered: POST-READ-6, ERRORS-READ-5, POST-READ-7, ERRORS-READ-6
- Requirements: REQ-25, REQ-28, REQ-53; Ketema's Q-1 (LibreOffice), Q-2 (one date format,
  YYYY-MM-DD, revised to typed cells), Q-3 (PPTX through PDF)

The implementation is src/warehouse/office.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites one of the four clauses.
  C2 VALUABLE: exact rows of a real .xlsx built from typed cells (a styled date, repeated
     numbers, an empty cell, a percentage, a non-ASCII name), exact refusal of a time of day;
     exact slide texts in order.
  C3 NON-DUPLICATIVE: test 1 pins the workbook reader; test 2 pins the deck reader.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.

Fixtures are flat OpenDocument files converted by LibreOffice itself, the same tool the
implementation uses; no test double is involved.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import office as impl

# Risk tier: HIGH. A misread date or a dropped cell changes every figure built on a workbook.

_NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:number="urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
)
_STYLES = (
    "<office:automatic-styles>"
    '<number:date-style style:name="N37"><number:month number:style="long"/>'
    '<number:text>/</number:text><number:day number:style="long"/><number:text>/</number:text>'
    "<number:year/></number:date-style>"
    '<number:percentage-style style:name="N11"><number:number number:decimal-places="0" '
    'number:min-integer-digits="1"/><number:text>%</number:text></number:percentage-style>'
    '<style:style style:name="ce1" style:family="table-cell" style:data-style-name="N37"/>'
    '<style:style style:name="ce2" style:family="table-cell" style:data-style-name="N11"/>'
    "</office:automatic-styles>"
)


def _fods(tables: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><office:document {_NS} office:version="1.3" '
        'office:mimetype="application/vnd.oasis.opendocument.spreadsheet">'
        f"{_STYLES}<office:body><office:spreadsheet>{tables}</office:spreadsheet></office:body>"
        "</office:document>"
    )


def _convert(src: Path, target: str) -> Path:
    """Fixture builder: LibreOffice converts a flat ODF file; the output sits next to it."""
    subprocess.run(  # noqa: S603 - fixed LibreOffice command on a file this test wrote
        [*contract.OFFICE_CONVERT_COMMAND, target, "--outdir", str(src.parent), str(src)],
        capture_output=True,
        check=True,
        timeout=180,
    )
    return src.with_suffix(f".{target}")


def test_workbook_sheets_keep_typed_cells_with_one_date_format(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_sheet_cell(), SheetTable, OFFICE_CONVERT_COMMAND,
      SHEET_TARGET
    - Enforces: POST-READ-6, ERRORS-READ-5
    - Category: positive, boundary (repeated cells, empty cell, trailing columns), negative
    - Risk tier: HIGH
    - Pyramid level: Integration (real LibreOffice conversion)
    - Equivalence partition: styled date at midnight; float repeated twice; empty cell;
      percentage; text with a non-ASCII letter; a date with a time of day; missing file.
    """
    good_src = tmp_path / "book.fods"
    good_src.write_text(
        _fods(
            '<table:table table:name="Data"><table:table-row>'
            '<table:table-cell office:value-type="string"><text:p>State</text:p></table:table-cell>'
            '<table:table-cell table:style-name="ce1" office:value-type="date" '
            'office:date-value="2024-08-01"><text:p>08/01/2024</text:p></table:table-cell>'
            "</table:table-row><table:table-row>"
            '<table:table-cell office:value-type="string"><text:p>Florida</text:p>'
            "</table:table-cell>"
            '<table:table-cell office:value-type="float" office:value="1234" '
            'table:number-columns-repeated="2"><text:p>1234</text:p></table:table-cell>'
            "<table:table-cell/>"
            '<table:table-cell table:style-name="ce2" office:value-type="percentage" '
            'office:value="0.25"><text:p>25%</text:p></table:table-cell>'
            "</table:table-row></table:table>"
            '<table:table table:name="Notes"><table:table-row>'
            '<table:table-cell office:value-type="string"><text:p>Do&#241;a Ana</text:p>'
            "</table:table-cell></table:table-row></table:table>"
        ),
        encoding="utf-8",
    )
    workbook = _convert(good_src, "xlsx")
    cell = contract.expected_sheet_cell
    want = [
        (
            "Data",
            (
                (
                    cell("string", text="State"),
                    cell("date", date_value="2024-08-01"),
                    None,
                    None,
                    None,
                ),
                (
                    cell("string", text="Florida"),
                    cell("float", value="1234"),
                    cell("float", value="1234"),
                    None,
                    cell("percentage", value="0.25"),
                ),
            ),
        ),
        ("Notes", ((cell("string", text="Do\u00f1a Ana"),),)),
    ]
    got = [(t.sheet, t.rows) for t in impl.read_sheets(workbook)]
    assert got == want, (
        "test_workbook_sheets_keep_typed_cells_with_one_date_format FAILED\n"
        "POST-READ-6 violation: sheets, rows or cells differ\n"
        f"EXPECTED: {want!r}\n"
        f"ACTUAL: {got!r}\n"
        "GUIDANCE: one table per worksheet in order; dates YYYY-MM-DD, numbers as stored, text as "
        "written, empty as None; repeated cells expanded; rows padded to the sheet's width"
    )

    timed_src = tmp_path / "timed.fods"
    timed_src.write_text(
        _fods(
            '<table:table table:name="Times"><table:table-row>'
            '<table:table-cell table:style-name="ce1" office:value-type="date" '
            'office:date-value="2024-08-01T13:05:00"><text:p>08/01/2024</text:p></table:table-cell>'
            "</table:table-row></table:table>"
        ),
        encoding="utf-8",
    )
    timed = _convert(timed_src, "xlsx")
    for label, path, needles in (
        ("time of day", timed, ("ERRORS-READ-5", "timed.xlsx", "Times")),
        ("missing file", tmp_path / "absent.xlsx", ("ERRORS-READ-5", "absent.xlsx")),
    ):
        with pytest.raises(impl.SourceReadError) as caught:
            impl.read_sheets(path)
        found = tuple(n in str(caught.value) for n in needles)
        assert found == (True,) * len(needles), (
            "test_workbook_sheets_keep_typed_cells_with_one_date_format FAILED\n"
            f"ERRORS-READ-5 violation for {label}: the refusal does not name the clause, file "
            "and sheet\n"
            f"EXPECTED: SourceReadError containing {needles!r}\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: stop on a time of day (one date format) or an unreadable file, and say where"
        )

    assert (impl.OFFICE_CONVERT_COMMAND, impl.SHEET_TARGET, impl.SLIDES_TARGET) == (
        contract.OFFICE_CONVERT_COMMAND,
        contract.SHEET_TARGET,
        contract.SLIDES_TARGET,
    ), (
        "test_workbook_sheets_keep_typed_cells_with_one_date_format FAILED\n"
        "POST-READ-6 violation: the LibreOffice command or targets differ from the contract\n"
        "EXPECTED: the contract's OFFICE_CONVERT_COMMAND, SHEET_TARGET and SLIDES_TARGET\n"
        "ACTUAL: different values\n"
        "GUIDANCE: use the contracted conversion"
    )


def test_slide_deck_is_one_page_per_slide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract OFFICE_CONVERT_COMMAND, SLIDES_TARGET, DocumentPage
    - Enforces: POST-READ-7, ERRORS-READ-6
    - Category: positive, negative
    - Risk tier: MEDIUM: one listed deck (DS-B5), whose slides the AI may quote
    - Pyramid level: Integration (real LibreOffice and Poppler)
    - Equivalence partition: a two-slide deck; a missing file; LibreOffice not on PATH.
    """
    deck_src = tmp_path / "deck.fodp"
    deck_src.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><office:document {_NS} office:version="1.3" '
        'office:mimetype="application/vnd.oasis.opendocument.presentation">'
        "<office:body><office:presentation>"
        '<draw:page draw:name="one"><draw:frame svg:x="2cm" svg:y="2cm" svg:width="20cm" '
        'svg:height="3cm"><draw:text-box><text:p>Alpha slide</text:p></draw:text-box></draw:frame>'
        "</draw:page>"
        '<draw:page draw:name="two"><draw:frame svg:x="2cm" svg:y="2cm" svg:width="20cm" '
        'svg:height="3cm"><draw:text-box><text:p>Beta slide</text:p></draw:text-box></draw:frame>'
        "</draw:page></office:presentation></office:body></office:document>",
        encoding="utf-8",
    )
    deck = _convert(deck_src, "pptx")
    pages = impl.read_slides(deck)
    view = [(p.page, p.text.strip()) for p in pages]
    assert view == [(1, "Alpha slide"), (2, "Beta slide")], (
        "test_slide_deck_is_one_page_per_slide FAILED\n"
        "POST-READ-7 violation: the slides were not returned one page each, in order\n"
        "EXPECTED: [(1, 'Alpha slide'), (2, 'Beta slide')]\n"
        f"ACTUAL: {view!r}\n"
        "GUIDANCE: convert the deck to PDF and read one page per slide"
    )

    with pytest.raises(impl.SourceReadError) as caught_missing:
        impl.read_slides(tmp_path / "absent.pptx")
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    with monkeypatch.context() as m:
        m.setenv("PATH", str(empty_bin))
        with pytest.raises(impl.SourceReadError) as caught_tool:
            impl.read_slides(deck)
    named = (
        "ERRORS-READ-6" in str(caught_missing.value),
        "absent.pptx" in str(caught_missing.value),
        "ERRORS-READ-6" in str(caught_tool.value),
        deck.name in str(caught_tool.value),
    )
    assert named == (True, True, True, True), (
        "test_slide_deck_is_one_page_per_slide FAILED\n"
        "ERRORS-READ-6 violation: a missing deck or a missing LibreOffice was not refused by name\n"
        "EXPECTED: SourceReadError citing ERRORS-READ-6 and naming the deck, in both cases\n"
        f"ACTUAL: {caught_missing.value!s} | {caught_tool.value!s}\n"
        "GUIDANCE: stop with the deck's name; never return zero slides"
    )
    assert shutil.which("soffice") is not None, "ARRANGE: LibreOffice must be on PATH for this test"
