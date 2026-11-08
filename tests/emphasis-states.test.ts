/**
 * RED test for SLICE-1 cycle 17: gap emphasis feature states (POST-APP-10, REQ-63).
 *
 * CONTRACT AUTHORITY RECORD: contracts/planner-map.app.contract.ts, POST-APP-10 (expectedEmphasisStates).
 * The context-line wording is covered by tests/gap-emphasis.test.tsx.
 */
import { describe, expect, it } from 'vitest'

import { expectedEmphasisStates } from '../contracts/planner-map.app.contract'
import { emphasisStates } from '../src/map/emphasis'

const RECORDS = [
  { geoid: '12095000100', drawn: true },
  { geoid: '12095000200', drawn: true },
  { geoid: '12095990000', drawn: false },
]

describe('POST-APP-10: emphasis feature states', () => {
  it.each([
    ['emphasis on, one focused', ['12095000100'], true],
    ['emphasis off', ['12095000100'], false],
    ['emphasis on, nothing focused', [], true],
    ['emphasis on, only a not-drawn tract focused', ['12095990000'], true],
  ] as const)('%s', (_label, focused, on) => {
    const want = expectedEmphasisStates(RECORDS, focused, on)
    const got = emphasisStates(RECORDS, focused, on)
    expect(
      new Map(got),
      'POST-APP-10 violation: outlined and faded tracts must follow the chosen group',
    ).toEqual(new Map(want))
  })
})
