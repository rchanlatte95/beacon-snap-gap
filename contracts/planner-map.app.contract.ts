/**
 * App domain contract for SLICE-1: Beacon "Opportunities to Serve" cross-agency alignment map & AI action wizard.
 * Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 17: PR #18 refactor, Z-24 A, Z-25 A).
 * Cross-reference: Build contract contracts/planner_map_contract.py (IP-4 static bundle).
 *
 * The implementation under src/ MUST NOT import this module (CL11-F).
 * Tests under tests/ import both this contract and src/ to assert alignment.
 */

export type VerificationMethod = 'test' | 'execution' | 'tool'

export interface Clause {
  readonly verification: VerificationMethod
  readonly text: string
  readonly requirements: readonly string[]
}

// --- 1. Importable specification constants -------------------------------------------------

export const PERSONA_LENSES = [
  { id: 'alignment', label: 'Both partners' },
  { id: 'planner', label: 'Food bank' },
  { id: 'officer', label: 'Small business lender' },
] as const

export type PersonaLensId = (typeof PERSONA_LENSES)[number]['id']

// The counts are binding (POST-APP-1). The labels are reference wording only: the screen may word
// a card differently (Ketema, 2026-11-08).
export const COHORT_CARDS = [
  { id: 'triple', label: 'Opportunities to Serve (Triple Gap)', expectedCount: 12 },
  { id: 'high_need', label: 'Classic Food Deserts (High Need)', expectedCount: 97 },
  { id: 'dual', label: 'Food + SBA Lending Gap (Bottom Quartile per 1,000 Residents)', expectedCount: 26 },
  { id: 'transport', label: 'Mobile Priority (No-Vehicle ≥6.9%)', expectedCount: 53 },
  { id: 'insufficient', label: 'Insufficient Data / Blind Spots', expectedCount: 2 },
] as const

export type CohortId = (typeof COHORT_CARDS)[number]['id'] | 'all'

export const CLASS_HIGH_NEED = 'Classic Food Desert'
export const CLASS_NO_GAP = 'No gap flagged'
export const CLASS_INSUFFICIENT = 'Insufficient data'

export const NO_SITE_CARD_TEXT =
  'No Second Harvest site found under this rule. Other food sources may exist.'
// Z-21: the narrative of a Coordinated Action Brief whose reduction is zero includes this sentence.
export const NO_REACH_TEXT = 'This plan does not reach these neighborhoods.'
export const FORBIDDEN_PHRASES = ['no food access', 'no access'] as const

export const DATAKIND_ATTRIBUTION_URL = 'http://www.datakind.org'
export const CC_BY_STATEMENT = 'CC BY 4.0'
export const BASE_MAP_UNAVAILABLE_TEXT = 'Base map unavailable'
export const OPENFREEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'

// Cycle 17 / REQ-56, REQ-64 (Z-2 2-A): reach comes from the Build's per-step values; the App never measures.
export const REACH_STEP_MILES = 0.5
export const MAX_REACH_MILES = 20
export const DEFAULT_REACH_MILES = 10
// REQ-57 (Z-25 A, amended by Z-28): the reach controls, and the tract card outside its drive-time
// estimate, never state a travel time (a duration in minutes or hours).
export const FORBIDDEN_TIME_PATTERN = /\b\d+(?:\.\d+)?\s*(?:minutes?|mins?|hours?|hrs?)\b/i
// REQ-67 (Z-28, Ryan's design): a drive time appears only in a labeled drive-time estimate.
export const DRIVE_TIME_HEADLINE = 'Estimated drive to a Second Harvest site:'
export const DRIVE_TIME_HEURISTIC_MARK = '(heuristic)'
// REQ-59, REQ-65 (Z-24 A): the three cuts, chosen from the Build's named percentiles.
export const CUT_PERCENTILES = {
  poverty: [50, 75, 90],
  no_vehicle: [50, 75, 90],
  sba_rate_per_1000: [10, 25, 50],
} as const
export type CutName = keyof typeof CUT_PERCENTILES
export const DEFAULT_PERCENTILES: Readonly<Record<CutName, number>> = {
  poverty: 75,
  no_vehicle: 75,
  sba_rate_per_1000: 25,
}
export const SBA_RATE_PER_RESIDENTS = 1000
export const SBA_MIN_POPULATION = 1200
// Group counts at the default percentiles (equal to the fixed rule, POST-APP-1).
export const DEFAULT_GROUP_COUNTS = { high_need: 97, dual: 26, transport: 53, triple: 12, insufficient: 2 } as const
// Test surface for the cycle 17 controls (data-testid values; on-screen wording is not bound).
export const APP_TEST_IDS = {
  reachShare: 'reach-share',
  reachSites: 'reach-sites',
  reachPeoplePerSite: 'reach-people-per-site',
  proximityResult: 'proximity-result',
  reachControls: 'reach-controls',
  cutSelect: (cut: CutName) => `cut-select-${cut}`,
  sourceEntry: (id: string) => `source-entry-${id}`,
} as const
export const DISTANCE_SLIDER_NAME = 'Distance limit in miles'

