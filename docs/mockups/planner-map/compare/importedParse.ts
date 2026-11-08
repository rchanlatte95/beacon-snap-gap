// Pure helpers for the "Your own data" Compare-with layer (imported.tsx). Owner: T6.
// Everything here runs in the browser on the user's file. Nothing is sent or stored.
import type { Feature, FeatureCollection, Geometry, Position } from 'geojson'

// The four Central Florida counties (CLAUDE.md): Lake, Orange, Osceola, Seminole.
export const COUNTY_FIPS = ['12069', '12095', '12097', '12117']
export const TRACT_HEADERS = ['geoid', 'tract', 'tract_geoid']
export const MAX_FILE_BYTES = 25 * 1024 * 1024
const MAX_ROWS_LISTED = 5

// ---------------- Results ----------------

// Values per tract GEOID for one named measure. Only tract-level numbers are kept (REQ-4).
export interface Measure {
  label: string
  values: Map<string, number>
  // CSV rows (spreadsheet numbering) that matched a tract but have no number in this column.
  blankRows: number[]
}

export interface ImportResult {
  fileName: string
  kind: 'csv' | 'points'
  measures: Measure[]
  // Plain status lines, shown under the file name.
  status: string[]
}

export class ImportError extends Error {}

// ---------------- CSV ----------------

// RFC 4180 style: commas, double quotes, "" inside quotes, CRLF or LF. Strips a UTF-8 BOM.
export function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false
  const s = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (quoted) {
      if (c === '"') {
        if (s[i + 1] === '"') {
          field += '"'
          i++
        } else quoted = false
      } else field += c
    } else if (c === '"') quoted = true
    else if (c === ',') {
      row.push(field)
      field = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else field += c
  }
  if (field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  return rows.filter((r) => r.some((f) => f.trim() !== ''))
}

export function parseNumber(raw: string | undefined): number | null {
  if (raw === undefined) return null
  const s = raw.trim().replace(/^\$/, '').replace(/,/g, '').replace(/%$/, '').trim()
  if (s === '') return null
  const v = Number(s)
  return Number.isFinite(v) ? v : null
}

type TractId =
  { ok: true; geoid: string } | { ok: false; why: 'blank' | 'short-form' | 'not-a-tract' }

// Accepts an 11-digit GEOID, also with a Census "1400000US" prefix or a ".0" a spreadsheet adds.
export function parseTractId(raw: string | undefined): TractId {
  const s = (raw ?? '').trim()
  if (s === '') return { ok: false, why: 'blank' }
  if (/^\d(\.\d+)?e\+?\d+$/i.test(s)) return { ok: false, why: 'short-form' }
  const m = /^(?:\d*US)?(\d{11})(?:\.0+)?$/i.exec(s)
  return m ? { ok: true, geoid: m[1]! } : { ok: false, why: 'not-a-tract' }
}

const rowList = (rows: number[]) =>
  rows.length <= MAX_ROWS_LISTED
    ? `row${rows.length === 1 ? '' : 's'} ${rows.join(', ')}`
    : `for example rows ${rows.slice(0, MAX_ROWS_LISTED).join(', ')}`
const rowsWord = (k: number) => `${k} row${k === 1 ? '' : 's'}`

