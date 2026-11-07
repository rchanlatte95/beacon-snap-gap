# SBA 7(a) and 504 loans by census tract: Central Florida

`sba_loans_by_tract_central_fl.csv` has one row for each of the 490 Beacon Central Florida tracts (Orange 12095, Seminole 12117, Lake 12069, Osceola 12097). It holds loan counts and gross approval dollars by program and period. It has **no borrower names and no street addresses** (manifest REQ-4).

Source: SBA 7(a) and 504 FOIA loan data, as of 2026-09-30, https://data.sba.gov/dataset/7a-504-foia (U.S. Government Works). Source ID DS-X5. The three raw files (about 504 MB) are not in the repo; `data/references/sba-foia.json` records their URLs, sizes and SHA-256 hashes.

## Columns
| Column | Meaning |
|---|---|
| `geoid` | 11-digit 2020 census tract ID. Joins to the hackathon tract tables |
| `loans_<program>_<period>` | Count of approved loans. Program: `7a` or `504`. Period: `fy2010_2019` or `fy2020_2026` (SBA fiscal year of approval) |
| `gross_usd_<program>_<period>` | Sum of `GrossApproval` in US dollars |
| `loans_total`, `gross_usd_total` | Sums over the four program and period columns |
| `jobs_supported_total` | Sum of SBA's `JobsSupported` field |

## How it was built
1. Kept loans whose `ProjectState` is FL and `ProjectCounty` is Orange, Seminole, Lake or Osceola: 7,817 loans (7(a) FY2020 on 3,652; 7(a) FY2010 to 2019 2,987; 504 FY2010 on 1,178).
2. Sent each borrower street address, city, state and ZIP to the Census Bureau batch geocoder (benchmark `Public_AR_Current`, vintage `Census2020_Current`, approved by the human on 2026-11-07). The address file and geocoder output stayed outside the repo.
3. Summed matched loans by 2020 tract.

## Limits
1. **Not every loan was placed.** 7,024 of 7,817 (89.9%) matched. 750 found no match and 43 tied. Of the matched loans, 30 fell outside the 490 tracts and were dropped, leaving **6,994 loans and about $3.92 billion**. Unmatched share by project county: Lake 14.2%, Seminole 13.2%, Osceola 12.4%, Orange 7.9%. Tract counts are therefore **undercounts**, and more so in the three smaller counties. Do not read a low count as low lending without checking.
2. **The address is the borrower's mailing address,** not necessarily the project or business location. A loan can sit in a different tract from the business it funds.
3. **Possible double-listing.** 78 groups (161 rows) share the same lender location ID, fiscal year, amount, NAICS code and address. They may be separate loans or repeated rows. Nothing was removed. The maximum effect is 83 loans (about 1%).
4. **Counts are not rates.** There is no population or business denominator in this file. Join to the hackathon population and labor-force tables before comparing tracts.
5. **7(a) and 504 are only part of small-business credit.** Banks' own loans, microloans and CDFI lending do not appear.
6. The fiscal year 2026 column is partial (as of 2026-09-30).
