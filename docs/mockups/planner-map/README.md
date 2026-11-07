# Planner map mock-up (SLICE-1 layout)

A clickable mock-up of the SLICE-1 Planner view. It is design and layout work only. It is not the App: the App in `src/` is written after the CONTRACTS and RED phases of each batch, and it reads the Build output `public/data/tracts.geojson` (Z-5). Vite does not put this page in `dist/`, so it is not in the Cloud Run image.

## Run it

```bash
node docs/mockups/planner-map/make-standin.mjs   # only if data/ changed; the output is committed
npm run dev
# open http://localhost:5173/docs/mockups/planner-map/
```

## What it shows

- 489 drawn tracts in the three REQ-14 classes, with a REQ-15 legend: Classic Food Desert (high need) 97, No gap flagged 391, Insufficient data 1 drawn. Tract `12095990000` (water, no shape) is in a "not drawn" note, so all 490 tracts are accounted for.
- A pantry coverage layer on the 97 high-need tracts only. You can switch it between load (Z-2e) and reach. Second Harvest sites are an optional layer.
- A tract card: why the tract has its class, pantry coverage, context indicators, a confidence label, every missing indicator (REQ-5), the REQ-3 text when no site is found, and sources.
- A list of the 97 high-need tracts, with a county filter and sort.
- A blank background with "Base map unavailable", because no tile source is chosen (Z-6, REQ-10). The page calls no outside service.
- The REQ-7 error: if a data file is missing or does not parse, the page names the file and draws no map.
- The DataKind and Beacon credit and the CC BY 4.0 statement on the page (REQ-12). The colors and type follow the Beacon brand guide (REQ-13, needs human review).

## Stand-in data

`make-standin.mjs` reads `data/**` and writes `data/*.json` in this folder. It does not write to `data/hackathon/` or `data/external/`. The output has tract-level fields only (REQ-4, REQ-17).

The class counts are real, and the script uses the class rule from `contracts/planner_map_contract.py`. It stops unless the counts are 97 / 391 / 2.

- The poverty cut is 17.025%: `statistics.quantiles(n=4, method='inclusive')` over 488 tracts, not rounded (POST-CLS-3).
- A tract is Insufficient data only when its poverty rate or its driving-distance LILA flag is blank (POST-CLS-2). A blank SNAP share goes in the card's list of missing indicators, but it does not change the class.

SNAP and poverty rates come from the hackathon S2201 and S1701 zips. The script checks them against `central_fl_tract_pantry_coverage.csv`.

These parts are stand-ins, and the page labels them:

| Item | Stand-in | Decided rule |
|---|---|---|
| Reach | 10 miles straight-line from each populated 2020 block to a site | 30-minute drive (Z-2, Z-2b, Z-2d). This needs routing data that is not in the repo |
| Load | Tract 2020 population ÷ sites within the stand-in reach | Residents per site within reach (Z-2e) |
| Confidence label | Three candidate rules, picked in the sidebar, with the words High / Medium / Low / Not rated (Appendix B wording). A: Low if under 500 households or over 20% group quarters, else Medium. B: Low if the tract is LILA and its poverty rate is within 2 points of the cut, else Medium. C: counts the A and B tests (none is High, one is Medium, two or more is Low). The 500, 20% and 2-point thresholds are stand-ins | Not decided. A human must confirm a rule before it goes in a contract |

## Questions this mock-up can help answer

- **Z-2e (decided: option A, load; Ketema and Ryan, cycle 11).** The mock-up shows reach too, only to compare. With the stand-in reach, all 97 high-need tracts are 100% in reach, but load goes from 19 to 1,050 residents per site. The manifest's drive-time test also put all 97 tracts in reach at 15 minutes. This supports the decision for load.
- **Z-3 (slider).** The sidebar has a disabled slider placeholder that shows where the slider could go.
- **Confidence label.** A rule is needed. The sidebar switches between three candidate rules and shows how many tracts get each level. Rules A and B never give High, because no rule can check the ACS margins of error: the repo has no poverty-rate margins of error. Rule C gives High when no test finds a limit.

## Note for the App

MapLibre GL JS 6 loads its worker from a path next to its own module URL. Vite moves the module, so the worker does not load and no tracts are drawn. The fix is `setWorkerUrl()` with the worker file imported as `?url` (see `PlannerMock.tsx`). The App needs the same fix.
