# Core taxonomy (draft, cycle 13)

Purpose: the short glossary that the QueryService sends to the model with every question, so the model uses these terms the way the brief, the data owners and this project do. It is grounded: each entry quotes or points to a source. A term with no stated definition is not here. The long dictionaries (SBA fields, USDA SRAM variables, FEMA NRI fields, Census table shells, Household Pulse variables) are loaded into the warehouse and reached through the schema tool; they are not sent with every question.

Status: draft for human review. Wording marked "project rule" is this project's own decision, recorded in `requirements/REQUIREMENT_MANIFEST.md`.

## Food access

| Term | Definition | Source |
|---|---|---|
| LILA | Low-Income AND Low-Access. The version to use is the one at 1/2 mile (urban) and 10 miles (rural), "not a distance-only flag." "LILA is the standard definition of a 'food desert' used in policy and research, since it requires both low income and low access, not just distance from a store." | `docs/hackathon/beacon-appendices.md`, Appendix B data notes (DS-B2) |
| DD_SRAM_LILATracts_halfAnd10 | USDA field: low-income and low-access tract measured at 1/2 mile for urban areas and 10 miles for rural areas, using driving (network-based) distance. The SRAM measures access to SNAP-authorized retailers. | USDA ERS SRAM variable lookup, driving distance (DS-H6) |
| SD_SRAM_LILATracts_halfAnd10 | The same flag using straight-line distance. | USDA ERS SRAM variable lookup, straight-line distance (DS-H6) |
| Classic Food Desert (brief) | Gap type: "Poverty rate in the top quartile, flagged under the LILA 1/2 or 10 miles low grocery access definition." Resource mapping in the brief: nearest food bank or pantry, mobile pantry programs if listed. | Appendix B gap taxonomy (DS-B2) |
| Classic Food Desert (project rule) | A tract whose poverty rate is at or above the 75th percentile of the tracts that have a poverty value (ACS 2024) AND whose `DD_SRAM_LILATracts_halfAnd10` flag is 1. The cut is computed, not a rounded number. | Manifest zone Z-1 |
| Transportation-Compounded Gap | Gap type: flagged for low grocery access and a no-reliable-transportation rate in the top quartile. The brief says the rate exists for NYC and Salt Lake City only. | Appendix B (DS-B2) |
| Possible Blind Spot | Gap type: "No indicator crosses its top-quartile threshold, but at least two of the available indicators fall in the second-highest quartile." No automatic recommendation; Review Required. | Appendix B (DS-B2) |
| Transport gap (project rule) | A Classic Food Desert tract whose household no-vehicle rate is at or above the inclusive 75th percentile of the non-blank no-vehicle rates across the Central Florida tracts (6.90%). The no-vehicle rate is a project proxy from ACS B08201, not the brief's "no reliable transportation" indicator. | Manifest REQ-20, DS-X7b; contract POST-ALN-2 |
| No gap flagged | A tract that is not a Classic Food Desert under the project rule. It does not mean the tract has no need. | Manifest D-1 |
| Insufficient data | A tract with a missing or blank rate that the rule needs, shown as Insufficient data and not as low need. | Manifest D-1, REQ-8 |

## Small business and lending

| Term | Definition | Source |
|---|---|---|
| SBA 7(a) and 504 | The two SBA loan programs in the FOIA loan files. "GrossApproval" is the total loan amount; "SBAGuaranteedApproval" is the amount of SBA's guaranty. | SBA 7(a) and 504 data dictionary (DS-X5) |
| Capital Access Gap | "SBA loan count per capita in the bottom quartile, despite a sizable labor force/population base." Maps to CDFIs, microloan lenders and SBA 7(a)/504-active lenders. | Appendix A (DS-B2) |
| Entrepreneurship Infrastructure Gap | "Poverty and/or unemployment rate in the top quartile, SBA loan count per capita in the bottom quartile." | Appendix A (DS-B2) |
| Credit Access Gap | "Mortgage denial rate ... in the top quartile, SBA loan activity at or above the median." The mortgage denial rate is Mortgage Denials divided by (Denials plus Mortgages Originated). | Appendix A (DS-B2) |
| Underinvestment Gap | "Median household income and employment rate both at or above the median, SBA loan activity in the bottom quartile" (the "looks fine but isn't" case). No automatic recommendation; Review Required. | Appendix A (DS-B2) |
| Dual gap (project rule) | A Classic Food Desert tract with at or below the regional median of 10 SBA loans (7(a) plus 504, DS-X5). 50 tracts in Central Florida. | Manifest REQ-19 |
| Triple gap, "Opportunity to Serve" (project rule) | A dual-gap tract that is also a transport-gap tract. 29 tracts in Central Florida. | Manifest REQ-20 |
| JobsSupported | "Total Jobs Created + Jobs Retained as reported by lender on SBA Loan Application." SBA does not review, audit or validate these numbers. | SBA data dictionary (DS-X5) |
| LoanStatus | CANCLD cancelled, CHGOFF charged off, COMMIT undisbursed, EXEMPT disbursed and not yet cancelled, paid or charged off (exempt from disclosure under FOIA Exemption 4), PIF paid in full. | SBA data dictionary (DS-X5) |

## Review and confidence (from the brief)

| Term | Definition | Source |
|---|---|---|
| Review tiers | No review needed: single clear gap type, strong evidence, direct resource match. Review recommended: competing gap types or moderate confidence. Review required: any underinvestment or blind-spot case, or conflicting or insufficient data. | Appendix A (DS-B2) |
| Confidence (brief) | High, Medium or Low in the brief's example output format. | Appendix A (DS-B2) |
| Confidence (project rule) | Not rated when the class is Insufficient data; Lower when households are under 500 or the group-quarters share is over 20%; Moderate otherwise. | Manifest REQ-22 |

## Geography and measures

| Term | Definition | Source |
|---|---|---|
| Tract | A 2020 census tract, identified by an 11-digit GEOID. Block values appear only as tract sums. | Manifest REQ-4 |
| Base geography | Boundary and census-block files; exempt from the 2024 scope and kept at the most recent vintage. | Manifest Z-15 |
| Poverty rate | "Share of the tract population living with income at or below the Federal poverty thresholds for family size." | USDA SRAM general tract characteristics lookup (DS-H6) |
| TractHUNV | "Total count of housing units without a vehicle in tract." | USDA SRAM lookup (DS-H6) |
| NRI, EAL | FEMA National Risk Index v1.20. "Expected Annual Loss" fields are in the NRI data dictionary; hazard prefixes (for example HRCN for hurricane) are in NRI_HazardInfo. | FEMA NRI data dictionary (DS-X16) |
| MOE | The 90% margin of error that ACS publishes with each estimate. | Manifest REQ-22, DS-X28 |

## Data scope words

| Term | Definition | Source |
|---|---|---|
| Reference period | The time the data describes, not the download date. The warehouse holds sources whose reference period reaches 2024-01-01 or later, plus base geography. | Manifest Z-15 |
| not recorded | A provenance field that the files, the manifest and the data sources document do not state. It is not inferred. | Manifest REQ-31 |
