# REQ-2026-001: Beacon SNAP-cliff planner map (SLICE-1, cycle 1)

## CCABDD Governance

Human owns: intent (front) + reality judgment (back).
AI owns: enforcement (middle).
Neither crosses the boundary.

The human confirms that the real-world effect matches intent.
AI MAY NOT infer success from metrics.

**INV-3**: No discretion. No judgment. Only state.
A contract executes only when all of its predicates evaluate to TRUE.

---

## Actors

| Actor | Role |
|:------|:-----|
| Planner | Food bank planner who decides where to send food and mobile pantries |
| Viewer | Anyone who opens the app, including judges and teammates, with no account |
| App | The static web application served from Cloud Run |
| Build | The offline data-preparation script that turns repo data files into the app's static data |

## 1. Intent Traceability
- **Source Prose**:
  > "We accept the recommended high impact need idea. enter req-elicit and follow all steps. we want to build an interactive web app in alignment with the track brief. use all context as initial requirements. (ideas 1,2,4 in combination) the application must have ui views for each of the main user types: food bank planner, SBDC or CDFI Program officer."
  >
  > "Two full views (option B ) is good for the first pass. PONYTAIL rules apply"
  >
  > "good enough to start so we can SEE what this looks and feels like. we will iterate from there. remember ccabdd-elegance."
  >
  > "for hosting just use my cloud run account. I accept the rest."
- **Trace gap**: The idea list that "ideas 1,2,4" refers to is not in the repo. Add it, or record where it is, so that this trace is complete.
- **Our Understanding**: SLICE-1 is the smallest working version of the Planner view. It shows Central Florida census tracts on a map, flags high-need tracts that lack a nearby pantry, lets the Planner change an assumed SNAP loss, and explains each flag. The goal of this cycle is for the human to see and feel the product, then refine. Later slices add the SBDC/CDFI officer view, saved views, approve/challenge, a policymaker summary and a flyer.
- **Ambiguity Score**: 5 (minor gaps; three decisions below block contracts). Rationale: the flow and stack are decided, but the definitions of "high need", "nearby", the slider's meaning and the Build output path are not.

## Known Ambiguities

- Z-1 definition of high need, Z-2 definition of nearby pantry, Z-3 meaning of the slider, Z-4 Cloud Run project and region, Z-5 Build output path (section 5).
- Z-1 and Z-3 must be decided together. The flag rule must use the slider value, or the slider changes no flags (section 5, "Constraint on Z-1 and Z-3").
- Second Harvest redistribution permission is not confirmed (section 6.5).

## 2. The Actor Matrix

| Actor | Permission Level | Prohibited Actions |
|:------|:-----------------|:-------------------|
| Planner | Read the map, change the scenario slider, open a tract card | Edit source data; see individual people |
| Viewer | Same as Planner | Same as Planner |
| App | Read static data files; compute flags in the browser | Call external services at runtime; store user data on a server |
| Build | Read `data/**`; write static app data | Alter files under `data/hackathon/` or `data/external/` |

## 3. The State Transition
- **Initial State ($S_0$)**: Repo holds hackathon and external data files; no app exists.
- **Transformation**: Build produces static tract data; App renders the map and card.
- **Terminal State ($S_1$)**: A Viewer opens the Cloud Run URL and sees 489 Central Florida tracts drawn on the map. Tract `12095990000` (water, no geometry) is listed in a "not drawn" note, so all 490 ACS tracts are accounted for. Tract `12095016515` has blank rates and shows as Insufficient data (REQ-8). The Viewer moves the slider, sees the flagged set change, and opens a card for any flagged tract showing evidence, a confidence label and data limitations.

## 3.5 Integration Specification

### Dependency Graph
Build DEPENDS ON the hackathon SNAP (S2201) and poverty (S1701) tables for tract rates.
Build DEPENDS ON the external ACS B08201 table (`data/external/census-acs/`, DS-X7b) for the no-vehicle rate, only if Z-1 E is chosen. These values came from the Census Reporter API, not the Census Bureau bulk files. Check them before you quote them in a submission.
Build DEPENDS ON the hackathon USDA SRAM file (DS-H6) for the LILA ½ mile / 10 mile flag, only if Z-1 B, D or E is chosen.
Build DEPENDS ON the Second Harvest site list for pantry locations.
Build DEPENDS ON the Census block file for people-near-a-pantry counts.
Build DEPENDS ON the tract GeoJSON (`data/external/geography/central_fl_tracts_2020.geojson`, 489 features) for polygons. The FEMA NRI file is a CSV with no geometry.
App DEPENDS ON the Build output for every value it shows.
App DEPENDS ON MapLibre GL JS for drawing the map.
Cloud Run DEPENDS ON a container image built from the App.

