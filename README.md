# beacon-snap-cliff

Beacon-track prototype for DevFest Florida 2026 (DataKind food access challenge). A planner map of
Central Florida that shows where food need, small-business lending and transportation gaps overlap,
so food banks and small-business lenders can see the same places and act together.

Central Florida here means four counties: Orange, Seminole, Lake and Osceola (490 census tracts).

## What it does

The app is one map-first screen with a question box.

- **Need classes.** Each tract is a Classic Food Desert (poverty rate in the top quartile and the
  USDA LILA low-access flag), No gap flagged, or Insufficient data. "No gap flagged" does not mean
  no need.
- **Gap lenses.** Dual gap (food desert with few SBA 7(a) and 504 loans per 1,000 residents),
  transport gap (food desert with many no-vehicle households) and the triple gap, the
  "Opportunity to Serve" where all three overlap.
- **Reach.** Second Harvest food-finder sites on the map, with an adjustable distance rule that
  shows which high-need tracts have no site within reach.
- **Persona lenses.** Both partners, Food bank, Small business lender. Each lens changes which
  cards and actions come first.
- **Questions.** A question box that answers from a built-in wizard today. When the query service
  is available it answers from the warehouse through Vertex AI (Gemini) and falls back to the wizard
  with the notice "AI unavailable. Using built-in filters."
- **Citations.** Every figure on screen links to its source in `docs/data-sources.md`.

## Who it is for

- Food bank planners who decide where to send food and mobile pantries.
- SBDC, CDFI and SBA program officers who decide where to target lending and outreach.
- Judges and teammates who view the shared deployment.

## Status

The project follows CCABDD: requirements, contracts and tests come first, implementation makes
them green. The manifest is `requirements/REQUIREMENT_MANIFEST.md`.

| Slice | Part | State |
|:------|:-----|:------|
| 1 | App (React, MapLibre) and Build (Python, writes the static data) | Implemented. Unit tests pass. |
| 3 | Warehouse Ingest (DuckDB, Parquet, GCS bucket) | Implemented as library modules in `src/warehouse/`. No command-line entry point yet. |
| 4 | QueryService (warehouse questions, Vertex AI) | Contract and tests exist. No implementation yet, so `uv run pytest` fails at collection. |
| 5 | Gateway (nginx login front door) | Not started. |

The original three feature ideas (SNAP-cliff forecaster, above-the-line need finder, data blind-spot
map) were re-planned into the single alignment map above. The manifest's revision history records
the decisions.

## Getting started

Requirements: Node 26, Python 3.12 or later, and [uv](https://docs.astral.sh/uv/).

```sh
npm install
python -m src.data_prep.alignment_bundle   # Build: writes public/data/ (git-ignored)
npm run dev
```

The Build reads repo files only and fetches nothing. It writes `planner-bundle.json`,
`tracts.geojson`, `counties.geojson` and `sites.geojson` under `public/data/`. Run it before
`npm run dev` or `npm run build`, or the app has no data.

The base map loads from OpenFreeMap (`src/map/mapConstants.ts`). When the tiles fail, the app shows
"Base map unavailable" and keeps the tract layer.

### Commands

| Command | Purpose |
|:--------|:--------|
| `npm run dev` | Vite dev server |
| `npm run build` | Type-check and build to `dist/` |
| `npm run typecheck` | Type-check only |
| `npm run lint` | ESLint |
| `npm run format` / `npm run format:check` | Prettier |
| `npm test` | Vitest, one run (jsdom, Testing Library) |
| `npm run test:e2e` | Playwright against `vite preview` on port 4173, from `e2e/`. No e2e test exists yet. Run `npx playwright install chromium` once first. |
| `uv run ruff check .` | Python lint |
| `uv run ruff format --check .` | Python format check |
| `uv run mypy` | Type-check `src/warehouse/` and the warehouse contract |
| `uv run pytest -q` | Python tests (fails at collection until SLICE-4 lands) |
| `docker build -t beacon-snap-cliff .` | Cloud Run image: Node 26 build, nginx on port 8080 |

Deploy only after a human approves.

## Repository layout

| Path | Contents |
|:-----|:---------|
| `src/` | App (`App.tsx`, `map/`, `ai/`, `wizard/`), Build (`data_prep/`), warehouse Ingest (`warehouse/`) |
| `tests/` | Vitest and pytest tests |
| `requirements/`, `contracts/`, `plans/` | CCABDD spec artifacts |
| `scripts/analysis/` | One-off analyses that print every number used in the docs |
| `scripts/data_prep/` | The earlier reach-data build (`reach.json`), kept for reference |
| `data/hackathon/` | Hackathon Drive files, unmodified (checksums in `docs/hackathon/data-manifest.md`) |
| `data/external/` | Data retrieved to fill gaps, limited to the four counties. Each folder's README gives the method. |
| `docs/data-sources.md` | Citation register. Every dataset, URL and fact has an ID. |
| `docs/hackathon/` | Challenge brief, appendices and captured pages |
| `docs/taxonomy.md` | Glossary the query service sends with every question |
| `docs/mockups/` | Design documents and the earlier mockup components |
| `nginx/`, `Dockerfile` | Cloud Run image |

## Data rules

- The join key is the 11-digit tract GEOID. The tract GeoJSON has 489 geometries; tract
  `12095990000` is water and is not drawn. Two tracts have no households and show as Insufficient
  data.
- CDC PLACES transportation columns are empty for Florida. The ACS B08201 no-vehicle share is the
  stand-in, and it is a proxy, not a validated substitute.
- Nothing is inferred. Every number has a registered source. New sources go in
  `docs/data-sources.md` with their status and basis.
- Second Harvest site data is public. Redistribution permission was not requested (issue #4).

## Attribution

Beacon content is CC BY 4.0. Credit [DataKind](https://www.datakind.org) and Beacon in the app and
the write-up. The app follows the Beacon design brand guidelines in `docs/hackathon/resources/`.

## Working on this repo

- Two people and their coding agents work here. Agents talk through GitHub issues on
  `ketema/beacon-snap-cliff` (`docs/agent-coordination.md`).
- Commit messages use Conventional Commits with a scope, for example `feat(app): ...`.

## License

MIT. See [LICENSE](LICENSE).
