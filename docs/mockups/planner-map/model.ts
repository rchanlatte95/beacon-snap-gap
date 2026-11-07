// Shared types, labels, number formats and the candidate confidence rules for the mock-up.
// Moved from PlannerMock.tsx without behavior change (scaffold for parallel work).
import type { FeatureCollection } from 'geojson'

export type Cls = 'desert' | 'nogap' | 'insufficient'
export type Coverage = 'load' | 'reach'
export type SortKey = 'poverty' | 'load' | 'snap'

export interface Tract {
  geoid: string
  name: string
  county: string
  cls: Cls
  drawn: boolean
  households: number | null
  snapHouseholds: number | null
  pctSnap: number | null
  pctPoverty: number | null
  lilaDD: number | null
  urban: number | null
  medianFamilyIncome: number | null
  groupQuartersPct: number | null
  noVehiclePct: number | null
  placesFoodInsecurity: number | null
  nriRisk: string | null
  socialVulnerability: string | null
  pop2020: number
  sitesInTract: number
  standinReachPct: number | null
  standinSitesInReach: number
  standinLoad: number | null
  missing: string[]
  centroid: [number, number] | null
}

export interface Records {
  generated: string
  povertyCut: { value: number; method: string; tracts: number }
  standinReachMiles: number
  counts: Record<Cls, number>
  countyLabels: { name: string; lngLat: [number, number] }[]
  snapTrend: { month: string; participants: number | null }[]
  mealGap: { county: string; rate: string; people: number | null }[]
  tracts: Tract[]
}

export interface Loaded {
  records: Records
  tracts: FeatureCollection
  counties: FeatureCollection
  sites: FeatureCollection
  // Parsed dataFile of each Compare-with layer, by layer id.
  extras: Record<string, unknown>
}

export const CLASS_LABEL: Record<Cls, string> = {
  desert: 'Classic Food Desert (high need)',
  nogap: 'No gap flagged',
  insufficient: 'Insufficient data',
}
export const NO_SITE_TEXT = 'No Second Harvest site found under this rule. Other food sources may exist.'

export const fmt = new Intl.NumberFormat('en-US')
export const pct = (v: number | null) => (v === null ? 'blank' : `${v.toFixed(1)}%`)
export const n = (v: number | null) => (v === null ? 'blank' : fmt.format(v))
export const featureId = (geoid: string) => Number(geoid.slice(2))

// Confidence: three candidate rules to compare. None is decided; a human picks one
// before any rule goes in a contract. The thresholds below are stand-ins.
export type ConfRule = 'size' | 'near' | 'count'
export type ConfLevel = 'High' | 'Medium' | 'Low' | 'Not rated'
export const CONF_LEVELS: ConfLevel[] = ['High', 'Medium', 'Low', 'Not rated']
export const SMALL_HOUSEHOLDS = 500
export const GROUP_QUARTERS_PCT = 20
export const NEAR_CUT_POINTS = 2
export const CONF_RULES: { id: ConfRule; name: string; summary: string }[] = [
  {
    id: 'size',
    name: 'A. Size and group quarters',
    summary: `Low if under ${SMALL_HOUSEHOLDS} households or over ${GROUP_QUARTERS_PCT}% group quarters, else Medium.`,
  },
  {
    id: 'near',
    name: 'B. Near the cut',
    summary: `Low if the tract is LILA and its poverty rate is within ${NEAR_CUT_POINTS} points of the cut, else Medium.`,
  },
  {
    id: 'count',
    name: 'C. Count of limits',
    summary: 'Counts the A and B tests: none is High, one is Medium, two or more is Low.',
  },
]
export const NO_MOE =
  'ACS 5-year margins of error are not in the repo for the poverty rate, so no rule checks them.'

export function limits(t: Tract, cut: number): { size: string[]; near: string[] } {
  const size: string[] = []
  const near: string[] = []
  if ((t.households ?? 0) < SMALL_HOUSEHOLDS)
    size.push(`Fewer than ${SMALL_HOUSEHOLDS} households, so ACS estimates are less stable.`)
  if ((t.groupQuartersPct ?? 0) > GROUP_QUARTERS_PCT)
    size.push(
      `${t.groupQuartersPct?.toFixed(0)}% of residents live in group quarters (for example dorms), which ACS household rates leave out.`,
    )
  if (t.lilaDD === 1 && t.pctPoverty !== null && Math.abs(t.pctPoverty - cut) < NEAR_CUT_POINTS)
    near.push(
      `The poverty rate (${t.pctPoverty.toFixed(1)}%) is within ${NEAR_CUT_POINTS} points of the ${cut.toFixed(3)}% cut, so a small change in the estimate could change the class.`,
    )
  return { size, near }
}

export function confidence(t: Tract, cut: number, rule: ConfRule): { level: ConfLevel; why: string[] } {
  if (t.cls === 'insufficient')
    return { level: 'Not rated', why: ['A core indicator is blank, so no class is computed.'] }
  const l = limits(t, cut)
  if (rule === 'count') {
    const all = [...l.size, ...l.near]
    const level = all.length === 0 ? 'High' : all.length === 1 ? 'Medium' : 'Low'
    return { level, why: all.length ? all : ['No limit found by the A or B tests.', NO_MOE] }
  }
  const hits = rule === 'size' ? l.size : l.near
  if (hits.length) return { level: 'Low', why: hits }
  return {
    level: 'Medium',
    why: [`No limit found by this rule. ${NO_MOE} The label stays below High for that reason.`],
  }
}
