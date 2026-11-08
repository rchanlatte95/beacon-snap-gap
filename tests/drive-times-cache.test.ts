// @vitest-environment node
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import type { FeatureCollection } from 'geojson'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { matrixMinimums, refreshDriveTimes } from '../scripts/cache-drive-times'
import {
  DRIVE_TIME_TTL_MS,
  driveTimeEstimate,
  parseDriveTimeCache,
  routingInputs,
} from '../src/map/driveTimes'

const NOW = Date.parse('2026-11-08T17:00:00Z')
const tracts = [
  { geoid: 'a', centroid: [-81, 28] as const },
  { geoid: 'b', centroid: [-81.1, 28.1] as const },
  { geoid: 'water', centroid: null },
]
const sites: FeatureCollection = {
  type: 'FeatureCollection',
  features: [0, 1].map((i) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'Point', coordinates: [-81 + i / 10, 28] },
  })),
}
const roots: string[] = []

async function fixture(places = tracts, destinations = sites) {
  await mkdir(resolve('.tmp'), { recursive: true })
  const root = await mkdtemp(resolve('.tmp/routing-test-'))
  roots.push(root)
  await mkdir(resolve(root, 'public/data'), { recursive: true })
  await writeFile(
    resolve(root, 'public/data/planner-bundle.json'),
    JSON.stringify({ tracts: places }),
  )
  await writeFile(resolve(root, 'public/data/sites.geojson'), JSON.stringify(destinations))
  return root
}

afterEach(async () => {
  vi.restoreAllMocks()
  for (const root of roots.splice(0)) {
    if (!root.startsWith(resolve('.tmp') + sep)) throw new Error('Test cleanup outside workspace')
    await rm(root, { recursive: true, force: true })
  }
})

