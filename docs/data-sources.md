# Data sources appendix

Citation register for every data source, reference and fact used or considered. Captured 2026-11-07.

Status legend: **In repo** = downloaded and committed. **Linked** = URL verified reachable by an automated fetch. **Search-listed** = surfaced by web search; the site refused an automated fetch (HTTP 403), so the URL has not been opened by us. **Not downloaded** = a candidate source, not yet in the repo.

## 1. Hackathon-supplied data (In repo)

Location: `data/hackathon/beacon-example-datasets/`. Checksums: `docs/hackathon/data-manifest.md`.
Origin: DataKind Beacon example public datasets, shared via the challenge brief: https://drive.google.com/drive/folders/1zuwSZjkK3gcvEzNFPJ8THFRw9ulCgA-p

| ID | File | Publisher / vintage | Contents (as inspected) |
|---|---|---|---|
| DS-H1 | Households and Households Receiving SNAP Census, S2201.zip | US Census Bureau, ACS 5-year 2024, table S2201 | SNAP households by tract. 3,085 tracts: Central FL 490, NYC 2,327, Salt Lake 268 |
| DS-H2 | Population - Below Poverty Level.zip | Census ACS 5-year 2024, S1701 | Poverty status by tract |
| DS-H3 | Household Income, Median.zip | Census ACS 5-year 2024, S1901 | Median household income by tract |
| DS-H4 | Total Population.zip | Census ACS 5-year 2024, S0101 | Age and sex population by tract |
| DS-H5 | Employed and Unemployed, 16+ Labor Force.zip | Census ACS 5-year 2024, B23025 | Labor force status by tract |
| DS-H6 | Low Grocery Access - 1/2 or 10 miles_2025-sram-fara-data.zip | USDA ERS, 2025 SRAM/FARA data | Driving-distance, straight-line and general tract characteristic files, with variable lookups. Includes LILA flags, poverty rate, SNAP and population counts |
| DS-H7 | Transportation_PLACES__Census_Tract_Data (GIS Friendly Format), 2025 release.csv | CDC PLACES, 2025 release | National tract file, 83,522 tracts. Includes FOODSTAMP, FOODINSECU and LACKTRPT columns (see finding F-1) |
| DS-H8 | SNAP_Retailer_Location_data.csv | USDA SNAP retailer locator export | 248,872 retailers nationally (FL 14,033; NY 16,015; UT 1,516), with latitude/longitude. Not joined to tracts |
| DS-H9 | mortgage_denials_originations_by_tract.xlsx | Not stated in the Drive folder | Mortgage originations and denials by tract. Not opened yet (no Excel reader in the kernel) |
| DS-H10 | Small Business FL.pdf, Small Business NY.pdf, SmallBusinessUtah.pdf | Provided with the Drive folder | Small-business context PDFs. Not yet read |

**Geography.** In the hackathon files, "Central Florida" is four counties: Orange (267 tracts), Seminole (89), Lake (75) and Osceola (59).

**Gap in the Drive folder.** The brief says SBA lending data is available, but no SBA loan file appears in the folder. See DS-X5.

### Findings from inspecting the files

- **F-1: CDC PLACES social-needs measures are empty for Florida.** In DS-H7, `FOODSTAMP_CrudePrev`, `FOODINSECU_CrudePrev` and `LACKTRPT_CrudePrev` have values for 40 states and no values at all for FL (also CO, KY, OR, PA, SD, TN, TX, VT, WA, WY). NY has 5,289 populated tracts and UT has 710. This explains why transportation data is missing for Central Florida, and it is a direct input to the blind-spot map.
- **F-2:** DS-H6 includes `TractSNAP` and `PovertyRate` in its tract characteristics file, which duplicates part of DS-H1 and DS-H2.
- **F-3: SBA 7(a) and 504 lending per resident does not follow food need by tract.** Over 488 Central FL tracts, Spearman rho between loans per 1,000 residents (all years) and SNAP share is -0.051 (p = 0.26), and with poverty rate -0.021 (p = 0.65). Desert tracts have a median of 1.7 loans per 1,000 residents and nogap tracts 1.8 (Mann-Whitney p = 0.82). 50 of 97 desert tracts are below the median lending, against 49.6% of nogap tracts (Fisher p = 0.82). The only signal is a weak positive link with no-vehicle share (rho 0.136, p = 0.0026), which is a noisy proxy. The result holds under a 2,000 population floor, an ACS 2024 denominator and raw counts. The claim that food need lines up with need for SBA lending is not supported. The data has no measure of need for capital. Sources: DS-X5, DS-H1, DS-H2, DS-H4, DS-H6, DS-X7b, DS-X24. Basis: computed in repo by `scripts/analysis/need_vs_sba_lending.py`. Note: `docs/analysis/need-vs-sba-lending.md`.

