# Second Harvest food finder: retrieved data

Files: `data/external/second-harvest-food-finder/`

## Source
- Page: https://feedhopenow.org/find-help/food-finder/ (Second Harvest Food Bank of Central Florida, "Food Locator").
- Retrieved: 2026-11-07.
- Covers partner sites in Brevard, Lake, Marion, Orange, Osceola, Seminole and Volusia counties, per the page.

## How it was retrieved
1. Plain HTTP fetches of the page returned 403 (bot block).
2. A headless Chromium session loaded the page normally. The list shows each site's name, days/hours, address, phone and a "Show on Map" link.
3. The page loads its data from a public feed of its map widget (Store Locator Widgets). That feed carries 424 sites with names, hours text, addresses, phone numbers and latitude/longitude.
4. The feed also carries unrelated widget settings, including map-service identifiers. Those were not saved. Only the `stores` list was kept.
5. Each site's coordinates were matched to a census tract and county with the Census Bureau geocoder (`geocoding.geo.census.gov`, coordinates endpoint, current benchmark and vintage). All 424 matched.

## Files
| File | Contents |
|---|---|
| `second_harvest_food_finder_raw_stores.json` | The `stores` list as published (424 entries) |
| `second_harvest_food_finder_locations.csv` | One row per site: id, name, hours text, address, ZIP, phone, lat, lng, tract GEOID, county |
| `central_fl_tract_pantry_coverage.csv` | The 490 Beacon tracts in Orange, Seminole, Lake and Osceola counties, with households, SNAP households, percent SNAP, percent poverty (ACS 2024 5-year, from the Beacon files) and the count of Second Harvest sites in the tract |

## What it shows
- 424 sites in total. By county: Orange 143, Volusia 69, Brevard 51, Lake 45, Marion 45, Osceola 31, Seminole 28, others 12.
- 179 of the 424 hours texts mention "TEFAP Agency" (a federal commodity program partner). Hours are free text, such as "2nd Saturday 8am-10am", not structured.
- Inside the four Beacon counties: 247 sites, all falling inside a Beacon tract. 154 of the 490 tracts contain at least one site.
- Tracts with poverty of 20% or more: 87, of which 45 contain no site.
- Tracts with 20% or more of households on SNAP: 107, of which 56 contain no site.

## Limits
1. A site is counted only in the tract where it sits. People cross tract lines, so a tract with zero sites is not necessarily without access. Distance-based access is a better measure.
2. These are partner sites that the food bank lists, not every pantry in the area. Other pantries and churches are not here.
3. Hours are free text and can be out of date. The page itself says to call ahead.
4. The feed has no capacity or demand data.
5. Redistribution is unconfirmed. The page is a public directory, but we have not asked Second Harvest for permission to republish it. Confirm before the repo is shared widely, or before using it in a public demo.
6. The percentages use ACS 2024 5-year tract estimates, which carry margins of error. 2 of the 490 tracts have no poverty or SNAP percentage.
