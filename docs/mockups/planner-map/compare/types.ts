// Contract for "Compare with..." layers. Each layer is one module in compare/ that exports a
// CompareLayer (or null until it is built). The shell lists the layers in one menu and shows
// only one at a time (rule: one question per map).
import type { ReactNode } from 'react'
import type { Map as MapLibre } from 'maplibre-gl'
import type { Records, Tract } from '../model'

export interface CompareContext {
  records: Records
  // Parsed contents of the layer's dataFile, or undefined when the layer has no dataFile.
  extra: unknown
  // The live map, or null before the map loads. Use it only in event handlers and effects.
  getMap: () => MapLibre | null
}

export interface CompareLayer {
  id: string
  // Plain words for the "Compare with..." menu (grade 8 or lower).
  menuLabel: string
  // One plain sentence: the question this layer answers. Shown when the layer is active.
  question: string
  // Optional file in ./data/, loaded at start with the other files. REQ-7 applies to it.
  dataFile?: string
  // MapLibre layer ids that addToMap creates. The shell shows them only when this layer is active.
  mapLayerIds: string[]
  // Add sources and layers. Insert layers before COMPARE_BEFORE_LAYER (mapStyle.ts) and
  // create them with layout visibility 'none'.
  addToMap: (map: MapLibre, ctx: CompareContext) => void
  // Legend and controls, shown in the sidebar while the layer is active.
  Panel: (props: { ctx: CompareContext }) => ReactNode
  // Optional plain sentences for the tract card while the layer is active.
  cardLines?: (t: Tract, ctx: CompareContext) => string[]
  // Sources for "How we know this": citation IDs from docs/data-sources.md.
  sources: { id: string; label: string }[]
}
