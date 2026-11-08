import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { AiAnswerCard, AiUnavailableNotice, AskPending } from './ai/AiAnswer'
import { tractGeoidsInResults, type AskAnswer, type AskService } from './ai/askClient'
import { OpportunityMap } from './map/OpportunityMap'
import { ProximityControls } from './map/ProximityControls'
import {
  DEFAULT_REACH_MILES,
  clampReachMiles,
  evaluateProximity,
  nearestSiteDistances,
  reachMinutes,
  sitesWithinMiles,
} from './map/proximity'
import { plainAction, plainConfidence, plainMissing } from './plainWords'
import { DataSources, SourceLinks } from './SourceCitations'
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
    readonly sba_rate_cut_per_1000: number
    readonly sba_min_population: number
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
  readonly initialSites?: GeoJSON.FeatureCollection
  readonly initialLoadError?: string
  readonly enableMap?: boolean
  /** The QueryService `ask` client. Without it, questions use the built-in wizard only. */
  readonly askService?: AskService
}

const BUNDLE_FILES = {
  bundle: 'public/data/planner-bundle.json',
  tracts: 'public/data/tracts.geojson',
  counties: 'public/data/counties.geojson',
  sites: 'public/data/sites.geojson',
} as const

const SHORTLIST_MAX = 40
const PERSONA_COHORTS: Record<PersonaLensId, CohortId> = {
  alignment: 'triple',
  planner: 'high_need',
  officer: 'dual',
}

const nf = new Intl.NumberFormat('en-US')
const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})
const pct = (v: number | null) => (v === null ? 'No data' : `${v.toFixed(1)}%`)
const num = (v: number | null) => (v === null ? 'No data' : nf.format(v))

