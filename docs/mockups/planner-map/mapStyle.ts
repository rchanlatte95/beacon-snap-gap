// Map style tokens. Owner: the map-readability task (T8). Other map layers, including
// the Compare-with layers in compare/, take their colors and line widths from here.
import type { StyleSpecification } from 'maplibre-gl'

export const COLORS = {
  desert: '#F79122',
  nogap: '#DFE7EE',
  primary900: '#1E343F',
  primary700: '#385981',
  primary500: '#6B8FA8',
}

export function hatchImage() {
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

export const BLANK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#F3F5F7' } }],
}

// Line widths in px. The values are the ones the mock-up used before T8.
export const WIDTH = {
  tract: 0.6,
  county: 1.6,
  selected: 3,
}

// Sequential palette for Compare-with layers (light to dark, Beacon primary blues).
export const COMPARE_SEQ = ['#DCE6EE', '#9FB8CC', '#6B8FA8', '#385981', '#1E343F'] as const

// Compare-with layers are inserted below this layer, so tract and county lines stay on top.
// The map task must keep a layer with this id.
export const COMPARE_BEFORE_LAYER = 'tract-line'