### Control Flow Requirements (Sequencing Specs)
| ID | Caller | Must Invoke | Temporal Constraint | Breaks If Missing |
|----|--------|-------------|---------------------|-------------------|
| SEQ-1 | Build | Join each pantry site to a tract and compute people-near-site counts | BEFORE it writes the static tract file | Map shows no pantry coverage |
| SEQ-2 | Build | Validate every output tract has polygon and rates, or mark it Insufficient | BEFORE it writes the static tract file | A tract silently shows blank values |
| SEQ-3 | App | Load the static tract file | BEFORE it renders the map or slider | Map draws without data |
| SEQ-4 | App | Recompute flags from the slider value | AFTER each slider change and BEFORE the next paint | Slider and map disagree |
| SEQ-5 | App | Read the clicked tract's record and its data-limitation list | BEFORE it opens the card | Card shows a flag without its caveats |

### Integration Points Checklist
| ID | Source | Target | Handoff Data | Contract Clause |
|----|--------|--------|-------------|-----------------|
| IP-1 | Hackathon tract tables | Build | SNAP household %, poverty % per tract | pending |
| IP-1b | External ACS B08201 table | Build | No-vehicle % per tract, a transportation proxy (only if Z-1 E is chosen; otherwise not loaded) | pending |
| IP-1c | Hackathon USDA SRAM file | Build | LILA ½ mile / 10 mile flag per tract (only if Z-1 B, D or E is chosen) | pending |
| IP-2 | Pantry site list | Build | Site id, lat/lng, tract id | pending |
| IP-3 | Census block file | Build | Block population and point | pending |
| IP-4 | Build | App | Static tract file (GeoJSON properties) at the Z-5 path | pending |
| IP-5 | App slider | App flagging rule | Scenario value | pending |
| IP-6 | App flagging rule | Tract card | Flag, evidence, confidence, limitations | pending |

### Lifecycle Paths
| Component | INIT (created/started by) | CLEANUP (stopped/released by) |
|-----------|--------------------------|-------------------------------|
| Build | Run by a developer or CI before the image build | Exits when files are written; leaves no state |
| App | Browser loads page from Cloud Run | Browser tab close; slider state is not stored |
| Cloud Run service | Deployed by the human's account | Removed by the human; the app has no teardown |

## 4. Hard Invariants (The "Never" List)

| ID | Category | Invariant | Verification | Priority | Rationale |
|----|----------|-----------|--------------|----------|-----------|
| INV-01 | Data integrity | REQ-1: The Build shall not alter any file under `data/hackathon/` or `data/external/`. | test | Must | Source data is the evidence base; edits would break citations |
| INV-02 | Honesty | REQ-2: The App shall not present a scenario result without the label "assumption-based estimate". | test | Must | No per-tract SNAP loss data exists; the slider is an assumption |
| INV-03 | Honesty | REQ-3: When a tract has no site under the coverage rule (Z-2), the tract card shall show the text "No Second Harvest site found under this rule. Other food sources may exist." The App shall not show the phrases "no food access" or "no access" for any tract. | test | Must | The site list is one food bank's network only, and the coverage rule (inside-tract count or straight-line distance) is an approximation |
| INV-04 | Privacy | REQ-4: The App shall not show or store data about individual people. The static tract file shall contain only tract-level fields. Block values shall appear only as tract sums, and the App data shall contain no block-level record. | test | Must | Data is tract and block aggregates only. Block population has differential-privacy noise, so a single block value is not valid |
| INV-05 | Honesty | REQ-5: The App shall not omit a missing or blank indicator from the tract card. | test | Must | Florida CDC values are blank; hiding that misleads |
| INV-06 | Scope | REQ-6: The App shall not call an external service at runtime, except map tile servers. | test | Should | Keeps the prototype static and cheap to host |
| INV-07 | Attribution | REQ-12: The App shall show, on every view, a credit to DataKind and Beacon with a link to www.datakind.org and the statement that Beacon content is CC BY 4.0. | test | Must | CC BY 4.0 requires attribution; repo rule in CLAUDE.md |
| INV-08 | Brand | REQ-13: The App shall follow `docs/hackathon/resources/beacon-design-brand-guidelines.pdf`. | human review | Must | Repo rule in CLAUDE.md. Compliance needs a person to judge it |

