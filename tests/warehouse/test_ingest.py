"""RED tests for SLICE-3 batch 7: the Ingest command.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_INGEST, POST-BASE-1, SEQ-5)
- Clauses covered: POST-INGEST-1 to POST-INGEST-7, POST-GLOSS-3, ERRORS-GLOSS-2,
  FORBIDDEN-INGEST-1, ERRORS-INGEST-1
- Requirements: REQ-25 to REQ-30, REQ-48, REQ-51, REQ-53, REQ-54

The implementation is src/warehouse/ingest.py: run(repo_root, env, workers), IngestError,
GlossaryDeclarationError, and a command line (python -m src.warehouse.ingest --workers N). It
does not import the contract (CL11-F).

FOUR-CRITERIA TEST VALIDITY GATE:
- C1 VALID: expectations come from contract oracles (expected_table_name, expected_unique_names,
  expected_state_filter, expected_origin, expected_scope reasons) and the fixture's literal bytes.
- C2 VALUABLE: an Ingest that drops a member, keeps an out-of-scope file, loses provenance, skips
  the log, differs by worker count, touches the network or overwrites a warehouse fails.
- C3 NON-DUPLICATIVE: readers, scope, filter and writer are tested alone elsewhere; these test
  their composition.
- C4 NOT FUTURE-EDIT: only contracted names.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest
from contracts import warehouse_contract as contract
from tests.warehouse import ingest_fixture as fx

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="ARRANGE: the warehouse location is a POSIX path (Cloud Run)"
)

from src.warehouse import ingest as impl  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ZIP = "cache:grp/bundle.zip"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build(tmp_path: Path, workers: int, name: str = "warehouse") -> tuple[Path, Path]:
    root = fx.build_repo(tmp_path / f"repo_{name}")
    location = tmp_path / name
    impl.run(root, {contract.WAREHOUSE_LOCATION_ENV: str(location)}, workers)
    return root, location


def _table(con: duckdb.DuckDBPyConnection, name: str) -> list[tuple[object, ...]]:
    return con.execute(f"SELECT * FROM {name}").fetchall()  # noqa: S608 - contract base-table names


def _data(location: Path, relative: str) -> list[tuple[object, ...]]:
    return (
        duckdb.connect()
        .execute("SELECT * FROM read_parquet(?)", [str(location / relative)])
        .fetchall()
    )


def test_ingest_builds_files_tables_provenance_documents_glossary_and_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-INGEST-1 to POST-INGEST-6, POST-GLOSS-3, POST-BASE-1
    - Enforces: scope over files and archive members; table names; state-filtered rows; documents;
      provenance from the manifest and the registry; columns; glossary from the declared
      dictionary; the row set aside in ingest_log and in the log output
    - Category: integration / positive / boundary (duplicate, out of time, skipped member)
    - Risk tier: High; every AI answer is built from this warehouse
    """
    caplog.set_level("INFO")
    root, location = _build(tmp_path, workers=1)
    con = duckdb.connect(str(location / contract.WAREHOUSE_DB_FILE), read_only=True)
    zip_bytes = (root / "data/cache/grp/bundle.zip").read_bytes()
    nr = contract.NOT_RECORDED
    want_files = sorted(
        [
            (ZIP, "DS-T3", "csv", _sha(zip_bytes), contract.FILE_LOADED, "2 members"),
            (f"{ZIP}!notes.txt", "DS-T3", "text", _sha(fx.NOTES), contract.FILE_LOADED, ""),
            (f"{ZIP}!tracts.csv", "DS-T3", "csv", _sha(fx.TRACTS), contract.FILE_LOADED, ""),
            (
                "cache:grp/dictionary.csv",
                "DS-T1",
                "csv",
                _sha(fx.DICTIONARY),
                contract.FILE_LOADED,
                "",
            ),
            (
                "cache:grp/loans.csv",
                "DS-T1",
                "csv",
                _sha(fx.LOANS),
                contract.FILE_LOADED,
                "1 rows set aside",
            ),
            (
                "cache:grp/loans_copy.csv",
                "DS-T1",
                "csv",
                _sha(fx.LOANS),
                contract.FILE_EXCLUDED,
                contract.EXCLUDE_DUPLICATE_CONTENT,
            ),
            (
                "cache:grp/old.csv",
                "DS-T2",
                "csv",
                _sha(fx.OLD),
                contract.FILE_EXCLUDED,
                contract.EXCLUDE_TIME_SCOPE,
            ),
            (
                "repo:data/external/tool.py",
                nr,
                nr,
                _sha(b"print('fixture')\n"),
                contract.FILE_NOT_A_SOURCE,
                "fixture code",
            ),
            (
                "repo:docs/readme.md",
                "REPO-DOC",
                "text",
                _sha(fx.README.encode()),
                contract.FILE_LOADED,
                "",
            ),
        ]
    )
    assert sorted(_table(con, "files")) == want_files, (
        f"POST-INGEST-1 violation: {_table(con, 'files')}"
    )

    names = contract.expected_unique_names(
        [
            contract.expected_table_name("DS-T3", ZIP, "tracts.csv", None),
            contract.expected_table_name("DS-T1", "cache:grp/dictionary.csv", None, None),
            contract.expected_table_name("DS-T1", "cache:grp/loans.csv", None, None),
        ]
    )
    tracts_t, dict_t, loans_t = names
    catalog = _table(con, "catalog")
    assert catalog == sorted(
        [
            (
                tracts_t,
                contract.expected_table_location(tracts_t),
                "ok",
                f"{ZIP}!tracts.csv",
                "DS-T3",
            ),
            (
                dict_t,
                contract.expected_table_location(dict_t),
                "ok",
                "cache:grp/dictionary.csv",
                "DS-T1",
            ),
            (
                loans_t,
                contract.expected_table_location(loans_t),
                "ok",
                "cache:grp/loans.csv",
                "DS-T1",
            ),
        ]
    ), f"POST-INGEST-2 violation: catalog {catalog}"

    loans = contract.expected_state_filter(
        ("LoanID", "BorrState", "GrossApproval"),
        [
            {"LoanID": a, "BorrState": b, "GrossApproval": c}
            for a, b, c in (("L1", "FL", "100"), ("L2", "TX", "200"), ("L4", "NY", "400"))
        ],
    )
    assert _data(location, contract.expected_table_location(loans_t)) == [
        (r["LoanID"], r["BorrState"], r["GrossApproval"]) for r in loans.rows
    ], "POST-INGEST-2 violation: loans rows"
    assert _data(location, contract.expected_table_location(tracts_t)) == [
        ("1400000US12095016510", "4200")
    ], "POST-INGEST-2 violation: archive member rows after the GEO_ID filter"

    docs = sorted(_table(con, "documents"))
    assert docs == sorted(
        [("repo:docs/readme.md", 1, fx.README), (f"{ZIP}!notes.txt", 1, fx.NOTES.decode())]
    ), f"POST-INGEST-3 violation: {docs}"

    sources = {r[0]: r for r in _table(con, "sources")}
    url, ts = contract.expected_origin(
        "cache:grp/loans.csv",
        [{"path": "grp/loans.csv", "status": "ok", "url": fx.URL, "ts": fx.TS}],
    )
    assert sources[loans_t] == (
        loans_t,
        "DS-T1",
        "cache:grp/loans.csv",
        url,
        ts,
        _sha(fx.LOANS),
        "Fixture Agency",
        "CC0",
        "2025-09-30",
        loans.applied_filter,
        loans.rows_in_source,
        loans.rows_loaded,
    ), f"POST-INGEST-4 violation: {sources[loans_t]}"
    assert sources[tracts_t][3:6] == ("https://example.org/bundle.zip", fx.TS, _sha(zip_bytes)), (
        "POST-INGEST-4 violation: an archive member takes the archive's origin and SHA-256"
    )
    assert sources[dict_t][6:9] == (nr, nr, nr), "POST-INGEST-4 violation: unstated fields"

    cols = [r for r in _table(con, "columns") if r[0] == loans_t]
    assert cols == [
        (loans_t, "LoanID", 1, "VARCHAR", ""),
        (loans_t, "BorrState", 2, "VARCHAR", ""),
        (loans_t, "GrossApproval", 3, "VARCHAR", ""),
    ], f"POST-INGEST-5 violation: {cols}"

    assert sorted(_table(con, "glossary")) == [
        (dict_t, "DS-T1", "BorrState", "Borrower state"),
        (dict_t, "DS-T1", "GrossApproval", "Amount approved"),
    ], f"POST-GLOSS-3 violation: {_table(con, 'glossary')}"

    assert _table(con, "ingest_log") == [
        ("cache:grp/loans.csv", "line 4", "TOO MANY COLUMNS", "L5,FL,500,extra")
    ], f"POST-INGEST-6 violation: {_table(con, 'ingest_log')}"
    assert any("loans.csv" in m and "line 4" in m for m in caplog.messages), (
        "POST-INGEST-6 violation: the set-aside row was not logged"
    )


