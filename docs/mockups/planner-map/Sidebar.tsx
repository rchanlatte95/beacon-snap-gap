// The sidebar. Owner: the plain-language task (T9).
// Progressive disclosure: glance (headline, summary, legend), explore (compare, layers, list),
// detail (everything technical, inside <details className="how-we-know">). Wording is in copy.ts.
import { useMemo, useState } from 'react'
import {
  CLASS_LABEL,
  CONF_LEVELS,
  CONF_RULES,
  GROUP_QUARTERS_PCT,
  NEAR_CUT_POINTS,
  NO_MOE,
  SMALL_HOUSEHOLDS,
  confidence,
  fmt,
  n,
} from './model'
import type { Cls, ConfLevel, ConfRule, Coverage, Records, SortKey, Tract } from './model'
import { COLORS } from './mapStyle'
import { COMPARE_LAYERS } from './compare'
import type { CompareContext, CompareLayer } from './compare/types'
import {
  BASE_SOURCES,
  CIRCLE_PLAIN,
  CLASS_PLAIN,
  GLOSSARY,
  UI,
  glanceSummary,
  tractNumber,
  wholePct,
} from './copy'

// ---------------- Sidebar ----------------

function Sparkline({ series }: { series: Records['snapTrend'] }) {
  const pts = series.filter((p) => p.participants !== null) as { month: string; participants: number }[]
  if (pts.length < 2) return null
  const vals = pts.map((p) => p.participants)
  const [lo, hi] = [Math.min(...vals), Math.max(...vals)]
  const W = 320
  const Hh = 56
  const xy = pts.map((p, i) => [
    (i / (pts.length - 1)) * (W - 8) + 4,
    Hh - 6 - ((p.participants - lo) / (hi - lo || 1)) * (Hh - 14),
  ])
  const first = pts[0]!
  const last = pts[pts.length - 1]!
  return (
    <figure style={{ margin: 0 }}>
      <svg className="spark" viewBox={`0 0 ${W} ${Hh}`} role="img" aria-label="Florida SNAP participants by month">
        <polyline
          fill="none"
          stroke={COLORS.primary700}
          strokeWidth="2"
          points={xy.map((p) => p.join(',')).join(' ')}
        />
        <circle cx={xy.at(-1)![0]} cy={xy.at(-1)![1]} r="3.5" fill={COLORS.desert} />
      </svg>
      <figcaption className="secondary">
        Florida SNAP participants: {fmt.format(first.participants)} ({first.month}) to{' '}
        {fmt.format(last.participants)} ({last.month}). Statewide only (CBPP, DS-X3b).
      </figcaption>
    </figure>
  )
}

// Every source once: the base sources, then each Compare-with layer's sources.
function sourceList() {
  const seen = new Set<string>()
  const out: { id: string; label: string; note?: string; layer?: string }[] = []
  const add = (s: (typeof out)[number]) => {
    if (seen.has(s.id)) return
    seen.add(s.id)
    out.push(s)
  }
  for (const s of BASE_SOURCES) add(s)
  for (const l of COMPARE_LAYERS) for (const s of l.sources) add({ ...s, layer: l.menuLabel })
  return out
}
// COMPARE_LAYERS is fixed when the module loads, so the list is built once.
const SOURCES = sourceList()

