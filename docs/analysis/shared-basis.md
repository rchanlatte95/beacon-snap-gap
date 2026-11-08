# Shared basis: where food need and small-business gaps meet

Findings F-4, F-5 and F-6 in `docs/data-sources.md`. Task N1 in `docs/mockups/planner-map/DESIGN-personas-summary.md`. Computed 2026-11-07. Every number in this note comes from the output of `python -I scripts/analysis/shared_basis.py`.

## Verdict

1. **The Appendix A small-business gap types do not give a shared basis beyond poverty.** The Entrepreneurship Infrastructure Gap is much more common in Classic Food Desert tracts (26.8% against 6.6%). All of that overlap comes from the poverty input that both rules use. Inside the top poverty quartile, desert tracts have this gap no more often than other tracts (26.8% against 32.0%, p = 0.62). The Capital Access Gap and the Underinvestment Gap show no difference.
2. **The Credit Access Gap is more common in desert tracts** (21.3% against 6.7%, p = 9.9e-05), because the mortgage denial rate goes up with poverty and SNAP share. Inside the top poverty quartile the difference is not significant (21.3% against 8.3%, p = 0.24, only 24 comparison tracts). With county quartile cuts, it gets smaller (13.8% against 8.5%, p = 0.12).
3. **Home mortgage applications are denied more often in desert tracts** (median denial rate 35.9% against 28.1%, p = 6.2e-11). This is a household credit fact, not a business credit fact.
4. **Desert tracts have more SNAP retailers per resident, not fewer** (median 0.74 against 0.46 per 1,000 residents, p = 9.7e-05). Most of these stores are convenience stores, pharmacies and dollar stores.

## Plain-language conclusion

The rules for "small business gaps" mostly point to the same poor neighborhoods that the food rule already finds. That is because both rules use the poverty rate, so it is not a new discovery. In high-need neighborhoods, banks turned down home loan applications more often in 2025: 35.9% against 28.1% in other neighborhoods. High-need neighborhoods also have more stores that take SNAP for each resident, and most of them are small-format stores like convenience stores and dollar stores. None of this shows that food need causes a need for business loans, or the other way around.

## The question

The team is building a "Common ground" summary that food banks, SBDCs, CDFIs and funders can share (decisions H-1 and H-9). Finding F-3 tested the claim that food need and SBA lending line up, and did not support it. The summary and the suggestion rules (S5, S6, S8, S9) still need tested facts about where food need and small-business gaps meet. This note tests four candidates:

1. The four Appendix A gap types, per tract.
2. How often each gap type falls in a Classic Food Desert tract, and how much of that overlap remains when poverty is held constant.
3. SNAP retailers (DS-H8) per resident, desert against nogap.
4. The mortgage denial rate (DS-H9) against poverty and SNAP share, desert against nogap.

## Method

- **Tracts.** The analysis set is the same as in F-3: 488 tracts, 97 desert and 391 nogap. The two class-insufficient tracts (`12095016515`, `12095990000`) are "insufficient data" for every gap type.
- **Food class.** From `docs/mockups/planner-map/data/records.standin.json` (the contracted rule: poverty at or above 17.025% AND the driving-distance LILA flag).
- **Denominator.** 2020 Census population per tract (`pop2020`, DS-X24), as in F-3.
- **One quartile method for every cut.** Python `statistics.quantiles(n=4, method='inclusive')`, over the 488 analysis tracts that have a value. This is the method of the class rule (`contracts/planner_map_contract.py`). The poverty Q3 from this script is 17.025%, the same as the class-rule cut.
- **Cut words.** "Top quartile" means at or above Q3. "Bottom quartile" means at or below Q1. "At or above the median" means at or above Q2.
- **Missing values.** A tract is "no" when any known condition fails. It is "insufficient data" when no known condition fails but at least one condition cannot be checked. It is "yes" when all conditions hold.
- **Tests.** Fisher exact test for each 2x2 table. Mann-Whitney U (two-sided) and Spearman rank correlation for continuous values, as in F-3. A Bonferroni threshold is given for each section.

### Inputs and the choices made

