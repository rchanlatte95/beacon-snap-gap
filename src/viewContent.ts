import {
  CLASS_HIGH_NEED,
  CLASS_INSUFFICIENT,
  CLASS_NO_GAP,
  type CohortId,
  type Insight,
  type PersonaLensId,
  type TractRecord,
} from './wizard/alignmentWizard'
import type { CutName } from './wizard/gapRules'

interface ViewContent {
  readonly pantry: boolean
  readonly lending: boolean
  readonly cohorts: readonly CohortId[]
  readonly cuts: readonly CutName[]
  readonly prompts: readonly string[]
}

export const VIEW_CONTENT: Readonly<Record<PersonaLensId, ViewContent>> = {
  alignment: {
    pantry: true,
    lending: true,
    cohorts: ['triple', 'high_need', 'dual', 'transport', 'insufficient'],
    cuts: ['poverty', 'no_vehicle', 'sba_rate_per_1000'],
    prompts: [
      'All three gaps in Orange County',
      'Food deserts with no pantry and few SBA loans',
      'Places with missing data',
    ],
  },
  planner: {
    pantry: true,
    lending: false,
    cohorts: ['high_need', 'transport', 'insufficient'],
    cuts: ['poverty', 'no_vehicle'],
    prompts: [
      'Food deserts with no pantry in Orange County',
      'Where should a mobile pantry go in Osceola?',
      'Places with missing data',
    ],
  },
  officer: {
    pantry: false,
    lending: true,
    cohorts: ['dual', 'insufficient'],
    cuts: ['poverty', 'sba_rate_per_1000'],
    prompts: [
      'Food deserts with few SBA loans in Orange County',
      'Food deserts with few SBA loans in Osceola',
      'Places with missing data',
    ],
  },
}

export function sourceIdsForView(
  ids: readonly string[],
  persona: PersonaLensId,
): readonly string[] {
  if (persona === 'alignment') return ids
  if (persona === 'planner') return ids.filter((id) => id !== 'DS-X5')
  return ids.filter((id) => ['DS-H2', 'DS-H6', 'DS-X5', 'DS-X24', 'DS-X28'].includes(id))
}

const count = (n: number) => `${n} neighborhood${n === 1 ? '' : 's'}`

export function actionSteps(tracts: readonly TractRecord[]) {
  const high = tracts.filter((t) => t.tract_class === CLASS_HIGH_NEED)
  const mobile = high.filter((t) => t.is_transport_gap).length
  const fixed = high.length - mobile
  const loans = high.filter((t) => t.is_dual_gap).length
  const missing = tracts.filter((t) => t.tract_class === CLASS_INSUFFICIENT).length
  const monitor = tracts.filter((t) => t.tract_class === CLASS_NO_GAP).length
  return {
    pantry: [
      mobile > 0
        ? `Plan mobile pantry stops in ${count(mobile)} where many homes have no car.`
        : '',
      fixed > 0 ? `Check pantry hours and food supplies in ${count(fixed)}.` : '',
      missing > 0 ? `Check local food needs in ${count(missing)} before adding service.` : '',
      monitor > 0 ? `Keep checking local food needs in ${count(monitor)}.` : '',
    ].filter(Boolean),
    lending: [
      loans > 0 ? `Offer loan advice to food businesses in ${count(loans)}.` : '',
      loans > 0 ? 'Start with corner stores and mobile food markets.' : '',
      loans === 0 && high.length > 0 ? 'Ask local food businesses what support they need.' : '',
      missing > 0 ? `Check business needs in ${count(missing)} before offering loans.` : '',
      monitor > 0 ? `Keep checking local business needs in ${count(monitor)}.` : '',
    ].filter(Boolean),
  }
}

export function viewInsights(
  tracts: readonly TractRecord[],
  persona: PersonaLensId,
): readonly Insight[] {
  if (tracts.length === 0) return []
  const view = VIEW_CONTENT[persona]
  const insights: Insight[] = []
  if (view.pantry) {
    insights.push({
      figure: String(tracts.filter((t) => t.sites_in_tract === 0).length),
      text: 'neighborhoods have no listed Second Harvest site inside.',
      tone: 'high',
      sourceIds: ['DS-X12'],
    })
    const mobile = tracts.filter((t) => t.is_transport_gap).length
    if (mobile > 0)
      insights.push({
        figure: String(mobile),
        text: 'neighborhoods to check for mobile pantry stops. Many homes have no car.',
        tone: 'high',
        sourceIds: ['DS-H2', 'DS-H6', 'DS-X7b'],
      })
  }
  if (view.lending && tracts.some((t) => t.tract_class !== CLASS_INSUFFICIENT))
    insights.push({
      figure: String(tracts.filter((t) => t.is_dual_gap).length),
      text: 'neighborhoods have few small business loans. Review local food businesses first.',
      tone: 'plain',
      sourceIds: ['DS-H2', 'DS-H6', 'DS-X5', 'DS-X24'],
    })
  const missing = tracts.filter((t) => t.tract_class === CLASS_INSUFFICIENT).length
  if (missing > 0)
    insights.push({
      figure: String(missing),
      text: 'neighborhoods need a local check before planning help.',
      tone: 'plain',
      sourceIds: ['DS-H2', 'DS-H6'],
    })
  return insights
}
