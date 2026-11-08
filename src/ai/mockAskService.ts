/**
 * Development stand-in for the QueryService `ask` reply. The dev server loads it for `ASK_PATH`
 * (vite.config.ts). Nothing in the App imports it, so it is not in the production bundle.
 *
 * It does not call Gemini, and its `model` field says so. Its numbers come from the real static
 * bundle through the built-in wizard, so a mock answer never shows a number that the data does
 * not hold. It applies the request's cut percentiles; it does not apply the distance. Its
 * citations come from the bundle's source list (`sources`).
 */
import { readFileSync } from 'node:fs'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { resolve } from 'node:path'

import type { SourceEntry } from '../sources'
import { answerWizardQuery, type TractRecord } from '../wizard/alignmentWizard'
import { applyCuts, cutValues, type Cuts } from '../wizard/gapRules'
import {
  ASK_TIMEOUT_MS,
  type AskAnswer,
  type AskCitation,
  type AskRequest,
  type AskResult,
  type AskThresholds,
} from './askClient'

export const MOCK_MODEL = 'Mock service, no Gemini call'

interface MockBundle {
  readonly tracts: readonly TractRecord[]
  readonly sources: readonly SourceEntry[]
  readonly thresholds: { readonly cuts: Cuts; readonly sba_min_population: number }
}

let bundle: MockBundle | null = null

function send(res: ServerResponse, status: number, body: unknown) {
  if (res.writableEnded || res.destroyed) return
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(body))
}

/**
 * `mode` is MOCK_ASK: `ok` answers after 0.7 s, `unavailable` replies 503, `slow` replies after
 * the App's time limit.
 */
export async function handleMockAsk(req: IncomingMessage, res: ServerResponse, mode: string) {
  if (req.method !== 'POST') return send(res, 405, { error: 'method_not_allowed' })
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  let request: AskRequest
  try {
    request = JSON.parse(Buffer.concat(chunks).toString('utf-8')) as AskRequest
  } catch {
    return send(res, 400, { error: 'bad_request', detail: 'The body is not JSON.' })
  }
  if (typeof request.question !== 'string' || !request.question.trim()) {
    return send(res, 400, { error: 'bad_request', detail: 'No question.' })
  }
  if (mode === 'unavailable') {
    return send(res, 503, { error: 'ai_unavailable', detail: 'Mock: Vertex AI unavailable.' })
  }
  await new Promise((done) => setTimeout(done, mode === 'slow' ? ASK_TIMEOUT_MS + 5_000 : 700))
  bundle ??= JSON.parse(
    readFileSync(resolve(process.cwd(), 'public/data/planner-bundle.json'), 'utf-8'),
  ) as MockBundle
  const tracts = applyCuts(
    bundle.tracts,
    cutValues(bundle.thresholds.cuts, request.percentiles),
    bundle.thresholds.sba_min_population,
  )
  const applied = { reach_miles: request.reach_miles, percentiles: request.percentiles }
  send(res, 200, mockAskAnswer(request.question, tracts, bundle.sources, applied))
}

const COUNTY_NAMES = ['Orange', 'Seminole', 'Lake', 'Osceola'] as const
const FILTER = 'Orange, Seminole, Lake and Osceola counties'

/** Short forms of each source's `period` text, as a warehouse as-of value would be. */
const AS_OF: Readonly<Record<string, string>> = {
  'DS-H2': 'ACS 2020-2024',
  'DS-H6': '2025',
  'DS-X5': '2026-09-30',
  'DS-X7b': 'ACS 2020-2024',
  'DS-X12': '2026-11-07',
  'DS-X24': '2020-04-01',
}

function citationsFor(sources: readonly SourceEntry[], ids: readonly string[]): AskCitation[] {
  return ids.flatMap((id) => {
    const source = sources.find((entry) => entry.id === id)
    if (!source) return []
    return [
      {
        table_name: `static_bundle.${id.toLowerCase().replace('-', '_')}`,
        dataset_id: source.id,
        origin_url: source.url,
        publisher: source.publisher,
        as_of: AS_OF[id] ?? source.period,
        applied_filter: FILTER,
      },
    ]
  })
}

function countySummary(
  tracts: readonly TractRecord[],
  sources: readonly SourceEntry[],
  applied: AskThresholds,
): AskAnswer {
  const rows = COUNTY_NAMES.map((county) => {
    const inCounty = tracts.filter((t) => t.county === county)
    const deserts = inCounty.filter((t) => t.tract_class === 'Classic Food Desert')
    return {
      county,
      neighborhoods: inCounty.length,
      food_deserts: deserts.length,
      all_three_gaps: inCounty.filter((t) => t.is_triple_gap).length,
      people_in_food_deserts: deserts.reduce((sum, t) => sum + t.pop2020, 0),
    }
  })
  const top = [...rows].sort((a, b) => b.food_deserts - a.food_deserts)[0]
  const totalDeserts = rows.reduce((sum, r) => sum + r.food_deserts, 0)
  const result: AskResult = {
    columns: Object.keys(rows[0] ?? {}),
    rows,
    row_count: rows.length,
    truncated: false,
    referenced_tables: ['static_bundle.tracts'],
  }
  return {
    answer: top
      ? `${top.county} County has the most food deserts: ${top.food_deserts} of its ${top.neighborhoods} neighborhoods. The four counties have ${totalDeserts} in all.`
      : 'No county rows.',
    model: MOCK_MODEL,
    results: [result],
    citations: citationsFor(sources, ['DS-H2', 'DS-H6', 'DS-X5', 'DS-X7b', 'DS-X24']),
    tracts: [],
    applied,
  }
}

export function mockAskAnswer(
  question: string,
  tracts: readonly TractRecord[],
  sources: readonly SourceEntry[],
  applied: AskThresholds,
): AskAnswer {
  if (/by county|each county|per county|every county/i.test(question)) {
    return countySummary(tracts, sources, applied)
  }

  const builtIn = answerWizardQuery(tracts, question)
  if (builtIn.appliedFilters.length === 0) {
    return {
      answer:
        'The mock service answers only the built-in filter questions, such as "food deserts in Osceola" or "food deserts by county". Gemini answers other questions when the QueryService is live.',
      model: MOCK_MODEL,
      results: [],
      citations: [],
      tracts: [],
      applied,
    }
  }

  // A tract list comes back whole: 490 rows at most, inside the contract's MAX_ROW_LIMIT of 1,000.
  const rows = builtIn.matchedTracts.map((t) => ({
    geoid: t.geoid,
    name: t.name,
    county: t.county,
    pct_poverty: t.pct_poverty,
    pct_no_vehicle: t.pct_no_vehicle,
    sba_loans_total: t.sba_loans_total,
    sites_in_tract: t.sites_in_tract,
    pop2020: t.pop2020,
  }))
  return {
    answer: builtIn.answerText,
    model: MOCK_MODEL,
    results: [
      {
        columns: Object.keys(rows[0] ?? { geoid: null }),
        rows,
        row_count: rows.length,
        truncated: false,
        referenced_tables: ['static_bundle.tracts'],
      },
    ],
    citations: citationsFor(sources, ['DS-H2', 'DS-H6', 'DS-X5', 'DS-X7b', 'DS-X12', 'DS-X24']),
    tracts: rows.map((r) => r.geoid),
    applied,
  }
}