export function readCsv(fileName: string, text: string, knownTracts: Set<string>): ImportResult {
  const rows = parseCsv(text)
  if (rows.length === 0) throw new ImportError('This file is empty.')
  const header = rows[0]!.map((h) => h.trim())
  const tractCol = header.findIndex((h) => TRACT_HEADERS.includes(h.toLowerCase()))
  if (tractCol < 0)
    throw new ImportError(
      'We could not find a census tract column. Name it geoid, tract or tract_geoid. ' +
        'It must hold the 11-digit tract number, for example 12069030102.',
    )
  const body = rows.slice(1)
  if (body.length === 0) throw new ImportError('This file has a header row but no data rows.')

  // A number column: not the tract column, at least one number, and 4 in 5 filled cells are numbers.
  const numberCols = header
    .map((h, i) => ({ h, i }))
    .filter(({ i }) => {
      if (i === tractCol) return false
      const filled = body.map((r) => r[i] ?? '').filter((v) => v.trim() !== '')
      const nums = filled.filter((v) => parseNumber(v) !== null).length
      return nums > 0 && nums >= 0.8 * filled.length
    })
  if (numberCols.length === 0)
    throw new ImportError(
      'We found the tract column, but no column with numbers. Add at least one column of numbers.',
    )

  const noId: number[] = []
  const shortForm: number[] = []
  const outside: number[] = []
  const unknown: number[] = []
  const repeated: number[] = []
  const seen = new Set<string>()
  // Row numbers count the header as row 1, as a spreadsheet does.
  const good: { row: number; geoid: string; cells: string[] }[] = []
  body.forEach((cells, k) => {
    const row = k + 2
    const id = parseTractId(cells[tractCol])
    if (!id.ok) {
      ;(id.why === 'short-form' ? shortForm : noId).push(row)
      return
    }
    if (!COUNTY_FIPS.includes(id.geoid.slice(0, 5))) return void outside.push(row)
    if (!knownTracts.has(id.geoid)) return void unknown.push(row)
    if (seen.has(id.geoid)) return void repeated.push(row)
    seen.add(id.geoid)
    good.push({ row, geoid: id.geoid, cells })
  })
  if (good.length === 0)
    throw new ImportError(
      `No row matched a neighborhood in the four counties. ` +
        `${rowsWord(outside.length)} ${outside.length === 1 ? 'was' : 'were'} outside the four counties, ` +
        `${rowsWord(unknown.length)} had a tract number we do not know, ` +
        `and ${rowsWord(noId.length + shortForm.length)} had no tract number we could read.`,
    )

  const status = [`${rowsWord(good.length)} matched a neighborhood (census tract).`]
  if (outside.length)
    status.push(
      `${rowsWord(outside.length)} ${outside.length === 1 ? 'was' : 'were'} outside the four counties.`,
    )
  if (unknown.length)
    status.push(
      `${rowsWord(unknown.length)} had a tract number we do not know (${rowList(unknown)}). ` +
        'The map uses 2020 tracts.',
    )
  if (noId.length)
    status.push(`${rowsWord(noId.length)} had no tract number we could read (${rowList(noId)}).`)
  if (shortForm.length)
    status.push(
      `${rowsWord(shortForm.length)} had a tract number that a spreadsheet changed into a short form ` +
        `like 1.2E+10 (${rowList(shortForm)}). Save the column as text and try again.`,
    )
  if (repeated.length)
    status.push(
      `${rowsWord(repeated.length)} repeated a tract we already had (${rowList(repeated)}). ` +
        'We used the first row for each tract.',
    )

  const measures: Measure[] = numberCols.map(({ h, i }) => {
    const values = new Map<string, number>()
    const blank: number[] = []
    for (const g of good) {
      const v = parseNumber(g.cells[i])
      if (v === null) blank.push(g.row)
      else values.set(g.geoid, v)
    }
    return { label: h || `column ${i + 1}`, values, blankRows: blank }
  })
  // Rows with no number depend on the column, so the panel adds that line for the chosen column.
  return { fileName, kind: 'csv', measures, status }
}

// Rows that matched a tract but have no number in this column (CSV only).
export function blankRowsLine(m: Measure): string | null {
  if (m.blankRows.length === 0) return null
  return `${rowsWord(m.blankRows.length)} had no number in ${m.label} (${rowList(m.blankRows)}).`
}

// ---------------- GeoJSON points ----------------

type Ring = Position[]
interface TractShape {
  geoid: string
  bbox: [number, number, number, number]
  polygons: Ring[][]
}

export function tractShapes(fc: FeatureCollection): TractShape[] {
  const shapes: TractShape[] = []
  for (const f of fc.features) {
    const geoid = String(f.properties?.geoid ?? '')
    const g = f.geometry
    if (!geoid || !g) continue
    const polygons =
      g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : null
    if (!polygons) continue
    let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity]
    for (const poly of polygons)
      for (const [x, y] of poly[0] ?? []) {
        w = Math.min(w, x!)
        e = Math.max(e, x!)
        s = Math.min(s, y!)
        n = Math.max(n, y!)
      }
    shapes.push({ geoid, bbox: [w, s, e, n], polygons })
  }
  return shapes
}

// Ray casting. A point is inside a polygon when it is inside the outer ring and in no hole.
function inRing(x: number, y: number, ring: Ring): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i] as [number, number]
    const [xj, yj] = ring[j] as [number, number]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

export function tractAt(x: number, y: number, shapes: TractShape[]): string | null {
  for (const t of shapes) {
    const [w, s, e, n] = t.bbox
    if (x < w || x > e || y < s || y > n) continue
    for (const [outer, ...holes] of t.polygons)
      if (outer && inRing(x, y, outer) && !holes.some((h) => inRing(x, y, h))) return t.geoid
  }
  return null
}

function features(json: unknown): Feature[] {
  const o = json as { type?: string; features?: unknown; geometry?: unknown }
  if (o?.type === 'FeatureCollection' && Array.isArray(o.features)) return o.features as Feature[]
  if (o?.type === 'Feature') return [o as Feature]
  if (typeof o?.type === 'string' && 'coordinates' in (o as object))
    return [{ type: 'Feature', properties: {}, geometry: o as Geometry }]
  throw new ImportError(
    'This JSON file is not GeoJSON. We need a GeoJSON FeatureCollection of points.',
  )
}

