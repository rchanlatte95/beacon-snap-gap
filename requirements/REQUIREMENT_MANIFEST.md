# REQ-2026-001: Beacon SNAP-cliff planner map (SLICE-1, SLICE-3 to SLICE-5, cycle 13)

## CCABDD Governance

Human owns: intent (front) + reality judgment (back).
AI owns: enforcement (middle).
Neither crosses the boundary.

The human confirms that the real-world effect matches intent.
AI MAY NOT infer success from metrics.

**INV-3**: No discretion. No judgment. Only state.
A contract executes only when all of its predicates evaluate to TRUE.

---

## Actors

| Actor | Role |
|:------|:-----|
| Planner | Food bank planner who decides where to send food and mobile pantries |
| Officer | SBDC, CDFI or SBA program officer who decides where to target small-business lending and technical assistance outreach |
| Viewer | Anyone who opens the app, including judges and teammates, with no account |
| App | The static web application served from Cloud Run |
| Build | The offline data-preparation script that turns repo data files into the app's static data |
| Ingest | The offline script that loads every retained source file into the warehouse (SLICE-3) |
| QueryService | The private service that answers questions over the warehouse and calls Vertex AI (SLICE-4) |
| Gateway | The public nginx front door that checks the login and forwards requests (SLICE-5) |
| Operator | The human who deploys, configures and removes the services (Ketema) |

## 1. Intent Traceability
- **Source Prose**:
  > "We accept the recommended high impact need idea. enter req-elicit and follow all steps. we want to build an interactive web app in alignment with the track brief. use all context as initial requirements. (ideas 1,2,4 in combination) the application must have ui views for each of the main user types: food bank planner, SBDC or CDFI Program officer."
  >
  > "Two full views (option B ) is good for the first pass. PONYTAIL rules apply"
  >
  > "good enough to start so we can SEE what this looks and feels like. we will iterate from there. remember ccabdd-elegance."
  >
  > "for hosting just use my cloud run account. I accept the rest."
  >
  > "my take away is that the app needs to help bring together different entities like the sba and snap program managers that target the same low income population and use their data to highlight things they might have missed. OPPORTUNITIES TO SERVE. ... we need a 'wizard' and AI powered UI that help showcase those insights. ... read your analysis and yes now you are getting it. i approve. let's translate this into requirements and update the manifest and contracts via constitutional refactor then move into implmentation red green cycles."
  >
  > Cycle 13, 2026-11-08: "my next area of focus is going to be wiring up the data and the AI. I want to discuss the pros and cons of AI provider options. local? cloud? where do we place the data so it can be queried? do we need an mcp server? the goal is to have the AI be able to answer natural language queries about the data."
  >
  > "i agree with using google vertex. perks to use the sponsor however where do we stick the data in such a way that the model has access to as well as the app has access to it? I agree we need a custom tailored tool, but how to design that over the disparate data sources? it is not just the tract data, it is all the sba data everything in our repo that was provided and that we downloaded. all that should be able to be queried to find relationships. not worried about the risks this will not be up for long and we turn it off after the hackathon. during the time it is up we must have secure authenticated access. the cloud run container can be placed behind an nginx container and the public ingress turned off. then the data is inside on a private network."
  >
  > "1-agreed. what about the large files we put in git lfs? 2- hybrid. 3- i accept your recommendation. 4-no need for authentication or the private network. i rescind this reauirement." Then: "ahh i forgot about the ai component. ok auth is back in, simple username:[omitted] password: [omitted from the repository under CL16]." Then: "B. but we also need ALL the real data, not just slices or derivations. every source needs to be included."
  >
  > "i want nothing fetched at build. gather all data sources you can from our data sources list. ... the app must be able to cite sources so ensure you are recording the data sources origin in the wharehouse." "again everything that can be retrieved get it. do not infer data. it must have a real source."
  >
  > "our bounds should be time in my opinion. yes no duplicates of course. ... what if we limit it to just 2024 and newer?" Then: "we do not need to delete anything we have already retrieved. base geography is exempt from the 2024 rules. those are just maps. use what is the most recent. same with the nri file. whatever we have is fine. yes skip the pre 2024 pulse waves." Then: "c. stay with the brief instructions." Then: "use a gcp bucket."
- **Trace gap**: The idea list that "ideas 1,2,4" refers to is not in the repo. Add it, or record where it is, so that this trace is complete.
- **Our Understanding**: SLICE-1 is the "Opportunities to Serve" cross-agency alignment map and AI-guided action wizard for Central Florida (490 tracts). It brings together Food Bank / SNAP planners and SBA / SBDC / CDFI lending officers around the same low-income population, contrasts food need (97 Classic Food Desert tracts) against SBA 7(a)/504 lending (DS-X5, 50 dual-gap tracts with at or below the regional median of 10 loans), household no-vehicle transportation barriers (DS-X7b, 53 tracts in the top quartile at or above 6.90%, yielding 29 triple-gap tracts), and median household income with 90% margins of error (DS-X28, DS-X29), keeps the legend pinned on the map canvas over clean exterior county borders, and provides a Gap-Zapper-style AI briefing, natural-language query/filter wizard, and one-click Coordinated Action Brief generator. The SNAP-loss slider remains stashed in SLICE-2 (Z-3).
- **Ambiguity Score**: SLICE-1 is 0 (ready for contracts and implementation). SLICE-3 is 0 (its zones are decided). SLICE-4 is 4 (small gaps: Z-7 to Z-11 are open). SLICE-5 is 1 (Z-12 is open). Rationale for SLICE-1: flow, stack, three-persona alignment scope, the high-need rule (Z-1, 97 tracts), the SBA lending contrast rule (DS-X5, 50 dual-gap tracts), the no-vehicle transportation barrier rule (DS-X7b, 53 tracts, 29 triple-gap tracts), median household income and MOE integration (DS-X28, DS-X29), the pantry-coverage load rule (Z-2, Z-2e), the map classes and pinned legend (D-1), the deterministic confidence rule, the AI insight and coordinated action wizard, the Build output path (Z-5), the base map tile source (Z-6, OpenFreeMap Positron vector tiles with REQ-10 fallback) and the deployment target (Z-4) are all decided. Z-3 (slider) is deferred to SLICE-2. 

## Known Ambiguities

- None for SLICE-1 or SLICE-3. Z-3 (slider) is deferred to SLICE-2.
- SLICE-4 has five open zones (Z-7 amendment of INV-06, Z-8 Vertex model, Z-9 loan-level exposure, Z-10 AI outage fallback, Z-11 acceptance questions). SLICE-5 has one (Z-12 shutdown trigger). See section 5.

## 2. The Actor Matrix