// SLICE-4 batch 2 (Z-26): the App side of the ask call. The server side is
// contracts/query_service_contract.py (PRE-ASK-1, POST-ASK-1, ERRORS-ASK-1, ERRORS-ASK-2).
export const ASK_PATH = '/api/ask'
export const ASK_TIMEOUT_MS = 50_000 // Z-30 (was 20 s, Z-26)
export const AI_UNAVAILABLE_TEXT = 'AI unavailable. Using built-in filters.'
export const SESSION_ENDED_TEXT = 'Your session ended. Sign in again.'
export const SIGN_IN_PATH = '/login' // served by the Gateway (SLICE-5)
export const NOT_RECORDED = 'not recorded'
export const QUESTION_BOX_NAME = 'Ask a question about Central Florida neighborhoods'
export const ASK_TEST_IDS = {
  aiAnswer: 'ai-answer',
  aiNotice: 'ai-notice',
  citationChip: (tableName: string) => `citation-chip-${tableName}`,
} as const

// --- 2. Domain exception classes (every message cites its clause ID) -----------------------

export class AppContractError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options)
    this.name = 'AppContractError'
  }
}

export class HonestyContractError extends AppContractError {
  constructor(message: string) {
    super(message)
    this.name = 'HonestyContractError'
  }
}

export class WizardBriefContractError extends AppContractError {
  constructor(message: string) {
    super(message)
    this.name = 'WizardBriefContractError'
  }
}

export class AttributionContractError extends AppContractError {
  constructor(message: string) {
    super(message)
    this.name = 'AttributionContractError'
  }
}

// --- 3. Immutable typed records ------------------------------------------------------------

export interface TractRecordShape {
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
  // Cycle 17 (POST-RCH-1 in the Build contract): index k is the step k * REACH_STEP_MILES.
  readonly reach_share: readonly (number | null)[]
  readonly reach_sites: readonly number[]
  readonly nearest_block_miles: number | null
}

export interface SourceEntryShape {
  readonly id: string
  readonly label: string
  readonly publisher: string
  readonly period: string
  readonly url: string
  readonly method: string
  readonly limits: string
}

/** The bundle's thresholds.cuts object (POST-CUT-1): {cut: {String(percentile): value}}. */
export type CutsShape = Readonly<Record<CutName, Readonly<Record<string, number>>>>

export interface ReachFacts {
  readonly miles: number
  readonly share: number | null
  readonly sites: number
  readonly peoplePerSite: number | null
  /** null when the tract has no distance data (nearest_block_miles is null). */
  readonly within: boolean | null
}

export interface GapFlags {
  readonly tract_class: string
  readonly is_dual_gap: boolean
  readonly is_transport_gap: boolean
  readonly is_triple_gap: boolean
}

