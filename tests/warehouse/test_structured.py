"""RED tests for SLICE-3 batch 6c-iii: JSON tables and geographic files.

CONTRACT AUTHORITY RECORD:
- File: contracts/warehouse_contract.py (CONTRACT_DOCUMENTS)
- Authority: AUTHORITATIVE for the warehouse and its Ingest (SLICE-3)
- Clauses covered: POST-READ-4, ERRORS-READ-3, POST-READ-5, ERRORS-READ-4
- Requirements: REQ-25, REQ-28

The implementation is src/warehouse/structured.py. It does not import the contract (CL11-F);
these tests import both.

FOUR-CRITERIA TEST VALIDITY GATE (both tests):
  C1 VALID: every assertion cites one of the four clauses.
  C2 VALUABLE: exact tables, columns and cell text against the contract oracle, including numbers
     kept as written ("0.1780", "1e5") and top-level entries a table-only reader would drop;
     exact column types for a GeoJSON and a zipped shapefile; refusals by name.
  C3 NON-DUPLICATIVE: test 1 pins the JSON shape rules; test 2 pins the geographic reader.
  C4 NOT FUTURE-EDIT: every assertion enforces a current clause.
"""

import json
import zipfile
from pathlib import Path

import duckdb
import pytest
from contracts import warehouse_contract as contract
from src.warehouse import structured as impl

# Risk tier: HIGH. A dropped JSON entry or an altered number changes what the AI cites; a lost
# feature drops a place from the map's source data.