| Actor | Permission Level | Prohibited Actions |
|:------|:-----------------|:-------------------|
| Planner | Read the map, switch persona lenses, run the AI wizard, generate a coordinated action brief | Edit source data; see individual people |
| Officer | Same as Planner | Same as Planner |
| Viewer | Same as Planner | Same as Planner |
| App | Read static data files; compute flags in the browser | Call external services at runtime; store user data on a server |
| Build | Read `data/**`; write static app data | Alter files under `data/hackathon/` or `data/external/` |
| Ingest | Read `data/**` and `data/cache/**`; write the warehouse | Fetch data over the network; alter any retained source file |
| QueryService | Read the warehouse; call Vertex AI | Write to the warehouse; return a column the catalog marks private |
| Gateway | Forward authenticated requests to the App and the QueryService | Forward a request that lacks valid credentials |
| Operator | Deploy, configure and remove the services; hold the secrets | Write a secret into a repository file |

## 3. The State Transition
- **Initial State ($S_0$)**: Repo holds hackathon and external data files; no app exists.
- **Transformation**: Build produces static tract data; App renders the map and card.
- **Terminal State ($S_1$)**: A Viewer opens the Cloud Run URL and sees the top KPI cohort strip (97 Classic Food Deserts, 50 Dual-Gap Food + SBA tracts, 53 Mobile-Priority Transport Gap tracts, 29 Triple-Gap Opportunities to Serve, and 2 Insufficient Data tracts), 489 Central Florida tracts drawn on the map with a pinned on-canvas legend and clean exterior county borders, and tract `12095990000` listed as not drawn. The Viewer switches persona lenses (`Food Bank Planner`, `SBA / CDFI Officer`, `Shared Alignment: Opportunities to Serve`), toggles overlays, uses the AI Insight & Coordinated Action Wizard to filter tracts or inspect a tract's evidence (including SBA loans, no-vehicle %, and median household income + 90% MOE), confidence badge and sources, and generates a Coordinated Action Brief.
- **SLICE-3 to SLICE-5 terminal state ($S_1$)**: A Viewer with the shared login opens the Gateway URL and asks a question in plain language about any loaded data (for example SBA lending, food-access flags, SNAP participation or NRI risk for Florida, New York or Utah). The App returns an answer built from the warehouse, with chips that name each source, its publisher, its as-of date and its origin link. A request without the login gets HTTP 401, and a request straight to the App or QueryService address from outside the Gateway fails. The warehouse holds every retained source file dated 2024 or later, plus base geography, and each table traces to its file.

## 3.5 Integration Specification

### Dependency Graph
Build DEPENDS ON the hackathon SNAP (S2201) and poverty (S1701) tables for tract rates.
Build DEPENDS ON the hackathon USDA SRAM file (DS-H6) for the driving-distance LILA flag `DD_SRAM_LILATracts_halfAnd10` (Z-1).
Build DEPENDS ON the Second Harvest site list for pantry locations.
Build DEPENDS ON the Census block file for people-near-a-pantry counts (Z-2 C).
Build DEPENDS ON the tract GeoJSON (`data/external/geography/central_fl_tracts_2020.geojson`, 489 features) for polygons. The FEMA NRI file is a CSV with no geometry.
App DEPENDS ON the Build output for every value it shows.
App DEPENDS ON MapLibre GL JS for drawing the map.
App DEPENDS ON a base map tile source (Z-6), with the REQ-10 fallback.
Cloud Run DEPENDS ON a container image built from the App.

Build DEPENDS ON the SBA 7(a)/504 tract table (`data/external/sba-loans/sba_loans_by_tract_central_fl.csv`, DS-X5) for loan counts, gross dollars and jobs supported per tract.
Build DEPENDS ON the ACS B08201 no-vehicle table (`data/external/census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv`, DS-X7b) for the household no-vehicle rate per tract.
Build DEPENDS ON the ACS S1901/B19013 median household income table (`data/external/census-acs/acs2024_s1901_median_household_income_central_fl_tracts.csv`, DS-X28, DS-X29) for median household income and 90% margins of error per tract.

Ingest DEPENDS ON the files listed in `data/cache/MANIFEST.jsonl` and under `data/hackathon/` and `data/external/` for every table it loads. It reads no other input.
Ingest DEPENDS ON `docs/data-sources.md` for each data source's ID and title.
QueryService DEPENDS ON the warehouse in the private Cloud Storage bucket for every answer.
QueryService DEPENDS ON Vertex AI for the language model.
App DEPENDS ON the QueryService for every AI answer and every query result, and on the Build output for the map (unchanged from SLICE-1).
Gateway DEPENDS ON Google Secret Manager for the login credential.
Gateway DEPENDS ON the App and the QueryService for the content it forwards.

### Control Flow Requirements (Sequencing Specs)
| ID | Caller | Must Invoke | Temporal Constraint | Breaks If Missing |
|----|--------|-------------|---------------------|-------------------|
| SEQ-1 | Build | Join each pantry site to a tract and compute people-near-site counts | BEFORE it writes the static tract file | Map shows no pantry coverage |
| SEQ-2 | Build | Validate every output tract has polygon and rates, or mark it Insufficient | BEFORE it writes the static tract file | A tract silently shows blank values |
| SEQ-3 | App | Load the static tract file | BEFORE it renders the map | Map draws without data |
| SEQ-4 | App | Read the clicked tract's record and its data-limitation list | BEFORE it opens the card | Card shows a flag without its caveats |
| SEQ-5 | Ingest | Write the files, catalog and sources tables | AFTER every table is loaded and BEFORE it reports success | A table exists with no provenance row |
| SEQ-6 | QueryService | Load the warehouse from the bucket | BEFORE it accepts its first request | A request is answered from a partial warehouse |
| SEQ-7 | QueryService | Attach the provenance of each table used | AFTER each tool call and BEFORE the answer text is built | An answer cites no source |
| SEQ-8 | Gateway | Check the login | BEFORE it forwards any request | An unauthenticated request reaches a backend |
| SEQ-9 | App | Show the deterministic notice and use the built-in wizard | AFTER the QueryService reports Vertex AI unavailable and BEFORE the next question | The Viewer sees a blank or stale answer |

### Integration Points Checklist
| ID | Source | Target | Handoff Data | Contract Clause |
|----|--------|--------|-------------|-----------------|
| IP-1 | Hackathon tract tables | Build | SNAP household %, poverty % per tract | pending |
| IP-6 | Hackathon USDA SRAM file | Build | Driving-distance LILA ½ mile / 10 mile flag per tract | pending |
| IP-2 | Pantry site list | Build | Site id, lat/lng, tract id | pending |
| IP-3 | Census block file | Build | Block population and point | pending |
| IP-4 | Build | App | Static tract file (GeoJSON properties) at the Z-5 path | pending |
| IP-5 | App flagging rule | Tract card | Flag, evidence, confidence, limitations | pending |
| IP-7 | SBA tract lending table (DS-X5) | Build | SBA 7(a)/504 loan count, gross dollars and jobs supported per tract | pending |
| IP-8 | ACS B08201 no-vehicle table (DS-X7b) | Build | Household no-vehicle percentage per tract | pending |
| IP-9 | ACS S1901/B19013 median household income table (DS-X28, DS-X29) | Build | Median household income, 90% margin of error and income status per tract | pending |
| IP-10 | Retained source files and `MANIFEST.jsonl` | Ingest | File bytes, origin URL, retrieval time, SHA-256 | pending |
| IP-11 | Ingest | Warehouse in the bucket | Parquet tables plus the files, catalog, sources, columns and documents tables | pending |
| IP-12 | Warehouse in the bucket | QueryService | Tables read at start | pending |
| IP-13 | QueryService | Vertex AI | Tool calls and tool results | pending |
| IP-14 | QueryService | App | Answer text, result rows, provenance records | pending |
| IP-15 | Gateway | App and QueryService | Authenticated requests | pending |

