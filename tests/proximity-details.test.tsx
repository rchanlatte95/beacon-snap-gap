import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OpportunitiesApp, type PlannerBundle } from '../src/App'
import { sitesWithinMiles } from '../src/map/proximity'

const bundle: PlannerBundle = JSON.parse(
  readFileSync(resolve(process.cwd(), 'public/data/planner-bundle.json'), 'utf8'),
)
const sites: GeoJSON.FeatureCollection = JSON.parse(
  readFileSync(resolve(process.cwd(), 'public/data/sites.geojson'), 'utf8'),
)

function factValue(label: string) {
  return screen.getByText(label).closest('.fact')!.querySelector('dd')
}

describe('nearby-site details follow the slider', () => {
  it('updates the distance label, site count, and people per site for the selected neighborhood', () => {
    render(<OpportunitiesApp initialBundle={bundle} initialSites={sites} enableMap={false} />)
    fireEvent.click(screen.getByTestId('kpi-card-high_need'))
    fireEvent.click(screen.getByTestId('tract-row-12095016510'))

    expect(factValue('Sites within 10 miles')).toHaveTextContent('37')
    expect(factValue('People per nearby site')).toHaveTextContent('228')
    fireEvent.input(screen.getByRole('slider', { name: 'Distance limit in miles' }), {
      target: { value: '0.5' },
    })
    expect(factValue('Sites within 0.5 miles')).toHaveTextContent('0')
    expect(factValue('People per nearby site')).toHaveTextContent('No data')
    expect(screen.queryByText('Sites within 10 miles')).not.toBeInTheDocument()
    fireEvent.input(screen.getByRole('slider', { name: 'Estimated time limit in minutes' }), {
      target: { value: '3' },
    })
    expect(factValue('Sites within 1 mile')).toHaveTextContent('0')
    fireEvent.click(screen.getByRole('button', { name: 'Reset proximity' }))
    expect(factValue('Sites within 10 miles')).toHaveTextContent('37')
    expect(factValue('People per nearby site')).toHaveTextContent('228')
  })

  it('keeps unavailable distances separate from a measured zero-site result', () => {
    expect(sitesWithinMiles(null, sites, 10)).toBeNull()
    expect(
      sitesWithinMiles([-81.3, 28.5], { type: 'FeatureCollection', features: [] }, 10),
    ).toBeNull()
    expect(
      sitesWithinMiles(
        [-81.3, 28.5],
        {
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: {},
              geometry: { type: 'Point', coordinates: [-81.3, 28.5] },
            },
          ],
        },
        0,
      ),
    ).toBe(1)
  })
})