const PROMPT_CHIPS = [
  'All three gaps in Orange County',
  'Food deserts with no pantry and few SBA loans',
  'Where should a mobile pantry go in Osceola?',
  'Food deserts in Seminole without a car',
  'Places with missing data',
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
    askService,
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
  const [overlays, setOverlays] = useState({ sba: false, transport: false, sites: false })
  const [emphasizeGaps, setEmphasizeGaps] = useState(false)
  const [proximityEnabled, setProximityEnabled] = useState(false)
  const [proximityMiles, setProximityMiles] = useState(DEFAULT_REACH_MILES)
  const [panelTab, setPanelTab] = useState<'briefing' | 'evidence'>('briefing')
  const [asking, setAsking] = useState(false)
  const [aiAnswer, setAiAnswer] = useState<AskAnswer | null>(null)
  const [aiUnavailable, setAiUnavailable] = useState(false)
  const askRun = useRef<AbortController | null>(null)

  useEffect(() => () => askRun.current?.abort(), [])

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
  const knownGeoids = useMemo(() => new Set(tracts.map((t) => t.geoid)), [tracts])
  const briefing = useMemo(
    () =>
      tracts.length
        ? buildExecutiveBriefing(tracts, {
            snapTrend: bundle?.snap_trend,
            mealGap: bundle?.meal_gap,
          })
        : [],
    [tracts, bundle],
  )
  const baseCohortTracts = useMemo(() => {
    const base = answer ? answer.matchedTracts : filterTractsByCohort(tracts, cohort)
    const sorted = [...base].sort((a, b) => (b.pct_poverty ?? 0) - (a.pct_poverty ?? 0))
    return sorted
  }, [tracts, cohort, answer])
  const sites = geo?.sites ?? props.initialSites
  const siteDistances = useMemo(
    () => (sites ? nearestSiteDistances(tracts, sites) : null),
    [tracts, sites],
  )
  const proximity = useMemo(
    () =>
      siteDistances ? evaluateProximity(baseCohortTracts, siteDistances, proximityMiles) : null,
    [baseCohortTracts, siteDistances, proximityMiles],
  )
  const proximityActive = proximityEnabled && proximity !== null
  const cohortTracts = proximityActive ? proximity.outside : baseCohortTracts
  const focusedGeoids = useMemo(
    () => cohortTracts.filter((t) => t.drawn).map((t) => t.geoid),
    [cohortTracts],
  )
  const selectedTract = useMemo(
    () => tracts.find((t) => t.geoid === selected) ?? null,
    [tracts, selected],
  )
  const selectedSiteCount = useMemo(
    () =>
      sites && selectedTract
        ? sitesWithinMiles(selectedTract.centroid, sites, proximityMiles)
        : null,
    [sites, selectedTract, proximityMiles],
  )
  const notDrawn = useMemo(() => tracts.filter((t) => !t.drawn), [tracts])

  const counts = {
    triple: bundle?.counts.triple_gap ?? 0,
    high_need: bundle?.counts.high_need ?? 0,
    dual: bundle?.counts.dual_gap ?? 0,
    transport: bundle?.counts.transport_gap ?? 0,
    insufficient: bundle?.counts.insufficient ?? 0,
  } as const

  const resetAsk = () => {
    askRun.current?.abort()
    askRun.current = null
    setAsking(false)
    setAiAnswer(null)
    setAiUnavailable(false)
  }
  const askAi = async (service: AskService, q: string) => {
    const run = new AbortController()
    askRun.current = run
    setAsking(true)
    const outcome = await service(q.trim(), run.signal).catch(() => ({ ok: false as const }))
    if (askRun.current !== run) return
    askRun.current = null
    setAsking(false)
    if (outcome.ok) {
      // A tract list in the reply focuses the map and the shortlist, like a built-in answer.
      const geoids = new Set(tractGeoidsInResults(outcome.answer.results, knownGeoids))
      setAiAnswer(outcome.answer)
      setAnswer(
        geoids.size > 0
          ? {
              matchedTracts: tracts.filter((t) => geoids.has(t.geoid)),
              answerText: outcome.answer.answer,
              appliedFilters: [],
            }
          : null,
      )
    } else {
      // REQ-39 / SEQ-9: the built-in wizard answers, with the notice.
      setAiUnavailable(true)
      setAnswer(answerWizardQuery(tracts, q))
    }
  }
  const runQuery = (q: string) => {
    resetAsk()
    setQuery(q)
    setBrief(null)
    setPanelTab('briefing')
    if (!q.trim() || !askService) {
      setAnswer(q.trim() ? answerWizardQuery(tracts, q) : null)
      return
    }
    setAnswer(null)
    void askAi(askService, q)
  }
  const chooseCohort = (id: CohortId) => {
    resetAsk()
    setCohort(id)
    setAnswer(null)
    setBrief(null)
    setQuery('')
  }
  const choosePersona = (id: PersonaLensId) => {
    setPersona(id)
    chooseCohort(PERSONA_COHORTS[id])
  }
  const changeProximity = (miles: number) => {
    setProximityMiles(clampReachMiles(miles))
    setProximityEnabled(true)
    setEmphasizeGaps(true)
    setBrief(null)
  }
  const selectTract = (geoid: string | null) => {
    setSelected(geoid)
    if (geoid) setPanelTab('evidence')
  }

  if (loadError) {
    return (
      <div className="app">
        <Header persona={persona} onPersona={choosePersona} />
        <main className="main main--error shell">
          <div className="load-error" role="alert">
            <h2>The map data did not load</h2>
            <p>
              The file <code>{loadError}</code> is missing or broken, so the map is not shown. To
              build it again, run <code>python -m src.data_prep.alignment_bundle</code>.
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
        <Header persona={persona} onPersona={choosePersona} />
        <main className="main main--error shell">
          <div className="loading">Loading the map data…</div>
        </main>
        <Footer />
      </div>
    )
  }

  const lens = PERSONA_LENSES.find((p) => p.id === persona)
  if (!lens) throw new Error(`Unknown persona lens ${persona}`)
  const cohortLabel = answer
    ? 'Your question'
    : (COHORT_CARDS.find((c) => c.id === cohort)?.label ?? 'All neighborhoods')

  return (
    <div className="app" data-persona={persona}>
      <Header persona={persona} onPersona={choosePersona} />

      <section className="hero shell" aria-label="Groups of neighborhoods">
        <div className="hero-lede">
          <span className="eyebrow">Orange, Seminole, Lake and Osceola counties</span>
          <h1>{lens.headline}</h1>
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
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => chooseCohort(card.id)}
            >
              <span className="kpi-value">{counts[card.id]}</span>
              <span className="kpi-label">{card.label}</span>
              <span className="kpi-hint">{card.hint}</span>
            </button>
          ))}
        </div>
      </section>

      <main className="main shell">
        <div className="map-col">
          <div className="map-toolbar">
            <div className="gap-context" id="gap-emphasis-context" role="status">
              <strong>{cohortLabel}</strong>
              {proximityActive && (
                <span>
                  Beyond {proximityMiles} mi / {reachMinutes(proximityMiles)} min estimated
                </span>
              )}
              <span>
                {nf.format(focusedGeoids.length)}{' '}
                {focusedGeoids.length === 1 ? 'neighborhood' : 'neighborhoods'} on map
                {cohortTracts.length > focusedGeoids.length &&
                  `; ${cohortTracts.length - focusedGeoids.length} without a map shape`}
                .{' '}
                {focusedGeoids.length === 0
                  ? 'No areas to emphasize.'
                  : emphasizeGaps
                    ? 'Outlined; other areas faded.'
                    : 'Emphasize this group on the map.'}
              </span>
            </div>
            <button
              type="button"
              className="gap-emphasis-button"
              aria-pressed={emphasizeGaps}
              aria-describedby="gap-emphasis-context"
              onClick={() => setEmphasizeGaps((on) => !on)}
            >
              <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
                <path
                  d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.7" />
              </svg>
              Emphasize gaps
            </button>
          </div>
          <ProximityControls
            ready={proximity !== null}
            enabled={proximityEnabled}
            miles={proximityMiles}
            outsideCount={proximity?.outside.length ?? 0}
            withinCount={proximity?.withinCount ?? 0}
            unknownCount={proximity?.unknown.length ?? 0}
            onEnabled={(enabled) => {
              setProximityEnabled(enabled)
              if (enabled) setEmphasizeGaps(true)
              setBrief(null)
            }}
            onMiles={changeProximity}
            onReset={() => {
              setProximityMiles(DEFAULT_REACH_MILES)
              setProximityEnabled(false)
              setBrief(null)
            }}
          />
          <div className="map-viewport">
            {enableMap && geo ? (
              <OpportunityMap
                tractsGeojson={geo.tracts}
                countiesGeojson={geo.counties}
                sitesGeojson={geo.sites}
                records={tracts}
                focusedGeoids={focusedGeoids}
                emphasizeGaps={emphasizeGaps}
                selectedGeoid={selected}
                onSelect={selectTract}
                overlays={overlays}
              />
            ) : (
              <div className="map-placeholder" aria-hidden="true" />
            )}

            <div className="overlay-pills" role="group" aria-label="Add to the map">
              <Pill
                on={overlays.sba}
                swatch="dash"
                onClick={() => setOverlays((o) => ({ ...o, sba: !o.sba }))}
              >
                Few business loans
              </Pill>
              <Pill
                on={overlays.transport}
                swatch="hatch"
                onClick={() => setOverlays((o) => ({ ...o, transport: !o.transport }))}
              >
                Many with no car
              </Pill>
              <Pill
                on={overlays.sites}
                swatch="dot"
                onClick={() => setOverlays((o) => ({ ...o, sites: !o.sites }))}
              >
                Second Harvest sites
              </Pill>
            </div>

            <div className="pinned-legend" data-testid="pinned-map-legend" aria-label="Map key">
              {emphasizeGaps && focusedGeoids.length > 0 && (
                <div className="legend-row legend-emphasis">
                  <i className="swatch swatch--emphasis" />
                  <span>Emphasized gaps</span>
                  <b>{focusedGeoids.length}</b>
                </div>
              )}
              <div className="legend-row">
                <i className="swatch swatch--triple" />
                <span>All three gaps</span>
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
                Not on the map:{' '}
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
                is water.
              </div>
            </div>
          </div>
        </div>

        <aside className="panel" aria-label="Findings and neighborhood details">
          <div className="panel-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={panelTab === 'briefing'}
              onClick={() => setPanelTab('briefing')}
            >
              Key findings
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={panelTab === 'evidence'}
              onClick={() => setPanelTab('evidence')}
            >
              Neighborhood details
            </button>
          </div>

          {panelTab === 'briefing' ? (
            <div className="panel-body" key="briefing">
              <section className="briefing">
                <h2>What the data shows</h2>
                <ol className="insights">
                  {briefing.map((item, i) => (
                    <li key={i} style={{ animationDelay: `${100 + i * 80}ms` }}>
                      <span className={`insight-figure insight-figure--${item.tone}`}>
                        {item.figure}
                      </span>
                      <div className="insight-text">
                        {item.text}
                        <SourceLinks ids={item.sourceIds} />
                      </div>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="ask">
                <h2>Ask a question</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    runQuery(query)
                  }}
                >
                  <input
                    aria-label="Ask a question about Central Florida neighborhoods"
                    placeholder="Try a county, pantries, cars or loans"
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
                {asking && <AskPending />}
                {aiAnswer && (
                  <AiAnswerCard
                    answer={aiAnswer}
                    knownGeoids={knownGeoids}
                    onClear={() => runQuery('')}
                    extra={
                      answer &&
                      proximityActive && (
                        <p>Of these, {cohortTracts.length} are beyond the proximity limit.</p>
                      )
                    }
                  />
                )}
                {answer && !aiAnswer && (
                  <div className="answer" role="status">
                    {aiUnavailable && <AiUnavailableNotice />}
                    <p>{answer.answerText}</p>
                    {proximityActive && (
                      <p>Of these, {cohortTracts.length} are beyond the proximity limit.</p>
                    )}
                    {answer.appliedFilters.length > 0 && (
                      <ul className="filters">
                        {answer.appliedFilters.map((f) => (
                          <li key={f}>{f}</li>
                        ))}
                      </ul>
                    )}
                    <button type="button" className="linklike" onClick={() => runQuery('')}>
                      Clear
                    </button>
                  </div>
                )}
              </section>

              <section className="shortlist">
                <h2>
                  Where to start <span className="count">{cohortTracts.length}</span>
                </h2>
                <p className="shortlist-sub">
                  {cohortLabel}
                  {proximityActive ? `, beyond ${proximityMiles} miles` : ''}, most poverty first.
                  Pick one to see why.
                </p>
                <ul>
                  {cohortTracts.slice(0, SHORTLIST_MAX).map((t) => (
                    <li key={t.geoid}>
                      <button
                        type="button"
                        data-testid={`tract-row-${t.geoid}`}
                        aria-current={selected === t.geoid}
                        onClick={() => selectTract(t.geoid)}
                      >
                        <span className="row-name">
                          <span>{t.name}</span>
                          <span className="row-county">{t.county}</span>
                        </span>
                        <span className="row-badges">
                          <em title="People in poverty">{pct(t.pct_poverty)} poverty</em>
                          <em title="Homes with no car">{pct(t.pct_no_vehicle)} no car</em>
                          <em title="SBA loans since 2010">
                            {t.sba_loans_total} {t.sba_loans_total === 1 ? 'loan' : 'loans'}
                          </em>
                          {proximityActive && (
                            <em title="Straight-line distance to the nearest Second Harvest site">
                              {siteDistances?.get(t.geoid)?.toFixed(1)} mi to a site
                            </em>
                          )}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                {cohortTracts.length > SHORTLIST_MAX && (
                  <p className="muted small">
                    Showing the {SHORTLIST_MAX} with the most poverty, out of {cohortTracts.length}.
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
                        tracts: proximityActive
                          ? cohortTracts
                          : answer
                            ? answer.matchedTracts
                            : tracts,
                        cohortId: proximityActive || answer ? 'all' : cohort,
                        personaId: persona,
                      }),
                    )
                  }
                  disabled={cohortTracts.length === 0}
                >
                  Make an action plan
                </button>
                {brief && <BriefCard brief={brief} />}
              </section>
            </div>
          ) : (
            <div className="panel-body" key={`evidence-${selected ?? 'none'}`}>
              {selectedTract ? (
                <TractEvidence
                  t={selectedTract}
                  thresholds={bundle.thresholds}
                  proximityMiles={proximityMiles}
                  nearbySiteCount={selectedSiteCount}
                />
              ) : (
                <p className="muted">Pick a neighborhood on the map or in the list.</p>
              )}
            </div>
          )}
        </aside>
      </main>

      <DataSources
        povertyCut={bundle.thresholds.poverty_cut_q75}
        lendingCut={bundle.thresholds.sba_rate_cut_per_1000}
        minPopulation={bundle.thresholds.sba_min_population}
        transportCut={bundle.thresholds.no_vehicle_q75}
      />
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
      <div className="header-inner shell">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">Beacon</span>
          <span className="brand-title">Opportunities to Serve · Central Florida</span>
        </div>
        <nav className="lenses" aria-label="Choose a view">
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
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer className="footer shell" role="contentinfo">
      <span>
        Data from DataKind&apos;s Beacon, shared under CC BY 4.0. Credit:{' '}
        <a href={DATAKIND_URL} target="_blank" rel="noreferrer">
          DataKind and Beacon (www.datakind.org)
        </a>
        .
      </span>
      <span>
        Sources: Census ACS 2024 · USDA SRAM 2025 · SBA loans · Second Harvest · Census 2020 · FEMA
        · CBPP SNAP Tracker · Feeding America 2024
      </span>
    </footer>
  )
}