| Input | Source | How it is computed | Choice and reason |
|---|---|---|---|
| SBA loans per capita | DS-X5 | 7(a) plus 504 loans, all years, per 1,000 residents (`pop2020`) | Same measure as F-3. Appendix A says "SBA loan count per capita" and "SBA loan activity"; this note uses the same measure for both |
| Poverty rate | DS-H2, from the stand-in | Percent of people below poverty | Same as F-3 |
| SNAP share | DS-H1, from the stand-in | Percent of households receiving SNAP | Same as F-3 |
| Unemployment rate | DS-H5 (`B23025`), read from the zip in place | Unemployed (`B23025_005E`) / civilian labor force (`B23025_003E`) | The standard definition |
| "Sizable labor force/population base" | DS-H5 | Labor force 16+ (`B23025_002E`) at or above the median (2,776 persons) | The appendix names labor force first. The median keeps one quartile method. Sensitivity: 2020 population at or above 2,000 (the S5 stand-in), and no size condition |
| Employment rate | DS-H5 | Employment-population ratio: civilian employed (`B23025_004E`) / population 16+ (`B23025_001E`) | Employed / civilian labor force is only 1 minus the unemployment rate, so it adds nothing new. Sensitivity: that version |
| Median household income | `data/external/census-acs/acs2024_s1901_median_household_income_central_fl_tracts.csv` (DS-X28 file, S1901 values) | As published. One tract is "250,000+" and is kept at $250,000 | This file is already limited to the 490 tracts and marks the lower-bound and unavailable values. The script checks it against the hackathon `Household Income, Median.zip` (DS-H3): 486 of 486 published values are equal |
| Mortgage denial rate | DS-H9 `mortgage_denials_originations_by_tract.xlsx`, Data sheet, read in place | Denials / (denials + originations), as Appendix A says | Equal to the file's `denial_rate` (largest difference 5.6e-16). A tract with fewer than 20 applications is "insufficient data". Sensitivity: no floor, and the README's suggestion of a quartile within each county |
| SNAP retailers | DS-H8, Florida rows | Point in polygon (ray casting in the script; shapely is not installed) with `data/external/geography/central_fl_tracts_2020.geojson` | Count per tract, per 1,000 residents |

### Cuts (488 analysis tracts)

| Input | Tracts with a value | Q1 | Median | Q3 | Cut used |
|---|---|---|---|---|---|
| SBA loans per 1,000 residents | 488 | 0.945 | 1.795 | 3.347 | bottom quartile <= 0.945; at or above median >= 1.795 |
| Poverty rate (%) | 488 | 6.200 | 10.000 | 17.025 | top quartile >= 17.025 |
| Unemployment rate (%) | 488 | 2.448 | 4.359 | 6.904 | top quartile >= 6.904 |
| Labor force (persons) | 488 | 1,891.250 | 2,776.500 | 3,820.500 | sizable >= 2,776 |
| Median household income ($) | 487 | 59,891.500 | 77,050.000 | 100,003.000 | at or above median >= 77,050 |
| Employment-population ratio (%) | 488 | 57.129 | 62.941 | 68.064 | at or above median >= 62.941 |
| Mortgage denial rate (>= 20 applications) | 475 | 0.240 | 0.288 | 0.353 | top quartile >= 0.3535 |

Tract `12095018901` (desert) has no 2020 to 2024 median income. Tract `12095013503` (nogap) has no HMDA row. 12 analysis tracts have 1 to 19 applications. The median tract has 126 applications.

## Results

### 1. Appendix A gap types (488 tracts)

| Gap type | Rule as coded | Yes | No | Insufficient data |
|---|---|---|---|---|
| Capital Access Gap | loans per 1,000 <= 0.945 AND labor force >= 2,776 | 57 | 431 | 0 |
| Entrepreneurship Infrastructure Gap | (poverty >= 17.025% OR unemployment >= 6.904%) AND loans per 1,000 <= 0.945 | 52 | 436 | 0 |
| Credit Access Gap | denial rate >= 0.3535 (>= 20 applications) AND loans per 1,000 >= 1.795 | 46 | 437 | 5 |
| Underinvestment Gap | income >= $77,050 AND employment-population ratio >= 62.941% AND loans per 1,000 <= 0.945 | 30 | 458 | 0 |

