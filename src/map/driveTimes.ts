import type { TractRecord } from '../wizard/alignmentWizard.ts'
import type * as GeoJSON from 'geojson'
import { isLocation, reachMinutes } from './proximity.ts'

export const DRIVE_TIME_TTL_MS = 24 * 60 * 60 * 1000
export const DRIVE_TIME_REFRESH_MS = 5 * 60 * 1000
export const DRIVE_TIME_FILE = '/data/drive-times.json'

export type DriveTimeResult =
  | { readonly status: 'ok'; readonly seconds: number }
  | { readonly status: 'no_route' | 'unavailable' | 'missing_coordinates' }

export interface DriveTimeCache {
  readonly version: 1
  readonly provider: 'openrouteservice'
  readonly profile: 'driving-car'
  readonly inputKey: string
  readonly fetchedAt: string
  readonly expiresAt: string
  readonly results: Readonly<Record<string, DriveTimeResult>>
}

export function routingInputs(
  tracts: readonly Pick<TractRecord, 'geoid' | 'centroid'>[],
  sites: GeoJSON.FeatureCollection,
) {
  const destinations = sites.features.flatMap((site) => {
    const point = site.geometry?.type === 'Point' ? site.geometry.coordinates : null
    return isLocation(point) ? [[point[0], point[1]] as const] : []
  })
  const origins = tracts.flatMap((tract) =>
    isLocation(tract.centroid) ? [{ geoid: tract.geoid, location: tract.centroid }] : [],
  )
  return { origins, destinations, inputKey: JSON.stringify([origins, destinations]) }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function parseDriveTimeCache(value: unknown): DriveTimeCache | null {
  if (
    !isRecord(value) ||
    value.version !== 1 ||
    value.provider !== 'openrouteservice' ||
    value.profile !== 'driving-car' ||
    typeof value.inputKey !== 'string' ||
    typeof value.fetchedAt !== 'string' ||
    typeof value.expiresAt !== 'string' ||
    !isRecord(value.results)
  )
    return null
  const fetched = Date.parse(value.fetchedAt)
  const expires = Date.parse(value.expiresAt)
  if (
    !Number.isFinite(fetched) ||
    !Number.isFinite(expires) ||
    expires <= fetched ||
    expires - fetched > DRIVE_TIME_TTL_MS
  )
    return null
  for (const result of Object.values(value.results)) {
    if (!isRecord(result)) return null
    if (result.status === 'ok') {
      if (
        typeof result.seconds !== 'number' ||
        !Number.isFinite(result.seconds) ||
        result.seconds < 0
      )
        return null
    } else if (!['no_route', 'unavailable', 'missing_coordinates'].includes(String(result.status)))
      return null
  }
  return value as unknown as DriveTimeCache
}

export function driveTimeEstimate(
  geoid: string,
  miles: number | null | undefined,
  cache: DriveTimeCache | null,
  inputKey: string | null,
  now = Date.now(),
) {
  let reason = 'Route data unavailable'
  if (cache && inputKey !== null) {
    if (cache.inputKey !== inputKey) reason = 'Route locations changed'
    else if (Date.parse(cache.expiresAt) <= now || Date.parse(cache.fetchedAt) > now)
      reason = 'Route cache expired'
    else {
      const result = cache.results[geoid]
      if (result?.status === 'ok') {
        return {
          minutes: result.seconds / 60,
          routed: true,
          note: `openrouteservice · Updated ${new Date(cache.fetchedAt).toLocaleString()}`,
        }
      }
      if (result?.status === 'no_route') reason = 'No road route returned'
      if (result?.status === 'missing_coordinates') reason = 'No population-center coordinates'
      if (result?.status === 'unavailable') reason = 'Routing request failed or not configured'
    }
  }
  return {
    minutes: miles == null || !Number.isFinite(miles) || miles < 0 ? null : reachMinutes(miles),
    routed: false,
    note: `${reason}. Heuristic fallback: 10 miles = 30 minutes; no road routes or traffic.`,
  }
}
