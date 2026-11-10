# DISCONNECT MATRIX: warehouse data access (constitutional refactor)

**Date**: 2026-11-08
**Branch**: data/hackathon-sources
**Decision**: option A, approved by Ketema 2026-11-08 ("A. implement via constitutional refactor. no shortcuts")
**Source Prose** (verbatim, Ketema, 2026-11-08):

> "the technology is irrelevant, but the value of duckdb is plain. do not reinvent in python what already exists. if there was a conflict due to where the data lives you should have surfaced that. the requirement intent was to decouple the data from the image build process. if a gcp bucket cannot be mounted say so. but hard coded local file paths is bad architecture. data access should be abstracted. this is a standard data adapter pattern. re-assess and present cohesive options"

> Earlier decision, answering "Store: DuckDB with Parquet in the image (my recommendation), GCS-loaded, or BigQuery?": "1-agreed."

> Z-14: "use a gcp bucket" (moved the store from the image to the bucket; the engine was not changed).

> "the bucket name is irrelevant, just create it and then record it and ensure it is a reusable reference. if the bucket is ever changed the reference constant needs to be updated."

## Summary

| Metric | Count |
|--------|-------|
| Total behaviors | 9 |
| OVERRIDE | 5 |
| NEW | 3 |
| REMOVE | 0 (folded into B05 OVERRIDE) |
| KEEP | 1 |

## Matrix

| ID | Behavior | EXPECTED | OBSERVED | DELTA | Location | Priority |
|----|----------|----------|----------|-------|----------|----------|
| B01 | Warehouse location | One configured warehouse location; the same artifact opens locally, in tests, and at the Cloud Run mount path | All 309 data views embed `<build-machine path>/parquet/<t>.parquet`; opened at `/mnt/warehouse` every data view fails | OVERRIDE | `data/cache/warehouse/warehouse.duckdb` (views), written by scratch `/tmp/dw/ingest2.py:472` | P1 |
| B02 | Catalog paths | `catalog.parquet` holds names relative to the warehouse location | 309 of 355 `ok` rows hold absolute paths; 1 (`glossary`) relative; 45 hold none | OVERRIDE | `parquet/catalog.parquet`, written by `/tmp/dw/ingest2.py:465`, `/tmp/refresh_seq5_wh.py` | P1 |
| B03 | Warehouse build code | The Operator builds the warehouse with Ingest code committed in the repo, composed from the contracted SLICE-3 functions | Build ran from three scratch scripts in `/tmp`; no tracked file opens DuckDB; `pyproject.toml` has no DuckDB dependency | NEW (pending Z-18) | N/A (insertion point: `src/warehouse/`) | P1 |
| B04 | Data adapter (read side) | A data adapter takes one configured location, opens the warehouse read-only in DuckDB, and builds table views from the catalog's relative names at connect | No adapter exists; SLICE-4 has no implementation yet | NEW | N/A (insertion point: `src/query_service/`) | P1 |
| B05 | Read-only enforcement | DuckDB enforces it: read-only warehouse file, exactly one statement of type SELECT by DuckDB's own parser, file access limited to the warehouse location, configuration locked | SLICE-4 contract `f01ca3f` enforces with a regex and a hand-written keyword list (`validate_readonly_sql`) | OVERRIDE (remove the regex validator) | `contracts/query_service_contract.py` (`validate_readonly_sql`, `FORBIDDEN_SQL_KEYWORDS`, `_WORD_RE`, `_STRING_LITERAL_RE`, `_FROM_JOIN_RE`) | P1 |
| B06 | Batch-1 SLICE-4 tests | Tests run the adapter and DuckDB over a small real warehouse (Parquet plus catalog) in a temporary location | Committed RED tests (`738884b`) build an in-memory Python dictionary snapshot; source not re-read (author recollection and commit message only) | OVERRIDE | `tests/query_service/test_schema_and_sql.py` | P1 |
| B07 | Bucket copy | The bucket holds an artifact that opens at any mount path | The bucket holds the same absolute-path artifact as local | OVERRIDE (re-upload after B01 to B03) | `gs://<warehouse-bucket>/` (`WAREHOUSE_GCS_URI`) | P1 |
| B08 | Cloud Run mount | The QueryService service mounts the bucket read-only at the configured location using its own identity (Storage Object Viewer) | Not deployed | NEW (execution-verified, SLICE-4 deploy) | N/A | P2 |
| B09 | SLICE-3 decision functions and base tables | Scope, state filter, provenance and glossary rules; base tables readable; Parquet readable by location-relative path; read-only file rejects writes | Base table `glossary` opens at the mount (70,196 rows); `read_parquet('/mnt/warehouse/parquet/...')` returns 62,243 rows; read-only file rejects `CREATE` | KEEP | `src/warehouse/{scope,state_filter,provenance,glossary}.py` | P1 |

## Evidence

### O1 to O7: mount simulation (Library/Database technique, executed 2026-11-08)

Harness: `/tmp/obs/observe_mount.py` in `python:3.12-slim`, DuckDB 2.0.0 (same version that built the warehouse), `data/cache/warehouse` mounted read-only at `/mnt/warehouse`.