## 2. Beacon and event materials (In repo, `docs/hackathon/`)

| ID | Item | URL | Status |
|---|---|---|---|
| DS-B1 | Beacon challenge brief | https://docs.google.com/document/d/1UFeoveMyn0UYYCc3oj4fVDRtXSA5nHvSzRTJfswc_Do | In repo: `beacon-challenge-brief.md` |
| DS-B2 | Beacon appendices A-C | https://docs.google.com/document/d/1L25DTxI31BlrH3QvB7k8H0rt6eowMiYA3YqHEwfJer0 | In repo: `beacon-appendices.md` |
| DS-B3 | DevFest Florida hackathon challenges | https://docs.google.com/document/d/e/2PACX-1vScTd33Ugr1xgLyJgOsECSZSKvMGaNRP19s2q01w8eZNBPwz7vTDqcPtyMjDyaE04xI2eykW4qcPvEp/pub?pli=1 | In repo: `devfest-hackathon-challenges.md` |
| DS-B4 | Beacon design and brand guidelines (v1.0, April 2026) | https://drive.google.com/file/d/1KZY4wAevNOpc0kg6owQqYE42hqKYrB2J/view | In repo: `resources/beacon-design-brand-guidelines.pdf` |
| DS-B5 | Presentation template | https://docs.google.com/presentation/d/1K32JXLRfH8UiGm-f5gWX9rhQ3gOBRsqxuU0g7JMQu98 | In repo: `resources/presentation-template.pptx` |
| DS-B6 | Submission folder | https://drive.google.com/drive/folders/1uocGWDFvUqsOzP5cm0CzO7rNlhv6kxsF | Folder was empty when checked |
| DS-B7 | Beacon site: home, getting started, guides (map analysis, upload data, teams, dataset builder), FAQ, about, license, terms | https://www.explorebeacon.org and https://www.marketing.explorebeacon.org | Text in `linked-pages.md` |
| DS-B8 | Beacon demo video | https://youtu.be/DC62d8BsUEs | Linked; video not downloaded |
| DS-B9 | CDFI Fund infographic | https://www.cdfifund.gov/system/files/documents/cdfi_infographic_v08a.pdf | In repo: `resources/cdfi-fund-infographic.pdf` |
| DS-B10 | Resource directories named in the appendices: SBA Resource Partner locator; NYC small business support map; Utah Association of Chambers directory; Feeding America food bank finder; USA.gov food help; Second Harvest Food Bank of Central Florida food finder; NYC Food Help; 211 Utah; NYC Open Data SBS Certified Business List | See `linked-pages.md` for each URL | Interactive finder tools. Static text only is captured. The Second Harvest finder returned 403 to automated fetch |

**Licensing note.** The Beacon site license page says its content is CC BY 4.0 and requires attribution to DataKind with a link to www.datakind.org (see `linked-pages.md`, "Beacon license"). Underlying public datasets (Census, USDA, CDC) carry their own publishers' terms. Credit DataKind and Beacon in the app and the write-up.

**Beacon capability facts (from the FAQ and guides).** Public data is available at census tract, ZCTA, county and congressional-district levels. The dataset builder exports a zip with a data CSV and a data-dictionary CSV. The map analysis allows up to 3 boundary indicators at once. Beacon updates data within 3 months of a source refresh. Beacon states that its data coverage can be incomplete because source data is incomplete.

## 3. External sources for the data gaps (not in the repo yet)

