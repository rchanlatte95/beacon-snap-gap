# SLICE-3 decision queue (QS6 / CL4-A)

Only Ketema unparks an entry. Decision-model support (jev-1.14, 2026-11-08) is advice, not a decision.

## Q-1: spreadsheet reader (batch 6c-iv)

- **Decided By: User** (Ketema, 2026-11-08): A.

- **Depends:** the spreadsheet reader clauses (not yet written) and their tests.
- **Options:**
  - **A.** LibreOffice (present) converts every sheet of `.xls` and `.xlsx` to CSV; the contracted `read_delimited` reads each CSV as text. One path for both formats. Parity with the first build: 62 sheets, 59 equal row counts, 99.64% of 2,980,074 cells equal.
  - **B.** DuckDB `read_xlsx` for `.xlsx` (sheet names read from the workbook XML); LibreOffice converts `.xls` to `.xlsx` first.
  - **C.** Install `python-calamine` (new dependency) for both formats.
- **Decision model:** A 81%, B 18%.
- **Recommendation:** A.

## Q-2: spreadsheet dates (batch 6c-iv)

- **Decided By: User** (Ketema, 2026-11-08): B, "One format. be consistent with what already exists." Then: "converge on 1 date format and make sure we always use that one."
- **Converged format:** `YYYY-MM-DD` (the contract's `DATE_PATTERN`, already used by the registry and provenance). Every first-build sheet date is midnight, so nothing is lost. A date cell with a time of day other than midnight stops the Ingest naming the file; no second format is introduced.
- **Existing formats:** the first build's 182 sheet tables hold 8,314 date cells, all `YYYY-MM-DD 00:00:00` (none has a time of day); the registry and provenance dates are `YYYY-MM-DD`.

- **Depends:** Q-1 option A.
- **Conflict:** the first build stored a date cell as pandas wrote it, `2024-08-01 00:00:00`; LibreOffice writes what the sheet shows, `08/01/2024`.
- **Options:** **A.** store the text as the sheet displays it; **B.** store a parsed date text, which needs a date rule per sheet.
- **Decision model:** A acceptable 88%.
- **Recommendation:** A. It is the source's own text, and every value stays text.

## Q-3: PPTX reader (batch 6c-iv)

- **Decided By: User** (Ketema, 2026-11-08): A.

- **Depends:** the PPTX reader clause (not yet written).
- **Options:** **A.** LibreOffice converts the deck to PDF, then `pdftotext`, one page per slide (both present); **B.** install `python-pptx`.
- **Decision model:** A 88%.
- **Recommendation:** A.

## Q-4: keep blank PDF pages (POST-READ-2, unparked)

- **Decided By: User** (Ketema, 2026-11-08): A. POST-READ-2 and ERRORS-READ-2 unparked.

- **Clause text:** "returns one DocumentPage per page that PDF_INFO_COMMAND reports, numbered from 1 in order, blank pages kept with their own text".
- **Conflict:** the first build dropped blank pages, so a document's stored page numbers could differ from the PDF's. REQ-25 says "load ... every retained source file" but does not say whether every page counts.
- **Options:** **A.** keep blank pages, so page N in the warehouse is page N of the PDF; **B.** drop blank pages, as the first build did.
- **Decision model:** support that keeping them is within scope 63%.
- **Recommendation:** A. Citations by page number stay true to the PDF.
- **Dependent:** POST-READ-2, ERRORS-READ-2 (page-count check), and their tests.

## Q-5: decode text without replacing bytes (POST-READ-3, unparked)

- **Decided By: User** (Ketema, 2026-11-08): neither A nor B alone, "the solution is a combination of both. do not let a single row exclude an entire file. allow the placeholders, but log it so that it is surfaced."
- **Effect on POST-READ-3:** an undecodable byte becomes a replacement character instead of stopping the file; every replacement is recorded (file, page or row, count) and surfaced. POST-READ-3 is amended accordingly and unparked; the same rule applies to delimited files, so one bad row never drops a table.
- **Design, Decided By: User** (Ketema, 2026-11-08): "A." Decode the whole file with UTF-8, else Latin-1, and report the encoding per file; on real data this keeps "Doña" (census population file), where UTF-8 with replacement gave "Do�a". Malformed delimited rows are set aside and returned with line, error type and raw text (POST-READ-1). Decision model, advisory: A over B 71%.

- **Clause text:** "decoded by the first of READ_ENCODINGS that decodes it without error ... no byte is replaced or dropped".
- **Conflict:** REQ-28 says "leave them unaltered". The decision model reads that as the files on disk only (support 38% that it covers the loaded text). The first build decoded with `errors="replace"`, which silently changed undecodable bytes in the loaded text.
- **Options:** **A.** REQ-28 also covers the loaded text: try UTF-8, then Latin-1, as `read_delimited` already does, and stop on failure; **B.** REQ-28 covers only the files on disk: allow replacement characters.
- **Recommendation:** A. It matches the contracted delimited reader, and the failure stays visible.
- **Dependent:** POST-READ-3 and its test.
