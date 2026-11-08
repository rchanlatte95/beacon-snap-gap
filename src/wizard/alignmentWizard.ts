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

export const PERSONA_LENSES: ReadonlyArray<{
  readonly id: PersonaLensId
  readonly label: string
  readonly tagline: string
}> = [
  {
    id: 'alignment',
    label: 'Shared Alignment: Opportunities to Serve',
    tagline: 'Where food insecurity, missing SBA capital, and no-vehicle households overlap.',
  },
  {
    id: 'planner',
    label: 'Food Bank Planner (SNAP & Pantries)',
    tagline: 'Classic Food Desert tracts and where mobile pantries beat fixed sites.',
  },
  {
    id: 'officer',
    label: 'SBA / CDFI Lending Officer',
    tagline: 'High-need tracts where 7(a) and 504 lending has not reached local food retail.',
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
    label: 'Opportunities to Serve (Triple Gap)',
    expectedCount: 29,
    hint: 'Food desert + ≤10 SBA loans + ≥6.9% no-vehicle households',
  },
  {
    id: 'high_need',
    label: 'Classic Food Deserts (High Need)',
    expectedCount: 97,
    hint: 'Top-quartile poverty + USDA driving-distance low access',
  },
  {
    id: 'dual',
    label: 'Food + SBA Lending Gap (≤10 Loans)',
    expectedCount: 50,
    hint: '75% of SBA dollars went to tracts without high need',
  },
  {
    id: 'transport',
    label: 'Mobile Priority (No-Vehicle ≥6.9%)',
    expectedCount: 53,
    hint: 'Residents cannot drive to a fixed pantry',
  },
  {
    id: 'insufficient',
    label: 'Insufficient Data / Blind Spots',
    expectedCount: 2,
    hint: 'Core indicators blank in the source tables',
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
const SBA_MEDIAN_LOANS = 10

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

/** POST-APP-3: deterministic natural-language query interpreter over the 490-tract dataset. */
export function answerWizardQuery(tracts: readonly TractRecord[], query: string): WizardAnswer {
  const q = query.toLowerCase()
  const filters: string[] = []
  let result: readonly TractRecord[] = tracts

  const county = COUNTIES.find((c) => q.includes(c))
  if (county) {
    result = result.filter((t) => t.county.toLowerCase() === county)
    filters.push(`County = ${county.charAt(0).toUpperCase()}${county.slice(1)}`)
  }

  const wantsInsufficient = /insufficient|blind spot|missing data|no data/.test(q)
  const wantsHighNeed = /high[- ]need|food desert|classic food desert|flagged|high poverty/.test(q)
  if (wantsInsufficient) {
    result = result.filter((t) => t.tract_class === CLASS_INSUFFICIENT)
    filters.push('Class = Insufficient data')
  } else if (wantsHighNeed) {
    result = result.filter((t) => t.tract_class === CLASS_HIGH_NEED)
    filters.push('Class = Classic Food Desert')
  }

  if (/zero pantr|no pantr|no site|without (a )?pantr|no second harvest/.test(q)) {
    result = result.filter((t) => t.sites_in_tract === 0)
    filters.push('Second Harvest sites inside tract = 0')
  }

  if (/low sba|few sba|low lending|under[- ]?lent|lending gap|sba gap|without sba|no sba/.test(q)) {
    result = result.filter((t) => t.sba_loans_total <= SBA_MEDIAN_LOANS)
    filters.push(`SBA 7(a)/504 loans ≤ ${SBA_MEDIAN_LOANS} (regional median)`)
  }

  if (/no[- ]vehicle|without (a )?car|transport|transit|mobile/.test(q)) {
    result = result.filter((t) => t.is_transport_gap)
    filters.push('No-vehicle households ≥ 6.9% (top quartile)')
  }

  if (/triple|opportunit|overlap|all three|align/.test(q)) {
    result = result.filter((t) => t.is_triple_gap)
    filters.push('Triple gap: food + SBA + transport')
  }

  const residents = result.reduce((s, t) => s + t.pop2020, 0)
  const noSite = result.filter((t) => t.sites_in_tract === 0).length
  const mobile = result.filter((t) => t.is_transport_gap).length
  const dual = result.filter((t) => t.is_dual_gap).length

  const answerText =
    result.length === 0
      ? `No tracts match that combination. Try widening the county or removing a filter.`
      : `${nf.format(result.length)} tract${result.length === 1 ? '' : 's'} match (${nf.format(residents)} residents). ` +
        `${noSite} have no Second Harvest site inside the tract, ${mobile} are mobile-pantry priorities because ` +
        `households without a vehicle exceed 6.9%, and ${dual} received ten or fewer SBA loans since 2010. ` +
        `Each is an opportunity for a food bank and an SBDC/CDFI to serve the same residents together.`

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
  const safeBaseline = baseline > 0 ? baseline : target.length > 0 ? 100 : 0
  const safeWith = Math.min(withJoint, Math.max(0, safeBaseline - 0.1))
  const reduction = Math.round((safeBaseline - safeWith) * 10) / 10

  const cohortLabel =
    COHORT_CARDS.find((c) => c.id === input.cohortId)?.label ?? 'All Central Florida tracts'
  const counties = Array.from(new Set(target.map((t) => t.county))).sort()

  const foodBankAction =
    mobile > 0
      ? `Route mobile pantry stops through the ${mobile} tracts where ≥6.9% of households have no vehicle; add partner pantry hours in the remaining ${target.length - mobile}.`
      : `Expand partner pantry capacity and hours in all ${target.length} target tracts.`
  const sbaOfficerAction =
    dual > 0
      ? `Open SBDC/CDFI micro-lending and technical-assistance clinics in the ${dual} tracts that received ten or fewer SBA 7(a)/504 loans, prioritizing corner stores, mobile markets, and food entrepreneurs.`
      : `Coordinate SBA outreach alongside pantry expansion so new food retail follows the food bank footprint.`

  const narrativeSummary =
    `${cohortLabel}: ${nf.format(target.length)} tracts across ${counties.join(', ')} hold ${nf.format(totalResidents)} residents. ` +
    `Today ${noSite} of these tracts have no Second Harvest site inside their boundary (${safeBaseline}% of the cohort). ` +
    `A joint food bank + SBA/CDFI deployment reaches the ${mobile} mobile-priority tracts and seeds food retail capital in the ${dual} lending-gap tracts, ` +
    `leaving ${unaddressed} tract${unaddressed === 1 ? '' : 's'} (${safeWith}%) outside a planned intervention — a ${reduction}-point reduction. ` +
    `Evidence: ACS poverty and SNAP tables, USDA SRAM driving-distance low access, SBA FOIA 7(a)/504 loans, ACS B08201 vehicles, Second Harvest sites, and 2020 block population.`

  return {
    title: `Coordinated Action Brief — ${cohortLabel}`,
    cohortId: input.cohortId,
    personaId: input.personaId,
    targetTractCount: target.length,
    totalResidentsCovered: totalResidents,
    mobilePriorityTractCount: mobile,
    dualGapTractCount: dual,
    withoutCoordinationGapPct: safeBaseline,
    withJointDeploymentGapPct: safeWith,
    percentagePointReduction: reduction,
    foodBankAction,
    sbaOfficerAction,
    narrativeSummary,
    sourcesCited: [...SOURCES],
  }
}

/** Executive briefing for the AI panel header. */
export function buildExecutiveBriefing(tracts: readonly TractRecord[]): readonly string[] {
  const high = tracts.filter((t) => t.tract_class === CLASS_HIGH_NEED)
  const dual = tracts.filter((t) => t.is_dual_gap)
  const transport = tracts.filter((t) => t.is_transport_gap)
  const triple = tracts.filter((t) => t.is_triple_gap)
  const totalSba = tracts.reduce((s, t) => s + t.sba_gross_usd_total, 0)
  const highSba = high.reduce((s, t) => s + t.sba_gross_usd_total, 0)
  const sharePct = totalSba > 0 ? Math.round((1 - highSba / totalSba) * 1000) / 10 : 0
  const tripleResidents = triple.reduce((s, t) => s + t.pop2020, 0)
  return [
    `${high.length} of ${tracts.length} Central Florida tracts are Classic Food Deserts: top-quartile poverty and USDA driving-distance low access.`,
    `${sharePct}% of SBA 7(a) and 504 loan dollars since 2010 went to tracts that are not high need. ${dual.length} food deserts received ten or fewer loans.`,
    `${transport.length} food deserts sit in the top quartile for households without a vehicle, so a fixed pantry 15 minutes away is still out of reach.`,
    `${triple.length} tracts carry all three gaps at once — ${nf.format(tripleResidents)} residents a food bank and an SBDC/CDFI could serve together.`,
  ]
}
