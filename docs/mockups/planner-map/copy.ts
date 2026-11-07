// Plain-language copy for the planner map mock-up. Owner: the plain-language task (T9).
//
// Three levels of detail (see the shared brief):
//   glance   the sidebar top: headline, one or two sentences, a legend of at most 4 entries
//   explore  the tract card top: 2 or 3 plain sentences about one neighborhood
//   detail   everything inside <details className="how-we-know">: numbers, method, sources
// Text in this file that is used outside "How we know this" must stay at US grade 8 or lower
// (check with check-readability.mjs). Technical terms go in GLOSSARY and the detail level only.
import type { Cls, ConfLevel, Coverage, Tract } from './model'
import { GROUP_QUARTERS_PCT, NEAR_CUT_POINTS, SMALL_HOUSEHOLDS, fmt, limits } from './model'

// ---------------- Glossary ----------------

// Plain wording for each technical term. The detail level shows this list as "Words we use".
export const GLOSSARY: { term: string; plain: string }[] = [
  {
    term: 'Census tract',
    plain:
      'A small area that the Census Bureau uses to count people. Each county has many tracts. On this page, "neighborhood" means a census tract.',
  },
  {
    term: 'SNAP',
    plain:
      'The Supplemental Nutrition Assistance Program, once called food stamps. It helps people with low income buy food.',
  },
  {
    term: 'ACS',
    plain:
      'The American Community Survey. The Census Bureau asks a sample of homes each year. We use the 5-year results for 2020 to 2024. Because it is a sample, each number is an estimate.',
  },
  {
    term: 'LILA',
    plain:
      'Low income and low access. A USDA flag for a neighborhood with low income where many people live far from a supermarket: more than 1/2 mile in a city or 10 miles in the country. We use the driving-distance version.',
  },
  {
    term: 'Quartile',
    plain:
      'One of four equal groups when you sort all neighborhoods from low to high. "Top quartile" means the top 1 in 4.',
  },
  {
    term: 'Group quarters',
    plain:
      'Shared housing such as dorms, nursing homes, prisons and shelters. The survey does not count these people in its household numbers.',
  },
  {
    term: 'Margin of error',
    plain:
      'How far a survey estimate could be from the true number. Small neighborhoods have larger margins of error.',
  },
  {
    term: 'Stand-in',
    plain:
      'A rough placeholder we use until the decided method or data is ready. Do not use a stand-in value for decisions.',
  },
  {
    term: 'Load',
    plain:
      'People per food site: the people in a neighborhood divided by the number of Second Harvest sites within reach. A higher number means each site is shared by more people.',
  },
  {
    term: 'Reach',
    plain:
      'The share of people in a neighborhood who live close enough to a Second Harvest site. The decided rule is a 30-minute drive. The mock-up uses a straight-line distance as a stand-in.',
  },
]

// ---------------- Reusable UI strings ----------------

export const UI = {
  headline: 'Where do people need food help most, and is help close by?',
  notice: 'Mock-up with stand-in data. Do not use it to make decisions.',
  clickHint: 'Click a neighborhood on the map, or pick one from the list.',
  howWeKnow: 'How we know this',
  compareWith: 'Compare with',
  compareNothing: 'Nothing',
  layersHeading: 'Show on the map',
  coverageToggle: 'How many people share each food site',
  coverageLoad: 'People per site',
  coverageReach: 'People near a site',
  sitesToggle: (count: number) => `Second Harvest food sites (${fmt.format(count)}, in 7 counties)`,
  listHeading: (count: number) => `High-need neighborhoods (${count})`,
  sortLabel: 'Sort neighborhoods',
  sortPoverty: 'Most poverty',
  sortSnap: 'Most SNAP use',
  sortLoad: 'Most people per site',
  noSiteInside: 'no food site inside',
  standin: 'stand-in',
  draft: 'draft',
  close: 'Close',
} as const

// Glance text. Computed from the data by the caller; this function only words it.
export function glanceSummary(desert: number, total: number, noSiteInside: number): string[] {
  return [
    `${desert} of ${total} neighborhoods in Central Florida have high poverty. Many people there also do not live near a supermarket.`,
    `In ${noSiteInside} of them, we found no Second Harvest food site inside the neighborhood. Other food sources may exist.`,
  ]
}

