# Detailed reference for Beacon Challenges (Appendices A-C)

Source: https://docs.google.com/document/d/1L25DTxI31BlrH3QvB7k8H0rt6eowMiYA3YqHEwfJer0
Captured: 2026-11-07 (text export; formatting simplified)

---

Detailed reference for Beacon Challenges
Whichever software idea you build across either challenge: an interactive prototype, a recommendation engine, a chat interface, or a trust/transparency layer, it needs underlying logic for deciding what counts as a “gap” and what to recommend. Think of what follows as plumbing, not a parallel project. It’s here to help your software decide what to show, not something separate you also have to deliver. Here’s an example these pieces could connect into a workflow: a tract gets pulled in → classified against the gap taxonomy → matched to a resource category → assigned a review tier → surfaced to a user who can approve, reject, or challenge it. You don’t need to build every stage, pick where you want to start or go deepest.
Challenge 1 Appendix A: Small Business Support Gaps
Geographic note: Beacon’s public economic indicators (SBA lending, income, employment, mortgage data) are available nationwide. NYC also has access to additional public small business certification data from NYC Open Data, not available in the other two cities. Treat this as an optional enhancement, not a requirement.
A few starting prompts, not a checklist:
* Where are concentrations of small businesses and entrepreneurs, and where does lending activity not match that?
* Where are there disparities in income, employment, or access to capital?
* Does the same community look like a “gap” by one indicator but not another, and what does that tell you?
* What would a small business support organization actually want to see to act on this?
Starting resources (optional):
* Example datasets for all three communities
* SBS Certified Business List from NYC Open Data
* Links to small business support organizations per city, sourced from the SBA Resource Partner locator, the NYC small business support map, and the Utah Association of Chambers directory
A possible framework, if useful (a “gap taxonomy”):
 An intermediate layer that translates raw indicator patterns into a defined gap type, use this, adapt it, or build your own. This is the logic that would sit behind, say, a recommendation engine deciding what to surface, or a chat interface answering “what’s going on in this area?”
Raw signal pattern
	Gap type
	SBA loan count per capita in the bottom quartile, despite a sizable labor force/population base
	Capital Access Gap
	Poverty and/or unemployment rate in the top quartile, SBA loan count per capita in the bottom quartile
	Entrepreneurship Infrastructure Gap
	Mortgage denial rate (Mortgage Denials ÷ [Denials + Mortgages Originated]) in the top quartile, SBA loan activity at or above the median
	Credit Access Gap
	Median household income and employment rate both at or above the median, SBA loan activity in the bottom quartile
	Underinvestment Gap (the “looks fine but isn’t” case)
	Mapping gap types to resources:
