/**
 * RED tests for SLICE-1 cycle 17 (PR #18 refactor): reach from the Build, miles only, adjustable cuts, sources.
 *
 * CONTRACT AUTHORITY RECORD:
 * - File: contracts/planner-map.app.contract.ts
 * - Clauses covered: POST-APP-6, FORBIDDEN-APP-2 (amended, cycle 20), POST-APP-8, POST-APP-9, POST-APP-16
 * - Requirements: REQ-56, REQ-64, REQ-57, REQ-59, REQ-65, REQ-62, REQ-67 (Z-24 A, Z-25 A, Z-28)
 *
 * FOUR-CRITERIA TEST VALIDITY GATE:
 * - C1 VALID: expected values come from the contract oracles (expectedReachFacts, expectedGapFlags) or constants.
 * - C2 VALUABLE: the fixture's reach, cut and source values are synthetic, so an App that measures distances,
 *   computes its own quantiles or keeps a typed source list fails.
 * - C3 NON-DUPLICATIVE: app.test.tsx covers the fixed cohorts; these cover the adjustable behaviour.
 * - C4 NOT FUTURE-EDIT: selectors are APP_TEST_IDS and DISTANCE_SLIDER_NAME from the contract.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  APP_TEST_IDS,
  CUT_PERCENTILES,
  DEFAULT_GROUP_COUNTS,
  DEFAULT_PERCENTILES,
  DISTANCE_SLIDER_NAME,
  expectedGapFlags,
  expectedReachFacts,
  DRIVE_TIME_HEADLINE,
  validateDriveTimeLabel,
  validateNoTravelTime,
  type CutName,
  type TractRecordShape,
} from '../contracts/planner-map.app.contract'
import { OpportunitiesApp } from '../src/App'
import { CUTS, SOURCES, loadCycle17Bundle as loadBundle, tractsOf } from './fixtures/cycle17Bundle'

const FOCUS = '12095016510'

function slider() {
  return screen.getByRole('slider', { name: DISTANCE_SLIDER_NAME })
}

function openFocusTract() {
  fireEvent.click(screen.getByTestId('kpi-card-high_need'))
  fireEvent.click(screen.getByTestId(`tract-row-${FOCUS}`))
}

/** The element's text with every drive-time estimate (POST-APP-16) left out. */
function textOutsideDriveTimeEstimates(element: HTMLElement): string {
  const copy = element.cloneNode(true) as HTMLElement
  for (const status of Array.from(copy.querySelectorAll('[role="status"]'))) {
    if ((status.textContent ?? '').trim().startsWith(DRIVE_TIME_HEADLINE)) status.remove()
  }
  return copy.textContent ?? ''
}

function groupCounts(
  tracts: readonly TractRecordShape[],
  percentiles: Readonly<Record<CutName, number>>,
) {
  const flags = tracts.map((t) => expectedGapFlags(t, CUTS, percentiles))
  return {
    high_need: flags.filter((f) => f.tract_class === 'Classic Food Desert').length,
    dual: flags.filter((f) => f.is_dual_gap).length,
    transport: flags.filter((f) => f.is_transport_gap).length,
    triple: flags.filter((f) => f.is_triple_gap).length,
  }
}

function expectCard(id: string, count: number) {
  expect(
    screen.getByTestId(`kpi-card-${id}`),
    `POST-APP-8 violation: cohort card ${id} must show ${count}`,
  ).toHaveTextContent(new RegExp(`(^|\\D)${count}(\\D|$)`))
}

