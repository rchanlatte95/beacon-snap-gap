"""Warehouse (SLICE-3): Ingest of retained source files.

Contract-Implementation Independence (CL11-F): this package does NOT import
contracts/warehouse_contract.py.
"""

from .glossary import (
    WAREHOUSE_GCP_PROJECT,
    WAREHOUSE_GCS_BUCKET,
    WAREHOUSE_GCS_URI,
)

__all__ = [
    "WAREHOUSE_GCP_PROJECT",
    "WAREHOUSE_GCS_BUCKET",
    "WAREHOUSE_GCS_URI",
]