## 5. High-Entropy Zones (Adjudicated)
| Zone | Question | Resolution | Decided By |
|------|----------|------------|------------|
| Stack | Which technologies? | React, Vite, TypeScript, MapLibre, static data, Vitest, no AI first | User (CL4) |
| Hosting | Where does it run? | User's Google Cloud Run account | User (CL4) |
| Scope | Which views first? | Planner only in SLICE-1 | User (CL4) |
| **Z-1** | What makes a tract "high need"? (decide with Z-3) | **Unresolved** | pending |
| **Z-2** | What counts as a "nearby pantry"? | **Unresolved** | pending |
| **Z-3** | What does the slider change? (decide with Z-1) | **Unresolved** | pending |
| **Z-4** | Which Cloud Run project and region? | **Unresolved** | pending |
| **Z-5** | Where does the Build write the static tract file? | **Unresolved** | pending |

### Options and recommendations (inputs, not decisions)

Counts below come from `data/external/second-harvest-food-finder/central_fl_tract_pantry_coverage.csv` (490 tracts; 2 have blank rates), the hackathon USDA SRAM file (DS-H6; all 490 tracts join) and the ACS B08201 file. Quartile cuts use the tracts that have a value, with Python `statistics.quantiles` (exclusive method). Top-quartile cuts: poverty 17.1%, no-vehicle share 6.9%. "LILA" is the ½ mile urban / 10 mile rural low-income and low-access flag. SD is the straight-line distance version and DD is the driving distance version. "No site" means no Second Harvest site inside the tract (Z-2 A).

- **Z-1 high need.**
  - A) SNAP households 20% or more OR poverty 20% or more: 141 tracts, 76 with no site. Simple. Does not use LILA.
  - B) The brief's "Classic Food Desert" rule, top-quartile poverty AND LILA: SD 68 tracts (40 with no site), DD 97 tracts (52 with no site).
  - C) A weighted score.
  - D) A AND LILA: SD 80 tracts (48 with no site), DD 111 tracts (58 with no site). Keeps A's plain thresholds and adds the brief's access test.
  - E) Top-quartile poverty AND (LILA OR top-quartile no-vehicle share): SD 109 tracts (59 with no site), DD 113 tracts (61 with no site). Uses no-vehicle share as the third Central Florida signal that the brief asks teams to try (`docs/hackathon/beacon-appendices.md:91`). The card must label it a proxy: it correlates about 0.52 with SNAP share and is not a validated substitute (F-1).
  - Sub-decision for B, D and E: SD or DD. The brief does not say which. No recommendation.
  - Revised recommendation: B, because it is the brief's own rule (`docs/hackathon/beacon-appendices.md:63` and `:70`) and judges will compare entries with it. Show A's rates on the card. E can be a second mode. The cycle 1 draft recommended A, but A does not use LILA, and the brief tells teams to use LILA.
- **Z-2 nearby.** A) A Second Harvest site inside the tract (76 of the 141 Z-1 A tracts have none). B) At least one site within 1 mile of the tract's center. C) The share of the tract's block population within 1 mile of a site. Recommend C, because the Census 2020 block file (`data/external/census-2020-blocks/`) was added for this purpose, with A shown beside it. Block population is for April 2020 and has differential-privacy noise, so use only tract sums.
- **Z-3 slider.** Let s be the scenario value: extra SNAP loss as a percent of current SNAP households. Let "displaced households" for a tract be `snap_households × s / 100`. This is an assumption-based estimate (REQ-2), because no tract-level SNAP-cut data exists (DS-X1 and DS-X2 are not downloaded).
  - A) s raises each tract's displaced households proportionally. Recommend A, because it is plain arithmetic and labeled as an assumption.
  - B) Same, scaled by tract-level risk (poverty).
  - C) A county total spread by SNAP share.
  - D) The slider moves the Z-1 need threshold instead of SNAP loss. This is a threshold sensitivity test, which the brief suggests for Challenge 1 (`docs/hackathon/beacon-appendices.md:56`). It always changes the flagged set, but it is not a SNAP-cut scenario, so it does not serve the SNAP-cliff feature.