Tracts by number of gap types: 0 types 352, 1 type 92, 2 types 39, 3 types 5, 4 types 0. 122 of 488 tracts (25.0%) are in the bottom quartile of SBA loans per 1,000.

### 2. Overlap with Classic Food Desert

The top poverty quartile (poverty >= 17.025%) has 122 tracts: 97 desert and 25 nogap. Every desert tract is in it, by the class rule. Inside it, "desert" means LILA flag 1 and "nogap" means LILA flag 0. So the second row of each pair asks: does the grocery-access flag add overlap, when poverty is already high? There are 8 Fisher tests. Bonferroni threshold: 0.0063.

| Gap type | Scope | Desert yes / known | Desert share | Nogap yes / known | Nogap share | Odds ratio | Fisher p |
|---|---|---|---|---|---|---|---|
| Capital Access Gap | All 488 tracts | 14 / 97 | 14.4% | 43 / 391 | 11.0% | 1.37 | 0.38 |
| Capital Access Gap | Top poverty quartile (122) | 14 / 97 | 14.4% | 1 / 25 | 4.0% | 4.05 | 0.3 |
| Entrepreneurship Infrastructure Gap | All 488 tracts | 26 / 97 | 26.8% | 26 / 391 | 6.6% | 5.14 | 2.0e-07 |
| Entrepreneurship Infrastructure Gap | Top poverty quartile (122) | 26 / 97 | 26.8% | 8 / 25 | 32.0% | 0.78 | 0.62 |
| Credit Access Gap | All 488 tracts | 20 / 94 | 21.3% | 26 / 389 | 6.7% | 3.77 | 9.9e-05 |
| Credit Access Gap | Top poverty quartile (122) | 20 / 94 | 21.3% | 2 / 24 | 8.3% | 2.97 | 0.24 |
| Underinvestment Gap | All 488 tracts | 3 / 97 | 3.1% | 27 / 391 | 6.9% | 0.43 | 0.24 |
| Underinvestment Gap | Top poverty quartile (122) | 3 / 97 | 3.1% | 0 / 25 | 0.0% | inf | 1 |

**How much of the Entrepreneurship Infrastructure Gap overlap is built in.** Every desert tract meets the poverty part of this gap. So in desert tracts, the gap is "yes" exactly when SBA loans per 1,000 are in the bottom quartile (the script checks this). That is 26 of 97 desert tracts (26.8%), close to the 25.0% of all tracts. In nogap tracts, only 91 of 391 meet the poverty-or-unemployment part (25 by poverty, 66 by unemployment only). The difference between 26.8% and 6.6% is therefore the shared poverty input, not a link between food need and lending. Inside the top poverty quartile, no overlap remains (26.8% against 32.0%, p = 0.62). Of the 52 tracts with this gap, 26 (50.0%) are desert tracts.

**Credit Access Gap.** This rule does not use poverty. The overlap comes from the mortgage denial rate, which goes up with poverty (section 4). Inside the top poverty quartile, 20 of 94 desert tracts and 2 of 24 nogap tracts have the gap (p = 0.24). The comparison group is small, so this test cannot rule a difference in or out.

### 2b. Sensitivity to threshold choices

| Variant | Yes | Insufficient data | Desert yes / known (share) | Nogap yes / known (share) | Fisher p (all 488) |
|---|---|---|---|---|---|
| Capital Access Gap, sizable = 2020 population >= 2,000 | 117 | 0 | 26 / 97 (26.8%) | 91 / 391 (23.3%) | 0.51 |
| Capital Access Gap, no size condition | 122 | 0 | 26 / 97 (26.8%) | 96 / 391 (24.6%) | 0.69 |
| Entrepreneurship Infrastructure Gap, poverty only (no unemployment) | 34 | 0 | 26 / 97 (26.8%) | 8 / 391 (2.0%) | 1.4e-13 |
| Credit Access Gap, no application floor | 46 | 0 | 20 / 97 (20.6%) | 26 / 391 (6.6%) | 0.00012 |
| Credit Access Gap, denial-rate Q3 within each county | 46 | 5 | 13 / 94 (13.8%) | 33 / 389 (8.5%) | 0.12 |
| Underinvestment Gap, employment = employed / civilian labor force | 34 | 0 | 2 / 97 (2.1%) | 32 / 391 (8.2%) | 0.042 |

