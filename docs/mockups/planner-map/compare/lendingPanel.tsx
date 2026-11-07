// Sidebar panel for the "Where small business loans went" Compare-with layer. Owner: task T5.
// See lending.ts for the purpose and the honesty rules (finding F-3).
import { useState } from 'react'
import { COLORS } from '../mapStyle'
import { fmt } from '../model'
import type { Tract } from '../model'
import type { CompareContext } from './types'
import {
  BANDS,
  SOURCES,
  bandOf,
  derive,
  inTen,
  loansWord,
  median,
  rateWords,
  showTract,
} from './lendingData'
import type { Derived, LendingTract, Row } from './lendingData'
import './lending.css'

// ---------------- Panel ----------------

const dotSwatch = {
  background: `radial-gradient(circle, ${COLORS.primary700} 1.1px, #fff 1.4px) 0 0 / 5px 5px`,
}

export function Panel({ ctx }: { ctx: CompareContext }) {
  const [showAll, setShowAll] = useState(false)
  const d = derive(ctx)
  if (!d) return <p className="secondary">The loan data did not load.</p>
  const { high, other, cut, closer, file } = d

  const drawn = ctx.records.tracts.filter((t) => t.drawn && t.cls !== 'insufficient')
  const per = (t: Tract) => file.tracts[t.geoid]?.per1k ?? null
  const zeroCount = drawn.filter((t) => per(t) === 0).length
  const bandCount = (b: (typeof BANDS)[number]) =>
    drawn.filter((t) => {
      const v = per(t)
      return v !== null && bandOf(v) === b
    }).length

  const medHigh = median(high.map((r) => r.l.per1k))
  const medOther = median(other.map((r) => r.l.per1k))
  const otherLow = other.filter((r) => r.l.per1k < cut).length
  const typical =
    Math.round(medHigh) === Math.round(medOther)
      ? `In both groups, a typical neighborhood got ${rateWords(medHigh)} for every 1,000 people since 2010.`
      : `A typical high-need neighborhood got ${rateWords(medHigh)} for every 1,000 people since 2010. A typical other neighborhood got ${rateWords(medOther)}.`
  const list = showAll ? closer : closer.slice(0, 5)

  return (
    <div className="lending-panel">
      <p className="lending-headline">
        High-need neighborhoods got about as many SBA small business loans for each person as other
        neighborhoods. We found no clear link between food need and SBA loans.
      </p>
      <p className="secondary">{typical}</p>

      <h3 className="lending-h">SBA loans for every 1,000 people, since 2010</h3>
      <ul className="legend">
        <li>
          <span className="swatch" style={dotSwatch} />
          <span>No loans found</span>
          <span className="count">{zeroCount}</span>
        </li>
        {BANDS.map((b) => (
          <li key={b.id}>
            <span className="swatch" style={{ background: b.color }} />
            <span>{b.label}</span>
            <span className="count">{bandCount(b)}</span>
          </li>
        ))}
        <li>
          <span
            className="swatch"
            style={{ background: 'transparent', border: `2.5px solid ${COLORS.desert}` }}
          />
          <span>High food need (orange outline)</span>
          <span className="count">{high.length}</span>
        </li>
      </ul>

      <h3 className="lending-h">Worth a closer look</h3>
      <p className="secondary">
        {closer.length} high-need neighborhoods got fewer loans for each person than most
        neighborhoods. The lowest first:
      </p>
      <ol className="lending-list">
        {list.map((r) => (
          <li key={r.t.geoid}>
            <button className="linklike" onClick={() => showTract(ctx.getMap(), r.t)}>
              {r.t.name}, {r.t.county}
            </button>{' '}
            <span className="count">
              {r.l.loans === 0 ? 'no loans' : `${loansWord(r.l.loans)} in all`}
            </span>
          </li>
        ))}
      </ol>
      {closer.length > 5 && (
        <button className="linklike lending-more" onClick={() => setShowAll(!showAll)}>
          {showAll ? 'Show fewer' : `Show all ${closer.length}`}
        </button>
      )}
      <p className="secondary">
        This is about as common in other neighborhoods: {inTen(otherLow / other.length)} of them (
        {otherLow} of {other.length}) also got fewer loans than most. So this list does not show
        that high-need places are left out. It shows places where a lender or adviser may want to
        ask why.
      </p>

      <HowWeKnow d={d} />
    </div>
  )
}

