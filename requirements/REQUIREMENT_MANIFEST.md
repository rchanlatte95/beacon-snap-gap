# REQ-2026-001: Beacon SNAP-cliff planner map (SLICE-1, cycle 4)

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
- **Our Understanding**: SLICE-1 is the smallest working version of the Planner view. It shows Central Florida census tracts on a map, flags high-need tracts that lack a nearby pantry, and explains each flag on a tract card. The SNAP-loss slider is stashed (Z-3) until the human has seen this first deliverable. The goal of this cycle is for the human to see and feel the product, then refine. Later slices add the slider, the SBDC/CDFI officer view, saved views, approve/challenge, a policymaker summary and a flyer.
- **Ambiguity Score**: 2 (ready for contracts). Rationale: flow, stack, scope, the high-need rule and the pantry-coverage rule are decided. Z-3 is deferred by both humans. Z-4 (Cloud Run project and region) blocks deployment only.

## Known Ambiguities

- Z-4 Cloud Run project and region (section 5). Z-3 (slider) is deferred.

## 2. The Actor Matrix

| Actor | Permission Level | Prohibited Actions |
|:------|:-----------------|:-------------------|
| Planner | Read the map, open a tract card | Edit source data; see individual people |
| Viewer | Same as Planner | Same as Planner |
| App | Read static data files; compute flags in the browser | Call external services at runtime; store user data on a server |
| Build | Read `data/**`; write static app data | Alter files under `data/hackathon/` or `data/external/` |

## 3. The State Transition
- **Initial State ($S_0$)**: Repo holds hackathon and external data files; no app exists.
- **Transformation**: Build produces static tract data; App renders the map and card.
- **Terminal State ($S_1$)**: A Viewer opens the Cloud Run URL, sees 490 Central Florida tracts colored by flag status, and opens a card for any flagged tract showing evidence, a confidence label and data limitations.

## 3.5 Integration Specification

### Dependency Graph
Build DEPENDS ON the hackathon SNAP, poverty and no-vehicle tables for tract rates.
Build DEPENDS ON the Second Harvest site list for pantry locations.
Build DEPENDS ON the Census block file for people-near-a-pantry counts.
Build DEPENDS ON the FEMA tract file for polygons.
App DEPENDS ON the Build output for every value it shows.
App DEPENDS ON MapLibre GL JS for drawing the map.
Cloud Run DEPENDS ON a container image built from the App.

### Control Flow Requirements (Sequencing Specs)
| ID | Caller | Must Invoke | Temporal Constraint | Breaks If Missing |
|----|--------|-------------|---------------------|-------------------|
| SEQ-1 | Build | Join each pantry site to a tract and compute people-near-site counts | BEFORE it writes the static tract file | Map shows no pantry coverage |
| SEQ-2 | Build | Validate every output tract has polygon and rates, or mark it Insufficient | BEFORE it writes the static tract file | A tract silently shows blank values |
| SEQ-3 | App | Load the static tract file | BEFORE it renders the map | Map draws without data |
| SEQ-4 | App | Read the clicked tract's record and its data-limitation list | BEFORE it opens the card | Card shows a flag without its caveats |

### Integration Points Checklist
| ID | Source | Target | Handoff Data | Contract Clause |
|----|--------|--------|-------------|-----------------|
| IP-1 | Hackathon tract tables | Build | SNAP household %, poverty %, no-vehicle % per tract | pending |
| IP-2 | Pantry site list | Build | Site id, lat/lng, tract id | pending |
| IP-3 | Census block file | Build | Block population and point | pending |
| IP-4 | Build | App | Static tract file (GeoJSON properties) | pending |
| IP-5 | App flagging rule | Tract card | Flag, evidence, confidence, limitations | pending |

### Lifecycle Paths
| Component | INIT (created/started by) | CLEANUP (stopped/released by) |
|-----------|--------------------------|-------------------------------|
| Build | Run by a developer or CI before the image build | Exits when files are written; leaves no state |
| App | Browser loads page from Cloud Run | Browser tab close; the App keeps no state |
| Cloud Run service | Deployed by the human's account | Removed by the human; the app has no teardown |

## 4. Hard Invariants (The "Never" List)

| ID | Category | Invariant | Verification | Priority | Rationale |
|----|----------|-----------|--------------|----------|-----------|
| INV-01 | Data integrity | REQ-1: The Build shall not alter any file under `data/hackathon/` or `data/external/`. | test | Must | Source data is the evidence base; edits would break citations |
| INV-03 | Honesty | REQ-3: The App shall not state or imply that a tract with no pantry site has no food access. | test | Must | Sites are counted only inside tract boundaries and the list is partial |
| INV-04 | Privacy | REQ-4: The App shall not show or store data about individual people. | test | Must | Data is tract and block aggregates only |
| INV-05 | Honesty | REQ-5: The App shall not omit a missing or blank indicator from the tract card. | test | Must | Florida CDC values are blank; hiding that misleads |
| INV-06 | Scope | REQ-6: The App shall not call an external service at runtime, except map tile servers. | test | Should | Keeps the prototype static and cheap to host |