describe('SLICE-1 cycle 17: reach, cuts and sources come from the Build', () => {
  it('enforces POST-APP-6: the tract card and shortlist index the Build reach values at the selected step', () => {
    const bundle = loadBundle()
    const tract = tractsOf(bundle).find((t) => t.geoid === FOCUS)!
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    openFocusTract()

    for (const [requested, shown] of [
      [10, 10],
      [0.74, 0.5],
      [99, 20],
    ] as const) {
      if (requested !== 10) fireEvent.input(slider(), { target: { value: String(requested) } })
      const facts = expectedReachFacts(tract, requested)
      expect(facts.miles).toBe(shown)
      expect(
        screen.getByTestId(APP_TEST_IDS.reachSites),
        `POST-APP-6 violation: site count at ${shown} miles must be the bundle's ${facts.sites}`,
      ).toHaveTextContent(String(facts.sites))
      expect(
        screen.getByTestId(APP_TEST_IDS.reachShare),
        `POST-APP-6 violation: share at ${shown} miles must be the bundle's ${facts.share}`,
      ).toHaveTextContent(`${Math.round((facts.share ?? 0) * 100)}%`)
      expect(
        screen.getByTestId(APP_TEST_IDS.reachPeoplePerSite),
        'POST-APP-6 violation: people per nearby site must be pop2020 / the bundle site count',
      ).toHaveTextContent(new Intl.NumberFormat('en-US').format(facts.peoplePerSite!))
    }

    fireEvent.input(slider(), { target: { value: '10' } })
    const cohort = tractsOf(bundle).filter((t) => t.tract_class === 'Classic Food Desert')
    const facts = cohort.map((t) => expectedReachFacts(t, 10).within)
    const within = facts.filter((w) => w === true).length
    const beyond = facts.filter((w) => w === false).length
    const unknown = facts.filter((w) => w === null).length
    const result = screen.getByTestId(APP_TEST_IDS.proximityResult)
    for (const part of [
      `${beyond} beyond`,
      `${within} within`,
      `${unknown} with no distance data`,
    ]) {
      expect(
        result,
        `POST-APP-6 violation: the shortlist split must read "${part}"`,
      ).toHaveTextContent(part)
    }
  })

  it('enforces FORBIDDEN-APP-2: the reach controls and the tract card state no travel time outside the drive-time estimate', () => {
    render(<OpportunitiesApp initialBundle={loadBundle()} enableMap={false} />)
    openFocusTract()
    expect(
      screen.queryByRole('slider', { name: /minute|time/i }),
      'FORBIDDEN-APP-2 violation: a time slider is present',
    ).toBeNull()
    const controls = screen.getByTestId(APP_TEST_IDS.reachControls)
    expect(
      controls,
      'FORBIDDEN-APP-2 violation: the reach controls must read in miles',
    ).toHaveTextContent(/miles/i)
    expect(() => validateNoTravelTime(textOutsideDriveTimeEstimates(controls))).not.toThrow()
    const panel = screen.getByTestId('tract-evidence-panel')
    expect(() => validateNoTravelTime(textOutsideDriveTimeEstimates(panel))).not.toThrow()
  })

  it('enforces POST-APP-16: each drive-time estimate names itself and, with no routed result, is marked heuristic', () => {
    // The test environment serves no routing cache, so every estimate is the heuristic fallback (Z-28).
    render(<OpportunitiesApp initialBundle={loadBundle()} enableMap={false} />)
    openFocusTract()
    const estimates = screen
      .queryAllByRole('status')
      .filter((s) => /\bdrive\b/i.test(s.textContent ?? ''))
    expect(
      estimates.length,
      'POST-APP-16 violation: the selected tract shows no drive-time estimate (Z-28: the App shows drive times)',
    ).toBeGreaterThan(0)
    for (const estimate of estimates) {
      expect(() => validateDriveTimeLabel(estimate.textContent ?? '', false)).not.toThrow()
    }
  })

  it('enforces POST-APP-8: three cut controls with the Build percentiles recount every group', () => {
    const bundle = loadBundle()
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)

    for (const cut of Object.keys(CUT_PERCENTILES) as CutName[]) {
      const select = screen.getByTestId(APP_TEST_IDS.cutSelect(cut)) as HTMLSelectElement
      const offered = within(select)
        .getAllByRole('option')
        .map((o) => Number((o as HTMLOptionElement).value))
      expect(
        offered,
        `POST-APP-8 violation: ${cut} must offer exactly ${CUT_PERCENTILES[cut]}`,
      ).toEqual([...CUT_PERCENTILES[cut]])
      expect(
        Number(select.value),
        `POST-APP-8 violation: ${cut} must start at ${DEFAULT_PERCENTILES[cut]}`,
      ).toBe(DEFAULT_PERCENTILES[cut])
    }
    const atDefaults = groupCounts(tractsOf(bundle), DEFAULT_PERCENTILES)
    expect(atDefaults).toEqual({
      high_need: DEFAULT_GROUP_COUNTS.high_need,
      dual: DEFAULT_GROUP_COUNTS.dual,
      transport: DEFAULT_GROUP_COUNTS.transport,
      triple: DEFAULT_GROUP_COUNTS.triple,
    })
    for (const [id, n] of Object.entries(atDefaults)) expectCard(id, n)

    const chosen = { ...DEFAULT_PERCENTILES, poverty: 90, sba_rate_per_1000: 50 }
    fireEvent.change(screen.getByTestId(APP_TEST_IDS.cutSelect('poverty')), {
      target: { value: '90' },
    })
    fireEvent.change(screen.getByTestId(APP_TEST_IDS.cutSelect('sba_rate_per_1000')), {
      target: { value: '50' },
    })
    const moved = groupCounts(tractsOf(bundle), chosen)
    expect(moved.high_need).not.toBe(atDefaults.high_need)
    for (const [id, n] of Object.entries(moved)) expectCard(id, n)
  })

  it('enforces POST-APP-9: the source list shows exactly the bundle sources, in order', () => {
    render(<OpportunitiesApp initialBundle={loadBundle()} enableMap={false} />)
    const entries = document.querySelectorAll('[data-testid^="source-entry-"]')
    expect(
      [...entries].map((e) => e.getAttribute('data-testid')),
      'POST-APP-9 violation: the list must hold only the bundle sources, in order',
    ).toEqual(SOURCES.map((s) => APP_TEST_IDS.sourceEntry(s.id)))
    for (const s of SOURCES) {
      const entry = screen.getByTestId(APP_TEST_IDS.sourceEntry(s.id))
      for (const text of [s.label, s.publisher, s.period, s.method, s.limits]) {
        expect(entry, `POST-APP-9 violation: ${s.id} must show "${text}"`).toHaveTextContent(text)
      }
      expect(
        within(entry)
          .getAllByRole('link')
          .some((a) => a.getAttribute('href') === s.url),
        `POST-APP-9 violation: ${s.id} must link to ${s.url}`,
      ).toBe(true)
    }
  })
})
