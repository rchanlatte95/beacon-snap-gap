/**
 * App side of the `ask` interface (manifest section 6, IP-14). The Viewer's question goes to the
 * project's QueryService. The QueryService answers with a Gemini model on Vertex AI (REQ-38) and
 * returns the answer text, the result rows and one citation for each warehouse table it used
 * (REQ-32, SEQ-7).
 *
 * The shapes, the status mapping and the time limit follow SLICE-4 batch 2 (Z-26, POST-APP-11 to
 * POST-APP-15). The request carries the distance and the three cut percentiles set (REQ-60).
 */
import type { CutName } from '../wizard/gapRules'

export const ASK_PATH = '/api/ask'

/** REQ-39 "slow": with no reply in this time, the App uses the built-in wizard. */
export const ASK_TIMEOUT_MS = 20_000

/** REQ-39 notice, word for word. */
export const AI_UNAVAILABLE_NOTICE = 'AI unavailable. Using built-in filters.'

/** REQ-66: a 401 means the Gateway session ended. */
export const SESSION_ENDED_NOTICE = 'Your session ended.'
export const SIGN_IN_TEXT = 'Sign in again.'
export const SIGN_IN_PATH = '/login'

export interface AskThresholds {
  readonly reach_miles: number
  readonly percentiles: Readonly<Record<CutName, number>>
}

export interface AskRequest extends AskThresholds {
  readonly question: string
}

/** REQ-32 / SEQ-7: one per warehouse table that the answer used. */
export interface AskCitation {
  readonly table_name: string
  readonly dataset_id: string
  readonly origin_url: string
  readonly publisher: string
  readonly as_of: string
  readonly applied_filter: string
}

export type AskCell = string | number | boolean | null

/** REQ-34: one read-only query result. */
export interface AskResult {
  readonly columns: readonly string[]
  readonly rows: readonly Readonly<Record<string, AskCell>>[]
  readonly row_count: number
  readonly truncated: boolean
  readonly referenced_tables: readonly string[]
}

export interface AskAnswer {
  readonly answer: string
  /** The model named in the QueryService configuration (REQ-38). */
  readonly model: string
  readonly results: readonly AskResult[]
  readonly citations: readonly AskCitation[]
  /** Every tract the answer names, however many (POST-APP-15). */
  readonly tracts: readonly string[]
  readonly applied: AskThresholds
}

export type AskOutcome =
  | { readonly ok: true; readonly answer: AskAnswer }
  | { readonly ok: false; readonly sessionEnded: boolean; readonly reason: string }

/** Never rejects: every failure is an outcome with `ok: false` (POST-APP-12). */
export type AskService = (request: AskRequest, signal: AbortSignal) => Promise<AskOutcome>

const CITATION_FIELDS = [
  'table_name',
  'dataset_id',
  'origin_url',
  'publisher',
  'as_of',
  'applied_filter',
] as const

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)
const isString = (v: unknown): v is string => typeof v === 'string'
const isCell = (v: unknown): v is AskCell =>
  v === null || typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean'

function parseCitation(v: unknown): AskCitation | null {
  if (!isRecord(v)) return null
  if (!CITATION_FIELDS.every((field) => isString(v[field]))) return null
  return {
    table_name: v.table_name as string,
    dataset_id: v.dataset_id as string,
    origin_url: v.origin_url as string,
    publisher: v.publisher as string,
    as_of: v.as_of as string,
    applied_filter: v.applied_filter as string,
  }
}

/** POST-APP-12: a result needs only its columns and rows; the other fields have safe defaults. */
function parseResult(v: unknown): AskResult | null {
  if (!isRecord(v)) return null
  const { columns, rows, row_count, truncated, referenced_tables } = v
  if (!Array.isArray(columns) || !Array.isArray(rows)) return null
  const names = columns.map(String)
  const parsedRows = rows.map((row: unknown) => {
    const parsed: Record<string, AskCell> = {}
    for (const column of names) {
      const cell: unknown = isRecord(row) ? (row[column] ?? null) : null
      parsed[column] = isCell(cell) ? cell : String(cell)
    }
    return parsed
  })
  return {
    columns: names,
    rows: parsedRows,
    row_count: typeof row_count === 'number' ? row_count : parsedRows.length,
    truncated: truncated === true,
    referenced_tables: Array.isArray(referenced_tables) ? referenced_tables.map(String) : [],
  }
}