function HowWeKnow({ d }: { d: Derived }) {
  const { set, high, other, cut, file } = d
  const med = (rows: Row[], f: (l: LendingTract) => number | null) =>
    median(rows.map((r) => f(r.l)).filter((v): v is number => v !== null))
  const zero = (rows: Row[]) => rows.filter((r) => r.l.loans === 0).length
  const low = (rows: Row[]) => rows.filter((r) => r.l.per1k < cut).length
  const few = high.filter((r) => r.l.loans <= 5).length
  const groups: [string, Row[]][] = [
    ['High need (Classic Food Desert)', high],
    ['No gap flagged', other],
  ]
  const usd = (v: number) => `$${fmt.format(Math.round(v))}`
  return (
    <details className="how-we-know">
      <summary>How we know this</summary>
      <p>
        <strong>What we counted.</strong> SBA 7(a) and 504 loans approved in fiscal years 2010 to
        2026 (2026 is partial, to 30 September 2026), placed in a neighborhood (census tract) by the
        borrower&apos;s mailing address with the Census Bureau geocoder (DS-X5). Each count is
        divided by the tract&apos;s 2020 Census population, the sum of its 2020 blocks (DS-X24).
        Stand-in file <span className="mono">lending.standin.json</span> ({file.generated}).
      </p>
      <p>
        <strong>Which tracts.</strong> {set.length} tracts: {high.length} high-need and{' '}
        {other.length} &ldquo;no gap&rdquo; tracts. Tracts with Insufficient data are left out (one
        has no households, one is water). &ldquo;Fewer than most&rdquo; means below the median of
        these {set.length} tracts: {cut.toFixed(2)} loans per 1,000 residents, all years.
      </p>
      <table className="lending-table">
        <thead>
          <tr>
            <th>Group</th>
            <th>Tracts</th>
            <th>Median loans per 1,000, all years</th>
            <th>Median loans per 1,000, FY2020 to 2026</th>
            <th>Median gross $ per 1,000, all years</th>
            <th>Below the median</th>
            <th>No loans</th>
          </tr>
        </thead>
        <tbody>
          {groups.map(([name, rows]) => (
            <tr key={name}>
              <th>{name}</th>
              <td>{rows.length}</td>
              <td>{med(rows, (l) => l.per1k).toFixed(1)}</td>
              <td>{med(rows, (l) => l.per1k20).toFixed(1)}</td>
              <td>{usd(med(rows, (l) => l.usdPer1k))}</td>
              <td>
                {low(rows)} ({((100 * low(rows)) / rows.length).toFixed(1)}%)
              </td>
              <td>{zero(rows)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        Spearman rank correlation between loans per 1,000 residents (all years) and food need, over{' '}
        {file.analysisTracts} tracts: {file.spearman.pctSnap.toFixed(3)} with SNAP share and{' '}
        {file.spearman.pctPoverty.toFixed(3)} with the poverty rate. Both are close to zero. The
        significance tests (Mann-Whitney, Fisher exact) and checks with other denominators are in
        finding F-3 (<span className="mono">docs/analysis/need-vs-sba-lending.md</span>). No
        difference found is not proof that the two groups are equal.
      </p>
      <p>
        <strong>Limits.</strong>
      </p>
      <ul>
        <li>
          Loans are placed by the borrower&apos;s mailing address. A tract&apos;s loans are not
          loans to the people who live there, and not always to a business there.
        </li>
        <li>
          Approved loans show where lending went. They do not show who needs a loan, applications
          that were denied, or businesses that did not apply. No file in the repo measures need for
          capital, so the claim that food need and need for SBA loans go together cannot be tested.
        </li>
        <li>
          Not every loan could be placed on the map (DS-X5 README, limit 1). The share not placed is
          higher in Lake, Seminole and Osceola than in Orange. Counts are undercounts, so a low
          count is not proof of low lending.
        </li>
        <li>
          This is lending per resident, not per business. The repo has no business counts by tract.
          A business district with few residents looks like high lending for that reason only.
        </li>
        <li>
          SBA 7(a) and 504 are only part of small business credit. Bank loans, microloans and CDFI
          loans are not in the data.
        </li>
        <li>
          Small numbers: {few} of {high.length} high-need tracts have 5 or fewer placed loans. One
          or two loans change their rate a lot.
        </li>
        <li>
          Tract level only. This says nothing about single households or businesses. Some rows in
          the SBA file may be listed twice (DS-X5 README, limit 3); none were removed.
        </li>
      </ul>
      <p>Sources: {SOURCES.map((s) => `${s.id} (${s.label})`).join('; ')}.</p>
    </details>
  )
}