* Capital Access Gap → CDFIs, microloan lenders, SBA 7(a)/504-active lenders
* Credit Access Gap → SBDC credit-readiness counseling, CDFIs
* Entrepreneurship Infrastructure Gap → SCORE mentorship, Women’s Business Centers, SBDCs, Chamber programs
* Underinvestment Gap → no auto-recommendation; routed straight to Review Required, since a counterintuitive result needs the most scrutiny before anyone acts on it
Evidence and matching rules: For each gap type, define which quartile thresholds count as sufficient evidence, what counts as conflicting evidence (e.g., high loan activity despite low population base likely signals a small but well-served area, not a gap), and which geographies are too small or data-sparse to trust.
A few test scenarios, if useful:
1. Clear capital access gap — sizable population, SBA loan activity in the bottom quartile
2. Competing signals — high poverty rate, but moderate loan activity
3. Underinvestment / blind spot — strong income and employment, but still low loan activity
4. Insufficient data — small tract with suppressed or missing values
Example output format, if useful:
* Geography ID / name
* Primary gap type, secondary gap type (if any)
* Confidence: High / Medium / Low
* Supporting evidence (indicators + computed values)
* Conflicting or limiting evidence
* Recommended resource category + 1–2 sample entries from the seed catalog
* Review tier
Human-review tiers (reviewer = DataKind staff): This maps directly to the recommendation engine’s user controls (approve, reject, confirm, challenge) and to the trust/transparency activity’s goal of making reasoning visible, a tier is the kind of thing a confidence badge or “why this was flagged” explanation would show.
* No review needed: single clear gap type, strong evidence, direct resource match available
* Review recommended: competing gap types or moderate confidence
* Review required: any underinvestment/blind-spot case, or conflicting/insufficient data
If you want to go further: build a working end-to-end prototype and a simple workflow diagram; test how sensitive your gap classifications are to small changes in thresholds; or, for NYC, cross-check SBA-based flags against the real business-address layer to see whether a “Capital Access Gap” tract has fewer registered businesses, or plenty of businesses just not getting loans.
Challenge 2 Appendix B: Food Access Gaps
What’s available: Beacon’s public food-access indicators, SNAP-related counts, SNAP retailer counts, USDA low-grocery-access measures, poverty-related counts, and the no-reliable-transportation rate, at the census tract level. Coverage differs by city, see the data notes below before building.
Data notes, if useful:
* “No Reliable Transportation – Adults” is available for NYC and Salt Lake City only. It is not currently available for Central Florida. Central Florida teams should build around the indicators that are available there (poverty, grocery access, SNAP participation) rather than this one.
* Poverty rate and SNAP participation rate are both available directly as ready-made percentages (no need to compute from raw counts and a population/household denominator).
* SNAP Retailers is available only as an address-level list, not pre-joined to the census tract. This will not be cross-walked to tract level before the event, so treat it as an optional manual lookup for a specific area of interest, not a systematic column you can compute across all tracts.
* USDA ERS publishes multiple “Low Grocery Access” definitions. Use the Low-Income AND Low-Access (“LILA”) version at ½ mile (urban) / 10 miles (rural), not a distance-only flag. LILA is the standard definition of a “food desert” used in policy and research, since it requires both low income and low access, not just distance from a store.
Starting resources (optional):
* Example datasets for all three communities
* Links to food access resources per city, sourced from Feeding America’s national finder Second Harvest Food Bank Central Florida ,NYC Food Help, and 211 Utah
A possible framework, if useful (a “gap taxonomy”): This is the logic that would sit behind, say, a recommendation engine deciding what to surface, or a chat interface answering “what’s going on in this area?”
Raw signal pattern
	Gap type
	Poverty rate in the top quartile, flagged under the LILA ½ or 10 miles low grocery access definition
	Classic Food Desert
	Flagged for low grocery access, no-reliable-transportation rate in the top quartile (NYC and Salt Lake City only; not available for Central Florida)
	Transportation-Compounded Gap
	No indicator crosses its top-quartile threshold, but at least two of the available indicators fall in the second-highest quartile (for Central Florida, this means poverty and grocery access only, since transportation isn’t available there)
	Possible Blind Spot
	Mapping gap types to resources:
* Classic Food Desert → nearest food bank/pantry, mobile pantry programs if listed
* Transportation-Compounded Gap → mobile pantry or delivery-based programs, transit-accessible locations
* Possible Blind Spot → no auto-recommendation; Review Required
A few test scenarios, if useful:
1. Clear classic food desert — high poverty, flagged under LILA
2. Transportation-compounded (NYC/SLC only) — flagged for low grocery access plus high no-reliable-transportation rate
3. Blind spot — moderate indicators throughout
4. Insufficient data
Example output format, if useful:
* Geography ID / name, primary/secondary gap type, confidence, supporting and limiting evidence, recommended resource(s), review tier
Human-review tiers: same structure as Appendix A. This maps directly to the recommendation engine’s user controls (approve, reject, confirm, challenge) and to the trust/transparency activity’s goal of making reasoning visible, a tier is exactly the kind of thing a confidence badge or “why this was flagged” explanation would show.
If you want to go further: 
* Test how a different grocery-access definition changes which communities get flagged, especially in SLC.
* Prototype a Benefit-Redemption-style gap (high SNAP participation relative to visible retailer density) for one specific area of interest, using the SNAP retailer address list as a manual lookup, since it isn’t available as a systematic per-tract column for this event.
* If you’re working in Central Florida, consider whether a different third signal (beyond poverty and grocery access) could stand in for what transportation provides in NYC and SLC, and tell us what you tried.
Appendix C: Geography Data Summary
* SBA lending and Census economic data: available in Central FL, NYC, and SLC (raw counts; rates must be computed)
* Bonus registered business open data: NYC only
* Poverty rate and SNAP participation rate: available in Central FL, NYC, and SLC as ready-made percentages
* No Reliable Transportation: available in NYC and SLC only, not Central FL
* Low Grocery Access (LILA definition): available in Central FL, NYC, and SLC
* SNAP Retailer locations: available as an address list only, not joined to census tract; manual lookup only for this event