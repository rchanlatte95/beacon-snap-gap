import { readFile, mkdir, rename, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import type * as GeoJSON from 'geojson'
import {
  DRIVE_TIME_TTL_MS,
  parseDriveTimeCache,
  routingInputs,
  type DriveTimeCache,
  type DriveTimeResult,
} from '../src/map/driveTimes.ts'
import type { TractRecord } from '../src/wizard/alignmentWizard.ts'
import { isLocation } from '../src/map/proximity.ts'

const MATRIX_URL = 'https://api.openrouteservice.org/v2/matrix/driving-car'
const MAX_CELLS = 3500
const REQUEST_INTERVAL_MS = 1700 // Below the hosted Standard limit of 40 requests/minute.

export function matrixMinimums(value: unknown, rows: number, columns: number): DriveTimeResult[] {
  const durations =
    value && typeof value === 'object' && 'durations' in value ? value.durations : null
  if (!Array.isArray(durations) || durations.length !== rows)
    throw new Error('Invalid route matrix')
  return durations.map((row: unknown) => {
    if (
      !Array.isArray(row) ||
      row.length !== columns ||
      row.some(
        (seconds: unknown) =>
          seconds !== null &&
          (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0),
      )
    )
      throw new Error('Invalid route duration')
    const reachable = (row as (number | null)[]).filter(
      (seconds): seconds is number => seconds !== null,
    )
    return reachable.length
      ? { status: 'ok', seconds: Math.min(...reachable) }
      : { status: 'no_route' }
  })
}

export async function refreshDriveTimes(
  options: {
    root?: string
    apiKey?: string
    fetchImpl?: typeof fetch
    now?: number
    pause?: (milliseconds: number) => Promise<unknown>
  } = {},
) {
  const root = options.root ?? process.cwd()
  const output = resolve(root, 'public/data/drive-times.json')
  const now = options.now ?? Date.now()
  const [bundle, sites] = await Promise.all([
    readFile(resolve(root, 'public/data/planner-bundle.json'), 'utf8').then(
      (text) => JSON.parse(text) as { tracts: TractRecord[] },
    ),
    readFile(resolve(root, 'public/data/sites.geojson'), 'utf8').then(
      (text) => JSON.parse(text) as GeoJSON.FeatureCollection,
    ),
  ])
  const { origins, destinations, inputKey } = routingInputs(bundle.tracts, sites)
  let previous: DriveTimeCache | null = null
  try {
    previous = parseDriveTimeCache(JSON.parse(await readFile(output, 'utf8')))
  } catch (error) {
    if (!(error instanceof SyntaxError) && (error as NodeJS.ErrnoException).code !== 'ENOENT')
      throw error
  }
  if (
    previous &&
    (previous.inputKey !== inputKey ||
      Date.parse(previous.fetchedAt) > now ||
      Date.parse(previous.expiresAt) <= now ||
      bundle.tracts.some((tract) => !Object.hasOwn(previous?.results ?? {}, tract.geoid)))
  )
    previous = null
  if (
    previous &&
    Object.values(previous.results).every((result) => result.status !== 'unavailable')
  )
    return previous
  const results: Record<string, DriveTimeResult> = Object.fromEntries(
    bundle.tracts.map((tract) => [
      tract.geoid,
      { status: isLocation(tract.centroid) ? 'unavailable' : 'missing_coordinates' },
    ]),
  )
  if (previous) Object.assign(results, previous.results)
  const pending = origins.filter((origin) => results[origin.geoid]?.status === 'unavailable')
  const apiKey = options.apiKey ?? process.env.ORS_API_KEY
  if (!apiKey) console.warn('Drive times: ORS_API_KEY not set. Using labeled heuristic fallback.')
  if (apiKey && destinations.length > 0) {
    const batchSize = Math.max(1, Math.floor(MAX_CELLS / destinations.length))
    if (destinations.length > MAX_CELLS) throw new Error('Too many sites for one matrix row')
    for (let offset = 0; offset < pending.length; offset += batchSize) {
      if (offset > 0) await (options.pause ?? delay)(REQUEST_INTERVAL_MS)
      const batch = pending.slice(offset, offset + batchSize)
      try {
        const response = await (options.fetchImpl ?? fetch)(MATRIX_URL, {
          method: 'POST',
          headers: { Authorization: apiKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            locations: [...batch.map((origin) => origin.location), ...destinations],
            sources: batch.map((_, index) => String(index)),
            destinations: destinations.map((_, index) => String(batch.length + index)),
            metrics: ['duration'],
          }),
          signal: AbortSignal.timeout(15_000),
        })
        if (!response.ok) {
          console.warn(
            `Drive times: provider returned HTTP ${response.status}. Using labeled fallback for remaining tracts.`,
          )
          break
        }
        const minimums = matrixMinimums(await response.json(), batch.length, destinations.length)
        batch.forEach((origin, index) => {
          results[origin.geoid] = minimums[index]!
        })
      } catch {
        console.warn(
          'Drive times: routing payload unavailable or invalid. Using labeled fallback for remaining tracts.',
        )
        break
      }
    }
  }
  const cache: DriveTimeCache = {
    version: 1,
    provider: 'openrouteservice',
    profile: 'driving-car',
    inputKey,
    fetchedAt: previous?.fetchedAt ?? new Date(now).toISOString(),
    expiresAt: previous?.expiresAt ?? new Date(now + DRIVE_TIME_TTL_MS).toISOString(),
    results,
  }
  await mkdir(resolve(root, 'public/data'), { recursive: true })
  const temporary = `${output}.${process.pid}.tmp`
  await writeFile(temporary, JSON.stringify(cache))
  for (let attempt = 0; ; attempt++) {
    try {
      await rename(temporary, output)
      break
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code
      if (attempt >= 3 || (code !== 'EPERM' && code !== 'EBUSY')) throw error
      await delay(100 * (attempt + 1))
    }
  }
  console.info(
    `Drive times: ${Object.values(results).filter((result) => result.status === 'ok').length}/${bundle.tracts.length} tracts have road-network estimates.`,
  )
  return cache
}

if (import.meta.main) {
  refreshDriveTimes().catch((error: unknown) => {
    console.error(
      'Drive-time cache preparation failed:',
      error instanceof Error ? error.message : error,
    )
    process.exitCode = 1
  })
}
