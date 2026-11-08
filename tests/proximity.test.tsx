import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OpportunitiesApp, type PlannerBundle } from '../src/App'
import {
  clampReachMiles,
  distanceMiles,
  evaluateProximity,
  nearestSiteDistances,
  reachMiles,
  reachMinutes,
} from '../src/map/proximity'

const bundle: PlannerBundle = JSON.parse(
  readFileSync(resolve(process.cwd(), 'public/data/planner-bundle.json'), 'utf-8'),
)
const sites: GeoJSON.FeatureCollection = JSON.parse(
  readFileSync(resolve(process.cwd(), 'public/data/sites.geojson'), 'utf-8'),
)

function distanceSlider() {
  return screen.getByRole('slider', { name: 'Distance limit in miles' })
}

function timeSlider() {
  return screen.getByRole('slider', { name: 'Estimated time limit in minutes' })
}

function result() {
  return document.getElementById('proximity-result')!
}

function context() {
  return document.getElementById('gap-emphasis-context')!
}

describe('pantry proximity calculations', () => {
  it('measures geographic distance and selects the nearest valid site', () => {
    expect(distanceMiles([0, 0], [0, 0])).toBe(0)
    expect(distanceMiles([0, 0], [1, 0])).toBeCloseTo(69.09, 1)
    expect(distanceMiles([-81.5, 28.5], [-81, 29])).toBeCloseTo(
      distanceMiles([-81, 29], [-81.5, 28.5]),
      8,
    )
    const index = nearestSiteDistances(
      [
        { geoid: 'origin', centroid: [0, 0] },
        { geoid: 'missing', centroid: null },
        { geoid: 'invalid', centroid: [NaN, 28] },
      ],
      {
        type: 'FeatureCollection',
        features: [
          { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [2, 0] } },
          { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [1, 0] } },
          { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [999, 0] } },
        ],
      },
    )
    expect(index.get('origin')).toBeCloseTo(69.09, 1)
    expect(index.get('missing')).toBeNull()
    expect(index.get('invalid')).toBeNull()
    expect(
      nearestSiteDistances([{ geoid: 'origin', centroid: [0, 0] }], {
        type: 'FeatureCollection',
        features: [],
      }).get('origin'),
    ).toBeNull()
  })

  it('links time to the 10-mile / 30-minute setup and clamps inputs to the visible range', () => {
    expect(reachMinutes(10)).toBe(30)
    expect(reachMinutes(0.5)).toBe(1.5)
    expect(reachMiles(15)).toBe(5)
    expect(clampReachMiles(-10)).toBe(0)
    expect(clampReachMiles(99)).toBe(20)
    expect(clampReachMiles(NaN)).toBe(10)
    expect(reachMiles(999)).toBe(20)
    for (let miles = 0; miles <= 20; miles += 0.5) {
      expect(reachMiles(reachMinutes(miles))).toBe(miles)
    }
  })

  it('keeps missing distances separate and includes the exact threshold in reach', () => {
    const tracts = bundle.tracts.slice(0, 4)
    const distances = new Map([
      [tracts[0]!.geoid, 0],
      [tracts[1]!.geoid, 1],
      [tracts[2]!.geoid, 1.01],
      [tracts[3]!.geoid, null],
    ])
    const evaluated = evaluateProximity(tracts, distances, 1)
    expect(evaluated.withinCount).toBe(2)
    expect(evaluated.outside.map((t) => t.geoid)).toEqual([tracts[2]!.geoid])
    expect(evaluated.unknown.map((t) => t.geoid)).toEqual([tracts[3]!.geoid])
  })
})

