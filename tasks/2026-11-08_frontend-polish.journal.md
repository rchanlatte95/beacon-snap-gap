# Journal: Frontend polish (margins, plain words, quieter map, panel overlap)

Request (Ryan, 2026-11-08): stronger left and right margins; wording at grade 8 or lower; simpler, less noisy map; fix text overlap on the right; check with screenshots; focus on what the data shows.

## Status

- 2026-11-08: done, verified. Not committed.

## Changes

- `src/app.css`: one content width (`.shell`, gutter `clamp(20px, 5vw, 80px)`, max 1480 px). The map row has a fixed height (`clamp(540px, 100vh - 260px, 900px)`), so the footer cannot draw over the panel. Map and panel are separate cards. Phone layout: lens list, two-column map key.
- `src/App.tsx`: plain words everywhere that is not pinned; findings as number + sentence; the panel body is keyed by tab and by tract, so it opens at the top; overlay pills off by default, with a small swatch each.
- `src/plainWords.ts` (new): screen text for the bundle's action, confidence and missing-indicator strings. The bundle and its Python tests are unchanged.
- `src/map/OpportunityMap.tsx`: first view fits the 97 food-desert tracts; land outside the four counties is faded by a mask above the labels; basemap POI, road-name, building, residential and minor-road layers hidden; tracts with no gap have no fill and no edge; county lines thinner.
- `src/wizard/alignmentWizard.ts`: plain card labels, hints, lens headline and tagline, query answer, action plan text. `buildExecutiveBriefing` now returns {figure, text, tone} and adds the CBPP SNAP trend (DS-X3b) and the Feeding America meal gap (DS-X9b), which were in the bundle but not on screen.

## Evidence

- `npm run typecheck` exit 0; `npm run lint` "No issues found"; `npx prettier --check src` all formatted; `npm run build` built; `npx vitest run` 1 file, 2 tests passed (tests/app.test.tsx not edited).
- Chromium (Playwright) screenshots at 1440x900, 1280x800, 1024x768, 390x844, plus tract details, list, action plan and planner lens: no page errors, no horizontal overflow, no overlapping text boxes except rows partly clipped by the panel's own scroll area. Footer top is at or below the map row bottom in every case.
- Flesch-Kincaid over visible text, one sentence per line or stop: 3.4 to 4.0. Only proper-noun lines (county names), source lists and pinned lens labels score above 8.

## Deviations

- Removed the claim "75% of SBA dollars went to tracts without high need" (card hint and briefing). Food deserts hold 20.7% of 2020 population and got 25.1% of SBA dollars and 21.9% of loans ($1,779 vs $1,383 per person); the median loan count is 10 in both groups. The 75% figure is proportional, not a gap.
- Added two findings from bundle data not shown before (SNAP trend, meal gap), as part of "focus on the insights the data provides".

## Follow-ups (need a human)

- The three lens button labels ("Shared Alignment: Opportunities to Serve", "Food Bank Planner (SNAP & Pantries)", "SBA / CDFI Lending Officer") and the legend term "Classic Food Desert" are pinned by `contracts/planner-map.app.contract.ts` and `tests/app.test.tsx`. Plain labels need a contract change by its owner.
- The "Few business loans" cohort is a median split (10 or fewer loans), so about half of all tracts fall under it. The triple-gap cohort depends on it; the team may want a better lending measure.
