// Planner map MOCK-UP (layout and design only). Not app behaviour: the App in src/ is
// written after the CONTRACTS and RED phases. Data comes from stand-in files made by
// make-standin.mjs, not from the Build output (public/data/tracts.geojson).
//
// Module layout (one owner each, so tasks can run in parallel):
//   PlannerMock.tsx  app shell and data loading
//   model.ts         types, labels, number formats, candidate confidence rules
//   mapStyle.ts      map colors, line widths, hatch image (T8)
//   MapView.tsx      the map (T8)
//   Sidebar.tsx      the sidebar (T9)
//   TractCard.tsx    the tract card (T9)
//   compare/         "Compare with..." layers, one module per layer (T3 to T6)
import { useCallback, useEffect, useState } from 'react'
import { setWorkerUrl } from 'maplibre-gl'
import type { Map as MapLibre } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'
import './mockup.css'
import type { ConfRule, Coverage, Loaded } from './model'
import { MapView } from './MapView'
import { Sidebar } from './Sidebar'
import { TractCard } from './TractCard'
import { COMPARE_LAYERS } from './compare'
import type { CompareContext, CompareLayer } from './compare/types'

// MapLibre 6 looks for its worker next to its own module URL. Vite moves that module
// (to .vite/deps in dev, to assets/ in a build), so point it at the worker file directly.
setWorkerUrl(workerUrl)

const DATA_DIR = './data/'
const FILES = {
  records: 'records.standin.json',
  tracts: 'tracts.standin.geojson',
  counties: 'counties.standin.geojson',
  sites: 'sites.standin.geojson',
} as const

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
  const withData = COMPARE_LAYERS.filter((l) => l.dataFile)
  const [records, tracts, counties, sites, ...extraFiles] = await Promise.all([
    get(FILES.records),
    get(FILES.tracts),
    get(FILES.counties),
    get(FILES.sites),
    ...withData.map((l) => get(l.dataFile!)),
  ])
  const extras = Object.fromEntries(withData.map((l, i) => [l.id, extraFiles[i]]))
  return { records, tracts, counties, sites, extras }
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
  const [compareId, setCompareId] = useState<string | null>(null)
  const [map, setMap] = useState<MapLibre | null>(null)
  const compareCtx = useCallback(
    (layer: CompareLayer): CompareContext => ({
      records: data!.records,
      extra: data!.extras[layer.id],
      getMap: () => map,
    }),
    [data, map],
  )
  const activeCompare = COMPARE_LAYERS.find((l) => l.id === compareId)

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
            compareId={compareId}
            setCompareId={setCompareId}
            compareCtx={compareCtx}
          />
          <div className="map-col">
            <MapView
              data={data}
              selected={selected}
              onSelect={setSelected}
              coverageOn={coverageOn}
              coverage={coverage}
              sitesOn={sitesOn}
              onMap={setMap}
              compareId={compareId}
              compareCtx={compareCtx}
            />
            {tract && (
              <TractCard
                t={tract}
                r={data.records}
                confRule={confRule}
                onClose={() => setSelected(null)}
                compareLines={activeCompare?.cardLines?.(tract, compareCtx(activeCompare))}
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
