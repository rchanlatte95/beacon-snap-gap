// Compare-with layer: where SBA small business loans went, next to food need. Owner: task T5.
//
// The user feedback asked to contrast need against where loans go, and claimed that people
// who need food also need SBA lending. Task T0 tested the claim and it is NOT supported
// (finding F-3, docs/analysis/need-vs-sba-lending.md). This layer shows where loans went and
// says what the comparison does and does not show. It must not claim that food need and SBA
// lending line up, and must not claim that high-need areas get less lending.
//
// Data: data/lending.standin.json, written by compare/make-lending.mjs (DS-X5, DS-X24).
//
// This module: data, plain-word helpers and map helpers, shared by lending.ts and lendingPanel.tsx.
import { MapMouseEvent } from 'maplibre-gl'
import type { Map as MapLibre } from 'maplibre-gl'
import { COLORS, COMPARE_SEQ } from '../mapStyle'
import { fmt } from '../model'
import type { Tract } from '../model'
import type { CompareContext } from './types'

// ---------------- Data ----------------

export type Group =
  | 'high-need-low-lending'
  | 'high-need-high-lending'
  | 'other-low-lending'
  | 'other-high-lending'
  | null

export interface LendingTract {
  loans: number
  loans20: number
  per1k: number | null
  per1k20: number | null
  usdPer1k: number | null
  usdPer1k20: number | null
  group: Group
}

export interface LendingFile {
  generated: string
  analysisTracts: number
  medianLoansPer1k: number
  spearman: { pctSnap: number; pctPoverty: number }
  tracts: Record<string, LendingTract>
}

export interface Row {
  t: Tract
  l: LendingTract & { per1k: number }
}

export interface Derived {
  file: LendingFile
  // Analysis set (F-3): high-need and "no gap" tracts with people.
  set: Row[]
  high: Row[]
  other: Row[]
  cut: number
  // High-need tracts below the median, lowest first.
  closer: Row[]
}

export const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = s.length / 2
  return s.length === 0 ? NaN : s.length % 2 ? s[Math.floor(m)]! : (s[m - 1]! + s[m]!) / 2
}

const cache = new WeakMap<object, Derived>()
export function derive(ctx: CompareContext): Derived | null {
  const file = ctx.extra as LendingFile | undefined
  if (!file || typeof file !== 'object' || !file.tracts) return null
  const hit = cache.get(file)
  if (hit) return hit
  const set: Row[] = []
  for (const t of ctx.records.tracts) {
    const l = file.tracts[t.geoid]
    if (l && l.group !== null && l.per1k !== null) set.push({ t, l: { ...l, per1k: l.per1k } })
  }
  const cut = median(set.map((r) => r.l.per1k))
  const high = set.filter((r) => r.t.cls === 'desert')
  const other = set.filter((r) => r.t.cls !== 'desert')
  const closer = high.filter((r) => r.l.per1k < cut).sort((a, b) => a.l.per1k - b.l.per1k)
  const d = { file, set, high, other, cut, closer }
  cache.set(file, d)
  return d
}

// ---------------- Plain words ----------------

export const loansWord = (k: number) => `${fmt.format(k)} ${k === 1 ? 'loan' : 'loans'}`

// A share as words people can picture: "about half", "about 7 in 10".
export function inTen(frac: number): string {
  const k = Math.round(frac * 10)
  if (k === 5) return 'about half'
  if (k <= 0) return 'less than 1 in 10'
  if (k >= 10) return 'almost all'
  return `about ${k} in 10`
}

export function rateWords(per1k: number): string {
  if (per1k === 0) return 'no SBA loans'
  if (per1k < 1) return 'less than 1 SBA loan'
  const k = Math.round(per1k)
  return `about ${k} SBA ${k === 1 ? 'loan' : 'loans'}`
}

// ---------------- Map ----------------

export const LAYER_FILL = 'lending-fill'
export const LAYER_ZERO = 'lending-zero'
export const LAYER_NEED = 'lending-need-line'
export const DOTS = 'lending-dots'

// Map classes: loans per 1,000 residents, all years. Round breaks; the median (about 1.8)
// falls in the middle class. No-loan tracts get a dot pattern so they stand out.
export const BANDS = [
  { id: 'low', label: 'Fewer than 1', min: 0, max: 1, color: COMPARE_SEQ[1] },
  { id: 'mid', label: '1 to 3', min: 1, max: 3, color: COMPARE_SEQ[2] },
  { id: 'high', label: '3 or more', min: 3, max: Infinity, color: COMPARE_SEQ[3] },
] as const
export const bandOf = (per1k: number) =>
  BANDS.find((b) => per1k > 0 && per1k >= b.min && per1k < b.max)

function hexRgb(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}

export function dotsImage() {
  const size = 8
  const data = new Uint8Array(size * size * 4)
  const [r, g, b] = hexRgb(COLORS.primary700)
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const on = (x === 3 || x === 4) && (y === 3 || y === 4)
      data.set(on ? [r, g, b, 255] : [255, 255, 255, 255], (y * size + x) * 4)
    }
  return { width: size, height: size, data }
}

// Fly to a tract, then click it, so the shell opens its card. The click goes through the
// map's own click event, so the shell's selection code stays the only code that selects.
export function showTract(map: MapLibre | null, t: Tract) {
  if (!map || !t.centroid) return
  const c = t.centroid
  map.once('idle', () => {
    const point = map.project(c)
    const hit = map.queryRenderedFeatures(point, { layers: [LAYER_FILL, LAYER_ZERO] })[0]
    if (!hit || String(hit.properties.geoid) !== t.geoid) return
    const box = map.getCanvas().getBoundingClientRect()
    const click = new MouseEvent('click', {
      clientX: box.left + point.x,
      clientY: box.top + point.y,
    })
    map.fire(new MapMouseEvent('click', map, click))
  })
  map.easeTo({ center: c, zoom: Math.max(map.getZoom(), 12), duration: 600 })
}

export const SOURCES = [
  { id: 'DS-X5', label: 'SBA 7(a) and 504 loan data, placed by census tract' },
  { id: 'F-3', label: 'Finding: SBA lending per resident does not follow food need' },
  { id: 'DS-X24', label: '2020 Census block population, summed by tract' },
]