export function Sidebar(props: {
  r: Records
  selected: string | null
  onSelect: (g: string) => void
  coverageOn: boolean
  setCoverageOn: (v: boolean) => void
  coverage: Coverage
  setCoverage: (v: Coverage) => void
  sitesOn: boolean
  setSitesOn: (v: boolean) => void
  siteCount: number
  confRule: ConfRule
  setConfRule: (v: ConfRule) => void
  compareId: string | null
  setCompareId: (v: string | null) => void
  compareCtx: (layer: CompareLayer) => CompareContext
}) {
  const { r, selected, onSelect, confRule } = props
  const cut = r.povertyCut.value
  const confCounts = useMemo(() => {
    const zero = () => Object.fromEntries(CONF_LEVELS.map((l) => [l, 0])) as Record<ConfLevel, number>
    const all = zero()
    const high = zero()
    for (const t of r.tracts) {
      const { level } = confidence(t, cut, confRule)
      all[level]++
      if (t.cls === 'desert') high[level]++
    }
    return { all, high }
  }, [r.tracts, cut, confRule])
  const levelText = (c: Record<ConfLevel, number>) =>
    CONF_LEVELS.filter((l) => c[l] > 0)
      .map((l) => `${l} ${c[l]}`)
      .join(' · ')
  const [county, setCounty] = useState<string>('All')
  const [sort, setSort] = useState<SortKey>('poverty')
  const drawnCounts = useMemo(() => {
    const c: Record<Cls, number> = { desert: 0, nogap: 0, insufficient: 0 }
    for (const t of r.tracts) if (t.drawn) c[t.cls]++
    return c
  }, [r.tracts])
  const notDrawn = r.tracts.filter((t) => !t.drawn)
  const insufficient = r.tracts.filter((t) => t.cls === 'insufficient')
  const flagged = useMemo(() => {
    const key = (t: Tract) =>
      sort === 'poverty' ? (t.pctPoverty ?? 0) : sort === 'snap' ? (t.pctSnap ?? 0) : (t.standinLoad ?? 0)
    return r.tracts
      .filter((t) => t.cls === 'desert' && (county === 'All' || t.county === county))
      .sort((a, b) => key(b) - key(a))
  }, [r.tracts, county, sort])
  const desert = r.tracts.filter((t) => t.cls === 'desert')
  const noSiteInside = desert.filter((t) => t.sitesInTract === 0).length
  const activeCompare = COMPARE_LAYERS.find((l) => l.id === props.compareId)
  const circle = CIRCLE_PLAIN[props.coverage]

  return (
    <div className="sidebar">
      {/* ---------- Glance ---------- */}
      <div className="glance">
        <h1 className="lede">{UI.headline}</h1>
        {glanceSummary(r.counts.desert, r.tracts.length, noSiteInside).map((s) => (
          <p key={s} className="glance-text">
            {s}
          </p>
        ))}
        <p className="notice">{UI.notice}</p>
      </div>

      <section aria-labelledby="legend-h">
        <h2 id="legend-h">What the colors mean</h2>
        <ul className="legend">
          {(['desert', 'nogap', 'insufficient'] as Cls[]).map((c) => (
            <li key={c}>
              <span className={`swatch ${c}`} />
              <span>
                {CLASS_LABEL[c]}
                <span className="legend-plain">{CLASS_PLAIN[c]}</span>
              </span>
              <span className="count">{drawnCounts[c]}</span>
            </li>
          ))}
          {props.coverageOn && (
            <li>
              <span className={`swatch circle ${props.coverage}`} />
              <span>
                {circle.name}
                <span className="legend-plain">{circle.plain}</span>
              </span>
              <span className="count" />
            </li>
          )}
        </ul>
        <p className="hint">{UI.clickHint}</p>
      </section>

      {/* ---------- Explore ---------- */}
      <section aria-labelledby="compare-h">
        <h2 id="compare-h">{UI.compareWith}</h2>
        <select
          className="sort"
          value={props.compareId ?? ''}
          onChange={(e) => props.setCompareId(e.target.value || null)}
          aria-label="Compare with"
          disabled={COMPARE_LAYERS.length === 0}
        >
          <option value="">{UI.compareNothing}</option>
          {COMPARE_LAYERS.map((l) => (
            <option key={l.id} value={l.id}>
              {l.menuLabel}
            </option>
          ))}
        </select>
        {activeCompare && (
          <>
            <p className="secondary">{activeCompare.question}</p>
            <activeCompare.Panel ctx={props.compareCtx(activeCompare)} />
          </>
        )}
      </section>

      <section aria-labelledby="layers-h">
        <h2 id="layers-h">{UI.layersHeading}</h2>
        <label className="layer">
          <input
            type="checkbox"
            checked={props.coverageOn}
            onChange={(e) => props.setCoverageOn(e.target.checked)}
          />
          <span>
            {UI.coverageToggle} <span className="standin">{UI.standin}</span>
          </span>
        </label>
        {props.coverageOn && (
          <>
            <div className="radio-row" role="radiogroup" aria-label="Coverage measure">
              <label>
                <input
                  type="radio"
                  name="cov"
                  checked={props.coverage === 'load'}
                  onChange={() => props.setCoverage('load')}
                />{' '}
                {UI.coverageLoad}
              </label>
              <label>
                <input
                  type="radio"
                  name="cov"
                  checked={props.coverage === 'reach'}
                  onChange={() => props.setCoverage('reach')}
                />{' '}
                {UI.coverageReach}
              </label>
            </div>
            {props.coverage === 'load' ? (
              <div className="circle-key" aria-label="Circle size key">
                {[50, 250, 1000].map((v) => {
                  const d = 2 * Math.max(3, 0.55 * Math.sqrt(v))
                  return (
                    <span key={v}>
                      <i style={{ width: d, height: d }} />
                      {fmt.format(v)}
                    </span>
                  )
                })}
                <span style={{ alignSelf: 'center' }}>people per site</span>
              </div>
            ) : (
              <div className="circle-key">
                {[
                  [COLORS.primary500, 'under 50%'],
                  [COLORS.primary700, '50 to 89%'],
                  [COLORS.primary900, '90% or more'],
                ].map(([c, l]) => (
                  <span key={l}>
                    <i style={{ width: 12, height: 12, background: c }} />
                    {l}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
        <label className="layer">
          <input
            type="checkbox"
            checked={props.sitesOn}
            onChange={(e) => props.setSitesOn(e.target.checked)}
          />
          <span>{UI.sitesToggle(props.siteCount)}</span>
        </label>
      </section>

      <section aria-labelledby="list-h">
        <h2 id="list-h">{UI.listHeading(flagged.length)}</h2>
        <div className="list-tools">
          {['All', 'Orange', 'Seminole', 'Lake', 'Osceola'].map((c) => (
            <button key={c} className="chip" aria-pressed={county === c} onClick={() => setCounty(c)}>
              {c}
            </button>
          ))}
          <select
            className="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            aria-label={UI.sortLabel}
          >
            <option value="poverty">{UI.sortPoverty}</option>
            <option value="snap">{UI.sortSnap}</option>
            <option value="load">{UI.sortLoad}</option>
          </select>
        </div>
        <ul className="tract-list">
          {flagged.map((t) => (
            <li key={t.geoid}>
              <button aria-current={selected === t.geoid} onClick={() => onSelect(t.geoid)}>
                <span className="t-name">
                  {tractNumber(t)} · {t.county}
                  {t.sitesInTract === 0 && (
                    <>
                      {' '}
                      <span className="tag warn">{UI.noSiteInside}</span>
                    </>
                  )}
                </span>
                <span className="t-num">
                  {sort === 'load'
                    ? `${n(t.standinLoad)} per site`
                    : sort === 'snap'
                      ? `${wholePct(t.pctSnap)} SNAP`
                      : `${wholePct(t.pctPoverty)} in poverty`}
                </span>
                <span className="t-meta">
                  How sure we are: {confidence(t, cut, confRule).level}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* ---------- Detail ---------- */}
      <details className="how-we-know">
        <summary>{UI.howWeKnow}</summary>

        <section aria-labelledby="hw-class-h">
          <h3 id="hw-class-h">How we color the map</h3>
          <p>
            Each neighborhood is a census tract (2020 tracts, ACS 2024 5-year data). There are{' '}
            {r.tracts.length} in Orange, Seminole, Lake and Osceola counties.
          </p>
          <p>
            <strong>{CLASS_LABEL.desert}</strong> needs both tests: (1) a poverty rate of{' '}
            {cut.toFixed(3)}% or more, which is the top quartile (75th percentile) of the{' '}
            {r.povertyCut.tracts} tracts with a poverty value ({r.povertyCut.method}, not rounded); and
            (2) the USDA driving-distance LILA flag (low income and low access at 1/2 mile urban, 10
            miles rural; <span className="mono">DD_SRAM_LILATracts_halfAnd10</span>).{' '}
            <strong>{CLASS_LABEL.nogap}</strong> means the tract does not pass both tests.{' '}
            <strong>{CLASS_LABEL.insufficient}</strong> means the poverty rate or the LILA flag is blank.
            A blank SNAP share is listed as missing on the card, but it does not change the class.
            Sources: DS-H2, DS-H6.
          </p>
          <p>
            Tracts with insufficient data ({insufficient.length}):{' '}
            {insufficient.map((t, i) => (
              <span key={t.geoid}>
                {i > 0 && '; '}
                <button className="linklike" onClick={() => onSelect(t.geoid)}>
                  {t.name}, {t.county} (<span className="mono">{t.geoid}</span>)
                </button>
                {!t.drawn && ' (water, no shape, not drawn)'}
              </span>
            ))}
            . The legend counts drawn tracts only. With the {notDrawn.length} tract that is not drawn,
            all {r.tracts.length} tracts are accounted for.
          </p>
        </section>

        <section aria-labelledby="conf-h">
          <h3 id="conf-h">
            How sure are we (confidence rule) <span className="standin">not decided</span>
          </h3>
          <p>
            The card shows High, Medium, Low or Not rated. A human must pick one of these candidate
            rules before any rule goes in a contract. Compare them here:
          </p>
          <div className="rule-pick" role="radiogroup" aria-label="Confidence rule">
            {CONF_RULES.map((c) => (
              <label key={c.id}>
                <input
                  type="radio"
                  name="conf"
                  checked={confRule === c.id}
                  onChange={() => props.setConfRule(c.id)}
                />
                <span>
                  <strong>{c.name}</strong>
                  <span className="secondary"> {c.summary}</span>
                </span>
              </label>
            ))}
          </div>
          <p>
            High-need tracts ({r.counts.desert}): {levelText(confCounts.high)}
            <br />
            All tracts ({r.tracts.length}): {levelText(confCounts.all)}
            <br />
            The {SMALL_HOUSEHOLDS}-household, {GROUP_QUARTERS_PCT}% group quarters and{' '}
            {NEAR_CUT_POINTS}-point thresholds are stand-ins. {NO_MOE}
          </p>
        </section>

        <section aria-labelledby="hw-cov-h">
          <h3 id="hw-cov-h">
            Food site coverage <span className="standin">stand-in</span>
          </h3>
          <p>
            Reach: the share of a tract's populated 2020 blocks' people within{' '}
            {r.standinReachMiles} miles straight-line of a Second Harvest site. Load: tract 2020
            population divided by the sites within that reach (residents per site, Z-2e). The decided
            reach rule is a 30-minute drive (Z-2, Z-2b, Z-2d); it needs routing data that is not in the
            repo. The circles show on the {r.counts.desert} high-need tracts only. Sites are Second
            Harvest partner sites only ({props.siteCount} sites in 7 counties). Other pantries and stores
            are not in the list, and hours change. Sources: DS-X12, DS-X27, DS-X24.
          </p>
        </section>

        <section aria-labelledby="ctx-h">
          <h3 id="ctx-h">Context (not used to color the map)</h3>
          <Sparkline series={r.snapTrend} />
          <p className="secondary">
            Food insecurity, 2024 (Feeding America, DS-X9b):{' '}
            {r.mealGap.map((m) => `${m.county[0]!.toUpperCase()}${m.county.slice(1)} ${m.rate}`).join(' · ')}
          </p>
        </section>

        <div className="deferred" aria-label="Deferred scenario slider">
          <strong>Scenario slider: deferred (Z-3, SLICE-2).</strong> Shown here only to discuss where it
          would go. When it returns, every result carries the label "assumption-based estimate".
          <input type="range" disabled aria-label="Scenario slider (deferred)" />
        </div>

        <section aria-labelledby="gloss-h">
          <h3 id="gloss-h">Words we use</h3>
          <dl className="glossary">
            {GLOSSARY.map((g) => (
              <div key={g.term}>
                <dt>{g.term}</dt>
                <dd>{g.plain}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section aria-labelledby="src-h">
          <h3 id="src-h">Sources</h3>
          <p>
            Stand-in data made from the repo files on {r.generated}. IDs are from{' '}
            <span className="mono">docs/data-sources.md</span>. Tract-level values only.
          </p>
          <ul className="source-list">
            {SOURCES.map((s) => (
              <li key={s.id}>
                <span className="mono">{s.id}</span> {s.label}
                {s.layer && <span className="secondary"> (Compare with: {s.layer})</span>}.
                {s.note && <span className="secondary"> {s.note}</span>}
              </li>
            ))}
          </ul>
          <p className="secondary">
            Missing values per indicator, all tracts:{' '}
            {Object.entries(
              r.tracts.reduce<Record<string, number>>((acc, t) => {
                for (const m of t.missing) acc[m] = (acc[m] ?? 0) + 1
                return acc
              }, {}),
            )
              .map(([k, v]) => `${k} ${v}`)
              .join(' · ')}
            .
          </p>
        </section>
      </details>
    </div>
  )
}