// One plain line under each fixed class name (CLASS_LABEL stays as it is, REQ-14).
export const CLASS_PLAIN: Record<Cls, string> = {
  desert: 'High poverty, and many people do not live near a supermarket.',
  nogap: 'We did not find both of those signs here. Need can still exist.',
  insufficient: 'Not enough data to tell. This does not mean need is low.',
}

// The fourth legend entry: the circles on the orange areas.
export const CIRCLE_PLAIN: Record<Coverage, { name: string; plain: string }> = {
  load: {
    name: 'Gray circles',
    plain: 'On orange areas only. A bigger circle means more people share each nearby food site.',
  },
  reach: {
    name: 'Blue circles',
    plain: 'On orange areas only. A darker circle means more people live near a food site.',
  },
}

// ---------------- Numbers people can picture ----------------

// "about 1 in 4" for 23.1. Picks the closest of 1 in N (N = 2 to 20) and N in 10.
export function oneIn(p: number | null): string {
  if (p === null) return 'an unknown share'
  if (p < 5) return 'fewer than 1 in 20'
  if (p >= 95) return 'almost all'
  const options: { v: number; text: string }[] = []
  for (let d = 2; d <= 20; d++) options.push({ v: 100 / d, text: `1 in ${d}` })
  for (let k = 3; k <= 9; k++) options.push({ v: k * 10, text: `${k} in 10` })
  const best = options.reduce((a, b) => (Math.abs(b.v - p) < Math.abs(a.v - p) ? b : a))
  return `about ${best.text}`
}

// The tract name without the word "Census Tract", for the glance and explore levels.
export function plainName(t: Pick<Tract, 'name'>): string {
  return t.name.replace(/^Census Tract /, 'Neighborhood ')
}

// The tract number alone ("165.10"), for list rows under a "neighborhoods" heading.
export function tractNumber(t: Pick<Tract, 'name'>): string {
  return t.name.replace(/^Census Tract /, '')
}

export const wholePct = (v: number | null) => (v === null ? 'unknown' : `${Math.round(v)}%`)

// ---------------- Tract card (explore level) ----------------

export function cardWhatIsHere(t: Tract, cut: number): string {
  if (!t.drawn) return 'This area is water, so it is not drawn on the map. No one lives here.'
  if (t.cls === 'insufficient') {
    const shared =
      t.groupQuartersPct !== null && t.groupQuartersPct > 50
        ? ' Most people here live in shared housing, like dorms, which the survey does not count as homes.'
        : ''
    return `We do not have enough data to rate this neighborhood.${shared}`
  }
  const poor = `${oneIn(t.pctPoverty)} people here live in poverty`
  const highPoverty = t.pctPoverty !== null && t.pctPoverty >= cut
  const lila = t.lilaDD === 1
  if (t.cls === 'desert')
    return `Poverty is high: ${poor}. The USDA also marks this as a low-income area where many people do not live near a supermarket.`
  if (highPoverty)
    return `Poverty is high: ${poor}. But the USDA does not mark it as a low-income area far from supermarkets.`
  if (lila)
    return `The USDA marks this as a low-income area where many people do not live near a supermarket. But poverty is not in the top 1 in 4 of neighborhoods: ${poor}.`
  return `Poverty is lower here: ${poor}. The USDA does not mark it as a low-income area far from supermarkets.`
}

export function cardWhyItMatters(t: Tract): string {
  if (t.cls === 'desert') return 'Families here may have a hard time getting enough healthy food.'
  if (t.cls === 'insufficient') return 'This does not mean need is low here.'
  return 'We did not find both signs of high need here. Some families can still need help.'
}

export function cardSites(t: Tract): string | null {
  if (t.sitesInTract === 0) return null // the caller shows the fixed REQ-3 sentence instead
  return t.sitesInTract === 1
    ? 'There is 1 Second Harvest food site inside this neighborhood.'
    : `There are ${t.sitesInTract} Second Harvest food sites inside this neighborhood.`
}