### Lifecycle Paths
| Component | INIT (created/started by) | CLEANUP (stopped/released by) |
|-----------|--------------------------|-------------------------------|
| Build | Run by a developer or CI before the image build | Exits when files are written; leaves no state |
| App | Browser loads page from Cloud Run | Browser tab close; the App keeps no state |
| Cloud Run service | Deployed by the human's account | Removed by the human; the app has no teardown |
| Ingest | Run by a developer before the warehouse upload | Exits when the tables are written; leaves no state beyond the warehouse |
| QueryService | Cloud Run starts it and it loads the warehouse (SEQ-6) | Operator removes the service after the hackathon |
| Gateway | Cloud Run starts it with the secret mounted | Operator removes the service after the hackathon |
| Bucket | Operator creates it and uploads the warehouse | Operator removes access grants and the bucket after the hackathon |

## 4. Hard Invariants (The "Never" List)

| ID | Category | Invariant | Verification | Priority | Rationale |
|----|----------|-----------|--------------|----------|-----------|
| INV-01 | Data integrity | REQ-1: The Build shall not alter any file under `data/hackathon/` or `data/external/`. | test | Must | Source data is the evidence base; edits would break citations |
| INV-03 | Honesty | REQ-3: When a tract has no Second Harvest site inside it (Z-2 A), or none of its block population is within 30 minutes' drive of a site (Z-2 C), the App shall show the text "No Second Harvest site found under this rule. Other food sources may exist." on that tract's card. | test | Must | The site list is one food bank's network only, and the coverage rule (inside-tract count or 30 minutes' drive) is an approximation |
| INV-11 | Honesty | REQ-16: The App shall not show the phrases "no food access" or "no access" for any tract, anywhere in the App. | test | Must | The site list is one food bank's network only; no site found is not proof of no access |
| INV-04 | Privacy | REQ-4: The App shall hold only tract-level data: no record about an individual person, no block-level record, and block values only as tract sums. | test | Must | Data is tract and block aggregates only. Block population has differential-privacy noise, so a single block value is not valid |
| INV-12 | Privacy | REQ-17: The Build shall write only tract-level fields to the static tract file. | test | Must | The file is served publicly, so a block-level field in it would be published even if the App ignored it |
| INV-05 | Honesty | REQ-5: The App shall not omit a missing or blank indicator from the tract card. | test | Must | Florida CDC values are blank; hiding that misleads |
| INV-06 | Scope | REQ-6: The App shall not call an external service at runtime, except map tile servers. | test | Should | Keeps the prototype static and cheap to host |
| INV-07 | Attribution | REQ-12: The App shall show, on every view, a credit to DataKind and Beacon with a link to www.datakind.org and the statement that Beacon content is CC BY 4.0. | test | Must | Beacon's license page requires CC BY 4.0 attribution to DataKind with a link to www.datakind.org (`docs/hackathon/linked-pages.md`, "Beacon license") |
| INV-08 | Brand | REQ-13: The App shall follow `docs/hackathon/resources/beacon-design-brand-guidelines.pdf`. | human review | Must | Decided by Ketema, 2026-11-07 ("we follow the branding"): the team follows the Beacon brand guidelines that DataKind provided. Compliance needs a person to judge it |
| INV-09 | Display | REQ-14: The App shall color each drawn tract (489 of 490) on the map as Classic Food Desert (high need), No gap flagged, or Insufficient data. | test | Must | Two of the three names are the brief's own; "No gap flagged" was proposed by Ryan's agent. The three classes cover all 490 tracts (97, 391 and 2), but tract `12095990000` (water) has no polygon, so it is listed as Insufficient data and not drawn |
| INV-10 | Display | REQ-15: The App shall show a legend pinned on the map canvas that names each map class and its color and remains visible when side panels scroll. | test | Must | Visual inspection of PR #11 showed the sidebar legend scrolled off screen |
| INV-13 | Alignment | REQ-18: The App shall provide three selectable persona lenses (Food Bank Planner, SBA / CDFI Officer, and Shared Alignment: Opportunities to Serve) and top KPI cohort cards that filter the map to the selected cohort. | test | Must | Sponsor feedback and Ketema's directive: program managers cannot decide in a silo and need a shared alignment driver |
| INV-14 | Lending contrast | REQ-19: The Build shall join SBA 7(a) and 504 lending per tract (DS-X5) and flag the 50 dual-gap tracts that are Classic Food Deserts with SBA loan counts at or below the regional median of 10 loans. | test | Must | Sponsor feedback: population needing food aligns with population needing SBA lending |
| INV-15 | Transport gap | REQ-20: The Build shall join the household no-vehicle rate per tract (DS-X7b), flag the 53 high-food-need tracts at or above the inclusive 75th-percentile no-vehicle threshold of 6.90% and the 29 triple-gap tracts, and recommend mobile pantry deployment for every tract that meets that threshold. | test | Must | Sponsor feedback: highlight the transportation gap for resource deployment |
| INV-16 | Action wizard | REQ-21: The App shall provide an AI Insight and Coordinated Action Wizard with an executive briefing, natural-language query or prompt-chip cohort filtering, and a one-click Coordinated Action Brief generator that outputs a cross-agency intervention plan with counterfactual impact. | test | Must | Ketema's directive from Gap Zapper analysis: AI-led insight-driven action taking |
| INV-17 | Confidence | REQ-22: The App shall show each tract's deterministic confidence level (Not rated when class is Insufficient data, Lower when households are under 500 or group-quarters share exceeds 20%, and Moderate otherwise), median household income with its 90% margin of error (DS-X28), and source IDs on the tract card. | test | Must | Sponsor feedback: surface sources, margins of error and confidence levels |
| INV-18 | Map clarity | REQ-23: The Build shall emit only exterior county boundary segments with no interior water-sliver or unshared tract edges inside a county. | test | Must | Visual inspection of PR #11 showed interior unshared edges drew confusing blue lines across counties |
| INV-19 | Map clarity | REQ-24: The App shall render tract fills at overview zoom without overlapping coverage circles obscuring the choropleth. | test | Must | Visual inspection of PR #11 showed 97 dark circles piled over urban Orange County tracts |
| INV-20 | Data scope | REQ-25: The Ingest shall load into a table every file under `data/cache/`, `data/hackathon/` and `data/external/` whose reference period reaches 2024-01-01 or later, and every base-geography file whatever its date. | test | Must | Ketema, 2026-11-08: limit to 2024 and newer; base geography is exempt because it is only maps |
| INV-21 | Data scope | REQ-26: The Ingest shall exclude a retained file only for time scope, for a byte-identical duplicate by SHA-256, or for a duplicate format of the same release. | test | Must | Ketema, 2026-11-08: no duplicates; nothing deleted. Excluded files stay on disk and in the file list |
| INV-22 | Data scope | REQ-27: The Ingest shall keep only the rows for Florida, New York and Utah from a source that has a state field. | test | Must | Ketema, 2026-11-08: "stay with the brief instructions" (the brief offers Central Florida, NYC and Salt Lake City) |
| INV-23 | Data integrity | REQ-28: The Ingest shall not read data over the network. | test | Must | Ketema, 2026-11-08: nothing fetched at build |
| INV-24 | Data integrity | REQ-29: The Ingest shall not alter any retained source file. | test | Must | REQ-1 covers `data/hackathon/` and `data/external/`; this adds `data/cache/` |
| INV-25 | Provenance | REQ-30: The Ingest shall record for every source file its data source ID, origin URL, retrieval method, retrieval time, SHA-256, publisher, license text and as-of date. | test | Must | Ketema, 2026-11-08: the app has to cite sources, so the warehouse records each source's origin |
| INV-26 | Provenance | REQ-31: The Ingest shall record a provenance field that it cannot read from the file, the manifest or the data sources document as "not recorded". | test | Must | Ketema, 2026-11-08: do not infer data; it needs a real source |
| INV-27 | Storage | REQ-32: The Operator shall keep the canonical warehouse in a private Google Cloud Storage bucket in project `<gcp-project>`. | tool | Must | Ketema, 2026-11-08: "use a gcp bucket" |
| INV-28 | Citation | REQ-33: The QueryService shall return with every answer the data source ID, origin URL, publisher, as-of date and applied filter of each table the answer used. | test | Must | Ketema, 2026-11-08: the app has to cite sources |
| INV-29 | Query safety | REQ-34: The QueryService shall run only read-only SELECT statements. | test | Must | The model writes the SQL, so the service enforces read-only access |
| INV-30 | Catalog | REQ-35: The QueryService shall provide a catalog tool that lists every loaded dataset and describes each dataset's columns, grain, join keys, as-of date and known caveats. | test | Must | The sources have different grains (block, tract, county, site point, month); the catalog is what lets a join be correct |
| INV-31 | Query tools | REQ-36: The QueryService shall provide a spatial lookup of the sites within a distance of a tract or point, and a correlation tool that returns the sample size, the coefficient, the method and the caveats. | test | Must | Ketema, 2026-11-08: the data has to be queried to find relationships; the tool computes the statistic so the model does not estimate it |
| INV-32 | Honesty | REQ-37: The QueryService shall build every number in an answer from a tool result. | execution | Must | A language model can invent a number; a live comparison of answers with a recomputation checks it |
| INV-33 | Privacy | REQ-38: The QueryService shall not return a column that the catalog marks private, including borrower names and borrower addresses. | test | Must | SBA loan files list borrower names and addresses; FORBIDDEN-PRIV-1 already keeps them out of the Build output |
| INV-34 | Scope | REQ-39: The QueryService shall call no external service except Vertex AI, using the service's own identity and holding no key in the browser. | test | Must | Ketema, 2026-11-08: Vertex AI is the provider, for the sponsor perks |
| INV-35 | Fallback | REQ-40: When Vertex AI is unavailable or exceeds its time limit, the App shall use the built-in deterministic wizard and show the notice "AI unavailable. Using built-in filters." | test | Should | Proposed by the agent (CL9-D fallback with an explicit trigger and notice); open as Z-10 |
| INV-36 | Citation | REQ-41: The App shall show beside every AI answer a chip for each cited data source with its ID, publisher, as-of date and a link to its origin URL. | test | Must | Ketema, 2026-11-08: the app has to cite sources |
| INV-37 | Access | REQ-42: The Gateway shall require HTTP basic authentication for every request to the App and the QueryService. | test | Must | Ketema, 2026-11-08: authenticated access while the services are up; username [omitted] |
| INV-38 | Secrets | REQ-43: The Operator shall keep the Gateway password only in Google Secret Manager and never in a repository file, an image layer or a log. | tool | Must | CL16; the password was given in chat and stays out of the repository |
| INV-39 | Access | REQ-44: The Operator shall set ingress to internal-only for the App and the QueryService, so that a request to either service's own address from outside the Gateway fails. | execution | Must | Ketema, 2026-11-08: option B, login plus a private network |
| INV-40 | Lifecycle | REQ-45: The Operator shall remove the Gateway, the QueryService, the App and the bucket's access grants after the hackathon ends. | tool | Should | Ketema, 2026-11-08: it comes down after the hackathon; the trigger is open as Z-12 |
| INV-41 | Data scope | REQ-46: The Ingest shall list every excluded file with its reason. | test | Must | Ketema, 2026-11-08: nothing is deleted, so exclusions must be visible |
| INV-42 | Data scope | REQ-47: The Ingest shall keep every row of a source that has no state field. | test | Must | A source without a state field cannot be filtered without guessing |
| INV-43 | Data scope | REQ-48: The Ingest shall record the rows in the source and the rows loaded for each table. | test | Must | A reader can check the filter against a recount |
| INV-44 | Provenance | REQ-49: The Ingest shall record for every table the file it came from and the filter applied. | test | Must | Ketema, 2026-11-08: the app cites sources down to the file |
| INV-45 | Provenance | REQ-50: The Ingest shall not infer a provenance field. | test | Must | Ketema, 2026-11-08: do not infer data; it needs a real source |
| INV-46 | Query safety | REQ-51: The QueryService shall apply a row limit and a time limit to every query. | test | Must | Keeps a model-written query from exhausting the service |
| INV-47 | Query safety | REQ-52: The QueryService shall reject any statement that is not a read-only SELECT with an error that names the rule broken. | test | Must | The caller learns which rule failed |
| INV-48 | Honesty | REQ-53: The QueryService shall not state a number that no tool returned. | execution | Must | A language model can invent a number; a live comparison with a recomputation checks it |
| INV-49 | Access | REQ-54: The Gateway shall answer a request without valid credentials with HTTP 401. | test | Must | Ketema, 2026-11-08: authenticated access while the services are up |

