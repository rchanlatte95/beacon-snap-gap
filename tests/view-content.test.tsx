import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OpportunitiesApp } from '../src/App'
import { mockAskAnswer } from '../src/ai/mockAskService'
import { actionSteps, sourceIdsForView, viewInsights } from '../src/viewContent'
import { loadCycle17Bundle, SOURCES } from './fixtures/cycle17Bundle'

const original = loadCycle17Bundle()
const bundle = {
  ...original,
  sources: [
    { ...SOURCES[0]!, id: 'DS-H1', label: 'SNAP households' },
    { ...SOURCES[0]!, id: 'DS-X5', label: 'SBA business loans' },
    { ...SOURCES[0]!, id: 'DS-X12', label: 'Second Harvest sites' },
    { ...SOURCES[0]!, id: 'DS-H2', label: 'Poverty rates' },
  ],
}

function plan() {
  fireEvent.click(screen.getByRole('button', { name: 'Make an action plan' }))
  return screen.getByTestId('coordinated-action-brief')
}

function choose(name: string) {
  fireEvent.click(screen.getByRole('button', { name }))
}

describe('short content follows the selected view', () => {
  it('shows pantry actions without loans, including in expanded details and sources', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    choose('Food bank')
    const card = plan()
    expect(within(card).getByRole('list', { name: 'Pantry next steps' })).toBeInTheDocument()
    expect(within(card).queryByRole('list', { name: 'Lending next steps' })).toBeNull()
    expect(card.textContent).not.toMatch(/loans|lending|SBA|CDFI/i)
    expect(screen.getByRole('main').textContent).not.toMatch(/loans|lending|SBA|CDFI/i)
    expect(screen.queryByTestId('cut-select-sba_rate_per_1000')).toBeNull()
    expect(screen.queryByTestId('source-entry-DS-X5')).toBeNull()
    expect(card.querySelector('details')).not.toHaveAttribute('open')
    expect(card.querySelector('details p')).not.toBeVisible()
  })

  it('shows lending actions without SNAP, pantry, or transport content', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    choose('Small business lender')
    const card = plan()
    expect(within(card).getByRole('list', { name: 'Lending next steps' })).toBeInTheDocument()
    expect(within(card).queryByRole('list', { name: 'Pantry next steps' })).toBeNull()
    expect(card.textContent).not.toMatch(/SNAP|pantry|Second Harvest|no car/i)
    expect(screen.getByRole('main').textContent).not.toMatch(/SNAP|pantry|Second Harvest|no car/i)
    expect(screen.queryByTestId('source-entry-DS-H1')).toBeNull()
    expect(screen.queryByTestId('source-entry-DS-X12')).toBeNull()
    expect(screen.queryByTestId('cut-select-no_vehicle')).toBeNull()
    expect(screen.queryByRole('slider', { name: 'Distance limit in miles' })).toBeNull()
  })

  it('keeps the neighborhood detail panel relevant after switching views', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    choose('Small business lender')
    fireEvent.click(document.querySelector('[data-testid^="tract-row-"]')!)
    const detail = screen.getByTestId('tract-evidence-panel')
    expect(detail.textContent).not.toMatch(/SNAP|pantry|Second Harvest|no car/i)
    expect(detail).toHaveTextContent('SBA loans since 2010')
    choose('Food bank')
    expect(detail.textContent).not.toMatch(/SBA|loans|lending/i)
    expect(detail).toHaveTextContent('Homes on SNAP')
  })

  it('shows both kinds of actions when the overlap view is selected', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    choose('Food bank')
    plan()
    choose('Both partners')
    const card = plan()
    expect(within(card).getByRole('list', { name: 'Pantry next steps' })).toBeInTheDocument()
    expect(within(card).getByRole('list', { name: 'Lending next steps' })).toBeInTheDocument()
    expect(screen.getByTestId('kpi-card-triple')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('source-entry-DS-H1')).toBeInTheDocument()
    expect(screen.getByTestId('source-entry-DS-X5')).toBeInTheDocument()
    expect(card).toHaveTextContent('Results have not been measured')
  })

  it('follows a metric card and then restores both topics when overlap is clicked', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    fireEvent.click(screen.getByTestId('kpi-card-dual'))
    expect(screen.getByRole('button', { name: 'Small business lender' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(plan().textContent).not.toMatch(/SNAP|pantry|no car/i)
    choose('Both partners')
    fireEvent.click(screen.getByTestId('kpi-card-triple'))
    const card = plan()
    expect(within(card).getAllByRole('list')).toHaveLength(2)
  })

  it('does not keep a hidden pantry distance filter active in the lender view', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Show only gaps beyond this distance' }))
    choose('Small business lender')
    const card = plan()
    expect(card.querySelector('h3')).not.toHaveTextContent('beyond')
    expect(card.querySelector('dd')).toHaveTextContent('26')
  })

  it('puts the plan before the long list and uses short action bullets', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    choose('Food bank')
    const card = plan()
    const shortlist = screen.getByRole('heading', { name: /Where to start/ })
    expect(card.compareDocumentPosition(shortlist) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const items = within(
      within(card).getByRole('list', { name: 'Pantry next steps' }),
    ).getAllByRole('listitem')
    for (const item of items) {
      expect((item.textContent ?? '').split(/\s+/).length).toBeLessThanOrEqual(20)
      expect(item.textContent).not.toMatch(/deployment|source values|cohort|counterfactual/i)
    }
  })

  it('limits quick takeaways to the selected view and selected neighborhoods', () => {
    const target = original.tracts.filter((t) => t.is_triple_gap).slice(0, 2)
    expect(
      viewInsights(target, 'planner')
        .map((i) => i.text)
        .join(' '),
    ).not.toMatch(/loan|SBA|lending/i)
    expect(
      viewInsights(target, 'officer')
        .map((i) => i.text)
        .join(' '),
    ).not.toMatch(/SNAP|pantry|car/i)
    expect(viewInsights(target, 'officer')[0]?.figure).toBe('2')
    expect(viewInsights(target, 'alignment')).toHaveLength(3)
  })

  it('keeps missing-data checklists separate from service and loan offers', () => {
    const target = original.tracts.filter((t) => t.tract_class === 'Insufficient data')
    const steps = actionSteps(target)
    expect(steps.pantry).toEqual([
      'Check local food needs in 2 neighborhoods before adding service.',
    ])
    expect(steps.lending).toEqual([
      'Check business needs in 2 neighborhoods before offering loans.',
    ])
    expect(sourceIdsForView(['DS-H1', 'DS-X5', 'DS-X12'], 'officer')).toEqual(['DS-X5'])
    expect(viewInsights(target, 'officer')).toHaveLength(1)
    expect(viewInsights(target, 'officer')[0]?.text).toContain('need a local check')
    expect(viewInsights([], 'officer')).toHaveLength(0)
  })

  it.each(['Food bank', 'Small business lender'])(
    'keeps tract question summaries and citations relevant in the %s view',
    async (name) => {
      render(
        <OpportunitiesApp
          initialBundle={bundle}
          enableMap={false}
          askService={async (request) => ({
            ok: true,
            answer: mockAskAnswer(request.question, bundle.tracts, bundle.sources, request),
          })}
        />,
      )
      choose(name)
      fireEvent.change(
        screen.getByRole('textbox', { name: /Ask a question about Central Florida/ }),
        {
          target: { value: 'Food deserts in Orange County' },
        },
      )
      choose('Ask')
      const reply = await screen.findByTestId('ai-answer')
      expect(reply).toHaveTextContent('neighborhoods match')
      if (name === 'Food bank') expect(reply.textContent).not.toMatch(/loan|SBA|lending/i)
      else expect(reply.textContent).not.toMatch(/SNAP|pantry|Second Harvest|no car/i)
    },
  )
})