County denial-rate Q3: Orange 0.3712, Seminole 0.3014, Lake 0.2955, Osceola 0.3841. Orange and Osceola, where most desert tracts are (F-3, section 5), have higher county cuts. So the county version flags fewer desert tracts. The Capital Access Gap gives the same answer under every size rule. The Underinvestment Gap result is not stable: the p-value changes from 0.24 to 0.042 with the employment definition.

### 3. SNAP retailers (DS-H8)

**What the file holds.** 248,872 rows. Columns: `X`, `Y`, `Record_ID`, `Store_Name`, `Store_Street_Address`, `Additonal_Address`, `City`, `State`, `Zip_Code`, `Zip4`, `County`, `Store_Type`, `Latitude`, `Longitude`, `Incentive_Program`, `Grantee_Name`, `ObjectId`. **No column holds a date**, so the date of the list is not known. Florida has 14,033 rows, all with coordinates.

**Join.** 1,693 Florida retailers fall inside one of the 489 tract polygons. 1,685 of these have one of the four county names in `County`. 8 have another county name (Polk 5, Sumter 2, Pasco 1). 10 rows with one of the four county names fall inside no polygon. 11 points fall inside two polygons, because the polygons are simplified to about 10 m (`docs/hackathon/external-data-retrieved.md`); the script keeps the first match. 1,691 retailers are in the analysis set, and 2 are in the class-insufficient tracts.

**Store types inside the four counties.** Convenience Store 760, Other 435, Supermarket 226, Super Store 136, Grocery Store 106, Specialty Store 22, Farmers and Markets 8. 410 of the 435 "Other" stores have a name that starts with Walgreens, CVS, Dollar Tree, Dollar General or Family Dollar. Nationally the file also has a "Restaurant Meals Program" type, with no rows here. `Incentive_Program` and `Grantee_Name` are empty for these stores.

There are 4 tests in the table. Bonferroni threshold: 0.0125.

| Measure | Desert median [IQR] | Nogap median [IQR] | Mann-Whitney p | P(desert > nogap) |
|---|---|---|---|---|
| All SNAP retailers per 1,000 residents | 0.74 [0.41 to 1.21] | 0.46 [0.21 to 0.88] | 9.7e-05 | 0.628 |
| Supermarkets and super stores per 1,000 | 0.16 [0.00 to 0.29] | 0.00 [0.00 to 0.20] | 0.0011 | 0.599 |
| All other store types per 1,000 | 0.58 [0.27 to 0.91] | 0.38 [0.15 to 0.69] | 0.00032 | 0.618 |
| Tracts with zero SNAP retailers | 8 of 97 (8.2%) | 68 of 391 (17.4%) | Fisher p 0.028 | odds ratio 0.43 |

- Pooled: desert tracts have 474 retailers for 553,282 residents (0.86 per 1,000). Nogap tracts have 1,217 for 2,111,848 (0.58 per 1,000).
- Tracts with no supermarket or super store: desert 36 (37.1%), nogap 211 (54.0%).
- Retailers per 1,000 go up with SNAP share (Spearman rho 0.343, p = 6.0e-15) and with poverty (rho 0.293, p = 4.0e-11).
- All 97 desert tracts are urban (USDA flag), and 340 of 391 nogap tracts are urban. Among urban tracts only, the result is the same: median 0.74 against 0.46 retailers per 1,000 (p = 0.00012).

A food desert flag (LILA) and a high count of SNAP stores can both be true. LILA measures distance from people's homes to a supermarket in USDA's own store list. This file counts every store type that takes SNAP, inside the tract lines.

### 4. Mortgage denial rate (DS-H9)

