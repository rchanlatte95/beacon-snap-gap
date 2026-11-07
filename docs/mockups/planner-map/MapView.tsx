// The map. Owner: the map-readability task (T8). Moved from PlannerMock.tsx without behavior change.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Map as MapLibre, Marker, NavigationControl, Popup } from 'maplibre-gl'
import type { ExpressionSpecification, LngLatBoundsLike } from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import { CLASS_LABEL, featureId } from './model'
import type { Coverage, Loaded } from './model'
import { BLANK_STYLE, COLORS, WIDTH, hatchImage } from './mapStyle'
import { COMPARE_LAYERS } from './compare'
import type { CompareContext, CompareLayer } from './compare/types'

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

// ---------------- Map ----------------

export function MapView(props: {
  data: Loaded
  selected: string | null
  onSelect: (geoid: string | null) => void
  coverageOn: boolean
  coverage: Coverage
  sitesOn: boolean
  // Called with the map after it loads, and with null when it is removed.
  onMap: (map: MapLibre | null) => void
  compareId: string | null
  compareCtx: (layer: CompareLayer) => CompareContext
}) {
  const { data, selected, onSelect, coverageOn, coverage, sitesOn, compareId } = props
  const el = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibre | null>(null)
  const onMapRef = useRef(props.onMap)
  useEffect(() => {
    onMapRef.current = props.onMap
  }, [props.onMap])
  const ctxRef = useRef(props.compareCtx)
  useEffect(() => {
    ctxRef.current = props.compareCtx
  }, [props.compareCtx])
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
        paint: { 'line-color': '#FFFFFF', 'line-width': WIDTH.tract },
      })
      map.addLayer({
        id: 'county-line',
        type: 'line',
        source: 'counties',
        paint: { 'line-color': COLORS.primary700, 'line-width': WIDTH.county },
      })
      map.addLayer({
        id: 'tract-selected',
        type: 'line',
        source: 'tracts',
        paint: {
          'line-color': COLORS.primary900,
          'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], WIDTH.selected, 0],
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

      for (const layer of COMPARE_LAYERS) layer.addToMap(map, ctxRef.current(layer))

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
      onMapRef.current(map)
    })
    return () => {
      onMapRef.current(null)
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

  // Compare-with: show only the active layer's map layers.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    for (const layer of COMPARE_LAYERS)
      for (const id of layer.mapLayerIds)
        map.setLayoutProperty(id, 'visibility', layer.id === compareId ? 'visible' : 'none')
  }, [compareId, ready])

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
