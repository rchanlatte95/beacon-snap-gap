/**
 * Plain-language display text for the fixed strings in public/data/planner-bundle.json.
 * The bundle keeps its own wording (src/data_prep/alignment_bundle.py); only the screen text changes.
 * An unknown string is shown as it is.
 */

const ACTIONS: Readonly<Record<string, string>> = {
  'Standard Monitoring (No Gap Flagged)': 'No gap found. Keep an eye on the numbers.',
  'Mobile Pantry Deployment + Joint SBA/CDFI Micro-Lending Outreach':
    'Send a mobile pantry. Bring small business lenders to help local food stores.',
  'Mobile Pantry / Transit-Accessible Food Deployment':
    'Send a mobile pantry, or put food near a bus stop.',
  'Partner Pantry Capacity & Hours Support': 'Help partner pantries add space and hours.',
  'Partner Pantry Expansion + SBA/SBDC Small-Business Outreach':
    'Grow partner pantries. Bring small business help.',
  'Field Verification & Data Gap Audit': 'Visit to check. Key numbers are missing.',
}

const MISSING: Readonly<Record<string, string>> = {
  'CDC PLACES social-needs measures (blank across Florida, F-1)':
    'CDC PLACES survey of food and ride needs. It is blank for all of Florida.',
  pct_poverty: 'Poverty rate',
  'pct_hh_snap (ACS S2201)': 'Share of homes on SNAP',
  'median_household_income (unavailable, ACS S1901/B19013)': 'Typical income. It is not published.',
  'median_household_income (lower_bound, ACS S1901/B19013)':
    'Typical income. Only a lowest value is published.',
}

export function plainAction(action: string): string {
  return ACTIONS[action] ?? action
}

export function plainMissing(indicator: string): string {
  return MISSING[indicator] ?? indicator
}

/** The confidence reasons come from four sentence patterns in alignment_bundle.py. */
export function plainConfidence(reason: string): string {
  let m =
    /^ACS 5-year tract estimate across ([\d,]+) households\.(?: Median income 90% MOE is ±(\$[\d,]+)\.)?/.exec(
      reason,
    )
  if (m) {
    return (
      `Based on a Census survey of ${m[1]} homes.` +
      (m[2] ? ` Typical income could be off by ${m[2]} either way.` : '')
    )
  }
  m = /^([\d.]+)% of residents live in group quarters/.exec(reason)
  if (m) {
    return `${m[1]}% of people here live in group housing, such as dorms or care homes. The survey counts of homes leave them out.`
  }
  m = /^Fewer than \d+ households \(([\d,]+)\)/.exec(reason)
  if (m) return `Only ${m[1]} homes, so the survey numbers are less exact.`
  if (/^Core classification indicator is blank/.test(reason)) {
    return 'A key number is blank, so we cannot sort this area.'
  }
  return reason
}