/** Accepts only a complete reply; anything else makes the App fall back (REQ-39). */
export function parseAskAnswer(v: unknown): AskAnswer | null {
  if (!isRecord(v)) return null
  const { answer, model, results, citations, tracts, applied } = v
  if (!isString(answer) || !answer.trim() || !isString(model)) return null
  if (!Array.isArray(results) || !Array.isArray(citations)) return null
  if (!Array.isArray(tracts) || !tracts.every(isString)) return null
  if (!isRecord(applied) || typeof applied.reach_miles !== 'number') return null
  if (!isRecord(applied.percentiles)) return null
  const parsedResults = results.map(parseResult)
  const parsedCitations = citations.map(parseCitation)
  if (parsedResults.some((r) => r === null) || parsedCitations.some((c) => c === null)) return null
  return {
    answer,
    model,
    results: parsedResults as AskResult[],
    citations: parsedCitations as AskCitation[],
    tracts,
    applied: {
      reach_miles: applied.reach_miles,
      percentiles: applied.percentiles as AskThresholds['percentiles'],
    },
  }
}

/** A provenance field the sources do not state reads "not recorded" (REQ-29); link only real URLs. */
export function isLinkableUrl(url: string): boolean {
  return /^https?:\/\//.test(url)
}

/** The column whose every value is a known tract GEOID, if the result is a list of tracts. */
export function tractColumn(result: AskResult, knownGeoids: ReadonlySet<string>): string | null {
  if (result.rows.length === 0) return null
  return (
    result.columns.find((column) =>
      result.rows.every((row) => {
        const value = row[column]
        return value !== null && value !== undefined && knownGeoids.has(String(value))
      }),
    ) ?? null
  )
}

/** Every tract GEOID named in the answer's tract-list results, first-seen order. */
export function tractGeoidsInResults(
  results: readonly AskResult[],
  knownGeoids: ReadonlySet<string>,
): string[] {
  const found = new Set<string>()
  for (const result of results) {
    const column = tractColumn(result, knownGeoids)
    if (column) for (const row of result.rows) found.add(String(row[column]))
  }
  return [...found]
}

export interface HttpAskOptions {
  readonly url?: string
  readonly timeoutMs?: number
  readonly fetchImpl?: typeof fetch
}

/** `POST {url}` with the AskRequest; same origin, so the Gateway session cookie goes along. */
export function createHttpAskService(options: HttpAskOptions = {}): AskService {
  const url = options.url ?? ASK_PATH
  const timeoutMs = options.timeoutMs ?? ASK_TIMEOUT_MS
  const doFetch = options.fetchImpl ?? ((input, init) => fetch(input, init))

  return async (request, signal) => {
    if (signal.aborted) return { ok: false, sessionEnded: false, reason: 'cancelled' }
    const run = new AbortController()
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      run.abort()
    }, timeoutMs)
    const cancel = () => run.abort()
    signal.addEventListener('abort', cancel)
    const failure = (fallbackReason: string, sessionEnded = false): AskOutcome => ({
      ok: false,
      sessionEnded,
      reason: timedOut
        ? `no reply in ${timeoutMs / 1000} s`
        : signal.aborted
          ? 'cancelled'
          : fallbackReason,
    })

    try {
      let res: Response
      try {
        res = await doFetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(request),
          credentials: 'same-origin',
          signal: run.signal,
        })
      } catch {
        return failure('network error')
      }
      if (res.status === 401) return failure('HTTP 401', true)
      if (!res.ok) return failure(`HTTP ${res.status}`)
      let body: unknown
      try {
        body = await res.json()
      } catch {
        return failure('reply is not JSON')
      }
      const answer = parseAskAnswer(body)
      return answer ? { ok: true, answer } : failure('reply does not match the ask interface')
    } finally {
      clearTimeout(timer)
      signal.removeEventListener('abort', cancel)
    }
  }
}
