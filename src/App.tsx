import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { OpportunityMap } from './map/OpportunityMap'
import {
  CLASS_HIGH_NEED,
  CLASS_INSUFFICIENT,
  CLASS_NO_GAP,
  COHORT_CARDS,
  PERSONA_LENSES,
  answerWizardQuery,
  buildExecutiveBriefing,
  filterTractsByCohort,
  generateCoordinatedActionBrief,
  type CohortId,
  type CoordinatedActionBrief,
  type PersonaLensId,
  type TractRecord,
  type WizardAnswer,
} from './wizard/alignmentWizard'
import './app.css'

export const NO_SITE_CARD_TEXT =
  'No Second Harvest site found under this rule. Other food sources may exist.'
export const DATAKIND_URL = 'http://www.datakind.org'
export const NOT_DRAWN_GEOID = '12095990000'

export interface PlannerBundle {
  readonly thresholds: {
    readonly poverty_cut_q75: number
    readonly poverty_cut_method: string
    readonly sba_loans_median: number
    readonly no_vehicle_q75: number
    readonly drive_time_minutes: number
  }
  readonly counts: {
    readonly total_tracts: number
    readonly drawn_tracts: number
    readonly high_need: number
    readonly no_gap: number
    readonly insufficient: number
    readonly dual_gap: number
    readonly transport_gap: number
    readonly triple_gap: number
  }
  readonly snap_trend?: readonly { readonly month: string; readonly participants: number | null }[]
  readonly meal_gap?: readonly {
    readonly county: string
    readonly rate: string
    readonly people: number | null
  }[]
  readonly tracts: readonly TractRecord[]
}

interface GeoLayers {
  readonly tracts: GeoJSON.FeatureCollection
  readonly counties: GeoJSON.FeatureCollection
  readonly sites: GeoJSON.FeatureCollection
}

export interface OpportunitiesAppProps {
  readonly initialBundle?: PlannerBundle
  readonly initialLoadError?: string
  readonly enableMap?: boolean
}

const BUNDLE_FILES = {
  bundle: 'public/data/planner-bundle.json',
  tracts: 'public/data/tracts.geojson',
  counties: 'public/data/counties.geojson',
  sites: 'public/data/sites.geojson',
} as const

const nf = new Intl.NumberFormat('en-US')
const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})
const pct = (v: number | null) => (v === null ? 'blank' : `${v.toFixed(1)}%`)
const num = (v: number | null) => (v === null ? 'blank' : nf.format(v))

const PROMPT_CHIPS = [
  'Show triple-gap opportunities in Orange County',
  'High-need tracts with zero pantries and low SBA loans',
  'Where should a mobile pantry go in Osceola?',
  'Which Seminole food deserts have no vehicle access?',
  'Insufficient data blind spots',
] as const

