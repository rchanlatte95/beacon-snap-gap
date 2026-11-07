# Design: personas, shared summary and suggestions (planner map mock-up)

Status: **design proposal, nothing decided.** Task T7 of the feedback wave, 2026-11-07, base commit `c8146db`. This file does not change `requirements/`, `contracts/` or `plans/`. Candidate requirements are listed in section 6 for a later req-elicit cycle.

It answers this feedback:

- "A program manager cannot decide in a silo. A shared alignment driver is needed." Ryan (project lead) decided this means one shared summary that food banks, SBDCs or CDFIs, and funders can all agree on.
- "The multiple persona view is important."
- "Output: data explanation, suggestions, recommendations."
- The lead: progressive disclosure, plain words, five-minute understanding.

The brief asks the same thing: "How might that individual insight move into collective sensemaking with a team? How might that shared understanding be turned into action?" (DS-B1, Challenge 1).

## 0. Top line

**Recommended shared driver: "Common ground: same places, shared facts, shared doubts, separate jobs."** All three partners look at the same short list of neighborhoods (the 97 Classic Food Desert tracts from the decided Z-1 rule), the same plain facts about money strain in those places (poverty and SNAP share, measured for 488 tracts), and the same list of what we do not know. Each partner then sees what *it* could consider there. The summary does not claim that food need and the need for loans go together. Finding F-3 tested that claim and did not support it.

Decisions a human must make before the next wave builds this (details in sections 2.5, 3.4 and 5):

| ID | Decision | Recommendation |
|---|---|---|
| H-1 | Which shared driver (section 2.1) | Candidate A, "same places, shared facts" |
| H-2 | Is the shared short list the 97 Classic Food Desert tracts only, or a union with the brief's small-business gap types? | The 97 only. A union mixes two rules and two meanings of "need" |
| H-3 | May the summary show the 50 "high need, low lending" tracts (F-3) as a list to talk about? | Yes, only with the fixed guard sentence in rule S7 |
| H-4 | Which confidence rule (A, B or C) feeds "How sure we are" | Still open from the mock-up; the suggestions cannot be rated until it is decided |
| H-5 | Every stand-in threshold in the rule table (no-vehicle cut, load cut, lending quartile, population floor) | Approve each value, or replace it, before any rule is coded |
| H-6 | May the no-vehicle estimate drive a suggestion at all (F-1)? | Yes, capped at "Low" sureness and always labeled an estimate |
| H-7 | Which organization and program names may appear in suggestions | Use help *categories* only until a human approves a named catalog |
| H-8 | Who reviews suggestions before anyone acts on them | The brief names DataKind staff as reviewer for the appendix tiers; confirm for this app |
| H-9 | How the summary is shared without a server (the App may not store user data on a server) | A print view and a link that holds the view state; no comments yet |
| H-10 | Fixed wording of each suggestion (like REQ-3) | Approve the texts in section 3.2 word for word, or edit them |

### 0.1 Decisions recorded (Ryan, 2026-11-07)

| ID | Decision |
|---|---|
| H-1 | Accepted. The shared driver is candidate A, "Common ground: same places, shared facts". |
| H-3 | Accepted. The 50 "high need, low lending" tracts (F-3) show only in the detail level ("How we know this"), always with the fixed guard sentence of rule S7. |
| H-6 | Accepted. The no-vehicle estimate may drive a suggestion, capped at "Low" sureness and always labeled an estimate. |
| H-7 | Accepted. Suggestions name help categories only, not named organizations. |
| H-9 | Accepted. Sharing is a print view plus a link that holds the view state. No server storage. |
| H-2, H-4, H-5, H-8, H-10 | Still open. H-4 (confidence rule) needs Ryan and Ketema. |

## 1. Personas

Principle: **one set of facts, three lenses.** A persona changes the headline question, the order of the first numbers and the default Compare-with layer. A persona never changes the facts, the class of a tract or the text of the shared summary. If two partners open the app, they see the same map classes and the same summary. That is what makes it a shared driver.

