import { useEffect, useRef, useState } from 'react'
import { Map as MapLibre, NavigationControl, setWorkerUrl } from 'maplibre-gl'
import type { ExpressionSpecification, LngLatBoundsLike, StyleSpecification } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import 'maplibre-gl/dist/maplibre-gl.css'

import type { TractRecord } from '../wizard/alignmentWizard'
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

type Ring = GeoJSON.Position[]

function outerRings(fc: GeoJSON.FeatureCollection): Ring[] {
  const rings: Ring[] = []
  for (const f of fc.features) {
    const g = f.geometry
    const polys =
      g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : []
    for (const p of polys) if (p[0]) rings.push(p[0])
  }
  return rings
}

/**
 * The first view: the box around the food-desert tracts, so the color fills the frame.
 * Falls back to all features, then to the old fixed box.
 */
function startBounds(tracts: GeoJSON.FeatureCollection): LngLatBoundsLike {
  const highNeed = tracts.features.filter((f) => f.properties?.tract_class === CLASS_HIGH_NEED)
  return featureBounds({ ...tracts, features: highNeed.length ? highNeed : tracts.features })
}

function featureBounds(fc: GeoJSON.FeatureCollection): LngLatBoundsLike {
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const ring of outerRings(fc)) {
    for (const [x = NaN, y = NaN] of ring) {
      if (Number.isNaN(x) || Number.isNaN(y)) continue
      w = Math.min(w, x)
      s = Math.min(s, y)
      e = Math.max(e, x)
      n = Math.max(n, y)
    }
  }
  return Number.isFinite(w)
    ? [
        [w, s],
        [e, n],
      ]
    : CENTRAL_FL_BOUNDS
}

function signedArea(ring: Ring): number {
  let a = 0
  let prev = ring.at(-1)
  for (const cur of ring) {
    if (prev) a += ((prev[0] ?? 0) - (cur[0] ?? 0)) * ((prev[1] ?? 0) + (cur[1] ?? 0))
    prev = cur
  }
  return a
}

/** A large box with the counties cut out, used to fade the land outside the four counties. */
function outsideMask(fc: GeoJSON.FeatureCollection): GeoJSON.Feature {
  const world: Ring = [
    [-90, 20],
    [-70, 20],
    [-70, 36],
    [-90, 36],
    [-90, 20],
  ]
  // MapLibre treats a ring as a hole only when its winding is opposite to the outer ring.
  const worldSign = Math.sign(signedArea(world))
  const holes = outerRings(fc).map((r) =>
    Math.sign(signedArea(r)) === worldSign ? [...r].reverse() : r,
  )
  return {
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [world, ...holes] },
  }
}

/** Basemap layers that add noise at the region scale. Place names and major roads stay. */
function quietBasemap(map: MapLibre) {
  const keepSymbols = new Set(['label_city', 'label_city_capital', 'label_town'])
  for (const layer of map.getStyle().layers ?? []) {
    const id = layer.id
    const src = 'source-layer' in layer ? layer['source-layer'] : undefined
    if (layer.type === 'symbol' && !keepSymbols.has(id)) {
      map.setLayoutProperty(id, 'visibility', 'none')
    } else if (
      src === 'building' ||
      src === 'aeroway' ||
      src === 'boundary' ||
      id === 'landuse_residential' ||
      id === 'landcover_wood' ||
      (src === 'transportation' && !/motorway|major/.test(id))
    ) {
      map.setLayoutProperty(id, 'visibility', 'none')
    } else if (src === 'transportation' && layer.type === 'line') {
      map.setPaintProperty(id, 'line-opacity', 0.45)
    }
  }
}

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
  readonly focusedGeoids: readonly string[]
  readonly emphasizeGaps: boolean
  readonly selectedGeoid: string | null
  readonly onSelect: (geoid: string | null) => void
  readonly overlays: {
    readonly sba: boolean
    readonly transport: boolean
    readonly sites: boolean
  }
}

