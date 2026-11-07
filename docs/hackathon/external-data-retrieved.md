# External data retrieved (second pass)

Captured 2026-11-07. The pages that returned 403 to plain HTTP fetches were opened in a headless Chromium session. Full page text is in `blocked-pages-text.md`. This file lists the datasets we built from them. The Second Harvest food finder has its own file: `second-harvest-food-finder-data.md`.

All tract data is limited to the four Beacon Central Florida counties: Orange (FIPS 12095), Seminole (12117), Lake (12069) and Osceola (12097).

## Datasets in `data/external/`

| Path | Source | Contents | Method |
|---|---|---|---|
| `cbpp-snap-tracker/cbpp_snap_tracker_downloadable_data.xlsx` | CBPP SNAP Tracker, data last updated 2026-10-21 | CBPP's own workbook: monthly SNAP participants by state (USDA data, state agency data, child participants), unemployment rates, source list | Downloaded from the link on the tracker page: https://apps.cbpp.org/fa2-24-26/data/downloadable_data.xlsx |
| `cbpp-snap-tracker/cbpp_florida_snap_monthly.csv` | Same workbook | Florida rows only, 2024-08 to 2026-07: USDA total, state-agency total, state-agency child, unemployment rate | Extracted by us from the workbook |
| `fema-nri/fema_nri_central_fl_tracts.csv` | FEMA National Risk Index, census-tract layer (service published by FEMA) | 489 tracts, 29 columns: risk, expected annual loss, social vulnerability, community resilience and hurricane, inland flood, coastal flood, strong wind, tornado and heat wave ratings | Queried the FEMA ArcGIS FeatureServer `National_Risk_Index_Census_Tracts` for the four counties. The 634 MB national zip was not downloaded |
| `geography/central_fl_tracts_2020.geojson` | Same FEMA layer (2020 census tract polygons) | 489 tract polygons, simplified to about 10 m, WGS84, 0.5 MB | Same query with geometry. It closes the tract-boundary gap (the hackathon files have no geometry) |
| `census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv` | US Census Bureau, ACS 2024 5-year, table B08201 (household size by vehicles available) | 490 tracts: total households, households with no vehicle, percent, margins of error | Retrieved through the Census Reporter API (https://api.censusreporter.org). The Census Bureau's own API now requires a key, so it was not used |
| `feeding-america/feeding_america_map_the_meal_gap_2024_central_fl_counties.csv` | Feeding America, Map the Meal Gap (2024 data year) | Four counties, overall and child: food insecure population (overall only), rate, share of food insecure people above or below the SNAP threshold (overall only), average meal cost, annual food budget shortfall | Read from each county's page on map.feedingamerica.org |

## Key numbers

**Florida SNAP participation (CBPP workbook, USDA series)**
- July 2025: 2,849,238. July 2026: 2,219,639. That is down 22.1%.
- Children (state-agency series): 1,114,916 in July 2025 and 867,843 in July 2026, down 22.2%.
- Unemployment rose over the same months, from 3.9% to 4.6%.
- The series has a one-month spike in November 2024 (3,441,512 in USDA data) that the state-agency series does not show. We have not confirmed why. The June 2026 USDA and state-agency values also differ by about 3%, and CBPP notes that some state data looks anomalous.
- CBPP text: Florida is one of seven states with caseload declines of 20 percent or more between July 2025 and July 2026. SNAP participation fell in every state except Alaska.

**Feeding America county estimates (2024 data)**

| County | Food insecure people | Rate | Child rate | Above SNAP threshold | Meal cost | Annual shortfall |
|---|---:|---:|---:|---:|---:|---:|
| Orange | 225,170 | 15.3% | 20.4% | 40% | $4.04 | $172.7M |
| Osceola | 77,700 | 18.2% | 21.4% | 30% | $3.80 | $56.1M |
| Seminole | 63,100 | 13.1% | 17.0% | 49% | $4.16 | $49.9M |
| Lake | 54,010 | 13.1% | 17.9% | 43% | $3.89 | $39.9M |

The pages state the SNAP threshold as 200 percent of the poverty level ("Below SNAP threshold of 200%"). Seminole's overall percentages sum to 101 because of rounding.

**Second Harvest regional figures (its Map the Meal Gap page)**
- 649,820 people, 1 in 7, are food insecure across its seven-county service area. 178,020 are children (1 in 5).
- The annual meal gap is 123.4 million meals, up 10.6%. Orange County accounts for 42.8 million.
- 38.9% of food insecure people may not qualify for SNAP on income alone. This excludes people who lose eligibility through recent policy changes.

**Florida statewide (Feeding Florida page):** over 3.2 million food insecure people, about 14% of the state, including over 800,000 children.

**USDA release, 2025-09-20 (primary source):** USDA announced the end of future Household Food Security Reports.

**UCF SBDC (Florida SBDC "Find" page):** Florida SBDC at UCF serves Brevard, Flagler, Lake, Orange, Osceola, Seminole, Sumter and Volusia counties. Phone 407-882-4850.

## Cross-checks

- Tract IDs and vintage line up across sources. Household counts in the ACS no-vehicle file match the Beacon SNAP file for all 488 tracts present in both (no difference above 5 households).
- The FEMA layer has 489 tracts. One Beacon tract, `12095990000`, is a water tract with no geometry.
- Two tracts have no vehicle percentage because they have no households.

## Combined view (computed from the files above)

In the four counties:
- 141 tracts have 20% or more of households on SNAP or 20% or more of people in poverty.
- 76 of those have no Second Harvest site inside the tract.
- 25 of those 76 also have 10% or more of households with no vehicle.
- 6 of those 76 are rated Relatively High or Very High for hurricane risk.
- Across all tracts, the share of households with no vehicle correlates about 0.52 with the SNAP share and 0.54 with the poverty rate. This supports using no-vehicle share as a stand-in for the missing transportation indicator, but it is a correlation and not a validated substitute.

## Limits

1. The FEMA service and the Census Reporter API are not the publishers' bulk downloads. Check values against the publishers before quoting them in a submission.
2. CBPP data is by state and month. There is no county or tract SNAP series here. County data from USDA FNS (DS-X1) or Florida DCF (DS-X2) is still needed to calibrate the forecaster below state level.
3. Feeding America county pages give 2024 estimates, and the child pages have no counts. A county data request is available (https://www.feedingamerica.org/research/map-the-meal-gap/by-county) if tract or finer detail is needed.
4. CDC PLACES: its current release notes say estimates for 2023 were not available for Florida for one BRFSS-based set of measures, and that the 2024 release added seven health-related social needs measures. The notes do not say why Florida's food insecurity, food stamp and transportation values are empty in our file. The likely cause is that Florida did not field the underlying survey module, but we have not confirmed that.
5. The FRAC SNAP Participation Dashboard (https://frac.org/research-resources/interactive-data-tools/snap-participation-dashboard/) and the FRAC county SNAP map are interactive tools. No downloadable file was found on their pages. The FRAC SNAP Maps meta-analysis PDF is linked at https://frac.org/wp-content/uploads/2026/09/SNAP-Maps-Meta-analysis.pdf and was not downloaded.
6. The FEMA National Risk Index overview page lists user guides and fact sheets, not downloaded here. The technical documentation is at https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf.
