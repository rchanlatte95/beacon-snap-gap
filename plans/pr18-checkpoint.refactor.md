# DISCONNECT MATRIX: PR #18 checkpoint (constitutional refactor)

**Date**: 2026-11-08
**Branch**: `data/hackathon-sources` at `4a37356` (main with PR #18, `2c082d8`, merged in)
**Decision**: Ketema, 2026-11-08: "the slider concept is the same: making hard coded taxonomy definitions dynamic (adjustable thresholds). so to me pr 18 is fine for feedback input. i would say merge it and treat it as a check point. pivot from it and execute consitutional refactor to define how to align with intent and get everythign wired up." On how "nearby" is measured: "2 - A", the share of each tract's block population within the threshold.
**Delegation**: Ketema: "after the disconnect matrix, requirements and contracts are updated i think you should delegate that work to ryan's agent and you work on the ai slice."

## Summary

| Metric | Count |
|--------|-------|
| Total behaviors | 9 |
| OVERRIDE | 4 (B01, B05, B06, B08) |
| NEW | 5 (B02, B03, B04, B07, B09) |
| REMOVE | 0 |
| KEEP | the display of gap emphasis and the proximity controls' layout (B04, B01 front end), pending requirements |

## Matrix

| ID | Behavior | EXPECTED | OBSERVED (execution) | DELTA | Location | Priority |
|----|----------|----------|----------|-------|----------|----------|
| B01 | "Nearby" reach under an adjustable threshold | One definition: the share of each tract's block population within the threshold of a Second Harvest site (Z-2, Ketema 2-A), computed once in the Build from block points. The card, map, shortlist and AI (REQ-35 `sites.near`) all show the same numbers; the slider only changes the threshold. Straight-line until #16 supplies drive time. | The browser computes its own straight-line distance from one tract centre (`proximity.ts`). At the same 10 miles it disagrees with the Build's `sites_in_reach` for **478 of 489** drawn tracts (95 of 97 Classic Food Deserts); e.g. tract `12069030102`: Build 17 sites, browser 2 (O1). | OVERRIDE | `src/map/proximity.ts`; `src/data_prep/alignment_bundle.py:52,281` | P1 |
| B02 | Time shown beside distance | A stated rule: minutes come from a drive-time source (#16), or are shown as an assumption-based estimate under a requirement. | Minutes = straight-line miles x 3, labelled on screen "an assumption-based estimate, without road routes or traffic" (no requirement states this rule) (O2). | NEW | `src/map/ProximityControls.tsx`, `proximity.ts` | P2 |
| B03 | Other taxonomy thresholds adjustable | Ketema: "making hard coded taxonomy definitions dynamic (adjustable thresholds)". Which definitions is open (zone Z-24). | Fixed in the Build: poverty 75th percentile (17.025%), no-vehicle 75th percentile (6.90%), SBA loans per 1,000 residents bottom quartile (0.9427) with the 1,200-resident floor, reach 10 miles, confidence 500 households / 20% group quarters (O3). Only reach is adjustable in the App. | NEW | `alignment_bundle.py`, `docs/taxonomy.md` | P1 (decision) |
| B04 | Gap emphasis | A requirement and contract clause for the toggle, the outlined group, the faded rest, and the "N on map; N without a map shape" context line. | Implemented and covered by `tests/gap-emphasis.test.tsx`, which cites no clause (O4: 15 of 15 app tests pass at `4a37356`). | NEW (contract existing behavior) | `src/App.tsx`, `src/map/OpportunityMap.tsx` | P2 |
| B05 | Source citations | The source list comes from the registry and the warehouse provenance (REQ-29), written into the bundle by the Build; the App renders it. | Hand-typed: `src/dataSources.ts` exports 13 sources (id, label, publisher, period, url, method, limits); all 13 IDs match the registry and `docs/data-sources.md` today (O5), but the facts are a second copy. | OVERRIDE | `src/dataSources.ts`, `src/SourceCitations.tsx` | P2 |
| B06 | Taxonomy sent to the model (REQ-36) | Defines the dual gap by the Z-23 rule. | `docs/taxonomy.md:31` still says "at or below the regional median of 10 SBA loans ... 50 tracts" (O3); a REQ-19 follow-up missed in cycle 16. | OVERRIDE | `docs/taxonomy.md:31` | P1 |
| B07 | Pitch outline in `docs/` | Registered so the retained-source rule passes (ERRORS-RET-2). | Unregistered since the merge; the Ingest stops on it (Ryan's agent, comment 6724086682). | NEW | `data/warehouse/source_registry.toml` | P1 |
| B08 | Tests that need Poppler, LibreOffice or DuckDB spatial | Skip with a stated reason when the tool is absent (design-by-contract: a missing dependency surfaces as SKIP). | 7 fail on Windows 11 (Ryan's agent, comment 6724167114): 5 for absent `pdfinfo`, `soffice` or the spatial extension; 2 for path portability: `test_adapter.py` builds a drive-letter path that `PurePosixPath` never treats as absolute, and `test_registry.py:286` looks for `str(path)` in a message formatted with `!r`. Neither affects Cloud Run. | OVERRIDE | `tests/warehouse/` | P2 |
| B09 | The three new test files | Each test cites a clause in the contract. | `tests/gap-emphasis.test.tsx`, `tests/proximity.test.tsx`, `tests/proximity-details.test.tsx` cite none. | NEW (map to clauses) | `tests/` | P2 |

## Evidence

- **O1** (Bun, real modules, 2026-11-08): `src/map/proximity.ts` `sitesWithinMiles(centroid, sites, 10)` against `public/data/planner-bundle.json` `sites_in_reach` over 490 tracts: agree 11, differ 478, no centroid 1; Classic Food Deserts differing 95 of 97; no food desert has its nearest site beyond 10 miles.
- **O2**: `ProximityControls.tsx` note at `4a37356`: "Time uses 10 miles = 30 minutes: an assumption-based estimate, without road routes or traffic."
- **O3**: `docs/taxonomy.md` threshold lines 11-42; Build constants in `alignment_bundle.py`.
- **O4**: full gates at `4a37356` (Build first): vitest 15 of 15, typecheck, lint, format, build pass.
- **O5**: `src/dataSources.ts` `DATA_SOURCES`: 13 IDs, all present in the registry and `docs/data-sources.md`.

## Zones (decided)

- **Z-24 A** (Ketema, "1 - A"): reach plus the poverty, no-vehicle and SBA-per-1,000 cuts adjustable as percentiles. REQ-55 to REQ-65.
- **Z-25 A** (Ketema, "2 - A"): miles only, no minutes. REQ-57.
- Implementation details chosen by jev at Ketema's direction (highest rated): reach 0 to 20 miles by 0.5 (0.88); within the limit when any populated block is in reach (0.71); cuts at named percentiles 50/75/90 and 10/25/50 (0.73).

## Next

After Ketema resolves Z-24 and Z-25:
1. Requirements (manifest, lint), then contracts (Build outputs for reach under the threshold and for the source list; App clauses for B01, B04, B05).
2. Failing tests, with B09 mapped.
3. Handoff to Ryan's agent for the implementation.
4. Ketema's agent moves to SLICE-4 (AI).
