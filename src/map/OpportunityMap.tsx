import { useEffect, useRef, useState } from 'react'
import { Map as MapLibre, NavigationControl, setWorkerUrl } from 'maplibre-gl'
import type { ExpressionSpecification, LngLatBoundsLike, StyleSpecification } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'

import type { CohortId, TractRecord } from '../wizard/alignmentWizard'
import { CLASS_HIGH_NEED, CLASS_INSUFFICIENT } from '../wizard/alignmentWizard'

// MapLibre 6 resolves its worker next to its own module URL; Vite relocates the module.
setWorkerUrl(workerUrl)

import { BASE_MAP_UNAVAILABLE_TEXT, COLORS, OPENFREEMAP_STYLE_URL } from './mapConstants'

const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#EEF2F5' } }],
}

const CENTRAL_FL_BOUNDS: LngLatBoundsLike = [
  [-81.98, 27.62],
  [-80.84, 29.3],
]

function hatchImage() {
  const size = 8
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const on = (x + y) % size === 0 || (x + y) % size === 1
      const i = (y * size + x) * 4
      data.set(on ? [107, 143, 168, 255] : [255, 255, 255, 255], i)
    }
  }
  return { width: size, height: size, data }
}

export interface OpportunityMapProps {
  readonly tractsGeojson: GeoJSON.FeatureCollection
  readonly countiesGeojson: GeoJSON.FeatureCollection
  readonly sitesGeojson: GeoJSON.FeatureCollection
  readonly records: readonly TractRecord[]
  readonly cohortId: CohortId
  readonly selectedGeoid: string | null
  readonly onSelect: (geoid: string | null) => void
  readonly overlays: {
    readonly sba: boolean
    readonly transport: boolean
    readonly sites: boolean
  }
}

function cohortFilter(cohortId: CohortId): ExpressionSpecification | null {
  switch (cohortId) {
    case 'all':
      return null
    case 'triple':
      return ['==', ['get', 'is_triple_gap'], true]
    case 'high_need':
      return ['==', ['get', 'tract_class'], CLASS_HIGH_NEED]
    case 'dual':
      return ['==', ['get', 'is_dual_gap'], true]
    case 'transport':
      return ['==', ['get', 'is_transport_gap'], true]
    case 'insufficient':
      return ['==', ['get', 'tract_class'], CLASS_INSUFFICIENT]
    default: {
      const exhaustive: never = cohortId
      return exhaustive
    }
  }
}

