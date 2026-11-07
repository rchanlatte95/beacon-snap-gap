// Planner map MOCK-UP (layout and design only). Not app behaviour: the App in src/ is
// written after the CONTRACTS and RED phases. Data comes from stand-in files made by
// make-standin.mjs, not from the Build output (public/data/tracts.geojson).
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map as MapLibre, Marker, NavigationControl, Popup, setWorkerUrl } from 'maplibre-gl'
import type { ExpressionSpecification, LngLatBoundsLike, StyleSpecification } from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import './mockup.css'

// MapLibre 6 looks for its worker next to its own module URL. Vite moves that module
// (to .vite/deps in dev, to assets/ in a build), so point it at the worker file directly.
setWorkerUrl(workerUrl)

type Cls = 'desert' | 'nogap' | 'insufficient'
type Coverage = 'load' | 'reach'
type SortKey = 'poverty' | 'load' | 'snap'

interface Tract {
  geoid: string
  name: string
  county: string
  cls: Cls
  drawn: boolean
  households: number | null
  snapHouseholds: number | null
  pctSnap: number | null
  pctPoverty: number | null
  lilaDD: number | null
  urban: number | null
  medianFamilyIncome: number | null
  groupQuartersPct: number | null
  noVehiclePct: number | null
  placesFoodInsecurity: number | null
  nriRisk: string | null
  socialVulnerability: string | null
  pop2020: number
  sitesInTract: number
  standinReachPct: number | null
  standinSitesInReach: number
  standinLoad: number | null
  missing: string[]
  centroid: [number, number] | null
}

interface Records {
  generated: string
  povertyCut: { value: number; method: string; tracts: number }
  standinReachMiles: number
  counts: Record<Cls, number>
  countyLabels: { name: string; lngLat: [number, number] }[]
  snapTrend: { month: string; participants: number | null }[]
  mealGap: { county: string; rate: string; people: number | null }[]
  tracts: Tract[]
}

interface Loaded {
  records: Records
  tracts: FeatureCollection
  counties: FeatureCollection
  sites: FeatureCollection
}

const CLASS_LABEL: Record<Cls, string> = {
  desert: 'Classic Food Desert (high need)',
  nogap: 'No gap flagged',
  insufficient: 'Insufficient data',
}
const COLORS = {
  desert: '#F79122',
  nogap: '#DFE7EE',
  primary900: '#1E343F',
  primary700: '#385981',
  primary500: '#6B8FA8',
}
const NO_SITE_TEXT = 'No Second Harvest site found under this rule. Other food sources may exist.'
const DATA_DIR = './data/'
const FILES = {
  records: 'records.standin.json',
  tracts: 'tracts.standin.geojson',
  counties: 'counties.standin.geojson',
  sites: 'sites.standin.geojson',
} as const

const fmt = new Intl.NumberFormat('en-US')
const pct = (v: number | null) => (v === null ? 'blank' : `${v.toFixed(1)}%`)
const n = (v: number | null) => (v === null ? 'blank' : fmt.format(v))
const featureId = (geoid: string) => Number(geoid.slice(2))

// REQ-7: a missing or unparsable file names the file and no map is drawn.
async function loadAll(): Promise<Loaded> {
  const get = async (file: string) => {
    let res: Response
    try {
      res = await fetch(DATA_DIR + file)
    } catch {
      throw new Error(file)
    }
    if (!res.ok) throw new Error(file)
    try {
      return await res.json()
    } catch {
      throw new Error(file)
    }
  }
  const [records, tracts, counties, sites] = await Promise.all([
    get(FILES.records),
    get(FILES.tracts),
    get(FILES.counties),
    get(FILES.sites),
  ])
  return { records, tracts, counties, sites }
}

