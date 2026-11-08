/**
 * Adjustable gap cuts (REQ-58, REQ-59, REQ-65, Z-24 A). The Build writes each cut value; the App picks
 * a percentile and recounts the groups with the REQ-19 and REQ-20 rules. It computes no quantiles.
 */
import {
  CLASS_HIGH_NEED,
  CLASS_INSUFFICIENT,
  CLASS_NO_GAP,
  type TractRecord,
} from './alignmentWizard'

export type CutName = 'poverty' | 'no_vehicle' | 'sba_rate_per_1000'
export type Percentiles = Readonly<Record<CutName, number>>
/** The bundle's thresholds.cuts: {cut: {percentile: value}}. */
export type Cuts = Readonly<Record<CutName, Readonly<Record<string, number>>>>
export type CutValues = Readonly<Record<CutName, number>>

export const CUT_NAMES: readonly CutName[] = ['poverty', 'no_vehicle', 'sba_rate_per_1000']
// REQ-59: the brief's values are the start.
export const DEFAULT_PERCENTILES: Percentiles = {
  poverty: 75,
  no_vehicle: 75,
  sba_rate_per_1000: 25,
}
const SBA_RATE_PER_RESIDENTS = 1000

// The Build's POST-ALN-3 actions (src/data_prep/alignment_bundle.py), so a tract's plan follows its flags.
const ACTION_MOBILE_AND_SBA = 'Mobile Pantry Deployment + Joint SBA/CDFI Micro-Lending Outreach'
const ACTION_MOBILE_PANTRY = 'Mobile Pantry / Transit-Accessible Food Deployment'
const ACTION_FIXED_AND_SBA = 'Partner Pantry Expansion + SBA/SBDC Small-Business Outreach'
const ACTION_PARTNER_PANTRY = 'Partner Pantry Capacity & Hours Support'
const ACTION_DATA_AUDIT = 'Field Verification & Data Gap Audit'
const ACTION_MONITOR = 'Standard Monitoring (No Gap Flagged)'

/** The percentiles the Build wrote for one cut, in ascending order. */
export function cutPercentiles(cuts: Cuts, name: CutName): number[] {
  return Object.keys(cuts[name])
    .map(Number)
    .sort((a, b) => a - b)
}

export function cutValues(cuts: Cuts, percentiles: Percentiles): CutValues {
  const value = (name: CutName) => {
    const v = cuts[name][String(percentiles[name])]
    if (v === undefined) {
      throw new Error(`The bundle has no ${name} cut at percentile ${percentiles[name]}`)
    }
    return v
  }
  return {
    poverty: value('poverty'),
    no_vehicle: value('no_vehicle'),
    sba_rate_per_1000: value('sba_rate_per_1000'),
  }
}

function actionFor(tractClass: string, dual: boolean, transport: boolean): string {
  if (tractClass === CLASS_INSUFFICIENT) return ACTION_DATA_AUDIT
  if (tractClass === CLASS_NO_GAP) return ACTION_MONITOR
  if (transport && dual) return ACTION_MOBILE_AND_SBA
  if (transport) return ACTION_MOBILE_PANTRY
  if (dual) return ACTION_FIXED_AND_SBA
  return ACTION_PARTNER_PANTRY
}

/** REQ-65: each tract's class, gap flags and action under the chosen cuts. Unchanged tracts are reused. */
export function applyCuts(
  tracts: readonly TractRecord[],
  cut: CutValues,
  minPopulation: number,
): readonly TractRecord[] {
  return tracts.map((t) => {
    let tractClass = CLASS_INSUFFICIENT
    let dual = false
    let transport = false
    if (t.pct_poverty !== null && t.lila_flag !== null) {
      const high = t.pct_poverty >= cut.poverty && t.lila_flag === 1
      tractClass = high ? CLASS_HIGH_NEED : CLASS_NO_GAP
      dual =
        high &&
        t.pop2020 >= minPopulation &&
        (t.sba_loans_total / t.pop2020) * SBA_RATE_PER_RESIDENTS <= cut.sba_rate_per_1000
      transport = high && t.pct_no_vehicle !== null && t.pct_no_vehicle >= cut.no_vehicle
    }
    const triple = dual && transport
    if (
      t.tract_class === tractClass &&
      t.is_dual_gap === dual &&
      t.is_transport_gap === transport &&
      t.is_triple_gap === triple
    ) {
      return t
    }
    return {
      ...t,
      tract_class: tractClass,
      is_dual_gap: dual,
      is_transport_gap: transport,
      is_triple_gap: triple,
      recommended_action: actionFor(tractClass, dual, transport),
    }
  })
}

/** "Top quarter" for poverty and no-vehicle cuts, "Lowest quarter" for the SBA cut. */
export function percentileLabel(name: CutName, percentile: number): string {
  const share = name === 'sba_rate_per_1000' ? percentile : 100 - percentile
  const part =
    share === 50 ? 'half' : share === 25 ? 'quarter' : share === 10 ? 'tenth' : `${share}%`
  return `${name === 'sba_rate_per_1000' ? 'Lowest' : 'Top'} ${part}`
}

/** A rate cut as the screen shows it, without float noise: 17.025, 6.9. */
export function rateText(value: number): string {
  return String(Number(value.toFixed(3)))
}