The persona switch replaces the view tabs in the header ("I work at: Food bank / Small business help or lending / Funding or policy"). The current mock-up has a "Planner" tab and a disabled later-slice tab, so the switch fits there. The manifest lists the SBDC/CDFI officer view and a policymaker summary as later slices.

| | Food bank planner | SBDC or CDFI program officer | Funder or policymaker |
|---|---|---|---|
| Plain label in the switch | Food bank | Small business help or lending | Funding or policy |
| Decision they make | Where to send food, mobile pantry stops and new partner sites (manifest actor "Planner") | Where to hold outreach and classes, and which lender partners to bring (DS-B1 Challenge 1; DS-X19) | Which joint plans to fund, and which data gaps to pay to fix |
| Glance question (one sentence on the page) | "Where do many families need food, far from a pantry?" | "Where did few SBA loans go, and who lives there?" | "Where can partners agree to act, and how sure are we?" |
| Default Compare-with layer | `transport` (getting there) | `lending` (SBA loans) | `blindspots` (data gaps) |
| Second layer to offer | `imported` (own data, for example pantry visit counts) | `imported` (own data, for example a loan portfolio) | `transport` |
| First number 1 | Families who get SNAP, as "about 1 in N" (`pctSnap`, DS-H1) | SBA loans per 1,000 residents (DS-X5 over DS-X24), with "counted by the borrower's mailing address" | People who live in high-need neighborhoods (sum of `pop2020` over the 97, DS-X24) |
| First number 2 | Residents per pantry site in reach (`standinLoad`, Z-2e; labeled stand-in) | Median income (`medianFamilyIncome` from DS-H6 is in the stand-in now; household median DS-H3/DS-X28 is in the repo but not in the stand-in) | County share of people who may not have enough food, and the share of them above Feeding America's SNAP income line (DS-X9b, FACT-18) |
| First number 3 | Homes without a car (`noVehiclePct`, DS-X7b; labeled "estimate, not proven", F-1) | Share of adults without a job (DS-H5; not in the stand-in yet) | How many of the 97 we are less sure about (Low or Not rated, or a blank number; needs H-4) |

Notes:

- With no tract selected, each number is shown for the whole area or the selected county. With a tract selected, it is shown for that neighborhood.
- All numbers are computed from data files at runtime (brief rule 7). No number is typed into the UI.
- The SBDC lens must carry the F-3 limits: loans show where approved loans went by mailing address, not who needs a loan.
- "Funder" and "policymaker" share one lens in this design. They may need different numbers later (question Q-8).

## 2. Shared summary ("Common ground")

### 2.1 Candidate shared drivers, ranked by data support

| Rank | Candidate | What it says | Evidence | Support |
|---|---|---|---|---|
| 1 | **A. Same places, shared facts** | "These are the same neighborhoods each of us screens first. Here is what we all can see, and what none of us can see." | Poverty rate is an input to both brief frameworks: Appendix A "Entrepreneurship Infrastructure Gap" (poverty or unemployment in the top quartile) and Appendix B "Classic Food Desert" (poverty in the top quartile) (DS-B2). Poverty and SNAP share are measured for 488 tracts (DS-H1, DS-H2). The 97 high-need tracts come from the decided Z-1 rule. | **Strong for the facts.** It claims no link between needs. Caution: the overlap between the two frameworks is partly built in, because both use poverty. The page must not present the overlap as a discovery. The count of tracts flagged by both frameworks is to be tested |
| 2 | B. SNAP cuts reach families and the stores where they use SNAP | "Fewer people get SNAP. That hits families, and it may hit the local stores that take SNAP." | Florida SNAP participation fell 22.1% from July 2025 to July 2026 (FACT-14, DS-X3b). SNAP retailer points exist (DS-H8) but are not joined to tracts. No county or tract SNAP-cut series is in the repo (DS-X1, DS-X2 not downloaded) | **Medium at state level, not tested locally.** Good for funders, but the local part (store counts by tract, and how many stores are small businesses) is to be tested. Use it as a context line, not as the driver |
| 3 | C. Getting there is hard | "Many homes have no car. That matters for pantry trips and for reaching business help." | No-vehicle share correlates about 0.52 with SNAP share (CLAUDE.md, manifest Z-1 option E) and weakly with SBA loans per 1,000 (rho 0.136, F-3). The estimate is noisy: median margin of error 0.93 times the estimate (F-3 limit 6). It is a proxy, not a validated measure (F-1) | **Weak.** Useful inside the food lens. Too noisy to carry a shared story |
| 4 | D. Food need and SBA lending line up | "People who need food also need SBA loans." | Tested by T0. Lending per resident does not go up or down with SNAP share (rho -0.051, p 0.26) or poverty (rho -0.021, p 0.65). High-need and other tracts have the same median lending (1.7 and 1.8 loans per 1,000; Mann-Whitney p 0.82) (F-3) | **Not supported. Rejected.** F-3 allows only one remnant: the 50 high-need, low-lending tracts as a list to examine, with its limits (rule S7) |

