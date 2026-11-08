"""RED tests for SLICE-3 batch 6c-v(a): archive members, formats, and member sources.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_DOCUMENTS, CONTRACT_REGISTRY)
- Authority: AUTHORITATIVE for the warehouse and its Ingest (SLICE-3)
- Clauses covered: POST-ARCH-1, ERRORS-ARCH-1, POST-ARCH-2, ERRORS-ARCH-2, POST-REG-2, ERRORS-REG-2
- Requirements: REQ-25, REQ-26, REQ-28

The implementation is src/warehouse/archive.py (not yet created). It does not import
the contract (CL11-F); these tests import both to bridge specification and implementation.

Expected public callable surface for src/warehouse/archive (mirroring contract oracles):
- archive_members(zip_path: Path, entry: RegistryEntry) -> tuple[ArchiveMember, ...]
  (argument order as in POST-ARCH-1)
- member_source(zip_path: Path, member: str, workdir: Path) -> str
- ArchiveMember(name: str, file_format: str, reference_end: str | None)
- ArchiveMemberError: the same class as src.warehouse.registry.ArchiveMemberError (defined in the
  registry, re-exported here), never the contract's class (CL11-F)

FOUR-CRITERIA TEST VALIDITY GATE (all tests):
  C1 VALID: every assertion cites a clause ID present in contracts/warehouse_contract.py
     (POST-ARCH-1, ERRORS-ARCH-1, POST-ARCH-2, ERRORS-ARCH-2, POST-REG-2, ERRORS-REG-2).
  C2 VALUABLE: exact member names, file formats, and reference ends against the contract oracle;
     skipping of directories, __MACOSX, and hidden entries; shapefile companion part exclusion
     (.shp listed alone, .shx/.dbf/.prj/.xml not listed as distinct members); exact /vsizip/
     path format for shapefiles; byte-identical extraction in workdir for non-shapefile members;
     fail-fast ArchiveMemberError on unknown extension or unlisted member in listed archive;
     SourceReadError on missing or invalid zip archive.
  C3 NON-DUPLICATIVE:
     - test_member_scope_unlisted_and_listed: pins member_scope format-by-extension vs listed
       members (POST-REG-2, ERRORS-REG-2, ERRORS-ARCH-1).
     - test_archive_members_skips_internal_and_groups_shapefile: pins archive_members member
       discovery, ordering, and shapefile part grouping against expected_archive_members
       (POST-ARCH-1).
     - test_archive_members_raises_on_unknown_extension_or_corrupt_zip: pins fail-fast errors on
       missing/corrupt archives and uncontracted member extensions (ERRORS-ARCH-1).
     - test_member_source_shapefile_vsizip_and_extracted_bytes: pins member_source returning
       /vsizip/ path for shapefiles and byte-identical extracted files for other members
       (POST-ARCH-2).
     - test_member_source_raises_when_member_missing: pins ArchiveMemberError when member does
       not exist in the archive (ERRORS-ARCH-2).
  C4 NOT FUTURE-EDIT: every test enforces a contracted clause committed in
     contracts/warehouse_contract.py (b27e929).
"""

import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from contracts import warehouse_contract as contract
from src.warehouse import archive as impl
from src.warehouse import reader as read_impl
from src.warehouse import registry as reg_impl

# Risk tier: HIGH. Unlisted archive members with wrong format or dropped companion parts
# corrupt Ingest and silently drop datasets or misassign format handlers.


def _make_registry_entry(
    tmp_path: Path,
    *,
    path: str,
    file_format: str = "csv",
    reference_end: str | None = "2026-09-30",
    members: Sequence[Mapping[str, str | None]] | None = None,
) -> reg_impl.RegistryEntry:
    """Build a validated RegistryEntry via the implementation's registry loader."""
    toml_lines = [
        "[[source]]",
        f'path = "{path}"',
        'ds = "DS-TEST"',
        'group = "test_group"',
        f'file_format = "{file_format}"',
    ]
    if reference_end is not None:
        toml_lines.extend(
            [
                f'reference_end = "{reference_end}"',
                'reference_basis = "test basis"',
            ]
        )
    if members:
        for m in members:
            toml_lines.extend(
                [
                    "[[source.member]]",
                    f'name = "{m["name"]}"',
                    f'file_format = "{m["file_format"]}"',
                ]
            )
            if m.get("reference_end") is not None:
                toml_lines.extend(
                    [
                        f'reference_end = "{m["reference_end"]}"',
                        'reference_basis = "member test basis"',
                    ]
                )
    reg_file = tmp_path / f"registry_{abs(hash(path))}.toml"
    reg_file.write_text("\n".join(toml_lines) + "\n", encoding="utf-8")
    loaded = reg_impl.load_registry(reg_file)
    return loaded[0]


