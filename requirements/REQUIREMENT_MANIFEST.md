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
| Viewer | Anyone with the shared login, including judges and teammates |
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
  >
  > Approval with caveats, 2026-11-08: "once authenticated the user shall not have to pass credentials on every request. authentication shall last for the length of the session, cleared on logout only. does not need to be complex. i also only want the warehouse built once and stored in its bucket. the app will just connect to it, not rebuild it repeatedly. i am flagging the fallback requirement as this may affect the ui (and i want to see that if so) but no changes yet i want to see what these requirements produce. approved with my caveats above"
  >
  > Zone answers, 2026-11-08: "3.8-flash. no contest"; "this is public data. i see no reason to restrict at all. the sba data by default in the insight queries we have defined aggregate, but if a sba loan administrator asks a natural language query wanting row level data it should not be restricted. drop the hackathon demo lens. C."; "A." (outage fallback); "i like these. keep them as the baseline. it highlights a few things: the ai will need a taxonomy file that is given on every query or it will hallucinate what 'Food Desert' is. generate a glossary of terms from the brief content, data source legends or meta data to ensure grounding. also recognize that any free form query should be allowed. the ai must have tools that allow free ad hoc queries. so its a tool that returns the warehouse schema"; "yes this is my responsibility. no hard date. mark as such: ketema will handle teardown."; "A" (no MCP server). Direction on form: "requirements are meant to change ... the invariant text must now state what we need to have a well functioning app. we do not restrict or put ourselves in a straight jacket. ponytail rules."
  >
  > Cycle 14 (data adapter), 2026-11-08: "the bucket name is irrelevant, just create it and then record it and ensure it is a reusable reference. if the bucket is ever changed the reference constant needs to be updated." Then: "the technology is irrelevant, but the value of duckdb is plain. do not reinvent in python what already exists. if there was a conflict due to where the data lives you should have surfaced that. the requirement intent was to decouple the data from the image build process. if a gcp bucket cannot be mounted say so. but hard coded local file paths is bad architecture. data access should be abstracted. this is a standard data adapter pattern. re-assess and present cohesive options" Then: "A. implement via constitutional refactor. no shortcuts" Then: "do not get hung up on obvious logic: if a rule say once but was executed in error it is invalid. rebuild if needed. continue"
  >
  > Sync with Ryan's side, 2026-11-08: on the plainer lens labels, "I have seen the updated prototype. i agree". On the forced reduction, "A." On bad bytes in a source file: "A & B neither are 100% correct. the solution is a combination of both. do not let a single row exclude an entire file. allow the placeholders, but log it so that it is surfaced." On who edits these files: "any change to a manifest or plan file must be linted. so that should tell you who has to make changes to those files." On REQ-19: "ryan and i discussed it and agreed on the revision. so yes." On the population floor: "present this question to jev and choose the highest rated answer. give it sensible options to choose from". On the code: "front end code goes to ryan's agent. we need to finish the back end and ai work" and "all ryan's agent needs is the requirements, contracts and tests, it can do the implementation from that for front end."
- **Trace gap**: The idea list that "ideas 1,2,4" refers to is not in the repo. Add it, or record where it is, so that this trace is complete.
- **Our Understanding**: SLICE-1 is the "Opportunities to Serve" cross-agency alignment map and AI-guided action wizard for Central Florida (490 tracts). It brings together Food Bank / SNAP planners and SBA / SBDC / CDFI lending officers around the same low-income population, contrasts food need (97 Classic Food Desert tracts) against SBA 7(a)/504 lending (DS-X5, 26 dual-gap tracts whose SBA loans per 1,000 residents are in the bottom quartile), household no-vehicle transportation barriers (DS-X7b, 53 tracts in the top quartile at or above 6.90%, yielding 12 triple-gap tracts), and median household income with 90% margins of error (DS-X28, DS-X29), keeps the legend pinned on the map canvas over clean exterior county borders, and provides a Gap-Zapper-style AI briefing, natural-language query/filter wizard, and one-click Coordinated Action Brief generator. The SNAP-loss slider remains stashed in SLICE-2 (Z-3).
- **Ambiguity Score**: 0 for SLICE-1 and for SLICE-3 to SLICE-5 (ready for contracts and implementation). Rationale for SLICE-1: flow, stack, three-persona alignment scope, the high-need rule (Z-1, 97 tracts), the SBA lending contrast rule (DS-X5, per capita, 26 dual-gap tracts), the no-vehicle transportation barrier rule (DS-X7b, 53 tracts, 12 triple-gap tracts), median household income and MOE integration (DS-X28, DS-X29), the pantry-coverage load rule (Z-2, Z-2e), the map classes and pinned legend (D-1), the deterministic confidence rule, the AI insight and coordinated action wizard, the Build output path (Z-5), the base map tile source (Z-6, OpenFreeMap Positron vector tiles with REQ-10 fallback) and the deployment target (Z-4) are all decided. Z-3 (slider) is deferred to SLICE-2. 

## Known Ambiguities

- None for SLICE-1 or SLICE-3 to SLICE-5. Z-3 (slider) is deferred to SLICE-2.

## 2. The Actor Matrix

| Actor | Permission Level | Prohibited Actions |
|:------|:-----------------|:-------------------|
| Planner | Read the map, switch persona lenses, run the AI wizard, generate a coordinated action brief | Edit source data; see individual people |
| Officer | Same as Planner | Same as Planner |
| Viewer | Same as Planner | Same as Planner |
| App | Read static data files; compute flags in the browser; ask the QueryService | Call a service other than the project's own query service and map tile servers; store user data on a server |
| Build | Read `data/**`; write static app data | Alter files under `data/hackathon/` or `data/external/` |
| Ingest | Read `data/**` and `data/cache/**`; write the warehouse | Fetch data over the network; alter any retained source file |
| QueryService | Read the warehouse; call Vertex AI | Write to the warehouse; return a column the catalog marks private |
| Gateway | Forward authenticated requests to the App and the QueryService | Forward a request that lacks valid credentials |
| Operator | Deploy, configure and remove the services; hold the secrets | Write a secret into a repository file |