Other files that could support a shared basis later, all **to be tested**:

- `mortgage_denials_originations_by_tract.xlsx` (DS-H9). Opened for this design: a README sheet says it is aggregated from the 2025 HMDA Modified Loan/Application Register for the three hackathon areas (Central Florida is the 7-county Second Harvest area), and a Data sheet has `census_tract`, `county_fips`, `area`, `mortgages_originated`, `mortgage_denials`, `total_applications`, `denial_rate` (a spreadsheet formula). It is not in the stand-in. The register entry for DS-H9 still says "Not opened yet" and should be updated by the data owner. Home mortgage denials are household credit, not business credit.
- FEMA NRI social vulnerability rating (DS-X16b, in the stand-in as `socialVulnerability`). Values come from the FEMA ArcGIS service, so check them against the bulk file before quoting.
- Median household income (DS-H3, DS-X28) and labor force (DS-H5).

### 2.2 Recommendation

Use **candidate A**. The shared driver is not a correlation. It is a shared, honest fact base: the same short list, the same facts, the same doubts, and a visible place where each partner's job is named. This matches what the brief asks for (collective sensemaking, then action, DS-B1) and what the data supports. Show candidate B as one dated context line. Do not use C or D as a driver.

Why this helps a program manager who "cannot decide in a silo": the summary gives three partners one page they can all sign off on, because every sentence on it is a fact they can check or a doubt they share. Each partner can then act on its own part without first agreeing on a claim the data does not support.

### 2.3 Text mock (one screen, grade 8 or lower)

The numbers below are the current values from the cited sources. In the app, each is computed from the data files. `[S-n]` points to the trace table in 2.4.

```
COMMON GROUND: food need in Central Florida
Orange, Seminole, Lake and Osceola counties.  Data as of: <date of each file>

WHAT WE ALL CAN SEE
 1. 97 of 490 neighborhoods have many people in poverty and a long trip
    to a grocery store. We call them high need.                          [S-1]
 2. 52 of these 97 have no Second Harvest site inside them.
    Other food sources may exist.                                        [S-2]
 3. In our four counties, between about 1 in 8 and nearly 1 in 5 people
    may not have enough food. Many of them earn too much to get SNAP.    [S-3]
 4. Across Florida, the number of people who get SNAP fell by more than
    1 in 5 in one year (July 2025 to July 2026). We do not have this
    number for each county or neighborhood.                              [S-4]
 5. SBA small business loans went to high-need neighborhoods about as
    often as to other neighborhoods. Loans do not tell us who needs one. [S-5]

WHAT NONE OF US CAN SEE YET
 6. How far people really travel to get food. Our travel test is a
    stand-in.                                                            [S-6]
 7. How many people each pantry serves, and how many businesses are in
    each neighborhood. This data is not in the app.                      [S-7]
 8. <N> of the 97 have a blank number or a low "how sure" label.         [S-8]

PLACES TO LOOK AT TOGETHER
 9. The 97 high-need neighborhoods.  [Open the list]  [Print this page]  [S-9]

WHAT EACH PARTNER COULD CONSIDER
 Food bank:   where a mobile pantry stop or a new partner site could help.
 Small business help or lending:  where to share loan and class
              information, and whether people there want it.
 Funder:      which joint plans to support, and which missing data to
              pay to collect.                                            [S-10]
```