When the slider slice starts, the App shall carry INV-02 (REQ-2, the "assumption-based estimate" label). See "Deferred items" in section 5.

**Pending amendment (Z-7).** INV-06 (REQ-6) and the App row of the Actor Matrix say the App calls no external service at runtime. SLICE-3 to SLICE-5 add a same-origin query API and a login. The text of INV-06 and the Viewer definition ("no account") stay as written until the human decides Z-7. This is not a thin amendment under QS6, because it changes an approved requirement.

## 5. High-Entropy Zones (Adjudicated)
| Zone | Question | Resolution | Decided By |
|------|----------|------------|------------|
| Stack | Which technologies? | React, Vite, TypeScript 7, MapLibre, static data, Vitest, no AI first. The compiler is TypeScript 7 (PR #8); `typescript-eslint` runs on the TypeScript 6 legacy API side by side until it supports 7 | User (CL4) |
| Hosting | Where does it run? | User's Google Cloud Run account | User (CL4) |
| Scope | Which views first? | **Three persona lenses in SLICE-1**: Food Bank Planner, SBA / CDFI Officer, and Shared Alignment ("Opportunities to Serve"), guided by a Gap-Zapper-style AI Insight and Coordinated Action Wizard | Ketema (CL4), 2026-11-07 |
| **Z-1** | What makes a tract "high need"? | **Option B with driving-distance LILA**: poverty rate at or above the 75th percentile of the 488 Central Florida tracts that have a poverty value (ACS 2024), AND the USDA driving-distance LILA flag (`DD_SRAM_LILATracts_halfAnd10`: 1/2 mile urban, 10 miles rural). This flags 97 tracts. Straight-line (Euclidean) LILA, 68 tracts, was considered. The contract names the quantile method (see note below) | B proposed by Ryan, confirmed by Ketema; driving distance decided by Ketema and Ryan (CL4), 2026-11-07 |
| **Z-2** | What counts as a "nearby pantry"? | **Option C shown beside A**: the share of the tract's block population within 30 minutes' drive of a Second Harvest site (drive time chosen over straight-line miles; N = 30 may change later), shown beside whether a site lies inside the tract. Block population is for April 2020 and has differential-privacy noise, so the Build uses only tract sums | Ryan proposed 2026-11-07 (issue #4); Ketema confirmed (CL4) |
| **Z-2b** | Is "nearby" in Z-2 C straight-line miles or drive time? | **Drive time.** Ketema first leaned to miles, then retracted it and accepted drive time | Ketema and Ryan (CL4), 2026-11-07 |
| **Z-2d** | How many minutes count as "nearby"? | **N = 30 minutes**, standard mid-day traffic (Wednesday 12:00). A 15-minute test also puts all 97 high-need tracts in reach; only 5 to 10 minutes separates them (55 and 90 of 97). N may change later | Ketema suggested; Ryan accepted (CL4), 2026-11-07 |
| **D-1** | What does the SLICE-1 map show? | **Three classes** in the brief's vocabulary: Classic Food Desert (high need by Z-1, 97 tracts), No gap flagged (391 tracts), Insufficient data (2 tracts: `12095016515` with no households and `12095990000`, water). Pantry coverage is a separate layer on the high-need tracts, not part of the class. Ketema left the label wording to the agent as non-consequential | Ketema and Ryan (CL4), 2026-11-07 |
| **D-2** | Keep the early merge of PR #5? | **Keep it and fix forward** | Ketema and Ryan (CL4), 2026-11-07 |
| **Z-2e** | What does the coverage layer tell a planner? | **Option A, load**: residents per pantry site within reach, for each high-need tract. Ketema chose it (reply "4 - a") and confirmed that reading; Ryan accepted ("Z-2e option A is fine") | Ketema and Ryan (CL4), 2026-11-07 |
| **Z-3** | What does the slider change? | **Deferred** until mock-ups or proofs of concept are rendered; Ryan's option A is kept as input for that step | Ketema and Ryan (CL4), 2026-11-07 |
| **Z-4** | Which Cloud Run project and region? | **Project `<gcp-project>`, region `us-east1`.** Cloud Run, Artifact Registry and Cloud Build APIs are enabled and the human's account is owner | Ketema (CL4), 2026-11-07 |
| **Z-5** | Where does the Build write the static tract file? | **`public/data/tracts.geojson`**, the standard Vite static directory. The Vite bundle goes to the standard `dist/`. Both paths are generated and listed in `.gitignore`, so neither is committed. Builds and test suites run in tmux offload | Ketema (CL4), 2026-11-07 |
| **Z-6** | Which base map tile source does the App use? | **OpenFreeMap Positron vector tiles** (`https://tiles.openfreemap.org/styles/positron`), free and keyless, with the REQ-10 blank-background fallback and "Base map unavailable" banner when tiles fail to load | Ketema (CL4), 2026-11-07 |
| **Z-7** | Does INV-06 (REQ-6) change to let the App call its own same-origin query API? | **Unresolved.** A) amend INV-06 so that the App calls only its own same-origin query API and map tile servers, and the QueryService calls only Vertex AI (recommended). B) keep INV-06 as written and run the AI in the browser (weaker answers, large downloads). Also decide the Viewer definition: today "no account", now a shared login | pending (CL4) |
| **Z-8** | Which Vertex AI model and region? | **Unresolved.** The model identifier and its availability in `us-east1` are checked against the Vertex AI documentation before the contract. Recommendation: the current Gemini Flash-class model for cost and speed, with the model name set in configuration | pending (CL4) |
| **Z-9** | May the QueryService return individual SBA loan rows? | **Unresolved.** A) aggregates and counts only. B) loan rows with borrower name and address removed (recommended: relationships such as lender or loan size by tract need the rows). C) full rows. Borrower names and addresses stay private in A and B | pending (CL4) |
| **Z-10** | What happens when Vertex AI is down? | **Unresolved.** A) fall back to the built-in deterministic wizard with the notice in REQ-40 (recommended). B) fail with an error and no fallback | pending (CL4) |
| **Z-11** | Which example questions define "answers natural-language questions about the data"? | **Unresolved.** The Completion Promise for SLICE-4 needs five to eight questions with a recomputed answer for each. The agent proposes them and the human edits | pending (CL4) |
| **Z-12** | When is the shutdown, and who triggers it? | **Unresolved.** Options: the human triggers it on a stated date, or a scheduled job removes the services on that date. Blocks only REQ-45 | pending (CL4) |
| **Z-13** | How are the services protected? | **Decided.** HTTP basic authentication at an nginx Gateway (username [omitted], password in Secret Manager, never in the repository), with the App and the QueryService on internal-only ingress. No other protection is added | Ketema (CL4), 2026-11-08 |
| **Z-14** | Where does the canonical warehouse live, and how do the App and model both reach it? | **Decided.** A private Google Cloud Storage bucket in `<gcp-project>`. The QueryService loads the warehouse at start. New App features read through the QueryService; the static tract file stays for the map | Ketema (CL4), 2026-11-08 |
| **Z-15** | What data does the warehouse hold? | **Decided.** Every retained source file with a reference period of 2024 or later, plus base geography (any date, the most recent), Florida, New York and Utah rows where a source has a state field, nothing fetched at build, nothing deleted, no duplicates. Retrieved files outside the scope stay on disk and are listed with their reason | Ketema (CL4), 2026-11-08 |
| **Z-16** | Which model provider and query design? | **Decided.** Vertex AI (Gemini) with a hybrid tool set: a catalog, read-only SQL and a few typed tools. The model never states a number the tools did not return | Ketema (CL4), 2026-11-08 |
| **Z-17** | Does SLICE-4 include an MCP server? | **Unresolved, deferred.** Recommendation: not in SLICE-4; wrap the same tools in MCP later if there is time. Blocks nothing | pending (CL4) |

