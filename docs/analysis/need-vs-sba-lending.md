# Food need against SBA lending, by census tract

Finding F-3 in `docs/data-sources.md`. Computed 2026-11-07. Every number in this note comes from the output of `python scripts/analysis/need_vs_sba_lending.py`.

## Verdict

**Not supported.** At tract level, SBA 7(a) and 504 lending per resident does not go up or down with food need. High-need tracts get about the same lending per resident as other tracts. The data also cannot measure who *needs* a loan. It shows only where approved loans went.

## Plain-language conclusion

Places where many people need food do not get more SBA loans, and they do not get fewer. Loans per person are about the same in high-need and lower-need neighborhoods. This data does not show that food need and the need for business loans go together.

## The question

A dashboard user said: "The population that needs food aligns with people that need lending from SBA." The user asked to contrast need against where loans are given out. This decides whether the team builds a "shared story" view that puts food need and capital need together.

We test one thing that the data can test: do tracts with more food need get more, or less, SBA lending per resident than other tracts?

## Method

- **Tracts.** The 490 Central Florida tracts. The analysis set is 488 tracts: the 97 "desert" (high need) tracts and the 391 "nogap" tracts. Two "insufficient" tracts are excluded: `12095016515` (no households) and `12095990000` (water, no population). The analysis set holds 6,987 of the 6,994 placed loans ($3.91 billion of $3.92 billion).
- **Food need.** Class (desert or nogap) by the contracted rule in `contracts/planner_map_contract.py` (poverty rate at or above 17.025% AND the driving-distance LILA flag). SNAP share (DS-H1) and poverty rate (DS-H2), from `docs/mockups/planner-map/data/records.standin.json`. No-vehicle share (DS-X7b), a proxy for transport need (finding F-1).
- **Lending.** SBA 7(a) plus 504 loans by borrower address (DS-X5, `data/external/sba-loans/`). Loan count and gross approval dollars, for all years, FY2010 to 2019, and FY2020 to 2026.
- **Denominator.** 2020 Census population per tract (sum of 2020 blocks, DS-X24), from the stand-in. ACS 2024 total population (DS-H4) is a check.
- **Tests.** Spearman rank correlation, because loan counts are skewed. Pearson is a side note only. Mann-Whitney U (two-sided) for desert against nogap. Fisher exact test for the 2x2 table. There are 18 correlation tests in the main table, so the Bonferroni threshold is p < 0.0028.
- **Effect size.** P(desert > nogap) is the chance that a random desert tract has more lending than a random nogap tract. 0.5 means no difference.

## Results

### 1. Correlation between lending per 1,000 residents and need (488 tracts)

| Lending measure | vs SNAP share: rho (p) | vs poverty rate: rho (p) | vs no-vehicle share: rho (p) |
|---|---|---|---|
| Loans per 1,000, all years | -0.051 (0.26) | -0.021 (0.65) | 0.136 (0.0026) |
| Loans per 1,000, FY2010 to 2019 | -0.059 (0.19) | 0.001 (0.99) | 0.146 (0.0012) |
| Loans per 1,000, FY2020 to 2026 | -0.035 (0.44) | -0.029 (0.52) | 0.106 (0.019) |
| Gross $ per 1,000, all years | -0.030 (0.51) | 0.036 (0.43) | 0.181 (5.9e-05) |
| Gross $ per 1,000, FY2010 to 2019 | -0.043 (0.35) | 0.036 (0.43) | 0.180 (6.2e-05) |
| Gross $ per 1,000, FY2020 to 2026 | -0.005 (0.91) | 0.035 (0.44) | 0.158 (0.00046) |

All 12 correlations with SNAP share and poverty rate are between -0.059 and 0.036. None is significant. The five correlations below the Bonferroni threshold are all with no-vehicle share, and all are weak (0.136 to 0.181). Pearson side note: Pearson r with no-vehicle share is 0.210 to 0.252. With SNAP share and poverty rate, Pearson r is 0.000 to 0.095.

### 2. Desert (97 tracts) against nogap (391 tracts)