def test_member_scope_unlisted_and_listed(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_member_scope(), MEMBER_FORMAT_BY_EXTENSION,
      ArchiveMemberError
    - Enforces: POST-REG-2, ERRORS-REG-2, ERRORS-ARCH-1
    - Category: positive, boundary, error
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition: unlisted archive with contracted extensions
      (.csv, .xlsx, .shp, .sas7bdat); unlisted archive with uncontracted extension (.bin);
      archive with listed members (found, not found).
    """
    # Unlisted members: format derives from extension (MEMBER_FORMAT_BY_EXTENSION)
    unlisted_entry = _make_registry_entry(
        tmp_path,
        path="cache:census/unlisted_archive.zip",
        reference_end="2024-12-31",
    )

    contract_entry = contract.RegistryEntry(
        path=unlisted_entry.path,
        ds=unlisted_entry.ds,
        group=unlisted_entry.group,
        file_format=unlisted_entry.file_format,
        reference_end=unlisted_entry.reference_end,
        reference_basis=unlisted_entry.reference_basis,
        is_base_geography=unlisted_entry.is_base_geography,
        release_id=unlisted_entry.release_id,
        publisher=unlisted_entry.publisher,
        license=unlisted_entry.license,
        as_of=unlisted_entry.as_of,
        members=(),
    )

    for member_name in [
        "data/table.csv",
        "docs/dict.XLSX",
        "gis/boundary.shp",
        "raw/pulse.sas7bdat",
        "notes/readme.TXT",
    ]:
        oracle_fmt, oracle_end = contract.expected_member_scope(contract_entry, member_name)
        actual_fmt, actual_end = reg_impl.member_scope(unlisted_entry, member_name)
        assert (actual_fmt, actual_end) == (oracle_fmt, oracle_end), (
            f"WHAT: test_member_scope_unlisted_and_listed FAILED\n"
            f"WHY: POST-REG-2 violation - unlisted member format must match extension\n"
            f"EXPECTED: {(oracle_fmt, oracle_end)!r}\n"
            f"ACTUAL: {(actual_fmt, actual_end)!r}\n"
            f"GUIDANCE: Derive unlisted member format from lower-case file extension"
        )

    # ERRORS-ARCH-1: unlisted member with uncontracted extension raises ArchiveMemberError
    with pytest.raises(reg_impl.ArchiveMemberError) as exc_info:
        reg_impl.member_scope(unlisted_entry, "payload.unknown_ext")
    assert "ERRORS-ARCH-1" in str(exc_info.value), (
        "WHAT: test_member_scope_unlisted_and_listed FAILED\n"
        "WHY: ERRORS-ARCH-1 violation - unknown extension must cite ERRORS-ARCH-1\n"
        "EXPECTED: error message citing 'ERRORS-ARCH-1'\n"
        f"ACTUAL: {str(exc_info.value)!r}\n"
        "GUIDANCE: Raise ArchiveMemberError citing ERRORS-ARCH-1 on uncontracted extension"
    )

    # Listed members: exact listing required
    listed_entry = _make_registry_entry(
        tmp_path,
        path="cache:snap/listed_archive.zip",
        reference_end="2025-06-30",
        members=[
            {"name": "FY24.xls", "file_format": "xls", "reference_end": "2024-09-30"},
            {"name": "FY25.xls", "file_format": "xls", "reference_end": "2025-09-30"},
        ],
    )
    actual_listed_fmt, actual_listed_end = reg_impl.member_scope(listed_entry, "FY24.xls")
    assert (actual_listed_fmt, actual_listed_end) == ("xls", "2024-09-30"), (
        "WHAT: test_member_scope_unlisted_and_listed FAILED\n"
        "WHY: POST-REG-2 violation - listed member must return its own facts\n"
        "EXPECTED: ('xls', '2024-09-30')\n"
        f"ACTUAL: {(actual_listed_fmt, actual_listed_end)!r}\n"
        "GUIDANCE: Return exact listed member format and reference_end"
    )
    with pytest.raises(reg_impl.UnregisteredSourceError) as exc_unreg:
        reg_impl.member_scope(listed_entry, "unlisted_file.xls")
    assert "ERRORS-REG-2" in str(exc_unreg.value), (
        "WHAT: test_member_scope_unlisted_and_listed FAILED\n"
        "WHY: ERRORS-REG-2 violation - missing listed member must raise UnregisteredSourceError\n"
        "EXPECTED: error message citing 'ERRORS-REG-2'\n"
        f"ACTUAL: {str(exc_unreg.value)!r}\n"
        "GUIDANCE: Raise UnregisteredSourceError when listed archive lacks member"
    )


def test_archive_members_skips_internal_and_groups_shapefile(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_archive_members(), ArchiveMember,
      SHAPEFILE_PART_EXTENSIONS
    - Enforces: POST-ARCH-1
    - Category: positive, boundary
    - Risk tier: HIGH
    - Pyramid level: Unit (zip archive fixture)
    - Equivalence partition: zip archive containing directories, __MACOSX resource fork,
      hidden dot-files, standard data files (.csv, .xlsx), shapefile group (.shp, .shx,
      .dbf, .prj, .shp.xml), and independent text files.
    """
    zip_path = tmp_path / "complex_archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        # Directory entry
        zf.writestr("subfolder/", "")
        # __MACOSX internal metadata
        zf.writestr("__MACOSX/._subfolder", b"mac-resource-fork")
        zf.writestr("__MACOSX/subfolder/._data.csv", b"mac-resource-fork")
        # Hidden files
        zf.writestr(".DS_Store", b"desktop-db")
        zf.writestr("subfolder/.hidden.txt", b"hidden")
        # Valid data file
        zf.writestr("subfolder/data.csv", "id,val\n1,10\n")
        # Valid spreadsheet
        zf.writestr("docs/summary.xlsx", b"fake-xlsx-bytes")
        # Shapefile components (.shp plus companion files)
        zf.writestr("gis/tracts.shp", b"shapefile-shp-bytes")
        zf.writestr("gis/tracts.shx", b"shapefile-shx-bytes")
        zf.writestr("gis/tracts.dbf", b"shapefile-dbf-bytes")
        zf.writestr("gis/tracts.prj", b"shapefile-prj-bytes")
        zf.writestr("gis/tracts.cpg", b"shapefile-cpg-bytes")
        zf.writestr("gis/tracts.shp.xml", b"<xml>metadata</xml>")
        # Another companion file pattern
        zf.writestr("gis/tracts.sbn", b"shapefile-sbn-bytes")

    entry = _make_registry_entry(
        tmp_path,
        path="cache:geo/complex_archive.zip",
        reference_end="2025-01-01",
    )

    contract_entry = contract.RegistryEntry(
        path=entry.path,
        ds=entry.ds,
        group=entry.group,
        file_format=entry.file_format,
        reference_end=entry.reference_end,
        reference_basis=entry.reference_basis,
        is_base_geography=entry.is_base_geography,
        release_id=entry.release_id,
        publisher=entry.publisher,
        license=entry.license,
        as_of=entry.as_of,
        members=(),
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        zip_names = zf.namelist()

    oracle_members = contract.expected_archive_members(zip_names, contract_entry)
    actual_members = impl.archive_members(zip_path, entry)

    # Validate against contract oracle
    expected_member_tuples = [(m.name, m.file_format, m.reference_end) for m in oracle_members]
    actual_member_tuples = [(m.name, m.file_format, m.reference_end) for m in actual_members]

    assert actual_member_tuples == expected_member_tuples, (
        "WHAT: test_archive_members_skips_internal_and_groups_shapefile FAILED\n"
        "WHY: POST-ARCH-1 violation - archive_members must match oracle\n"
        f"EXPECTED: {expected_member_tuples!r}\n"
        f"ACTUAL: {actual_member_tuples!r}\n"
        "GUIDANCE: Skip directories, __MACOSX, and hidden files; associate companion parts to .shp"
    )

    # Explicit negative check: ensure no shapefile companion parts or hidden entries appear
    member_names = [m.name for m in actual_members]
    assert "gis/tracts.shx" not in member_names, (
        "WHAT: test_archive_members_skips_internal_and_groups_shapefile FAILED\n"
        "WHY: POST-ARCH-1 violation - companion .shx must not be listed as distinct member\n"
        "EXPECTED: 'gis/tracts.shx' absent from archive_members\n"
        f"ACTUAL: present in {member_names!r}\n"
        "GUIDANCE: Group shapefile companions into the .shp member"
    )
    assert ".DS_Store" not in member_names, (
        "WHAT: test_archive_members_skips_internal_and_groups_shapefile FAILED\n"
        "WHY: POST-ARCH-1 violation - hidden files must be skipped\n"
        "EXPECTED: '.DS_Store' absent from archive_members\n"
        f"ACTUAL: present in {member_names!r}\n"
        "GUIDANCE: Filter out entries starting with '.'"
    )


def test_archive_members_raises_on_unknown_extension_or_corrupt_zip(
    tmp_path: Path,
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract ArchiveMemberError, SourceReadError
    - Enforces: ERRORS-ARCH-1
    - Category: error, negative
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition: zip with an unknown extension member; missing zip; non-zip file.
    """
    entry = _make_registry_entry(
        tmp_path,
        path="cache:misc/bad_archive.zip",
        reference_end="2025-01-01",
    )

    # 1. Zip archive containing member with unknown extension
    unknown_ext_zip = tmp_path / "unknown_ext.zip"
    with zipfile.ZipFile(unknown_ext_zip, "w") as zf:
        zf.writestr("valid.csv", "a,b\n1,2\n")
        zf.writestr("payload.bin", b"\x00\x01\x02\x03")

    with pytest.raises(impl.ArchiveMemberError) as exc_arch:
        impl.archive_members(unknown_ext_zip, entry)
    assert "ERRORS-ARCH-1" in str(exc_arch.value), (
        "WHAT: test_archive_members_raises_on_unknown_extension_or_corrupt_zip FAILED\n"
        "WHY: ERRORS-ARCH-1 violation - unknown extension must raise ArchiveMemberError\n"
        "EXPECTED: ArchiveMemberError citing 'ERRORS-ARCH-1'\n"
        f"ACTUAL: {str(exc_arch.value)!r}\n"
        "GUIDANCE: Raise ArchiveMemberError when extension has no contracted format"
    )
    assert "payload.bin" in str(exc_arch.value), (
        "WHAT: test_archive_members_raises_on_unknown_extension_or_corrupt_zip FAILED\n"
        "WHY: ERRORS-ARCH-1 violation - error message must name the offending member\n"
        "EXPECTED: 'payload.bin' in error message\n"
        f"ACTUAL: {str(exc_arch.value)!r}\n"
        "GUIDANCE: Include member name in ArchiveMemberError message"
    )

    # 2. Missing zip archive
    missing_zip = tmp_path / "non_existent.zip"
    with pytest.raises(read_impl.SourceReadError) as exc_missing:
        impl.archive_members(missing_zip, entry)
    assert "ERRORS-ARCH-1" in str(exc_missing.value), (
        "WHAT: test_archive_members_raises_on_unknown_extension_or_corrupt_zip FAILED\n"
        "WHY: ERRORS-ARCH-1 violation - missing archive must raise SourceReadError\n"
        "EXPECTED: SourceReadError citing 'ERRORS-ARCH-1'\n"
        f"ACTUAL: {str(exc_missing.value)!r}\n"
        "GUIDANCE: Raise SourceReadError naming the archive when file is missing"
    )

    # 3. Not a zip archive (corrupt / arbitrary text)
    not_a_zip = tmp_path / "not_a_zip.zip"
    not_a_zip.write_text("plain text, definitely not a PK zip archive", encoding="utf-8")
    with pytest.raises(read_impl.SourceReadError) as exc_corrupt:
        impl.archive_members(not_a_zip, entry)
    assert "ERRORS-ARCH-1" in str(exc_corrupt.value), (
        "WHAT: test_archive_members_raises_on_unknown_extension_or_corrupt_zip FAILED\n"
        "WHY: ERRORS-ARCH-1 violation - non-zip file must raise SourceReadError\n"
        "EXPECTED: SourceReadError citing 'ERRORS-ARCH-1'\n"
        f"ACTUAL: {str(exc_corrupt.value)!r}\n"
        "GUIDANCE: Raise SourceReadError naming the archive when zipfile fails to open"
    )


def test_member_source_shapefile_vsizip_and_extracted_bytes(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract VSIZIP_PREFIX, member_source()
    - Enforces: POST-ARCH-2
    - Category: positive, boundary
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition: shapefile member returns /vsizip/ path in place;
      tabular/text member extracts byte-identical file into workdir.
    """
    zip_path = tmp_path / "sources.zip"
    csv_bytes = b"header1,header2\nval1,val2\n"
    shp_bytes = b"SHAPEFILE_BYTES_TEST"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("folder/data.csv", csv_bytes)
        zf.writestr("geo/tracts.shp", shp_bytes)

    workdir = tmp_path / "workdir"
    workdir.mkdir()

    # Shapefile member: must return /vsizip/ path, read in place without extracting
    shp_source = impl.member_source(zip_path, "geo/tracts.shp", workdir)
    expected_shp_source = f"{contract.VSIZIP_PREFIX}{zip_path.resolve()}/geo/tracts.shp"
    assert shp_source == expected_shp_source, (
        "WHAT: test_member_source_shapefile_vsizip_and_extracted_bytes FAILED\n"
        "WHY: POST-ARCH-2 violation - shapefile member must return /vsizip/ path\n"
        f"EXPECTED: {expected_shp_source!r}\n"
        f"ACTUAL: {shp_source!r}\n"
        "GUIDANCE: For .shp members return VSIZIP_PREFIX + archive_path + '/' + member"
    )

    # Non-shapefile member: must be extracted into workdir and be byte-identical
    csv_source = impl.member_source(zip_path, "folder/data.csv", workdir)
    extracted_path = Path(csv_source)
    assert extracted_path.is_file(), (
        "WHAT: test_member_source_shapefile_vsizip_and_extracted_bytes FAILED\n"
        "WHY: POST-ARCH-2 violation - non-shapefile member must extract to a file in workdir\n"
        f"EXPECTED: existing file path under {str(workdir)!r}\n"
        f"ACTUAL: {csv_source!r}\n"
        "GUIDANCE: Extract member into workdir and return the extracted file path"
    )
    assert extracted_path.is_relative_to(workdir), (
        "WHAT: test_member_source_shapefile_vsizip_and_extracted_bytes FAILED\n"
        "WHY: POST-ARCH-2 violation - extracted file must be within workdir\n"
        f"EXPECTED: path relative to {str(workdir)!r}\n"
        f"ACTUAL: {str(extracted_path)!r}\n"
        "GUIDANCE: Ensure extraction target is inside workdir"
    )
    assert extracted_path.read_bytes() == csv_bytes, (
        "WHAT: test_member_source_shapefile_vsizip_and_extracted_bytes FAILED\n"
        "WHY: POST-ARCH-2 violation - extracted file bytes must equal archive bytes (REQ-28)\n"
        f"EXPECTED: {csv_bytes!r}\n"
        f"ACTUAL: {extracted_path.read_bytes()!r}\n"
        "GUIDANCE: Write raw extracted bytes without modification"
    )


def test_member_source_raises_when_member_missing(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract ArchiveMemberError
    - Enforces: ERRORS-ARCH-2
    - Category: error, negative
    - Risk tier: HIGH
    - Pyramid level: Unit
    - Equivalence partition: requested member does not exist in zip archive.
    """
    zip_path = tmp_path / "valid.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("exists.csv", "id\n1\n")

    workdir = tmp_path / "workdir"
    workdir.mkdir()

    missing_member = "does_not_exist.csv"
    with pytest.raises(impl.ArchiveMemberError) as exc_info:
        impl.member_source(zip_path, missing_member, workdir)

    assert "ERRORS-ARCH-2" in str(exc_info.value), (
        "WHAT: test_member_source_raises_when_member_missing FAILED\n"
        "WHY: ERRORS-ARCH-2 violation - missing member must raise ArchiveMemberError\n"
        "EXPECTED: ArchiveMemberError citing 'ERRORS-ARCH-2'\n"
        f"ACTUAL: {str(exc_info.value)!r}\n"
        "GUIDANCE: Raise ArchiveMemberError naming archive and missing member"
    )
    assert missing_member in str(exc_info.value), (
        "WHAT: test_member_source_raises_when_member_missing FAILED\n"
        "WHY: ERRORS-ARCH-2 violation - error message must name the missing member\n"
        f"EXPECTED: error message containing {missing_member!r}\n"
        f"ACTUAL: {str(exc_info.value)!r}\n"
        "GUIDANCE: Include missing member name in ArchiveMemberError message"
    )