export function cardLoad(t: Tract): string | null {
  if (t.standinLoad === null) return null
  return `Counting sites outside the neighborhood too, each nearby site is shared by about ${fmt.format(t.standinLoad)} people from here (rough stand-in).`
}

const SURE_WORD: Record<ConfLevel, string> = {
  High: 'High',
  Medium: 'Medium',
  Low: 'Low',
  'Not rated': 'Not rated',
}

// "How sure are we" in plain words. Uses the same tests as model.confidence().
export function cardHowSure(t: Tract, cut: number, level: ConfLevel): string {
  const head = `How sure are we: ${SURE_WORD[level]}.`
  if (level === 'Not rated') return `${head} Key facts are missing, so we cannot rate it.`
  const reasons: string[] = []
  const l = limits(t, cut)
  if (level !== 'High' && l.size.length) {
    if ((t.households ?? 0) < SMALL_HOUSEHOLDS)
      reasons.push(`Fewer than ${SMALL_HOUSEHOLDS} homes are here, so the numbers can swing.`)
    if ((t.groupQuartersPct ?? 0) > GROUP_QUARTERS_PCT)
      reasons.push('Many people here live in shared housing, like dorms, which the numbers leave out.')
  }
  if (level !== 'High' && l.near.length)
    reasons.push(
      `Poverty here is within ${NEAR_CUT_POINTS} points of our line, so a small change could flip the color.`,
    )
  if (reasons.length === 0)
    reasons.push(
      level === 'High'
        ? 'We found no warning signs in the data we have.'
        : 'We found no warning signs, but we cannot yet check how far off the survey could be.',
    )
  return `${head} ${reasons.join(' ')} The way we rate this is a draft.`
}

// REQ-5: the explore level says plainly when a fact is missing; the list is in the detail level.
export function cardMissing(t: Tract): string | null {
  if (t.missing.length === 0) return null
  const statewide = t.missing.every((m) => m.includes('CDC PLACES'))
  return statewide
    ? 'Some health survey facts are missing for all of Florida, and so for here too. See How we know this.'
    : 'Some facts about this neighborhood are missing. See How we know this.'
}

// ---------------- Sources (detail level) ----------------

// Base sources of the map and card. Compare-with layers add their own (COMPARE_LAYERS[i].sources).
// IDs are from docs/data-sources.md. The note says how much to trust the source.
export const BASE_SOURCES: { id: string; label: string; note?: string }[] = [
  { id: 'DS-H2', label: 'ACS 2024 5-year S1701, poverty rate', note: 'Survey estimate.' },
  { id: 'DS-H1', label: 'ACS 2024 5-year S2201, SNAP households', note: 'Survey estimate.' },
  {
    id: 'DS-H6',
    label: 'USDA ERS 2025 SRAM/FARA, driving-distance LILA flag',
  },
  {
    id: 'DS-X12',
    label: 'Second Harvest food finder, partner sites',
    note: 'One food bank network only; hours change. Redistribution permission was not obtained (the data is public).',
  },
  { id: 'DS-X27', label: 'Census Bureau geocoder, sites matched to tracts' },
  {
    id: 'DS-X24',
    label: 'Census 2020 blocks, population for the stand-in reach and load',
    note: 'April 2020 counts with privacy noise; only tract sums are used.',
  },
  {
    id: 'DS-X7b',
    label: 'ACS 2024 5-year B08201, no-vehicle households (via Census Reporter)',
    note: 'An estimate that is not proven to measure transport need (finding F-1). Not from the bulk file; check before quoting.',
  },
  {
    id: 'DS-X16b',
    label: 'FEMA National Risk Index, tract layer',
    note: 'From the ArcGIS service, not the bulk file; check before quoting.',
  },
  {
    id: 'DS-H7',
    label: 'CDC PLACES 2025',
    note: 'Social-needs columns are blank for all of Florida (finding F-1).',
  },
  { id: 'DS-X3b', label: 'CBPP SNAP Tracker, Florida monthly participants', note: 'Statewide only.' },
  { id: 'DS-X9b', label: 'Feeding America Map the Meal Gap 2024, county food insecurity' },
]
