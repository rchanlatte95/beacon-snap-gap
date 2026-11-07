/**
 * App domain contract for SLICE-1: Beacon "Opportunities to Serve" cross-agency alignment map & AI action wizard.
 * Authority: requirements/REQUIREMENT_MANIFEST.md (cycle 12).
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
  { id: 'alignment', label: 'Shared Alignment: Opportunities to Serve' },
  { id: 'planner', label: 'Food Bank Planner (SNAP & Pantries)' },
  { id: 'officer', label: 'SBA / CDFI Lending Officer' },
] as const

export type PersonaLensId = (typeof PERSONA_LENSES)[number]['id']

export const COHORT_CARDS = [
  { id: 'triple', label: 'Opportunities to Serve (Triple Gap)', expectedCount: 29 },
  { id: 'high_need', label: 'Classic Food Deserts (High Need)', expectedCount: 97 },
  { id: 'dual', label: 'Food + SBA Lending Gap (≤10 Loans)', expectedCount: 50 },
  { id: 'transport', label: 'Mobile Priority (No-Vehicle ≥6.9%)', expectedCount: 53 },
  { id: 'insufficient', label: 'Insufficient Data / Blind Spots', expectedCount: 2 },
] as const

export type CohortId = (typeof COHORT_CARDS)[number]['id'] | 'all'

export const CLASS_HIGH_NEED = 'Classic Food Desert'
export const CLASS_NO_GAP = 'No gap flagged'
export const CLASS_INSUFFICIENT = 'Insufficient data'

export const NO_SITE_CARD_TEXT =
  'No Second Harvest site found under this rule. Other food sources may exist.'
export const FORBIDDEN_PHRASES = ['no food access', 'no access'] as const

export const DATAKIND_ATTRIBUTION_URL = 'http://www.datakind.org'
export const CC_BY_STATEMENT = 'CC BY 4.0'
export const BASE_MAP_UNAVAILABLE_TEXT = 'Base map unavailable'
export const OPENFREEMAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'

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
  if (
    brief.withJointDeploymentGapPct >= brief.withoutCoordinationGapPct ||
    brief.percentagePointReduction <= 0
  ) {
    throw new WizardBriefContractError(
      `POST-APP-3 violation: counterfactual must show positive reduction (without=${brief.withoutCoordinationGapPct}%, with=${brief.withJointDeploymentGapPct}%)`,
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

// --- 5. Traceability map -------------------------------------------------------------------

export const CONTRACT_PLANNER_MAP_APP: Readonly<Record<string, Clause>> = {
  'POST-APP-1': {
    verification: 'test',
    text: 'The App renders the three selectable persona lenses (Shared Alignment, Food Bank Planner, SBA/CDFI Officer) and the five KPI cohort cards with exact counts (29, 97, 50, 53, 2); clicking a cohort card filters the active shortlist to that cohort.',
    requirements: ['REQ-18', 'REQ-19', 'REQ-20'],
  },
  'POST-APP-2': {
    verification: 'test',
    text: 'The App renders a legend pinned inside the map canvas naming Classic Food Desert, No gap flagged, and Insufficient data, plus the clickable not-drawn water tract (12095990000), and renders overview tract fills without overlapping circle clutter.',
    requirements: ['REQ-14', 'REQ-15', 'REQ-23', 'REQ-24'],
  },
  'POST-APP-3': {
    verification: 'test',
    text: 'The AI Insight & Coordinated Action Wizard answers natural-language queries or prompt chips by filtering matching tracts and generates a CoordinatedActionBrief with partner roles (Food Bank + SBA/CDFI), counterfactual gap reduction, and DS-* citations.',
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
} as const
