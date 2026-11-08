import type { TractRecord } from '../wizard/alignmentWizard'

export const DEFAULT_REACH_MILES = 10
export const DEFAULT_REACH_MINUTES = 30
export const MAX_REACH_MILES = 20
export const REACH_STEP_MILES = 0.5

export type ProximityIndex = ReadonlyMap<string, number | null>

function isLocation(point: readonly number[] | null): point is readonly [number, number] {
  return (
    point !== null &&
    point.length >= 2 &&
    Number.isFinite(point[0]) &&
    Number.isFinite(point[1]) &&
    Math.abs(point[0]!) <= 180 &&
    Math.abs(point[1]!) <= 90
  )
}

export function distanceMiles(a: readonly [number, number], b: readonly [number, number]): number {
  const radians = Math.PI / 180
  const h =
    Math.sin(((b[1] - a[1]) * radians) / 2) ** 2 +
    Math.cos(a[1] * radians) *
      Math.cos(b[1] * radians) *
      Math.sin(((b[0] - a[0]) * radians) / 2) ** 2
  return 2 * 3958.8 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h))))
}

function siteLocations(sites: GeoJSON.FeatureCollection) {
  return sites.features.flatMap((feature) => {
    const point = feature.geometry?.type === 'Point' ? feature.geometry.coordinates : null
    return isLocation(point) ? [point] : []
  })
}

export function sitesWithinMiles(
  center: readonly [number, number] | null,
  sites: GeoJSON.FeatureCollection,
  miles: number,
): number | null {
  const locations = siteLocations(sites)
  if (!isLocation(center) || locations.length === 0) return null
  return locations.filter((site) => distanceMiles(center, site) <= miles).length
}

export function nearestSiteDistances(
  tracts: readonly Pick<TractRecord, 'geoid' | 'centroid'>[],
  sites: GeoJSON.FeatureCollection,
): ProximityIndex {
  const locations = siteLocations(sites)
  return new Map(
    tracts.map((tract) => [
      tract.geoid,
      isLocation(tract.centroid) && locations.length > 0
        ? locations.reduce(
            (nearest, site) => Math.min(nearest, distanceMiles(tract.centroid!, site)),
            Infinity,
          )
        : null,
    ]),
  )
}

export function clampReachMiles(value: number): number {
  const finite = Number.isFinite(value) ? value : DEFAULT_REACH_MILES
  return (
    Math.round(Math.min(MAX_REACH_MILES, Math.max(0, finite)) / REACH_STEP_MILES) * REACH_STEP_MILES
  )
}

export function reachMinutes(miles: number): number {
  return (miles * DEFAULT_REACH_MINUTES) / DEFAULT_REACH_MILES
}

export function reachMiles(minutes: number): number {
  return clampReachMiles((minutes * DEFAULT_REACH_MILES) / DEFAULT_REACH_MINUTES)
}

export function evaluateProximity(
  tracts: readonly TractRecord[],
  distances: ProximityIndex,
  limitMiles: number,
) {
  const outside: TractRecord[] = []
  const unknown: TractRecord[] = []
  let withinCount = 0
  for (const tract of tracts) {
    const distance = distances.get(tract.geoid)
    if (distance === null || distance === undefined) unknown.push(tract)
    else if (distance > limitMiles) outside.push(tract)
    else withinCount++
  }
  return { outside, unknown, withinCount }
}