describe('road-network drive-time cache', () => {
  it('sends every site as a destination, selects shortest seconds, and keeps missing coordinates separate', async () => {
    const root = await fixture()
    const request = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        durations: [
          [900, 120],
          [null, 0],
        ],
      }),
    )
    const cache = await refreshDriveTimes({
      root,
      apiKey: 'test-key',
      fetchImpl: request,
      now: NOW,
    })
    const [url, init] = request.mock.calls[0]!
    expect(url).toBe('https://api.heigit.org/openrouteservice/v2/matrix/driving-car')
    expect(init?.headers).toEqual({ Authorization: 'test-key', 'Content-Type': 'application/json' })
    expect(JSON.parse(init!.body as string)).toEqual({
      locations: [
        [-81, 28],
        [-81.1, 28.1],
        [-81, 28],
        [-80.9, 28],
      ],
      sources: ['0', '1'],
      destinations: ['2', '3'],
      metrics: ['duration'],
    })
    expect(cache.results).toEqual({
      a: { status: 'ok', seconds: 120 },
      b: { status: 'ok', seconds: 0 },
      water: { status: 'missing_coordinates' },
    })
    expect(Date.parse(cache.expiresAt) - Date.parse(cache.fetchedAt)).toBe(24 * 60 * 60 * 1000)
    const saved = await readFile(resolve(root, 'public/data/drive-times.json'), 'utf8')
    expect(JSON.parse(saved)).toEqual(cache)
    expect(saved).not.toContain('test-key')
    expect(driveTimeEstimate('a', 10, cache, cache.inputKey, NOW).minutes).toBe(2)
    expect(driveTimeEstimate('b', 10, cache, cache.inputKey, NOW).minutes).toBe(0)
  })

  it('reuses fresh results without requests, then refreshes at expiry and when sites move', async () => {
    const root = await fixture()
    const request = vi.fn<typeof fetch>().mockImplementation(async () =>
      Response.json({
        durations: [
          [100, 200],
          [300, 400],
        ],
      }),
    )
    const options = { root, apiKey: 'test-key', fetchImpl: request }
    const cache = await refreshDriveTimes({ ...options, now: NOW })
    await refreshDriveTimes({ ...options, now: NOW + 1000 })
    expect(request).toHaveBeenCalledTimes(1)
    await refreshDriveTimes({ ...options, now: NOW + DRIVE_TIME_TTL_MS })
    expect(request).toHaveBeenCalledTimes(2)
    await writeFile(
      resolve(root, 'public/data/sites.geojson'),
      JSON.stringify({ ...sites, features: sites.features.slice(1) }),
    )
    request.mockResolvedValueOnce(Response.json({ durations: [[500], [600]] }))
    const changed = await refreshDriveTimes({ ...options, now: NOW + DRIVE_TIME_TTL_MS + 1 })
    expect(request).toHaveBeenCalledTimes(3)
    expect(changed.inputKey).not.toBe(cache.inputKey)
    expect(changed.results.a).toEqual({ status: 'ok', seconds: 500 })
  })

  it('batches below 3500 cells, stops on failure, and retries only failed origins without extending old results', async () => {
    const manySites: FeatureCollection = {
      ...sites,
      features: Array.from({ length: 1800 }, () => sites.features[0]!),
    }
    const root = await fixture(tracts, manySites)
    const pause = vi.fn(async () => undefined)
    const request = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({ durations: [Array.from({ length: 1800 }, () => 123)] }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 429 }))
    const options = { root, apiKey: 'test-key', fetchImpl: request, pause }
    const partial = await refreshDriveTimes({ ...options, now: NOW })
    expect(partial.results.a).toEqual({ status: 'ok', seconds: 123 })
    expect(partial.results.b).toEqual({ status: 'unavailable' })
    expect(pause).toHaveBeenCalledWith(1700)
    request.mockResolvedValueOnce(
      Response.json({ durations: [Array.from({ length: 1800 }, () => 456)] }),
    )
    const resumed = await refreshDriveTimes({ ...options, now: NOW + 1000 })
    expect(request).toHaveBeenCalledTimes(3)
    const retryBody = JSON.parse(request.mock.calls[2]![1]!.body as string)
    expect(retryBody.locations[0]).toEqual([-81.1, 28.1])
    expect(retryBody.sources.length * retryBody.destinations.length).toBeLessThanOrEqual(3500)
    expect(resumed.results.a).toEqual(partial.results.a)
    expect(resumed.results.b).toEqual({ status: 'ok', seconds: 456 })
    expect(resumed.fetchedAt).toBe(partial.fetchedAt)
    expect(resumed.expiresAt).toBe(partial.expiresAt)
  })

  it.each(['http', 'network', 'timeout', 'payload'] as const)(
    'marks %s failure as unavailable and uses the labeled heuristic',
    async (failure) => {
      const root = await fixture()
      const request = vi.fn<typeof fetch>().mockImplementation(async () => {
        if (failure === 'network') throw new TypeError('Network error')
        if (failure === 'timeout') throw new DOMException('Timed out', 'TimeoutError')
        return failure === 'http'
          ? new Response(null, { status: 503 })
          : Response.json({ durations: [[-1, 0]] })
      })
      const cache = await refreshDriveTimes({
        root,
        apiKey: 'test-key',
        fetchImpl: request,
        now: NOW,
      })
      expect(cache.results.a).toEqual({ status: 'unavailable' })
      const estimate = driveTimeEstimate('a', 10, cache, cache.inputKey, NOW)
      expect(estimate.minutes).toBe(30)
      expect(estimate.routed).toBe(false)
      expect(estimate.note).toContain('Heuristic fallback')
    },
  )

  it('does not call the provider without a key or invent a time without coordinates', async () => {
    const root = await fixture()
    const request = vi.fn<typeof fetch>()
    const cache = await refreshDriveTimes({ root, apiKey: '', fetchImpl: request, now: NOW })
    expect(request).not.toHaveBeenCalled()
    expect(driveTimeEstimate('water', null, cache, cache.inputKey, NOW)).toMatchObject({
      minutes: null,
      routed: false,
    })
    expect(driveTimeEstimate('a', 2, cache, cache.inputKey, NOW).minutes).toBe(6)
  })

  it('separates unreachable routes from valid zero duration and rejects malformed matrices', () => {
    expect(
      matrixMinimums(
        {
          durations: [
            [null, null],
            [0, null],
          ],
        },
        2,
        2,
      ),
    ).toEqual([{ status: 'no_route' }, { status: 'ok', seconds: 0 }])
    for (const durations of [null, [], [[1]], [[-1, 2]], [[NaN, 2]], [['12', 2]]]) {
      expect(() => matrixMinimums({ durations }, 1, 2)).toThrow()
    }
  })

  it('rejects invalid cache values and never serves stale, future-dated, or mismatched results as routed', async () => {
    const root = await fixture()
    const cache = await refreshDriveTimes({
      root,
      apiKey: 'test-key',
      fetchImpl: vi.fn<typeof fetch>().mockResolvedValue(
        Response.json({
          durations: [
            [60, 120],
            [null, null],
          ],
        }),
      ),
      now: NOW,
    })
    expect(parseDriveTimeCache(cache)).toEqual(cache)
    for (const invalid of [
      null,
      {},
      { ...cache, provider: 'google' },
      { ...cache, fetchedAt: 'no date' },
      { ...cache, results: { a: { status: 'ok', seconds: -1 } } },
      { ...cache, expiresAt: new Date(NOW + DRIVE_TIME_TTL_MS + 1).toISOString() },
    ])
      expect(parseDriveTimeCache(invalid)).toBeNull()
    for (const [key, clock] of [
      [cache.inputKey, NOW + DRIVE_TIME_TTL_MS],
      ['other-sites', NOW],
      [cache.inputKey, NOW - 1],
    ] as const) {
      expect(driveTimeEstimate('a', 10, cache, key, clock)).toMatchObject({
        minutes: 30,
        routed: false,
      })
    }
    expect(driveTimeEstimate('b', 10, cache, cache.inputKey, NOW).note).toContain(
      'No road route returned',
    )
    expect(routingInputs(tracts, sites).origins).toHaveLength(2)
  })
})
