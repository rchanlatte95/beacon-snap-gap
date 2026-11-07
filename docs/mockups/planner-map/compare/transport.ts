// Compare-with layer: families without a car (task T3).
// Question: where do many families have no car, in high-need neighborhoods with no pantry site?
// Data: data/transport.standin.json, made by compare/make-transport.mjs from DS-X7b.
// The no-vehicle share is a proxy for transport need, not a validated measure (finding F-1).
import type { ExpressionSpecification, Map as MapLibre } from 'maplibre-gl'
import type { Tract } from '../model'
import { COLORS, COMPARE_BEFORE_LAYER, WIDTH } from '../mapStyle'
import type { CompareContext, CompareLayer } from './types'
import {
  CLASS_COLORS,
  FOCUS_STATE,
  SOURCES,
  STRIPE_ON_DARK,
  STRIPE_ON_LIGHT,
  asData,
  capital,
  classOf,
  isCandidate,
  oneIn,
} from './transportData'
import { TransportPanel } from './transportPanel'

// Two stripe images: dark stripes for the lightest class, white stripes for the darker
// classes, so the stripes show on every class color.
const STRIPES_DARK = 'transport-stripes-dark'
const STRIPES_LIGHT = 'transport-stripes-light'

function rgb(hex: string): [number, number, number] {
  const v = parseInt(hex.replace('#', ''), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}

// Diagonal stripes on a clear background, so the class color shows through.
// The direction is the opposite of the base map's "Insufficient data" hatch.
function stripesImage(color: [number, number, number]) {
  const size = 12
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const on = (x - y + size) % size < 3
      data.set(on ? [...color, 230] : [0, 0, 0, 0], (y * size + x) * 4)
    }
  return { width: size, height: size, data }
}

function addToMap(map: MapLibre, ctx: CompareContext) {
  const d = asData(ctx.extra)
  if (!map.hasImage(STRIPES_DARK))
    map.addImage(STRIPES_DARK, stripesImage(rgb(STRIPE_ON_LIGHT)), { pixelRatio: 2 })
  if (!map.hasImage(STRIPES_LIGHT))
    map.addImage(STRIPES_LIGHT, stripesImage(rgb(STRIPE_ON_DARK)), { pixelRatio: 2 })
  const byClass: string[][] = CLASS_COLORS.map(() => [])
  const withData: string[] = []
  const veryRough: string[] = []
  const veryRoughLight: string[] = []
  for (const [geoid, t] of Object.entries(d.tracts)) {
    if (t.pct === null) continue
    withData.push(geoid)
    byClass[classOf(t.pct)]!.push(geoid)
    if (t.band === 'veryRough') {
      veryRough.push(geoid)
      if (classOf(t.pct) === 0) veryRoughLight.push(geoid)
    }
  }
  const pairs: (string[] | string)[] = []
  byClass.forEach((ids, i) => {
    if (ids.length) pairs.push(ids, CLASS_COLORS[i]!)
  })
  const fillColor = (pairs.length
    ? ['match', ['get', 'geoid'], ...pairs, CLASS_COLORS[0]!]
    : CLASS_COLORS[0]!) as unknown as ExpressionSpecification
  const hidden = { visibility: 'none' } as const
  map.addLayer(
    {
      id: 'transport-fill',
      type: 'fill',
      source: 'tracts',
      layout: hidden,
      filter: ['in', ['get', 'geoid'], ['literal', withData]],
      paint: {
        'fill-color': fillColor,
        'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.8, 1],
      },
    },
    COMPARE_BEFORE_LAYER,
  )
  map.addLayer(
    {
      id: 'transport-stripes',
      type: 'fill',
      source: 'tracts',
      layout: hidden,
      filter: ['in', ['get', 'geoid'], ['literal', veryRough]],
      paint: {
        // No antialias outline: on a pattern fill it draws the stripe color along the edge.
        'fill-antialias': false,
        'fill-pattern': [
          'case',
          ['in', ['get', 'geoid'], ['literal', veryRoughLight]],
          STRIPES_DARK,
          STRIPES_LIGHT,
        ],
      },
    },
    COMPARE_BEFORE_LAYER,
  )
  map.addLayer(
    {
      id: 'transport-high-need',
      type: 'line',
      source: 'tracts',
      layout: { ...hidden, 'line-join': 'round' },
      filter: ['==', ['get', 'cls'], 'desert'],
      paint: { 'line-color': COLORS.desert, 'line-width': WIDTH.selected },
    },
    COMPARE_BEFORE_LAYER,
  )
  // The tract picked in the panel list: a dark line on a white casing, visible on every class.
  const focusWidth = (w: number): ExpressionSpecification => [
    'case',
    ['boolean', ['feature-state', FOCUS_STATE], false],
    w,
    0,
  ]
  map.addLayer(
    {
      id: 'transport-focus-casing',
      type: 'line',
      source: 'tracts',
      layout: hidden,
      paint: { 'line-color': STRIPE_ON_DARK, 'line-width': focusWidth(WIDTH.selected * 2) },
    },
    COMPARE_BEFORE_LAYER,
  )
  map.addLayer(
    {
      id: 'transport-focus',
      type: 'line',
      source: 'tracts',
      layout: hidden,
      paint: { 'line-color': COLORS.primary900, 'line-width': focusWidth(WIDTH.selected) },
    },
    COMPARE_BEFORE_LAYER,
  )
}

function cardLines(t: Tract, ctx: CompareContext): string[] {
  const v = asData(ctx.extra).tracts[t.geoid]
  if (!v || v.pct === null)
    return ['We have no car numbers for this neighborhood, because no families were counted here.']
  const share = oneIn(v.pct)
  const lines = [
    share
      ? `${capital(share)} families here has no car.`
      : 'The survey found no families without a car here.',
  ]
  if (v.band === 'closer') lines.push('This number is a fair estimate, but it is not exact.')
  else if (v.band === 'rough') lines.push('This number is a rough estimate.')
  else if (share)
    lines.push('This number is a very rough guess. The real number could be much higher or lower.')
  else lines.push('This number is a very rough guess.')
  if (isCandidate(t, v))
    lines.push(
      'High need, many families without a car and no Second Harvest site inside: this may be a good place for a mobile pantry or deliveries.',
    )
  return lines
}

const layer: CompareLayer = {
  id: 'transport',
  menuLabel: 'Families without a car',
  question: 'Where do many families have no car?',
  dataFile: 'transport.standin.json',
  mapLayerIds: [
    'transport-fill',
    'transport-stripes',
    'transport-high-need',
    'transport-focus-casing',
    'transport-focus',
  ],
  addToMap,
  Panel: TransportPanel,
  cardLines,
  sources: SOURCES,
}
export default layer
