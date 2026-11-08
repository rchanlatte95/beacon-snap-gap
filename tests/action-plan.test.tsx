import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { validateCoordinatedBrief } from '../contracts/planner-map.app.contract'
import { OpportunitiesApp } from '../src/App'
import { mockAskAnswer } from '../src/ai/mockAskService'
import {
  CLASS_HIGH_NEED,
  CLASS_INSUFFICIENT,
  CLASS_NO_GAP,
  generateCoordinatedActionBrief,
} from '../src/wizard/alignmentWizard'
import { loadCycle17Bundle } from './fixtures/cycle17Bundle'

const bundle = loadCycle17Bundle()
const missing = bundle.tracts.filter((t) => t.tract_class === CLASS_INSUFFICIENT)
const triple = bundle.tracts.find((t) => t.is_triple_gap)!
const noGap = bundle.tracts.find((t) => t.tract_class === CLASS_NO_GAP)!

function makePlan() {
  fireEvent.click(screen.getByRole('button', { name: 'Make an action plan' }))
  return screen.getByTestId('coordinated-action-brief')
}

function ask(question: string) {
  fireEvent.change(screen.getByRole('textbox', { name: /Ask a question about Central Florida/ }), {
    target: { value: question },
  })
  fireEvent.click(screen.getByRole('button', { name: /^Ask$/ }))
}