def test_workers_give_the_same_warehouse_and_the_command_uses_no_network(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: POST-INGEST-7, FORBIDDEN-INGEST-1 (REQ-51, REQ-28)
    - Enforces: the command line with 2 workers under a socket block builds the same base tables
      and data as 1 in-process worker, and no source file changes
    - Category: integration / invariant
    - Risk tier: High; the one canonical build must not depend on parallelism or the network
    """
    _, loc1 = _build(tmp_path, workers=1, name="one")
    root2 = fx.build_repo(tmp_path / "repo_two")
    before = {p: _sha(p.read_bytes()) for p in sorted(root2.rglob("*")) if p.is_file()}
    guard = tmp_path / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import socket\n"
        "def _deny(*args, **kwargs):\n"
        "    raise OSError('FORBIDDEN-INGEST-1: network use')\n"
        "socket.socket.connect = _deny\n"
        "socket.create_connection = _deny\n",
        encoding="utf-8",
    )
    loc2 = tmp_path / "two"
    env = os.environ | {
        contract.WAREHOUSE_LOCATION_ENV: str(loc2),
        "PYTHONPATH": os.pathsep.join([str(guard), str(REPO)]),
    }
    done = subprocess.run(  # noqa: S603 - fixed interpreter and module
        [sys.executable, "-m", contract.INGEST_MODULE, "--workers", "2", "--repo", str(root2)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, (
        f"POST-INGEST-7 violation: the command failed: {done.stderr[-500:]}"
    )
    after = {p: _sha(p.read_bytes()) for p in sorted(root2.rglob("*")) if p.is_file()}
    assert after == before, "FORBIDDEN-INGEST-1 violation: a source file changed"

    a = duckdb.connect(str(loc1 / contract.WAREHOUSE_DB_FILE), read_only=True)
    b = duckdb.connect(str(loc2 / contract.WAREHOUSE_DB_FILE), read_only=True)
    for base in contract.BASE_TABLES:
        assert sorted(_table(a, base)) == sorted(_table(b, base)), (
            f"POST-INGEST-7 violation: {base}"
        )
    for name, relative, *_ in _table(a, "catalog"):
        assert _data(loc1, relative) == _data(loc2, relative), f"POST-INGEST-7 violation: {name}"


def test_ingest_stops_without_a_warehouse_on_bad_input(tmp_path: Path) -> None:
    """
    CONTRACT TRACEABILITY:
    - Contract: ERRORS-INGEST-1, ERRORS-GLOSS-2 (REQ-25, REQ-30, REQ-31, REQ-51)
    - Enforces: an existing warehouse, an unregistered candidate, or a bad glossary declaration
      stops the run naming the clause, and leaves no warehouse.duckdb
    - Category: negative / error
    - Risk tier: High; the canonical warehouse is built once and never overwritten
    """
    root, location = _build(tmp_path, workers=1)
    with pytest.raises(impl.IngestError) as again:
        impl.run(root, {contract.WAREHOUSE_LOCATION_ENV: str(location)}, 1)
    assert "ERRORS-INGEST-1" in str(again.value)

    extra = fx.build_repo(tmp_path / "repo_extra")
    (extra / "docs" / "unlisted.md").write_text("not registered\n", encoding="utf-8")
    loc = tmp_path / "extra"
    with pytest.raises(impl.IngestError) as unlisted:
        impl.run(extra, {contract.WAREHOUSE_LOCATION_ENV: str(loc)}, 1)
    assert "ERRORS-INGEST-1" in str(unlisted.value)
    assert "unlisted.md" in str(unlisted.value)
    assert not (loc / contract.WAREHOUSE_DB_FILE).exists(), (
        "ERRORS-INGEST-1 violation: a warehouse was written"
    )

    bad = fx.build_repo(tmp_path / "repo_bad")
    reg = bad / "data" / "warehouse" / "source_registry.toml"
    reg.write_text(
        reg.read_text(encoding="utf-8").replace('term = "Field Name"', 'term = " "'),
        encoding="utf-8",
    )
    loc_bad = tmp_path / "bad"
    with pytest.raises(impl.GlossaryDeclarationError) as gloss:
        impl.run(bad, {contract.WAREHOUSE_LOCATION_ENV: str(loc_bad)}, 1)
    assert "ERRORS-GLOSS-2" in str(gloss.value)
    assert not (loc_bad / contract.WAREHOUSE_DB_FILE).exists()
