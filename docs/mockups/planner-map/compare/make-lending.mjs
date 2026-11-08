// Stand-in data for the "Where small business loans went" Compare-with layer (task T5).
//
// Run from the repo root:  node docs/mockups/planner-map/compare/make-lending.mjs
// Reads data/external/sba-loans/ (DS-X5) and the mock-up's records.standin.json (2020
// population, DS-X24, and the food need class). Writes docs/mockups/planner-map/data/
// lending.standin.json. Never writes under data/.
//
// The numbers follow docs/analysis/need-vs-sba-lending.md (finding F-3): the same
// 488-tract analysis set, the same denominator (2020 population), the same median cut.
// The script stops if its numbers do not match that note. Tract-level fields only (REQ-4).

import { readFileSync, writeFileSync } from 'node:fs'

const RECORDS = 'docs/mockups/planner-map/data/records.standin.json'
const SBA = 'data/external/sba-loans/sba_loans_by_tract_central_fl.csv'
const OUT = 'docs/mockups/planner-map/data/lending.standin.json'

function check(ok, msg) {
  if (!ok) throw new Error(`make-lending: ${msg}`)
}

// ---- inputs ----
const rec = JSON.parse(readFileSync(RECORDS, 'utf8'))
check(rec.tracts.length === 490, 'records: expected 490 tracts')

const lines = readFileSync(SBA, 'utf8').trim().split(/\r?\n/)
const head = lines[0].split(',')
const sba = new Map()
for (const line of lines.slice(1)) {
  const v = line.split(',')
  const row = Object.fromEntries(head.map((k, i) => [k, k === 'geoid' ? v[i] : Number(v[i])]))
  sba.set(row.geoid, row)
}
check(sba.size === 490, 'SBA: expected 490 tracts')
const placed = [...sba.values()].reduce((s, r) => s + r.loans_total, 0)
check(placed === 6994, `SBA: README says 6,994 placed loans, found ${placed}`)

// ---- helpers ----
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = s.length / 2
  return s.length % 2 ? s[Math.floor(m)] : (s[m - 1] + s[m]) / 2
}
// Average ranks (ties share the mean rank), as scipy.stats.rankdata does.
function ranks(xs) {
  const idx = xs.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0])
  const out = new Array(xs.length)
  for (let i = 0; i < idx.length;) {
    let j = i
    while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++
    const r = (i + j) / 2 + 1
    for (let k = i; k <= j; k++) out[idx[k][1]] = r
    i = j + 1
  }
  return out
}
function pearson(x, y) {
  const mx = x.reduce((a, b) => a + b, 0) / x.length
  const my = y.reduce((a, b) => a + b, 0) / y.length
  let sxy = 0
  let sxx = 0
  let syy = 0
  for (let i = 0; i < x.length; i++) {
    sxy += (x[i] - mx) * (y[i] - my)
    sxx += (x[i] - mx) ** 2
    syy += (y[i] - my) ** 2
  }
  return sxy / Math.sqrt(sxx * syy)
}
const spearman = (x, y) => pearson(ranks(x), ranks(y))
const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d

// ---- per-tract rates ----
const rows = rec.tracts.map((t) => {
  const s = sba.get(t.geoid)
  check(s, `SBA: no row for ${t.geoid}`)
  const loans = s.loans_total
  const loans20 = s.loans_7a_fy2020_2026 + s.loans_504_fy2020_2026
  const usd = s.gross_usd_total
  const usd20 = s.gross_usd_7a_fy2020_2026 + s.gross_usd_504_fy2020_2026
  const per = (v) => (t.pop2020 > 0 ? (v / t.pop2020) * 1000 : null)
  return {
    t,
    loans,
    loans20,
    usd,
    usd20,
    per1k: per(loans),
    per1k20: per(loans20),
    usdPer1k: per(usd),
    usdPer1k20: per(usd20),
  }
})

// Analysis set (F-3): desert and nogap tracts with people. 488 tracts.
const inSet = (r) => (r.t.cls === 'desert' || r.t.cls === 'nogap') && r.t.pop2020 > 0
const set = rows.filter(inSet)
check(set.length === 488, `analysis set: expected 488 tracts, found ${set.length}`)

const cut = median(set.map((r) => r.per1k))
check(
  cut.toFixed(2) === '1.80',
  `median loans per 1,000 should be 1.80 (F-3), found ${cut.toFixed(2)}`,
)

const groupOf = (r) =>
  !inSet(r)
    ? null
    : `${r.t.cls === 'desert' ? 'high-need' : 'other'}-${r.per1k < cut ? 'low' : 'high'}-lending`

const groups = {}
for (const r of set) groups[groupOf(r)] = (groups[groupOf(r)] ?? 0) + 1
const want = {
  'high-need-low-lending': 50,
  'high-need-high-lending': 47,
  'other-low-lending': 194,
  'other-high-lending': 197,
}
for (const [k, v] of Object.entries(want))
  check(groups[k] === v, `2x2 ${k}: expected ${v} (F-3), found ${groups[k]}`)

const rhoSnap = spearman(
  set.map((r) => r.per1k),
  set.map((r) => r.t.pctSnap),
)
const rhoPoverty = spearman(
  set.map((r) => r.per1k),
  set.map((r) => r.t.pctPoverty),
)
check(
  rhoSnap.toFixed(3) === '-0.051',
  `Spearman vs SNAP share should be -0.051 (F-3), found ${rhoSnap.toFixed(3)}`,
)
check(
  rhoPoverty.toFixed(3) === '-0.021',
  `Spearman vs poverty rate should be -0.021 (F-3), found ${rhoPoverty.toFixed(3)}`,
)

// ---- output ----
const out = {
  generated: new Date().toISOString().slice(0, 10),
  note: 'Stand-in for the planner-map mock-up. SBA 7(a) and 504 loans (DS-X5) placed by borrower mailing address, per 1,000 residents (2020 Census, DS-X24). Method and limits: docs/analysis/need-vs-sba-lending.md (F-3).',
  analysisTracts: set.length,
  medianLoansPer1k: round(cut, 4),
  spearman: { pctSnap: round(rhoSnap, 4), pctPoverty: round(rhoPoverty, 4) },
  tracts: Object.fromEntries(
    rows.map((r) => [
      r.t.geoid,
      {
        loans: r.loans,
        loans20: r.loans20,
        per1k: r.per1k === null ? null : round(r.per1k, 6),
        per1k20: r.per1k20 === null ? null : round(r.per1k20, 6),
        usdPer1k: r.usdPer1k === null ? null : Math.round(r.usdPer1k),
        usdPer1k20: r.usdPer1k20 === null ? null : Math.round(r.usdPer1k20),
        group: groupOf(r),
      },
    ]),
  ),
}
writeFileSync(OUT, JSON.stringify(out) + '\n')
console.log(
  `Wrote ${OUT}: ${rows.length} tracts, median ${cut.toFixed(2)} loans per 1,000, ` +
    `2x2 ${JSON.stringify(groups)}, Spearman SNAP ${rhoSnap.toFixed(3)}, poverty ${rhoPoverty.toFixed(3)}.`,
)
