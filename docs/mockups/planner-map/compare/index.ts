// Registry of Compare-with layers. Each slot has one owner task; edit only your own module.
import type { CompareLayer } from './types'
import transport from './transport'
import blindspots from './blindspots'
import lending from './lending'
import imported from './imported'

export const COMPARE_LAYERS: CompareLayer[] = [transport, blindspots, lending, imported].filter(
  (l): l is CompareLayer => l !== null,
)
