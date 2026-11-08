/**
 * App side of the `ask` interface (manifest section 6, IP-14). The Viewer's question goes to the
 * project's QueryService. The QueryService answers with a Gemini model on Vertex AI (REQ-38) and
 * returns the answer text, the result rows and one citation for each warehouse table it used
 * (REQ-32, SEQ-7).
 *
 * The field names are the ones in contracts/query_service_contract.py (`SqlQueryResult`,
 * `SourceCitation`). The HTTP path, the status codes and the time limit are this side's proposal
 * on issue #14 until Ketema's side writes the `ask` contract.
 */

export const ASK_PATH = '/api/ask'

/** REQ-39 "slow": with no reply in this time, the App uses the built-in wizard. */
export const ASK_TIMEOUT_MS = 20_000

/** REQ-39 notice, word for word. */
export const AI_UNAVAILABLE_NOTICE = 'AI unavailable. Using built-in filters.'

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
}

export type AskOutcome =
  | { readonly ok: true; readonly answer: AskAnswer }
  | { readonly ok: false; readonly reason: string }

/** Never rejects: every failure is an outcome with `ok: false`. */
export type AskService = (question: string, signal: AbortSignal) => Promise<AskOutcome>

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

function parseResult(v: unknown): AskResult | null {
  if (!isRecord(v)) return null
  const { columns, rows, row_count, truncated, referenced_tables } = v
  if (!Array.isArray(columns) || !columns.every(isString)) return null
  if (!Array.isArray(referenced_tables) || !referenced_tables.every(isString)) return null
  if (typeof truncated !== 'boolean' || typeof row_count !== 'number') return null
  // POST-SQL-1: row_count equals the number of rows returned.
  if (!Array.isArray(rows) || rows.length !== row_count) return null
  const parsedRows: Record<string, AskCell>[] = []
  for (const row of rows) {
    if (!isRecord(row)) return null
    const parsed: Record<string, AskCell> = {}
    for (const column of columns) {
      const cell = row[column] ?? null
      if (!isCell(cell)) return null
      parsed[column] = cell
    }
    parsedRows.push(parsed)
  }
  return { columns, rows: parsedRows, row_count, truncated, referenced_tables }
}

/** Accepts only a complete reply; anything else makes the App fall back (REQ-39). */
export function parseAskAnswer(v: unknown): AskAnswer | null {
  if (!isRecord(v)) return null
  const { answer, model, results, citations } = v
  if (!isString(answer) || !answer.trim() || !isString(model) || !model.trim()) return null
  if (!Array.isArray(results) || !Array.isArray(citations)) return null
  const parsedResults = results.map(parseResult)
  const parsedCitations = citations.map(parseCitation)
  if (parsedResults.some((r) => r === null) || parsedCitations.some((c) => c === null)) return null
  return {
    answer,
    model,
    results: parsedResults as AskResult[],
    citations: parsedCitations as AskCitation[],
  }
}

/** A provenance field the sources do not state reads "not recorded" (REQ-29); link only real URLs. */
export function isLinkableUrl(url: string): boolean {
  return /^https?:\/\//i.test(url)
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

/** `POST {url}` with `{"question": ...}`; same origin, so the Gateway session cookie goes along. */
export function createHttpAskService(options: HttpAskOptions = {}): AskService {
  const url = options.url ?? ASK_PATH
  const timeoutMs = options.timeoutMs ?? ASK_TIMEOUT_MS
  const doFetch = options.fetchImpl ?? ((input, init) => fetch(input, init))

  return async (question, signal) => {
    if (signal.aborted) return { ok: false, reason: 'cancelled' }
    const run = new AbortController()
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      run.abort()
    }, timeoutMs)
    const cancel = () => run.abort()
    signal.addEventListener('abort', cancel)
    const failure = (fallbackReason: string): AskOutcome => ({
      ok: false,
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
          body: JSON.stringify({ question }),
          credentials: 'same-origin',
          signal: run.signal,
        })
      } catch {
        return failure('network error')
      }
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
