"""Warehouse writer: data tables to Parquet through the adapter, base tables into warehouse.duckdb.

Specification: contracts/warehouse_contract.py, CONTRACT_WRITER (SLICE-3 batch 6a).
Requirements: REQ-48, REQ-51. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import duckdb

from .adapter import (
    WAREHOUSE_DB_FILE,
    WarehouseLocation,
    table_location,
    table_path,
)

BASE_TABLES: Final[tuple[str, ...]] = (
    "files",
    "catalog",
    "sources",
    "columns",
    "documents",
    "glossary",
    "ingest_log",
)
CATALOG_REQUIRED_COLUMNS: Final[tuple[str, ...]] = ("table_name", "parquet", "status")


class WarehouseWriteError(Exception):
    """ERRORS-WRITE-1 or POST-WRITE-2: the warehouse cannot be written as specified."""


class WarehouseWriter:
    """Writes one warehouse build at one location.

    Data tables go to Parquet files named by table_location(); base tables go into
    warehouse.duckdb as tables. No view is created, because a view embeds a location
    (POST-WRITE-2, INV-WRITE-1).
    """

    def __init__(self, location: WarehouseLocation) -> None:
        self._location = location
        self._written: dict[str, str] = {}

    def write_table(self, table_name: str, relation: duckdb.DuckDBPyRelation) -> str:
        """Write a data table's rows to its Parquet file and return its relative location.

        Raises:
            WarehouseWriteError: ERRORS-WRITE-1, the table was already written in this build.
            WarehouseLocationError: ERRORS-ADAPT-3, the table name is invalid (propagated).
        """
        if table_name in self._written:
            raise WarehouseWriteError(
                f"ERRORS-WRITE-1 violation: table {table_name!r} was already written in this build"
            )
        relative = table_location(table_name)
        path = Path(table_path(self._location, table_name, relative))
        path.parent.mkdir(parents=True, exist_ok=True)
        relation.write_parquet(str(path))  # POST-WRITE-1
        self._written[table_name] = relative
        return relative

    def finalize(self, base_tables: Mapping[str, duckdb.DuckDBPyRelation]) -> None:
        """Write warehouse.duckdb holding exactly the base tables and no views.

        Raises:
            WarehouseWriteError: ERRORS-WRITE-1 when a base table is missing or unexpected, or
                the catalog lacks a required column; POST-WRITE-2 when the catalog does not list
                exactly the written tables at their relative locations.
        """
        missing = [name for name in BASE_TABLES if name not in base_tables]
        unexpected = sorted(set(base_tables) - set(BASE_TABLES))
        if missing or unexpected:
            raise WarehouseWriteError(
                f"ERRORS-WRITE-1 violation: base tables missing {missing}, unexpected {unexpected}"
            )
        catalog = base_tables["catalog"]
        absent = [col for col in CATALOG_REQUIRED_COLUMNS if col not in catalog.columns]
        if absent:
            raise WarehouseWriteError(
                f"ERRORS-WRITE-1 violation: catalog lacks required columns {absent}"
            )
        listed = dict(catalog.select("table_name, parquet").fetchall())
        if listed != self._written:
            raise WarehouseWriteError(
                f"POST-WRITE-2 violation: catalog lists {listed}, written {self._written}"
            )
        db_path = Path(self._location.root) / WAREHOUSE_DB_FILE
        # Base tables arrive on other connections; stage each to Parquet outside the warehouse
        # location so DuckDB carries the column types, then load it as a table.
        with tempfile.TemporaryDirectory() as staging:
            con = duckdb.connect(str(db_path))
            try:
                for name in BASE_TABLES:
                    staged = str(Path(staging) / f"{name}.parquet")
                    base_tables[name].write_parquet(staged)
                    # name comes from BASE_TABLES, never from input; the file is bound.
                    create = f"CREATE TABLE {name} AS SELECT * FROM read_parquet(?)"  # noqa: S608
                    con.execute(create, [staged])
            finally:
                con.close()