// Counts points per tract, then drops the points: only the counts leave this function.
export function readPoints(fileName: string, text: string, shapes: TractShape[]): ImportResult {
  let json: unknown
  try {
    json = JSON.parse(text.charCodeAt(0) === 0xfeff ? text.slice(1) : text)
  } catch {
    throw new ImportError('This file is not valid JSON, so we could not read it as GeoJSON.')
  }
  const counts = new Map<string, number>(shapes.map((s) => [s.geoid, 0]))
  let inside = 0
  let outside = 0
  let badLocation = 0
  let notPoint = 0
  for (const f of features(json)) {
    const g = f?.geometry
    const pts: Position[] =
      g?.type === 'Point' ? [g.coordinates] : g?.type === 'MultiPoint' ? g.coordinates : []
    if (!g || (g.type !== 'Point' && g.type !== 'MultiPoint')) {
      notPoint++
      continue
    }
    for (const p of pts) {
      const [x, y] = p
      if (typeof x !== 'number' || typeof y !== 'number' || Math.abs(x) > 180 || Math.abs(y) > 90) {
        badLocation++
        continue
      }
      const geoid = tractAt(x, y, shapes)
      if (geoid === null) outside++
      else {
        inside++
        counts.set(geoid, (counts.get(geoid) ?? 0) + 1)
      }
    }
  }
  const total = inside + outside + badLocation
  if (total === 0)
    throw new ImportError(
      notPoint > 0
        ? `This file has ${notPoint} shapes, but no points. We can only count points (for example offices or sites).`
        : 'This file has no points.',
    )
  const word = (k: number) => `${k} point${k === 1 ? '' : 's'}`
  const status = [`${word(inside)} fell inside a neighborhood (census tract) on the map.`]
  if (outside)
    status.push(
      `${word(outside)} are not inside any of our neighborhoods. Most likely they are outside the four counties.`,
    )
  if (badLocation)
    status.push(`${word(badLocation)} had no usable location (longitude and latitude).`)
  if (notPoint)
    status.push(
      `${notPoint} feature${notPoint === 1 ? ' was not a point' : 's were not points'}, so we skipped ${notPoint === 1 ? 'it' : 'them'}.`,
    )
  if (inside === 0)
    status.push('No point fell inside the four counties, so every neighborhood shows 0.')
  status.push(
    'We counted the points and then let them go. The map shows only the count per neighborhood.',
  )
  return {
    fileName,
    kind: 'points',
    measures: [{ label: 'points in your file', values: counts, blankRows: [] }],
    status,
  }
}

// ---------------- Classes and summaries ----------------

export function median(vs: number[]): number | null {
  if (vs.length === 0) return null
  const s = [...vs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2
}

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo]! + (sorted[hi]! - sorted[lo]!) * (pos - lo)
}

export const formatValue = (v: number) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: Math.abs(v) < 100 ? 2 : 0 }).format(v)

// Up to 4 classes from the quartiles of the file's own values. Repeated cut points are merged,
// so a file with few distinct values (for example counts of 0 and 1) gets fewer classes.
// Class k holds values above cut k-1 and up to cut k (the last class has no upper cut).
export interface Classes {
  cuts: number[]
  labels: string[]
  classOf: (v: number) => number
}

export function quartileClasses(values: number[]): Classes {
  const s = [...values].sort((a, b) => a - b)
  const min = s[0]!
  const max = s[s.length - 1]!
  const cuts = [...new Set([0.25, 0.5, 0.75].map((q) => quantile(s, q)))].filter((c) => c < max)
  const ints = s.every(Number.isInteger) && cuts.every(Number.isInteger)
  const f = formatValue
  const labels: string[] = []
  for (let k = 0; k <= cuts.length; k++) {
    const lo = k === 0 ? null : cuts[k - 1]!
    const hi = k === cuts.length ? null : cuts[k]!
    if (ints) {
      const a = lo === null ? min : lo + 1
      const b = hi === null ? max : hi
      labels.push(a === b ? f(a) : `${f(a)} to ${f(b)}`)
    } else if (lo === null) labels.push(`${f(hi ?? max)} or less`)
    else if (hi === null) labels.push(`over ${f(lo)}`)
    else labels.push(`over ${f(lo)} to ${f(hi)}`)
  }
  const classOf = (v: number) => {
    let k = 0
    while (k < cuts.length && v > cuts[k]!) k++
    return k
  }
  return { cuts, labels, classOf }
}

// Spread n classes over the palette, light to dark.
export function pickColors(palette: readonly string[], n: number): string[] {
  if (n <= 1) return [palette[Math.floor(palette.length / 2)]!]
  return Array.from(
    { length: n },
    (_, i) => palette[Math.round((i * (palette.length - 1)) / (n - 1))]!,
  )
}