export interface CoordinatedActionBriefShape {
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

// --- 4. Pure callable validators -----------------------------------------------------------

export function validateNoForbiddenPhrases(renderedText: string): string {
  const lower = renderedText.toLowerCase()
  for (const phrase of FORBIDDEN_PHRASES) {
    if (lower.includes(phrase)) {
      throw new HonestyContractError(
        `FORBIDDEN-APP-1 violation: rendered text contains forbidden phrase "${phrase}"`,
      )
    }
  }
  return renderedText
}

export function validateCoordinatedBrief(
  brief: CoordinatedActionBriefShape,
): CoordinatedActionBriefShape {
  if (brief.targetTractCount <= 0) {
    throw new WizardBriefContractError(
      'POST-APP-3 violation: CoordinatedActionBrief targetTractCount must be > 0',
    )
  }
  const expectedReduction =
    Math.round((brief.withoutCoordinationGapPct - brief.withJointDeploymentGapPct) * 10) / 10
  if (
    brief.withJointDeploymentGapPct > brief.withoutCoordinationGapPct ||
    brief.percentagePointReduction < 0 ||
    brief.percentagePointReduction !== expectedReduction
  ) {
    throw new WizardBriefContractError(
      `POST-APP-3 violation: the reduction must equal without minus with and never be negative (without=${brief.withoutCoordinationGapPct}%, with=${brief.withJointDeploymentGapPct}%, reduction=${brief.percentagePointReduction})`,
    )
  }
  if (brief.percentagePointReduction === 0 && !brief.narrativeSummary.includes(NO_REACH_TEXT)) {
    throw new WizardBriefContractError(
      `POST-APP-3 violation: a zero reduction must say "${NO_REACH_TEXT}" (Z-21)`,
    )
  }
  if (!brief.foodBankAction.trim() || !brief.sbaOfficerAction.trim()) {
    throw new WizardBriefContractError(
      'POST-APP-3 violation: CoordinatedActionBrief must specify both foodBankAction and sbaOfficerAction',
    )
  }
  if (brief.sourcesCited.length === 0) {
    throw new WizardBriefContractError(
      'POST-APP-3 violation: CoordinatedActionBrief must cite at least one DS-* source',
    )
  }
  validateNoForbiddenPhrases(brief.narrativeSummary)
  return brief
}

export function validateAttributionFooter(footerText: string, hrefs: readonly string[]): void {
  if (!footerText.includes('DataKind') || !footerText.includes(CC_BY_STATEMENT)) {
    throw new AttributionContractError(
      `POST-APP-5 violation: footer text must credit DataKind and ${CC_BY_STATEMENT}`,
    )
  }
  if (!hrefs.some((h) => h.includes('datakind.org'))) {
    throw new AttributionContractError(
      'POST-APP-5 violation: footer must include a link to www.datakind.org',
    )
  }
}

/** POST-APP-6 oracle: the step a requested distance selects (clamped to 0..20, nearest 0.5; NaN gives the default). */
export function expectedReachMiles(requested: number): number {
  if (!Number.isFinite(requested)) return DEFAULT_REACH_MILES
  const clamped = Math.min(MAX_REACH_MILES, Math.max(0, requested))
  return Math.round(clamped / REACH_STEP_MILES) * REACH_STEP_MILES
}

/** POST-APP-6 oracle: a tract's reach facts at a distance, read from the Build's per-step values only. */
export function expectedReachFacts(tract: TractRecordShape, requested: number): ReachFacts {
  const miles = expectedReachMiles(requested)
  const k = Math.round(miles / REACH_STEP_MILES)
  const sites = tract.reach_sites[k] ?? 0
  return {
    miles,
    share: tract.reach_share[k] ?? null,
    sites,
    peoplePerSite: sites > 0 ? Math.round(tract.pop2020 / sites) : null,
    within: tract.nearest_block_miles === null ? null : tract.nearest_block_miles <= miles,
  }
}

/** POST-APP-8 oracle: a tract's class and gap flags under the chosen percentiles (REQ-19, REQ-20 rules). */
export function expectedGapFlags(
  tract: TractRecordShape,
  cuts: CutsShape,
  percentiles: Readonly<Record<CutName, number>>,
): GapFlags {
  const cut = (name: CutName): number => {
    const value = cuts[name][String(percentiles[name])]
    if (value === undefined) {
      throw new AppContractError(`POST-APP-8 violation: no ${name} cut at percentile ${percentiles[name]}`)
    }
    return value
  }
  if (tract.pct_poverty === null || tract.lila_flag === null) {
    return { tract_class: CLASS_INSUFFICIENT, is_dual_gap: false, is_transport_gap: false, is_triple_gap: false }
  }
  const high = tract.pct_poverty >= cut('poverty') && tract.lila_flag === 1
  const dual =
    high &&
    tract.pop2020 >= SBA_MIN_POPULATION &&
    (tract.sba_loans_total / tract.pop2020) * SBA_RATE_PER_RESIDENTS <= cut('sba_rate_per_1000')
  const transport = high && tract.pct_no_vehicle !== null && tract.pct_no_vehicle >= cut('no_vehicle')
  return {
    tract_class: high ? CLASS_HIGH_NEED : CLASS_NO_GAP,
    is_dual_gap: dual,
    is_transport_gap: transport,
    is_triple_gap: dual && transport,
  }
}

/** FORBIDDEN-APP-2 validator: reach text never states a travel time. */
export function validateNoTravelTime(renderedText: string): string {
  if (FORBIDDEN_TIME_PATTERN.test(renderedText)) {
    throw new HonestyContractError(
      `FORBIDDEN-APP-2 violation: reach text states a travel time: ${JSON.stringify(renderedText.slice(0, 120))}`,
    )
  }
  return renderedText
}

/**
 * POST-APP-16 validator: a drive-time estimate names itself and states its basis. A heuristic
 * estimate carries DRIVE_TIME_HEURISTIC_MARK; a road-network (routed) one does not.
 */
export function validateDriveTimeLabel(estimateText: string, routed: boolean): string {
  const text = estimateText.trim()
  if (!text.startsWith(DRIVE_TIME_HEADLINE)) {
    throw new HonestyContractError(
      `POST-APP-16 violation: a drive time is not inside a drive-time estimate: ${JSON.stringify(text.slice(0, 120))}`,
    )
  }
  if (text.includes(DRIVE_TIME_HEURISTIC_MARK) !== !routed) {
    throw new HonestyContractError(
      `POST-APP-16 violation: the estimate must ${routed ? 'not ' : ''}carry ${DRIVE_TIME_HEURISTIC_MARK}: ${JSON.stringify(text.slice(0, 120))}`,
    )
  }
  return estimateText
}

export interface EmphasisState {
  readonly dimmed: boolean
  readonly emphasized: boolean
  readonly muted: boolean
}

/** POST-APP-10 oracle: the feature state of each drawn tract (not-drawn tracts get none). */
export function expectedEmphasisStates(
  records: readonly Pick<TractRecordShape, 'geoid' | 'drawn'>[],
  focusedGeoids: readonly string[],
  emphasizeGaps: boolean,
): ReadonlyMap<string, EmphasisState> {
  const include = new Set(focusedGeoids)
  const active = emphasizeGaps && include.size > 0
  return new Map(
    records
      .filter((r) => r.drawn)
      .map((r) => [
        r.geoid,
        {
          dimmed: !include.has(r.geoid),
          emphasized: active && include.has(r.geoid),
          muted: active && !include.has(r.geoid),
        },
      ]),
  )
}

export interface AskRequestShape {
  readonly question: string
  readonly reach_miles: number
  readonly percentiles: Readonly<Record<CutName, number>>
}

export interface AskCitationShape {
  readonly table_name: string
  readonly dataset_id: string
  readonly origin_url: string
  readonly publisher: string
  readonly as_of: string
  readonly applied_filter: string
}

export interface AskResultShape {
  readonly columns: readonly string[]
  readonly rows: readonly Readonly<Record<string, string | number | boolean | null>>[]
  readonly row_count: number
  readonly truncated: boolean
  readonly referenced_tables: readonly string[]
}

export interface AskAnswerShape {
  readonly answer: string
  readonly model: string
  readonly results: readonly AskResultShape[]
  readonly citations: readonly AskCitationShape[]
  readonly tracts: readonly string[]
  readonly applied: { readonly reach_miles: number; readonly percentiles: Readonly<Record<CutName, number>> }
}

export type AskOutcomeShape =
  | { readonly ok: true; readonly answer: AskAnswerShape }
  | { readonly ok: false; readonly sessionEnded: boolean; readonly reason: string }

/** Never rejects: every failure is an outcome with ok: false (POST-APP-12). */
export type AskServiceShape = (request: AskRequestShape, signal: AbortSignal) => Promise<AskOutcomeShape>

const CITATION_KEYS = ['table_name', 'dataset_id', 'origin_url', 'publisher', 'as_of', 'applied_filter'] as const

type Unchecked<T> = { readonly [K in keyof T]?: unknown }

/** POST-APP-12 oracle: true when a 200 body has the ask reply shape. */
export function isAskAnswerShape(body: unknown): body is AskAnswerShape {
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return false
  const { answer, model, results, citations, tracts, applied } = body as Unchecked<AskAnswerShape>
  if (typeof applied !== 'object' || applied === null) return false
  const { reach_miles, percentiles } = applied as Unchecked<AskAnswerShape['applied']>
  return (
    typeof answer === 'string' &&
    answer.trim() !== '' &&
    typeof model === 'string' &&
    Array.isArray(results) &&
    results.every((r: unknown) => {
      if (typeof r !== 'object' || r === null) return false
      const { columns, rows } = r as Unchecked<AskResultShape>
      return Array.isArray(columns) && Array.isArray(rows)
    }) &&
    Array.isArray(citations) &&
    citations.every((c: unknown) => {
      if (typeof c !== 'object' || c === null) return false
      const fields = c as Unchecked<AskCitationShape>
      return CITATION_KEYS.every((k) => typeof fields[k] === 'string')
    }) &&
    Array.isArray(tracts) &&
    tracts.every((t: unknown) => typeof t === 'string') &&
    typeof reach_miles === 'number' &&
    typeof percentiles === 'object' &&
    percentiles !== null
  )
}

/** POST-APP-12 oracle: how a reply maps to an outcome. */
export function expectedOutcomeKind(
  reply: { readonly status: number; readonly body: unknown } | 'network-error' | 'timeout',
): 'ok' | 'session_ended' | 'unavailable' {
  if (reply === 'network-error' || reply === 'timeout') return 'unavailable'
  if (reply.status === 401) return 'session_ended'
  if (reply.status === 200 && isAskAnswerShape(reply.body)) return 'ok'
  return 'unavailable'
}

/** POST-APP-13 oracle: the link a citation chip carries, or null when the origin is not a web address. */
export function expectedChipHref(citation: AskCitationShape): string | null {
  return /^https?:\/\//.test(citation.origin_url) ? citation.origin_url : null
}

// --- 5. Traceability map -------------------------------------------------------------------

export const CONTRACT_PLANNER_MAP_APP: Readonly<Record<string, Clause>> = {
  'POST-APP-1': {
    verification: 'test',
    text: 'The App renders the three selectable persona lenses labelled "Food bank", "Small business lender" and "Both partners" (PERSONA_LENSES) and the five KPI cohort cards with exact counts (12, 97, 26, 53, 2); clicking a cohort card filters the active shortlist to that cohort. The on-screen wording of a cohort card is not bound by COHORT_CARDS.label; its count is.',
    requirements: ['REQ-18', 'REQ-19', 'REQ-20'],
  },
  'POST-APP-2': {
    verification: 'test',
    text: 'The App renders a legend pinned inside the map canvas naming Classic Food Desert, No gap flagged, and Insufficient data, plus the clickable not-drawn water tract (12095990000), and renders overview tract fills without overlapping circle clutter.',
    requirements: ['REQ-14', 'REQ-15', 'REQ-23', 'REQ-24'],
  },
  'POST-APP-3': {
    verification: 'test',
    text: 'The AI Insight & Coordinated Action Wizard answers natural-language queries or prompt chips by filtering matching tracts (a lending-gap term such as "low SBA loans" selects tracts by the REQ-19 rule, is_dual_gap, never by a raw loan count) and generates a CoordinatedActionBrief with partner roles (Food Bank + SBA/CDFI), DS-* citations, and a counterfactual gap reduction that equals the without-coordination share minus the with-joint-deployment share, computed from the cohort, never adjusted and never negative; a zero reduction is shown as zero and the narrative states NO_REACH_TEXT (Z-21).',
    requirements: ['REQ-21'],
  },
  'POST-APP-4': {
    verification: 'test',
    text: 'Opening a tract card shows its class proof, SBA loan count and gross dollars, household no-vehicle %, median household income with its 90% MOE, deterministic confidence badge with reason, every missing indicator, and the REQ-3 text when sites_in_tract == 0.',
    requirements: ['REQ-3', 'REQ-5', 'REQ-8', 'REQ-22'],
  },
  'POST-APP-5': {
    verification: 'test',
    text: 'Every view displays the DataKind and Beacon credit with a link to www.datakind.org and the CC BY 4.0 license statement.',
    requirements: ['REQ-12'],
  },
  'FORBIDDEN-APP-1': {
    verification: 'test',
    text: 'The App never displays the phrases "no food access" or "no access" anywhere in the UI or generated briefs.',
    requirements: ['REQ-16'],
  },
  'ERRORS-APP-1': {
    verification: 'test',
    text: 'When a static bundle file fails to load or parse, the App halts map rendering and displays an error alert naming the failed file.',
    requirements: ['REQ-7'],
  },
  'POST-APP-6': {
    verification: 'test',
    text: 'One distance control selects a step from 0 to 20 miles by 0.5, starting at 10 (expectedReachMiles clamps and rounds any other value). For the selected step the tract card shows the share of block population in reach, the nearby site count and the people per nearby site, and the shortlist splits a group into within the limit, beyond it and no distance data, all equal to expectedReachFacts over the bundle. The App computes no distances: changing the bundle values changes what is shown.',
    requirements: ['REQ-56', 'REQ-64'],
  },
  'FORBIDDEN-APP-2': {
    verification: 'test',
    text: 'The reach controls show distances in straight-line miles and never a travel time (validateNoTravelTime over their text); there is no time slider; the tract card states no travel time outside its drive-time estimate (POST-APP-16).',
    requirements: ['REQ-57'],
  },
  'POST-APP-16': {
    verification: 'test',
    text: "Each drive-time estimate the App shows is one role='status' element whose text passes validateDriveTimeLabel: it starts with DRIVE_TIME_HEADLINE, and it carries DRIVE_TIME_HEURISTIC_MARK exactly when the estimate is not a road-network route (Z-28).",
    requirements: ['REQ-67'],
  },
  'POST-APP-8': {
    verification: 'test',
    text: 'Three cut controls offer exactly the percentiles in CUT_PERCENTILES and start at DEFAULT_PERCENTILES. Every class, gap flag, cohort card count, map fill, shortlist and wizard filter uses expectedGapFlags over the bundle cuts for the chosen percentiles; at the defaults the counts equal DEFAULT_GROUP_COUNTS.',
    requirements: ['REQ-59', 'REQ-65'],
  },
  'POST-APP-9': {
    verification: 'test',
    text: 'The source list shows exactly the bundle sources entries, in order, each with its label, publisher, period, method, limits and a link to its URL; no other source appears in it.',
    requirements: ['REQ-62'],
  },
  'POST-APP-10': {
    verification: 'test',
    text: 'src/map/emphasis.ts exports emphasisStates(records, focusedGeoids, emphasizeGaps), equal to expectedEmphasisStates; the map applies it as feature states, the outline layers drawing "emphasized" tracts and the fills fading "muted" ones. While emphasis is on, the context line states "<n> on map" and, when some have no shape, "; <m> without a map shape" for the chosen group; turning emphasis off clears both.',
    requirements: ['REQ-63'],
  },
  'POST-APP-11': {
    verification: 'test',
    text: 'src/ai/askClient.ts exports createHttpAskService({ url?, timeoutMs?, fetchImpl? }) returning an AskServiceShape that POSTs to ASK_PATH with a JSON body equal to the AskRequestShape and same-origin credentials. The App (prop askService) sends each question with the distance and the three cut percentiles currently set.',
    requirements: ['REQ-60'],
  },
  'POST-APP-12': {
    verification: 'test',
    text: 'The ask service never rejects and maps each reply by expectedOutcomeKind: a 200 with an ask-shaped body is ok; a 401 is session ended; any other status, a network error, a body that is not ask-shaped, or no reply within timeoutMs (ASK_TIMEOUT_MS by default) is unavailable. On unavailable the App shows AI_UNAVAILABLE_TEXT (ASK_TEST_IDS.aiNotice) and answers the question with the built-in wizard.',
    requirements: ['REQ-39'],
  },
  'POST-APP-13': {
    verification: 'test',
    text: 'Beside an AI answer (ASK_TEST_IDS.aiAnswer) the App shows one chip per citation (ASK_TEST_IDS.citationChip(table_name)) with its dataset_id, publisher and as_of, linked to expectedChipHref(citation) when that is not null and with no link otherwise (for example NOT_RECORDED).',
    requirements: ['REQ-40'],
  },
  'POST-APP-14': {
    verification: 'test',
    text: 'On session ended the App shows SESSION_ENDED_TEXT with a link to SIGN_IN_PATH, does not show AI_UNAVAILABLE_TEXT, and answers the question with the built-in wizard.',
    requirements: ['REQ-66'],
  },
  'POST-APP-15': {
    verification: 'test',
    text: 'On an ok answer the question shortlist holds exactly the tracts in answer.tracts, however many there are (Z-26: not limited by SQL row limits).',
    requirements: ['REQ-60'],
  },
} as const