function Pill({
  on,
  swatch,
  onClick,
  children,
}: {
  on: boolean
  swatch: 'dash' | 'hatch' | 'dot'
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button type="button" className="pill" aria-pressed={on} onClick={onClick}>
      <i className={`pill-swatch pill-swatch--${swatch}`} aria-hidden="true" />
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
          <span className="cf-label">Today</span>
          <span className="cf-value cf-value--bad">{brief.withoutCoordinationGapPct}%</span>
          <span className="cf-sub">have no Second Harvest site inside</span>
        </div>
        <div>
          <span className="cf-label">If both partners act</span>
          <span className="cf-value cf-value--good">{brief.withJointDeploymentGapPct}%</span>
          <span className="cf-sub">{brief.percentagePointReduction} points lower</span>
        </div>
      </div>
      <dl className="brief-facts">
        <dt>Neighborhoods</dt>
        <dd>{brief.targetTractCount}</dd>
        <dt>People</dt>
        <dd>{nf.format(brief.totalResidentsCovered)}</dd>
        <dt>Many with no car</dt>
        <dd>{brief.mobilePriorityTractCount}</dd>
        <dt>Few business loans</dt>
        <dd>{brief.dualGapTractCount}</dd>
      </dl>
      <h4>Food bank</h4>
      <p>{brief.foodBankAction}</p>
      <h4>Small business lender (SBA, CDFI)</h4>
      <p>{brief.sbaOfficerAction}</p>
      <h4>In short</h4>
      <p>{brief.narrativeSummary}</p>
      <SourceLinks ids={brief.sourcesCited} />
    </article>
  )
}

