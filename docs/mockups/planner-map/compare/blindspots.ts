// Compare-with layer: where our data has gaps (README feature 3, the data blind-spot map).
// Owner: task T4.
//
// Two kinds of gap:
// - Region-wide gaps are true for every tract (for example the CDC PLACES social-needs
//   columns, finding F-1). They must not color the map, so the panel lists them in a box.
// - Tract gaps: an indicator that is blank for this tract only, or numbers that are less
//   stable because the tract is small or has many people in group quarters (the size tests
//   of confidence rule A in model.ts, with the same thresholds).
//
// REQ-5: every missing indicator is named. REQ-8: missing data is never "low need".
import type { ExpressionSpecification, Map as MapLibre } from 'maplibre-gl'
import type { CompareContext, CompareLayer } from './types'
import type { Tract } from '../model'
import { SMALL_HOUSEHOLDS, fmt } from '../model'
import { COLORS, COMPARE_BEFORE_LAYER, WIDTH, hatchImage } from '../mapStyle'
import type { GapLevel } from './blindspotsData'
import {
  BIG_LAYER,
  FILL,
  FILL_LAYER,
  HATCH_ID,
  NEED_LAYER,
  allPlaces,
  listText,
  plain,
  summarize,
} from './blindspotsData'
import { BlindspotsPanel } from './blindspotsPanel'

function addToMap(map: MapLibre, ctx: CompareContext) {
  if (!map.getSource('tracts')) return
  const { byGeoid } = summarize(ctx.records)
  const ids = (lvl: GapLevel) =>
    [...byGeoid].filter(([, g]) => g.level === lvl).map(([geoid]) => geoid)
  const inLevel = (lvl: GapLevel): ExpressionSpecification => [
    'in',
    ['get', 'geoid'],
    ['literal', ids(lvl)],
  ]
  if (!map.hasImage(HATCH_ID)) map.addImage(HATCH_ID, hatchImage(), { pixelRatio: 2 })
  map.addLayer(
    {
      id: FILL_LAYER,
      type: 'fill',
      source: 'tracts',
      filter: ['!', inLevel('big')],
      layout: { visibility: 'none' },
      paint: { 'fill-color': ['case', inLevel('some'), FILL.some, FILL.none] },
    },
    COMPARE_BEFORE_LAYER,
  )
  // The worst level uses the hatch, the same convention as Insufficient data on the main map.
  map.addLayer(
    {
      id: BIG_LAYER,
      type: 'fill',
      source: 'tracts',
      filter: inLevel('big'),
      layout: { visibility: 'none' },
      paint: { 'fill-pattern': HATCH_ID },
    },
    COMPARE_BEFORE_LAYER,
  )
  // High-need tracts keep an orange outline, so the planner can still find them. The wider
  // width token keeps the outline visible under the white tract lines.
  map.addLayer(
    {
      id: NEED_LAYER,
      type: 'line',
      source: 'tracts',
      filter: ['==', ['get', 'cls'], 'desert'],
      layout: { visibility: 'none' },
      paint: { 'line-color': COLORS.desert, 'line-width': WIDTH.selected },
    },
    COMPARE_BEFORE_LAYER,
  )
}

function cardLines(t: Tract, ctx: CompareContext): string[] {
  const { regionWide, byGeoid } = summarize(ctx.records)
  const g = byGeoid.get(t.geoid)
  if (!g) return []
  const lines: string[] = []
  if (g.level === 'big')
    lines.push(
      'Key facts are missing here, so we cannot say if need is high. This does not mean need is low.',
    )
  if (g.own.length > 0)
    lines.push(
      `We are missing ${g.own.length} ${g.own.length === 1 ? 'fact' : 'facts'} about this neighborhood: ${listText(g.own.map(plain))}.`,
    )
  if (g.fewHomes)
    lines.push(
      t.households === null || t.households === 0
        ? 'The survey counts no homes here, so there are no family numbers to read.'
        : `Fewer than ${fmt.format(SMALL_HOUSEHOLDS)} homes are here, so the numbers can change a lot from one survey to the next.`,
    )
  if (g.groupQuarters)
    lines.push(
      `About ${Math.round(t.groupQuartersPct ?? 0)} in 100 people here live in group housing, such as dorms or care homes. The survey's family numbers leave them out.`,
    )
  if (g.level === 'none')
    lines.push('We have every local fact we track for this neighborhood, and the numbers are steady.')
  if (regionWide.length > 0)
    lines.push(
      `Like every neighborhood in the region, we also do not know ${listText(regionWide.map(plain))}.${
        allPlaces(regionWide) ? ' A national health survey left these blank for all of Florida.' : ''
      }`,
    )
  return lines
}

const layer: CompareLayer = {
  id: 'blindspots',
  menuLabel: 'Where our data has gaps',
  question: 'Where is our picture less complete, or less sure?',
  mapLayerIds: [FILL_LAYER, BIG_LAYER, NEED_LAYER],
  addToMap,
  Panel: BlindspotsPanel,
  cardLines,
  sources: [
    { id: 'DS-H7', label: 'CDC PLACES 2025, tract file' },
    { id: 'F-1', label: 'CDC PLACES social-needs columns are blank for Florida' },
    { id: 'DS-H2', label: 'ACS 2024 5-year S1701, poverty' },
    { id: 'DS-H1', label: 'ACS 2024 5-year S2201, SNAP households' },
    { id: 'DS-H6', label: 'USDA 2025 SRAM, LILA flags and group quarters' },
    { id: 'DS-X7b', label: 'ACS 2024 5-year B08201, no-vehicle households' },
    { id: 'DS-X16b', label: 'FEMA National Risk Index' },
    { id: 'DS-X3b', label: 'CBPP SNAP Tracker, Florida only' },
    { id: 'DS-X12', label: 'Second Harvest food finder' },
    { id: 'DS-X24', label: 'Census 2020 blocks (stand-in reach)' },
    { id: 'DS-X5', label: 'SBA 7(a) and 504 FOIA loan data' },
  ],
}
export default layer
