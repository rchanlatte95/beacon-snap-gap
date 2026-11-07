/**
 * RED tests for SLICE-1 batch 3: App "Opportunities to Serve" cross-agency alignment UI & AI wizard.
 *
 * CONTRACT AUTHORITY RECORD:
 * - File: contracts/planner-map.app.contract.ts
 * - Authority: AUTHORITATIVE for the App (SLICE-1 Opportunities to Serve)
 * - Clauses covered: POST-APP-1, POST-APP-2, POST-APP-3, POST-APP-4, POST-APP-5, FORBIDDEN-APP-1, ERRORS-APP-1
 *
 * FOUR-CRITERIA TEST VALIDITY GATE:
 * - C1 VALID: cites POST-APP-1..5, FORBIDDEN-APP-1, ERRORS-APP-1 in contracts/planner-map.app.contract.ts
 * - C2 VALUABLE: asserts exact cohort counts, exact wizard query filtering & counterfactual brief, exact card fields, and exact failure alert
 * - C3 NON-DUPLICATIVE: test 1 covers AI wizard & brief logic; test 2 covers rendered React UI, pinned legend, card, attribution, and load error
 * - C4 NOT FUTURE-EDIT: exercises only the contracted SLICE-1 App surface
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import * as appContract from '../contracts/planner-map.app.contract'
import {
  answerWizardQuery,
  filterTractsByCohort,
  generateCoordinatedActionBrief,
} from '../src/wizard/alignmentWizard'
import { OpportunitiesApp } from '../src/App'

interface BundleFile {
  readonly thresholds: {
    readonly poverty_cut_q75: number
    readonly poverty_cut_method: string
    readonly sba_loans_median: number
    readonly no_vehicle_q75: number
    readonly drive_time_minutes: number
  }
  readonly counts: {
    readonly total_tracts: number
    readonly drawn_tracts: number
    readonly high_need: number
    readonly no_gap: number
    readonly insufficient: number
    readonly dual_gap: number
    readonly transport_gap: number
    readonly triple_gap: number
  }
  readonly tracts: readonly appContract.TractRecordShape[]
}

const bundlePath = resolve(process.cwd(), 'public/data/planner-bundle.json')
const bundle: BundleFile = JSON.parse(readFileSync(bundlePath, 'utf-8')) as BundleFile

describe('SLICE-1 batch 3: Opportunities to Serve AI Wizard & App UI', () => {
  it('enforces POST-APP-1, POST-APP-3, and FORBIDDEN-APP-1 on cohort filtering, NL query, and Coordinated Action Brief generation', () => {
    // POST-APP-1: exact cohort counts from the 490-tract dataset
    expect(
      filterTractsByCohort(bundle.tracts, 'triple').length,
      'POST-APP-1 violation: triple-gap cohort must equal 29 tracts',
    ).toBe(29)
    expect(
      filterTractsByCohort(bundle.tracts, 'high_need').length,
      'POST-APP-1 violation: high_need cohort must equal 97 tracts',
    ).toBe(97)
    expect(
      filterTractsByCohort(bundle.tracts, 'dual').length,
      'POST-APP-1 violation: dual-gap (food + SBA <= 10 loans) cohort must equal 50 tracts',
    ).toBe(50)
    expect(
      filterTractsByCohort(bundle.tracts, 'transport').length,
      'POST-APP-1 violation: transport-gap (no-vehicle >= 6.9%) cohort must equal 53 tracts',
    ).toBe(53)
    expect(
      filterTractsByCohort(bundle.tracts, 'insufficient').length,
      'POST-APP-1 violation: insufficient-data cohort must equal 2 tracts',
    ).toBe(2)

    // POST-APP-3: natural-language query filtering & explanation
    const nlResult = answerWizardQuery(
      bundle.tracts,
      'Show high-need tracts in Orange County with zero pantries and low SBA loans',
    )
    expect(
      nlResult.matchedTracts.length,
      'POST-APP-3 violation: Orange County high-need tracts with 0 sites inside and <=10 SBA loans must be non-empty',
    ).toBeGreaterThan(0)
    for (const t of nlResult.matchedTracts) {
      expect(t.county).toBe('Orange')
      expect(t.tract_class).toBe(appContract.CLASS_HIGH_NEED)
      expect(t.sites_in_tract).toBe(0)
      expect(t.sba_loans_total).toBeLessThanOrEqual(10)
    }
    appContract.validateNoForbiddenPhrases(nlResult.answerText)

    // POST-APP-3 & FORBIDDEN-APP-1: Coordinated Action Brief with counterfactual reduction
    const brief = generateCoordinatedActionBrief({
      tracts: bundle.tracts,
      cohortId: 'triple',
      personaId: 'alignment',
    })
    appContract.validateCoordinatedBrief(brief)
    expect(brief.targetTractCount).toBe(29)
    expect(brief.mobilePriorityTractCount).toBe(29)
    expect(brief.dualGapTractCount).toBe(29)
  })

  it('enforces POST-APP-1, POST-APP-2, POST-APP-4, POST-APP-5, FORBIDDEN-APP-1, and ERRORS-APP-1 in OpportunitiesApp', () => {
    const { container, unmount } = render(<OpportunitiesApp initialBundle={bundle} />)

    // POST-APP-1: 3 persona lenses & 5 KPI cohort cards rendered
    for (const lens of appContract.PERSONA_LENSES) {
      expect(
        screen.getByRole('button', { name: new RegExp(lens.label, 'i') }),
        `POST-APP-1 violation: missing persona lens button ${lens.label}`,
      ).toBeInTheDocument()
    }
    for (const card of appContract.COHORT_CARDS) {
      expect(
        screen.getByTestId(`kpi-card-${card.id}`),
        `POST-APP-1 violation: missing KPI card ${card.id}`,
      ).toHaveTextContent(String(card.expectedCount))
    }

    // POST-APP-2: pinned legend inside map canvas + clickable not-drawn water tract 12095990000
    const pinnedLegend = screen.getByTestId('pinned-map-legend')
    expect(pinnedLegend).toHaveTextContent(appContract.CLASS_HIGH_NEED)
    expect(pinnedLegend).toHaveTextContent(appContract.CLASS_NO_GAP)
    expect(pinnedLegend).toHaveTextContent(appContract.CLASS_INSUFFICIENT)
    expect(pinnedLegend).toHaveTextContent('12095990000')

    // POST-APP-4: select tract 12095016510 and verify evidence, SBA contrast, no-vehicle %, income+MOE, confidence, REQ-3 text
    const tractBtn = screen.getByTestId('tract-row-12095016510')
    fireEvent.click(tractBtn)
    const detailPanel = screen.getByTestId('tract-evidence-panel')
    expect(detailPanel).toHaveTextContent('12095016510')
    expect(detailPanel).toHaveTextContent('58.1%')
    expect(detailPanel).toHaveTextContent(appContract.NO_SITE_CARD_TEXT)
    expect(detailPanel).toHaveTextContent('CDC PLACES')

    // POST-APP-5: attribution footer with DataKind link and CC BY 4.0
    const footer = screen.getByRole('contentinfo')
    const hrefs = Array.from(footer.querySelectorAll('a')).map((a) => a.getAttribute('href') ?? '')
    appContract.validateAttributionFooter(footer.textContent ?? '', hrefs)

    // FORBIDDEN-APP-1: no forbidden phrases anywhere in rendered app
    appContract.validateNoForbiddenPhrases(container.textContent ?? '')
    unmount()

    // ERRORS-APP-1: load failure shows alert naming the failed file and draws no map
    render(<OpportunitiesApp initialLoadError="public/data/planner-bundle.json" />)
    const alert = screen.getByRole('alert')
    expect(
      alert,
      'ERRORS-APP-1 violation: load error alert must name the failed file',
    ).toHaveTextContent('public/data/planner-bundle.json')
    expect(screen.queryByTestId('pinned-map-legend')).toBeNull()
  })
})
