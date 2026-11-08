import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { CutControls } from './map/CutControls'
import { AiAnswerCard, AiUnavailableNotice, AskPending, SessionEndedNotice } from './ai/AiAnswer'
import { type AskAnswer, type AskService } from './ai/askClient'
import { DriveTimeEstimate, DriveTimeNotes, type DriveTimeProps } from './map/DriveTimeEstimate'
import { routingInputs } from './map/driveTimes'
import { nearestSiteDistances } from './map/proximity'
import { useDriveTimes } from './map/useDriveTimes'
import { OpportunityMap } from './map/OpportunityMap'
import { ProximityControls } from './map/ProximityControls'
import {
  DEFAULT_REACH_MILES,
  milesText,
  reachFacts,
  reachMiles,
  splitByReach,
  type ReachFacts,
} from './map/reach'
import { plainAction, plainConfidence, plainMissing } from './plainWords'
import { DataSources, SourceLinks } from './SourceCitations'
import { SourcesContext, type SourceEntry } from './sources'
import {
  DEFAULT_PERCENTILES,
  applyCuts,
  cutValues,
  percentileLabel,
  rateText,
  type CutName,
  type CutValues,
  type Cuts,
  type Percentiles,
} from './wizard/gapRules'
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
    /** REQ-58: the cut at each named percentile. */
    readonly cuts?: Cuts
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
  /** REQ-61, REQ-62: the only sources the App lists. */
  readonly sources?: readonly SourceEntry[]
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

/** A bundle from before cycle 17 has no cuts or sources; it counts as broken (rebuild it). */
function isBundle(v: unknown): v is PlannerBundle {
  return (
    !!v &&
    typeof v === 'object' &&
    'tracts' in v &&
    Array.isArray(v.tracts) &&
    'counts' in v &&
    'sources' in v &&
    Array.isArray(v.sources) &&
    'thresholds' in v &&
    !!v.thresholds &&
    typeof v.thresholds === 'object' &&
    'cuts' in v.thresholds
  )
}