- **Constraint on Z-1 and Z-3.** Z-3 A, B and C multiply every tract by the same factor or by a fixed tract weight. Z-1 A, B, D and E use only rates. If the flag rule uses only rates, the slider changes no flags, and the completion promise (section 8) fails. The flag rule must include the scenario value.
  - F) Combined rule: flag a tract when it meets the Z-1 rule AND it has no nearby site under Z-2 AND its displaced households are N or more. N is a human decision. Check with Z-1 A, Z-2 A and N = 50: s = 5% flags 2 tracts, 10% flags 27, 20% flags 59, 50% flags 71 and 100% flags 74. Recommend F with Z-3 A arithmetic, because the flagged set then changes with the slider and a test can recompute it from the source data.
- **Z-4 deployment.** The active gcloud configuration points at project `ai-panel-ephemeral-org`, which looks unrelated. Options: that project; another project of yours; a new one. Region also needed. No recommendation until you name the project.
- **Z-5 Build output path.** Recommend `public/data/tracts.geojson`. The taxonomy classes `public/**` as production code, Vite serves it as a static file, and the INV-01 test can check that the Build writes only under `public/data/`.

## 5.5 Rejected Alternatives
| Decision | Alternative Considered | Why Rejected |
|----------|----------------------|--------------|
| Static data in the repo | A backend with a database | Adds infrastructure and a security surface for no first-pass benefit |
| Rule-based "why flagged" | An LLM-written explanation | Cannot be verified; adds a runtime dependency |
| Cloud Run | GitHub Pages | User chose Cloud Run |

### Deferred map alternatives (not decisions; test later if needed)

These are candidates for each mapping job. They are not chosen and not rejected. Test a row only when its trigger occurs. "Runs in" tells where the tool would run. Any App-side row that calls a service at runtime must be checked against INV-06 before use. Usage limits and terms in this table are from memory and are not verified; confirm them on the provider's site before a test.

| Job | Current plan | Alternative | Runs in | INV-06 fit | Trigger to test it | Test to run |
|-----|-------------|-------------|---------|------------|--------------------|-------------|
| Map library | MapLibre GL JS | Leaflet | App | Yes (library is bundled) | MapLibre WebGL fails on a target device, or the team needs a simpler API | Render the 489 tract polygons and the tract card; compare load time and bundle size |
| Map library | MapLibre GL JS | Google Maps JavaScript API | App | Partial: tiles only. Places, Routes and Geocoding calls would break INV-06 | A stakeholder requires Google base maps | Confirm API key, billing and Places storage terms first. The key is visible in a static app |
| Base map tiles | Not named in this manifest | OpenFreeMap (hosted OSM vector tiles, no key) | App | Yes (tile server) | Choose a tile source for REQ-10 | Load tiles; block the tile host and confirm "Base map unavailable" (REQ-10) |
| Base map tiles | Not named | Protomaps PMTiles file served from the same Cloud Run container | App | Yes (no external service at all) | Tile host limits, outages or an offline demo | Serve one PMTiles file for the 4 counties; check file size and container size |
| Base map tiles | Not named | `tile.openstreetmap.org` raster tiles | App | Yes (tile server) | Quick local demo only. The OSM tile usage policy forbids heavy use | Local smoke test only; not for the deployed URL |
| Geocoding (address to tract) | Census Bureau Geocoder, already used for the 424 Second Harvest sites (DS-X27) | Nominatim (OSM geocoder; public server about 1 request per second) | Build | Yes (Build only) | A new pantry list without tract IDs, for example DS-X13 | Geocode the 424 Second Harvest addresses; compare tract IDs with the DS-X27 results |
| Point-to-tract join | Census Geocoder tract IDs | geopandas (Python) or turf.js (TypeScript) point-in-polygon with the 2020 tract GeoJSON | Build | Yes | Join SNAP retailers (DS-H8) or other points without a geocoder call | Join the 424 sites by polygon; the result must equal the DS-X27 tract IDs |
| Distance to pantry | Straight-line distance from each populated 2020 block point to the nearest site (Z-2 option C) | OpenRouteService API (driving and walking matrix, isochrones; free key) | Build | Yes (Build only; a runtime call breaks INV-06) | Planners say straight-line distance misleads, for example across lakes or highways | Compare straight-line and road distance for the high-need tracts under the chosen Z-1 rule; report the tracts whose flag changes |
| Distance to pantry | Straight-line | OSRM, Valhalla or GraphHopper on a Florida OSM extract (self-hosted) | Build | Yes | Same trigger, and ORS limits are too low | Same comparison as the row above |
| Transit time | None (no transit data in the repo) | r5py or OpenTripPlanner with OSM streets and a LYNX GTFS feed (feed not yet confirmed) | Build | Yes | The plan must cover the 50,303 households with no vehicle (USDA `TractHUNV`, DS-H6) | Confirm that a LYNX GTFS feed exists; compute transit time from block points to sites for one county first |
| Pantry and food-store points | Second Harvest partner sites (DS-X12) and SNAP retailers (DS-H8) | OSM via Overpass API (`amenity=food_bank`, `social_facility=food_bank`) | Build | Yes | Look for pantries that are not Second Harvest partners (data blind-spot map) | List OSM pantries in the 4 counties that are farther than 0.25 mi from every DS-X12 site |
| Pantry and food-store points | Same | Overture Maps Places | Build | Yes | Same trigger, or OSM coverage is too thin | Same test as the row above; record the license terms |

