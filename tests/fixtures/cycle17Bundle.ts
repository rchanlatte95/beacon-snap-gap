/**
 * Test fixture: the committed static bundle plus the cycle 17 fields (POST-RCH-1, POST-CUT-1,
 * POST-SRC-1) with synthetic reach and source values, so an App that measures distances, computes
 * its own quantiles or keeps a typed source list cannot pass. The cuts are the Build oracle's
 * real values over the committed tracts.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  MAX_REACH_MILES,
  REACH_STEP_MILES,
  type CutsShape,
  type SourceEntryShape,
  type TractRecordShape,
} from '../../contracts/planner-map.app.contract'
import type { PlannerBundle } from '../../src/App'

export const STEPS = Math.round(MAX_REACH_MILES / REACH_STEP_MILES) + 1

export const CUTS: CutsShape = {
  poverty: { '50': 10.0, '75': 17.025, '90': 23.13 },
  no_vehicle: { '50': 3.55, '75': 6.9, '90': 12.63 },
  sba_rate_per_1000: {
    '10': 0.44915923508772565,
    '25': 0.9427292010370022,
    '50': 1.7944535073409462,
  },
}

export const SOURCES: SourceEntryShape[] = [
  {
    id: 'DS-T1',
    label: 'Fixture label one',
    publisher: 'Fixture publisher one',
    period: 'Fixture period one',
    url: 'https://example.org/one',
    method: 'Fixture method one',
    limits: 'Fixture limits one',
  },
  {
    id: 'DS-T2',
    label: 'Fixture label two',
    publisher: 'Fixture publisher two',
    period: 'Fixture period two',
    url: 'https://example.org/two',
    method: 'Fixture method two',
    limits: 'Fixture limits two',
  },
]

export function loadCycle17Bundle(): PlannerBundle {
  const raw = JSON.parse(
    readFileSync(resolve(process.cwd(), 'public/data/planner-bundle.json'), 'utf8'),
  )
  raw.tracts = raw.tracts.map((t: Record<string, unknown>, i: number) => ({
    ...t,
    reach_share: Array.from({ length: STEPS }, (_, k) => k / (STEPS - 1)),
    reach_sites: Array.from({ length: STEPS }, (_, k) => 100 + k),
    nearest_block_miles: i % 5 === 0 ? null : i % 2 === 0 ? 2.0 : 15.5,
  }))
  raw.thresholds = { ...raw.thresholds, cuts: CUTS }
  raw.sources = SOURCES
  return raw as PlannerBundle
}

export function tractsOf(bundle: PlannerBundle): TractRecordShape[] {
  return (bundle as unknown as { tracts: TractRecordShape[] }).tracts
}