| Lending measure | Desert median [IQR] | Nogap median [IQR] | Zero-loan share, desert / nogap | Mann-Whitney p | P(desert > nogap) |
|---|---|---|---|---|---|
| Loans per 1,000, all years | 1.7 [0.8 to 3.5] | 1.8 [1.0 to 3.3] | 3.1% / 2.6% | 0.82 | 0.492 |
| Loans per 1,000, FY2010 to 2019 | 0.6 [0.3 to 1.8] | 0.8 [0.4 to 1.5] | 10.3% / 11.3% | 0.75 | 0.490 |
| Loans per 1,000, FY2020 to 2026 | 1.0 [0.5 to 1.9] | 1.0 [0.5 to 1.7] | 6.2% / 8.2% | 0.9 | 0.504 |
| Gross $ per 1,000, all years | $907,098 [$263,923 to $2,463,799] | $780,886 [$262,613 to $1,982,286] | 3.1% / 2.6% | 0.48 | 0.523 |
| Gross $ per 1,000, FY2010 to 2019 | $291,068 [$60,810 to $914,974] | $253,435 [$38,727 to $807,258] | 10.3% / 11.3% | 0.56 | 0.519 |
| Gross $ per 1,000, FY2020 to 2026 | $479,224 [$153,549 to $1,514,239] | $423,545 [$106,677 to $1,208,790] | 6.2% / 8.2% | 0.34 | 0.531 |

The two groups are almost the same on every measure. Only 13 of 488 tracts have zero placed loans.

### 3. 2x2 count

High need is class desert. Low need is class nogap. The lending cut is the **median loans per 1,000 residents, all years, over the 488 tracts: 1.80**. Low lending is below the median. High lending is at or above the median.

| | Low lending | High lending | Total |
|---|---|---|---|
| High need | 50 | 47 | 97 |
| Low need | 194 | 197 | 391 |

- **50 tracts are "high need, low lending"** (51.5% of desert tracts). By county: Orange 37, Osceola 10, Seminole 3. The list is in `docs/analysis/high_need_low_lending_tracts.csv`.
- For comparison, 49.6% of nogap tracts are also low lending. Fisher exact test: odds ratio 1.08, p = 0.82. A desert tract is no more likely than a nogap tract to be low lending.

### 4. Denominator check

Top 10 tracts by loans per 1,000 residents (all years):

| GEOID | County | Class | 2020 pop | ACS 2024 pop | Loans | Loans per 1,000 |
|---|---|---|---|---|---|---|
| 12095018400 | Orange | nogap | 2,381 | 2,401 | 71 | 29.82 |
| 12095017001 | Orange | nogap | 4,966 | 5,947 | 133 | 26.78 |
| 12095016406 | Orange | desert | 2,045 | 1,690 | 50 | 24.45 |
| 12095018300 | Orange | desert | 3,149 | 2,478 | 70 | 22.23 |
| 12095015901 | Orange | nogap | 2,428 | 2,460 | 52 | 21.42 |
| 12095018902 | Orange | nogap | 4,922 | 5,720 | 104 | 21.13 |
| 12117021504 | Seminole | nogap | 3,150 | 3,380 | 62 | 19.68 |
| 12095019000 | Orange | nogap | 3,621 | 4,445 | 64 | 17.67 |
| 12095016803 | Orange | nogap | 2,860 | 2,137 | 49 | 17.13 |
| 12117020101 | Seminole | nogap | 1,291 | 1,283 | 21 | 16.27 |

The top 10 have a median of 3,004 residents (all tracts: 5,094). They hold 676 loans (9.7%). Eight are nogap and two are desert. No analysis tract has fewer than 1,000 residents, so there are no near-empty commercial tracts that inflate the rate. We used a population floor of 2,000 (22 tracts are below it) to test this.

| Variant | n | Loans per 1,000 vs SNAP / poverty / no-vehicle: rho (p) | Desert vs nogap: MWU p, P(desert > nogap) |
|---|---|---|---|
| All tracts, 2020 pop | 488 | -0.051 (0.26) / -0.021 (0.65) / 0.136 (0.0026) | 0.82, 0.492 |
| Exclude the top 10 | 478 | -0.056 (0.22) / -0.028 (0.55) / 0.103 (0.025) | 0.81, 0.492 |
| 2020 pop at or above 2,000 | 466 | -0.038 (0.42) / -0.013 (0.78) / 0.136 (0.0032) | 0.72, 0.488 |
| ACS 2024 pop as denominator | 488 | -0.055 (0.22) / -0.003 (0.94) / 0.160 (0.00038) | 0.97, 0.501 |
| Raw loan count per tract (no denominator) | 488 | -0.059 (0.2) / -0.019 (0.67) / 0.103 (0.023) | 0.66, 0.515 |

**The denominator does not distort the result.** Every variant gives the same answer: no link with SNAP share or poverty rate, no desert against nogap difference, and a weak positive link with no-vehicle share. The script also prints the dollar version of this table, with the same pattern.

### 5. Within each county (loans per 1,000, all years)

