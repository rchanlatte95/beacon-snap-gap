import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import type { FeatureCollection } from 'geojson'
import { act, fireEvent, render, renderHook, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { OpportunitiesApp, type PlannerBundle } from '../src/App'
import { DRIVE_TIME_TTL_MS, routingInputs, type DriveTimeCache } from '../src/map/driveTimes'
import { useDriveTimes } from '../src/map/useDriveTimes'

const bundle: PlannerBundle = JSON.parse(
  readFileSync(resolve('public/data/planner-bundle.json'), 'utf8'),
)
const focus = bundle.tracts.find((tract) => tract.geoid === '12095016510')!
const sites: FeatureCollection = {
  type: 'FeatureCollection',
  features: [0, 0.1, 0.2].map((offset) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'Point', coordinates: [focus.centroid![0], focus.centroid![1] + offset] },
  })),
}
function cache(): DriveTimeCache {
  const now = Date.now()
  return {
    version: 1,
    provider: 'openrouteservice',
    profile: 'driving-car',
    inputKey: routingInputs(bundle.tracts, sites).inputKey,
    fetchedAt: new Date(now - 1000).toISOString(),
    expiresAt: new Date(now + DRIVE_TIME_TTL_MS - 1000).toISOString(),
    results: { [focus.geoid]: { status: 'ok', seconds: 1260 } },
  }
}
function openTract() {
  fireEvent.click(screen.getByTestId('kpi-card-high_need'))
  fireEvent.click(screen.getByTestId(`tract-row-${focus.geoid}`))
}
const controls = () => screen.getByRole('region', { name: 'Distance and gap rules' })
// The notes and credits sit on the neighborhood card and in the map's (i) box, not under the slider.
const card = () => screen.getByTestId('tract-evidence-panel')

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('cached drive times in the map controls', () => {
  it('replaces only the time slider, credits route data, and preserves live distance filtering and site counts', async () => {
    const request = vi.fn<typeof fetch>().mockImplementation(async () => Response.json(cache()))
    vi.stubGlobal('fetch', request)
    render(<OpportunitiesApp initialBundle={bundle} initialSites={sites} enableMap={false} />)
    expect(controls()).toHaveTextContent('Select a neighborhood')
    openTract()
    await screen.findAllByText(/Estimated drive to a Second Harvest site: 21 min/)
    expect(screen.getAllByRole('slider')).toHaveLength(1)
    expect(screen.queryByRole('slider', { name: /time|minute/i })).toBeNull()
    expect(within(card()).getByRole('link', { name: 'openrouteservice' })).toHaveAttribute(
      'href',
      'https://openrouteservice.org/',
    )
    expect(within(card()).getByRole('link', { name: 'CC BY-SA 4.0' })).toHaveAttribute(
      'href',
      'https://creativecommons.org/licenses/by-sa/4.0/',
    )
    expect(card()).toHaveTextContent('Updated')
    expect(card()).toHaveTextContent('No live traffic')
    expect(controls()).not.toHaveTextContent('No live traffic')
    const slider = screen.getByRole('slider', { name: 'Distance limit in miles' })
    for (const [miles, expectedSites] of [
      [0, 0],
      [10, 41],
      [20, 158],
    ]) {
      fireEvent.change(slider, { target: { value: String(miles) } })
      const panel = screen.getByTestId('tract-evidence-panel')
      const fact = within(panel).getByText(`Sites within ${miles} miles`).closest('.fact')!
      expect(fact.querySelector('dd')).toHaveTextContent(String(expectedSites))
      expect(controls()).toHaveTextContent('Estimated drive to a Second Harvest site: 21 min')
      expect(
        screen.getByRole('checkbox', { name: 'Show only gaps beyond this distance' }),
      ).toBeChecked()
      expect(document.getElementById('gap-emphasis-context')).toHaveTextContent(
        `Beyond ${miles} mi`,
      )
      expect(document.getElementById('gap-emphasis-context')).not.toHaveTextContent(/min/)
    }
    expect(request).toHaveBeenCalledTimes(1)
    expect(request.mock.calls[0]![0]).toBe('/data/drive-times.json')
    for (const [name, value] of [
      ['High poverty', '90'],
      ['Many with no car', '90'],
      ['Few business loans', '50'],
    ]) {
      const select = screen.getByRole('combobox', { name })
      fireEvent.change(select, { target: { value } })
      expect(select).toHaveValue(value)
      expect(controls()).toHaveTextContent('Estimated drive to a Second Harvest site: 21 min')
    }
    fireEvent.click(screen.getByRole('button', { name: 'Reset rules' }))
    expect(slider).toHaveValue('10')
    expect(
      screen.getByRole('checkbox', { name: 'Show only gaps beyond this distance' }),
    ).not.toBeChecked()
    expect(screen.getByRole('combobox', { name: 'High poverty' })).toHaveValue('75')
    expect(screen.getByRole('combobox', { name: 'Many with no car' })).toHaveValue('75')
    expect(screen.getByRole('combobox', { name: 'Few business loans' })).toHaveValue('25')
  })

  it.each(['missing', 'network', 'invalid', 'expired', 'changed', 'no-route'] as const)(
    'clearly labels %s route data and preserves the distance slider',
    async (failure) => {
      const value = cache()
      const request = vi.fn<typeof fetch>().mockImplementation(async () => {
        if (failure === 'network') throw new TypeError('offline')
        if (failure === 'missing') return new Response(null, { status: 404 })
        if (failure === 'invalid')
          return Response.json({
            ...value,
            results: { [focus.geoid]: { status: 'ok', seconds: 'bad' } },
          })
        if (failure === 'expired')
          return Response.json({
            ...value,
            fetchedAt: new Date(Date.now() - DRIVE_TIME_TTL_MS - 1000).toISOString(),
            expiresAt: new Date(Date.now() - 1000).toISOString(),
          })
        if (failure === 'changed') return Response.json({ ...value, inputKey: 'old locations' })
        return Response.json({ ...value, results: { [focus.geoid]: { status: 'no_route' } } })
      })
      vi.stubGlobal('fetch', request)
      render(<OpportunitiesApp initialBundle={bundle} initialSites={sites} enableMap={false} />)
      openTract()
      await act(async () => {})
      expect(card()).toHaveTextContent('Heuristic fallback: 10 miles = 30 minutes')
      expect(controls()).not.toHaveTextContent('Heuristic fallback')
      expect(controls()).toHaveTextContent(
        'Estimated drive to a Second Harvest site: 9 min (heuristic)',
      )
      expect(card()).toHaveTextContent('The other 20% may need longer')
      expect(controls()).not.toHaveTextContent('Estimated drive to a Second Harvest site: 0 min')
      expect(within(card()).queryByRole('link', { name: 'openrouteservice' })).toBeNull()
      fireEvent.change(screen.getByRole('slider'), { target: { value: '20' } })
      expect(document.getElementById('gap-emphasis-context')).toHaveTextContent('Beyond 20 mi')
    },
  )

  it('checks the cache periodically, falls back when it expires or cannot be fetched, and recovers', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-08T17:00:00Z'))
    const value = cache()
    const request = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(value))
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockImplementation(async () => Response.json(cache()))
    vi.stubGlobal('fetch', request)
    const { result, unmount } = renderHook(() => useDriveTimes(true))
    await act(async () => {})
    expect(result.current.cache).toEqual(value)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(result.current.cache).toBeNull()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(result.current.cache?.provider).toBe('openrouteservice')
    expect(request).toHaveBeenCalledTimes(3)
    unmount()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(request).toHaveBeenCalledTimes(3)
  })

  it('aborts a slow cache request instead of leaving the app pending', async () => {
    vi.useFakeTimers()
    const request = vi.fn<typeof fetch>().mockImplementation(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options?.signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          )
        }),
    )
    vi.stubGlobal('fetch', request)
    const { result } = renderHook(() => useDriveTimes(true))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(request.mock.calls[0]![1]!.signal!.aborted).toBe(true)
    expect(result.current.cache).toBeNull()
  })
})
