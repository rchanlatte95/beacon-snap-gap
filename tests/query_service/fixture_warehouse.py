"""Test fixture: a small real warehouse written with src/warehouse/writer.py.

Tables are found by their catalog source_file (POST-BASE-1), as the tools find them. Values are
text, as the Ingest keeps them. The base tables follow BASE_TABLE_COLUMNS.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import duckdb
from contracts import query_service_contract as contract
from src.warehouse import adapter
from src.warehouse.writer import WarehouseWriter

TRACT_A = "12095016510"
TRACT_B = "12095016600"
TRACT_EMPTY = "12095990000"  # a tract with no populated block
TRACT_C = "12095016700"  # a tract with more blocks than one page
SITES = (
    ("S1", "Pantry One", "1 Main St", "28.5400", "-81.3800", TRACT_A, "Orange"),
    ("S2", "Pantry Two", "2 Oak Ave", "28.6000", "-81.2000", TRACT_B, "Orange"),
    ("S3", "Pantry Three", "3 Far Rd", "29.9000", "-82.9000", TRACT_B, "Lake"),
)
BLOCKS = (
    (f"{TRACT_A}1001", "120", "28.5410", "-81.3790"),
    (f"{TRACT_A}1002", "0", "28.9000", "-81.9000"),
    (f"{TRACT_B}2001", "300", "28.5900", "-81.2100"),
    (f"{TRACT_EMPTY}0001", "0", "28.4000", "-81.4000"),
    # Pagination (POST-TOOL-1): TRACT_C has more blocks than one page. Every block is far from every
    # site except the last in total order, which sits beside S3; a one-page read misses S3.
    *((f"{TRACT_C}{i:04d}", "10", "25.0000", "-80.0000") for i in range(1200)),
    (f"{TRACT_C}1200", "10", "29.9001", "-82.9001"),
)
TRACTS = (
    (TRACT_A, "12.5", "4"),
    (TRACT_B, "30.1", "9"),
    (TRACT_C, "20.0", "5"),
    (TRACT_EMPTY, "", "0"),
)
LOANS = tuple((f"L{i}", "FL", str(1000 * i)) for i in range(1, 21))

TABLES = {
    "second_harvest_sites": (contract.SITES_SOURCE_FILE, "DS-X12", contract.SITE_COLUMNS, SITES),
    "census_blocks": (contract.BLOCKS_SOURCE_FILE, "DS-X24", contract.BLOCK_COLUMNS, BLOCKS),
    "tract_coverage": (
        contract.TRACTS_SOURCE_FILE,
        "DS-X12",
        (contract.TRACT_ID_COLUMN, "pct_poverty", "sba_loans_total"),
        TRACTS,
    ),
    "sba_loans": (
        "repo:data/external/sba-loans/foia.csv",
        "DS-X5",
        ("LoanID", "BorrState", "GrossApproval"),
        LOANS,
    ),
}
ORIGINS = {
    "second_harvest_sites": "https://feedhopenow.org/find-help/food-finder/",
    "census_blocks": contract.NOT_RECORDED,
    "tract_coverage": "https://feedhopenow.org/find-help/food-finder/",
    "sba_loans": "https://data.sba.gov/dataset/7a-504-foia",
}


def _rel(
    con: duckdb.DuckDBPyConnection, name: str, cols: Sequence[str], rows: Sequence[Sequence[object]]
) -> duckdb.DuckDBPyRelation:
    con.execute(f"CREATE TEMP TABLE {name} ({', '.join(f'{c} VARCHAR' for c in cols)})")
    if rows:
        placeholders = ", ".join("?" for _ in cols)
        # name and columns come from this fixture, never from input
        insert = f"INSERT INTO {name} VALUES ({placeholders})"  # noqa: S608
        con.executemany(insert, [tuple(None if v is None else str(v) for v in r) for r in rows])
    return con.table(name)


def build_warehouse(root: Path, glossary_terms: int = 0) -> Path:
    """Write the fixture warehouse at root and return root.

    glossary_terms adds that many (term, definition) rows for sba_loans, in order: TERM-0001 ...
    """
    loc = adapter.warehouse_location({contract.ENGINE_LOCATION_ENV: str(root)})
    con = duckdb.connect()
    writer = WarehouseWriter(loc)
    parquet = {
        name: writer.write_table(name, _rel(con, f"d_{name}", cols, rows))
        for name, (_, _, cols, rows) in TABLES.items()
    }
    base = contract.ENGINE_BASE_COLUMNS
    rows_by_base: dict[str, list[tuple[object, ...]]] = {
        "catalog": [(n, parquet[n], "ok", t[0], t[1]) for n, t in TABLES.items()],
        "sources": [
            (
                n,
                t[1],
                t[0],
                ORIGINS[n],
                "2026-11-07",
                "0" * 64,
                "Fixture publisher",
                "CC BY 4.0",
                "2026-11-07",
                "Central Florida",
                len(t[3]),
                len(t[3]),
            )
            for n, t in TABLES.items()
        ],
        "columns": [
            (n, c, i, "VARCHAR", "") for n, t in TABLES.items() for i, c in enumerate(t[2], 1)
        ],
        "glossary": [
            ("sba_loans", "DS-X5", f"TERM-{i:04d}", f"Definition {i}")
            for i in range(1, glossary_terms + 1)
        ],
        "files": [],
        "documents": [],
        "ingest_log": [],
    }
    writer.finalize({name: _rel(con, f"b_{name}", base[name], rows_by_base[name]) for name in base})
    return root


def fixture_sites() -> tuple[contract.Site, ...]:
    return tuple(contract.Site(s[0], s[1], s[2], s[6], float(s[3]), float(s[4])) for s in SITES)


def populated_blocks(geoid: str) -> tuple[tuple[float, float], ...]:
    return tuple(
        (float(b[2]), float(b[3])) for b in BLOCKS if b[0].startswith(geoid) and int(b[1]) > 0
    )