export function OpportunityMap(props: OpportunityMapProps) {
  const {
    tractsGeojson,
    countiesGeojson,
    sitesGeojson,
    records,
    cohortId,
    selectedGeoid,
    onSelect,
    overlays,
  } = props
  const el = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibre | null>(null)
  const [ready, setReady] = useState(false)
  const [tilesFailed, setTilesFailed] = useState(false)
  const selectRef = useRef(onSelect)
  useEffect(() => {
    selectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    if (!el.current) return
    const map = new MapLibre({
      container: el.current,
      style: OPENFREEMAP_STYLE_URL,
      bounds: CENTRAL_FL_BOUNDS,
      fitBoundsOptions: { padding: 28 },
      attributionControl: { compact: true },
      dragRotate: false,
    })
    mapRef.current = map
    map.addControl(new NavigationControl({ showCompass: false }), 'top-left')

    let fellBack = false
    const fallback = () => {
      if (fellBack) return
      fellBack = true
      setTilesFailed(true)
      map.setStyle(BLANK_STYLE)
    }
    map.on('error', (e) => {
      const err: unknown = e.error
      const msg =
        err && typeof err === 'object' && 'message' in err && typeof err.message === 'string'
          ? err.message
          : ''
      if (/style|tile|fetch|network|Failed/i.test(msg) && !map.getSource('tracts')) fallback()
    })

    const addLayers = () => {
      if (map.getSource('tracts')) return
      if (!map.hasImage('hatch')) map.addImage('hatch', hatchImage(), { pixelRatio: 2 })
      map.addSource('tracts', { type: 'geojson', data: tractsGeojson })
      map.addSource('counties', { type: 'geojson', data: countiesGeojson })
      map.addSource('sites', { type: 'geojson', data: sitesGeojson })
      const firstSymbol = map.getStyle().layers?.find((l) => l.type === 'symbol')?.id

      map.addLayer(
        {
          id: 'tract-fill',
          type: 'fill',
          source: 'tracts',
          filter: ['!=', ['get', 'tract_class'], CLASS_INSUFFICIENT],
          paint: {
            'fill-color': [
              'case',
              ['==', ['get', 'is_triple_gap'], true],
              COLORS.triple,
              ['==', ['get', 'tract_class'], CLASS_HIGH_NEED],
              COLORS.highNeed,
              COLORS.noGap,
            ],
            'fill-opacity': [
              'case',
              ['boolean', ['feature-state', 'dimmed'], false],
              0.18,
              ['boolean', ['feature-state', 'hover'], false],
              0.95,
              0.82,
            ],
          },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'tract-insufficient',
          type: 'fill',
          source: 'tracts',
          filter: ['==', ['get', 'tract_class'], CLASS_INSUFFICIENT],
          paint: { 'fill-pattern': 'hatch', 'fill-opacity': 0.9 },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'tract-line',
          type: 'line',
          source: 'tracts',
          paint: { 'line-color': '#FFFFFF', 'line-width': 0.5, 'line-opacity': 0.9 },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'sba-gap-outline',
          type: 'line',
          source: 'tracts',
          filter: ['==', ['get', 'is_dual_gap'], true],
          layout: { visibility: 'none' },
          paint: { 'line-color': COLORS.ink, 'line-width': 1.6, 'line-dasharray': [1.5, 1] },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'transport-gap-fill',
          type: 'fill',
          source: 'tracts',
          filter: ['==', ['get', 'is_transport_gap'], true],
          layout: { visibility: 'none' },
          paint: { 'fill-pattern': 'hatch', 'fill-opacity': 0.55 },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'county-line',
          type: 'line',
          source: 'counties',
          paint: { 'line-color': COLORS.ink, 'line-width': 2, 'line-opacity': 0.85 },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'tract-selected',
          type: 'line',
          source: 'tracts',
          paint: {
            'line-color': COLORS.ink,
            'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3.2, 0],
          },
        },
        firstSymbol,
      )
      map.addLayer({
        id: 'sites',
        type: 'circle',
        source: 'sites',
        minzoom: 9,
        layout: { visibility: 'none' },
        paint: {
          'circle-color': '#FFFFFF',
          'circle-radius': 3.4,
          'circle-stroke-color': COLORS.mid,
          'circle-stroke-width': 1.4,
        },
      })

      let hovered: number | null = null
      const clearHover = () => {
        if (hovered !== null)
          map.setFeatureState({ source: 'tracts', id: hovered }, { hover: false })
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
        })
        map.on('mouseleave', layer, () => {
          clearHover()
          map.getCanvas().style.cursor = ''
        })
      }
      map.on('click', (e) => {
        const f = map.queryRenderedFeatures(e.point, {
          layers: ['tract-fill', 'tract-insufficient'],
        })[0]
        selectRef.current(f ? String(f.properties.geoid) : null)
      })
      setReady(true)
    }

    map.on('load', addLayers)
    map.on('style.load', () => {
      if (fellBack) addLayers()
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [tractsGeojson, countiesGeojson, sitesGeojson])

  // Cohort dimming
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const filter = cohortFilter(cohortId)
    const include = new Set<string>()
    if (filter) {
      for (const r of records) {
        const inCohort =
          cohortId === 'triple'
            ? r.is_triple_gap
            : cohortId === 'high_need'
              ? r.tract_class === CLASS_HIGH_NEED
              : cohortId === 'dual'
                ? r.is_dual_gap
                : cohortId === 'transport'
                  ? r.is_transport_gap
                  : r.tract_class === CLASS_INSUFFICIENT
        if (inCohort) include.add(r.geoid)
      }
    }
    for (const r of records) {
      if (!r.drawn) continue
      map.setFeatureState(
        { source: 'tracts', id: Number(r.geoid.slice(2)) },
        { dimmed: filter !== null && !include.has(r.geoid) },
      )
    }
  }, [cohortId, records, ready])

  // Overlay toggles
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    map.setLayoutProperty('sba-gap-outline', 'visibility', overlays.sba ? 'visible' : 'none')
    map.setLayoutProperty(
      'transport-gap-fill',
      'visibility',
      overlays.transport ? 'visible' : 'none',
    )
    map.setLayoutProperty('sites', 'visibility', overlays.sites ? 'visible' : 'none')
  }, [overlays, ready])

  // Selection outline and camera
  const prev = useRef<string | null>(null)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    if (prev.current)
      map.setFeatureState(
        { source: 'tracts', id: Number(prev.current.slice(2)) },
        { selected: false },
      )
    prev.current = selectedGeoid
    if (!selectedGeoid) return
    map.setFeatureState(
      { source: 'tracts', id: Number(selectedGeoid.slice(2)) },
      { selected: true },
    )
    const c = records.find((r) => r.geoid === selectedGeoid)?.centroid
    if (!c) return
    map.easeTo({ center: [c[0], c[1]], zoom: Math.max(map.getZoom(), 10.5), duration: 650 })
  }, [selectedGeoid, records, ready])

  return (
    <div className="map-wrap">
      <div ref={el} className="map-canvas" aria-label="Map of Central Florida census tracts" />
      {tilesFailed && <div className="map-badge">{BASE_MAP_UNAVAILABLE_TEXT}</div>}
    </div>
  )
}