| County | n | Desert tracts | vs SNAP share | vs poverty rate | vs no-vehicle share |
|---|---|---|---|---|---|
| Orange | 265 | 72 | -0.119 (0.054) | -0.030 (0.63) | 0.093 (0.13) |
| Seminole | 89 | 5 | 0.136 (0.2) | -0.097 (0.36) | 0.242 (0.022) |
| Lake | 75 | 2 | 0.187 (0.11) | -0.007 (0.95) | 0.282 (0.014) |
| Osceola | 59 | 18 | -0.340 (0.0084) | 0.006 (0.96) | -0.017 (0.9) |

The county pattern is not the same in each county. In Osceola, tracts with a higher SNAP share get fewer loans per resident (rho -0.340, p = 0.0084). This is one result from 12 tests on 59 tracts. It does not pass a Bonferroni threshold for 12 tests (0.0042). It is a lead to examine, not a finding.

### 6. The no-vehicle signal

The only clear signal is a weak positive link with no-vehicle share. It stays in urban tracts (437 tracts, rho 0.139, p = 0.0035) and is absent in rural tracts (51 tracts, rho -0.024, p = 0.87). One possible reason is that car-free households and business mailing addresses both cluster in urban cores. This is not tested. The no-vehicle estimate is also very noisy (see Limits). Do not use it as evidence that lending follows food need.

## What this means for the "shared story" view

The data does not support a view that says food need and SBA lending line up. It also does not show that high-need tracts are left out of SBA lending: they get about the same lending per resident as other tracts. If the team builds a view on food need and capital, it must not claim alignment or a lending gap. It can show the 50 high-need, low-lending tracts as a list to examine, with the limits below.

## Limits

1. **Borrower address is not where residents live, and not always where the business is.** Loans are placed by the borrower's mailing address (DS-X5 README, limit 2). A tract's loans are not loans to its residents.
2. **Loans are a supply measure, not a measure of need for capital.** An approved loan shows that a lender and a borrower closed a deal. It does not show unmet demand, denied applications or businesses that did not apply. The claim is about *need* for SBA lending. No file in the repo measures that, so this part of the claim cannot be tested.
3. **No business counts by tract.** The repo has no count of businesses or employers by tract. Lending per resident is not lending per business. A tract with many businesses and few residents looks "high lending" for that reason only.
4. **Undercounts that differ by county.** The DS-X5 README states that 89.9% of loans matched to an address (limit 1). The unmatched share is higher in Lake (14.2%), Seminole (13.2%) and Osceola (12.4%) than in Orange (7.9%). Low counts can be partly a geocoding effect.
5. **7(a) and 504 are only part of small-business credit.** Bank loans, microloans and CDFI lending are not in the data.
6. **ACS margins of error.** SNAP share, poverty rate and no-vehicle share are ACS 5-year estimates with margins of error. For no-vehicle households, the median margin of error is 0.93 times the estimate, and 95.5% of tracts with a nonzero estimate have a margin of error at or above half the estimate. ACS 2024 total population has a median margin of error of 0.149 times the estimate. No-vehicle share is also only a proxy for transport need (F-1).
7. **Small samples.** 27 of 97 desert tracts have 5 or fewer placed loans from FY2010 to FY2026. A difference of one or two loans changes their rate a lot. Osceola has 59 tracts and Lake has only 2 desert tracts.
8. **Population vintage.** The 2020 Census count is used for loans made from FY2010 to FY2026. The ACS 2024 check gives the same result (Spearman between the two populations: 0.951).
9. **Tract-level only.** This is an ecological test. It says nothing about individual households or businesses. Nearby tracts are also not independent, so the p-values are optimistic. That makes the "no link" result stronger, not weaker.
10. **Possible double-listing** in the SBA file: at most 83 loans (about 1%), not removed (DS-X5 README, limit 3).
11. **Fiscal year 2026 is partial** (data as of 2026-09-30).

## Files

- Script: `scripts/analysis/need_vs_sba_lending.py`. It reads repo files only. It writes only `docs/analysis/high_need_low_lending_tracts.csv`.
- Tract list: `docs/analysis/high_need_low_lending_tracts.csv` (50 rows). Columns: GEOID, county, class, SNAP share, poverty rate, loans per 1,000 residents, placed loans, 2020 population.
- Sources: DS-X5 (SBA), DS-H1 (SNAP), DS-H2 (poverty), DS-H4 (ACS population), DS-H6 (LILA flag), DS-X7b (no vehicle), DS-X24 (2020 blocks).
