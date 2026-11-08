/**
 * Opportunities to Serve — deterministic AI insight & coordinated action engine (SLICE-1).
 *
 * Contract-Implementation Independence (CL11-F): this module does NOT import from
 * contracts/planner-map.app.contract.ts. It redeclares its constants and types independently;
 * tests under tests/ assert alignment.
 */

export type PersonaLensId = 'alignment' | 'planner' | 'officer'
export type CohortId = 'all' | 'triple' | 'high_need' | 'dual' | 'transport' | 'insufficient'

export const CLASS_HIGH_NEED = 'Classic Food Desert'
export const CLASS_NO_GAP = 'No gap flagged'
export const CLASS_INSUFFICIENT = 'Insufficient data'

// The lens labels are pinned by contracts/planner-map.app.contract.ts (POST-APP-1).
export const PERSONA_LENSES: ReadonlyArray<{
  readonly id: PersonaLensId
  readonly label: string
  readonly headline: string
  readonly tagline: string
}> = [
  {
    id: 'alignment',
    label: 'Both partners',
    headline: 'Where food banks and lenders can help together',
    tagline: 'Red areas have all three gaps. Orange areas are other food deserts.',
  },
  {
    id: 'planner',
    label: 'Food bank',
    headline: 'Where food banks are needed most',
    tagline:
      'Food deserts, and the places where a mobile pantry may reach more people than a fixed one.',
  },
  {
    id: 'officer',
    label: 'Small business lender',
    headline: 'Where small business loans could help most',
    tagline: 'Food deserts with the fewest SBA loans for their population since 2010.',
  },
]

export const COHORT_CARDS: ReadonlyArray<{
  readonly id: Exclude<CohortId, 'all'>
  readonly label: string
  readonly expectedCount: number
  readonly hint: string
}> = [
  {
    id: 'triple',
    label: 'All three gaps',
    expectedCount: 12,
    hint: 'Food desert, few business loans, many homes with no car',
  },
  {
    id: 'high_need',
    label: 'Classic Food Deserts',
    expectedCount: 97,
    hint: 'High poverty and far from a grocery store',
  },
  {
    id: 'dual',
    label: 'Few business loans',
    expectedCount: 26,
    hint: 'Food deserts in the lowest quarter for SBA loans per 1,000 people',
  },
  {
    id: 'transport',
    label: 'Many with no car',
    expectedCount: 53,
    hint: 'Food deserts where 6.9% or more of homes have no car',
  },
  {
    id: 'insufficient',
    label: 'Insufficient data',
    expectedCount: 2,
    hint: 'Key numbers are blank, so we cannot sort them',
  },
]

export interface TractRecord {
  readonly geoid: string
  readonly name: string
  readonly county: string
  readonly tract_class: string
  readonly drawn: boolean
  readonly households: number | null
  readonly snap_households: number | null
  readonly pct_hh_snap: number | null
  readonly pct_poverty: number | null
  readonly lila_flag: number | null
  readonly sba_loans_total: number
  readonly sba_gross_usd_total: number
  readonly sba_jobs_supported: number
  readonly pct_no_vehicle: number | null
  readonly median_household_income: number | null
  readonly median_household_income_moe90: number | null
  readonly income_status: string
  readonly urban: number | null
  readonly group_quarters_pct: number | null
  readonly nri_risk: string | null
  readonly social_vulnerability: string | null
  readonly pop2020: number
  readonly sites_in_tract: number
  readonly sites_in_reach: number
  readonly pantry_load: number | null
  readonly is_dual_gap: boolean
  readonly is_transport_gap: boolean
  readonly is_triple_gap: boolean
  readonly confidence_level: string
  readonly confidence_reason: string
  readonly recommended_action: string
  readonly missing_indicators: readonly string[]
  readonly centroid: readonly [number, number] | null
  // REQ-55 (Z-2 2-A): index k is the distance k * 0.5 miles, written by the Build.
  readonly reach_share: readonly (number | null)[]
  readonly reach_sites: readonly number[]
  readonly nearest_block_miles: number | null
}

export interface WizardAnswer {
  readonly matchedTracts: readonly TractRecord[]
  readonly answerText: string
  readonly appliedFilters: readonly string[]
}