## 3. The State Transition
- **Initial State ($S_0$)**: Repo holds hackathon and external data files; no app exists.
- **Transformation**: Build produces static tract data; App renders the map and card.
- **Terminal State ($S_1$)**: A Viewer opens the Cloud Run URL and sees the top KPI cohort strip (97 Classic Food Deserts, 26 Dual-Gap Food + SBA tracts, 53 Mobile-Priority Transport Gap tracts, 12 Triple-Gap Opportunities to Serve, and 2 Insufficient Data tracts), 489 Central Florida tracts drawn on the map with a pinned on-canvas legend and clean exterior county borders, and tract `12095990000` listed as not drawn. The Viewer switches persona lenses (`Food bank`, `Small business lender`, `Both partners`), toggles overlays, uses the AI Insight & Coordinated Action Wizard to filter tracts or inspect a tract's evidence (including SBA loans, no-vehicle %, and median household income + 90% MOE), confidence badge and sources, and generates a Coordinated Action Brief.
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
Ingest DEPENDS ON the data dictionaries and lookup files it loads for the glossary table.
Ingest DEPENDS ON the data adapter to write the warehouse at the configured warehouse location.
QueryService DEPENDS ON `docs/taxonomy.md` for the core taxonomy it sends with every question.
QueryService DEPENDS ON the data adapter for every answer; the adapter opens the warehouse read-only in DuckDB at one configured warehouse location (the bucket mount in Cloud Run).
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
| SEQ-6 | QueryService | Open the warehouse read-only through the data adapter at the configured warehouse location | BEFORE it accepts its first request | A request is answered with no warehouse behind it |
| SEQ-7 | QueryService | Attach the provenance of each table used | AFTER each tool call and BEFORE the answer text is built | An answer cites no source |
| SEQ-8 | Gateway | Check the login | BEFORE it forwards any request | An unauthenticated request reaches a backend |
| SEQ-9 | App | Show the deterministic notice and use the built-in wizard | AFTER the QueryService reports Vertex AI unavailable and BEFORE the next question | The Viewer sees a blank or stale answer |
| SEQ-10 | QueryService | Attach the core taxonomy to the model request | BEFORE the model's first tool call in a question | The model invents what a term means |

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
| IP-11 | Ingest (data adapter) | Warehouse at the configured warehouse location | Parquet tables plus the files, catalog, sources, columns, documents and glossary tables, with table locations relative to the warehouse location | pending |
| IP-12 | Warehouse at the configured warehouse location (the bucket mount in Cloud Run) | QueryService (data adapter) | Tables opened read-only in DuckDB | pending |
| IP-13 | QueryService | Vertex AI | Tool calls and tool results | pending |
| IP-14 | QueryService | App | Answer text, result rows, provenance records | pending |
| IP-15 | Gateway | App and QueryService | Authenticated requests | pending |
| IP-16 | `docs/taxonomy.md` | QueryService | Core taxonomy text | pending |

### Lifecycle Paths
| Component | INIT (created/started by) | CLEANUP (stopped/released by) |
|-----------|--------------------------|-------------------------------|
| Build | Run by a developer or CI before the image build | Exits when files are written; leaves no state |
| App | Browser loads page from Cloud Run | Browser tab close; the App keeps no state |
| Cloud Run service | Deployed by the human's account | Removed by the human; the app has no teardown |
| Ingest | Run by the Operator with the Ingest code committed in this repository, before the warehouse upload | Exits when the tables are written; leaves no state beyond the warehouse |
| QueryService | Cloud Run starts it with the bucket mounted read-only, and it opens the warehouse through the data adapter (SEQ-6) | Operator removes the service after the hackathon |
| Gateway | Cloud Run starts it with the secret mounted | Operator removes the service after the hackathon |
| Bucket | Operator creates it and uploads the warehouse built by the committed Ingest | Operator removes access grants and the bucket after the hackathon |

## 4. Hard Invariants (The "Never" List)

