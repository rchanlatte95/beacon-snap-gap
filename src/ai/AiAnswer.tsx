import type { ReactNode } from 'react'

import {
  AI_UNAVAILABLE_NOTICE,
  SESSION_ENDED_NOTICE,
  SIGN_IN_PATH,
  SIGN_IN_TEXT,
  isLinkableUrl,
  tractColumn,
  type AskAnswer,
  type AskCell,
  type AskCitation,
  type AskResult,
} from './askClient'

const TABLE_ROWS_MAX = 8
const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

function cellText(cell: AskCell | undefined): string {
  if (cell === null || cell === undefined) return 'No data'
  if (typeof cell === 'number') return nf.format(cell)
  if (typeof cell === 'boolean') return cell ? 'Yes' : 'No'
  return cell
}

const ACRONYMS = new Set(['acs', 'fema', 'geoid', 'id', 'nri', 'sba', 'snap', 'usda'])

/** `few_sba_loans` -> "Few SBA loans". */
function heading(column: string): string {
  const words = column.split('_').map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w))
  const text = words.join(' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

const isNumberColumn = (result: AskResult, column: string) =>
  result.rows.some((row) => typeof row[column] === 'number') &&
  result.rows.every((row) => row[column] === null || typeof row[column] === 'number')

/** REQ-40, POST-APP-13: one chip per cited table, with its ID, publisher, as-of date and origin link. */
export function CitationChips({ citations }: { readonly citations: readonly AskCitation[] }) {
  const unique = citations.filter(
    (c, i) => citations.findIndex((d) => d.table_name === c.table_name) === i,
  )
  if (unique.length === 0) {
    return <p className="sources">No source was cited for this answer.</p>
  }
  return (
    <ul className="cite-chips" aria-label="Sources for this answer">
      {unique.map((c) => {
        const body = (
          <>
            <b>{c.dataset_id}</b> {c.publisher} <span className="cite-date">· as of {c.as_of}</span>
          </>
        )
        const title = `Table ${c.table_name}. Filter: ${c.applied_filter}.`
        return (
          <li key={c.table_name} data-testid={`citation-chip-${c.table_name}`}>
            {isLinkableUrl(c.origin_url) ? (
              <a
                className="cite-chip"
                href={c.origin_url}
                target="_blank"
                rel="noreferrer"
                title={title}
              >
                {body}
              </a>
            ) : (
              <span className="cite-chip" title={`${title} Origin: ${c.origin_url}.`}>
                {body}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function ResultTable({ result }: { readonly result: AskResult }) {
  const shown = result.rows.slice(0, TABLE_ROWS_MAX)
  const numeric = new Set(result.columns.filter((c) => isNumberColumn(result, c)))
  return (
    <div className="answer-table-wrap">
      <table className="answer-table">
        <thead>
          <tr>
            {result.columns.map((c) => (
              <th key={c} scope="col" className={numeric.has(c) ? 'num' : undefined}>
                {heading(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i}>
              {result.columns.map((c) => (
                <td key={c} className={numeric.has(c) ? 'num' : undefined}>
                  {cellText(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {(result.row_count > shown.length || result.truncated) && (
        <p className="answer-table-note">
          Showing {shown.length} of {nf.format(result.row_count)} rows
          {result.truncated ? '. The service stopped at its row limit.' : '.'}
        </p>
      )}
    </div>
  )
}

/** A reply from the QueryService. Tract lists go to the map and the shortlist, not a table. */
export function AiAnswerCard({
  answer,
  knownGeoids,
  extra,
  onClear,
}: {
  readonly answer: AskAnswer
  readonly knownGeoids: ReadonlySet<string>
  readonly extra?: ReactNode
  readonly onClear: () => void
}) {
  const tables = answer.results.filter((r) => r.rows.length > 0 && !tractColumn(r, knownGeoids))
  return (
    <div className="answer answer--ai" role="status" data-testid="ai-answer">
      <p>{answer.answer}</p>
      {extra}
      {tables.map((r, i) => (
        <ResultTable key={i} result={r} />
      ))}
      <CitationChips citations={answer.citations} />
      <p className="answer-meta">
        Answered by {answer.model}.{' '}
        <button type="button" className="linklike" onClick={onClear}>
          Clear
        </button>
      </p>
    </div>
  )
}

/** REQ-39 / SEQ-9: shown with the built-in wizard's answer when the AI did not answer. */
export function AiUnavailableNotice() {
  return (
    <p className="ai-notice" data-testid="ai-notice">
      {AI_UNAVAILABLE_NOTICE}
    </p>
  )
}

/** REQ-66: shown with the built-in wizard's answer when the ask call gets a 401. */
export function SessionEndedNotice() {
  return (
    <p className="ai-notice" data-testid="ai-notice">
      {SESSION_ENDED_NOTICE} <a href={SIGN_IN_PATH}>{SIGN_IN_TEXT}</a>
    </p>
  )
}

export function AskPending() {
  return (
    <p className="answer-pending" role="status">
      Looking up the answer…
    </p>
  )
}