export interface CoordinatedActionBrief {
  readonly title: string
  readonly cohortId: CohortId
  readonly personaId: PersonaLensId
  readonly targetTractCount: number
  readonly totalResidentsCovered: number
  readonly mobilePriorityTractCount: number
  readonly dualGapTractCount: number
  readonly withoutCoordinationGapPct: number
  readonly withJointDeploymentGapPct: number
  readonly percentagePointReduction: number
  readonly foodBankAction: string
  readonly sbaOfficerAction: string
  readonly narrativeSummary: string
  readonly sourcesCited: readonly string[]
}

const SOURCES = [
  'DS-H2',
  'DS-H1',
  'DS-H6',
  'DS-X5',
  'DS-X7b',
  'DS-X12',
  'DS-X24',
  'DS-X28',
] as const
const COUNTIES = ['orange', 'seminole', 'lake', 'osceola'] as const
// Z-21: a brief whose reduction is zero says so.
export const NO_REACH_TEXT = 'This plan does not reach these neighborhoods.'

const nf = new Intl.NumberFormat('en-US')

export function filterTractsByCohort(
  tracts: readonly TractRecord[],
  cohortId: CohortId,
): readonly TractRecord[] {
  switch (cohortId) {
    case 'all':
      return tracts
    case 'triple':
      return tracts.filter((t) => t.is_triple_gap)
    case 'high_need':
      return tracts.filter((t) => t.tract_class === CLASS_HIGH_NEED)
    case 'dual':
      return tracts.filter((t) => t.is_dual_gap)
    case 'transport':
      return tracts.filter((t) => t.is_transport_gap)
    case 'insufficient':
      return tracts.filter((t) => t.tract_class === CLASS_INSUFFICIENT)
    default: {
      const exhaustive: never = cohortId
      return exhaustive
    }
  }
}

/**
 * POST-APP-3: deterministic natural-language query interpreter over the 490-tract dataset.
 * `noVehicleCut` is the no-car cut in force (REQ-65), shown in the transport filter.
 */
export function answerWizardQuery(
  tracts: readonly TractRecord[],
  query: string,
  noVehicleCut?: number,
): WizardAnswer {
  const q = query.toLowerCase()
  const filters: string[] = []
  let result: readonly TractRecord[] = tracts

  const county = COUNTIES.find((c) => q.includes(c))
  if (county) {
    result = result.filter((t) => t.county.toLowerCase() === county)
    filters.push(`${county.charAt(0).toUpperCase()}${county.slice(1)} County`)
  }

  const wantsInsufficient = /insufficient|blind spot|missing data|no data/.test(q)
  const wantsHighNeed = /high[- ]need|food desert|classic food desert|flagged|high poverty/.test(q)
  if (wantsInsufficient) {
    result = result.filter((t) => t.tract_class === CLASS_INSUFFICIENT)
    filters.push('Insufficient data')
  } else if (wantsHighNeed) {
    result = result.filter((t) => t.tract_class === CLASS_HIGH_NEED)
    filters.push('Classic Food Deserts')
  }

  if (/zero pantr|no pantr|no site|without (a )?pantr|no second harvest/.test(q)) {
    result = result.filter((t) => t.sites_in_tract === 0)
    filters.push('No Second Harvest site inside')
  }

  if (/low sba|few sba|low lending|under[- ]?lent|lending gap|sba gap|without sba|no sba/.test(q)) {
    // REQ-19: the Build's lending-gap flag, never a raw loan count.
    result = result.filter((t) => t.is_dual_gap)
    filters.push('Food desert with few SBA loans for its population')
  }

  if (/no[- ]vehicle|without (a )?car|transport|transit|mobile/.test(q)) {
    result = result.filter((t) => t.is_transport_gap)
    filters.push(
      noVehicleCut === undefined
        ? 'Food desert where many homes have no car'
        : `Food desert where ${Number(noVehicleCut.toFixed(3))}% or more of homes have no car`,
    )
  }

  if (/triple|opportunit|overlap|all three|align/.test(q)) {
    result = result.filter((t) => t.is_triple_gap)
    filters.push('All three gaps')
  }

  const residents = result.reduce((s, t) => s + t.pop2020, 0)
  const noSite = result.filter((t) => t.sites_in_tract === 0).length
  const mobile = result.filter((t) => t.is_transport_gap).length
  const dual = result.filter((t) => t.is_dual_gap).length

  const answerText =
    result.length === 0
      ? `No neighborhoods match. Try another county or fewer words.`
      : `${nf.format(result.length)} neighborhood${result.length === 1 ? '' : 's'} match, with ${nf.format(residents)} people. ` +
        `${noSite} have no Second Harvest site inside. ` +
        `In ${mobile}, many homes have no car. ` +
        `${dual} got few SBA loans for their population since 2010.`

  return { matchedTracts: result, answerText, appliedFilters: filters }
}