function Fact({
  label,
  note,
  value,
  tag,
}: {
  label: string
  note?: string
  value: ReactNode
  tag?: { readonly good: boolean; readonly text: string } | null
}) {
  return (
    <div className="fact">
      <dt>
        {label}
        {note && <span className="fact-note">{note}</span>}
      </dt>
      <dd>
        {value}
        {tag && <span className={`check ${tag.good ? 'yes' : 'no'}`}>{tag.text}</span>}
      </dd>
    </div>
  )
}

function incomeText(t: TractRecord): string {
  if (t.median_household_income === null) return 'Not published'
  const base = money.format(t.median_household_income)
  const moe =
    t.median_household_income_moe90 !== null
      ? ` ± ${money.format(t.median_household_income_moe90)}`
      : ''
  return t.income_status === 'lower_bound' ? `${base} or more${moe}` : `${base}${moe}`
}

function TractEvidence({
  t,
  thresholds,
  proximityMiles,
  nearbySiteCount,
}: {
  t: TractRecord
  thresholds: PlannerBundle['thresholds']
  proximityMiles: number
  nearbySiteCount: number | null
}) {
  const povertyMet = t.pct_poverty !== null && t.pct_poverty >= thresholds.poverty_cut_q75
  const lilaMet = t.lila_flag === 1
  const badge = t.is_triple_gap
    ? 'triple'
    : t.tract_class === CLASS_HIGH_NEED
      ? 'high'
      : t.tract_class === CLASS_INSUFFICIENT
        ? 'insufficient'
        : 'nogap'
  return (
    <article className="evidence" data-testid="tract-evidence-panel">
      <header>
        <h2>{t.name}</h2>
        <div className="muted small">
          {t.county} County · <code>{t.geoid}</code>
          {!t.drawn && ' · not on the map (water)'}
        </div>
        <div className={`class-badge class-badge--${badge}`}>
          {t.is_triple_gap ? 'All three gaps · ' : ''}
          {t.tract_class}
        </div>
      </header>

      <section>
        <h3>What could help</h3>
        <p className="action-line">{plainAction(t.recommended_action)}</p>
      </section>

      <section>
        <h3>Why it is on the map</h3>
        <dl className="facts">
          <Fact
            label="People in poverty"
            note={`High means ${thresholds.poverty_cut_q75}% or more`}
            value={pct(t.pct_poverty)}
            tag={
              t.pct_poverty === null
                ? null
                : { good: !povertyMet, text: povertyMet ? 'high' : 'not high' }
            }
          />
          <Fact
            label="Low income and far from a store"
            note="USDA test: over 1/2 mile in town or 10 miles in the country, by road"
            value={t.lila_flag === null ? 'No data' : lilaMet ? 'Yes' : 'No'}
          />
        </dl>
      </section>

      <section>
        <h3>Food and money</h3>
        <dl className="facts">
          <Fact
            label="SBA loans since 2010"
            note={`Few means ${thresholds.sba_rate_cut_per_1000.toFixed(2)} or fewer per 1,000 people, in places with ${nf.format(thresholds.sba_min_population)} or more people`}
            value={
              t.pop2020 > 0
                ? `${t.sba_loans_total} (${((t.sba_loans_total / t.pop2020) * 1000).toFixed(2)} per 1,000 people) · ${money.format(t.sba_gross_usd_total)}`
                : `${t.sba_loans_total} · ${money.format(t.sba_gross_usd_total)}`
            }
            tag={t.is_dual_gap ? { good: false, text: 'few' } : null}
          />
          <Fact
            label="Homes with no car"
            note={`Many means ${thresholds.no_vehicle_q75}% or more`}
            value={pct(t.pct_no_vehicle)}
            tag={t.is_transport_gap ? { good: false, text: 'many' } : null}
          />
          <Fact label="Second Harvest sites inside" value={t.sites_in_tract} />
          <Fact
            label={`Sites within ${proximityMiles} ${proximityMiles === 1 ? 'mile' : 'miles'}`}
            note="Straight-line from the population center"
            value={nearbySiteCount === null ? 'No data' : nearbySiteCount}
          />
          <Fact
            label="People per nearby site"
            note="2020 population divided by sites in this radius"
            value={num(
              nearbySiteCount !== null && nearbySiteCount > 0 && t.pop2020 > 0
                ? Math.round(t.pop2020 / nearbySiteCount)
                : null,
            )}
          />
        </dl>
        {t.sites_in_tract === 0 && <p className="callout">{NO_SITE_CARD_TEXT}</p>}
      </section>

      <section>
        <h3>The people</h3>
        <dl className="facts">
          <Fact
            label="Typical home income"
            note="Median, ± 90% margin of error"
            value={incomeText(t)}
          />
          <Fact
            label="Homes on SNAP"
            value={`${pct(t.pct_hh_snap)} (${num(t.snap_households)} of ${num(t.households)})`}
          />
          <Fact label="People" note="2020 Census" value={nf.format(t.pop2020)} />
          <Fact label="Disaster risk" note="FEMA" value={t.nri_risk ?? 'No data'} />
          <Fact
            label="Social vulnerability"
            note="FEMA"
            value={t.social_vulnerability ?? 'No data'}
          />
        </dl>
      </section>

      <section className="confidence">
        <h3>How sure are we?</h3>
        <strong className={`conf conf--${t.confidence_level.toLowerCase().replace(/\s+/g, '-')}`}>
          {t.confidence_level}
        </strong>
        <p>{plainConfidence(t.confidence_reason)}</p>
      </section>

      <section>
        <h3>What we do not know ({t.missing_indicators.length})</h3>
        <ul className="missing">
          {t.missing_indicators.map((m) => (
            <li key={m}>{plainMissing(m)}</li>
          ))}
        </ul>
      </section>

      <SourceLinks
        ids={[
          'DS-H2',
          'DS-H1',
          'DS-H6',
          'DS-X5',
          'DS-X7b',
          'DS-X28',
          'DS-X12',
          'DS-X24',
          'DS-X16b',
          'DS-H7',
        ]}
      />
    </article>
  )
}
