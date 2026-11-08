/**
 * RED tests for SLICE-4 batch 2: the App side of the ask call (Z-26).
 *
 * CONTRACT AUTHORITY RECORD:
 * - File: contracts/planner-map.app.contract.ts
 * - Clauses covered: POST-APP-11, POST-APP-12, POST-APP-13, POST-APP-14, POST-APP-15
 * - Requirements: REQ-60, REQ-39, REQ-40, REQ-66
 * - Server side: contracts/query_service_contract.py (PRE-ASK-1, POST-ASK-1)
 *
 * FOUR-CRITERIA TEST VALIDITY GATE:
 * - C1 VALID: outcomes come from expectedOutcomeKind, links from expectedChipHref, texts from constants.
 * - C2 VALUABLE: a client that drops the thresholds, rejects, shows the outage notice on a 401, links a
 *   "not recorded" origin, or caps the shortlist at a row limit fails.
 * - C3 NON-DUPLICATIVE: reach-thresholds.test.tsx covers the controls; these cover the ask call.
 * - C4 NOT FUTURE-EDIT: selectors are contract constants; src/ai/ask.test.tsx (PR #19) is not relied on.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import {
  AI_UNAVAILABLE_TEXT,
  APP_TEST_IDS,
  ASK_PATH,
  ASK_TEST_IDS,
  DISTANCE_SLIDER_NAME,
  NOT_RECORDED,
  QUESTION_BOX_NAME,
  SESSION_ENDED_TEXT,
  SIGN_IN_PATH,
  expectedChipHref,
  expectedOutcomeKind,
  type AskAnswerShape,
  type AskOutcomeShape,
  type AskRequestShape,
} from '../contracts/planner-map.app.contract'
import { createHttpAskService } from '../src/ai/askClient'
import { OpportunitiesApp } from '../src/App'
import { loadCycle17Bundle, tractsOf } from './fixtures/cycle17Bundle'

const REQUEST: AskRequestShape = {
  question: 'Which food deserts lack SBA loans?',
  reach_miles: 5,
  percentiles: { poverty: 90, no_vehicle: 75, sba_rate_per_1000: 25 },
}

function answerWith(tracts: readonly string[]): AskAnswerShape {
  return {
    answer: 'These neighborhoods match.',
    model: 'gemini-3.8-flash',
    results: [
      {
        columns: ['geoid'],
        rows: tracts.slice(0, 2).map((g) => ({ geoid: g })),
        row_count: 2,
        truncated: true,
        referenced_tables: ['sba_loans', 'tract_pop'],
      },
    ],
    citations: [
      {
        table_name: 'sba_loans',
        dataset_id: 'DS-X5',
        origin_url: 'https://data.sba.gov/dataset/7a-504-foia',
        publisher: 'U.S. Small Business Administration',
        as_of: '2026-09-30',
        applied_filter: 'BorrState in FL, NY, UT',
      },
      {
        table_name: 'tract_pop',
        dataset_id: 'DS-X24',
        origin_url: NOT_RECORDED,
        publisher: 'U.S. Census Bureau',
        as_of: '2020',
        applied_filter: 'none',
      },
    ],
    tracts,
    applied: { reach_miles: REQUEST.reach_miles, percentiles: REQUEST.percentiles },
  }
}

function respond(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('POST-APP-11 and POST-APP-12: the HTTP ask client', () => {
  it('posts the request as JSON to ASK_PATH and maps every reply by expectedOutcomeKind', async () => {
    const answer = answerWith(['12095016510'])
    type Kind = 'ok' | 'session_ended' | 'unavailable'
    const cases: [string, () => Promise<Response>, Kind][] = [
      [
        '200 ask-shaped',
        async () => respond(200, answer),
        expectedOutcomeKind({ status: 200, body: answer }),
      ],
      ['401', async () => respond(401, {}), expectedOutcomeKind({ status: 401, body: {} })],
      [
        '503',
        async () => respond(503, { error: 'ERRORS-ASK-2' }),
        expectedOutcomeKind({ status: 503, body: {} }),
      ],
      [
        '200 wrong shape',
        async () => respond(200, { answer: 'x' }),
        expectedOutcomeKind({ status: 200, body: { answer: 'x' } }),
      ],
      [
        'network error',
        async () => Promise.reject(new TypeError('offline')),
        expectedOutcomeKind('network-error'),
      ],
    ]
    for (const [label, reply, kind] of cases) {
      const calls: { url: string; init: RequestInit }[] = []
      const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        calls.push({ url: String(url), init: init ?? {} })
        return reply()
      }) as unknown as typeof fetch
      const service = createHttpAskService({ fetchImpl })
      const outcome: AskOutcomeShape = await service(REQUEST, new AbortController().signal)
      expect(calls, `POST-APP-11 violation (${label}): exactly one request`).toHaveLength(1)
      expect(calls[0]!.url).toBe(ASK_PATH)
      expect(calls[0]!.init.method).toBe('POST')
      expect(calls[0]!.init.credentials).toBe('same-origin')
      expect(
        JSON.parse(String(calls[0]!.init.body)),
        `POST-APP-11 violation (${label}): the body must be the AskRequestShape`,
      ).toEqual(REQUEST)
      const got = outcome.ok ? 'ok' : outcome.sessionEnded ? 'session_ended' : 'unavailable'
      expect(got, `POST-APP-12 violation (${label}): outcome must be ${kind}`).toBe(kind)
      if (outcome.ok) expect(outcome.answer.tracts).toEqual(answer.tracts)
    }
  })

  it('gives up after timeoutMs and reports unavailable without rejecting', async () => {
    const fetchImpl = ((_url: RequestInfo | URL, init?: RequestInit) => {
      const { promise, reject } = Promise.withResolvers<Response>()
      init?.signal?.addEventListener('abort', () =>
        reject(new DOMException('aborted', 'AbortError')),
      )
      return promise
    }) as typeof fetch
    const service = createHttpAskService({ fetchImpl, timeoutMs: 20 })
    const outcome = await service(REQUEST, new AbortController().signal)
    expect(outcome.ok, 'POST-APP-12 violation: a slow reply must be unavailable').toBe(false)
    expect(outcome.ok === false && outcome.sessionEnded).toBe(false)
    expect(expectedOutcomeKind('timeout')).toBe('unavailable')
  })
})

describe('POST-APP-11 to POST-APP-15: the question box', () => {
  function ask(service: (r: AskRequestShape, s: AbortSignal) => Promise<AskOutcomeShape>) {
    const bundle = loadCycle17Bundle()
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} askService={service} />)
    fireEvent.input(screen.getByRole('slider', { name: DISTANCE_SLIDER_NAME }), {
      target: { value: '5' },
    })
    fireEvent.change(screen.getByTestId(APP_TEST_IDS.cutSelect('poverty')), {
      target: { value: '90' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: QUESTION_BOX_NAME }), {
      target: { value: REQUEST.question },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
    return bundle
  }

  it('sends the current thresholds, shows the answer with chips, and lists every answer tract', async () => {
    const bundle = loadCycle17Bundle()
    const tracts = tractsOf(bundle)
      .filter((t) => t.drawn)
      .slice(0, 250)
      .map((t) => t.geoid)
    const answer = answerWith(tracts)
    const service = vi.fn(async () => ({ ok: true, answer }) as const)
    ask(service)

    expect(await screen.findByTestId(ASK_TEST_IDS.aiAnswer)).toHaveTextContent(answer.answer)
    expect(
      service.mock.calls[0]![0],
      'POST-APP-11 violation: the App must send the thresholds set',
    ).toEqual(REQUEST)
    for (const c of answer.citations) {
      const chip = screen.getByTestId(ASK_TEST_IDS.citationChip(c.table_name))
      for (const text of [c.dataset_id, c.publisher, c.as_of]) {
        expect(
          chip,
          `POST-APP-13 violation: chip ${c.table_name} must show "${text}"`,
        ).toHaveTextContent(text)
      }
      const hrefs = within(chip)
        .queryAllByRole('link')
        .map((a) => a.getAttribute('href'))
      const want = expectedChipHref(c)
      expect(hrefs, `POST-APP-13 violation: chip ${c.table_name} link`).toEqual(
        want === null ? [] : [want],
      )
    }
    const rows = [...document.querySelectorAll('[data-testid^="tract-row-"]')].map((r) =>
      r.getAttribute('data-testid')!.slice('tract-row-'.length),
    )
    expect(
      [...rows].sort(),
      `POST-APP-15 violation: the shortlist must hold exactly the ${tracts.length} answer tracts`,
    ).toEqual([...tracts].sort())
    expect(screen.queryByText(AI_UNAVAILABLE_TEXT)).toBeNull()
  })

  it('falls back to the built-in wizard with the outage notice when the AI is unavailable', async () => {
    ask(async () => ({ ok: false, sessionEnded: false, reason: 'HTTP 503' }))
    expect(await screen.findByTestId(ASK_TEST_IDS.aiNotice)).toHaveTextContent(AI_UNAVAILABLE_TEXT)
    expect(screen.queryByTestId(ASK_TEST_IDS.aiAnswer)).toBeNull()
    expect(
      document.getElementById('gap-emphasis-context'),
      'POST-APP-12 violation: the built-in wizard must answer the question',
    ).toHaveTextContent('Your question')
  })

  it('shows the session-ended notice with a sign-in link, not the outage notice', async () => {
    ask(async () => ({ ok: false, sessionEnded: true, reason: 'HTTP 401' }))
    const notice = await screen.findByTestId(ASK_TEST_IDS.aiNotice)
    expect(notice, 'POST-APP-14 violation').toHaveTextContent(SESSION_ENDED_TEXT)
    expect(within(notice).getByRole('link')).toHaveAttribute('href', SIGN_IN_PATH)
    expect(
      screen.queryByText(AI_UNAVAILABLE_TEXT),
      'POST-APP-14 violation: no outage notice',
    ).toBeNull()
    expect(document.getElementById('gap-emphasis-context')).toHaveTextContent('Your question')
  })
})
