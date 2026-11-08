/**
 * RED test for Z-30: the App waits ASK_TIMEOUT_MS for an answer, above the QueryService deadline.
 *
 * CONTRACT AUTHORITY RECORD:
 * - File: contracts/planner-map.app.contract.ts (ASK_TIMEOUT_MS, POST-APP-12)
 * - Requirements: REQ-39, REQ-60 (Z-26, limits superseded by Z-30)
 *
 * FOUR-CRITERIA TEST VALIDITY GATE:
 * - C1 VALID: POST-APP-12 maps a reply that does not arrive within ASK_TIMEOUT_MS to the outage notice.
 * - C2 VALUABLE: an App that gives up before the service's 45 s deadline fails.
 * - C3 NON-DUPLICATIVE: tests/ask.test.tsx injects its own timeout; this checks the App's value.
 * - C4 NOT FUTURE-EDIT: the constant exists and is used by the ask client today.
 */
import { describe, expect, it } from 'vitest'

import { ASK_TIMEOUT_MS } from '../contracts/planner-map.app.contract'
import { ASK_TIMEOUT_MS as APP_ASK_TIMEOUT_MS } from '../src/ai/askClient'

describe('Z-30: the App waits long enough for an AI answer', () => {
  it('enforces POST-APP-12: the ask client waits ASK_TIMEOUT_MS', () => {
    expect(
      APP_ASK_TIMEOUT_MS,
      `POST-APP-12 violation: the App gives up after ${APP_ASK_TIMEOUT_MS} ms\n` +
        `EXPECTED: ${ASK_TIMEOUT_MS} ms (Z-30, above the QueryService's 45 s deadline)\n` +
        'GUIDANCE: wait the contracted time before showing the outage notice',
    ).toBe(ASK_TIMEOUT_MS)
  })
})