export function OpportunityMap(props: OpportunityMapProps) {
  const {
    tractsGeojson,
    countiesGeojson,
    sitesGeojson,
    records,
    focusedGeoids,
    emphasizeGaps,
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
      bounds: startBounds(tractsGeojson),
      fitBoundsOptions: { padding: { top: 56, bottom: 28, left: 36, right: 36 } },
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
      quietBasemap(map)
      if (!map.hasImage('hatch')) map.addImage('hatch', hatchImage(), { pixelRatio: 2 })
      map.addSource('tracts', { type: 'geojson', data: tractsGeojson })
      map.addSource('counties', { type: 'geojson', data: countiesGeojson })
      map.addSource('sites', { type: 'geojson', data: sitesGeojson })
      map.addSource('outside', { type: 'geojson', data: outsideMask(countiesGeojson) })
      const firstSymbol = map.getStyle().layers?.find((l) => l.type === 'symbol')?.id

      // Keep the class colors visible, including when other groups are faded.
      const isHighNeed: ExpressionSpecification = ['==', ['get', 'tract_class'], CLASS_HIGH_NEED]
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
              isHighNeed,
              COLORS.highNeed,
              COLORS.noGap,
            ],
            'fill-opacity': [
              'case',
              ['boolean', ['feature-state', 'hover'], false],
              0.95,
              ['boolean', ['feature-state', 'muted'], false],
              0.14,
              ['boolean', ['feature-state', 'emphasized'], false],
              0.98,
              ['!', isHighNeed],
              ['case', ['boolean', ['feature-state', 'dimmed'], false], 0.4, 0.7],
              ['boolean', ['feature-state', 'dimmed'], false],
              0.28,
              0.88,
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
          paint: {
            'fill-pattern': 'hatch',
            'fill-opacity': ['case', ['boolean', ['feature-state', 'muted'], false], 0.14, 0.9],
          },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'tract-line',
          type: 'line',
          source: 'tracts',
          paint: {
            'line-color': ['case', isHighNeed, '#FFFFFF', COLORS.soft],
            'line-width': ['case', isHighNeed, 0.6, 0.4],
            'line-opacity': [
              'case',
              ['boolean', ['feature-state', 'muted'], false],
              0.18,
              isHighNeed,
              0.9,
              0.5,
            ],
          },
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
          paint: { 'line-color': COLORS.ink, 'line-width': 1.4, 'line-dasharray': [2, 1.2] },
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
          id: 'gap-emphasis-halo',
          type: 'line',
          source: 'tracts',
          paint: {
            'line-color': '#FFFFFF',
            'line-width': 5,
            'line-opacity': ['case', ['boolean', ['feature-state', 'emphasized'], false], 1, 0],
          },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'gap-emphasis-outline',
          type: 'line',
          source: 'tracts',
          paint: {
            'line-color': COLORS.ink,
            'line-width': 2.4,
            'line-opacity': ['case', ['boolean', ['feature-state', 'emphasized'], false], 1, 0],
          },
        },
        firstSymbol,
      )
      map.addLayer(
        {
          id: 'county-line',
          type: 'line',
          source: 'counties',
          paint: { 'line-color': COLORS.ink, 'line-width': 1.2, 'line-opacity': 0.55 },
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
            'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2.6, 0],
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
      // On top of everything, place names too, so the land outside the four counties fades back.
      map.addLayer({
        id: 'outside-mask',
        type: 'fill',
        source: 'outside',
        paint: { 'fill-color': COLORS.paper, 'fill-opacity': 0.7 },
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

  // The map and shortlist follow the same cohort or question results.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    const include = new Set(focusedGeoids)
    const active = emphasizeGaps && include.size > 0
    for (const r of records) {
      if (!r.drawn) continue
      map.setFeatureState(
        { source: 'tracts', id: Number(r.geoid.slice(2)) },
        {
          dimmed: !include.has(r.geoid),
          emphasized: active && include.has(r.geoid),
          muted: active && !include.has(r.geoid),
        },
      )
    }
  }, [focusedGeoids, emphasizeGaps, records, ready])

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
      <div ref={el} className="map-canvas" aria-label="Map of Central Florida neighborhoods" />
      {tilesFailed && <div className="map-badge">{BASE_MAP_UNAVAILABLE_TEXT}</div>}
    </div>
  )
}
