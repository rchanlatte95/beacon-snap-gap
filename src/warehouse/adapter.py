"""Data adapter: the one configured warehouse location and table locations relative to it.

Specification: contracts/warehouse_contract.py, CONTRACT_ADAPTER (SLICE-3 batch 5).
Requirements: REQ-47, REQ-48. Runtime declarations are independent of that module;
tests bridge the specification and this implementation (CL11-F).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

WAREHOUSE_LOCATION_ENV: Final = "WAREHOUSE_LOCATION"
WAREHOUSE_DB_FILE: Final = "warehouse.duckdb"
PARQUET_DIR: Final = "parquet"
TABLE_NAME_PATTERN: Final = re.compile(r"^[a-z_][a-z0-9_]*$")


class WarehouseLocationError(Exception):
    """ERRORS-ADAPT-1..3 or FORBIDDEN-ADAPT-1: a warehouse or table location is invalid."""


@dataclass(frozen=True, slots=True)
class WarehouseLocation:
    """An absolute, normalized POSIX directory that holds the warehouse."""

    root: str


def warehouse_location(env: Mapping[str, str]) -> WarehouseLocation:
    """Return the warehouse location taken only from WAREHOUSE_LOCATION (POST-ADAPT-1).

    Raises:
        WarehouseLocationError: ERRORS-ADAPT-1, the variable is unset, empty, relative or
            contains '..'.
    """
    raw = env.get(WAREHOUSE_LOCATION_ENV)
    if raw is None or not raw.strip():
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-1 violation: {WAREHOUSE_LOCATION_ENV} is unset or empty"
        )
    path = PurePosixPath(raw.strip())
    if not path.is_absolute():
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-1 violation: {WAREHOUSE_LOCATION_ENV} {raw!r} is not an absolute path"
        )
    if ".." in path.parts:
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-1 violation: {WAREHOUSE_LOCATION_ENV} {raw!r} contains '..'"
        )
    return WarehouseLocation(root=str(path))


def require_warehouse(location: WarehouseLocation) -> WarehouseLocation:
    """Return the location unchanged when it holds the warehouse file (ERRORS-ADAPT-2).

    Raises:
        WarehouseLocationError: ERRORS-ADAPT-2, the directory or its warehouse file is missing.
    """
    root = Path(location.root)
    if not root.is_dir():
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-2 violation: warehouse location {location.root!r} does not exist"
        )
    if not (root / WAREHOUSE_DB_FILE).is_file():
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-2 violation: {WAREHOUSE_DB_FILE} is missing from warehouse location "
            f"{location.root!r}"
        )
    return location


def table_location(table_name: str) -> str:
    """Return a table's Parquet location relative to the warehouse location (POST-ADAPT-2).

    Raises:
        WarehouseLocationError: ERRORS-ADAPT-3, the table name does not match TABLE_NAME_PATTERN.
    """
    if not TABLE_NAME_PATTERN.match(table_name):
        raise WarehouseLocationError(
            f"ERRORS-ADAPT-3 violation: table name {table_name!r} does not match "
            f"{TABLE_NAME_PATTERN.pattern}"
        )
    return f"{PARQUET_DIR}/{table_name}.parquet"


def table_path(location: WarehouseLocation, table_name: str, relative: str) -> str:
    """Join a relative table location to the warehouse location (POST-ADAPT-3).

    Raises:
        WarehouseLocationError: FORBIDDEN-ADAPT-1, the table location is empty, absolute,
            backslashed or contains '..'.
    """
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise WarehouseLocationError(
            f"FORBIDDEN-ADAPT-1 violation: table {table_name!r} has location {relative!r}, which "
            f"is not relative to the warehouse location {location.root!r}"
        )
    return str(PurePosixPath(location.root) / rel)
