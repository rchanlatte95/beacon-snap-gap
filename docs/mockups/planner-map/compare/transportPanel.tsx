// Sidebar panel for the "Families without a car" layer (task T3).
import { useMemo, useRef } from 'react'
import { featureId } from '../model'
import type { Tract } from '../model'
import { COLORS } from '../mapStyle'
import type { CompareContext } from './types'
import {
  BAND_WORDS,
  BREAKS,
  CLASS_COLORS,
  FOCUS_STATE,
  MANY,
  SOURCES,
  STRIPE_ON_DARK,
  STRIPE_ON_LIGHT,
  asData,
  capital,
  oneIn,
  summarize,
} from './transportData'
import './transport.css'

// Legend swatch: the same stripes as the map, drawn with CSS.
const stripes = (fill: string, stripe: string) => ({
  background: `repeating-linear-gradient(45deg, ${stripe} 0 1.5px, transparent 1.5px 6px), ${fill}`,
})

export function TransportPanel({ ctx }: { ctx: CompareContext }) {
  const d = asData(ctx.extra)
  const s = useMemo(() => summarize(ctx.records, d), [ctx.records, d])
  const focused = useRef<string | null>(null)
  const cvCloser = Math.round(d.rule.cvCloser * 100)
  const cvVeryRough = Math.round(d.rule.cvVeryRough * 100)
  const top = BREAKS[BREAKS.length - 1]
  const tickLabels = ['0', ...BREAKS.slice(0, -1).map(String), `${top}+`]
  const cols = { gridTemplateColumns: `repeat(${CLASS_COLORS.length}, 1fr)` }
  const manyOneIn = Math.round(100 / MANY)

  const showOnMap = (t: Tract) => {
    const map = ctx.getMap()
    if (!map || !t.centroid) return
    if (focused.current)
      map.setFeatureState(
        { source: 'tracts', id: featureId(focused.current) },
        { [FOCUS_STATE]: false },
      )
    focused.current = t.geoid
    map.setFeatureState({ source: 'tracts', id: featureId(t.geoid) }, { [FOCUS_STATE]: true })
    map.easeTo({ center: t.centroid, zoom: Math.max(map.getZoom(), 12), duration: 700 })
  }

  return (
    <div className="tr-panel">
      <p className="tr-headline">
        <strong>{s.candidates.length}</strong> high-need neighborhoods have many families without a
        car (1 in {manyOneIn} or more) and no Second Harvest site inside. They may be good places
        for a mobile pantry or food deliveries.
      </p>

      <ul className="legend tr-legend" aria-label="Map key for families without a car">
        <li className="tr-ramp-row">
          <span>Families with no car, out of every 100</span>
          <span className="tr-ramp" style={cols} aria-hidden="true">
            {CLASS_COLORS.map((c) => (
              <span key={c} style={{ background: c }} />
            ))}
          </span>
          <span className="tr-ticks" style={cols} aria-hidden="true">
            {tickLabels.map((l) => (
              <span key={l}>{l}</span>
            ))}
          </span>
        </li>
        <li>
          <span className="swatch tr-swatch-stripes" aria-hidden="true">
            <span style={stripes(CLASS_COLORS[0]!, STRIPE_ON_LIGHT)} />
            <span style={stripes(CLASS_COLORS[2]!, STRIPE_ON_DARK)} />
          </span>
          <span>Striped: the number is a very rough guess</span>
          <span className="count">{s.veryRoughDrawn}</span>
        </li>
        <li>
          <span
            className="swatch"
            style={{ background: CLASS_COLORS[1], border: `2px solid ${COLORS.desert}` }}
          />
          <span>Orange outline: high-need neighborhood</span>
          <span className="count">{s.highNeed.length}</span>
        </li>
      </ul>

      <p className="secondary tr-caveat">
        Not having a car is only a clue that getting food is hard. Car counts for small areas are
        rough, so check with local partners before you act. Other food sources may exist.
      </p>

      {s.candidates.length > 0 && (
        <div>
          <h3 className="tr-list-h">High need, many without a car, no site inside</h3>
          <ul className="tr-list">
            {s.candidates.map(({ t, v }) => (
              <li key={t.geoid}>
                <button type="button" onClick={() => showOnMap(t)}>
                  <span className="tr-name">{t.name}</span>
                  <span className="tr-num">{capital(oneIn(v.pct ?? 0) ?? '')}</span>
                  <span className="tr-meta">
                    {t.county} County · {v.band ? BAND_WORDS[v.band] : 'no data'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="secondary tr-hint">Pick a name to find it on the map, then click it.</p>
        </div>
      )}

      <details className="how-we-know">
        <summary>How we know this</summary>
        <div className="tr-detail">
          <p>
            <strong>Source.</strong> ACS 2024 5-year estimates, table B08201 (households by vehicles
            available), for each neighborhood (census tract) (DS-X7b). The values came through the
            Census Reporter API, not the Census Bureau bulk files, so check them before you quote
            them. File: <span className="mono">{d.file}</span>.
          </p>
          <p>
            <strong>Method.</strong> Share = households with no vehicle ÷ all households.{' '}
            <span className="mono">compare/make-transport.mjs</span> computes the share, its margin
            of error and a reliability band for each tract, and writes{' '}
            <span className="mono">data/transport.standin.json</span>.
          </p>
          <p>
            <strong>Breaks.</strong> Under {BREAKS[0]}%,{' '}
            {BREAKS.slice(0, -1)
              .map((b, i) => `${b}% to under ${BREAKS[i + 1]}%`)
              .join(', ')}
            , and {top}% or more. Drawn tracts per class, light to dark: {s.classCounts.join(' / ')}
            .
          </p>
          <p>
            <strong>"Many", "high need" and "no site inside".</strong> "Many" means a no-vehicle
            share of {MANY}% or more (1 in {manyOneIn} households), the two darkest classes. "High
            need" means the Classic Food Desert class. "No site inside" means no Second Harvest site
            inside the tract boundary (DS-X12). Of {s.highNeed.length} high-need tracts,{' '}
            {s.highNeedNoSite} have no site inside, and {s.candidates.length} of those have a share
            of {MANY}% or more. Only {s.firmCandidates.length} of the {s.candidates.length} stay at{' '}
            {MANY}% or more at the low end of the 90% margin of error.
          </p>
          <p>
            <strong>Margin of error rule.</strong> The margin of error (MOE, 90%) of the share uses
            the ACS proportion formula: √(MOE<sub>no vehicle</sub>² − share² × MOE<sub>all</sub>²) ÷
            all households (the + form when the value under the root is negative). Coefficient of
            variation (CV) = (MOE ÷ {d.rule.z}) ÷ share. CV under {cvCloser}%: closer estimate (
            {d.bands.closer} tracts). CV {cvCloser}% to under {cvVeryRough}%: rough estimate (
            {d.bands.rough}). CV {cvVeryRough}% or more, or a zero estimate: very rough guess,
            striped on the map ({d.bands.veryRough}). At CV {cvVeryRough}% (1 ÷ {d.rule.z}) the MOE
            equals the estimate, so the 90% range reaches zero.
          </p>
          <p>
            <strong>Blank.</strong> {s.blank.length} tracts have no households, so they have no
            share:{' '}
            {s.blank.map((g, i) => (
              <span key={g}>
                {i > 0 && ', '}
                <span className="mono">{g}</span>
              </span>
            ))}
            . They keep the base map fill.
          </p>
          <p>
            <strong>Not a proven measure (F-1).</strong> CDC PLACES "lack of reliable
            transportation" (LACKTRPT) is blank for all of Florida, so the no-vehicle share is a
            stand-in (a proxy). It is not a validated measure of transport need. It does not count
            bus service, rides from family or friends, or travel time.
          </p>
          <ul className="tr-sources">
            {SOURCES.map((src) => (
              <li key={src.id}>
                <span className="mono">{src.id}</span>: {src.label}
              </li>
            ))}
          </ul>
        </div>
      </details>
    </div>
  )
}