async function fetchJson(path: string): Promise<unknown> {
  let res: Response
  try {
    res = await fetch(path.replace(/^public\//, '/'))
  } catch {
    throw new Error(path)
  }
  if (!res.ok) throw new Error(path)
  try {
    return await res.json()
  } catch {
    throw new Error(path)
  }
}

function isFeatureCollection(v: unknown): v is GeoJSON.FeatureCollection {
  return (
    !!v && typeof v === 'object' && 'type' in v && v.type === 'FeatureCollection' && 'features' in v
  )
}

function isBundle(v: unknown): v is PlannerBundle {
  return !!v && typeof v === 'object' && 'tracts' in v && Array.isArray(v.tracts) && 'counts' in v
}

export function OpportunitiesApp(props: OpportunitiesAppProps) {
  const {
    initialBundle,
    initialLoadError,
    enableMap = typeof window !== 'undefined' && !('__vitest_worker__' in globalThis),
  } = props
  const [bundle, setBundle] = useState<PlannerBundle | null>(initialBundle ?? null)
  const [geo, setGeo] = useState<GeoLayers | null>(null)
  const [loadError, setLoadError] = useState<string | null>(initialLoadError ?? null)
  const [persona, setPersona] = useState<PersonaLensId>('alignment')
  const [cohort, setCohort] = useState<CohortId>('triple')
  const [selected, setSelected] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState<WizardAnswer | null>(null)
  const [brief, setBrief] = useState<CoordinatedActionBrief | null>(null)
  const [overlays, setOverlays] = useState({ sba: true, transport: false, sites: false })
  const [panelTab, setPanelTab] = useState<'briefing' | 'evidence'>('briefing')

  useEffect(() => {
    if (initialBundle || initialLoadError) return
    let cancelled = false
    ;(async () => {
      try {
        const raw = await fetchJson(BUNDLE_FILES.bundle)
        if (!isBundle(raw)) throw new Error(BUNDLE_FILES.bundle)
        if (!cancelled) setBundle(raw)
      } catch (err: unknown) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : BUNDLE_FILES.bundle)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [initialBundle, initialLoadError])

  useEffect(() => {
    if (!enableMap || !bundle || loadError) return
    let cancelled = false
    ;(async () => {
      try {
        const [t, c, s] = await Promise.all([
          fetchJson(BUNDLE_FILES.tracts),
          fetchJson(BUNDLE_FILES.counties),
          fetchJson(BUNDLE_FILES.sites),
        ])
        if (!isFeatureCollection(t)) throw new Error(BUNDLE_FILES.tracts)
        if (!isFeatureCollection(c)) throw new Error(BUNDLE_FILES.counties)
        if (!isFeatureCollection(s)) throw new Error(BUNDLE_FILES.sites)
        if (!cancelled) setGeo({ tracts: t, counties: c, sites: s })
      } catch (err: unknown) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : BUNDLE_FILES.tracts)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [enableMap, bundle, loadError])

  const tracts = useMemo(() => bundle?.tracts ?? [], [bundle])
  const briefing = useMemo(() => (tracts.length ? buildExecutiveBriefing(tracts) : []), [tracts])
  const cohortTracts = useMemo(() => {
    const base = answer ? answer.matchedTracts : filterTractsByCohort(tracts, cohort)
    const sorted = [...base].sort((a, b) => (b.pct_poverty ?? 0) - (a.pct_poverty ?? 0))
    return sorted
  }, [tracts, cohort, answer])
  const selectedTract = useMemo(
    () => tracts.find((t) => t.geoid === selected) ?? null,
    [tracts, selected],
  )
  const notDrawn = useMemo(() => tracts.filter((t) => !t.drawn), [tracts])

  const counts = {
    triple: bundle?.counts.triple_gap ?? 0,
    high_need: bundle?.counts.high_need ?? 0,
    dual: bundle?.counts.dual_gap ?? 0,
    transport: bundle?.counts.transport_gap ?? 0,
    insufficient: bundle?.counts.insufficient ?? 0,
  } as const

  const runQuery = (q: string) => {
    setQuery(q)
    setAnswer(q.trim() ? answerWizardQuery(tracts, q) : null)
    setBrief(null)
    setPanelTab('briefing')
  }
  const chooseCohort = (id: CohortId) => {
    setCohort(id)
    setAnswer(null)
    setBrief(null)
    setQuery('')
  }
  const selectTract = (geoid: string | null) => {
    setSelected(geoid)
    if (geoid) setPanelTab('evidence')
  }

  if (loadError) {
    return (
      <div className="app">
        <Header persona={persona} onPersona={setPersona} />
        <main className="main main--error">
          <div className="load-error" role="alert">
            <h2>The planner data did not load</h2>
            <p>
              The file <code>{loadError}</code> is missing or does not parse, so no map is drawn.
              Run <code>python -m src.data_prep.alignment_bundle</code> to rebuild the static
              bundle.
            </p>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  if (!bundle) {
    return (
      <div className="app">
        <Header persona={persona} onPersona={setPersona} />
        <main className="main main--error">
          <div className="loading">Loading Central Florida tract data…</div>
        </main>
        <Footer />
      </div>
    )
  }

  const lens = PERSONA_LENSES.find((p) => p.id === persona)
  if (!lens) throw new Error(`Unknown persona lens ${persona}`)

  return (
    <div className="app" data-persona={persona}>
      <Header persona={persona} onPersona={setPersona} />

      <section className="kpi-strip" aria-label="Opportunity cohorts">
        <div className="kpi-lede">
          <span className="eyebrow">
            Central Florida · 490 tracts · Orange, Seminole, Lake, Osceola
          </span>
          <h1>{lens.label}</h1>
          <p>{lens.tagline}</p>
        </div>
        <div className="kpi-cards">
          {COHORT_CARDS.map((card, i) => (
            <button
              key={card.id}
              type="button"
              data-testid={`kpi-card-${card.id}`}
              className={`kpi-card kpi-card--${card.id}`}
              aria-pressed={cohort === card.id && !answer}
              style={{ animationDelay: `${i * 70}ms` }}
              onClick={() => chooseCohort(card.id)}
            >
              <span className="kpi-value">{counts[card.id]}</span>
              <span className="kpi-label">{card.label}</span>
              <span className="kpi-hint">{card.hint}</span>
            </button>
          ))}
        </div>
      </section>

      <main className="main">
        <div className="map-col">
          {enableMap && geo ? (
            <OpportunityMap
              tractsGeojson={geo.tracts}
              countiesGeojson={geo.counties}
              sitesGeojson={geo.sites}
              records={tracts}
              cohortId={answer ? 'all' : cohort}
              selectedGeoid={selected}
              onSelect={selectTract}
              overlays={overlays}
            />
          ) : (
            <div className="map-placeholder" aria-hidden="true" />
          )}

          <div className="overlay-pills" role="group" aria-label="Alignment overlays">
            <Pill on={overlays.sba} onClick={() => setOverlays((o) => ({ ...o, sba: !o.sba }))}>
              SBA lending gap
            </Pill>
            <Pill
              on={overlays.transport}
              onClick={() => setOverlays((o) => ({ ...o, transport: !o.transport }))}
            >
              No-vehicle transport gap
            </Pill>
            <Pill
              on={overlays.sites}
              onClick={() => setOverlays((o) => ({ ...o, sites: !o.sites }))}
            >
              Second Harvest sites
            </Pill>
          </div>

          <div className="pinned-legend" data-testid="pinned-map-legend" aria-label="Map legend">
            <div className="legend-row">
              <i className="swatch swatch--triple" />
              <span>Opportunity to Serve (triple gap)</span>
              <b>{counts.triple}</b>
            </div>
            <div className="legend-row">
              <i className="swatch swatch--high" />
              <span>{CLASS_HIGH_NEED}</span>
              <b>{counts.high_need}</b>
            </div>
            <div className="legend-row">
              <i className="swatch swatch--nogap" />
              <span>{CLASS_NO_GAP}</span>
              <b>{bundle.counts.no_gap}</b>
            </div>
            <div className="legend-row">
              <i className="swatch swatch--insufficient" />
              <span>{CLASS_INSUFFICIENT}</span>
              <b>{counts.insufficient}</b>
            </div>
            <div className="legend-note">
              Not drawn:{' '}
              {notDrawn.map((t) => (
                <button
                  key={t.geoid}
                  type="button"
                  className="linklike"
                  onClick={() => selectTract(t.geoid)}
                >
                  {t.name} ({t.geoid})
                </button>
              ))}{' '}
              is water with no shape.
            </div>
          </div>
        </div>

        <aside className="panel" aria-label="AI insight and coordinated action wizard">
          <div className="panel-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={panelTab === 'briefing'}
              onClick={() => setPanelTab('briefing')}
            >
              Insight &amp; action
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={panelTab === 'evidence'}
              onClick={() => setPanelTab('evidence')}
            >
              Tract evidence
            </button>
          </div>

          {panelTab === 'briefing' ? (
            <div className="panel-body">
              <section className="briefing">
                <h2>
                  <span className="spark" aria-hidden="true" /> Executive briefing
                </h2>
                <ol>
                  {briefing.map((line, i) => (
                    <li key={i} style={{ animationDelay: `${120 + i * 90}ms` }}>
                      {line}
                    </li>
                  ))}
                </ol>
              </section>

              <section className="ask">
                <h2>Ask the alignment wizard</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    runQuery(query)
                  }}
                >
                  <input
                    aria-label="Ask a question about Central Florida tracts"
                    placeholder="e.g. high-need tracts in Orange County with zero pantries and low SBA loans"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <button type="submit">Ask</button>
                </form>
                <div className="chips">
                  {PROMPT_CHIPS.map((c) => (
                    <button key={c} type="button" className="chip" onClick={() => runQuery(c)}>
                      {c}
                    </button>
                  ))}
                </div>
                {answer && (
                  <div className="answer" role="status">
                    <p>{answer.answerText}</p>
                    {answer.appliedFilters.length > 0 && (
                      <ul className="filters">
                        {answer.appliedFilters.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    )}
                    <button type="button" className="linklike" onClick={() => runQuery('')}>
                      Clear and return to cohort cards
                    </button>
                  </div>
                )}
              </section>

              <section className="shortlist">
                <h2>
                  Opportunities to serve <span className="count">{cohortTracts.length}</span>
                </h2>
                <ul>
                  {cohortTracts.slice(0, 40).map((t) => (
                    <li key={t.geoid}>
                      <button
                        type="button"
                        data-testid={`tract-row-${t.geoid}`}
                        aria-current={selected === t.geoid}
                        onClick={() => selectTract(t.geoid)}
                      >
                        <span className="row-name">
                          {t.name}
                          <span className="row-county">{t.county}</span>
                        </span>
                        <span className="row-badges">
                          <em title="Poverty rate">{pct(t.pct_poverty)}</em>
                          <em title="SBA 7(a)/504 loans since 2010">{t.sba_loans_total} SBA</em>
                          <em title="Households without a vehicle">
                            {pct(t.pct_no_vehicle)} no car
                          </em>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                {cohortTracts.length > 40 && (
                  <p className="muted">
                    Showing the 40 highest-poverty tracts of {cohortTracts.length}.
                  </p>
                )}
              </section>

              <section className="action">
                <button
                  type="button"
                  className="cta"
                  onClick={() =>
                    setBrief(
                      generateCoordinatedActionBrief({
                        tracts: answer ? answer.matchedTracts : tracts,
                        cohortId: answer ? 'all' : cohort,
                        personaId: persona,
                      }),
                    )
                  }
                  disabled={cohortTracts.length === 0}
                >
                  Generate coordinated action brief
                </button>
                {brief && <BriefCard brief={brief} />}
              </section>
            </div>
          ) : (
            <div className="panel-body">
              {selectedTract ? (
                <TractEvidence t={selectedTract} thresholds={bundle.thresholds} />
              ) : (
                <p className="muted">
                  Select a tract on the map or in the shortlist to see its evidence.
                </p>
              )}
            </div>
          )}
        </aside>
      </main>

      <Footer />
    </div>
  )
}

function Header({
  persona,
  onPersona,
}: {
  persona: PersonaLensId
  onPersona: (p: PersonaLensId) => void
}) {
  return (
    <header className="header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span className="brand-name">Beacon</span>
        <span className="brand-title">Opportunities to Serve · Central Florida</span>
      </div>
      <nav className="lenses" aria-label="Persona lens">
        {PERSONA_LENSES.map((p) => (
          <button
            key={p.id}
            type="button"
            className="lens"
            aria-pressed={persona === p.id}
            onClick={() => onPersona(p.id)}
          >
            {p.label}
          </button>
        ))}
      </nav>
    </header>
  )
}

function Footer() {
  return (
    <footer className="footer" role="contentinfo">
      <span>
        Indicators from DataKind&apos;s Beacon. Beacon content is CC BY 4.0. Credit:{' '}
        <a href={DATAKIND_URL} target="_blank" rel="noreferrer">
          DataKind and Beacon (www.datakind.org)
        </a>
        .
      </span>
      <span>
        Sources: ACS 2024 S1701, S2201, B08201, S1901 · USDA SRAM 2025 · SBA FOIA 7(a)/504 · Second
        Harvest · Census 2020 blocks · FEMA NRI
      </span>
    </footer>
  )
}

function Pill({
  on,
  onClick,
  children,
}: {
  on: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button type="button" className="pill" aria-pressed={on} onClick={onClick}>
      {children}
    </button>
  )
}

function BriefCard({ brief }: { brief: CoordinatedActionBrief }) {
  return (
    <article className="brief" data-testid="coordinated-action-brief">
      <h3>{brief.title}</h3>
      <div className="counterfactual">
        <div>
          <span className="cf-label">Without coordination</span>
          <span className="cf-value cf-value--bad">{brief.withoutCoordinationGapPct}%</span>
          <span className="cf-sub">of target tracts have no site inside</span>
        </div>
        <div>
          <span className="cf-label">With joint deployment</span>
          <span className="cf-value cf-value--good">{brief.withJointDeploymentGapPct}%</span>
          <span className="cf-sub">↓ {brief.percentagePointReduction} points</span>
        </div>
      </div>
      <dl className="brief-facts">
        <dt>Target tracts</dt>
        <dd>{brief.targetTractCount}</dd>
        <dt>Residents covered</dt>
        <dd>{nf.format(brief.totalResidentsCovered)}</dd>
        <dt>Mobile-priority tracts</dt>
        <dd>{brief.mobilePriorityTractCount}</dd>
        <dt>SBA lending-gap tracts</dt>
        <dd>{brief.dualGapTractCount}</dd>
      </dl>
      <h4>Food bank planner</h4>
      <p>{brief.foodBankAction}</p>
      <h4>SBA / CDFI officer</h4>
      <p>{brief.sbaOfficerAction}</p>
      <h4>Narrative</h4>
      <p>{brief.narrativeSummary}</p>
      <p className="sources">Sources: {brief.sourcesCited.join(', ')}</p>
    </article>
  )
}

function TractEvidence({
  t,
  thresholds,
}: {
  t: TractRecord
  thresholds: PlannerBundle['thresholds']
}) {
  const povertyMet = t.pct_poverty !== null && t.pct_poverty >= thresholds.poverty_cut_q75
  const lilaMet = t.lila_flag === 1
  return (
    <article className="evidence" data-testid="tract-evidence-panel">
      <header>
        <h2>{t.name}</h2>
        <div className="muted">
          {t.county} County · <code>{t.geoid}</code>
          {!t.drawn && ' · not drawn (water, no shape)'}
        </div>
        <div
          className={`class-badge class-badge--${t.is_triple_gap ? 'triple' : t.tract_class === CLASS_HIGH_NEED ? 'high' : t.tract_class === CLASS_INSUFFICIENT ? 'insufficient' : 'nogap'}`}
        >
          {t.is_triple_gap ? 'Opportunity to Serve · ' : ''}
          {t.tract_class}
        </div>
      </header>

      <section>
        <h3>Recommended coordinated action</h3>
        <p className="action-line">{t.recommended_action}</p>
      </section>

      <section>
        <h3>Why this class</h3>
        <dl className="facts">
          <dt>
            Poverty rate (cut {thresholds.poverty_cut_q75.toFixed(3)}%,{' '}
            {thresholds.poverty_cut_method})
          </dt>
          <dd>
            {pct(t.pct_poverty)}{' '}
            <span className={`check ${povertyMet ? 'yes' : 'no'}`}>
              {povertyMet ? 'meets' : 'below'}
            </span>
          </dd>
          <dt>USDA low income &amp; low access, driving distance</dt>
          <dd>
            <span className={`check ${lilaMet ? 'yes' : 'no'}`}>
              {t.lila_flag === null ? 'blank' : lilaMet ? 'Yes' : 'No'}
            </span>
          </dd>
        </dl>
      </section>

      <section>
        <h3>Cross-agency alignment</h3>
        <dl className="facts">
          <dt>SBA 7(a)/504 loans since 2010 (median {thresholds.sba_loans_median})</dt>
          <dd>
            {t.sba_loans_total} · {money.format(t.sba_gross_usd_total)}
            {t.is_dual_gap && <span className="check no">lending gap</span>}
          </dd>
          <dt>
            Households without a vehicle (top quartile ≥ {thresholds.no_vehicle_q75.toFixed(2)}%)
          </dt>
          <dd>
            {pct(t.pct_no_vehicle)}
            {t.is_transport_gap && <span className="check no">mobile priority</span>}
          </dd>
          <dt>Second Harvest sites inside the tract</dt>
          <dd>{t.sites_in_tract}</dd>
          <dt>Sites within reach · residents per site</dt>
          <dd>
            {t.sites_in_reach} · {num(t.pantry_load)}
          </dd>
        </dl>
        {t.sites_in_tract === 0 && <p className="callout">{NO_SITE_CARD_TEXT}</p>}
      </section>

      <section>
        <h3>Context</h3>
        <dl className="facts">
          <dt>Median household income (90% MOE)</dt>
          <dd>
            {t.median_household_income === null
              ? `blank (${t.income_status})`
              : money.format(t.median_household_income)}
            {t.median_household_income_moe90 !== null &&
              ` ± ${money.format(t.median_household_income_moe90)}`}
          </dd>
          <dt>Households on SNAP</dt>
          <dd>
            {pct(t.pct_hh_snap)} ({num(t.snap_households)} of {num(t.households)})
          </dd>
          <dt>Population 2020 (tract sum)</dt>
          <dd>{nf.format(t.pop2020)}</dd>
          <dt>FEMA risk / social vulnerability</dt>
          <dd>
            {t.nri_risk ?? 'blank'} / {t.social_vulnerability ?? 'blank'}
          </dd>
        </dl>
      </section>

      <section className="confidence">
        <h3>Confidence</h3>
        <strong className={`conf conf--${t.confidence_level.toLowerCase().replace(/\s+/g, '-')}`}>
          {t.confidence_level}
        </strong>
        <p>{t.confidence_reason}</p>
      </section>

      <section>
        <h3>Missing indicators ({t.missing_indicators.length})</h3>
        <ul className="missing">
          {t.missing_indicators.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </section>

      <p className="sources">
        Sources: ACS 2024 S1701 (DS-H2), S2201 (DS-H1), B08201 (DS-X7b), S1901/B19013 (DS-X28); USDA
        SRAM 2025 (DS-H6); SBA FOIA (DS-X5); Second Harvest (DS-X12); Census 2020 blocks (DS-X24);
        FEMA NRI (DS-X16b).
      </p>
    </article>
  )
}