describe('live distance and time controls', () => {
  it('updates counts and the shortlist on input, links sliders, and restores the full group', () => {
    render(<OpportunitiesApp initialBundle={bundle} initialSites={sites} enableMap={false} />)
    expect(distanceSlider()).toHaveValue('10')
    expect(timeSlider()).toHaveValue('30')
    expect(context()).toHaveTextContent('12 neighborhoods on map')

    fireEvent.input(distanceSlider(), { target: { value: '1' } })
    expect(timeSlider()).toHaveValue('3')
    expect(result()).toHaveTextContent('3 beyond the limit; 9 within it; 0 with no distance data.')
    expect(context()).toHaveTextContent('3 neighborhoods on map')
    expect(screen.getAllByTestId(/^tract-row-/)).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Emphasize gaps' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    fireEvent.input(timeSlider(), { target: { value: '1.5' } })
    expect(distanceSlider()).toHaveValue('0.5')
    expect(context()).toHaveTextContent('8 neighborhoods on map')
    expect(screen.getAllByTestId(/^tract-row-/)).toHaveLength(8)

    fireEvent.click(screen.getByRole('checkbox', { name: 'Show gaps beyond this limit' }))
    expect(context()).toHaveTextContent('12 neighborhoods on map')
    expect(distanceSlider()).toHaveValue('0.5')
    fireEvent.click(screen.getByRole('button', { name: 'Reset proximity' }))
    expect(distanceSlider()).toHaveValue('10')
    expect(timeSlider()).toHaveValue('30')
    expect(screen.getByRole('checkbox', { name: 'Show gaps beyond this limit' })).not.toBeChecked()
  })

  it('applies the current limit to new metrics, persona lenses, and question results', () => {
    render(<OpportunitiesApp initialBundle={bundle} initialSites={sites} enableMap={false} />)
    fireEvent.input(distanceSlider(), { target: { value: '1' } })
    fireEvent.click(screen.getByTestId('kpi-card-high_need'))
    expect(context()).toHaveTextContent('32 neighborhoods on map')
    expect(result()).toHaveTextContent(
      '32 beyond the limit; 65 within it; 0 with no distance data.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Small business lender' }))
    expect(context()).toHaveTextContent('10 neighborhoods on map')
    fireEvent.change(
      screen.getByRole('textbox', { name: 'Ask a question about Central Florida neighborhoods' }),
      { target: { value: 'All three gaps in Orange County' } },
    )
    fireEvent.click(screen.getByRole('button', { name: /^Ask$/ }))
    expect(context()).toHaveTextContent('Your question')
    const rows = screen.getAllByTestId(/^tract-row-/)
    for (const row of rows) {
      expect(row).toHaveTextContent('Orange')
      expect(row).toHaveTextContent('mi to a site')
    }
    expect(rows).toHaveLength(3)
    expect(
      screen.getByText(`Of these, ${rows.length} are beyond the proximity limit.`),
    ).toBeInTheDocument()
  })

  it('handles empty results, missing positions, and resets stale action plans when the limit changes', () => {
    render(<OpportunitiesApp initialBundle={bundle} initialSites={sites} enableMap={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Make an action plan' }))
    expect(document.querySelector('.brief')).not.toBeNull()
    fireEvent.input(distanceSlider(), { target: { value: '1' } })
    expect(document.querySelector('.brief')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Make an action plan' }))
    expect(document.querySelector('.brief')).toHaveTextContent('3 neighborhoods')
    fireEvent.input(timeSlider(), { target: { value: '30' } })
    expect(context()).toHaveTextContent('0 neighborhoods on map. No areas to emphasize.')
    expect(result()).toHaveTextContent('0 beyond the limit; 12 within it; 0 with no distance data.')
    expect(screen.getByRole('button', { name: 'Make an action plan' })).toBeDisabled()
    expect(document.querySelector('.brief')).toBeNull()

    fireEvent.click(screen.getByTestId('kpi-card-insufficient'))
    expect(result()).toHaveTextContent('0 beyond the limit; 1 within it; 1 with no distance data.')
    expect(screen.queryAllByTestId(/^tract-row-/)).toHaveLength(0)
  })

  it('disables controls until site data is available and labels the estimate', () => {
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} />)
    expect(distanceSlider()).toBeDisabled()
    expect(timeSlider()).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: 'Show gaps beyond this limit' })).toBeDisabled()
    expect(screen.getByText(/Time uses 10 miles = 30 minutes/)).toHaveTextContent(
      'assumption-based estimate',
    )
  })
})