/** POST-APP-3: one-click Coordinated Action Brief with a deterministic counterfactual. */
export function generateCoordinatedActionBrief(input: {
  readonly tracts: readonly TractRecord[]
  readonly cohortId: CohortId
  readonly personaId: PersonaLensId
}): CoordinatedActionBrief {
  const target = filterTractsByCohort(input.tracts, input.cohortId)
  const totalResidents = target.reduce((s, t) => s + t.pop2020, 0)
  const mobile = target.filter((t) => t.is_transport_gap).length
  const dual = target.filter((t) => t.is_dual_gap).length
  const noSite = target.filter((t) => t.sites_in_tract === 0).length

  // Counterfactual: baseline = share of target tracts with no site inside the tract (uncoordinated status quo).
  // Joint deployment = mobile routes reach every transport-priority tract and SBA micro-lending opens
  // a food retail point in every dual-gap tract, leaving only tracts that are neither.
  const baseline = target.length > 0 ? Math.round((noSite / target.length) * 1000) / 10 : 0
  const unaddressed = target.filter(
    (t) => t.sites_in_tract === 0 && !t.is_transport_gap && !t.is_dual_gap,
  ).length
  const withJoint = target.length > 0 ? Math.round((unaddressed / target.length) * 1000) / 10 : 0
  // POST-APP-3 (Z-21): report the computed shares as they are, including a zero reduction.
  const reduction = Math.round((baseline - withJoint) * 10) / 10

  const cohortLabel =
    COHORT_CARDS.find((c) => c.id === input.cohortId)?.label ?? 'All neighborhoods'
  const counties = Array.from(new Set(target.map((t) => t.county))).sort()
  const rest = target.length - mobile
  const plural = (n: number, word: string) => `${nf.format(n)} ${word}${n === 1 ? '' : 's'}`

  const foodBankAction =
    mobile > 0
      ? `Send mobile pantry stops to the ${plural(mobile, 'neighborhood')} where many homes have no car.` +
        (rest > 0 ? ` Add pantry hours in the other ${nf.format(rest)}.` : '')
      : `Add pantry space and hours in all ${plural(target.length, 'neighborhood')}.`
  const sbaOfficerAction =
    dual > 0
      ? `Hold small business loan and coaching clinics in the ${plural(dual, 'neighborhood')} with few SBA loans for their population. Start with corner stores, mobile markets and food businesses.`
      : `Plan small business help next to new pantry sites, so new food stores can follow.`

  const narrativeSummary =
    `${cohortLabel}: ${plural(target.length, 'neighborhood')} with ${nf.format(totalResidents)} people. ` +
    `Counties: ${counties.join(', ')}. ` +
    `Today ${noSite} of them (${baseline}%) have no Second Harvest site inside. ` +
    `Suppose the food bank serves the ${mobile} with many homes that have no car, and lenders help the ${dual} with few loans. ` +
    (reduction === 0
      ? NO_REACH_TEXT
      : unaddressed === 0
        ? `Then every one of them would have a plan.`
        : `Then ${plural(unaddressed, 'neighborhood')} (${withJoint}%) would still have no plan. That is ${reduction} points lower than today.`)

  return {
    title: `Action plan: ${cohortLabel}`,
    cohortId: input.cohortId,
    personaId: input.personaId,
    targetTractCount: target.length,
    totalResidentsCovered: totalResidents,
    mobilePriorityTractCount: mobile,
    dualGapTractCount: dual,
    withoutCoordinationGapPct: baseline,
    withJointDeploymentGapPct: withJoint,
    percentagePointReduction: reduction,
    foodBankAction,
    sbaOfficerAction,
    narrativeSummary,
    sourcesCited: [...SOURCES],
  }
}

