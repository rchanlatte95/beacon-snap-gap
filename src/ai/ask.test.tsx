import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OpportunitiesApp, type PlannerBundle } from '../App'
import { answerWizardQuery } from '../wizard/alignmentWizard'
import {
  AI_UNAVAILABLE_NOTICE,
  createHttpAskService,
  type AskOutcome,
  type AskService,
} from './askClient'
import { MOCK_MODEL, mockAskAnswer } from './mockAskService'

const bundle: PlannerBundle = JSON.parse(
  readFileSync(resolve(process.cwd(), 'public/data/planner-bundle.json'), 'utf-8'),
)

function ask(question: string) {
  fireEvent.change(
    screen.getByRole('textbox', { name: 'Ask a question about Central Florida neighborhoods' }),
    { target: { value: question } },
  )
  fireEvent.click(screen.getByRole('button', { name: /^Ask$/ }))
}

const context = () => document.getElementById('gap-emphasis-context')!

const applied = {
  reach_miles: 10,
  percentiles: { poverty: 75, no_vehicle: 75, sba_rate_per_1000: 25 },
}
const mock = (q: string) => mockAskAnswer(q, bundle.tracts, bundle.sources ?? [], applied)
const request = (question: string) => ({ question, ...applied })

describe('ask: App and QueryService', () => {
  it('shows the AI answer with source chips and puts its tracts on the map', async () => {
    let release: (o: AskOutcome) => void = () => {}
    const service: AskService = (q) =>
      new Promise((done) => {
        release = done
        void q
      })
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} askService={service} />)

    const question = 'All three gaps in Orange County'
    ask(question)
    expect(screen.getByText('Looking up the answer…')).toBeInTheDocument()
    release({ ok: true, answer: mock(question) })

    const expected = answerWizardQuery(bundle.tracts, question)
    expect(await screen.findByText(expected.answerText)).toBeInTheDocument()
    expect(screen.queryByText('Looking up the answer…')).not.toBeInTheDocument()
    expect(screen.getByText(`Answered by ${MOCK_MODEL}.`, { exact: false })).toBeInTheDocument()
    expect(screen.queryByText(AI_UNAVAILABLE_NOTICE)).not.toBeInTheDocument()

    // REQ-40: ID, publisher, as-of date and origin link on each chip.
    const chips = screen.getByRole('list', { name: 'Sources for this answer' })
    const sba = within(chips).getByText('DS-X5').closest('a')!
    expect(sba).toHaveAttribute('href', 'https://data.sba.gov/dataset/7a-504-foia')
    expect(sba).toHaveTextContent('U.S. Small Business Administration')
    expect(sba).toHaveTextContent('as of 2026-09-30')

    const drawn = expected.matchedTracts.filter((t) => t.drawn).length
    expect(context()).toHaveTextContent('Your question')
    expect(context()).toHaveTextContent(`${drawn} neighborhood`)
  })

  it('shows a non-tract result as a table and leaves the map on the chosen group', async () => {
    const service: AskService = async (r) => ({ ok: true, answer: mock(r.question) })
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} askService={service} />)

    ask('Food deserts by county')
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Food deserts')).toBeInTheDocument()
    expect(within(table).getAllByRole('row')).toHaveLength(5)
    expect(context()).toHaveTextContent('All three gaps')
  })

  it('falls back to the built-in wizard with the REQ-39 notice', async () => {
    const service: AskService = async () => ({ ok: false, sessionEnded: false, reason: 'HTTP 503' })
    render(<OpportunitiesApp initialBundle={bundle} enableMap={false} askService={service} />)

    const question = 'Food deserts in Seminole without a car'
    ask(question)
    expect(await screen.findByText(AI_UNAVAILABLE_NOTICE)).toBeInTheDocument()
    expect(
      screen.getByText(answerWizardQuery(bundle.tracts, question).answerText),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Sources for this answer' })).toBeNull()
  })
})

describe('createHttpAskService', () => {
  const signal = () => new AbortController().signal
  const reply = (body: unknown, status = 200) =>
    Promise.resolve(new Response(JSON.stringify(body), { status }))

  it('posts the request and accepts a complete reply', async () => {
    let sent: { url: string; body: string } | null = null
    const answer = mock('food deserts by county')
    const service = createHttpAskService({
      fetchImpl: (url, init) => {
        sent = { url: String(url), body: String(init?.body) }
        return reply(answer)
      },
    })
    const sentRequest = request('food deserts by county')
    expect(await service(sentRequest, signal())).toEqual({ ok: true, answer })
    expect(sent).toEqual({ url: '/api/ask', body: JSON.stringify(sentRequest) })
  })

  it('falls back on an error status, a broken reply, or no reply in time', async () => {
    const cases: [typeof fetch, string][] = [
      [() => reply({ error: 'ai_unavailable' }, 503), 'HTTP 503'],
      [() => reply({ answer: 'x' }), 'reply does not match the ask interface'],
      [
        (_url, init) =>
          new Promise((_done, fail) =>
            init?.signal?.addEventListener('abort', () => fail(new Error('aborted'))),
          ),
        'no reply in 0.02 s',
      ],
    ]
    for (const [fetchImpl, reason] of cases) {
      const service = createHttpAskService({ fetchImpl, timeoutMs: 20 })
      expect(await service(request('q'), signal())).toEqual({
        ok: false,
        sessionEnded: false,
        reason,
      })
    }
  })
})
