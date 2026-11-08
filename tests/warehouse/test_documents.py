"""RED tests for SLICE-3 batch 6c-ii: reading PDF pages and text files.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_DOCUMENTS)
- Authority: AUTHORITATIVE for the warehouse and its Ingest (SLICE-3)
- Clauses covered: POST-READ-2, ERRORS-READ-2, POST-READ-3 (unparked: Z-22 design A, Ketema)
- Requirements: REQ-25, REQ-28, REQ-53, REQ-54

The implementation is src/warehouse/documents.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites POST-READ-2 or ERRORS-READ-2.
  C2 VALUABLE: a real three-page PDF with a blank middle page, read by the real Poppler tools;
     exact page numbers and texts; refusal by name for a missing file, a non-PDF, missing tools
     and a page-count mismatch.
  C3 NON-DUPLICATIVE: test 1 pins the pages returned; test 2 pins every refusal.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.

TEST DOUBLE CONTRACT (CL13): the fake pdfinfo in test 2 honours the one behaviour the contract
uses from the real tool, a line "Pages: <n>" on stdout with exit status 0, and nothing else.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import documents as impl

# Risk tier: HIGH. Dropped or renumbered pages make every page citation point at the wrong text.


def _pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one page per string; an empty string is a blank page."""
    objs: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        content = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode() if text else b""
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def test_every_pdf_page_is_returned_in_order_with_blank_pages_kept(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_pdf_pages(), PDF_TEXT_COMMAND, PDF_INFO_COMMAND,
      PAGE_BREAK
    - Enforces: POST-READ-2
    - Category: positive, boundary (blank page in the middle)
    - Risk tier: HIGH
    - Pyramid level: Integration (real pdftotext and pdfinfo)
    """
    pdf = tmp_path / "three.pdf"
    pdf.write_bytes(_pdf(["Alpha", "", "Gamma"]))
    stdout = subprocess.run(  # noqa: S603 - fixed contract command on a file this test wrote
        [*contract.PDF_TEXT_COMMAND, str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    want = contract.expected_pdf_pages(stdout, 3)
    got = impl.read_pdf_pages(pdf)
    got_view = [(p.page, p.text) for p in got]
    assert got_view == [(p.page, p.text) for p in want], (
        "test_every_pdf_page_is_returned_in_order_with_blank_pages_kept FAILED\n"
        "POST-READ-2 violation: the pages differ from pdftotext's pages\n"
        f"EXPECTED: {[(p.page, p.text) for p in want]!r}\n"
        f"ACTUAL: {got_view!r}\n"
        "GUIDANCE: one page per PDF page, numbered from 1, each text exactly as pdftotext wrote it"
    )
    assert [p.page for p in got] == [1, 2, 3], (
        "test_every_pdf_page_is_returned_in_order_with_blank_pages_kept FAILED\n"
        "POST-READ-2 violation: a page was dropped or renumbered\n"
        "EXPECTED: [1, 2, 3]\n"
        f"ACTUAL: {[p.page for p in got]!r}\n"
        "GUIDANCE: keep the blank page so page N stored is page N of the PDF"
    )
    placed = ("Alpha" in got[0].text, got[1].text.strip(), "Gamma" in got[2].text)
    assert placed == (True, "", True), (
        "test_every_pdf_page_is_returned_in_order_with_blank_pages_kept FAILED\n"
        "POST-READ-2 violation: page texts are not where the PDF has them\n"
        "EXPECTED: 'Alpha' on page 1, a blank page 2, 'Gamma' on page 3\n"
        f"ACTUAL: {got_view!r}\n"
        "GUIDANCE: split pdftotext output on PAGE_BREAK, in order"
    )
    assert (impl.PDF_TEXT_COMMAND, impl.PDF_INFO_COMMAND, impl.PAGE_BREAK) == (
        contract.PDF_TEXT_COMMAND,
        contract.PDF_INFO_COMMAND,
        contract.PAGE_BREAK,
    ), (
        "test_every_pdf_page_is_returned_in_order_with_blank_pages_kept FAILED\n"
        "POST-READ-2 violation: the commands or page break differ from the contract\n"
        "EXPECTED: the contract's PDF_TEXT_COMMAND, PDF_INFO_COMMAND and PAGE_BREAK\n"
        "ACTUAL: different values\n"
        "GUIDANCE: use the contracted Poppler commands"
    )


def test_unreadable_or_incomplete_pdfs_stop_with_the_file_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_pdf_pages(), SourceReadError
    - Enforces: ERRORS-READ-2
    - Category: negative
    - Risk tier: HIGH
    - Pyramid level: Integration (real tools; a fake pdfinfo for the count mismatch)
    - Equivalence partition: missing file; bytes that are not a PDF; Poppler not on PATH;
      pdfinfo reporting more pages than pdftotext produced.
    """
    with pytest.raises(contract.SourceReadError):
        contract.expected_pdf_pages("a\fb\f", 3)

    good = tmp_path / "good.pdf"
    good.write_bytes(_pdf(["Alpha", "Beta"]))
    not_pdf = tmp_path / "notes.pdf"
    not_pdf.write_bytes(b"this is not a pdf")
    for label, path in (("missing file", tmp_path / "absent.pdf"), ("not a PDF", not_pdf)):
        with pytest.raises(impl.SourceReadError) as caught:
            impl.read_pdf_pages(path)
        named = ("ERRORS-READ-2" in str(caught.value), path.name in str(caught.value))
        assert named == (True, True), (
            "test_unreadable_or_incomplete_pdfs_stop_with_the_file_named FAILED\n"
            f"ERRORS-READ-2 violation for {label}: the refusal does not cite the clause and file\n"
            f"EXPECTED: SourceReadError citing ERRORS-READ-2 and naming {path.name!r}\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: stop the Ingest and name the file the tools could not read"
        )

    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    with monkeypatch.context() as m:
        m.setenv("PATH", str(empty_bin))
        with pytest.raises(impl.SourceReadError) as caught_tool:
            impl.read_pdf_pages(good)
    assert "ERRORS-READ-2" in str(caught_tool.value), (
        "test_unreadable_or_incomplete_pdfs_stop_with_the_file_named FAILED\n"
        "ERRORS-READ-2 violation: a missing Poppler tool was not reported\n"
        "EXPECTED: SourceReadError citing ERRORS-READ-2\n"
        f"ACTUAL: {caught_tool.value!s}\n"
        "GUIDANCE: a missing command stops the Ingest; it never yields zero pages"
    )

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake = fake_bin / "pdfinfo"
    fake.write_text("#!/bin/sh\necho 'Pages:          5'\n")
    fake.chmod(0o755)
    with monkeypatch.context() as m:
        poppler_dir = Path(shutil.which("pdftotext") or "pdftotext").parent
        m.setenv("PATH", f"{fake_bin}:{poppler_dir}:/usr/bin:/bin")
        with pytest.raises(impl.SourceReadError) as caught_count:
            impl.read_pdf_pages(good)
    counted = ("ERRORS-READ-2" in str(caught_count.value), "5" in str(caught_count.value))
    assert counted == (True, True), (
        "test_unreadable_or_incomplete_pdfs_stop_with_the_file_named FAILED\n"
        "ERRORS-READ-2 violation: a page-count mismatch was not refused\n"
        "EXPECTED: SourceReadError citing ERRORS-READ-2 with both counts (2 and 5)\n"
        f"ACTUAL: {caught_count.value!s}\n"
        "GUIDANCE: compare pdftotext's pages with pdfinfo's count and stop when they differ"
    )


def test_text_file_is_one_page_decoded_without_replacement(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_text_pages(), TEXT_PAGE, READ_ENCODINGS
    - Enforces: POST-READ-3 (and ERRORS-READ-1 for a missing text file)
    - Category: positive, boundary (Latin-1 fallback), negative
    - Risk tier: HIGH: a replaced letter changes a place name the AI quotes
    - Pyramid level: Unit (files on disk)
    - Equivalence partition: UTF-8 Markdown; Latin-1 text ("Doña", as in the census file);
      missing file.
    """
    cases = (
        ("utf8.md", b"# Taxonomy\nClassic Food Desert\n"),
        ("latin.txt", b"Do\xf1a Ana County\n"),
    )
    for name, raw in cases:
        path = tmp_path / name
        path.write_bytes(raw)
        want_pages, want_enc = contract.expected_text_pages(raw)
        got_pages, got_enc = impl.read_text_pages(path)
        got_view = ([(p.page, p.text) for p in got_pages], got_enc)
        assert got_view == ([(p.page, p.text) for p in want_pages], want_enc), (
            "test_text_file_is_one_page_decoded_without_replacement FAILED\n"
            f"POST-READ-3 violation for {name}: page, text or encoding differs\n"
            f"EXPECTED: {([(p.page, p.text) for p in want_pages], want_enc)!r}\n"
            f"ACTUAL: {got_view!r}\n"
            "GUIDANCE: one page numbered TEXT_PAGE, decoded whole by the first of READ_ENCODINGS "
            "that fits, no byte replaced"
        )
    assert "\ufffd" not in impl.read_text_pages(tmp_path / "latin.txt")[0][0].text, (
        "test_text_file_is_one_page_decoded_without_replacement FAILED\n"
        "POST-READ-3 violation: a replacement character appeared in a Latin-1 file\n"
        "EXPECTED: 'Doña Ana County'\n"
        f"ACTUAL: {impl.read_text_pages(tmp_path / 'latin.txt')[0][0].text!r}\n"
        "GUIDANCE: fall back to Latin-1 for the whole file instead of replacing bytes"
    )
    with pytest.raises(impl.SourceReadError) as caught:
        impl.read_text_pages(tmp_path / "absent.md")
    assert "absent.md" in str(caught.value), (
        "test_text_file_is_one_page_decoded_without_replacement FAILED\n"
        "ERRORS-READ-1 violation: a missing text file was not refused by name\n"
        "EXPECTED: SourceReadError naming 'absent.md'\n"
        f"ACTUAL: {caught.value!s}\n"
        "GUIDANCE: stop with the file name"
    )
