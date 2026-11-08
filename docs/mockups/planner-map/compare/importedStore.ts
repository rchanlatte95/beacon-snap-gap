// State and helpers for the "Your own data" Compare-with layer (imported.ts). Owner: T6.
// The loaded file lives in module memory only (no browser storage) until reload or "Remove file".
import type { GeoJSONSource, Map as MapLibre } from 'maplibre-gl'
import type { Feature, FeatureCollection } from 'geojson'
import { CLASS_LABEL } from '../model'
import type { Records, Tract } from '../model'
import { COMPARE_SEQ } from '../mapStyle'
import type { CompareContext } from './types'
import { ImportError, formatValue, median, pickColors, quartileClasses } from './importedParse'
import type { ImportResult, Measure } from './importedParse'

export const SOURCE = 'imported'
export const FILL = 'imported-fill'
export const HIGH_NEED = 'imported-high-need'
// Tracts that have no value in the user's file. White, so they do not read as a value class.
export const NO_VALUE = '#FFFFFF'
export const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

export const SOURCES = [
  { id: 'Your file', label: 'Your own file (not checked by us)' },
  {
    id: 'DS-H3',
    label: 'Sample CSV: Census ACS 2020-2024 table S1901, median household income by tract',
  },
  { id: 'DS-X28', label: 'Sample CSV: the repo extract of S1901, checked against Census B19013' },
  {
    id: 'DS-X12',
    label:
      'Sample points: Second Harvest food finder site locations (redistribution permission not obtained)',
  },
]

// ---------------- In-memory store ----------------
// The Panel unmounts when the user picks another Compare layer, and cardLines is a plain
// function, so the loaded file lives in module memory (not browser storage) until reload.

export interface Loaded {
  result: ImportResult
  measureIdx: number
}
let loaded: Loaded | null = null
const listeners = new Set<() => void>()
export function setLoaded(next: Loaded | null) {
  loaded = next
  listeners.forEach((l) => l())
}
export function subscribe(l: () => void) {
  listeners.add(l)
  return () => listeners.delete(l)
}
export const getLoaded = () => loaded

// Tract shapes, read once from the map's tract source.
let tractsCache: FeatureCollection | null = null
export async function tractFeatures(map: MapLibre): Promise<FeatureCollection> {
  if (tractsCache) return tractsCache
  const src = map.getSource('tracts') as GeoJSONSource | undefined
  if (!src || typeof src.getData !== 'function')
    throw new ImportError('The map has no neighborhood shapes yet. Try again in a moment.')
  tractsCache = (await src.getData()) as FeatureCollection
  return tractsCache
}

// ---------------- What to show ----------------

export interface View {
  measure: Measure
  labels: string[]
  colors: string[]
  cuts: number[]
  classOf: (v: number) => number
  comparison: string
  // A second plain line (points files: the middle values).
  secondary: string | null
  method: string
}

export function buildView(l: Loaded, records: Records): View | null {
  const measure = l.result.measures[l.measureIdx]
  if (!measure || measure.values.size === 0) return null
  const { cuts, labels, classOf } = quartileClasses([...measure.values.values()])
  const colors = pickColors(COMPARE_SEQ, labels.length)
  const isPoints = l.result.kind === 'points'

  const high: number[] = []
  const other: number[] = []
  for (const t of records.tracts) {
    const v = measure.values.get(t.geoid)
    if (v === undefined) continue
    if (t.cls === 'desert') high.push(v)
    else if (t.cls === 'nogap') other.push(v)
  }
  const highTotal = records.counts.desert
  const mh = median(high)
  const mo = median(other)
  const f = formatValue
  let medians: string
  if (high.length < 3 || mh === null || mo === null)
    medians = `Too few high-need neighborhoods have a value in your file to compare (${high.length} of ${highTotal}).`
  else {
    const what = isPoints ? 'Your file has' : `Your data (${measure.label}) is`
    const more = isPoints ? 'more points' : 'higher'
    const less = isPoints ? 'fewer points' : 'lower'
    medians =
      mh === mo
        ? `${isPoints ? 'Your file has' : `Your data (${measure.label}) has`} the same middle value in high-need neighborhoods and in other neighborhoods (${f(mh)}).`
        : `${what} ${mh > mo ? more : less} in high-need neighborhoods (middle value ${f(mh)}) than in other neighborhoods (middle value ${f(mo)}).`
  }
  // For points, most neighborhoods have 0, so the middle values often match. The share of
  // neighborhoods with at least one point says more, so it leads and the medians follow.
  let comparison = medians
  let secondary: string | null = null
  if (isPoints && high.length > 0 && other.length > 0) {
    const hh = high.filter((v) => v > 0).length
    const oo = other.filter((v) => v > 0).length
    const part = (k: number, n: number) =>
      `${k} of ${n}${k === 0 ? '' : `, about 1 in ${Math.round(n / k)}`}`
    const sh = hh / high.length
    const so = oo / other.length
    comparison =
      sh === so
        ? `The same share of high-need neighborhoods (${part(hh, high.length)}) and other neighborhoods (${part(oo, other.length)}) have at least one of your points.`
        : `A ${sh > so ? 'larger' : 'smaller'} share of high-need neighborhoods have at least one of your points (${part(hh, high.length)}) than other neighborhoods (${part(oo, other.length)}).`
    secondary = medians
  }
  const method =
    `Medians over ${high.length} of ${highTotal} ${CLASS_LABEL.desert} tracts and ${other.length} of ` +
    `${records.counts.nogap} ${CLASS_LABEL.nogap} tracts that have a value. ` +
    `${CLASS_LABEL.insufficient} tracts are left out.`
  return { measure, labels, colors, cuts, classOf, comparison, secondary, method }
}

export async function drawOnMap(map: MapLibre, view: View | null) {
  const src = map.getSource(SOURCE) as GeoJSONSource | undefined
  if (!src) return
  if (!view) {
    await src.setData(EMPTY)
    return
  }
  const tracts = await tractFeatures(map)
  const features: Feature[] = tracts.features.map((f) => {
    const geoid = String(f.properties?.geoid ?? '')
    const v = view.measure.values.get(geoid)
    return {
      type: 'Feature',
      geometry: f.geometry,
      properties: {
        geoid,
        cls: f.properties?.cls ?? null,
        color: v === undefined ? NO_VALUE : view.colors[view.classOf(v)],
      },
    }
  })
  await src.setData({ type: 'FeatureCollection', features })
}

export function kindOf(name: string, text: string): 'csv' | 'points' {
  const ext = name.toLowerCase().split('.').pop()
  if (ext === 'csv' || ext === 'txt') return 'csv'
  if (ext === 'geojson' || ext === 'json') return 'points'
  return /^\s*[[{]/.test(text) ? 'points' : 'csv'
}

// ---------------- Card ----------------

export function cardLines(t: Tract, ctx: CompareContext): string[] {
  if (!loaded) return ['No file loaded yet. Choose one in the sidebar under Compare with.']
  const view = buildView(loaded, ctx.records)
  if (!view) return ['Your file has no value for this neighborhood.']
  const v = view.measure.values.get(t.geoid)
  if (v === undefined) return ['Your file has no value for this neighborhood.']
  const label = loaded.result.kind === 'points' ? 'number of points' : view.measure.label
  return [`Your file: ${label} = ${formatValue(v)} for this neighborhood.`]
}