export interface Insight {
  readonly figure: string
  readonly text: string
  /** Matches the map color: triple = red, high = orange. */
  readonly tone: 'plain' | 'high' | 'triple'
  readonly sourceIds: readonly string[]
}

export interface BriefingContext {
  readonly snapTrend?: readonly { readonly month: string; readonly participants: number | null }[]
  readonly mealGap?: readonly {
    readonly county: string
    readonly rate: string
    readonly people: number | null
  }[]
}

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const

function monthName(ym: string): string {
  const [y, m] = ym.split('-')
  return `${MONTHS[Number(m) - 1] ?? m} ${y}`
}

/** Household-weighted share of homes with no car, in percent. */
function noCarShare(tracts: readonly TractRecord[]): number | null {
  let homes = 0
  let noCar = 0
  for (const t of tracts) {
    if (t.pct_no_vehicle === null || !t.households) continue
    homes += t.households
    noCar += (t.pct_no_vehicle / 100) * t.households
  }
  return homes > 0 ? (noCar / homes) * 100 : null
}

/** Plain-language findings for the side panel. Each one is computed from the bundle. */
export function buildExecutiveBriefing(
  tracts: readonly TractRecord[],
  context: BriefingContext = {},
): readonly Insight[] {
  const out: Insight[] = []

  // CBPP SNAP Tracker (DS-X3b): Florida, the latest month against the same month a year before.
  const trend = (context.snapTrend ?? []).filter((r) => r.participants !== null)
  const last = trend.at(-1)
  if (last && last.participants !== null) {
    const [y, m] = last.month.split('-')
    const before = trend.find((r) => r.month === `${Number(y) - 1}-${m}`)
    if (before && before.participants) {
      const change = (last.participants - before.participants) / before.participants
      out.push({
        figure: `${Math.abs(Math.round(change * 100))}%`,
        sourceIds: ['DS-X3b'],
        tone: 'plain',
        text: `${change < 0 ? 'fewer' : 'more'} Floridians got SNAP in ${monthName(last.month)} than a year before. ${change < 0 ? 'More families may turn to food banks.' : ''}`.trim(),
      })
    }
  }

  // Feeding America Map the Meal Gap 2024 (DS-X9b): the four counties.
  const meal = (context.mealGap ?? []).filter((r) => r.people !== null)
  const top = [...meal].sort((a, b) => parseFloat(b.rate) - parseFloat(a.rate))[0]
  if (top) {
    const people = meal.reduce((s, r) => s + (r.people ?? 0), 0)
    const name = top.county.charAt(0).toUpperCase() + top.county.slice(1)
    out.push({
      figure: nf.format(Math.round(people / 1000) * 1000),
      sourceIds: ['DS-X9b'],
      tone: 'plain',
      text: `people in these four counties may not have enough to eat (2024). ${name} County has the highest rate: ${top.rate}.`,
    })
  }

  const high = tracts.filter((t) => t.tract_class === CLASS_HIGH_NEED)
  const others = tracts.filter((t) => t.tract_class === CLASS_NO_GAP)
  const pop = tracts.reduce((s, t) => s + t.pop2020, 0)
  const highPop = high.reduce((s, t) => s + t.pop2020, 0)
  const carHigh = noCarShare(high)
  const carOther = noCarShare(others)
  if (highPop > 0) {
    out.push({
      figure: `1 in ${Math.round(pop / highPop)}`,
      sourceIds: ['DS-H2', 'DS-H6', 'DS-X7b', 'DS-X24'],
      tone: 'high',
      text:
        `people here live in a food desert. ` +
        (carHigh !== null && carOther !== null
          ? `There, ${carHigh.toFixed(1)}% of homes have no car. Elsewhere, ${carOther.toFixed(1)}% do.`
          : ''),
    })
  }

  const triple = tracts.filter((t) => t.is_triple_gap)
  const tripleResidents = triple.reduce((s, t) => s + t.pop2020, 0)
  out.push({
    figure: nf.format(triple.length),
    sourceIds: ['DS-H2', 'DS-H6', 'DS-X5', 'DS-X7b', 'DS-X24'],
    tone: 'triple',
    text: `neighborhoods have all three gaps. ${nf.format(tripleResidents)} people live there. They are a good place to start.`,
  })
  return out
}