```
duckdb 2.0.0
O1 object kinds: [('BASE TABLE', 5), ('VIEW', 309)]
O2 views with absolute build-machine paths: 309 of 309
O3 catalog ok rows: absolute parquet=309 relative=1 total=355
O4 query a data view -> ERROR IOException IO Error: No files found that match the pattern "<build-machine path>/data/cache/warehouse/parquet/sba_foia_7a_fy2020_present_asof_260930.parquet"
O5 query base table glossary -> (70196,)
O6 read parquet by mount-relative path -> (62243,)
O7 write on read_only connection -> ERROR InvalidInputException Invalid Input Error: Cannot execute statement of type "CREATE" on database "warehouse" which is attached in read-only mode!
EXIT=0
```

### P1 to P5: DuckDB native controls (executed 2026-11-08, DuckDB 2.0.0)

```
P1 view inside allowed root -> (70196,)
P2 read outside root -> ERROR PermissionException Permission Error: Cannot access file "/etc/hosts" - file system operations are disabled by configuration
P3 change setting after lock -> ERROR InvalidInputException ... the configuration has been locked
P4 write (in-memory db) -> (1,)
P5 parse 'SELECT 1' -> ['StatementType.SELECT']
P5 parse 'WITH a AS (SELECT 1) SELECT * FROM a' -> ['StatementType.SELECT']
P5 parse 'DELETE FROM glossary' -> ['StatementType.DELETE']
P5 parse 'SELECT 1; DROP VIEW glossary' -> ['StatementType.SELECT', 'StatementType.DROP']
P5 parse "ATTACH 'x.db'" -> ['StatementType.ATTACH']
P5 parse 'PRAGMA version' -> ['StatementType.PRAGMA']
```

P4 means an in-memory connection alone is not read-only; read-only comes from the read-only warehouse file (O7) plus the one-SELECT-statement check (P5).

### B03: build code location (executed 2026-11-08)

```
tracked files touching duckdb/warehouse: []
scratch build scripts: ['/tmp/build_glossary_wh.py', '/tmp/dw/ingest2.py', '/tmp/refresh_seq5_wh.py']
pyproject has duckdb dep: False
```

### B08: platform capability (primary sources, read 2026-11-08)

- Cloud Run mounts a Cloud Storage bucket read-only as a volume (Cloud Storage FUSE, no container change, service identity with Storage Object Viewer; mounts must complete within 30 seconds). Google Cloud docs, "Configure Cloud Storage volume mounts for Cloud Run services", last updated 2026-10-30.
- DuckDB reads `gs://` directly only with HMAC keys (option B, not chosen). DuckDB docs 2.0, "Google Cloud Storage Import", "S3 API Support".

## Zones

- **Z-18** (B03): decided by Ketema, 2026-11-08: "if a rule say once but was executed in error it is invalid. rebuild if needed." The Operator rebuilds the warehouse with Ingest code committed in this repository (REQ-51).
- **Z-19** (B01, B04, B05, B08): decided by Ketema, 2026-11-08, option A (read-only Cloud Run bucket mount, one configured warehouse location, data adapter, DuckDB). Manifest cycle 14: REQ-47 to REQ-52.

## Phase 2 bridge findings (disposable prototype `/tmp/bridge/adapter_bridge.py`, DuckDB 2.0.0, executed 2026-11-08)

```
Q5 query after relocation -> [('L1',), ('L2',)] truncated
Q7 row limit -> [('L1',), ('L2',)] truncated
Q3 read outside location -> ERROR PermissionException Permission Error: Cannot access file "/etc/hosts" - file system operations are disabled by configuration
Q4 copy out -> REJECTED by parser ['StatementType.COPY']
Q4 temp table -> REJECTED by parser ['StatementType.CREATE']
Q4 multi -> REJECTED by parser ['StatementType.SELECT', 'StatementType.SELECT']
Q4 with-select -> [(3,)] complete
Q3 unlock -> ERROR InvalidInputException
Q2 write to file -> ERROR InvalidInputException
Q6 -> InterruptException INTERRUPT Error: Interrupted!   (timer + con.interrupt(), 0.65 s; connection usable after)
Q8 absolute catalog path -> REJECTED
```

What the contracts take from this:

- Writer (Ingest): one Parquet file per table at `parquet/<table_name>.parquet`; the `catalog` table holds that relative name; `warehouse.duckdb` holds base tables only and no views, because a view would embed a location.
- Location (data adapter): one configured value, `WAREHOUSE_LOCATION`; every table path is the location joined with a catalog relative name; an absolute or `..` name is rejected.
- Reader (QueryService engine, SLICE-4): open `warehouse.duckdb` read-only; create TEMP views from the catalog; then `allowed_directories` = the location, `enable_external_access = false`, `lock_configuration = true`; accept a statement only when DuckDB's parser returns exactly one `SELECT`; fetch `row_limit + 1` rows to detect truncation; a timer calls `interrupt()` at the time limit.
- Split: the data adapter (location and relative names) is SLICE-3 (REQ-47, REQ-48, contract `CONTRACT_ADAPTER` in `contracts/warehouse_contract.py`); the DuckDB engine that reads through it is SLICE-4 (REQ-46, REQ-49, REQ-50, SEQ-6, `contracts/query_service_contract.py`).

## Batch order

1. SLICE-3 batch 5: data adapter location and relative table locations (B01, B02 core; REQ-47, REQ-48).
2. SLICE-3 batch 6: Ingest writer in the repository, through the adapter (B03; REQ-48, REQ-51).
3. SLICE-3 batch 7: rebuild, re-upload and mount-simulation check (B07; REQ-51 execution).
4. SLICE-4 batch 1 redo: DuckDB engine over the adapter replacing the regex validator and the dictionary tests (B04 to B06; REQ-46, REQ-49, REQ-50, SEQ-6).