## 6. Tool/API Interface Summary
| Interface | Purpose | Mutates State? | Called By | Triggered When |
|-----------|---------|----------------|----------|---------------|
| build-tract-data | Produce the static tract file | YES (writes app data only) | Build | A developer or CI runs it |
| loadTractData | Load the static file | NO | App | Page load |
| computeFlags(scenario) | Flag high-need tracts without nearby pantries | NO | App | Slider change |
| buildTractCard(tractId) | Evidence, confidence, limitations | NO | App | Tract click |

## 6.5 Blocking Dependencies
| Unresolved Zone | Blocks |
|-----------------|--------|
| Z-1 (with Z-3) | Contract for the flagging rule, tests, implementation |
| Z-1 sub-decision: SD or DD LILA | Build (LILA column), if Z-1 B, D or E is chosen |
| Z-2 | Contract for pantry coverage, Build, tests |
| Z-3 (with Z-1) | Contract for the slider, tests |
| Z-4 | Deployment only (not contracts) |
| Z-5 | Build, INV-01 test |
| Second Harvest redistribution permission (not confirmed) | Public deployment of site names and locations (CLAUDE.md rule). Contracts, tests and local builds are not blocked |

## 7. Failure Mode Specification (CL9)

| Requirement | Failure Condition | Behavior | Notification |
|------------|-------------------|----------|-------------|
| REQ-7 | Static tract file is missing or fails to parse | Halt: the App draws no map | The App shall show an error naming the file |
| REQ-8 | A tract has a missing indicator | Show the tract as Insufficient data, not as low need | Card names the missing indicator |
| REQ-9 | Build input file is missing or has changed columns | Halt: the Build exits non-zero | The Build shall name the file and column |
| REQ-10 | Map tiles fail to load | FALLBACK: draw tracts on a blank background | The App shall display "Base map unavailable" |
| REQ-11 | Slider value is outside its range | Clamp to the range | The slider shows the clamped value |

## 8. Completion Promise (Ralph Loop Exit)
> "A Viewer opens the deployed URL, sees 489 tracts drawn and tract 12095990000 listed as not drawn (no geometry), moves the slider and sees the flagged set change by an amount a test can recompute from the source data, and opens a card whose evidence matches the source tables for that tract and names every missing indicator. A test that passes while the card omits a missing indicator, or while the slider changes only the label, must fail."

Human acceptance remains with the human: whether the map and card are useful to a food bank planner.

## 9. Contract Authority
**Authoritative Source**: `contracts/planner_map_contract.py` (to be authored after zones Z-1 to Z-3 are resolved)

requirements/REQUIREMENT_MANIFEST.md (this file)
        ↓
plans/planner-map.plan.yml (SLICE-1, drafted after the manifest is linted)
        ↓
contracts/planner_map_contract.py
        ↓
tests/
        ↓
src/

## 10. Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-11-07 | Ketema, agent | Cycle 1 draft from req-elicit. Zones Z-1 to Z-4 open. |
| 2026-11-07 | Ryan Chanlatte, agent | Cycle 1 review. Corrected tract count (489 drawn), polygon and no-vehicle sources, and the reversed Rejected Alternatives row. Made INV-03 and INV-04 testable. Added INV-07 (attribution), INV-08 (brand), Z-5 (Build output path) and the Second Harvest permission dependency. Added Z-1 options D and E with counts, revised the Z-1 recommendation to B, and added Z-3 option D and combined rule F. Zones Z-1 to Z-5 open. |
| 2026-11-07 | Ryan Chanlatte, agent | Added "Deferred map alternatives" under 5.5: candidate map library, tile, geocoding, routing, transit and point-data tools, each with a trigger and a test. No decision changed. |