| ID | Category | Invariant | Verification | Priority | Rationale |
|----|----------|-----------|--------------|----------|-----------|
| INV-01 | Data integrity | REQ-1: The Build shall not alter any file under `data/hackathon/` or `data/external/`. | test | Must | Source data is the evidence base; edits would break citations |
| INV-03 | Honesty | REQ-3: When a tract has no Second Harvest site inside it (Z-2 A), or none of its block population is within 30 minutes' drive of a site (Z-2 C), the App shall show the text "No Second Harvest site found under this rule. Other food sources may exist." on that tract's card. | test | Must | The site list is one food bank's network only, and the coverage rule (inside-tract count or 30 minutes' drive) is an approximation |
| INV-11 | Honesty | REQ-16: The App shall not show the phrases "no food access" or "no access" for any tract, anywhere in the App. | test | Must | The site list is one food bank's network only; no site found is not proof of no access |
| INV-04 | Privacy | REQ-4: The App shall hold in its static files only tract-level data: no block-level record, and block values only as tract sums. | test | Must | Block population has differential-privacy noise, so a single block value is not valid. Query answers may return loan rows (Z-9, Ketema, 2026-11-08); the static files stay tract-level |
| INV-12 | Privacy | REQ-17: The Build shall write only tract-level fields to the static tract file. | test | Must | The file is served publicly, so a block-level field in it would be published even if the App ignored it |
| INV-05 | Honesty | REQ-5: The App shall not omit a missing or blank indicator from the tract card. | test | Must | Florida CDC values are blank; hiding that misleads |
| INV-06 | Scope | REQ-6: The App shall get every value it shows from this project's own files and query service, and its map tiles from a tile server. | test | Should | Ketema, 2026-11-08 (Z-7): the app needs its data and AI answers from the project's own services; the earlier ban on any runtime service call is replaced by this need |
| INV-07 | Attribution | REQ-12: The App shall show, on every view, a credit to DataKind and Beacon with a link to www.datakind.org and the statement that Beacon content is CC BY 4.0. | test | Must | Beacon's license page requires CC BY 4.0 attribution to DataKind with a link to www.datakind.org (`docs/hackathon/linked-pages.md`, "Beacon license") |
| INV-08 | Brand | REQ-13: The App shall follow `docs/hackathon/resources/beacon-design-brand-guidelines.pdf`. | human review | Must | Decided by Ketema, 2026-11-07 ("we follow the branding"): the team follows the Beacon brand guidelines that DataKind provided. Compliance needs a person to judge it |
| INV-09 | Display | REQ-14: The App shall color each drawn tract (489 of 490) on the map as Classic Food Desert (high need), No gap flagged, or Insufficient data. | test | Must | Two of the three names are the brief's own; "No gap flagged" was proposed by Ryan's agent. The three classes cover all 490 tracts (97, 391 and 2), but tract `12095990000` (water) has no polygon, so it is listed as Insufficient data and not drawn |
| INV-10 | Display | REQ-15: The App shall show a legend pinned on the map canvas that names each map class and its color and remains visible when side panels scroll. | test | Must | Visual inspection of PR #11 showed the sidebar legend scrolled off screen |
| INV-13 | Alignment | REQ-18: The App shall provide three selectable persona lenses (Food Bank Planner, SBA / CDFI Officer, and Shared Alignment: Opportunities to Serve), labelled on screen "Food bank", "Small business lender" and "Both partners", and top KPI cohort cards that filter the map to the selected cohort. | test | Must | Sponsor feedback and Ketema's directive: program managers cannot decide in a silo and need a shared alignment driver; labels Ketema, 2026-11-08 (Z-20) |
| INV-14 | Lending contrast | REQ-19: The Build shall flag as dual-gap each Classic Food Desert with at least 1,200 residents whose SBA 7(a) and 504 loans per 1,000 residents (DS-X5) are at or below the bottom-quartile cut over the populated tracts (inclusive quartile, 0.9427; 26 tracts). | test | Must | The brief, Appendix A: "SBA loan count per capita in the bottom quartile, despite a sizable labor force/population base"; Ketema and Ryan, 2026-11-08 (Z-23) |
| INV-15 | Transport gap | REQ-20: The Build shall join the household no-vehicle rate per tract (DS-X7b), flag the 53 high-food-need tracts at or above the inclusive 75th-percentile no-vehicle threshold of 6.90% and the 12 triple-gap tracts, and recommend mobile pantry deployment for every tract that meets that threshold. | test | Must | Sponsor feedback: highlight the transportation gap for resource deployment |
| INV-16 | Action wizard | REQ-21: The App shall provide an AI Insight and Coordinated Action Wizard with an executive briefing, natural-language query or prompt-chip cohort filtering, and a one-click Coordinated Action Brief generator that outputs a cross-agency intervention plan with counterfactual impact. | test | Must | Ketema's directive from Gap Zapper analysis: AI-led insight-driven action taking |
| INV-17 | Confidence | REQ-22: The App shall show each tract's deterministic confidence level (Not rated when class is Insufficient data, Lower when households are under 500 or group-quarters share exceeds 20%, and Moderate otherwise), median household income with its 90% margin of error (DS-X28), and source IDs on the tract card. | test | Must | Sponsor feedback: surface sources, margins of error and confidence levels |
| INV-18 | Map clarity | REQ-23: The Build shall emit only exterior county boundary segments with no interior water-sliver or unshared tract edges inside a county. | test | Must | Visual inspection of PR #11 showed interior unshared edges drew confusing blue lines across counties |
| INV-19 | Map clarity | REQ-24: The App shall render tract fills at overview zoom without overlapping coverage circles obscuring the choropleth. | test | Must | Visual inspection of PR #11 showed 97 dark circles piled over urban Orange County tracts |
| INV-20 | Data scope | REQ-25: The Ingest shall load into the warehouse every retained source file with a reference period of 2024-01-01 or later, and every base-geography file at its most recent vintage. | test | Must | Ketema, 2026-11-08: 2024 and newer; base geography is only maps |
| INV-21 | Data scope | REQ-26: The Ingest shall list each excluded file with its reason: time scope, duplicate content, or duplicate format. | test | Must | Ketema, 2026-11-08: nothing is deleted, and there are no duplicates |
| INV-22 | Data scope | REQ-27: The Ingest shall keep only the Florida, New York and Utah rows of a source that has a state field, and every row of a source that has none. | test | Must | Ketema, 2026-11-08: stay with the brief's three regions |
| INV-23 | Data integrity | REQ-28: The Ingest shall read retained source files from local disk only and leave them unaltered. | test | Must | Ketema, 2026-11-08: nothing is fetched at build; raw sources stay as retrieved |
| INV-24 | Provenance | REQ-29: The Ingest shall record for every table its source file, origin URL, retrieval time, SHA-256, publisher, license, as-of date, applied filter, rows in the source and rows loaded; a field that the sources do not state reads "not recorded". | test | Must | Ketema, 2026-11-08: the app cites its sources and does not infer data |
| INV-25 | Glossary | REQ-30: The Ingest shall build a glossary table from the data dictionaries and lookup files that it loads. | test | Must | Ketema, 2026-11-08: the model needs grounded definitions of the terms |
| INV-26 | Storage | REQ-31: The Operator shall build the warehouse once and keep it in a private Google Cloud Storage bucket in project `<gcp-project>`. | tool | Must | Ketema, 2026-11-08: "use a gcp bucket"; built once, stored in its bucket |
| INV-27 | Citation | REQ-32: The QueryService shall return with every answer the source ID, origin URL, publisher, as-of date and filter of each table the answer used. | test | Must | Ketema, 2026-11-08: the app has to cite sources |
| INV-28 | Schema | REQ-33: The QueryService shall provide a schema tool that returns the warehouse tables, columns, grain, join keys, as-of dates and glossary terms. | test | Must | Ketema, 2026-11-08: free-form questions need the warehouse schema; the sources differ in grain |
| INV-29 | Free query | REQ-34: The QueryService shall run any read-only SELECT statement that the model writes, within a row limit and a time limit. | test | Must | Ketema, 2026-11-08: any free-form query is allowed; loan rows are not restricted (Z-9) |
| INV-30 | Query tools | REQ-35: The QueryService shall provide a spatial lookup of sites near a tract or point and a correlation tool that returns the sample size, coefficient, method and caveats. | test | Must | Ketema, 2026-11-08: the data is queried to find relationships; the tool computes the statistic |
| INV-31 | Grounding | REQ-36: The QueryService shall send the core taxonomy in `docs/taxonomy.md` to the model with every question. | test | Must | Ketema, 2026-11-08: without it the model invents what "Food Desert" means |
| INV-32 | Honesty | REQ-37: The QueryService shall build every number in an answer from a tool result. | execution | Must | A language model can invent a number; a live comparison with a recomputation checks it |
| INV-33 | Provider | REQ-38: The QueryService shall call Vertex AI with a Gemini model named in its configuration, using the service's own identity. | test | Must | Ketema, 2026-11-08 (Z-8): Vertex AI for the sponsor perks, starting with Gemini 3.8 Flash; no key reaches the browser |
| INV-34 | Fallback | REQ-39: When Vertex AI is unavailable or slow, the App shall use the built-in wizard and show the notice "AI unavailable. Using built-in filters." | test | Must | Ketema, 2026-11-08 (Z-10). FLAGGED by Ketema: this may change the UI; the rendered result is shown to him before it is accepted |
| INV-35 | Citation | REQ-40: The App shall show beside every AI answer a chip for each cited source with its ID, publisher, as-of date and origin link. | test | Must | Ketema, 2026-11-08: the app has to cite sources |
| INV-36 | Access | REQ-41: The Gateway shall sign a Viewer in once with a username and password and keep the Viewer signed in until the Viewer logs out. | test | Must | Ketema, 2026-11-08 (Z-13): username [omitted]; no repeated credentials on each request; only a logout ends the session; nothing complex. A request with no valid session gets HTTP 401 |
| INV-37 | Secrets | REQ-42: The Operator shall keep the Gateway password only in Google Secret Manager. | tool | Must | CL16: the password given in chat stays out of every repository file, image layer and log |
| INV-38 | Access | REQ-43: The Operator shall set the App and the QueryService to internal-only ingress. | execution | Must | Ketema, 2026-11-08 (Z-13): login plus a private network; a request to a service address from outside the Gateway fails |
| INV-39 | Lifecycle | REQ-44: The Operator shall remove the Gateway, the QueryService, the App and the bucket's access grants when the hackathon is over. | human review | Should | Ketema, 2026-11-08 (Z-12): "ketema will handle teardown"; no fixed date |
| INV-40 | Access | REQ-45: The App shall provide a logout control that ends the Viewer's session. | test | Must | Ketema, 2026-11-08 (Z-13): the session is cleared on logout only |
| INV-41 | Storage | REQ-46: The QueryService shall read the warehouse from the bucket through the data adapter without rebuilding it. | test | Must | Ketema, 2026-11-08 (Z-14): the warehouse is built once and stored in its bucket; the app connects to it and does not rebuild it |
| INV-42 | Storage | REQ-47: The Ingest and the QueryService shall reach the warehouse through one data adapter that takes a single configured warehouse location. | test | Must | Ketema, 2026-11-08 (Z-19): data access goes through a standard data adapter (verbatim in section 1) |
| INV-43 | Storage | REQ-48: The Ingest shall record in the warehouse only table locations relative to the warehouse location. | test | Must | Ketema, 2026-11-08 (Z-19): "hard coded local file paths is bad architecture"; observations O2 to O4 in `plans/warehouse-adapter.refactor.md` |
| INV-44 | Query engine | REQ-49: The QueryService shall run every query with DuckDB over the warehouse files. | test | Must | Ketema, cycle 13 ("1-agreed" to DuckDB with Parquet) and 2026-11-08: "the value of duckdb is plain. do not reinvent in python what already exists" |
| INV-45 | Query engine | REQ-50: The QueryService shall enforce read-only access with DuckDB's read-only database mode, DuckDB's statement parser and DuckDB's file-access limits. | test | Must | Ketema, 2026-11-08: "do not reinvent in python what already exists"; probes P1 to P5 in `plans/warehouse-adapter.refactor.md` |
| INV-46 | Build | REQ-51: The Operator shall build the warehouse with the Ingest code committed in this repository. | execution | Must | Ketema, 2026-11-08 (Z-18): "if a rule say once but was executed in error it is invalid. rebuild if needed" |
| INV-47 | Storage | REQ-52: The Operator shall mount the warehouse bucket read-only into the QueryService at the configured warehouse location, using the service's own identity. | execution | Must | Ketema, 2026-11-08 (Z-19, option A): a Cloud Run Cloud Storage volume mount |
| INV-48 | Data integrity | REQ-53: The Ingest shall load each retained file that contains an undecodable byte or an unparsable row, with a replacement character for each undecodable byte and without each unparsable row. | test | Must | Ketema, 2026-11-08 (Z-22): "do not let a single row exclude an entire file. allow the placeholders" |
| INV-49 | Data integrity | REQ-54: The Ingest shall log each replaced byte and each excluded row with its file and location. | test | Must | Ketema, 2026-11-08 (Z-22): "but log it so that it is surfaced" |
| INV-50 | Reach | REQ-55: For each tract, the Build shall write the share of its 2020 block population whose straight-line distance to the nearest Second Harvest site is at most d miles, and the number of distinct sites within d miles of any populated block, for every d from 0 to 20 miles in steps of 0.5, together with the smallest such distance over its populated blocks. | test | Must | Ketema, 2026-11-08 (Z-2, option 2-A): "nearby" is the share of each tract's block population within the threshold. Grid: PR #18's slider (jev, at Ketema's direction (2026-11-08): 0.88) |
| INV-51 | Reach | REQ-56: The App shall take every reach figure for the selected distance from the Build's values for that distance. | test | Must | Ketema, 2026-11-08: the browser's own centre-point distance disagreed with the Build for 478 of 489 tracts (Disconnect Matrix B01) |
| INV-59 | Reach | REQ-64: The App shall count a tract as within the limit when its smallest block distance is at most the selected distance. | test | Must | Consistent with REQ-3 (no block population in reach means no site under the rule); jev, at Ketema's direction (2026-11-08): 0.71 |
| INV-52 | Honesty | REQ-57: The App shall show the reach controls in straight-line miles, never as a travel time. | test | Must | Ketema, 2026-11-08 (Z-25 A, amended by Z-28): the reach rule stays straight-line miles; a drive time is a separate fact for the selected tract |
| INV-62 | Honesty | REQ-67: The App shall label each drive time it shows as a road-network estimate or as the heuristic fallback. | test | Must | Ketema, 2026-11-08 (Z-28, deferring to Ryan): a fallback estimate is never shown as a routed time |
| INV-53 | Thresholds | REQ-58: The Build shall write the inclusive-quartile cut of the poverty and household no-vehicle rates at the 50th, 75th and 90th percentiles, and of SBA loans per 1,000 residents at the 10th, 25th and 50th percentiles, over the same tracts as the fixed rule. | test | Must | Ketema, 2026-11-08 (Z-24 A): the gap cuts become adjustable, with one quantile computation in the Build. Named choices: jev, at Ketema's direction (2026-11-08): 0.73 |
| INV-54 | Thresholds | REQ-59: The App shall let the user choose one of the Build's percentiles for each of the three cuts, starting at 75 for poverty, 75 for no-vehicle and 25 for SBA loans. | test | Must | Ketema, 2026-11-08 (Z-24 A): the brief's values are the start |
| INV-60 | Thresholds | REQ-65: The App shall recount every gap group with the REQ-19 and REQ-20 rules using the Build's cut for each chosen percentile. | test | Must | Ketema, 2026-11-08 (Z-24 A): at the starting percentiles the counts equal the fixed rule (97 Classic Food Deserts, 26 dual, 53 transport, 12 triple) |
| INV-61 | Access | REQ-66: When the QueryService refuses a question because the Viewer's session has ended, the App shall show the notice "Your session ended. Sign in again." with a link to the sign-in page. | test | Must | jev at Ketema's direction (2026-11-08), highest rated: a separate message (0.82) rather than the outage notice; the built-in wizard stays usable |
| INV-55 | Grounding | REQ-60: The QueryService shall answer each question under the reach distance and cut percentiles that the App sends with it. | test | Must | Ketema, 2026-11-08 (Z-24): the AI answers under the thresholds currently set (SLICE-4) |
| INV-56 | Provenance | REQ-61: The Build shall write into the static bundle the entry from docs/data-sources.md (ID, label, publisher, period, URL, retrieval method, limits) for every source the App cites. | test | Must | Ketema, 2026-11-08: the source list comes from one authority, not a typed copy (Disconnect Matrix B05) |
| INV-57 | Provenance | REQ-62: The App shall list as sources only the entries in the static bundle. | test | Must | Ketema, 2026-11-08: Disconnect Matrix B05 |
| INV-58 | Display | REQ-63: While gap emphasis is on, the App shall draw an outline around each tract of the chosen group, draw the other tracts at reduced opacity, and show the count of the group's tracts on the map beside the count without a map shape. | test | Should | Ketema, 2026-11-08: PR #18 checkpoint feature kept (Disconnect Matrix B04) |

When the slider slice starts, the App shall carry INV-02 (REQ-2, the "assumption-based estimate" label). See "Deferred items" in section 5.

**Cycle 13 amends two approved requirements (Z-7, Z-9).** INV-06 (REQ-6) now states the need instead of a ban, and INV-04 (REQ-4) covers the static files only. Ketema decided both (CL4), 2026-11-08. SLICE-1 behavior stays the same: its App still draws from its static files and a tile server.

## 5. High-Entropy Zones (Adjudicated)
| Zone | Question | Resolution | Decided By |
|------|----------|------------|------------|
| Stack | Which technologies? | React, Vite, TypeScript 7, MapLibre, static data, Vitest, no AI first. The compiler is TypeScript 7 (PR #8); `typescript-eslint` runs on the TypeScript 6 legacy API side by side until it supports 7. Warehouse engine: DuckDB over Parquet (cycle 13, "1-agreed"; reached through the data adapter, Z-19) | User (CL4) |
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
| **Z-7** | Does INV-06 (REQ-6) change to let the App use its own query API? | **Decided.** INV-06 states the need: the App gets its data from this project's own files and query service, and its map tiles from a tile server. A Viewer is someone with the shared login | Ketema (CL4), 2026-11-08 |
| **Z-8** | Which Vertex AI model? | **Decided.** Gemini 3.8 Flash to start, named in configuration. The model name and its availability in `us-east1` are confirmed with a live call when the contract is written | Ketema (CL4), 2026-11-08 |
| **Z-9** | May the QueryService return individual SBA loan rows? | **Decided.** Yes, full rows with no column restriction; the data is public. The default insight queries aggregate, and row-level data comes back when the user asks | Ketema (CL4), 2026-11-08 |
| **Z-10** | What happens when Vertex AI is down? | **Decided, flagged.** The App falls back to the built-in wizard and shows the notice in REQ-39. Ketema flagged REQ-39 because it may affect the UI; he wants to see what it produces before accepting it | Ketema (CL4), 2026-11-08 |
| **Z-11** | Which questions define "answers natural-language questions about the data"? | **Decided.** Six baseline questions, listed in section 8, plus free-form questions through the schema tool and read-only SQL | Ketema (CL4), 2026-11-08 |
| **Z-12** | When is the shutdown, and who triggers it? | **Decided.** Ketema handles the teardown himself, with no fixed date | Ketema (CL4), 2026-11-08 |
| **Z-13** | How are the services protected? | **Decided.** A username and password login at an nginx Gateway (username [omitted], password in Secret Manager, never in the repository). A Viewer signs in once, stays signed in until logout, and nothing else ends the session. The App and the QueryService take internal-only ingress | Ketema (CL4), 2026-11-08 |
| **Z-14** | Where does the canonical warehouse live, and how do the App and the model both reach it? | **Decided.** A private Google Cloud Storage bucket in `<gcp-project>`. The Ingest runs once and the QueryService reads the warehouse from the bucket through the data adapter (Z-19); nothing rebuilds it. New App features read through the QueryService; the static tract file stays for the map | Ketema (CL4), 2026-11-08 |
| **Z-15** | What data does the warehouse hold? | **Decided.** Every retained source file with a reference period of 2024 or later, plus base geography (most recent vintage), Florida, New York and Utah rows where a source has a state field, nothing fetched at build, nothing deleted, no duplicates | Ketema (CL4), 2026-11-08 |
| **Z-16** | Which provider and query design? | **Decided.** Vertex AI with a schema tool, read-only SQL for free-form queries, a spatial lookup and a correlation tool. The core taxonomy goes with every question | Ketema (CL4), 2026-11-08 |
| **Z-17** | Is an MCP server in scope? | **Decided.** No. A later slice can wrap the same tools | Ketema (CL4), 2026-11-08 |
| **Z-18** | Who builds the corrected warehouse, given that REQ-31 says it is built once? | **Decided.** The first build ran from scratch scripts and wrote machine-specific paths, so it was done in error and does not count as the one build. The Operator rebuilds the warehouse with the Ingest code committed in this repository (REQ-51) and uploads it to the bucket | Ketema (CL4), 2026-11-08 |
| **Z-19** | How does the QueryService reach the warehouse in the bucket? | **Decided, option A.** Cloud Run mounts the bucket read-only as a volume at a configured warehouse location, using the service's own identity. DuckDB opens the warehouse there through a data adapter that takes that one location; tests and local runs use the same adapter with a different location. The warehouse stores only locations relative to it | Ketema (CL4), 2026-11-08 |
| **Z-20** | Which labels does the App show for the three persona lenses? | **Decided.** "Food bank", "Small business lender" and "Both partners" (the wording in the updated prototype). The lens roles in REQ-18 do not change | Ketema (CL4), 2026-11-08 |
| **Z-21** | What does the Coordinated Action Brief show when the joint action reaches no more tracts than today? | **Decided, option A.** The brief shows the reduction as it is, including zero, and says plainly that the plan does not reach those tracts. The App never adjusts a figure so that a check passes | Ketema (CL4), 2026-11-08 |
| **Z-22** | What does the Ingest do when some bytes or rows of a source file cannot be read? | **Decided: a combination.** One bad row or byte never excludes the whole file. An undecodable byte is loaded as a replacement character and a malformed row is set aside; each one is logged and listed in the Ingest report. A file that cannot be opened at all still stops the Ingest | Ketema (CL4), 2026-11-08 |
| **Z-23** | How does REQ-19 decide that a food desert lacks SBA lending, and what counts as a "sizable population base"? | **Decided.** The brief's own rule: SBA loans per 1,000 residents in the bottom quartile (inclusive quartile, the Z-1 method, over the 489 populated tracts: 0.9427), replacing the raw count at or below the median of 10. "Sizable" is the Census Bureau's 1,200-resident tract minimum (chosen by the decision model at Ketema's instruction, support 64% against no floor 45%, bottom-quartile population 26%, median population 21%). Counts: dual gap 26, triple gap 12 (67,564 people); food deserts stay 97 | Ketema and Ryan (CL4), 2026-11-08 |
| **Z-24** | Which taxonomy definitions become adjustable? | **Option A**: reach distance (already a slider) plus the three gap cuts, poverty (top quarter), household no-vehicle (top quarter) and SBA loans per 1,000 residents (bottom quarter), each a percentile with the brief's value as the start. Confidence rules stay fixed. The AI answers under the thresholds currently set (REQ-55 to REQ-65) | Ketema (CL4), 2026-11-08: "1 - A" |
| **Z-25** | How is time shown until #16 supplies drive times? | **Option A**: miles only; no minutes on screen (REQ-57). The 10-mile default stands in for Z-2d's 30 minutes until #16 | Ketema (CL4), 2026-11-08: "2 - A" |
| **Z-26** | What are the details of the App's `ask` call (PR #19 alignment)? | **Decided by jev** (jev at Ketema's direction (2026-11-08), highest rated): POST `/api/ask` with the question, the reach distance and the three cut percentiles (REQ-60); the reply holds the answer, the model, the tool results, the citations and a `tracts` field listing every GEOID the answer refers to, so the map is never limited by SQL row limits (0.74, reconciled 0.80); "slow" in REQ-39 means no reply within 20 seconds (0.74); a session-ended refusal gets its own notice (REQ-66, 0.82) | Ketema (CL4), 2026-11-08: "use jev for those implementation detail choices. take the highest rated one" |
| **Z-27** | Does the planner get drive times from a routing provider (#16)? | **Decided: no.** Ketema rescinded the Google Routes plan ("i rescind the google drive times.") after choosing it from jev's ratings; Ryan chose "Demo on miles only". #16 stays frozen. Reach is straight-line miles from block points (Z-2 2-A, REQ-55), shown in miles only (Z-25 A); the drive-time intent of Z-2b and Z-2d is not delivered in this release | Ketema (CL4), 2026-11-08 |
| **Z-28** | Does the App show drive times (#16), which Ryan's side has built? | **Decided: yes, Ryan's design.** Ketema: "i defer to ryan's choice on this. we talked and he says he already has it built and is using the open source dynamic lookup with api key." The openrouteservice matrix (hosted, API key on the server side only) gives a cached road-network estimate per tract; without it the App shows the labeled heuristic fallback (`docs/drive-times.md`). The reach controls stay straight-line miles (REQ-57 amended). Supersedes Z-27, and Z-25 A for the drive-time estimate | Ketema (CL4), 2026-11-08, deferring to Ryan |
| **Z-29** | Is sign-in required for this release (SLICE-5)? | **Decided: no, open access.** Ketema: "ignore login logout. defer that. open access" and "we understand and accept the risk. deploy". The App and the QueryService are public; SLICE-5 (REQ-41 to REQ-45) and the internal-only ingress of REQ-52 are deferred | Ketema (CL4), 2026-11-08 |

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
| Bucket mounted read-only (Z-19 A) | DuckDB reads `gs://` directly (Z-19 B) | DuckDB authenticates to Cloud Storage only with HMAC keys, a long-lived credential to create, rotate and remove; the mount uses the service's own identity |
| Bucket mounted read-only (Z-19 A) | Copy the bucket to the container at startup (Z-19 C) | About 1 GB per cold start held in memory, and a slow start |
| DuckDB's own read-only and statement checks (REQ-50) | A hand-written SQL regex and keyword list | Re-implements what DuckDB already enforces ("do not reinvent in python what already exists") |

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
| ingest-warehouse | Load retained files into the warehouse tables at the configured warehouse location through the data adapter | YES (writes the warehouse only) | Ingest | The Operator runs it |
| open-warehouse | Open the warehouse read-only in DuckDB at the configured warehouse location | NO | QueryService (data adapter) | QueryService startup (SEQ-6) |
| schema.describe | Return tables, columns, grain, join keys, as-of dates and glossary terms | NO | QueryService | A model tool call |
| sql.query | Run a read-only SELECT within the limits | NO | QueryService | A model tool call |
| sites.near | Find sites within a distance of a tract or point | NO | QueryService | A model tool call |
| stats.correlate | Compute a correlation with sample size, method and caveats | NO | QueryService | A model tool call |
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

## 7. Failure Mode Specification (CL9)

| Requirement | Failure Condition | Behavior | Notification |
|------------|-------------------|----------|-------------|
| REQ-7 | Static tract file is missing or fails to parse | Halt: the App draws no map | The App shall show an error naming the file |
| REQ-8 | A tract has a missing indicator | Show the tract as Insufficient data, not as low need | Card names the missing indicator |
| REQ-9 | Build input file is missing or has changed columns | Halt: the Build exits non-zero | The Build shall name the file and column |
| REQ-10 | Map tiles fail to load | FALLBACK: draw tracts on a blank background | The App shall display "Base map unavailable" |
| REQ-25 | The Ingest cannot open or read a file in scope at all | Halt: the Ingest exits non-zero | The Ingest shall name the file and the reader error |
| REQ-53 | A retained file contains an undecodable byte or an unparsable row | Load the file; put a replacement character in place of each undecodable byte and leave out each unparsable row (Z-22) | The Ingest shall log each replacement and each excluded row with its file and location (REQ-54) |
| REQ-21 | The joint action in a Coordinated Action Brief reaches no more tracts than today | Show the reduction as it is, including zero (Z-21) | The App shall state in the brief that the plan does not reach those tracts |
| REQ-29 | A provenance field is absent from the sources | Record "not recorded" and continue | The files table shows "not recorded" for that field |
| REQ-34 | The model writes a statement that is not a read-only SELECT, or a query exceeds a limit | Reject the statement | The QueryService shall return an error that names the rule broken |
| REQ-38 | Vertex AI is unreachable or slow | FALLBACK: the built-in wizard (REQ-39) | The App shall show the notice in REQ-39 |
| REQ-41 | A request has no valid session | Reject the request | The Gateway shall answer HTTP 401 and show the login |
| REQ-43 | A request reaches a service address directly | The request fails | The service address returns an error and no content |
| REQ-47 | The configured warehouse location is unset, missing, or holds no warehouse | Halt: the QueryService does not start | The QueryService shall exit non-zero naming the location and the missing item |
| REQ-48 | A catalog table location is absolute or points outside the warehouse location | Halt: the QueryService does not start | The QueryService shall exit non-zero naming the table and its location |
| REQ-50 | A statement is not exactly one SELECT, or reads a file outside the warehouse location | Reject the statement | The QueryService shall return an error that names the rule broken |

When the slider slice starts, the App shall carry REQ-11 (slider clamp).

## 8. Completion Promise (Ralph Loop Exit)
> "A Viewer opens the deployed URL, sees 489 tracts drawn and colored by flag status, and sees tract 12095990000 listed as not drawn (no geometry). The flagged set equals a set a test recomputes from the source data. The Viewer opens a card whose evidence matches the source tables for that tract and names every missing indicator. A test that passes while the card omits a missing indicator, or while the flagged set differs from the recomputed set, must fail."

Human acceptance remains with the human: whether the map and card are useful to a food bank planner.

> SLICE-3 (warehouse): "The files table lists every retained source file as loaded or excluded with its reason; the row counts of the tables equal a recount of the source files after the state filter; every table has an origin URL, SHA-256 and filter; a run with the network disabled produces the same tables. A check that passes while a table has no origin URL, or while a count differs from a recount, must fail. The warehouse opens read-only through the data adapter in a fresh container at a location other than the one it was built at, and every catalog table location is relative to that location."
>
> SLICE-4 (query service and AI): "A Viewer asks these six baseline questions, and each answer equals an independent recomputation from the source files and names the sources it used: (1) How many Classic Food Desert tracts are in Orange County, and how many of them had 10 or fewer SBA loans? (2) Which five lenders approved the most SBA 7(a) loans in Florida with an approval date in 2024 or later? (3) Among the Classic Food Desert tracts, which five have the highest FEMA hurricane expected annual loss? (4) Across the 490 Central Florida tracts, how strongly is poverty rate correlated with SBA loan count? (5) Where did the median income for tract 12095016510 come from, and how reliable is it? (6) How many people lost SNAP in Seminole County? For question 6 the correct answer states that the warehouse holds no county-level figure. Free-form questions run through the schema tool and read-only SQL. A check that passes when an answer states a number that no tool returned must fail."
>
> SLICE-5 (access): "A Viewer signs in once and later requests carry no credentials until the Viewer logs out; a request with no valid session gets HTTP 401; a request to a service's own address from outside the Gateway fails; the password appears in no repository file, image layer or log."

Human acceptance of SLICE-3 to SLICE-5 remains with the human: whether the answers are useful and trustworthy. Ketema handles the teardown (Z-12).

## 9. Contract Authority
**Authoritative Sources**: `contracts/planner_map_contract.py` (Build domain, Python) and `contracts/planner-map.app.contract.ts` (App domain, TypeScript, cross-referenced by clause ID per Idiomatic Per-Ecosystem Distribution)

SLICE-3 (warehouse, Ingest and data adapter): `contracts/warehouse_contract.py`. SLICE-4 (QueryService): `contracts/query_service_contract.py`.

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
| 2026-11-08 | Ketema, agent | Cycle 13: wiring the data and the AI. Added actors Ingest, QueryService, Gateway and Operator; requirements REQ-25 to REQ-44 (INV-20 to INV-39) for SLICE-3 (warehouse), SLICE-4 (query service and AI) and SLICE-5 (access); SEQ-5 to SEQ-10, IP-10 to IP-16, lifecycle rows, interfaces and failure modes; core taxonomy in `docs/taxonomy.md`. Resolved zones Z-7 to Z-17 one at a time with Ketema (CL4). INV-06 now states the need (own files and query service plus tiles) and INV-04 covers the static files only (Z-9: loan rows are not restricted). The first draft of this cycle had 30 requirements; the human asked for need-based statements, not a straitjacket (PONYTAIL), so it was compressed to 20. The password given in chat is not recorded (CL16). Ambiguity 0. Ketema approved the manifest and plan with caveats: a session login (sign in once, logout only ends it; REQ-41, REQ-45), the warehouse built once and read from its bucket (REQ-31, REQ-46), and REQ-39 flagged for UI review. |
| 2026-11-08 | Ketema, agent | Cycle 14: data adapter (constitutional refactor, option A). Recorded DuckDB over Parquet as the warehouse engine (cycle 13 "1-agreed", lost when cycle 13 was compressed). Added Z-18 (the first build was done in error; rebuild with committed Ingest code) and Z-19 (Cloud Run read-only bucket mount, one configured warehouse location, data adapter). Added REQ-47 to REQ-52 (INV-42 to INV-47); amended REQ-46, SEQ-6, IP-11, IP-12, the dependency graph, lifecycle rows, interfaces, failure modes, rejected alternatives and the SLICE-3 completion promise. Evidence: `plans/warehouse-adapter.refactor.md`. |
| 2026-11-08 | Ketema, agent | Cycle 15: sync with Ryan's side after PR #15. Added Z-20 (lens labels "Food bank", "Small business lender", "Both partners"; REQ-18 amended), Z-21 (the Coordinated Action Brief shows a zero reduction honestly; REQ-21 failure mode added; contract POST-APP-3 to be relaxed) and Z-22 (bad bytes or rows never exclude a whole file; REQ-53 and REQ-54 added as INV-48 and INV-49; REQ-25 failure mode narrowed to files that cannot be opened or read at all). Lint: 0 errors. |
| 2026-11-08 | Ketema, agent | Cycle 16: REQ-19 revised to the brief's per-capita rule (Z-23): SBA loans per 1,000 residents in the bottom quartile, with a 1,200-resident floor for "sizable". Dual gap 50 to 26 and triple gap 29 to 12 in REQ-20, Our Understanding, the ambiguity rationale and the S1 terminal state; the S1 lens labels follow Z-20. The SLICE-4 baseline question (1) keeps its "10 or fewer SBA loans" wording: it is a question for the AI, not the flag rule. |
| 2026-11-08 | Ketema, agent | Cycle 17: constitutional refactor of the PR #18 checkpoint (`plans/pr18-checkpoint.refactor.md`). Added Z-24 (A: reach plus the three gap cuts adjustable as percentiles) and Z-25 (A: miles only, no minutes). Added REQ-55 to REQ-65 as INV-50 to INV-60: Build reach per distance step, App reach from the Build, miles only, Build cuts per percentile, App recount, QueryService under the set thresholds, source list from docs/data-sources.md through the bundle, gap emphasis. Grids and the within-limit rule chosen by jev at Ketema's direction (highest rated): reach 0 to 20 miles by 0.5 (0.88), within the limit when any populated block is in reach (0.71), cuts at named percentiles 50/75/90 and 10/25/50 (0.73). |
| 2026-11-08 | Ketema, agent | Cycle 18: SLICE-4 started (Ketema: "proceed with slice-4"). Added Z-26 (the `ask` call details chosen by jev at Ketema's direction, for PR #19) and REQ-66 as INV-61 (session-ended notice). |
| 2026-11-08 | Ketema, agent | Cycle 19: Z-27, Google drive times rescinded; #16 frozen; the demo uses straight-line miles only. |
| 2026-11-08 | Ketema, agent | Cycle 20: Z-28, drive times by Ryan's design (Ketema defers to Ryan), REQ-57 amended, REQ-67 added as INV-62; Z-29, open access, SLICE-5 deferred. |