At glance level, only lines 1, 2, 5, 6 and 9 show. The rest open with "See more" (explore level). Every line has a "How we know this" detail (section 4).

### 2.4 Trace table

| Line | Evidence | Computed from (runtime) | Detail-level caveat |
|---|---|---|---|
| S-1 | Z-1 rule and D-1 (manifest); DS-H2 poverty, DS-H6 driving-distance LILA flag; cut 17.025% (inclusive quartile over 488 tracts) | `records.counts.desert`, `records.tracts.length` | 2 tracts are Insufficient data; 1 (water) is not drawn |
| S-2 | DS-X12 sites, DS-H6; manifest Z-1 option B records "DD 97 tracts (52 with no site)" | count of desert tracts with `sitesInTract === 0` | REQ-3 text. The site list is one food bank's network only |
| S-3 | FACT-18 (DS-X9b): Orange 15.3% (40% above the SNAP threshold), Osceola 18.2% (30%), Seminole 13.1% (49%), Lake 13.1% (43%) | `records.mealGap` | County level, 2024 data year. Feeding America's "SNAP threshold" is 200% of poverty, not the federal 130% gross income test (CLAUDE.md; FACT-11 is snippet-based). Not a tract value |
| S-4 | FACT-14 (DS-X3b): 2,849,238 in July 2025 to 2,219,639 in July 2026, down 22.1% | `records.snapTrend` | State level, monthly. Net count, not the same people. No county or tract series (DS-X1, DS-X2 not downloaded) |
| S-5 | F-3: median 1.7 (high need) and 1.8 (other) loans per 1,000 residents; Mann-Whitney p 0.82; rho with SNAP share -0.051 | lending data file from the `lending` layer (T5) | Mailing address, not where residents live; 89.9% of loans placed; undercount higher in Lake, Seminole, Osceola; 7(a) and 504 only (DS-X5 README, F-3 limits) |
| S-6 | Z-2, Z-2b, Z-2d (30-minute drive decided); stand-in is 10 miles straight-line (mock-up README) | `records.standinReachMiles` | Routing data is not in the repo |
| S-7 | F-3 limits 2 and 3 (no business counts, no measure of need for capital); no pantry visit data in the register | none (fixed text) | The `imported` layer lets a partner add its own data |
| S-8 | REQ-5 (missing indicators); confidence rule not decided (H-4) | count of desert tracts with `missing.length > 0` or level Low or Not rated | Rule thresholds are stand-ins |
| S-9 | Z-1, D-1 | the existing high-need list | |
| S-10 | Appendix A and B resource mapping (DS-B2); section 3 of this file | fixed text | Considerations, not orders |

### 2.5 What the summary must never say

| Never say | Why |
|---|---|
| That food need and SBA lending (or the need for loans) line up, go together, or follow each other | F-3, brief feedback item 6 |
| That high-need neighborhoods get less lending, are "left out" by lenders, or are "underserved" by lenders | F-3: same median lending; 50 of 97 below the median against 49.6% of other tracts (Fisher p 0.82) |
| That loans measure who needs a loan | F-3 limit 2 |
| "no food access" or "no access", anywhere | REQ-16 |
| Anything other than the exact REQ-3 sentence when no Second Harvest site is found | REQ-3 |
| A value for one household, one person or one census block; "these families are eligible" | REQ-4, REQ-17; "above-the-line" is a tract-level likelihood only (CLAUDE.md) |
| That SNAP cuts caused anything in a given county or neighborhood | No county or tract SNAP-cut series (DS-X1, DS-X2 not downloaded) |
| County SNAP declines from the Florida Policy Institute as facts | Data sources caveat 1 (advocacy research; recompute first) |
| "Car-free" or "no car" as a fact for a neighborhood | F-1: no-vehicle share is an estimate and a proxy |
| "No need" or "fine" for a No gap flagged tract | "No gap flagged" is not "no need" (REQ-14 class name) |
| "Worst", "failing" or a ranking of partners or organizations | Not measured; blocks agreement between partners |
| Orders: "must", "should", "need to", "send", "fund this" | Suggestions are things to consider (section 3.1) |
| A FEMA or Census Reporter value as checked | Data sources caveat 4: check against bulk files first |
| A number that is not computed from a data file, F-3 or a cited DS or FACT entry | Brief rule 7 |

