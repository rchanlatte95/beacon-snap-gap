/**
 * Gap emphasis (PR #18), mapped in cycle 17.
 * CONTRACT AUTHORITY RECORD: contracts/planner-map.app.contract.ts, POST-APP-10 (REQ-63): the context line
 * states "<n> on map" and "<m> without a map shape" for the chosen group, and turning emphasis off clears it.
 * Feature states are covered by tests/emphasis-states.test.ts.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OpportunitiesApp, type PlannerBundle } from '../src/App'

const bundle: PlannerBundle = JSON.parse(
  readFileSync(resolve(process.cwd(), 'public/data/planner-bundle.json'), 'utf-8'),
)

function context() {
  return document.getElementById('gap-emphasis-context')!
}

function toggle() {
  return screen.getByRole('button', { name: 'Emphasize gaps' })
}

describe('metric-specific gap emphasis', () => {
  it('follows the selected metric, keeps overlays and selection, and can be turned off', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)

    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    expect(context()).toHaveTextContent('All three gaps')
    expect(context()).toHaveTextContent('12 neighborhoods on map')
    fireEvent.click(toggle())
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(context()).toHaveTextContent('Outlined; other areas faded.')
    expect(
      within(screen.getByTestId('pinned-map-legend')).getByText('Emphasized gaps'),
    ).toBeInTheDocument()

    const overlays = screen.getByRole('group', { name: 'Add to the map' })
    const sites = within(overlays).getByRole('button', { name: 'Second Harvest sites' })
    fireEvent.click(sites)
    fireEvent.click(screen.getByTestId('kpi-card-transport'))
    expect(context()).toHaveTextContent('Many with no car')
    expect(context()).toHaveTextContent('53 neighborhoods on map')
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    expect(sites).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByTestId('kpi-card-high_need'))
    expect(context()).toHaveTextContent('97 neighborhoods on map')
    fireEvent.click(screen.getByTestId('tract-row-12095016510'))
    expect(screen.getByTestId('tract-evidence-panel')).toHaveTextContent('12095016510')
    fireEvent.click(toggle())
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByText('Emphasized gaps')).not.toBeInTheDocument()
    expect(screen.getByTestId('tract-evidence-panel')).toHaveTextContent('12095016510')
    expect(sites).toHaveAttribute('aria-pressed', 'true')
  })

  it('selects the relevant gap metric when the persona changes', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    fireEvent.click(toggle())

    for (const [persona, card, label, count] of [
      ['Food bank', 'high_need', 'Classic Food Deserts', 97],
      ['Small business lender', 'dual', 'Few business loans', 26],
      ['Both partners', 'triple', 'All three gaps', 12],
    ] as const) {
      fireEvent.click(screen.getByRole('button', { name: persona }))
      expect(screen.getByTestId(`kpi-card-${card}`)).toHaveAttribute('aria-pressed', 'true')
      expect(context()).toHaveTextContent(label)
      expect(context()).toHaveTextContent(`${count} neighborhoods on map`)
      expect(toggle()).toHaveAttribute('aria-pressed', 'true')
    }
  })

  it('uses the exact question results and separates missing shapes from mapped matches', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    fireEvent.click(toggle())
    fireEvent.click(screen.getByTestId('kpi-card-insufficient'))
    expect(context()).toHaveTextContent('1 neighborhood on map; 1 without a map shape')
    const legend = screen.getByTestId('pinned-map-legend')
    expect(within(legend).getByText('Emphasized gaps').parentElement).toHaveTextContent('1')

    const question = screen.getByRole('textbox', {
      name: 'Ask a question about Central Florida neighborhoods',
    })
    fireEvent.change(question, { target: { value: 'All three gaps in Orange County' } })
    fireEvent.click(screen.getByRole('button', { name: /^Ask$/ }))
    const matches = bundle.tracts.filter((t) => t.county === 'Orange' && t.is_triple_gap && t.drawn)
    expect(matches.length).toBeGreaterThan(0)
    expect(matches.length).toBeLessThan(12)
    expect(context()).toHaveTextContent('Your question')
    expect(context()).toHaveTextContent(`${matches.length} neighborhoods on map`)
    expect(toggle()).toHaveAttribute('aria-pressed', 'true')

    const emptyCounty = ['Orange', 'Seminole', 'Lake', 'Osceola'].find(
      (county) =>
        !bundle.tracts.some((t) => t.county === county && t.tract_class === 'Insufficient data'),
    )
    expect(emptyCounty).toBeDefined()
    fireEvent.change(question, { target: { value: `Places with missing data in ${emptyCounty}` } })
    fireEvent.click(screen.getByRole('button', { name: /^Ask$/ }))
    expect(context()).toHaveTextContent('0 neighborhoods on map. No areas to emphasize.')
    expect(screen.queryByText('Emphasized gaps')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /^Clear$/ }))
    expect(context()).toHaveTextContent('Insufficient data')
    expect(context()).toHaveTextContent('1 neighborhood on map; 1 without a map shape')
    fireEvent.click(toggle())
    expect(toggle()).toHaveAttribute('aria-pressed', 'false')
  })
})