**Note on the Z-1 poverty cut.** The cycle 1 review gave 17.1% and cycle 3 gave 17.0%. Both are roundings of the same 75th percentile, computed two ways with Python `statistics.quantiles(n=4)` over the 488 tracts that have a poverty value: exclusive method 17.075%, inclusive method 17.025%. Both cuts give the same 97 tracts (driving-distance LILA) and 68 tracts (straight-line LILA). The only tract between the rounded and the computed cuts is `12069031107` (poverty 17.0%), and it has no LILA flag, so a literal "17.0% or more" rule also gives 97. Do not encode a rounded value. The contract computes the cut and names the method.

### Options and recommendations (inputs, not decisions)

Counts below come from `data/external/second-harvest-food-finder/central_fl_tract_pantry_coverage.csv` (490 tracts; 2 have blank rates), the hackathon USDA SRAM file (DS-H6; all 490 tracts join) and the ACS B08201 file. "LILA" is the ½ mile urban / 10 mile rural low-income and low-access flag. SD is the straight-line distance version and DD is the driving distance version. "No site" means no Second Harvest site inside the tract (Z-2 A).

- **Z-1 high need (decided: B with DD).** Options kept for the record:
  - A) SNAP households 20% or more OR poverty 20% or more: 141 tracts, 76 with no site. Does not use LILA.
  - B) The brief's "Classic Food Desert" rule, top-quartile poverty AND LILA: SD 68 tracts (40 with no site), DD 97 tracts (52 with no site). Chosen, with DD.
  - C) A weighted score.
  - D) A AND LILA: SD 80 tracts (48 with no site), DD 111 tracts (58 with no site).
  - E) Top-quartile poverty AND (LILA OR top-quartile no-vehicle share, cut 6.9%): SD 109 tracts (59 with no site), DD 113 tracts (61 with no site). The card would have to label no-vehicle share a proxy: it correlates about 0.52 with SNAP share and is not a validated substitute (F-1). E can be a second mode in a later slice.