475 tracts have 20 or more applications (desert 90, nogap 385). Over these tracts, the median denial rate is 0.2878. The pooled rate is 0.2850 (23,051 denials of 80,871 applications). There are 6 tests in this section. Bonferroni threshold: 0.0083.

| Compared with | n | Spearman rho | p | Pearson r (side note) | p |
|---|---|---|---|---|---|
| Poverty rate | 475 | 0.345 | 9.3e-15 | 0.322 | 6.7e-13 |
| SNAP share | 475 | 0.434 | 3.0e-23 | 0.410 | 1.1e-20 |
| SBA loans per 1,000 | 475 | -0.082 | 0.074 | -0.022 | 0.63 |
| Median household income | 474 | -0.388 | 1.9e-18 | -0.357 | 1.0e-15 |

- Desert against nogap: median 0.3589 [0.2971 to 0.4152] against 0.2807 [0.2360 to 0.3333] (35.9% against 28.1%). Mann-Whitney p = 6.2e-11. P(desert > nogap) = 0.721.
- Inside the top poverty quartile: desert median 0.3589 (n = 90) against nogap 0.2933 (n = 21, 29.3%). Mann-Whitney p = 0.026. This does not pass the Bonferroni threshold, and the nogap group is small.
- Without the application floor (487 tracts), Spearman with poverty is 0.351 (p = 1.4e-15).
- 119 tracts are in the top denial-rate quartile: 49 of 90 desert tracts (54.4%) and 70 of 385 nogap tracts (18.2%). 46 of them also have SBA loans per 1,000 at or above the median, which makes them Credit Access Gap tracts.
- The denial rate has no clear link with SBA loans per 1,000 (rho -0.082, p = 0.074).

## What the Common ground summary may say

Each sentence below is supported by the results. Keep the caveat in brackets on the detail level.

1. "The food-need rule and the small-business gap rules both use the poverty rate. So they often point to the same places. This is by design, not a new finding." (Section 2.)
2. "High-need neighborhoods are in the lowest quarter for SBA loans per resident about as often as other neighborhoods: 26 of 97, against 122 of 488 overall." (Section 2; F-3 limits apply.)
3. "In 2025, home loan applications were turned down more often in high-need neighborhoods than in other neighborhoods (middle value 35.9% against 28.1%)." [Home mortgages only, not business loans. HMDA 2025. Tracts with fewer than 20 applications left out.]
4. "High-need neighborhoods have more stores per resident that take SNAP than other neighborhoods. Most of these stores are convenience stores, pharmacies and dollar stores." [Date of the store list is not known. Counts stores inside tract lines, not stores people use.]
5. Detail level only (decision H-3): "These 26 high-need neighborhoods are also in the lowest quarter for SBA loans per resident. This is a place to talk about, not a pattern." These are the 26 desert tracts with the Entrepreneurship Infrastructure Gap (`docs/analysis/tract_gap_types.csv`). They are a subset of the F-3 list of 50. Always show the S7 guard sentence with them.

## What the Common ground summary must not say

| Must not say | Why |
|---|---|
| That food deserts and small-business gaps "overlap", "match" or "confirm each other" as a finding | The Entrepreneurship Infrastructure Gap overlap is built in by the shared poverty input. Inside the top poverty quartile, it is 26.8% against 32.0% (p = 0.62) |
| That high-need neighborhoods have more small-business gaps in general | Capital Access Gap: 14.4% against 11.0% (p = 0.38). Underinvestment Gap: 3.1% against 6.9% (p = 0.24) |
| That businesses in high-need neighborhoods are denied credit, or that lenders deny business loans there | HMDA covers home mortgage applications only. It has no business credit |
| That mortgage denials show unfair treatment, or that high need causes denials | The file has no applicant credit data or denial reasons. This is a tract-level association |
| That high-need neighborhoods lack stores that take SNAP | The opposite: 0.74 against 0.46 retailers per 1,000 (p = 9.7e-05) |
| That these SNAP stores are small or local businesses | The file has no size or ownership field. 410 of 435 "Other" stores have national chain names |
| That SNAP cuts will close stores or cost stores a stated amount | No sales or redemption data is in the repo. No county or tract SNAP-cut series (DS-X1, DS-X2) |
| A Credit Access Gap count as stable | It changes with the cut: 20 of 94 desert tracts with one Central Florida cut, 13 of 94 with county cuts |
| An Underinvestment Gap result for desert tracts | It is unstable (p 0.24 or 0.042 by employment definition), and it is a "Review required" type in Appendix A |