## 5. High-Entropy Zones (Adjudicated)
| Zone | Question | Resolution | Decided By |
|------|----------|------------|------------|
| Stack | Which technologies? | React, Vite, TypeScript, MapLibre, static data, Vitest, no AI first | User (CL4) |
| Hosting | Where does it run? | User's Google Cloud Run account | User (CL4) |
| Scope | Which views first? | Planner only in SLICE-1 | User (CL4) |
| **Z-1** | What makes a tract "high need"? | **Option B with driving-distance LILA**: poverty rate at or above the 75th percentile of the 490 Central Florida tracts (17.0%, ACS 2024) AND the USDA driving-distance LILA flag (`DD_SRAM_LILATracts_halfAnd10`: 1/2 mile urban, 10 miles rural). This flags 97 tracts. Straight-line (Euclidean) LILA, 68 tracts, was considered | B proposed by Ryan, confirmed by Ketema; driving distance chosen by Ketema (CL4), 2026-11-07 |
| **Z-2** | What counts as a "nearby pantry"? | **Option C shown beside A**: the share of the tract's block population within 1 mile of a Second Harvest site, shown beside whether a site lies inside the tract | Ryan proposed 2026-11-07 (issue #4); Ketema confirmed (CL4) |
| **Z-3** | What does the slider change? | **Deferred** until mock-ups or proofs of concept are rendered; Ryan's option A is kept as input for that step | Ketema and Ryan (CL4), 2026-11-07 |
| **Z-4** | Which Cloud Run project and region? | **Unresolved** | pending |

### Options and recommendations (inputs, not decisions)
- **Z-1 high need.** A) SNAP households 20% or more OR poverty 20% or more (gives 141 tracts; simple). B) The brief's quartile rule: top-quartile poverty plus a LILA flag. C) A weighted score. Recommend A for cycle 1, because it is easy to explain and to see. B can be a second mode.
- **Z-2 nearby.** A) A Second Harvest site inside the tract (76 of the 141 have none). B) At least one site within 1 mile of the tract's center. C) The share of the tract's block population within 1 mile of a site. Recommend C, because it is what Ryan's block data was added for, with A shown beside it.
- **Z-3 slider (deferred).** Options kept for the later slice: A) Extra SNAP loss as a percent of current SNAP households. B) Same, scaled by tract poverty. C) A county total spread by SNAP share. The human found the slider confusing and asked to see the first deliverable before deciding; a visual mock accompanies the question when it returns.
- **Z-4 deployment.** The active gcloud configuration points at project `ai-panel-ephemeral-org`, which looks unrelated. Options: that project; another project of yours; a new one. Region also needed. No recommendation until you name the project.

### Deferred items (stashed with Z-3; written as obligations when the slider slice starts)
- REQ-2 (deferred): every scenario result carries the label "assumption-based estimate", because no per-tract SNAP loss data exists.
- REQ-11 (deferred): an out-of-range slider value is clamped to the range and the clamped value is shown.
- SEQ-S (deferred): flags are recomputed after each slider change and before the next paint, so the slider and map agree.

## 5.5 Rejected Alternatives
| Decision | Alternative Considered | Why Rejected |
|----------|----------------------|--------------|
| Static data in the repo | A backend with a database | Adds infrastructure and a security surface for no first-pass benefit |
| Rule-based "why flagged" | An LLM-written explanation | Cannot be verified; adds a runtime dependency |
| GitHub Pages | Cloud Run | User chose Cloud Run |

## 6. Tool/API Interface Summary
| Interface | Purpose | Mutates State? | Called By | Triggered When |
|-----------|---------|----------------|----------|---------------|
| build-tract-data | Produce the static tract file | YES (writes app data only) | Build | A developer or CI runs it |
| loadTractData | Load the static file | NO | App | Page load |
| computeFlags() | Flag high-need tracts without nearby pantries | NO | App | Page load |
| buildTractCard(tractId) | Evidence, confidence, limitations | NO | App | Tract click |

## 6.5 Blocking Dependencies
| Unresolved Zone | Blocks |
|-----------------|--------|
| Z-1 | Decided; the flagging contract defines the 97-tract rule and its quartile basis |
| Z-2 | Decided; the contract for pantry coverage defines the block-population radius |
| Z-3 | Deferred; blocks only the later slider slice |
| Z-4 | Deployment only (not contracts) |

## 7. Failure Mode Specification (CL9)

| Requirement | Failure Condition | Behavior | Notification |
|------------|-------------------|----------|-------------|
| REQ-7 | Static tract file is missing or fails to parse | Halt: the App draws no map | The App shall show an error naming the file |
| REQ-8 | A tract has a missing indicator | Show the tract as Insufficient data, not as low need | Card names the missing indicator |
| REQ-9 | Build input file is missing or has changed columns | Halt: the Build exits non-zero | The Build shall name the file and column |
| REQ-10 | Map tiles fail to load | FALLBACK: draw tracts on a blank background | The App shall display "Base map unavailable" |

## 8. Completion Promise (Ralph Loop Exit)
> "A Viewer opens the deployed URL, sees 490 tracts colored by flag status, and the flagged set equals a set a test recomputes from the source data. The Viewer opens a card whose evidence matches the source tables for that tract and names every missing indicator. A test that passes while the card omits a missing indicator, or while the flagged set differs from the recomputed set, must fail."

Human acceptance remains with the human: whether the map and card are useful to a food bank planner.

## 9. Contract Authority
**Authoritative Source**: `contracts/planner_map_contract.py` (to be authored once the human approves the SLICE-1 plan)

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
| 2026-11-07 | Ketema, agent | Cycle 2: the human stashed the slider (Z-3 deferred) after finding it confusing. Removed from SLICE-1 scope: slider, scenario label (REQ-2), range clamp (REQ-11), the slider sequencing spec and integration point. SEQ and IP numbers renumbered. Ambiguity score 5 to 4. |
| 2026-11-07 | Ketema, agent | Cycle 3: Z-1 option B and Z-2 option C beside A recorded (proposed by Ryan, confirmed by Ketema). Z-3 deferred by both humans. Z-1b LILA distance type remains open. Ambiguity score 4 to 3. |
| 2026-11-07 | Ketema, agent | Cycle 4: Z-1b recorded. The human chose driving-distance LILA (97 tracts). Ambiguity score 3 to 2. Only Z-4 remains open, and it blocks deployment only. |
