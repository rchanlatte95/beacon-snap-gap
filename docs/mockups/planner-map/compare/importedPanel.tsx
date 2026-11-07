// Sidebar panel for the "Your own data" Compare-with layer (imported.ts). Owner: T6.
// Reads the user's file in the browser: no network call, no upload, no browser storage.
import { useEffect, useState, useSyncExternalStore } from 'react'
import type { ChangeEvent } from 'react'
import { COLORS } from '../mapStyle'
import type { CompareContext } from './types'
import {
  ImportError,
  MAX_FILE_BYTES,
  blankRowsLine,
  formatValue,
  readCsv,
  readPoints,
  tractShapes,
} from './importedParse'
import type { ImportResult } from './importedParse'
import {
  NO_VALUE,
  SOURCES,
  buildView,
  drawOnMap,
  getLoaded,
  kindOf,
  setLoaded,
  subscribe,
  tractFeatures,
} from './importedStore'
import sampleCsv from './samples/SAMPLE-census-median-household-income.csv?raw'
import samplePoints from './samples/SAMPLE-second-harvest-sites-subset.geojson?raw'
import './imported.css'

const SAMPLES = [
  {
    name: 'SAMPLE-census-median-household-income.csv',
    text: sampleCsv,
    label: 'Census income by neighborhood (CSV)',
  },
  {
    name: 'SAMPLE-second-harvest-sites-subset.geojson',
    text: samplePoints,
    label: 'Some Second Harvest sites (points)',
  },
]

// ---------------- Panel ----------------

