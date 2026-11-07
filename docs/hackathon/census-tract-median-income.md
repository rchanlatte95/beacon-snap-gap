# Median household income for the planner map

Checked 2026-11-07 against `docs/mockups/planner-map/data/records.standin.json`.

## Result

Census median household income is available for almost all mapped tracts. The repo already contains the source: `data/hackathon/beacon-example-datasets/Household Income, Median.zip` (DS-H3). It contains ACS five-year table S1901 for 2020-2024, in 2024 dollars. All 490 frontend GEOIDs match the archive.

The household median is `S1901_C01_012E`. Its 90% margin of error is `S1901_C01_012M`. [Official Census variable definitions](https://api.census.gov/data/2024/acs/acs5/subject/groups/S1901.html).

| County | Frontend tracts | Numeric median and margin of error | Published lower bound | Unavailable |
|---|---:|---:|---:|---:|
| Lake | 75 | 75 | 0 | 0 |
| Orange | 267 | 264 | 0 | 3 |
| Osceola | 59 | 59 | 0 | 0 |
| Seminole | 89 | 88 | 1 | 0 |
| Total | 490 | 486 | 1 | 3 |

Of the 97 high need tracts in the mock-up, 96 have a numeric 2020-2024 median. The remaining tract has a prior-period estimate, listed below. There are 489 drawn tracts; the water tract is the one record without a shape.

## Gaps and the closest alternatives

| GEOID | Tract | 2020-2024 result | Alternative or treatment |
|---|---|---|---|
| `12095018901` | Orange 189.01, high need | Median unavailable; 1,938 households | Same GEOID in the 2019-2023 ACS: **$39,873, with a 90% margin of error of $17,904**, in 2023 dollars. Keep the period and uncertainty visible. |
| `12095016515` | Orange 165.15 | Median unavailable; zero households | Keep unavailable. A household median has no useful interpretation when the household count is zero. |
| `12095990000` | Orange 9900, water | Median unavailable; zero households | Keep unavailable. This tract is not drawn. |
| `12117020703` | Seminole 207.03 | **$250,000+** | Preserve the lower bound. Do not turn the Census bulk value `250001` into an exact dollar estimate. No numeric margin of error is published. |

The [2023 Census B19013 bulk file](https://www2.census.gov/programs-surveys/acs/summary_file/2023/table-based-SF/data/5YRData/acsdt5y2023-b19013.dat) supplies the historical alternative for tract 189.01. Its large margin of error limits precision. It overlaps the 2020-2024 period and uses a different dollar year; it does not establish a change in income.

For context from the same period as the main data, Orange County's median is **$79,719, with a 90% margin of error of $1,200**, in 2024 dollars. This is a county statistic; it must not fill the tract median field. The estimate is in the [2024 Census B19013 bulk file](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b19013.dat) and agrees with [Census QuickFacts](https://www.census.gov/quickfacts/fact/table/orangecountyflorida/INC110224).

## Use in the frontend

Use median **household** income as a context indicator, with its period, dollar year and margin of error. Keep missing values separate from zero and preserve the `$250,000+` bound. Fourteen of the 486 numeric medians have margins of error greater than half their estimates. A numeric value alone does not establish precision.

The mock-up generator currently reads USDA SRAM `MedianFamilyIncome` into `medianFamilyIncome`. The tract card does not display that field. Family income and household income cover different populations and must have separate labels. This data addition does not change the frontend or its classification rule.

The ACS 2020-2024 five-year release covers census tracts and was released January 29, 2026. It is a five-year estimate, not a measure of income in November 2026. [Census release details](https://www.census.gov/programs-surveys/acs/news/data-releases/2024/release.html). As checked on 2026-11-07, the 2025 ACS schedule still lists the five-year release as TBD; the published one-year product does not supply tract estimates. [Census release schedule](https://www.census.gov/programs-surveys/acs/news/data-releases/2025/release-schedule.html).

## Saved data and verification

- [490 tract rows](../../data/external/census-acs/acs2024_s1901_median_household_income_central_fl_tracts.csv): primary estimates, margins of error, raw Census symbols, a separate lower-bound field, and separate historical alternative fields. GEOIDs are strings.
- [Four county rows](../../data/external/census-acs/acs2024_b19013_median_household_income_central_fl_counties.csv): county context from the 2020-2024 ACS.
- [Extraction script](../../data/external/census-acs/extract_median_income.py): downloads official bulk files to ignored `data/cache/census-income/`, checks their SHA-256 hashes, and compares S1901 against B19013. It needs Python's standard library and no API key.

Run from the repo root:

```powershell
python data/external/census-acs/extract_median_income.py
```

Result: exit 0. All 490 GEOIDs match. All 486 numeric estimate and margin-of-error pairs agree between the supplied S1901 archive and the Census B19013 bulk file. The lower bound and three unavailable records also agree. The script writes 490 tract rows and four county rows.

Bulk file SHA-256:

| File | SHA-256 |
|---|---|
| `acsdt5y2024-b19013.dat` | `b25a176b0e6c339b6f3a2a0d3d8446bf06f5f080b4395993ec9a8313efb1c229` |
| `acsdt5y2023-b19013.dat` | `c9007017b7bb29ba758c77612ec9a4a0b897a4ed931d527754629866f580a110` |

The Census API redirected a request without a key to its Missing Key page. Census Reporter's API returned HTTP 403. Official bulk downloads succeeded and supply the verification and alternative data above.
