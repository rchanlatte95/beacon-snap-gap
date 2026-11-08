// Compare-with layer "Your own data". Owner: T6.
// A partner loads a CSV of numbers by census tract, or a GeoJSON file of points, and sees it next
// to need. The file is read in the browser only: no network call, no upload, no browser storage.
// Points are counted per tract and then dropped (REQ-4: tract level only).
// Parts: importedParse.ts (file reading), importedStore.ts (state, map data, card line),
// importedPanel.tsx (sidebar panel), samples/ (sample files made from public repo data).
import { COLORS, COMPARE_BEFORE_LAYER, WIDTH } from '../mapStyle'
import type { CompareLayer } from './types'
import { ImportedPanel } from './importedPanel'
import { EMPTY, FILL, HIGH_NEED, NO_VALUE, SOURCE, SOURCES, cardLines } from './importedStore'

const layer: CompareLayer = {
  id: 'imported',
  menuLabel: 'Your own data',
  question: 'How does your data line up with need?',
  mapLayerIds: [FILL, HIGH_NEED],
  addToMap: (map) => {
    map.addSource(SOURCE, { type: 'geojson', data: EMPTY })
    map.addLayer(
      {
        id: FILL,
        type: 'fill',
        source: SOURCE,
        layout: { visibility: 'none' },
        paint: { 'fill-color': ['coalesce', ['get', 'color'], NO_VALUE] },
      },
      COMPARE_BEFORE_LAYER,
    )
    map.addLayer(
      {
        id: HIGH_NEED,
        type: 'line',
        source: SOURCE,
        filter: ['==', ['get', 'cls'], 'desert'],
        layout: { visibility: 'none', 'line-join': 'round' },
        paint: { 'line-color': COLORS.desert, 'line-width': WIDTH.selected },
      },
      COMPARE_BEFORE_LAYER,
    )
  },
  Panel: ImportedPanel,
  cardLines,
  sources: SOURCES,
}

export default layer