## 3. Suggestions (recommendations)

### 3.1 How a suggestion is written

1. It starts with "Consider" or "You may want to". It never uses "must", "should", "need to" or a bare order.
2. One reason, then one action. The reason is a plain clause before the action. At most about 20 words per sentence.
3. It names a *kind* of help (mobile pantry, credit counseling), not a ranked organization (H-7).
4. When the tract has no Second Harvest site inside it, the card shows the REQ-3 sentence word for word, before any suggestion. REQ-16 applies to every suggestion.
5. Every suggestion shows "How sure we are: High / Medium / Low / Not rated" (Appendix B wording) and a "Why we suggest this" link that opens the detail level.
6. A suggestion's sureness is the **lowest** of: the tract's confidence label (H-4) and the cap of its evidence in the table. A stand-in or a proxy caps the suggestion at Low.
7. Review tier (Appendix A and B): High with one rule fired is "No review needed"; Medium, or two rules that point different ways, is "Review recommended"; Low, Not rated, an underinvestment case or a blind spot is "Review required". In this mock-up no suggestion is "No review needed" until humans approve the rules (H-5, H-10).
8. A No gap flagged tract gets no food suggestion. It can still get a small-business suggestion.
9. Later slice (manifest: approve/challenge): each suggestion gets "Helpful", "Not right here" and "We need more data". When partners disagree, the page shows the disagreement (brief, recommendation engine stretch). It does not pick one answer.

### 3.2 Rule table

Thresholds marked **stand-in** need human approval (H-5). "Who acts" names the persona whose card shows the suggestion first; all personas can see all suggestions in the detail level.