- **Z-2 nearby (decided: C beside A).** A) A Second Harvest site inside the tract. B) At least one site within 1 mile of the tract's center. C) The share of the tract's block population within 1 mile of a site.
- **Z-2b distance type.** Straight-line distance from each populated 2020 block point to the nearest site needs no routing service. Road distance needs a routing engine at Build time (see "Deferred map alternatives"). No recommendation.
- **Z-3 slider (deferred).** Let s be the scenario value: extra SNAP loss as a percent of current SNAP households. Let "displaced households" for a tract be `snap_households × s / 100`. This is an assumption-based estimate (REQ-2), because no tract-level SNAP-cut data exists (DS-X1 and DS-X2 are not downloaded). The human found the slider confusing and asked to see the first deliverable before deciding; a visual mock accompanies the question when it returns.
  - A) s raises each tract's displaced households proportionally. Ryan's input for the later slice.
  - B) Same, scaled by tract-level risk (poverty).
  - C) A county total spread by SNAP share.
  - D) The slider moves the Z-1 need threshold instead of SNAP loss. This is a threshold sensitivity test, which the brief suggests for Challenge 1 (`docs/hackathon/beacon-appendices.md:56`). It is not a SNAP-cut scenario.
  - **Constraint for the later slice.** Z-1 B uses only rates. Z-3 A, B and C multiply every tract by the same factor or by a fixed tract weight. If the flag rule uses only rates, the slider changes no flags. When the slider returns, a human decides whether the flag rule takes the scenario value, for example F) flag a tract when it meets Z-1 AND it has no nearby site under Z-2 AND its displaced households are N or more (N is a human decision).
- **Z-5 Build output path (decided).** `public/data/tracts.geojson`. The taxonomy classes `public/**` as production code, Vite serves it as a static file, and the INV-01 test can check that the Build writes only under `public/data/`.
- **Z-6 base map tiles.** Candidates are in "Deferred map alternatives" below: OpenFreeMap (hosted, no key), a Protomaps PMTiles file served from the same container, or `tile.openstreetmap.org` (local demo only). No recommendation.

### Deferred items (stashed with Z-3; written as obligations when the slider slice starts)
- REQ-2 (deferred): every scenario result carries the label "assumption-based estimate", because no per-tract SNAP loss data exists.
- REQ-11 (deferred): an out-of-range slider value is clamped to the range and the clamped value is shown.
- SEQ-S (deferred): flags are recomputed after each slider change and before the next paint, so the slider and map agree.

## 5.5 Rejected Alternatives
| Decision | Alternative Considered | Why Rejected |
|----------|----------------------|--------------|
| Static data in the repo | A backend with a database | Adds infrastructure and a security surface for no first-pass benefit |
| Rule-based "why flagged" | An LLM-written explanation | Cannot be verified; adds a runtime dependency |
| Cloud Run | GitHub Pages | User chose Cloud Run |

### Deferred map alternatives (not decisions; test later if needed)

These are candidates for each mapping job. They are not chosen and not rejected. Test a row only when its trigger occurs. "Runs in" tells where the tool would run. Any App-side row that calls a service at runtime is checked against INV-06 before use. Usage limits and terms in this table are from memory and are not verified; confirm them on the provider's site before a test.

| Job | Current plan | Alternative | Runs in | INV-06 fit | Trigger to test it | Test to run |
|-----|-------------|-------------|---------|------------|--------------------|-------------|
| Map library | MapLibre GL JS | Leaflet | App | Yes (library is bundled) | MapLibre WebGL fails on a target device, or the team needs a simpler API | Render the 489 tract polygons and the tract card; compare load time and bundle size |
| Map library | MapLibre GL JS | Google Maps JavaScript API | App | Partial: tiles only. Places, Routes and Geocoding calls would break INV-06 | A stakeholder requires Google base maps | Confirm API key, billing and Places storage terms first. The key is visible in a static app |
| Base map tiles | Z-6 (unresolved) | OpenFreeMap (hosted OSM vector tiles, no key) | App | Yes (tile server) | Choose a tile source for REQ-10 | Load tiles; block the tile host and confirm "Base map unavailable" (REQ-10) |
| Base map tiles | Z-6 (unresolved) | Protomaps PMTiles file served from the same Cloud Run container | App | Yes (no external service at all) | Tile host limits, outages or an offline demo | Serve one PMTiles file for the 4 counties; check file size and container size |
| Base map tiles | Z-6 (unresolved) | `tile.openstreetmap.org` raster tiles | App | Yes (tile server) | Quick local demo only. The OSM tile usage policy forbids heavy use | Local smoke test only; not for the deployed URL |
| Geocoding (address to tract) | Census Bureau Geocoder, already used for the 424 Second Harvest sites (DS-X27) | Nominatim (OSM geocoder; public server about 1 request per second) | Build | Yes (Build only) | A new pantry list without tract IDs, for example DS-X13 | Geocode the 424 Second Harvest addresses; compare tract IDs with the DS-X27 results |
| Point-to-tract join | Census Geocoder tract IDs | geopandas (Python) or turf.js (TypeScript) point-in-polygon with the 2020 tract GeoJSON | Build | Yes | Join SNAP retailers (DS-H8) or other points without a geocoder call | Join the 424 sites by polygon; expected: the same tract IDs as DS-X27 |
| Distance to pantry | Z-2b (unresolved); straight-line distance from each populated 2020 block point to the nearest site is the option that needs no routing service | OpenRouteService API (driving and walking matrix, isochrones; free key) | Build | Yes (Build only; a runtime call breaks INV-06) | Z-2b chooses road distance, or planners say straight-line distance misleads, for example across lakes or highways | Compare straight-line and road distance for the 97 Z-1 tracts; report the tracts whose flag changes |
| Distance to pantry | Same | OSRM, Valhalla or GraphHopper on a Florida OSM extract (self-hosted) | Build | Yes | Same trigger, and ORS limits are too low | Same comparison as the row above |
| Transit time | None (no transit data in the repo) | r5py or OpenTripPlanner with OSM streets and a LYNX GTFS feed (feed not yet confirmed) | Build | Yes | A human decides whether the plan reaches the 50,303 households with no vehicle (USDA `TractHUNV`, DS-H6) | Confirm that a LYNX GTFS feed exists; compute transit time from block points to sites for one county first |
| Pantry and food-store points | Second Harvest partner sites (DS-X12) and SNAP retailers (DS-H8) | OSM via Overpass API (`amenity=food_bank`, `social_facility=food_bank`) | Build | Yes | Look for pantries that are not Second Harvest partners (data blind-spot map) | List OSM pantries in the 4 counties that are farther than 0.25 mi from every DS-X12 site |
| Pantry and food-store points | Same | Overture Maps Places | Build | Yes | Same trigger, or OSM coverage is too thin | Same test as the row above; record the license terms |

