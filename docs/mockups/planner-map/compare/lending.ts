// Compare-with layer: where SBA small business loans went, next to food need. Owner: task T5.
//
// The user feedback asked to contrast need against where loans go, and claimed that people
// who need food also need SBA lending. Task T0 tested the claim and it is NOT supported
// (finding F-3, docs/analysis/need-vs-sba-lending.md). This layer shows where loans went and
// says what the comparison does and does not show. It must not claim that food need and SBA
// lending line up, and must not claim that high-need areas get less lending.
//
// Data: data/lending.standin.json, written by compare/make-lending.mjs (DS-X5, DS-X24).
import type { ExpressionSpecification } from 'maplibre-gl'
import { COLORS, COMPARE_BEFORE_LAYER, WIDTH } from '../mapStyle'
import type { Tract } from '../model'
import type { CompareContext, CompareLayer } from './types'
import {
  BANDS,
  DOTS,
  LAYER_FILL,
  LAYER_NEED,
  LAYER_ZERO,
  SOURCES,
  bandOf,
  derive,
  dotsImage,
  inTen,
  loansWord,
  rateWords,
} from './lendingData'
import type { Row } from './lendingData'
import { Panel } from './lendingPanel'

// ---------------- Tract card ----------------

function cardLines(t: Tract, ctx: CompareContext): string[] {
  const d = derive(ctx)
  const l = d?.file.tracts[t.geoid]
  if (!d || !l) return []
  if (l.group === null || l.per1k === null)
    return [
      'This neighborhood has no food need class, so it is not part of this loan comparison.',
      l.loans > 0
        ? `We placed ${loansWord(l.loans)} for businesses here since 2010.`
        : 'We found no SBA loans for businesses here since 2010.',
    ]
  const v = l.per1k
  const share = (pred: (r: Row) => boolean) => d.set.filter(pred).length / d.set.length
  const lines: string[] = []
  if (l.loans === 0) {
    lines.push('We found no SBA loans for businesses here since 2010.')
    lines.push('Some loans could not be placed on the map, so the real number may be higher.')
  } else {
    lines.push(
      `Businesses here got ${rateWords(v)} for every 1,000 residents since 2010 (${loansWord(l.loans)} in all).`,
    )
    if (v < d.cut)
      lines.push(
        `That is fewer than most neighborhoods: ${inTen(share((r) => r.l.per1k > v))} got more.`,
      )
    else {
      const fewer = share((r) => r.l.per1k < v)
      lines.push(
        fewer >= 0.6
          ? `That is more than most neighborhoods: ${inTen(fewer)} got fewer.`
          : 'That is close to the middle: about half of neighborhoods got fewer.',
      )
    }
  }
  lines.push(
    l.group === 'high-need-low-lending'
      ? 'Food need is high here and loans are fewer than most. That may be worth a closer look, but it is about as common in other neighborhoods.'
      : 'Loans are counted where the business owner gets mail, so they are not all loans to people who live here.',
  )
  return lines
}

// ---------------- Layer ----------------

const layer: CompareLayer = {
  id: 'lending',
  menuLabel: 'Where small business loans went',
  question: 'Where did SBA small business loans go, and how does that compare with food need?',
  dataFile: 'lending.standin.json',
  mapLayerIds: [LAYER_FILL, LAYER_ZERO, LAYER_NEED],
  addToMap(map, ctx) {
    const d = derive(ctx)
    if (!d) return
    const entries = Object.entries(d.file.tracts).filter(
      ([, l]) => l.group !== null && l.per1k !== null,
    )
    const zeroIds = entries.filter(([, l]) => l.per1k === 0).map(([g]) => g)
    const color: unknown[] = ['match', ['get', 'geoid']]
    for (const b of BANDS) {
      const ids = entries.filter(([, l]) => bandOf(l.per1k!) === b).map(([g]) => g)
      if (ids.length) color.push(ids, b.color)
    }
    color.push('rgba(0,0,0,0)')
    const filled = entries.filter(([, l]) => l.per1k! > 0).map(([g]) => g)
    if (!map.hasImage(DOTS)) map.addImage(DOTS, dotsImage(), { pixelRatio: 2 })
    const hoverOpacity: ExpressionSpecification = [
      'case',
      ['boolean', ['feature-state', 'hover'], false],
      0.8,
      1,
    ]
    map.addLayer(
      {
        id: LAYER_FILL,
        type: 'fill',
        source: 'tracts',
        layout: { visibility: 'none' },
        filter: ['in', ['get', 'geoid'], ['literal', filled]],
        paint: {
          'fill-color': color as ExpressionSpecification,
          'fill-opacity': hoverOpacity,
        },
      },
      COMPARE_BEFORE_LAYER,
    )
    map.addLayer(
      {
        id: LAYER_ZERO,
        type: 'fill',
        source: 'tracts',
        layout: { visibility: 'none' },
        filter: ['in', ['get', 'geoid'], ['literal', zeroIds]],
        paint: { 'fill-pattern': DOTS, 'fill-opacity': hoverOpacity },
      },
      COMPARE_BEFORE_LAYER,
    )
    map.addLayer(
      {
        id: LAYER_NEED,
        type: 'line',
        source: 'tracts',
        layout: { visibility: 'none', 'line-join': 'round' },
        filter: ['==', ['get', 'cls'], 'desert'],
        paint: {
          'line-color': COLORS.desert,
          // Same high-need outline width as the other Compare layers.
          'line-width': WIDTH.selected,
        },
      },
      COMPARE_BEFORE_LAYER,
    )
  },
  Panel,
  cardLines,
  sources: SOURCES,
}
export default layer