## Limits

1. **Shared poverty input.** The desert rule and the Entrepreneurship Infrastructure Gap both use top-quartile poverty. The all-tract comparison for that gap measures this shared input. Use only the within-quartile comparison to judge overlap.
2. **Small comparison groups.** The top poverty quartile has only 25 nogap tracts (24 with a Credit Access value, 21 with a denial rate). The within-quartile tests have low power. A p-value above 0.05 there does not prove that no difference exists.
3. **ACS margins of error.** For unemployed persons, the median margin of error is 0.81 times the estimate, and 96.7% of tracts with a nonzero estimate have a margin of error at or above half the estimate. 9 tracts have an estimate of 0. For labor force, the median ratio is 0.185. For median household income, it is 0.212. Poverty and SNAP share also have margins of error (F-3 limit 6). Tracts near a cut can change class with a small change in the estimate.
4. **SBA loans.** Loans are placed by the borrower's mailing address. 89.9% of loans were placed, and the undercount is higher in Lake, Seminole and Osceola. 7(a) and 504 only. Loans show supply, not need (F-3 limits 1, 2, 4, 5).
5. **HMDA scope.** The file is the 2025 activity year of the FFIEC HMDA Modified LAR, as aggregated by the file's author (not named). It counts originated (action_taken 1) and denied (action_taken 3) applications only. It covers home mortgage lending by HMDA reporters, not all lenders. HMDA reports the tract of the property, not of the applicant's home (FFIEC reporting rule; the README sheet does not say this, and this note did not check it). 538 applications in the target counties had no tract, were left out, and had about an 80% denial rate (README sheet). The file has no denial reasons, credit scores or income. 45 tracts with a denial rate have only 20 to 49 applications.
6. **SNAP retailer list.** No date column, so the date of the list is not known. The file was downloaded 2026-11-07. It lists stores that are authorized to take SNAP. It does not show sales, SNAP redemptions, store size, ownership or hours. Store type is USDA's label. Residents are not shoppers: a store on a busy road serves people from many tracts. Tract polygons are simplified to about 10 m (11 points in two polygons; 10 points with a four-county name in no polygon).
7. **The thresholds are choices.** The labor-force median for "sizable", the 20-application floor, the employment definition and the four-county quartiles all need human approval (H-5). Section 2b shows how the counts change.
8. **Tract-level only.** These are ecological tests. Nearby tracts are not independent, so p-values are optimistic. Nothing here describes a household or a business.
9. **Population vintage.** The 2020 Census count is the denominator for loans from FY2010 to FY2026 and for a store list of unknown date.

## Files

- Script: `scripts/analysis/shared_basis.py`. It reads repo files only (the zips and the xlsx in place). It writes only `docs/analysis/tract_gap_types.csv`.
- Tract table: `docs/analysis/tract_gap_types.csv` (490 rows). Columns: GEOID, county, food class, the four gap types (yes / no / insufficient data), and the inputs: 2020 population, SBA loans and loans per 1,000, poverty rate, SNAP share, LILA driving flag, labor force, civilian labor force, unemployment rate, employment-population ratio, median household income and its status, mortgage originations, denials, applications and denial rate, SNAP retailers, supermarkets and super stores, and retailers per 1,000.
- Sources: DS-X5 (SBA), DS-H1 (SNAP), DS-H2 (poverty), DS-H5 (labor force), DS-H3 and DS-X28 (median income), DS-H6 (LILA flag), DS-H8 (SNAP retailers), DS-H9 (HMDA), DS-X24 (2020 blocks), tract polygons from the FEMA layer (`docs/hackathon/external-data-retrieved.md`), DS-B2 (Appendix A and B).