## 6. Tool/API Interface Summary
| Interface | Purpose | Mutates State? | Called By | Triggered When |
|-----------|---------|----------------|----------|---------------|
| build-tract-data | Produce the static tract file | YES (writes app data only) | Build | A developer or CI runs it |
| loadTractData | Load the static file | NO | App | Page load |
| computeFlags() | Flag high-need tracts without nearby pantries | NO | App | Page load |
| buildTractCard(tractId) | Evidence, confidence, limitations | NO | App | Tract click |
| ingest-warehouse | Load retained files into the warehouse tables | YES (writes the warehouse only) | Ingest | A developer runs it |
| catalog.list and catalog.describe | List and describe datasets | NO | QueryService | A model tool call |
| sql.query | Run a read-only SELECT | NO | QueryService | A model tool call |
| sites.near | Find sites within a distance | NO | QueryService | A model tool call |
| stats.correlate | Compute a correlation with sample size and caveats | NO | QueryService | A model tool call |
| ask | Answer a plain-language question with citations | NO | App | The Viewer submits a question |

## 6.5 Blocking Dependencies
| Unresolved Zone | Blocks |
|-----------------|--------|
| Z-1 | Decided; the flagging contract defines the 97-tract rule and names its quantile method |
| Z-2 | Decided; the contract for pantry coverage defines the travel-time threshold |
| Z-2b | Decided (drive time); the contract for pantry coverage defines the routing source and departure time |
| Z-3 | Deferred; blocks only the later slider slice |
| Z-4 | Decided (`<gcp-project>`, `us-east1`); deployment can proceed after the human approves a deploy |
| Z-5 | Decided (`public/data/tracts.geojson`); contract clause for IP-4, Build, INV-01 test |
| Z-6 | Decided (OpenFreeMap Positron vector tiles with REQ-10 fallback); blocks nothing |
| Second Harvest and Feeding America redistribution | Decided by the human in cycle 6: no permission request is needed, because the data was already public. Blocks nothing |
| Z-7 | The App and QueryService contracts that carry REQ-39 to REQ-41, and any change to INV-06 |
| Z-8 | The contract for REQ-39 (model identifier, region) |
| Z-9 | Contracts for REQ-33 and REQ-38 (what a result row may contain) |
| Z-10 | The contract for REQ-40 |
| Z-11 | The SLICE-4 Completion Promise and its execution tests |
| Z-12 | The contract for REQ-45 only |
| Z-17 | Nothing |

## 7. Failure Mode Specification (CL9)

| Requirement | Failure Condition | Behavior | Notification |
|------------|-------------------|----------|-------------|
| REQ-7 | Static tract file is missing or fails to parse | Halt: the App draws no map | The App shall show an error naming the file |
| REQ-8 | A tract has a missing indicator | Show the tract as Insufficient data, not as low need | Card names the missing indicator |
| REQ-9 | Build input file is missing or has changed columns | Halt: the Build exits non-zero | The Build shall name the file and column |
| REQ-10 | Map tiles fail to load | FALLBACK: draw tracts on a blank background | The App shall display "Base map unavailable" |
| REQ-25 | The Ingest cannot read a file in scope | Halt: the Ingest exits non-zero | The Ingest shall name the file and the reader error |
| REQ-30 | A required provenance field is absent | Record "not recorded" and continue | The files table shows "not recorded" for that field |
| REQ-34 | A statement is not a read-only SELECT, or exceeds a limit | Reject the statement | The QueryService shall return an error naming the rule broken |
| REQ-39 | Vertex AI is unreachable or slow | Pending Z-10 (proposed fallback in REQ-40) | The App shall show the notice in REQ-40 |
| REQ-42 | Credentials are missing or wrong | Reject the request | The Gateway shall answer HTTP 401 |
| REQ-44 | A request reaches a service address directly | The request fails | The service address returns an error and no content |

When the slider slice starts, the App shall carry REQ-11 (slider clamp).

## 8. Completion Promise (Ralph Loop Exit)
> "A Viewer opens the deployed URL, sees 489 tracts drawn and colored by flag status, and sees tract 12095990000 listed as not drawn (no geometry). The flagged set equals a set a test recomputes from the source data. The Viewer opens a card whose evidence matches the source tables for that tract and names every missing indicator. A test that passes while the card omits a missing indicator, or while the flagged set differs from the recomputed set, must fail."

Human acceptance remains with the human: whether the map and card are useful to a food bank planner.

> SLICE-3 (warehouse): "The warehouse files table lists every retained source file with its reason for exclusion or its tables; the row counts of the tables equal a recount of the source files after the state filter; no table lacks a provenance row; the Ingest run with the network disabled produces the same tables. A check that passes while a table has no origin URL, or while a count differs from a recount, must fail."
>
> SLICE-4 (query service and AI): pending Z-11. The Viewer asks the agreed questions and each answer matches a recomputation from the source files and cites the sources it used. A check that passes when an answer states a number that the tools did not return must fail.
>
> SLICE-5 (access): a request without the login gets HTTP 401; a request to a service's own address from outside the Gateway fails; the password appears in no repository file, image layer or log; the Operator removes the services on the shutdown trigger (Z-12).

Human acceptance of SLICE-3 to SLICE-5 remains with the human: whether the answers are useful and trustworthy.

## 9. Contract Authority
**Authoritative Sources**: `contracts/planner_map_contract.py` (Build domain, Python) and `contracts/planner-map.app.contract.ts` (App domain, TypeScript, cross-referenced by clause ID per Idiomatic Per-Ecosystem Distribution)

