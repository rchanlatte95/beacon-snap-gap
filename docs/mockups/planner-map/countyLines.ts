// County lines without the stray inside segments. Owner: the map-readability task (T8).
//
// make-standin.mjs builds each county outline from the tract edges that occur only once in
// that county. Two neighbor tracts often have different vertices on the edge they share, so
// many inside edges also occur only once. The map then drew county-weight lines through the
// middle of a county (for example 2,045 of 2,844 Orange segments). This filter keeps a
// segment only when it does not lie on the edge of a different tract in the same county.
// It keeps the edges between two counties and the outer edge of the drawn area.
import type { Feature, FeatureCollection, Position } from 'geojson'

// About 10 m. Results are the same from 10 m to 100 m, so the value is not sensitive.
const EPS = 1e-4
const CELL = 0.01
const COUNTY_FIPS: Record<string, string> = {
  Orange: '095',
  Seminole: '117',
  Lake: '069',
  Osceola: '097',
}

interface Seg {
  a: Position
  b: Position
  geoid: string
}

function rings(f: Feature): Position[][] {
  const g = f.geometry
  if (g.type === 'Polygon') return g.coordinates
  if (g.type === 'MultiPolygon') return g.coordinates.flat()
  return []
}

function distToSeg(p: Position, a: Position, b: Position): number {
  const [px, py] = [p[0]!, p[1]!]
  const [ax, ay, bx, by] = [a[0]!, a[1]!, b[0]!, b[1]!]
  const dx = bx - ax
  const dy = by - ay
  const len2 = dx * dx + dy * dy
  const t = len2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0
  return Math.hypot(px - ax - t * dx, py - ay - t * dy)
}

export function cleanCountyLines(
  counties: FeatureCollection,
  tracts: FeatureCollection,
): FeatureCollection {
  const grid = new Map<string, Seg[]>()
  const cell = (v: number) => Math.floor(v / CELL)
  for (const f of tracts.features) {
    const geoid = String(f.properties?.geoid ?? '')
    for (const ring of rings(f))
      for (let i = 0; i < ring.length - 1; i++) {
        const a = ring[i]!
        const b = ring[i + 1]!
        const s: Seg = { a, b, geoid }
        const [x0, x1] = [cell(Math.min(a[0]!, b[0]!) - EPS), cell(Math.max(a[0]!, b[0]!) + EPS)]
        const [y0, y1] = [cell(Math.min(a[1]!, b[1]!) - EPS), cell(Math.max(a[1]!, b[1]!) + EPS)]
        for (let x = x0; x <= x1; x++)
          for (let y = y0; y <= y1; y++) {
            const k = `${x},${y}`
            const list = grid.get(k)
            if (list) list.push(s)
            else grid.set(k, [s])
          }
      }
  }

  const features = counties.features.map((f): Feature => {
    const fips = COUNTY_FIPS[String(f.properties?.county)]
    if (!fips || f.geometry.type !== 'MultiLineString') return f
    const kept = f.geometry.coordinates.filter((line) => {
      const a = line[0]
      const b = line[line.length - 1]
      if (!a || !b) return false
      const m: Position = [(a[0]! + b[0]!) / 2, (a[1]! + b[1]!) / 2]
      const near = (grid.get(`${cell(m[0]!)},${cell(m[1]!)}`) ?? []).filter(
        (s) => distToSeg(m, s.a, s.b) < EPS,
      )
      const owners = new Set(near.map((s) => s.geoid))
      // One owner: the segment's own tract only, so it is an outer edge. Keep it.
      if (owners.size <= 1) return true
      // Shared with a tract in another county: a county border. Keep it.
      // Shared only with tracts in the same county: an inside edge. Drop it.
      return [...owners].some((g) => g.slice(2, 5) !== fips)
    })
    return { ...f, geometry: { type: 'MultiLineString', coordinates: kept } }
  })
  return { ...counties, features }
}