// Confidence: three candidate rules to compare. None is decided; a human picks one
// before any rule goes in a contract. The thresholds below are stand-ins.
type ConfRule = 'size' | 'near' | 'count'
type ConfLevel = 'High' | 'Medium' | 'Low' | 'Not rated'
const CONF_LEVELS: ConfLevel[] = ['High', 'Medium', 'Low', 'Not rated']
const SMALL_HOUSEHOLDS = 500
const GROUP_QUARTERS_PCT = 20
const NEAR_CUT_POINTS = 2
const CONF_RULES: { id: ConfRule; name: string; summary: string }[] = [
  {
    id: 'size',
    name: 'A. Size and group quarters',
    summary: `Low if under ${SMALL_HOUSEHOLDS} households or over ${GROUP_QUARTERS_PCT}% group quarters, else Medium.`,
  },
  {
    id: 'near',
    name: 'B. Near the cut',
    summary: `Low if the tract is LILA and its poverty rate is within ${NEAR_CUT_POINTS} points of the cut, else Medium.`,
  },
  {
    id: 'count',
    name: 'C. Count of limits',
    summary: 'Counts the A and B tests: none is High, one is Medium, two or more is Low.',
  },
]
const NO_MOE =
  'ACS 5-year margins of error are not in the repo for the poverty rate, so no rule checks them.'

function limits(t: Tract, cut: number): { size: string[]; near: string[] } {
  const size: string[] = []
  const near: string[] = []
  if ((t.households ?? 0) < SMALL_HOUSEHOLDS)
    size.push(`Fewer than ${SMALL_HOUSEHOLDS} households, so ACS estimates are less stable.`)
  if ((t.groupQuartersPct ?? 0) > GROUP_QUARTERS_PCT)
    size.push(
      `${t.groupQuartersPct?.toFixed(0)}% of residents live in group quarters (for example dorms), which ACS household rates leave out.`,
    )
  if (t.lilaDD === 1 && t.pctPoverty !== null && Math.abs(t.pctPoverty - cut) < NEAR_CUT_POINTS)
    near.push(
      `The poverty rate (${t.pctPoverty.toFixed(1)}%) is within ${NEAR_CUT_POINTS} points of the ${cut.toFixed(3)}% cut, so a small change in the estimate could change the class.`,
    )
  return { size, near }
}

function confidence(t: Tract, cut: number, rule: ConfRule): { level: ConfLevel; why: string[] } {
  if (t.cls === 'insufficient')
    return { level: 'Not rated', why: ['A core indicator is blank, so no class is computed.'] }
  const l = limits(t, cut)
  if (rule === 'count') {
    const all = [...l.size, ...l.near]
    const level = all.length === 0 ? 'High' : all.length === 1 ? 'Medium' : 'Low'
    return { level, why: all.length ? all : ['No limit found by the A or B tests.', NO_MOE] }
  }
  const hits = rule === 'size' ? l.size : l.near
  if (hits.length) return { level: 'Low', why: hits }
  return {
    level: 'Medium',
    why: [`No limit found by this rule. ${NO_MOE} The label stays below High for that reason.`],
  }
}

function bbox(fc: FeatureCollection): LngLatBoundsLike {
  let [w, s, e, nn] = [180, 90, -180, -90]
  const visit = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number') {
      const [x, y] = c as number[]
      if (x === undefined || y === undefined) return
      w = Math.min(w, x)
      e = Math.max(e, x)
      s = Math.min(s, y)
      nn = Math.max(nn, y)
    } else if (Array.isArray(c)) c.forEach(visit)
  }
  for (const f of fc.features) if (f.geometry.type !== 'GeometryCollection') visit(f.geometry.coordinates)
  return [
    [w, s],
    [e, nn],
  ]
}

function hatchImage() {
  const size = 8
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const on = (x + y) % size === 0 || (x + y) % size === 1
      const i = (y * size + x) * 4
      data.set(on ? [123, 135, 148, 255] : [255, 255, 255, 255], i)
    }
  return { width: size, height: size, data }
}

const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#F3F5F7' } }],
}

// ---------------- Map ----------------

