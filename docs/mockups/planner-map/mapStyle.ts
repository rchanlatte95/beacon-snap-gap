// Map style tokens. Owner: the map-readability task (T8). Other map layers, including
// the Compare-with layers in compare/, take their colors and line widths from here.
//
// Edge rules (one look per meaning, so the reader does not have to think):
//   - Neighborhood (tract) line: thin, mid blue, the same on every fill.
//   - County line: darker blue and about three times as wide as a tract line.
//   - Selected: a white glow with a near-black core line, wider than a county line.
//     Hover: the same look, lighter.
//     No border has a white glow, so hover and selected never look like a border type.
// All widths grow with zoom: thin at the overview, so small city tracts do not become a
// mesh, and wider when zoomed in, so lines do not become hair-thin.
import type { ExpressionSpecification, StyleSpecification } from 'maplibre-gl'

export const COLORS = {
  desert: '#F79122',
  nogap: '#DFE7EE',
  primary900: '#1E343F',
  primary700: '#385981',
  primary500: '#6B8FA8',
  // Line colors. Opaque, so a line looks the same on the orange and the grey fills.
  tractLine: '#6B8FA8',
  countyLine: '#385981',
  highlight: '#FFFFFF',
  // Insufficient data hatch. Same colors as the legend swatch (.swatch.insufficient).
  hatchLine: '#7B8794',
  hatchBase: '#FFFFFF',
}

// Width in px at each zoom stop, linear between stops.
function byZoom(...stops: [number, number][]): ExpressionSpecification {
  return ['interpolate', ['linear'], ['zoom'], ...stops.flat()] as ExpressionSpecification
}

// Line widths. Each value is a MapLibre zoom expression: use it directly as a 'line-width'.
// It is not a number, so do not do arithmetic on it.
export const WIDTH = {
  tract: byZoom([8, 0.25], [10, 0.5], [12, 0.9], [14, 1.4]),
  county: byZoom([8, 1.5], [10, 2], [12, 2.6], [14, 3.4]),
  // Dark core line of the selected tract.
  selected: byZoom([8, 2], [10, 2.5], [12, 3.2], [14, 4]),
  // White glow under the selected (or hovered) core line.
  highlight: byZoom([8, 5], [10, 6], [12, 7.5], [14, 9]),
}

// Insufficient data hatch: diagonal lines from top left to bottom right, like the legend
// swatch (repeating-linear-gradient at 45deg). 12 device px tile at pixelRatio 2.
export function hatchImage() {
  const size = 12
  const on = hex(COLORS.hatchLine)
  const off = hex(COLORS.hatchBase)
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const d = (x - y + size) % size
      const i = (y * size + x) * 4
      data.set(d < 4 ? on : off, i)
    }
  return { width: size, height: size, data }
}

function hex(c: string): [number, number, number, number] {
  const n = parseInt(c.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 255]
}

// Pantry coverage circle radius in px for a load value (residents per site in reach).
// The area grows with the load. The circles get smaller when you zoom out, so they do not
// pile up in the dense city tracts. At zoom 11 the radius is 0.55 * sqrt(load), minimum 3.
const LOAD_FACTOR: [number, number][] = [
  [8, 0.22],
  [11, 0.55],
  [14, 0.8],
]
const LOAD_MIN: Record<number, number> = { 8: 1.5, 11: 3, 14: 4 }

export function loadRadiusPx(load: number, zoom = 11): number {
  const z = Math.min(14, Math.max(8, zoom))
  const i = z <= 11 ? 0 : 1
  const [z0, f0] = LOAD_FACTOR[i]!
  const [z1, f1] = LOAD_FACTOR[i + 1]!
  const t = (z - z0) / (z1 - z0)
  const min = LOAD_MIN[z0]! + t * (LOAD_MIN[z1]! - LOAD_MIN[z0]!)
  return Math.max(min, (f0 + t * (f1 - f0)) * Math.sqrt(load))
}

export const COVERAGE_RADIUS = {
  load: [
    'interpolate',
    ['linear'],
    ['zoom'],
    ...LOAD_FACTOR.flatMap(([z, f]) => [
      z,
      ['max', LOAD_MIN[z]!, ['*', f, ['sqrt', ['get', 'load']]]],
    ]),
  ] as ExpressionSpecification,
  reach: byZoom([8, 2.5], [11, 5], [14, 7]),
}

export const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#F3F5F7' } }],
}

// Sequential palette for Compare-with layers (light to dark, Beacon primary blues).
export const COMPARE_SEQ = ['#DCE6EE', '#9FB8CC', '#6B8FA8', '#385981', '#1E343F'] as const

// Compare-with layers are inserted below this layer, so tract and county lines stay on top.
// The map task must keep a layer with this id.
export const COMPARE_BEFORE_LAYER = 'tract-line'