| ID | Condition (tract data) | Plain suggestion (proposed fixed text) | Evidence | How sure (cap) | Who acts | Tier |
|---|---|---|---|---|---|---|
| S1 | Classic Food Desert AND `sitesInTract = 0` AND `noVehiclePct` at or above NV_CUT (**stand-in 6.9%**, the top-quartile cut in manifest Z-1 option E) | "Many homes here may not have a car. Consider a mobile pantry stop or home delivery." (after the REQ-3 sentence) | DS-H2, DS-H6, DS-X12, DS-X7b (estimate, F-1); Appendix B "Transportation-Compounded Gap" maps to mobile or delivery programs, but the brief says that rule is NYC and SLC only, so this is a stand-in version | Low (proxy with large margins of error) | Food bank | Review required |
| S2 | Classic Food Desert AND `sitesInTract = 0` AND (`noVehiclePct` below NV_CUT or blank) | "Consider checking for other food sources nearby before you plan a new stop or partner site." (after the REQ-3 sentence) | DS-H2, DS-H6, DS-X12; Appendix B "Classic Food Desert" maps to nearest pantry or mobile pantry | Medium (the site list is one network) | Food bank | Review recommended |
| S3 | Classic Food Desert AND `standinLoad` at or above LOAD_CUT (**stand-in**: top quartile of load over the 97; value to be computed) | "Pantry sites near here may serve many people. Consider asking them if they need more food, helpers or hours." | Z-2e (load, decided); DS-X12, DS-X24. Load spans 19 to 1,050 residents per site with the stand-in reach (mock-up README) | Low until the 30-minute drive rule replaces the 10-mile stand-in | Food bank | Review required |
| S4 | Classic Food Desert AND `socialVulnerability` is "Very High" or "Relatively High" | "People here may be hit harder by storms. Consider this place in storm and disaster food plans." | DS-X16b (ArcGIS values; check against the bulk file) | Medium | Food bank; Funder | Review recommended |
| S5 | SBA loans per 1,000 in the bottom quartile (**stand-in** cut, Appendix A) AND `pop2020` at or above 2,000 (**stand-in**; the floor F-3 used as a test) | "Few SBA loans went to addresses here. Consider sharing loan information, after you ask local owners what they need." | DS-X5, DS-X24; Appendix A "Capital Access Gap" maps to CDFIs, microloan lenders, 7(a) and 504 lenders | Low (mailing address; undercount differs by county) | Small business help or lending | Review required |
| S6 | Poverty or unemployment in the top quartile AND SBA loans per 1,000 in the bottom quartile (**stand-in** cuts) | "Consider business classes or mentoring here, for example through an SBDC." | DS-H2, DS-H5, DS-X5; Appendix A "Entrepreneurship Infrastructure Gap" maps to SCORE, Women's Business Centers, SBDCs, Chamber programs | Low | Small business help or lending | Review required |
| S7 | Classic Food Desert AND SBA loans per 1,000 (all years) below the median of 488 tracts (1.80 in F-3). This is the F-3 list of 50 tracts | "Food and small business partners may both want to look here. Consider one shared visit or meeting." **Fixed guard sentence, always shown:** "High-need places get about as many SBA loans as other places. This is a place to talk about, not a pattern." | F-3 (the note allows this list, with its limits); `docs/analysis/high_need_low_lending_tracts.csv` | Low | Food bank and Small business help or lending; Funder may convene | Review required |
| S8 | Median income and employment both at or above the median AND SBA loans per 1,000 in the bottom quartile | No suggestion. Text: "This place looks fine on most numbers but got few loans. A person needs to look at it first." | DS-H3 or DS-X28, DS-H5, DS-X5; Appendix A "Underinvestment Gap" (no auto-recommendation) | Not rated | Small business help or lending | Review required |
| S9 | Mortgage denial rate in the top quartile AND SBA loans per 1,000 at or above the median | "Consider credit help here, for example SBDC credit counseling or a CDFI." | DS-H9 (2025 HMDA; not yet in the stand-in; register entry to update); Appendix A "Credit Access Gap" | **Blocked: to be tested** | Small business help or lending | Review required |
| S10 | `cls = insufficient` OR a core indicator is blank (`missing` not empty) | "We cannot tell what is happening here from public data. Consider asking local partners, or adding your own data." | REQ-5, REQ-8; F-1 | Not rated | All; Funder may pay for data | Review required |
| S11 | Appendix B "Possible Blind Spot" (no top-quartile signal, two signals in the second-highest quartile) | No suggestion. "A person needs to look at this place first." | DS-B2. **Rule undefined for Central Florida**: LILA is a yes or no flag, so it has no quartile. A human must define it | Not rated | All | Review required |
| S12 | Meta rule: the tract's confidence is Low or Not rated | Adds "Check this before you act." to every suggestion on the card | H-4 (confidence rule) | sets the cap | All | Review required |
| S13 | Area level (funder): the county with the largest share of its high-need tracts at Low, Not rated or with blanks | "Consider paying for better local data here, for example pantry visit counts." | REQ-5; H-4 | Medium | Funder | Review recommended |

A card shows at most two suggestions at explore level: the first two that match the current persona. The rest are in the detail level.

### 3.3 What "How sure we are" means on a suggestion

| Label | Meaning (plain, shown on hover or in detail) |
|---|---|
| High | The numbers are strong, and one rule clearly fits. |
| Medium | The numbers fit, but one part is a guess or is old. |
| Low | It rests on a stand-in, an estimate or a small count. Check first. |
| Not rated | We do not have enough data to say. |

### 3.4 Decisions a human must approve before any rule is built