requirements/REQUIREMENT_MANIFEST.md (this file)
        ↓
plans/planner-map.plan.yml (SLICE-1, drafted after the manifest is linted)
        ↓
contracts/planner_map_contract.py
        ↓
tests/
        ↓
src/

## 10. Revision History
| Date | Author | Change |
|------|--------|--------|
| 2026-11-07 | Ketema, agent | Cycle 1 draft from req-elicit. Zones Z-1 to Z-4 open. |
| 2026-11-07 | Ryan Chanlatte, agent | Cycle 1 review. Corrected tract count (489 drawn), polygon and no-vehicle sources, and the reversed Rejected Alternatives row. Made INV-03 and INV-04 testable. Added INV-07 (attribution), INV-08 (brand), Z-5 (Build output path) and the Second Harvest permission dependency. Added Z-1 options D and E with counts, revised the Z-1 recommendation to B, and added Z-3 option D and combined rule F. Zones Z-1 to Z-5 open. |
| 2026-11-07 | Ryan Chanlatte, agent | Added "Deferred map alternatives" under 5.5: candidate map library, tile, geocoding, routing, transit and point-data tools, each with a trigger and a test. No decision changed. |
| 2026-11-07 | Ketema, agent | Cycle 2: the human stashed the slider (Z-3 deferred) after finding it confusing. Removed from SLICE-1 scope: slider, scenario label (REQ-2), range clamp (REQ-11), the slider sequencing spec and integration point. SEQ and IP numbers renumbered. Ambiguity score 5 to 4. |
| 2026-11-07 | Ketema, agent | Cycle 3: Z-1 option B and Z-2 option C beside A recorded (proposed by Ryan, confirmed by Ketema). Z-3 deferred by both humans. Z-1b LILA distance type remains open. Ambiguity score 4 to 3. |
| 2026-11-07 | Ketema, agent | Cycle 4: Z-1b recorded. The human chose driving-distance LILA (97 tracts). Ambiguity score 3 to 2. Only Z-4 remains open, and it blocks deployment only. |
| 2026-11-07 | Ketema, agent | Cycle 5: Z-4 project recorded as `<gcp-project>` (chosen by the human). Z-4b region remains open and blocks deployment only. |
| 2026-11-07 | Ketema, agent | Cycle 6: Z-4b recorded (`us-east1`, Ketema). Z-1b recorded as decided by Ketema and Ryan. The human decided no permission request is needed for Second Harvest and Feeding America data, which were already public. Ambiguity score 2 to 1. |
| 2026-11-07 | Ryan Chanlatte, agent | Cycle 7: merged the cycle 1 review branch with cycles 2 to 6, which had branched from the cycle 1 draft. Kept every human decision from cycles 2 to 6. Restored from the review: 489 drawn tracts and the "not drawn" note, the tract GeoJSON as polygon source, testable INV-03 and INV-04, INV-07, INV-08, Z-5, the trace gap, the Rejected Alternatives row order and the deferred map alternatives. Recorded the cycle 6 redistribution decision in 6.5 in place of the review's permission dependency. Dropped the stale "Recommend A" text. Removed the no-vehicle table from Build inputs, because Z-1 B does not use it. Added the note on the Z-1 poverty cut (17.075% and 17.025% give the same 97 tracts). Added open zones Z-2b (distance type for the 1 mile test) and Z-6 (base map tiles). Ambiguity score 1 to 2. |
| 2026-11-07 | Ketema, agent | Cycle 8: replaced the CLAUDE.md citations in INV-07 and INV-08 with sources a reader can check. INV-07 cites Beacon's license page. INV-08 records the human's decision (Ketema, "we follow the branding"): Must stays. CLAUDE.md is a local file of Ryan's agent and stays git-ignored (decided by Ketema). |
| 2026-11-07 | Ketema, agent | Cycle 9: fixed the 17 IEEE 29148 lint errors (IP-1c renamed IP-6; REQ-3 and REQ-4 reworded to one SHALL each with the App as actor; passive deferred notes reworded; the blocking table column renamed; SHALL and MUST turned into statements of fact in the decision record and in Deferred map alternatives). Recorded D-1 (three classes), D-2 (keep PR #5), the legend (INV-10, REQ-15), the class requirement (INV-09, REQ-14), Z-2b drive time, Z-2d N = 30 minutes and Z-2e (option A, to confirm). Label wording chosen by the agent at Ketema's direction. |
| 2026-11-07 | Ketema, agent | Cycle 10: applied Ryan's agent's review of cycle 9. REQ-3 split into REQ-3 (card text) and REQ-16 (the two phrases never appear anywhere). Added REQ-17 (the Build writes only tract-level fields to the static file). REQ-14 counts the 489 drawn tracts. Three "fact" rewordings became human decisions or expectations. Recorded Z-5 (`public/data/tracts.geojson`, ignored, builds in tmux offload, Ketema) and Z-2e (Ketema confirmed; Ryan to accept). Ambiguity 1: only Z-6 remains. |
| 2026-11-07 | Ketema, agent | Cycle 11: Z-2e Decided By is now Ketema and Ryan (Ryan accepted on issue #4). Stack row records TypeScript 7 at Ketema's direction; PR #8 moves the scaffolding. |
| 2026-11-07 | Ketema, agent | Cycle 12: constitutional refactor incorporating sponsor feedback, live visual inspection of PR #11, PR #12 median household income data (DS-X28, DS-X29), and Ketema's Gap Zapper directive. Added Actor Officer and requirements REQ-18 (three persona lenses and KPI cohort cards), REQ-19 (SBA lending contrast, DS-X5, 50 dual-gap tracts), REQ-20 (no-vehicle transport gap, DS-X7b, 53 tracts, 29 triple-gap tracts, mobile deployment recommendation), REQ-21 (AI Insight and Coordinated Action Wizard with counterfactual brief generator), REQ-22 (deterministic confidence level, median household income + 90% MOE, and sources), REQ-23 (exterior-only county boundaries), and REQ-24 (unobscured overview choropleth). Recorded Z-6 (OpenFreeMap Positron with REQ-10 fallback). Ambiguity score 1 to 0. |
| 2026-11-08 | Ketema, agent | Cycle 13: wiring the data and the AI. Added actors Ingest, QueryService, Gateway and Operator; requirements REQ-25 to REQ-54 (INV-20 to INV-49; each with one SHALL after the lint) for SLICE-3 (warehouse), SLICE-4 (query service and AI) and SLICE-5 (access); dependencies, SEQ-5 to SEQ-9, IP-10 to IP-15, lifecycle rows, interfaces and failure modes. Recorded decided zones Z-13 to Z-16 (login plus internal ingress; GCS bucket; 2024-or-newer scope with Florida, New York and Utah; Vertex AI with hybrid tools). Open zones Z-7 to Z-12 and Z-17 (Z-7 is a pending amendment of INV-06, not thin under QS6). INV-06 and the SLICE-1 text are unchanged. The password given in chat is not recorded here (CL16). |