def test_json_tables_keep_every_entry_with_values_as_written(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract expected_json_tables(), JsonTable, JSON_ROOT_KEY,
      JSON_BLOB_COLUMN
    - Enforces: POST-READ-4, ERRORS-READ-3
    - Category: positive, boundary, negative
    - Risk tier: HIGH
    - Pyramid level: Unit (files on disk)
    - Equivalence partition: object with tables plus other entries; top-level array; a bare
      scalar; invalid JSON; missing file.
    """
    cases = {
        "mixed.json": (
            '{"state":[{"a":0.1780,"b":1e5,"c":true,"d":null,"e":{"x":1.50}},{"a":2,"h":"new"}],'
            '"national":{"k":1},"note":"text"}'
        ),
        "array.json": '[{"x":1},{"y":"z"}]',
        "scalar.json": '"just text"',
    }
    for name, text in cases.items():
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        want = [(t.key, t.columns, t.rows) for t in contract.expected_json_tables(text)]
        got = [(t.key, t.columns, t.rows) for t in impl.read_json_tables(path)]
        assert got == want, (
            "test_json_tables_keep_every_entry_with_values_as_written FAILED\n"
            f"POST-READ-4 violation for {name}: tables, columns or cells differ\n"
            f"EXPECTED: {want!r}\n"
            f"ACTUAL: {got!r}\n"
            "GUIDANCE: one table per array of objects, the other top-level entries in one root "
            "row, scalars as written, nested values as compact JSON, null as None"
        )
    assert (impl.JSON_ROOT_KEY, impl.JSON_BLOB_COLUMN) == (
        contract.JSON_ROOT_KEY,
        contract.JSON_BLOB_COLUMN,
    ), (
        "test_json_tables_keep_every_entry_with_values_as_written FAILED\n"
        "POST-READ-4 violation: the root key or blob column differs from the contract\n"
        f"EXPECTED: {(contract.JSON_ROOT_KEY, contract.JSON_BLOB_COLUMN)!r}\n"
        f"ACTUAL: {(impl.JSON_ROOT_KEY, impl.JSON_BLOB_COLUMN)!r}\n"
        "GUIDANCE: use the contract's names"
    )

    broken = tmp_path / "broken.json"
    broken.write_text('{"a": [1, 2', encoding="utf-8")
    for label, path in (("invalid JSON", broken), ("missing file", tmp_path / "absent.json")):
        with pytest.raises(impl.SourceReadError) as caught:
            impl.read_json_tables(path)
        assert path.name in str(caught.value), (
            "test_json_tables_keep_every_entry_with_values_as_written FAILED\n"
            f"ERRORS-READ-3 violation for {label}: the refusal does not name the file\n"
            f"EXPECTED: SourceReadError naming {path.name!r}\n"
            f"ACTUAL: {caught.value!s}\n"
            "GUIDANCE: stop with the file name; never return an empty table"
        )


def test_geographic_files_keep_every_feature_with_text_attributes(tmp_path: Path):
    """
    CONTRACT TRACEABILITY:
    - Contract: warehouse_contract validate_geo_columns(), GEO_EXTENSION, GEO_ROW_ID_COLUMN,
      GEO_GEOMETRY_COLUMN
    - Enforces: POST-READ-5, ERRORS-READ-4
    - Category: positive (GeoJSON file, shapefile inside a zip), negative
    - Risk tier: HIGH
    - Pyramid level: Integration (DuckDB spatial / GDAL on real files)
    - Equivalence partition: GeoJSON with a numeric attribute; zipped shapefile read through a
      /vsizip/ member path; a file GDAL cannot open.
    """
    con = duckdb.connect(":memory:")
    con.execute(f"LOAD {contract.GEO_EXTENSION}")
    geojson = tmp_path / "places.geojson"
    geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"GEOID": "12095", "ALAND": 2350, "NAME": "Orange"},
                        "geometry": {"type": "Point", "coordinates": [-81.38, 28.54]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"GEOID": "12117", "ALAND": 801, "NAME": "Seminole"},
                        "geometry": {"type": "Point", "coordinates": [-81.25, 28.71]},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    # Fixture only: DuckDB 2.0 refuses a GDAL write with an SRS unless the axis order is explicit.
    con.execute("SET geometry_always_xy = true")
    con.execute(
        "COPY (SELECT * EXCLUDE (OGC_FID) FROM ST_Read($p)) "
        "TO $o (FORMAT GDAL, DRIVER 'ESRI Shapefile')",
        {"p": str(geojson), "o": str(shp_dir / "places.shp")},
    )
    zipped = tmp_path / "places.zip"
    with zipfile.ZipFile(zipped, "w") as archive:
        for part in sorted(shp_dir.iterdir()):
            archive.write(part, arcname=part.name)

    for label, source in (
        ("GeoJSON file", str(geojson)),
        ("zipped shapefile", f"/vsizip/{zipped}/places.shp"),
    ):
        rel = impl.read_geo(con, source)
        types = [str(t) for t in rel.types]
        contract.validate_geo_columns(rel.columns, types)
        names = sorted(r[0] for r in rel.select("NAME").fetchall())
        attrs = [c for c in rel.columns if c != contract.GEO_GEOMETRY_COLUMN]
        assert (names, sorted(attrs)) == (["Orange", "Seminole"], ["ALAND", "GEOID", "NAME"]), (
            "test_geographic_files_keep_every_feature_with_text_attributes FAILED\n"
            f"POST-READ-5 violation for {label}: features or attribute columns differ\n"
            "EXPECTED: both features; attributes ALAND, GEOID, NAME; no GDAL row id\n"
            f"ACTUAL: names={names!r}, attributes={attrs!r}, types={types!r}\n"
            "GUIDANCE: every feature, attributes as text, geometry kept, no added row id"
        )

    not_geo = tmp_path / "notes.geojson"
    not_geo.write_text("this is not geographic data", encoding="utf-8")
    with pytest.raises(impl.SourceReadError) as caught:
        impl.read_geo(con, str(not_geo))
    assert "notes.geojson" in str(caught.value), (
        "test_geographic_files_keep_every_feature_with_text_attributes FAILED\n"
        "ERRORS-READ-4 violation: an unreadable source was not refused by name\n"
        "EXPECTED: SourceReadError naming 'notes.geojson'\n"
        f"ACTUAL: {caught.value!s}\n"
        "GUIDANCE: stop with the source name; never return an empty relation"
    )
    assert (impl.GEO_EXTENSION, impl.GEO_ROW_ID_COLUMN, impl.GEO_GEOMETRY_COLUMN) == (
        contract.GEO_EXTENSION,
        contract.GEO_ROW_ID_COLUMN,
        contract.GEO_GEOMETRY_COLUMN,
    ), (
        "test_geographic_files_keep_every_feature_with_text_attributes FAILED\n"
        "POST-READ-5 violation: the extension or column names differ from the contract\n"
        "EXPECTED: the contract's GEO_EXTENSION, GEO_ROW_ID_COLUMN and GEO_GEOMETRY_COLUMN\n"
        "ACTUAL: different values\n"
        "GUIDANCE: use the contract's names"
    )
