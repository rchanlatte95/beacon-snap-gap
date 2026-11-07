// The sidebar. Owner: the plain-language task (T9). Moved from PlannerMock.tsx without behavior change.
import { useMemo, useState } from 'react'
import {
  CLASS_LABEL,
  CONF_LEVELS,
  CONF_RULES,
  GROUP_QUARTERS_PCT,
  NEAR_CUT_POINTS,
  SMALL_HOUSEHOLDS,
  confidence,
  fmt,
  n,
  pct,
} from './model'
import type { Cls, ConfLevel, ConfRule, Coverage, Records, SortKey, Tract } from './model'
import { COLORS } from './mapStyle'
import { COMPARE_LAYERS } from './compare'
import type { CompareContext, CompareLayer } from './compare/types'

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

  return (
    <div className="sidebar">
      <div>
        <h1 className="lede">Where is need high, and is a pantry in reach?</h1>
        <p className="secondary" style={{ margin: 0 }}>
          {r.counts.desert} of {r.tracts.length} Central Florida tracts meet the Classic Food Desert
          rule. {noSiteInside} of them have no Second Harvest site inside the tract. Click a tract to
          see why.
        </p>
      </div>

      <div className="notice">
        <strong>Mock-up.</strong> Stand-in data from the repo files ({r.generated}). This page is for
        layout and design review only. Do not use its values for decisions.
      </div>

      <section aria-labelledby="legend-h">
        <h2 id="legend-h">Map classes</h2>
        <ul className="legend">
          {(['desert', 'nogap', 'insufficient'] as Cls[]).map((c) => (
            <li key={c}>
              <span className={`swatch ${c}`} />
              <span>{CLASS_LABEL[c]}</span>
              <span className="count">{drawnCounts[c]}</span>
            </li>
          ))}
        </ul>
        <div className="not-drawn">
          Not drawn ({notDrawn.length}):{' '}
          {notDrawn.map((t) => (
            <button key={t.geoid} className="linklike" onClick={() => onSelect(t.geoid)}>
              {t.name}, {t.county} (<span className="mono">{t.geoid}</span>)
            </button>
          ))}{' '}
          is water and has no shape. It counts as Insufficient data, so all {r.tracts.length} tracts
          are accounted for.
        </div>
      </section>

      <section aria-labelledby="conf-h">
        <h2 id="conf-h">
          Confidence rule <span className="standin">not decided</span>
        </h2>
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
        <p className="rule">
          High-need tracts ({r.counts.desert}): {levelText(confCounts.high)}
          <br />
          All tracts ({r.tracts.length}): {levelText(confCounts.all)}
          <br />
          The {SMALL_HOUSEHOLDS}-household, {GROUP_QUARTERS_PCT}% and {NEAR_CUT_POINTS}-point
          thresholds are stand-ins.
        </p>
      </section>

      <section aria-labelledby="compare-h">
        <h2 id="compare-h">Compare with</h2>
        <select
          className="sort"
          value={props.compareId ?? ''}
          onChange={(e) => props.setCompareId(e.target.value || null)}
          aria-label="Compare with"
          disabled={COMPARE_LAYERS.length === 0}
        >
          <option value="">Nothing</option>
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
        <h2 id="layers-h">Layers</h2>
        <label className="layer">
          <input
            type="checkbox"
            checked={props.coverageOn}
            onChange={(e) => props.setCoverageOn(e.target.checked)}
          />
          <span>
            Pantry coverage on high-need tracts <span className="standin">stand-in</span>
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
                Load (Z-2e)
              </label>
              <label>
                <input
                  type="radio"
                  name="cov"
                  checked={props.coverage === 'reach'}
                  onChange={() => props.setCoverage('reach')}
                />{' '}
                Reach
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
                <span style={{ alignSelf: 'center' }}>residents per site in reach</span>
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
          <span>Second Harvest sites ({props.siteCount}, 7 counties)</span>
        </label>
      </section>

      <section aria-labelledby="list-h">
        <h2 id="list-h">Classic Food Desert tracts ({flagged.length})</h2>
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
            aria-label="Sort tracts"
          >
            <option value="poverty">Poverty %</option>
            <option value="snap">SNAP %</option>
            <option value="load">Load</option>
          </select>
        </div>
        <ul className="tract-list">
          {flagged.map((t) => (
            <li key={t.geoid}>
              <button aria-current={selected === t.geoid} onClick={() => onSelect(t.geoid)}>
                <span className="t-name">
                  {t.name}
                  {t.sitesInTract === 0 && <span className="tag warn">no site inside</span>}
                </span>
                <span className="t-num">
                  {sort === 'load' ? n(t.standinLoad) : pct(sort === 'snap' ? t.pctSnap : t.pctPoverty)}
                </span>
                <span className="t-meta">
                  {t.county} · SNAP {pct(t.pctSnap)} · {n(t.households)} households ·{' '}
                  {confidence(t, cut, confRule).level} confidence
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="ctx-h">
        <h2 id="ctx-h">Context</h2>
        <Sparkline series={r.snapTrend} />
        <p className="secondary">
          Food insecurity, 2024 (Feeding America, DS-X9b):{' '}
          {r.mealGap.map((m) => `${m.county[0]!.toUpperCase()}${m.county.slice(1)} ${m.rate}`).join(' · ')}
        </p>
      </section>

      <div className="deferred" aria-label="Deferred scenario slider">
        <strong>Scenario slider: deferred (Z-3, SLICE-2).</strong> Shown here only to discuss where
        it would go. When it returns, every result carries the label "assumption-based estimate".
        <input type="range" disabled aria-label="Scenario slider (deferred)" />
      </div>
    </div>
  )
}