// Card hints that name a cut follow the chosen percentiles.
const CARD_HINTS: Partial<Record<CohortId, (cut: CutValues, p: Percentiles) => string>> = {
  dual: (_cut, p) =>
    `Food deserts in the ${percentileLabel('sba_rate_per_1000', p.sba_rate_per_1000).toLowerCase()} for SBA loans per 1,000 people`,
  transport: (cut) =>
    `Food deserts where ${rateText(cut.no_vehicle)}% or more of homes have no car`,
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
  // The question in force. Its answer is recounted when the cuts change.
  const [askedQuery, setAskedQuery] = useState('')
  const [brief, setBrief] = useState<CoordinatedActionBrief | null>(null)
  const [overlays, setOverlays] = useState({ sba: false, transport: false, sites: false })
  const [emphasizeGaps, setEmphasizeGaps] = useState(false)
  const [proximityEnabled, setProximityEnabled] = useState(false)
  const [proximityMiles, setProximityMiles] = useState(DEFAULT_REACH_MILES)
  const [percentiles, setPercentiles] = useState<Percentiles>(DEFAULT_PERCENTILES)
  const [panelTab, setPanelTab] = useState<'briefing' | 'evidence'>('briefing')
  const [asking, setAsking] = useState(false)
  const [aiAnswer, setAiAnswer] = useState<AskAnswer | null>(null)
  const [aiUnavailable, setAiUnavailable] = useState(false)
  const [aiSessionEnded, setAiSessionEnded] = useState(false)
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

  // REQ-65: every class, flag, count, fill, list and question below uses the Build's cut for each
  // chosen percentile.
  const cuts = bundle?.thresholds.cuts ?? null
  const cut = useMemo(() => (cuts ? cutValues(cuts, percentiles) : null), [cuts, percentiles])
  const tracts = useMemo(
    () =>
      bundle && cut ? applyCuts(bundle.tracts, cut, bundle.thresholds.sba_min_population) : [],
    [bundle, cut],
  )
  const knownGeoids = useMemo(() => new Set(tracts.map((t) => t.geoid)), [tracts])
  // POST-APP-15: an AI reply's tract list focuses the map and the shortlist, like a built-in answer.
  const answer = useMemo((): ReturnType<typeof answerWizardQuery> | null => {
    if (aiAnswer) {
      const geoids = new Set(aiAnswer.tracts)
      return geoids.size > 0
        ? {
            matchedTracts: tracts.filter((t) => geoids.has(t.geoid)),
            answerText: aiAnswer.answer,
            appliedFilters: [],
          }
        : null
    }
    return askedQuery.trim() ? answerWizardQuery(tracts, askedQuery, cut?.no_vehicle) : null
  }, [aiAnswer, tracts, askedQuery, cut])
  const sites = geo?.sites ?? props.initialSites
  const driveTimes = useDriveTimes(sites !== undefined)
  const routingKey = useMemo(
    () => (sites ? routingInputs(tracts, sites).inputKey : null),
    [tracts, sites],
  )
  const siteDistances = useMemo(
    () => (sites ? nearestSiteDistances(tracts, sites) : null),
    [tracts, sites],
  )
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
  // REQ-56, REQ-64: the split reads the Build's closest-block distance; the App measures nothing.
  const proximity = useMemo(
    () => splitByReach(baseCohortTracts, proximityMiles),
    [baseCohortTracts, proximityMiles],
  )
  // The QueryService applies the distance to an AI answer (REQ-60), so the App does not filter it again.
  const proximityActive = proximityEnabled && !aiAnswer
  const cohortTracts = proximityActive ? proximity.beyond : baseCohortTracts
  const focusedGeoids = useMemo(
    () => cohortTracts.filter((t) => t.drawn).map((t) => t.geoid),
    [cohortTracts],
  )
  const selectedTract = useMemo(
    () => tracts.find((t) => t.geoid === selected) ?? null,
    [tracts, selected],
  )
  const notDrawn = useMemo(() => tracts.filter((t) => !t.drawn), [tracts])
  const driveTimeProps: DriveTimeProps | null = selectedTract && {
    geoid: selectedTract.geoid,
    originLabel: `${selectedTract.name}, ${selectedTract.county} County`,
    population: selectedTract,
    miles: siteDistances?.get(selectedTract.geoid),
    cache: driveTimes.cache,
    inputKey: routingKey,
    now: driveTimes.now,
  }
  // Under the slider: the estimate only. Its notes and the distance rule go in the map's (i) box.
  const sliderDriveTime = driveTimeProps ? (
    <DriveTimeEstimate {...driveTimeProps} showNotes={false} />
  ) : (
    <p className="proximity-note">Select a neighborhood to see its estimated drive time.</p>
  )
  const mapNotes = (
    <>
      {driveTimeProps && <DriveTimeNotes {...driveTimeProps} />}
      <p className="proximity-note">
        A neighborhood is within the distance when any of its populated blocks is. Straight-line
        miles, not road miles.
      </p>
    </>
  )

  const counts = useMemo(
    () => ({
      triple: tracts.filter((t) => t.is_triple_gap).length,
      high_need: tracts.filter((t) => t.tract_class === CLASS_HIGH_NEED).length,
      dual: tracts.filter((t) => t.is_dual_gap).length,
      transport: tracts.filter((t) => t.is_transport_gap).length,
      insufficient: tracts.filter((t) => t.tract_class === CLASS_INSUFFICIENT).length,
      no_gap: tracts.filter((t) => t.tract_class === CLASS_NO_GAP).length,
    }),
    [tracts],
  )

  const resetAsk = () => {
    askRun.current?.abort()
    askRun.current = null
    setAsking(false)
    setAiAnswer(null)
    setAiUnavailable(false)
    setAiSessionEnded(false)
  }
  const askAi = async (service: AskService, q: string) => {
    const run = new AbortController()
    askRun.current = run
    setAsking(true)
    const request = { question: q.trim(), reach_miles: proximityMiles, percentiles }
    const outcome = await service(request, run.signal).catch(() => ({
      ok: false as const,
      sessionEnded: false,
    }))
    if (askRun.current !== run) return
    askRun.current = null
    setAsking(false)
    if (outcome.ok) {
      setAiAnswer(outcome.answer)
    } else {
      // REQ-39 / SEQ-9 and REQ-66: the built-in wizard answers, with the notice.
      if (outcome.sessionEnded) setAiSessionEnded(true)
      else setAiUnavailable(true)
      setAskedQuery(q)
    }
  }
  const runQuery = (q: string) => {
    resetAsk()
    setQuery(q)
    setBrief(null)
    setPanelTab('briefing')
    if (!q.trim() || !askService) {
      setAskedQuery(q)
      return
    }
    setAskedQuery('')
    void askAi(askService, q)
  }
  const chooseCohort = (id: CohortId) => {
    resetAsk()
    setCohort(id)
    setAskedQuery('')
    setBrief(null)
    setQuery('')
  }
  const choosePersona = (id: PersonaLensId) => {
    setPersona(id)
    chooseCohort(PERSONA_COHORTS[id])
  }
  const changeProximity = (miles: number) => {
    setProximityMiles(reachMiles(miles))
    setProximityEnabled(true)
    setEmphasizeGaps(true)
    setBrief(null)
  }
  const changeCut = (name: CutName, percentile: number) => {
    setPercentiles((current) => ({ ...current, [name]: percentile }))
    setBrief(null)
  }
  const resetRules = () => {
    setProximityMiles(DEFAULT_REACH_MILES)
    setProximityEnabled(false)
    setPercentiles(DEFAULT_PERCENTILES)
    setBrief(null)
  }
  const selectTract = (geoid: string | null) => {
    setSelected(geoid)
    if (geoid) setPanelTab('evidence')
  }

  // A bundle without the cycle 17 cuts is from an older Build: rebuild it.
  const brokenFile = loadError ?? (bundle && !cuts ? BUNDLE_FILES.bundle : null)
  if (brokenFile) {
    return (
      <div className="app">
        <Header persona={persona} onPersona={choosePersona} />
        <main className="main main--error shell">
          <div className="load-error" role="alert">
            <h2>The map data did not load</h2>
            <p>
              The file <code>{brokenFile}</code> is missing or broken, so the map is not shown. To
              build it again, run <code>python -m src.data_prep.alignment_bundle</code>.
            </p>
          </div>
        </main>
        <Footer />
      </div>
    )
  }

  if (!bundle || !cuts || !cut) {
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
    <SourcesContext.Provider value={bundle.sources ?? []}>
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
                <span className="kpi-hint">
                  {CARD_HINTS[card.id]?.(cut, percentiles) ?? card.hint}
                </span>
              </button>
            ))}
          </div>
        </section>

        <main className="main shell">
          <div className="map-col">
            <div className="map-toolbar">
              <div className="gap-context" id="gap-emphasis-context" role="status">
                <strong>{cohortLabel}</strong>
                {proximityActive && <span>Beyond {milesText(proximityMiles)}</span>}
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
              enabled={proximityEnabled}
              miles={proximityMiles}
              beyondCount={proximity.beyond.length}
              withinCount={proximity.withinCount}
              unknownCount={proximity.unknown.length}
              onEnabled={(enabled) => {
                setProximityEnabled(enabled)
                if (enabled) setEmphasizeGaps(true)
                setBrief(null)
              }}
              onMiles={changeProximity}
              onReset={resetRules}
              driveTime={sliderDriveTime}
            >
              <CutControls cuts={cuts} percentiles={percentiles} onChange={changeCut} />
            </ProximityControls>
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
                  attributionNotes={mapNotes}
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
                  <b>{counts.no_gap}</b>
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
                  <p className="ask-model">Powered by Gemini 3.8 Flash</p>
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
                    />
                  )}
                  {answer && !aiAnswer && (
                    <div className="answer" role="status">
                      {aiUnavailable && <AiUnavailableNotice />}
                      {aiSessionEnded && <SessionEndedNotice />}
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
                    {proximityActive ? `, beyond ${milesText(proximityMiles)}` : ''}, most poverty
                    first. Pick one to see why.
                  </p>
                  <ul>
                    {(aiAnswer ? cohortTracts : cohortTracts.slice(0, SHORTLIST_MAX)).map((t) => (
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
                              <em title="Straight-line miles from the closest populated block to a Second Harvest site">
                                {t.nearest_block_miles === null
                                  ? 'No distance data'
                                  : `${t.nearest_block_miles.toFixed(1)} mi to a site`}
                              </em>
                            )}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {!aiAnswer && cohortTracts.length > SHORTLIST_MAX && (
                    <p className="muted small">
                      Showing the {SHORTLIST_MAX} with the most poverty, out of{' '}
                      {cohortTracts.length}.
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
                    minPopulation={bundle.thresholds.sba_min_population}
                    cut={cut}
                    reach={reachFacts(selectedTract, proximityMiles)}
                    driveTime={driveTimeProps && <DriveTimeEstimate {...driveTimeProps} />}
                  />
                ) : (
                  <p className="muted">Pick a neighborhood on the map or in the list.</p>
                )}
              </div>
            )}
          </aside>
        </main>

        <DataSources
          povertyCut={rateText(cut.poverty)}
          lendingCut={cut.sba_rate_per_1000}
          lendingPart={percentileLabel(
            'sba_rate_per_1000',
            percentiles.sba_rate_per_1000,
          ).toLowerCase()}
          minPopulation={bundle.thresholds.sba_min_population}
          transportCut={rateText(cut.no_vehicle)}
        />
        <Footer />
      </div>
    </SourcesContext.Provider>
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
  testId,
}: {
  label: string
  note?: string
  value: ReactNode
  tag?: { readonly good: boolean; readonly text: string } | null
  testId?: string
}) {
  return (
    <div className="fact">
      <dt>
        {label}
        {note && <span className="fact-note">{note}</span>}
      </dt>
      <dd data-testid={testId}>
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
  minPopulation,
  cut,
  reach,
  driveTime,
}: {
  t: TractRecord
  minPopulation: number
  cut: CutValues
  reach: ReachFacts
  driveTime: ReactNode
}) {
  const povertyMet = t.pct_poverty !== null && t.pct_poverty >= cut.poverty
  const distance = milesText(reach.miles)
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
            note={`High means ${rateText(cut.poverty)}% or more`}
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
            note={`Few means ${cut.sba_rate_per_1000.toFixed(2)} or fewer per 1,000 people, in places with ${nf.format(minPopulation)} or more people`}
            value={
              t.pop2020 > 0
                ? `${t.sba_loans_total} (${((t.sba_loans_total / t.pop2020) * 1000).toFixed(2)} per 1,000 people) · ${money.format(t.sba_gross_usd_total)}`
                : `${t.sba_loans_total} · ${money.format(t.sba_gross_usd_total)}`
            }
            tag={t.is_dual_gap ? { good: false, text: 'few' } : null}
          />
          <Fact
            label="Homes with no car"
            note={`Many means ${rateText(cut.no_vehicle)}% or more`}
            value={pct(t.pct_no_vehicle)}
            tag={t.is_transport_gap ? { good: false, text: 'many' } : null}
          />
          <Fact label="Second Harvest sites inside" value={t.sites_in_tract} />
          <Fact
            label={`People within ${distance} of a site`}
            note="Share of 2020 population, straight-line from each populated block"
            value={reach.share === null ? 'No people counted' : `${Math.round(reach.share * 100)}%`}
            testId="reach-share"
          />
          <Fact
            label={`Sites within ${distance}`}
            note="Second Harvest sites this close to a populated block"
            value={reach.sites}
            testId="reach-sites"
          />
          <Fact
            label="People per nearby site"
            note="2020 population divided by those sites"
            value={
              reach.peoplePerSite === null ? 'No site this close' : nf.format(reach.peoplePerSite)
            }
            testId="reach-people-per-site"
          />
        </dl>
        {driveTime}
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
