import { createContext } from 'react'

/** One entry of the bundle's source list (REQ-61), copied by the Build from docs/data-sources.md section 9. */
export interface SourceEntry {
  readonly id: string
  readonly label: string
  readonly publisher: string
  readonly period: string
  readonly url: string
  readonly method: string
  readonly limits: string
}

export const SOURCE_REGISTER_URL =
  'https://github.com/ketema/beacon-snap-cliff/blob/e1ad7f11e788b293cb638db67b4fe8f5ee0b1751/docs/data-sources.md'

/** REQ-62: the App lists and links only the bundle's sources. */
export const SourcesContext = createContext<readonly SourceEntry[]>([])