export function ImportedPanel({ ctx }: { ctx: CompareContext }) {
  const state = useSyncExternalStore(subscribe, getLoaded)
  const [error, setError] = useState<{ file: string; message: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const map = ctx.getMap()
  const view = state ? buildView(state, ctx.records) : null

  useEffect(() => {
    if (!map) return
    drawOnMap(map, view).catch(() =>
      setError({
        file: state?.result.fileName ?? '',
        message: 'We could not draw your file on the map.',
      }),
    )
    // view is rebuilt from state on every render; state and the map are what change it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, state])

  async function load(name: string, text: string) {
    setBusy(true)
    setError(null)
    try {
      let result: ImportResult
      if (kindOf(name, text) === 'csv') {
        result = readCsv(name, text, new Set(ctx.records.tracts.map((t) => t.geoid)))
      } else {
        const m = ctx.getMap()
        if (!m) throw new ImportError('The map is not ready yet. Try again in a moment.')
        result = readPoints(name, text, tractShapes(await tractFeatures(m)))
      }
      setLoaded({ result, measureIdx: 0 })
    } catch (e) {
      setLoaded(null)
      setError({
        file: name,
        message:
          e instanceof ImportError
            ? e.message
            : 'We could not read this file. Use a CSV file or a GeoJSON file.',
      })
    } finally {
      setBusy(false)
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > MAX_FILE_BYTES) {
      setLoaded(null)
      setError({ file: file.name, message: 'This file is larger than 25 MB. Use a smaller file.' })
      return
    }
    let text: string
    try {
      text = await file.text()
    } catch {
      setLoaded(null)
      setError({ file: file.name, message: 'Your browser could not open this file.' })
      return
    }
    await load(file.name, text)
  }

  const blankLine = view ? blankRowsLine(view.measure) : null
  return (
    <div className="imp">
      <p className="imp-private">
        <strong>Your file stays on your computer.</strong> We do not upload it or save it. It is
        gone when you reload the page.
      </p>

      <label className="imp-pick">
        <span>Choose a file (CSV or GeoJSON)</span>
        <input
          type="file"
          accept=".csv,.geojson,.json,text/csv,application/geo+json,application/json"
          onChange={onFile}
          disabled={busy}
          data-testid="imported-file"
        />
      </label>
      <div className="imp-samples">
        <span className="secondary">
          Or try a sample file. Samples use public data. They are not partner data.
        </span>
        {SAMPLES.map((s) => (
          <button
            key={s.name}
            className="linklike"
            onClick={() => load(s.name, s.text)}
            disabled={busy}
          >
            {s.label}
          </button>
        ))}
      </div>

      {busy && <p className="secondary">Reading your file…</p>}

      {error && (
        <div className="imp-error" role="alert">
          <strong>We could not use {error.file || 'this file'}.</strong> {error.message}
        </div>
      )}

      {state && (
        <div className="imp-result">
          <div className="imp-file">
            <span>
              Showing <strong>{state.result.fileName}</strong>
            </span>
            <button className="linklike" onClick={() => setLoaded(null)}>
              Remove file
            </button>
          </div>

          {state.result.measures.length > 1 && (
            <label className="imp-col">
              <span>Number to show</span>
              <select
                value={state.measureIdx}
                onChange={(e) => setLoaded({ ...state, measureIdx: Number(e.target.value) })}
              >
                {state.result.measures.map((m, i) => (
                  <option key={m.label + i} value={i}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          {view ? (
            <>
              <p className="imp-headline">{view.comparison}</p>
              {view.secondary && <p className="secondary">{view.secondary}</p>}

              <div className="imp-legend" aria-label="Map key for your file">
                <div className="imp-legend-title">{view.measure.label}</div>
                <ul className="imp-ramp">
                  {view.labels.map((l, i) => (
                    <li key={l}>
                      <span className="imp-swatch" style={{ background: view.colors[i] }} />
                      <span>{l}</span>
                    </li>
                  ))}
                </ul>
                <ul className="imp-keys">
                  {state.result.kind === 'csv' && (
                    <li>
                      <span className="imp-swatch" style={{ background: NO_VALUE }} />
                      No value in your file
                    </li>
                  )}
                  <li>
                    <span
                      className="imp-swatch imp-outline"
                      style={{ borderColor: COLORS.desert }}
                    />
                    High-need neighborhood
                  </li>
                </ul>
              </div>
            </>
          ) : (
            <p className="imp-error" role="alert">
              No neighborhood has a number in {state.result.measures[state.measureIdx]?.label}. Pick
              another column.
            </p>
          )}

          <ul className="imp-status" aria-label="What we found in your file">
            {state.result.status.map((s) => (
              <li key={s}>{s}</li>
            ))}
            {blankLine && <li>{blankLine}</li>}
          </ul>
        </div>
      )}

      <details className="how-we-know">
        <summary>How we know this</summary>
        <p>
          <strong>Your file is not checked by us.</strong> The page reads it with the browser File
          API. It makes no network request and writes nothing to localStorage, IndexedDB or cookies.
          The values stay in page memory until you remove the file or reload.
        </p>
        <p>
          <strong>CSV.</strong> One row per census tract. The tract column is named geoid, tract or
          tract_geoid (any case) and holds the 11-digit 2020 tract GEOID (state 12, county 069, 095,
          097 or 117, then 6 digits). A Census prefix such as 1400000US is allowed. A number column
          is any other column where at least 4 in 5 filled cells are numbers; $ , and % are removed.
          If a tract appears twice, the first row is used.
        </p>
        <p>
          <strong>GeoJSON.</strong> Point or MultiPoint features in longitude and latitude (WGS84).
          Each point is matched to a drawn tract shape with a point-in-polygon test in the browser.
          Only the count per tract is kept; the points are not drawn and not kept. A point exactly
          on a tract line can go to either tract. Tract {'12095990000'} (water) has no shape, so no
          point can fall in it.
        </p>
        {view && (
          <>
            <p>
              <strong>Colors.</strong> Cut points are the quartiles (25th, 50th and 75th
              percentiles) of the {view.measure.values.size} values in your file that matched a
              tract: {view.cuts.map(formatValue).join(', ') || 'none'}. Repeated cut points are
              merged, so a file with few distinct values gets fewer than 4 colors.
            </p>
            <p>
              <strong>Comparison.</strong> {view.method} It describes the middle values in your file
              only. It does not show cause, and it is not a statistical test.
            </p>
          </>
        )}
        <p>
          <strong>Sample files.</strong> They are made by{' '}
          <span className="mono">compare/samples/make-samples.mjs</span>. The CSV is tract median
          household income from Census ACS 2020-2024 table S1901 (DS-H3; extract checked against
          B19013, DS-X28). Four tracts have no published number, so they show how blank rows are
          reported. The points are every 10th Second Harvest food finder site (DS-X12), so some fall
          outside the four counties. Redistribution permission for the Second Harvest data was not
          obtained; the data is already public.
        </p>
        <ul>
          {SOURCES.map((s) => (
            <li key={s.id}>
              <span className="mono">{s.id}</span>: {s.label}
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