describe('action plan advice and selection titles', () => {
  it('gives verification tasks for missing data while retaining the impact contract', () => {
    const brief = generateCoordinatedActionBrief({
      tracts: missing,
      cohortId: 'all',
      personaId: 'alignment',
    })

    expect(brief.dataCheckTractCount).toBe(2)
    expect(brief.foodBankAction).toMatch(/verify.*2 neighborhoods.*before/i)
    expect(brief.sbaOfficerAction).toMatch(/verify.*2 neighborhoods.*before/i)
    expect(`${brief.foodBankAction} ${brief.sbaOfficerAction}`).not.toMatch(
      /Send mobile|Add pantry|Hold small business|new pantry sites/i,
    )
    expect(brief.narrativeSummary).toContain('No service deployment is proposed for them')
    expect(brief.narrativeSummary).not.toContain('Suppose the food bank serves the 0')
    expect(() => validateCoordinatedBrief(brief)).not.toThrow()
  })

  it('separates service candidates, missing data, and monitoring in a mixed group', () => {
    const brief = generateCoordinatedActionBrief({
      tracts: [triple, missing[0]!, noGap],
      cohortId: 'all',
      personaId: 'alignment',
    })

    expect(brief.targetTractCount).toBe(3)
    expect(brief.dataCheckTractCount).toBe(1)
    expect(brief.foodBankAction).toContain('1 neighborhood where many homes have no car')
    expect(brief.sbaOfficerAction).toContain('1 neighborhood with few SBA loans')
    for (const action of [brief.foodBankAction, brief.sbaOfficerAction]) {
      expect(action).toContain('1 neighborhood with insufficient data')
      expect(action).toContain('1 neighborhood with no gap flagged')
      expect(action).not.toContain('other 2')
    }
    expect(() => validateCoordinatedBrief(brief)).not.toThrow()
  })

  it('keeps monitoring advice separate from service deployment when no gap is flagged', () => {
    const brief = generateCoordinatedActionBrief({
      tracts: [noGap],
      cohortId: 'all',
      personaId: 'planner',
    })
    expect(brief.foodBankAction).toMatch(/Monitor/)
    expect(brief.sbaOfficerAction).toMatch(/Monitor/)
    expect(`${brief.foodBankAction} ${brief.sbaOfficerAction}`).not.toMatch(
      /Add pantry|new pantry sites/i,
    )
  })

  it('does not treat an unrelated missing source as an unclassified food desert', () => {
    expect(triple.tract_class).toBe(CLASS_HIGH_NEED)
    expect(triple.missing_indicators.length).toBeGreaterThan(0)
    const brief = generateCoordinatedActionBrief({
      tracts: [triple],
      cohortId: 'all',
      personaId: 'alignment',
    })
    expect(brief.dataCheckTractCount).toBe(0)
    expect(brief.foodBankAction).toContain('Send mobile pantry stops')
    expect(brief.sbaOfficerAction).toContain('Hold small business loan and coaching clinics')
  })

  it('shows missing gap assessments separately from measured zero in the missing-data plan', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    fireEvent.click(screen.getByTestId('kpi-card-insufficient'))
    const plan = makePlan()
    expect(within(plan).getAllByText('Not assessed')).toHaveLength(2)
    expect(plan).toHaveTextContent('Need data checks2')
    expect(plan).toHaveTextContent('Verify')
    expect(within(plan).getByRole('heading', { level: 3 })).toHaveTextContent(
      'Action plan: Insufficient data',
    )
  })

  it('names the submitted built-in question even after the input is edited', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    const question = 'Food deserts in Orange County'
    ask(question)
    fireEvent.change(
      screen.getByRole('textbox', { name: /Ask a question about Central Florida/ }),
      {
        target: { value: 'Food deserts in Lake County' },
      },
    )
    const title = within(makePlan()).getByRole('heading', { level: 3 })
    expect(title).toHaveTextContent(`Action plan: Question results: ${question}`)
    expect(title).not.toHaveTextContent('All neighborhoods')
    expect(title).not.toHaveTextContent('Lake County')
  })

  it('names the selected group and distance without changing the target', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Show only gaps beyond this distance' }))
    const plan = makePlan()
    expect(within(plan).getByRole('heading', { level: 3 })).toHaveTextContent(
      'Action plan: All three gaps · beyond 10 miles',
    )
    const expected = bundle.tracts.filter(
      (t) => t.is_triple_gap && t.nearest_block_miles !== null && t.nearest_block_miles > 10,
    ).length
    expect(plan.querySelector('dd')).toHaveTextContent(String(expected))
  })

  it('includes both the submitted question and the active distance', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    ask('Food deserts in Orange County')
    fireEvent.input(screen.getByRole('slider', { name: 'Distance limit in miles' }), {
      target: { value: '0.5' },
    })
    expect(within(makePlan()).getByRole('heading', { level: 3 })).toHaveTextContent(
      'Action plan: Question results: Food deserts in Orange County · beyond 0.5 miles',
    )
  })

  it('retains the submitted AI question in the title after an input edit', async () => {
    render(
      <OpportunitiesApp
        initialBundle={bundle}
        enableMap={false}
        askService={async (request) => ({
          ok: true,
          answer: mockAskAnswer(request.question, bundle.tracts, bundle.sources ?? [], request),
        })}
      />,
    )
    const question = 'All three gaps in Orange County'
    ask(question)
    await screen.findByTestId('ai-answer')
    fireEvent.change(
      screen.getByRole('textbox', { name: /Ask a question about Central Florida/ }),
      {
        target: { value: 'Food deserts in Lake County' },
      },
    )
    expect(within(makePlan()).getByRole('heading', { level: 3 })).toHaveTextContent(
      `Action plan: Question results: ${question}`,
    )
  })

  it('uses the distance applied by the AI service when the controls have since changed', async () => {
    render(
      <OpportunitiesApp
        initialBundle={bundle}
        enableMap={false}
        askService={async (request) => ({
          ok: true,
          answer: mockAskAnswer(request.question, bundle.tracts, bundle.sources ?? [], request),
        })}
      />,
    )
    ask('All three gaps in Orange County')
    await screen.findByTestId('ai-answer')
    fireEvent.input(screen.getByRole('slider', { name: 'Distance limit in miles' }), {
      target: { value: '0.5' },
    })
    const title = within(makePlan()).getByRole('heading', { level: 3 })
    expect(title).toHaveTextContent('distance rule: 10 miles')
    expect(title).not.toHaveTextContent('beyond 0.5 miles')
  })
})