function MapView(props: {
  data: Loaded
  selected: string | null
  onSelect: (geoid: string | null) => void
  coverageOn: boolean
  coverage: Coverage
  sitesOn: boolean
}) {
  const { data, selected, onSelect, coverageOn, coverage, sitesOn } = props
  const el = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibre | null>(null)
  const [ready, setReady] = useState(false)
  const [hover, setHover] = useState<{ x: number; y: number; geoid: string } | null>(null)
  const byId = useMemo(
    () => new Map(data.records.tracts.map((t) => [t.geoid, t])),
    [data.records.tracts],
  )
  const selectRef = useRef(onSelect)
  useEffect(() => {
    selectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    if (!el.current) return
    const map = new MapLibre({
      container: el.current,
      style: BLANK_STYLE,
      bounds: bbox(data.tracts),
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      dragRotate: false,
    })
    mapRef.current = map
    map.addControl(new NavigationControl({ showCompass: false }), 'top-left')

    map.on('load', () => {
      map.addImage('hatch', hatchImage(), { pixelRatio: 2 })
      map.addSource('tracts', { type: 'geojson', data: data.tracts })
      map.addSource('counties', { type: 'geojson', data: data.counties })
      map.addSource('sites', { type: 'geojson', data: data.sites })
      map.addSource('coverage', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: data.records.tracts
            .filter((t) => t.cls === 'desert' && t.centroid)
            .map((t) => ({
              type: 'Feature',
              properties: { geoid: t.geoid, load: t.standinLoad ?? 0, reach: t.standinReachPct ?? 0 },
              geometry: { type: 'Point', coordinates: t.centroid as [number, number] },
            })),
        },
      })
      map.addLayer({
        id: 'tract-fill',
        type: 'fill',
        source: 'tracts',
        filter: ['!=', ['get', 'cls'], 'insufficient'],
        paint: {
          'fill-color': ['match', ['get', 'cls'], 'desert', COLORS.desert, COLORS.nogap],
          'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.8, 1],
        },
      })
      map.addLayer({
        id: 'tract-insufficient',
        type: 'fill',
        source: 'tracts',
        filter: ['==', ['get', 'cls'], 'insufficient'],
        paint: { 'fill-pattern': 'hatch' },
      })
      map.addLayer({
        id: 'tract-line',
        type: 'line',
        source: 'tracts',
        paint: { 'line-color': '#FFFFFF', 'line-width': 0.6 },
      })
      map.addLayer({
        id: 'county-line',
        type: 'line',
        source: 'counties',
        paint: { 'line-color': COLORS.primary700, 'line-width': 1.6 },
      })
      map.addLayer({
        id: 'tract-selected',
        type: 'line',
        source: 'tracts',
        paint: {
          'line-color': COLORS.primary900,
          'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3, 0],
        },
      })
      map.addLayer({
        id: 'coverage',
        type: 'circle',
        source: 'coverage',
        paint: {
          'circle-color': COLORS.primary900,
          'circle-radius': 6,
          'circle-stroke-color': COLORS.primary900,
          'circle-stroke-width': 1.5,
          'circle-opacity': 0.4,
        },
      })
      map.addLayer({
        id: 'sites',
        type: 'circle',
        source: 'sites',
        layout: { visibility: 'none' },
        paint: {
          'circle-color': '#FFFFFF',
          'circle-radius': 3.2,
          'circle-stroke-color': COLORS.primary900,
          'circle-stroke-width': 1.4,
        },
      })

      for (const c of data.records.countyLabels) {
        const div = document.createElement('div')
        div.className = 'county-label'
        div.textContent = c.name
        new Marker({ element: div }).setLngLat(c.lngLat).addTo(map)
      }

      let hovered: number | null = null
      const clearHover = () => {
        if (hovered !== null) map.setFeatureState({ source: 'tracts', id: hovered }, { hover: false })
        hovered = null
      }
      for (const layer of ['tract-fill', 'tract-insufficient']) {
        map.on('mousemove', layer, (e) => {
          const f = e.features?.[0]
          if (!f || typeof f.id !== 'number') return
          if (hovered !== f.id) {
            clearHover()
            hovered = f.id
            map.setFeatureState({ source: 'tracts', id: hovered }, { hover: true })
          }
          map.getCanvas().style.cursor = 'pointer'
          setHover({ x: e.point.x, y: e.point.y, geoid: String(f.properties.geoid) })
        })
        map.on('mouseleave', layer, () => {
          clearHover()
          map.getCanvas().style.cursor = ''
          setHover(null)
        })
      }

      map.on('click', (e) => {
        const site = map.queryRenderedFeatures(e.point, { layers: ['sites'] })[0]
        if (site && site.geometry.type === 'Point') {
          const box = document.createElement('div')
          const [title, addr, hours] = ['strong', 'div', 'div'].map((t) => document.createElement(t))
          title!.textContent = String(site.properties.name)
          addr!.textContent = String(site.properties.address)
          hours!.textContent = String(site.properties.hours)
          hours!.className = 'secondary'
          box.append(title!, addr!, hours!)
          new Popup({ maxWidth: '280px' })
            .setLngLat(site.geometry.coordinates as [number, number])
            .setDOMContent(box)
            .addTo(map)
          return
        }
        const tract = map.queryRenderedFeatures(e.point, {
          layers: ['tract-fill', 'tract-insufficient'],
        })[0]
        selectRef.current(tract ? String(tract.properties.geoid) : null)
      })
      setReady(true)
    })
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [data])

  // Selected outline and camera.
  const prevSelected = useRef<string | null>(null)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (prevSelected.current)
      map.setFeatureState(
        { source: 'tracts', id: featureId(prevSelected.current) },
        { selected: false },
      )
    prevSelected.current = selected
    if (!selected) return
    map.setFeatureState({ source: 'tracts', id: featureId(selected) }, { selected: true })
    const c = byId.get(selected)?.centroid
    if (!c) return
    // Urban tracts are small at the overview zoom; zoom in and keep the tract clear of the card.
    const narrow = window.innerWidth <= 860
    map.easeTo({
      center: c,
      zoom: Math.max(map.getZoom(), 11),
      offset: narrow ? [0, -120] : [-200, 0],
      duration: 700,
    })
  }, [selected, ready, byId])

  // Layer toggles and coverage encoding.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.setLayoutProperty('coverage', 'visibility', coverageOn ? 'visible' : 'none')
    map.setLayoutProperty('sites', 'visibility', sitesOn ? 'visible' : 'none')
    const radius: ExpressionSpecification | number =
      coverage === 'load' ? ['max', 3, ['*', 0.55, ['sqrt', ['get', 'load']]]] : 6
    const color: ExpressionSpecification | string =
      coverage === 'reach'
        ? ['step', ['get', 'reach'], COLORS.primary500, 50, COLORS.primary700, 90, COLORS.primary900]
        : COLORS.primary900
    map.setPaintProperty('coverage', 'circle-radius', radius)
    map.setPaintProperty('coverage', 'circle-color', color)
  }, [coverageOn, coverage, sitesOn, ready])

  const hoverTract = hover ? byId.get(hover.geoid) : undefined
  return (
    <div className="map-wrap">
      <div ref={el} className="map" aria-label="Map of Central Florida census tracts" />
      {/* REQ-10 fallback: no tile source is chosen (Z-6), so tracts sit on a blank background. */}
      <div className="map-badge">Base map unavailable (tile source not chosen, Z-6)</div>
      {hover && hoverTract && (
        <div className="hover-tip" style={{ left: hover.x, top: hover.y }}>
          {hoverTract.name}, {hoverTract.county}: {CLASS_LABEL[hoverTract.cls]}
        </div>
      )}
    </div>
  )
}

