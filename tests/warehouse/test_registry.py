"""RED tests for SLICE-3 batch 6b: the committed source registry and fail-fast reading.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_REGISTRY)
- Authority: AUTHORITATIVE for the warehouse and its Ingest (SLICE-3)
- Clauses covered: POST-REG-1, POST-REG-2, ERRORS-REG-1, ERRORS-REG-2, FORBIDDEN-REG-1,
  POST-READ-1, ERRORS-READ-1
- Requirements: REQ-25, REQ-26, REQ-28, REQ-29

The implementations are src/warehouse/registry.py and src/warehouse/reader.py. They do not
import the contract (CL11-F); these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites a clause present in CONTRACT_REGISTRY.
  C2 VALUABLE: exact entry fields, exact-only matching (near-miss paths and member names must
     fail), every invalid registry shape, exact rows and VARCHAR types, the encoding chosen, and
     a raised error for an unreadable file are asserted.
  C3 NON-DUPLICATIVE: test 1 pins the registry; test 2 pins reading.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.
"""

import tomllib
from pathlib import Path

import duckdb
import pytest
from contracts import warehouse_contract as contract
from src.warehouse import reader as read_impl
from src.warehouse import registry as reg_impl

# Risk tier: HIGH. A substring match or a silent read failure drops or mislabels a source with
# no signal, which is the defect recorded for the first build.

REGISTRY_TEXT = """
[[source]]
path = "cache:sba/FOIA_7a_FY2020_Present_asof_260930.csv"
ds = "DS-X5"
group = "sba"
file_format = "csv"
reference_end = "2026-09-30"
reference_basis = "measured: ApprovalDate maximum"
publisher = "U.S. Small Business Administration"
as_of = "2026-09-30 (file name)"

[[source]]
path = "cache:usda-fns-snap/snap-zip-fy69tocurrent-10.zip"
ds = "DS-X1"
group = "usda-fns-snap"
file_format = "xls"

  [[source.member]]
  name = "FY24.xls"
  file_format = "xls"
  reference_end = "2024-09-30"
  reference_basis = "file name FY24"

[[source]]
path = "cache:census-pulse-2024/HPS_Phase4Cycle01_PUF_CSV.zip"
ds = "DS-X18"
group = "census-pulse-2024"
file_format = "csv"
reference_end = "2024-01-29"
reference_basis = "documentation: cycle 1 collection end"
release_id = "pulse-2024-cycle01"
"""