1. H-4: the confidence rule. Every "How sure" depends on it.
2. H-5: each stand-in threshold: NV_CUT (6.9%), LOAD_CUT, the lending quartile and median, the 2,000 population floor, and the quartile method (the Z-1 note uses the inclusive method; keep the same method for every cut).
3. H-6: whether the no-vehicle estimate may trigger S1.
4. H-3: whether S7 is shown at all, and the exact guard sentence.
5. H-7: help categories only, or a named catalog (Second Harvest programs, UCF SBDC (DS-X22b), SCORE, CDFIs). Second Harvest redistribution permission was not obtained; Ketema decided no request is needed (issue #4, manifest 6.5).
6. H-10: the fixed text of each suggestion.
7. H-8: who reviews "Review required" items, and what the app shows until then.
8. Whether lending suggestions (S5 to S9) may show on the food bank card at all, or only in its detail level. Recommendation: detail level only, to avoid an implied link (F-3).
9. A definition for S11 in Central Florida, or drop it.
10. Whether S9 is tested now (open DS-H9 in a committed script and register the result).

## 4. Progressive disclosure layout

### 4.1 Glance (first five seconds)

```
+----------------------------------------------------------------------------------+
| Beacon  Food need in Central Florida      [Common ground]                        |
|         I work at: (o) Food bank  ( ) Small business help or lending  ( ) Funding |
+--------------------------------+-------------------------------------------------+
| Where do many families need    |                                                 |
| food, far from a pantry?       |                                                 |
|                                |                                                 |
|  97         <1 in N>      ...  |                  MAP                            |
|  high-need  families get       |       (one question, legend <= 4 entries)       |
|  places     SNAP               |                                                 |
|  (3 numbers, persona order)    |                                                 |
|                                |                                                 |
|  Legend (<= 4 entries)         |                                                 |
|  Compare with: [Getting there v]                                                 |
|                                |                                                 |
|  Common ground: 1 line + link  |                                                 |
+--------------------------------+-------------------------------------------------+
| Data from DataKind Beacon (www.datakind.org), CC BY 4.0                          |
+----------------------------------------------------------------------------------+
```

- The persona switch sits in the header. It changes the headline, the three numbers and the default Compare-with layer only.
- The sidebar shows one line from the shared summary (line 1) with "See common ground". Every persona sees the same line.

### 4.2 Explore (click a neighborhood, or open Common ground)

Tract card:

```
+----------------------------------------------+
| <Neighborhood name>, <County>            [x] |
| [Classic Food Desert (high need)]            |
|                                              |
| What is here: <1 in N> families get SNAP.    |
| Why it matters: many people in poverty and a |
| long trip to a grocery store.                |
| How sure we are: Medium                      |
|                                              |
| No Second Harvest site found under this      |
| rule. Other food sources may exist.          |
|                                              |
| THINGS TO CONSIDER (max 2, your lens first)  |
|  - Many homes here may not have a car.       |
|    Consider a mobile pantry stop or home     |
|    delivery.   How sure: Low   [Why?]        |
|                                              |
| WHAT OTHER PARTNERS SEE (1 line each)        |
|  Small business help: <one fact line>        |
|  Funding: <one fact line>                    |
|                                              |
| > How we know this                           |
+----------------------------------------------+
```

(Text in angle brackets is a placeholder, not data.)

"What other partners see" is the shared lens on the card: one fact line from each other persona, so a planner sees the same place through a partner's eyes without switching.

Common ground view (replaces the sidebar, map stays):

```
+--------------------------------+-------------------------------------------------+
| COMMON GROUND                  |                                                 |
| What we all can see  (lines 1-5)|     MAP: the 97 high-need places outlined,     |
| What none of us can see (6-8)  |     nothing else                                |
| Places to look at together  (9)|                                                 |
|   [list, sorted by your lens]  |                                                 |
| What each partner could        |                                                 |
| consider (10)                  |                                                 |
| [Print this page] [Copy link]  |                                                 |
+--------------------------------+-------------------------------------------------+
```

### 4.3 Detail ("How we know this", inside `<details className="how-we-know">`)

- On the card: every number with its source ID, the class rule and cut, the rules that fired (S-IDs), each threshold with its stand-in label, the suggestion's sureness cap and why, every missing indicator (REQ-5), and the F-3 limits when any lending line shows.
- On Common ground: the trace table (2.4) per line, the dates of each file, and the "never say" list in plain form ("What this page will not claim").
- Technical words (LILA, ACS, quartile, margin of error, load, reach, proxy, Spearman) appear only here.

## 5. Open questions for humans

- Q-1 (H-1): Is candidate A the shared driver?
- Q-2 (H-2): Short list = the 97, or a union with the small-business gap types?
- Q-3 (H-3): Show the F-3 list of 50 with the guard sentence, or leave it out of the app?
- Q-4: Funder default layer: data gaps (recommended), or none?
- Q-5 (H-9): How do partners share the page? The App may not store user data on a server (manifest actor matrix), so notes, flags and approvals between people (brief stretch goal; manifest later slice "saved views, approve/challenge") need either a print view and a link with the view state, or a change to the actor matrix.
- Q-6 (H-7): Which program names may appear?
- Q-7 (H-8): Who reviews?
- Q-8: Do funders and policymakers need separate numbers?
- Q-9: Is the Feeding America county figure (200% of poverty "SNAP threshold") acceptable in the funder lens, given the CLAUDE.md caution about the 130% federal test?
- Q-10: Should the next wave test candidate B (join DS-H8 to tracts; download DS-X1 county data) and DS-H9 (mortgage denials)?
- Q-11: Persona labels: "Small business help or lending" for SBDC and CDFI, "Funding or policy" for funders. Are these plain and accurate enough?
- Q-12: Add the candidate requirements in section 6 through req-elicit?

## 6. Build plan for the next wave

Candidate requirements (for req-elicit, not decided): (a) the App shall not state or imply that food need and SBA lending line up, or that high-need tracts get less lending (F-3); (b) every suggestion shall be phrased as a consideration and show a sureness label; (c) the persona switch shall not change any fact, class or summary sentence.

| Task | Files | Depends on | Blocked by |
|---|---|---|---|
| N1. Analysis: test the shared-basis candidates. Count tracts flagged by both Appendix A "Entrepreneurship Infrastructure Gap" and Classic Food Desert (and say that both use poverty); join DS-H8 retailers to tracts and compare desert and nogap; open DS-H9 and test denial rate against poverty. Register results as F-4 onward | `scripts/analysis/shared_basis.py`, `docs/analysis/shared-basis.md`, `docs/data-sources.md` (F-4+, DS-H9 entry) | repo data only | none |
| N2. Persona config: id, label, question, default layer, first-number functions | `docs/mockups/planner-map/personas.ts` | T3 to T6 layer ids merged; T9 `copy.ts` | Q-11 |
| N3. Persona switch in the header; default Compare-with layer on switch | `PlannerMock.tsx`, `Sidebar.tsx`, `mockup.css` | N2 | shell owner assigned |
| N4. Summary facts: pure functions that compute each line from the data files | `docs/mockups/planner-map/summary.ts`, `tests/mockups/summary.test.ts` | T5 lending data file (loans per 1,000 per tract) | H-1, H-2 |
| N5. Common ground view and print styles | `docs/mockups/planner-map/CommonGround.tsx`, `mockup.css` | N4, T9 copy | H-9 |
| N6. Suggestion engine: the rule table as data (id, condition, text, evidence, cap, persona, tier) and pure evaluation | `docs/mockups/planner-map/suggestions.ts`, `tests/mockups/suggestions.test.ts` | N1 (for S9), lending file | H-4, H-5, H-6, H-10 |
| N7. Card section "Things to consider" and "What other partners see" | `TractCard.tsx` | N6, N2 | H-3, H-7 |
| N8. Wording tests: no REQ-16 phrases; no F-3 alignment phrases; no order words in suggestions; REQ-3 sentence present whenever `sitesInTract = 0` | `tests/mockups/wording.test.ts` | N4, N6 | candidate requirements (a) and (b) |
| N9. Reading-level check for text outside `.how-we-know` (optional) | `scripts/check-reading-level.mjs` | T9 copy | none |

Order: N1 and N2 can start at once. N4 and N6 follow, then N3, N5 and N7. N8 runs last against all text.