// ---------------- Tract card ----------------

function TractCard(props: { t: Tract; r: Records; confRule: ConfRule; onClose: () => void }) {
  const { t, r, confRule, onClose } = props
  const cut = r.povertyCut.value
  const povertyMet = t.pctPoverty !== null && t.pctPoverty >= cut
  const lilaMet = t.lilaDD === 1
  const conf = confidence(t, cut, confRule)
  const ruleName = CONF_RULES.find((c) => c.id === confRule)!.name
  const noSite = t.sitesInTract === 0 || t.standinReachPct === 0
  // The two class inputs (POST-CLS-2). Other blanks are listed under Missing indicators.
  const core = t.missing.filter((m) => /S1701|SRAM/.test(m))
  return (
    <aside className="card" aria-label={`Tract card for ${t.name}`}>
      <div className="card-head">
        <div>
          <h3>{t.name}</h3>
          <div className="secondary">
            {t.county} County · <span className="mono">{t.geoid}</span>
            {!t.drawn && ' · not drawn (water, no shape)'}
          </div>
        </div>
        <button className="close" onClick={onClose} aria-label="Close tract card">
          ×
        </button>
      </div>
      <div className="class-badge">
        <span className={`swatch ${t.cls}`} />
        {CLASS_LABEL[t.cls]}
      </div>

      <section>
        <h4>Why this class</h4>
        {t.cls === 'insufficient' ? (
          <p className="rule">
            Insufficient data: {core.join(', ') || 'a core indicator'} is blank in the source. This
            is not a low-need result.
          </p>
        ) : (
          <>
            <dl className="facts">
              <dt>Poverty rate (top quartile is {cut.toFixed(3)}% or more)</dt>
              <dd>
                {pct(t.pctPoverty)}{' '}
                <span className={`check ${povertyMet ? 'yes' : 'no'}`}>
                  {povertyMet ? 'meets' : 'below'}
                </span>
              </dd>
              <dt>Low income and low access, driving distance (½ mi urban, 10 mi rural)</dt>
              <dd>
                <span className={`check ${lilaMet ? 'yes' : 'no'}`}>
                  {lilaMet ? 'Yes' : 'No'}
                </span>
              </dd>
            </dl>
            <p className="rule">
              Classic Food Desert needs both. Cut: 75th percentile of {r.povertyCut.tracts} tracts (
              {r.povertyCut.method}).
            </p>
          </>
        )}
      </section>

      <section>
        <h4>Pantry coverage</h4>
        <dl className="facts">
          <dt>Second Harvest sites inside the tract</dt>
          <dd>{t.sitesInTract}</dd>
          <dt>
            Residents within reach of a site <span className="standin">stand-in</span>
          </dt>
          <dd>{pct(t.standinReachPct)}</dd>
          <dt>
            Load: residents per site within reach <span className="standin">stand-in</span>
          </dt>
          <dd>{n(t.standinLoad)}</dd>
        </dl>
        {noSite && <p className="callout">{NO_SITE_TEXT}</p>}
        <p className="rule">
          Stand-in reach is {r.standinReachMiles} miles straight-line from each populated 2020 block.
          The decided rule is a 30-minute drive (Z-2d), which needs routing data that is not in the
          repo yet. Sites are Second Harvest partner sites only; other pantries and stores are not
          in the list, and hours change.
        </p>
      </section>

      <section>
        <h4>Context (not used in the class)</h4>
        <dl className="facts">
          <dt>Households on SNAP</dt>
          <dd>
            {pct(t.pctSnap)} ({n(t.snapHouseholds)} of {n(t.households)})
          </dd>
          <dt>No-vehicle households (proxy, not validated)</dt>
          <dd>{pct(t.noVehiclePct)}</dd>
          <dt>Population, 2020 (tract sum)</dt>
          <dd>{n(t.pop2020)}</dd>
          <dt>Area type (USDA)</dt>
          <dd>{t.urban === null ? 'blank' : t.urban === 1 ? 'Urban' : 'Rural'}</dd>
          <dt>FEMA risk / social vulnerability</dt>
          <dd>
            {t.nriRisk ?? 'blank'} / {t.socialVulnerability ?? 'blank'}
          </dd>
        </dl>
      </section>

      <section className="confidence">
        <h4>Confidence</h4>
        <div>
          <strong>{conf.level}</strong> under rule {ruleName}{' '}
          <span className="standin">rule not decided</span>
        </div>
        <ul className="conf-why">
          {conf.why.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </section>

      <section>
        <h4>Missing indicators ({t.missing.length})</h4>
        {t.missing.length === 0 ? (
          <p className="rule">None.</p>
        ) : (
          <ul className="missing">
            {t.missing.map((m) => (
              <li key={m}>
                {m}: blank in the source
                {m.includes('CDC PLACES') && ' (blank for all of Florida, finding F-1)'}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sources">
        Sources: ACS 2024 5-year S1701 (DS-H2), S2201 (DS-H1), B08201 (DS-X7b); USDA 2025 SRAM
        (DS-H6); Second Harvest food finder (DS-X12); Census 2020 blocks (DS-X24); FEMA NRI
        (DS-X16b); CDC PLACES 2025 (DS-H7).
      </section>
    </aside>
  )
}

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

function Sidebar(props: {
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

// ---------------- App shell ----------------

export function MockApp() {
  const [data, setData] = useState<Loaded | null>(null)
  const [failedFile, setFailedFile] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [coverageOn, setCoverageOn] = useState(true)
  const [coverage, setCoverage] = useState<Coverage>('load')
  const [sitesOn, setSitesOn] = useState(false)
  const [confRule, setConfRule] = useState<ConfRule>('size')

  useEffect(() => {
    loadAll().then(setData, (e: Error) => setFailedFile(e.message))
  }, [])

  const tract = data && selected ? data.records.tracts.find((t) => t.geoid === selected) : undefined

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-mark">Beacon</span>
          <span className="brand-title">SNAP-cliff planner map · Central Florida</span>
        </div>
        <nav className="tabs" aria-label="Views">
          <button className="tab" aria-selected="true">
            Food bank planner
          </button>
          <button className="tab" disabled title="Later slice">
            SBDC / CDFI officer
          </button>
        </nav>
        <span className="mock-badge">Mock-up · stand-in data</span>
      </header>

      {failedFile ? (
        <div className="load-error" role="alert">
          <h2>The map data did not load</h2>
          <p>
            The file <span className="mono">{failedFile}</span> is missing or does not parse, so no
            map is drawn. Run <span className="mono">node docs/mockups/planner-map/make-standin.mjs</span>
            .
          </p>
        </div>
      ) : !data ? (
        <div className="load-error" style={{ background: '#fff', borderColor: '#cbd2d9' }}>
          Loading stand-in data…
        </div>
      ) : (
        <main className="main">
          <Sidebar
            r={data.records}
            selected={selected}
            onSelect={setSelected}
            coverageOn={coverageOn}
            setCoverageOn={setCoverageOn}
            coverage={coverage}
            setCoverage={setCoverage}
            sitesOn={sitesOn}
            setSitesOn={setSitesOn}
            siteCount={data.sites.features.length}
            confRule={confRule}
            setConfRule={setConfRule}
          />
          <div className="map-col">
            <MapView
              data={data}
              selected={selected}
              onSelect={setSelected}
              coverageOn={coverageOn}
              coverage={coverage}
              sitesOn={sitesOn}
            />
            {tract && (
              <TractCard
                t={tract}
                r={data.records}
                confRule={confRule}
                onClose={() => setSelected(null)}
              />
            )}
          </div>
        </main>
      )}

      <footer className="footer">
        <span>
          Indicators from DataKind's Beacon. Beacon content is CC BY 4.0. Credit:{' '}
          <a href="http://www.datakind.org" target="_blank" rel="noreferrer">
            DataKind and Beacon (www.datakind.org)
          </a>
          .
        </span>
        <span>Map drawn with MapLibre GL JS. DevFest Florida 2026, Beacon track.</span>
      </footer>
    </div>
  )
}