def test_registry_entries_match_only_by_exact_path_and_member_name(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract validate_registry(), expected_registry_entry(),
      expected_member_scope()
    - Enforces: POST-REG-1, ERRORS-REG-1, POST-REG-2, ERRORS-REG-2, FORBIDDEN-REG-1
    - Category: positive, negative, boundary
    - Risk tier: HIGH
    - Pyramid level: Unit (TOML file on disk)
    - Equivalence partition: stated and unstated facts; exact path, near-miss paths (suffix,
      case, prefix); archive with listed members (listed, unlisted) and without (inherits);
      eight invalid registry shapes.
    """
    reg_file = tmp_path / "source_registry.toml"
    reg_file.write_text(REGISTRY_TEXT)
    got = reg_impl.load_registry(reg_file)
    want = contract.validate_registry(tomllib.loads(REGISTRY_TEXT))
    got_fields = [
        (
            e.path,
            e.ds,
            e.group,
            e.file_format,
            e.reference_end,
            e.reference_basis,
            e.is_base_geography,
            e.release_id,
            e.publisher,
            e.license,
            e.as_of,
            tuple((m.name, m.file_format, m.reference_end, m.reference_basis) for m in e.members),
        )
        for e in got
    ]
    want_fields = [
        (
            e.path,
            e.ds,
            e.group,
            e.file_format,
            e.reference_end,
            e.reference_basis,
            e.is_base_geography,
            e.release_id,
            e.publisher,
            e.license,
            e.as_of,
            tuple((m.name, m.file_format, m.reference_end, m.reference_basis) for m in e.members),
        )
        for e in want
    ]
    assert got_fields == want_fields, (
        "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
        "POST-REG-1 violation: loaded entries differ from the registry's stated facts\n"
        f"EXPECTED: {want_fields!r}\n"
        f"ACTUAL: {got_fields!r}\n"
        "GUIDANCE: one entry per [[source]]; unstated publisher, license, as_of and basis read "
        "'not recorded'"
    )
    assert got[0].license == contract.NOT_RECORDED, (
        "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
        "POST-REG-1 violation: an unstated license was not recorded as 'not recorded'\n"
        f"EXPECTED: {contract.NOT_RECORDED!r}\n"
        f"ACTUAL: {got[0].license!r}\n"
        "GUIDANCE: never infer a fact the registry does not state"
    )

    exact = "cache:sba/FOIA_7a_FY2020_Present_asof_260930.csv"
    assert reg_impl.registry_entry(got, exact).ds == "DS-X5", (
        "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
        "POST-REG-2 violation: the exact path did not return its entry\n"
        "EXPECTED: entry with ds 'DS-X5'\n"
        "ACTUAL: a different entry\n"
        "GUIDANCE: return the entry whose path equals the retained file's path"
    )
    for near_miss in (exact + ".bak", exact.upper(), exact[:-4], "cache:sba/FOIA_7a"):
        with pytest.raises(contract.UnregisteredSourceError):
            contract.expected_registry_entry(want, near_miss)
        with pytest.raises(reg_impl.UnregisteredSourceError) as caught:
            reg_impl.registry_entry(got, near_miss)
        assert near_miss in str(caught.value), (
            "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
            f"ERRORS-REG-2 / FORBIDDEN-REG-1 violation for {near_miss!r}: not refused by name\n"
            "EXPECTED: UnregisteredSourceError naming the file\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: only exact path equality matches; name the unregistered file"
        )

    series = reg_impl.registry_entry(got, "cache:usda-fns-snap/snap-zip-fy69tocurrent-10.zip")
    assert reg_impl.member_scope(series, "FY24.xls") == ("xls", "2024-09-30"), (
        "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
        "POST-REG-2 violation: a listed member did not return its own facts\n"
        "EXPECTED: ('xls', '2024-09-30')\n"
        f"ACTUAL: {reg_impl.member_scope(series, 'FY24.xls')!r}\n"
        "GUIDANCE: a listed member uses its own format and reference end"
    )
    for unlisted in ("FY23.xls", "fy24.xls", "FY24.xlsx"):
        with pytest.raises(reg_impl.UnregisteredSourceError):
            reg_impl.member_scope(series, unlisted)
    pulse = reg_impl.registry_entry(got, "cache:census-pulse-2024/HPS_Phase4Cycle01_PUF_CSV.zip")
    assert reg_impl.member_scope(pulse, "pulse2024_puf_01.csv") == ("csv", "2024-01-29"), (
        "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
        "POST-REG-2 violation: a member of an entry without listed members did not inherit\n"
        "EXPECTED: ('csv', '2024-01-29')\n"
        f"ACTUAL: {reg_impl.member_scope(pulse, 'pulse2024_puf_01.csv')!r}\n"
        "GUIDANCE: an entry without listed members passes its own facts to every member"
    )

    base = 'path = "p"\nds = "DS-X5"\ngroup = "g"\nfile_format = "csv"\n'
    bad_registries = [
        ("no entries", "title = 'x'\n"),
        ("no ds", '[[source]]\npath = "p"\ngroup = "g"\nfile_format = "csv"\n'),
        ("duplicate path", f"[[source]]\n{base}\n[[source]]\n{base}"),
        (
            "unknown format",
            '[[source]]\npath = "p"\nds = "d"\ngroup = "g"\nfile_format = "parquet"\n',
        ),
        (
            "not a real date",
            f'[[source]]\n{base}reference_end = "2024-13-01"\nreference_basis = "x"\n',
        ),
        ("end without basis", f'[[source]]\n{base}reference_end = "2024-12-31"\n'),
        ("empty release", f'[[source]]\n{base}release_id = ""\n'),
        (
            "repeated member",
            f'[[source]]\n{base}[[source.member]]\nname = "a"\nfile_format = "csv"\n'
            '[[source.member]]\nname = "a"\nfile_format = "csv"\n',
        ),
    ]
    for label, text in bad_registries:
        with pytest.raises(contract.RegistryError):
            contract.validate_registry(tomllib.loads(text))
        bad_file = tmp_path / f"bad_{label.replace(' ', '_')}.toml"
        bad_file.write_text(text)
        with pytest.raises(reg_impl.RegistryError):
            reg_impl.load_registry(bad_file)

    assert reg_impl.REGISTRY_FILE == contract.REGISTRY_FILE, (
        "test_registry_entries_match_only_by_exact_path_and_member_name FAILED\n"
        "ERRORS-REG-2 violation: registry location differs from the contract\n"
        f"EXPECTED: {contract.REGISTRY_FILE!r}\n"
        f"ACTUAL: {reg_impl.REGISTRY_FILE!r}\n"
        "GUIDANCE: the committed registry lives at the contract's location"
    )


def test_delimited_read_keeps_text_reports_encoding_and_fails_fast(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract READ_ENCODINGS, RejectedRow
    - Enforces: POST-READ-1, ERRORS-READ-1 (Z-22: a malformed row never excludes the file)
    - Category: positive, negative, boundary
    - Risk tier: HIGH
    - Pyramid level: Integration (DuckDB reading real files)
    - Equivalence partition: UTF-8 CSV with leading-zero codes; Latin-1 CSV; pipe-delimited file
      without a header; a CSV with one row of too many columns; missing file; a directory.
    """
    con = duckdb.connect(":memory:")

    utf8 = tmp_path / "codes.csv"
    utf8.write_bytes(b"GEO_ID,code,name\n1400000US12095016510,007,Orlando\n")
    rel, enc, rejects = read_impl.read_delimited(con, utf8)
    type_names = {str(t) for t in rel.types}
    assert (rel.fetchall(), type_names, enc, rejects) == (
        [("1400000US12095016510", "007", "Orlando")],
        {"VARCHAR"},
        "utf-8",
        (),
    ), (
        "test_delimited_read_keeps_text_reports_encoding_and_fails_fast FAILED\n"
        "POST-READ-1 violation: rows, column types or encoding wrong for a UTF-8 file\n"
        "EXPECTED: one row with code '007', all VARCHAR, encoding 'utf-8'\n"
        f"ACTUAL: {rel.fetchall()!r}, {type_names!r}, {enc!r}\n"
        "GUIDANCE: keep every value as text exactly as written; report the encoding used"
    )

    latin = tmp_path / "latin.csv"
    latin.write_bytes(b"name\ncaf\xe9\n")
    rel_l, enc_l, _ = read_impl.read_delimited(con, latin)
    assert (rel_l.fetchall(), enc_l) == ([("caf\u00e9",)], "latin-1"), (
        "test_delimited_read_keeps_text_reports_encoding_and_fails_fast FAILED\n"
        "POST-READ-1 violation: a Latin-1 file was not decoded after UTF-8 failed\n"
        "EXPECTED: [('caf\u00e9',)], 'latin-1'\n"
        f"ACTUAL: {rel_l.fetchall()!r}, {enc_l!r}\n"
        "GUIDANCE: try READ_ENCODINGS in order and report the one that succeeded"
    )

    piped = tmp_path / "blocks.pl"
    piped.write_bytes(b"PLST|FL|750|12\nPLST|FL|750|13\n")
    rel_p, _, _ = read_impl.read_delimited(con, piped, delimiter="|", header=False)
    assert rel_p.fetchall() == [("PLST", "FL", "750", "12"), ("PLST", "FL", "750", "13")], (
        "test_delimited_read_keeps_text_reports_encoding_and_fails_fast FAILED\n"
        "POST-READ-1 violation: a headerless pipe file did not keep every row\n"
        "EXPECTED: both rows as text\n"
        f"ACTUAL: {rel_p.fetchall()!r}\n"
        "GUIDANCE: a headerless file keeps its first line as data"
    )

    ragged = tmp_path / "ragged.csv"
    ragged.write_bytes(b"a,b\n1,2\n3,4,5\n6,7\n")
    rel_r, _, rejects_r = read_impl.read_delimited(con, ragged)
    want_reject = contract.RejectedRow(line=3, error_type="TOO MANY COLUMNS", raw="3,4,5")
    got_view = (rel_r.fetchall(), [(r.line, r.error_type, r.raw) for r in rejects_r])
    assert got_view == (
        [("1", "2"), ("6", "7")],
        [(want_reject.line, want_reject.error_type, want_reject.raw)],
    ), (
        "test_delimited_read_keeps_text_reports_encoding_and_fails_fast FAILED\n"
        "POST-READ-1 violation: a malformed row excluded the file or was not reported\n"
        "EXPECTED: rows [('1', '2'), ('6', '7')] and one rejected row at line 3, "
        "'TOO MANY COLUMNS', raw '3,4,5'\n"
        f"ACTUAL: {got_view!r}\n"
        "GUIDANCE: load every parsable row and return each unparsable row with its line (Z-22)"
    )

    for label, bad in (("missing", tmp_path / "absent.csv"), ("directory", tmp_path)):
        with pytest.raises(read_impl.SourceReadError) as caught:
            read_impl.read_delimited(con, bad)
        # The reader quotes the path with !r, which doubles each backslash of a Windows path.
        named = (str(bad), str(bad).replace("\\", "\\\\"))
        assert any(form in str(caught.value) for form in named), (
            "test_delimited_read_keeps_text_reports_encoding_and_fails_fast FAILED\n"
            f"ERRORS-READ-1 violation for {label}: the error does not name the file\n"
            f"EXPECTED: SourceReadError naming {str(bad)!r}\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: stop with the file name and the reader's message; never return empty"
        )

    assert tuple(read_impl.READ_ENCODINGS) == contract.READ_ENCODINGS, (
        "test_delimited_read_keeps_text_reports_encoding_and_fails_fast FAILED\n"
        "POST-READ-1 violation: encoding order differs from the contract\n"
        f"EXPECTED: {contract.READ_ENCODINGS!r}\n"
        f"ACTUAL: {tuple(read_impl.READ_ENCODINGS)!r}\n"
        "GUIDANCE: the encodings and their order equal the contract's"
    )