| ID | Gap it fills | Source | URL | What it provides | Status |
|---|---|---|---|---|---|
| DS-X1 | No per-tract data on actual SNAP cuts; need county-level counts to calibrate the forecaster | USDA FNS SNAP data tables | https://www.fna.usda.gov/pd/supplemental-nutrition-assistance-program-snap | Bi-annual (January and July) state and county participation and issuance data | Linked; not downloaded |
| DS-X2 | Same gap, Florida detail | Florida DCF ESS Standard Reports | https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-standard | Monthly Florida SNAP caseload reports | Linked; not downloaded |
| DS-X3 | Same gap; context and county table | Florida Policy Institute, "Participation in SNAP Falls Sharply Across Florida After Congress Makes Drastic Program Cuts" (Cindy Huddleston, 2026-06-11) | https://www.floridapolicy.org/posts/participation-in-snap-falls-sharply-across-florida-after-congress-makes-drastic-program-cuts | Statewide decline figures, county-level drop, H.R. 1 summary (see section 4) | Linked; text read |
| DS-X4 | Policy rules the forecast should model | OBBBA (H.R. 1) SNAP explainers: BenefitsUSA https://benefitsusa.org/en/blog/obbb-snap-changes-2026-every-rule-that-changed ; Brookings https://www.brookings.edu/articles/snap-cuts-in-the-one-big-beautiful-bill-act-will-significantly-impair-recession-response/ | As listed | Work-requirement age range raised to 64, other eligibility changes | Search-listed; read only snippets. Verify against CBPP or USDA before using any rule in the app |
| DS-X5 | SBA lending missing from Drive folder | SBA 7(a) and 504 FOIA loan data | https://data.sba.gov/dataset/7a-504-foia | Loan-level 7(a) and 504 files, updated quarterly, with a data dictionary. Need to geocode to tracts | Linked; not downloaded |
| DS-X6 | Same | SBA open data: PPP, other loan reports | https://data.sba.gov/oca-datasets | PPP loan-level data and other reports | Linked; not downloaded |
| DS-X7 | Transportation proxy for Central Florida (PLACES is blank) | Census ACS table B08201 (household size by vehicles available), ACS 5-year via the Census API | https://api.census.gov/data/2024/acs/acs5/variables.html ; table reference https://censusreporter.org/tables/B08201/ | Households with no vehicle, by tract. Candidate stand-in for the missing transportation indicator | API page linked; Census Reporter 403 to automated fetch; not downloaded |
| DS-X8 | Above-the-line need: income relative to the eligibility line | SNAP eligibility rules: USDA FNS https://www.fna.usda.gov/snap/recipient/eligibility ; Florida DCF https://www.myflfamilies.com/services/public-assistance/supplemental-nutrition-assistance-program-snap/snap-eligibility/ | As listed | Gross income test at 130% of the federal poverty level; reporting rules. Pair with ACS income-to-poverty-ratio tables (not yet identified) | Linked; ACS ratio table to be chosen |
| DS-X9 | Replacement for discontinued USDA food-security data | Feeding America Map the Meal Gap: portal https://map.feedingamerica.org/ ; county data request page https://www.feedingamerica.org/research/map-the-meal-gap/by-county ; Feeding Florida page https://www.feedingflorida.org/take-action/learn/map-the-meal-gap/ | As listed | County and congressional-district food insecurity estimates, by income band, child and senior rates | Portal and request page linked; county data may require a request form |
| DS-X10 | Same; official food-security source status | USDA ERS Household Food Security in the United States in 2024 https://www.ers.usda.gov/publications/113622 ; USDA announcement of termination https://www.usda.gov/about-usda/news/press-releases/2025/09/20/usda-terminates-redundant-food-insecurity-survey | As listed | Last national report; evidence of discontinuation | ERS linked; USDA release search-listed |
| DS-X11 | Local food insecurity context | Second Harvest Food Bank of Central Florida, Map the Meal Gap page | https://feedhopenow.org/our-work/hunger-in-central-florida/map-the-meal-gap-report/ | Service-area food insecurity (649,820 people, 1 in 7, per search snippet) | Search-listed |
| DS-X12 | No pantry locations, hours or capacity | Second Harvest food finder (Brevard, Lake, Marion, Orange, Osceola, Seminole, Volusia counties) | https://feedhopenow.org/find-help/food-finder/ | 424 partner sites with name, free-text hours, address, phone, lat/lng. Matched to census tracts by us | **In repo**: `data/external/second-harvest-food-finder/`; method and limits in `docs/hackathon/second-harvest-food-finder-data.md`. Redistribution permission not yet confirmed |
| DS-X13 | Same | FeedingFL Central Florida food help | https://feedingfl.org/food-help/central-florida/ | Directory for Orange, Osceola, Seminole | Linked; directory only |
| DS-X14 | Same | United Way of Central Florida 211 | https://uwcf.org/211/ | Referral service covering food and nutrition programs | Linked; service, not a dataset |
| DS-X15 | Tract boundaries for the map | Census cartographic boundary files https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html ; TIGER/Line https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html | As listed | Simplified tract polygons for mapping (shapefile, KML). Needed for any choropleth | Linked; not downloaded. The hackathon data has no geometry |
| DS-X16 | Hurricane and disaster resilience overlay (optional) | FEMA National Risk Index | https://www.fema.gov/about/openfema/data-sets/national-risk-index-data ; overview https://www.fema.gov/flood-maps/products-tools/national-risk-index | Tract-level expected annual loss, social vulnerability, community resilience | Search-listed |
| DS-X17 | Tract-level food access definitions; atlas | USDA ERS Food Access Research Atlas | https://www.ers.usda.gov/data-products/food-access-research-atlas | Tract-level food access indicators; documents LILA definitions | Linked; the hackathon DS-H6 already contains the 2025 data |
| DS-X18 | Statewide food insufficiency trend | Census Household Pulse Survey and its successor, HTOPS | https://www.census.gov/programs-surveys/household-pulse-survey/data.html | National and state food sufficiency; cross-sectional collection ended 2024-09-16 | Linked; national level only |
| DS-X19 | Small business context and need statements | Federal Reserve Banks, Survey of Small Business Resource Organizations, 2025-07-15 https://www.fedsmallbusiness.org/analysis/2025/2025-survey-of-business-resource-organizations ; CDFI Fund study of CDFIs and conventional lenders https://www.cdfifund.gov/system/files/documents/relationships-between-community-development-financial-institutions-and-conventional-lenders-in-small-business-finance.pdf | As listed | Qualitative evidence for the program-officer persona | Linked |
| DS-X20 | SNAP participant characteristics | USDA FNS, Characteristics of SNAP Households: FY2023 | https://www.fna.usda.gov/research/snap/characteristics-fy23 | National and state SNAP household characteristics (QC data) | Linked |
| DS-X21 | Transportation and food access evidence | Food Swamps and Transportation Access: Intersecting Structural Determinants (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC12563320/ | Research on food swamps and transportation barriers | Linked |
| DS-X22 | Local SBDC network (outreach target for the officer view) | Florida SBDC Network | https://floridasbdc.org/ | Network of advising centers | Search-listed |
| DS-X23 | Health measures (non-social-needs) for Florida | CDC PLACES | https://www.cdc.gov/places/ | Tract-level health estimates; social-needs measures are blank for FL (see F-1) | Search-listed |
| DS-X27 | Match points to census tracts | US Census Bureau Geocoder, coordinates endpoint | https://geocoding.geo.census.gov/geocoder/ | Tract and county for a latitude/longitude. Used for DS-X12 (424 of 424 matched). Renumbered from DS-X24 to avoid a collision with the census block IDs | Used; free, no key |
| DS-X24 | Population near a landmark or latitude/longitude (finer than tract) | Census TIGER/Line 2020 blocks, Florida (`tl_2020_12_tabblock20.zip`) | https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_12_tabblock20.zip | Block polygons with 2020 population, housing units and an interior latitude/longitude point | Downloaded 2026-11-07; 353 MB zip not committed. Extract for the 4 hackathon counties (Orange, Seminole, Lake, Osceola) in `data/external/census-2020-blocks/` (see its README) |
| DS-X25 | Verification of DS-X24 county sums | Census 2020 redistricting data (PL 94-171), Florida (`fl2020.pl.zip`) | https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Florida/fl2020.pl.zip | Official 2020 counts (P1 population, H1 housing units) for all Florida geographies | Downloaded 2026-11-07; used for verification only, not committed |
| DS-X26 | 2020 to 2025 county growth factors for DS-X24 | Census Vintage 2025 county population estimates (`co-est2025-alldata.csv`) | https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv | July 1 estimates 2020 to 2025 for each county, with the April 1, 2020 estimates base | Downloaded 2026-11-07; values for the 4 counties copied to the DS-X24 README; not committed |

## 4. Facts retrieved for citation

Each fact is attributed to its source. Treat figures from search snippets as unverified until the full page is read.

| ID | Fact | Source | Basis |
|---|---|---|---|
| FACT-1 | H.R. 1, enacted 2025-07-04, cut federal SNAP funding by $187 billion over 10 years. | DS-X3 (Florida Policy Institute) | Full page read |
| FACT-2 | In the first five months after enactment, Florida SNAP participation fell about 10 percent, or 277,513 people. | DS-X3 | Full page read |
| FACT-3 | In the year before enactment, Florida participation fell about 3.2 percent. | DS-X3 | Full page read |
| FACT-4 | Every Florida county dropped significantly in 2025. The highest declines, about 14 percent, were in Monroe and Collier counties. | DS-X3 | Full page read |
| FACT-5 | Florida DCF estimated about 9,753 lawfully present immigrants became ineligible, and about 181,217 participants had benefits put at risk by expanded work-reporting rules. | DS-X3, citing DCF | Full page read |
| FACT-6 | States pay a share of benefit costs from FY2028 if error rates are 6 percent or higher, with possible delays to 2029 or 2030. Administrative cost share rises from FY2027. | DS-X3 | Full page read |
| FACT-7 | Florida caseload fell by about 20,000 more people in January 2026 alone, and is at its lowest in over 15 years. | DS-X3 | Full page read |
| FACT-8 | About 25 million people, nearly half of those who are food insecure, had incomes too high for federal nutrition assistance (2024 data, released 2026-07-28). | Feeding America press release | Page read (https://www.feedingamerica.org/about-us/press-room/Map-the-Meal-Gap-2026) |
| FACT-9 | The national food budget shortfall exceeded $33 billion; food-insecure households reported needing $23.16 more per person per week. | Same | Page read |
| FACT-10 | USDA stopped collecting food security data; Feeding America plans to explore alternative data sources for 2027 onward. | Same, and USDA announcement dated 2025-09-20 (DS-X10) | Feeding America page read; USDA snippet only |
| FACT-11 | SNAP gross income limit is 130 percent of the federal poverty level, with a net income limit of 100 percent. | DS-X8; BenefitsUSA https://benefitsusa.org/en/snap-income-limits | Snippets only |
| FACT-12 | Fed survey (143 organizations, April 2025): over half reported small businesses less optimistic; a majority reported harder operating costs, supply chains and financing. | DS-X19 | First chunk of the page read |
| FACT-13 | Second Harvest Food Bank of Central Florida reports 649,820 people (1 in 7) food insecure in its service area (Map the Meal Gap 2026). | DS-X11 | Search snippet only |

## 5. Known caveats

1. The Florida Policy Institute article is advocacy research. Its figures cite state and federal data, but we should recompute county declines from DS-X1 or DS-X2 before presenting them as facts.
2. Eligibility rules in FACT-11 come from snippets and an explainer site, not the rule text. Confirm with the USDA FNS page before encoding thresholds.
3. No dataset in sections 1 or 3 gives household-level eligibility. "Above-the-line" must stay a tract-level likelihood.
4. Sites that blocked plain fetches were retrieved with a headless browser (DS-X12 and section 6). Values from the FEMA service and the Census Reporter API should still be checked against the publishers' bulk files before we quote them in a submission.
5. We did not download GUIDE-track data (the higher-education starter package). It is outside the Beacon track.
6. The Census Data API (api.census.gov) returned a "Missing Key" page for a request with no key (checked 2026-11-07). Get a free API key before you use DS-X7 or other API pulls. Census QuickFacts returned HTTP 403 (Cloudflare) to automated fetches. Files on www2.census.gov downloaded without problems.

## 6. Second pass: previously blocked sources (retrieved with a headless browser)

Details, methods and limits: `docs/hackathon/external-data-retrieved.md`. Full page text: `docs/hackathon/blocked-pages-text.md`.

| ID | Source | URL | Result | Repo location |
|---|---|---|---|---|
| DS-X3b | CBPP SNAP Tracker (data updated 2026-10-21) | https://www.cbpp.org/research/food-assistance/snap-tracker-people-are-losing-food-assistance-as-the-harmful-2025 ; workbook https://apps.cbpp.org/fa2-24-26/data/downloadable_data.xlsx | In repo. State-level monthly SNAP participation. Florida down 22.1% from July 2025 to July 2026 | `data/external/cbpp-snap-tracker/` |
| DS-X16b | FEMA National Risk Index, census-tract layer | https://www.fema.gov/about/openfema/data-sets/national-risk-index-data ; overview https://www.fema.gov/flood-maps/products-tools/national-risk-index ; service `services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0` | In repo for the four counties (489 tracts) | `data/external/fema-nri/` |
| DS-X15b | Tract polygons (2020 tracts, from the FEMA layer above) | Same service | In repo. Fills the tract-boundary gap | `data/external/geography/` |
| DS-X7b | ACS 2024 5-year B08201, no-vehicle households, via Census Reporter | https://censusreporter.org/tables/B08201/ ; API https://api.censusreporter.org | In repo for 490 tracts. The Census Bureau API now requires a key (not used) | `data/external/census-acs/` |
| DS-X9b | Feeding America Map the Meal Gap, county pages | https://map.feedingamerica.org/ | In repo for four counties (2024 data year) | `data/external/feeding-america/` |
| DS-X10b | USDA press release, 2025-09-20, "USDA Terminates Redundant Food Insecurity Survey" | https://www.usda.gov/about-usda/news/press-releases/2025/09/20/usda-terminates-redundant-food-insecurity-survey | Text read in full; confirms termination of future Household Food Security Reports | `docs/hackathon/blocked-pages-text.md` |
| DS-X11b | Second Harvest, Map the Meal Gap page | https://feedhopenow.org/our-work/hunger-in-central-florida/map-the-meal-gap-report/ | Text read in full; regional figures in FACT-14 to FACT-16 | `docs/hackathon/blocked-pages-text.md` |
| DS-X9c | Feeding Florida, Map the Meal Gap page | https://www.feedingflorida.org/take-action/learn/map-the-meal-gap/ | Text read; statewide figures only | `docs/hackathon/blocked-pages-text.md` |
| DS-X23b | CDC PLACES home and current release notes | https://www.cdc.gov/places/ ; https://www.cdc.gov/places/current-release-notes/index.html | Text read. No explanation found for Florida's blank social-needs values (see F-1) | `docs/hackathon/blocked-pages-text.md` |
| DS-X22b | Florida SBDC homepage and "Find Your SBDC" | https://floridasbdc.org/ ; https://floridasbdc.org/find/ | Text read. UCF SBDC serves Brevard, Flagler, Lake, Orange, Osceola, Seminole, Sumter and Volusia | `docs/hackathon/blocked-pages-text.md` |
| DS-X3c | FRAC SNAP map by county, and interactive data tools | https://frac.org/research/resource-library/snap-map-snap-matters-every-community ; https://frac.org/research-resources/interactive-data-tools/ | Text read. Interactive dashboard only; no downloadable file found. Meta-analysis PDF: https://frac.org/wp-content/uploads/2026/09/SNAP-Maps-Meta-analysis.pdf | `docs/hackathon/blocked-pages-text.md` |

### Additional facts

| ID | Fact | Source | Basis |
|---|---|---|---|
| FACT-14 | Florida SNAP participation (USDA series) fell from 2,849,238 in July 2025 to 2,219,639 in July 2026, down 22.1%. | DS-X3b workbook | Computed by us from the downloaded workbook |
| FACT-15 | SNAP participation fell in every state except Alaska between July 2025 and July 2026, down 5.5 million people (13 percent) nationally to 36.1 million. Florida is one of seven states with declines of 20 percent or more. | DS-X3b page text | Page read |
| FACT-16 | Second Harvest's seven-county area has 649,820 food insecure people (1 in 7), including 178,020 children. The annual meal gap is 123.4 million meals. 38.9% of food insecure people may not qualify for SNAP on income alone. | DS-X11b | Page read |
| FACT-17 | The earlier "45 percent" decline in a CBPP snippet refers to Arizona (July 2025 to September 2026), not Florida. Florida's decline is in FACT-14. | DS-X3b page text | Page read |
| FACT-18 | Orange County has 225,170 food insecure people (15.3%); 40% are above the SNAP threshold. Osceola 77,700 (18.2%, 30% above). Seminole 63,100 (13.1%, 49% above). Lake 54,010 (13.1%, 43% above). | DS-X9b | County pages read |
| FACT-19 | USDA announced on 2025-09-20 that it would end future Household Food Security Reports. | DS-X10b | Primary source read |
