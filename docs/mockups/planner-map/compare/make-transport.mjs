// Stand-in data for the "Families without a car" Compare-with layer (task T3).
// This is mock-up data, not the Build (REQ-9, Z-5).
//
// Run from the repo root:  node docs/mockups/planner-map/compare/make-transport.mjs
// Reads data/external/census-acs/ (never writes there).
// Writes docs/mockups/planner-map/data/transport.standin.json, keyed by tract GEOID.
// Tract-level fields only (REQ-4, REQ-17).
//
// Source: ACS 2024 5-year table B08201 via the Census Reporter API (DS-X7b).
// No-vehicle share is a proxy for transport need, not a validated measure (finding F-1).
//
// Reliability rule (ACS General Handbook, chapter 8):
// - MOE of a proportion p = x / X:  sqrt(MOEx^2 - p^2 * MOEX^2) / X. When the value under the
//   root is negative, use the + form instead.
// - Coefficient of variation CV = (MOE / 1.645) / p. ACS margins of error are at 90%.
// - Bands: CV under 30% is 'closer'; 30% to under 1 / 1.645 (about 61%) is 'rough';
//   1 / 1.645 or more is 'veryRough'. At CV = 1 / 1.645 the margin of error equals the
//   estimate, so the 90% range reaches zero. A zero estimate is 'veryRough'.

import { readFileSync, writeFileSync } from 'node:fs'

const IN = 'data/external/census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv'
const RECORDS = 'docs/mockups/planner-map/data/records.standin.json'
const OUT = 'docs/mockups/planner-map/data/transport.standin.json'
const Z90 = 1.645
const CV_CLOSER = 0.3
const CV_VERY_ROUGH = 1 / Z90
const EXPECTED_TRACTS = 490

const lines = readFileSync(IN, 'utf8').trim().split(/\r?\n/)
const header = lines[0].split(',')
const want = [
  'geoid',
  'total_households',
  'no_vehicle_households',
  'pct_no_vehicle',
  'moe_total_households',
  'moe_no_vehicle_households',
]
if (want.some((c, i) => header[i] !== c)) throw new Error(`${IN}: unexpected header ${header}`)

const recordIds = new Set(JSON.parse(readFileSync(RECORDS, 'utf8')).tracts.map((t) => t.geoid))
const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d

const tracts = {}
const bands = { closer: 0, rough: 0, veryRough: 0, blank: 0 }
for (const line of lines.slice(1)) {
  const [geoid, totS, noCarS, pctS, moeTotS, moeNoCarS] = line.split(',')
  if (!/^12(069|095|097|117)\d{6}$/.test(geoid)) throw new Error(`bad GEOID ${geoid}`)
  if (!recordIds.has(geoid)) throw new Error(`${geoid} is not in ${RECORDS}`)
  const X = Number(totS)
  const x = Number(noCarS)
  const MX = Number(moeTotS)
  const Mx = Number(moeNoCarS)
  if (!(X > 0)) {
    // No households: no share can be computed.
    tracts[geoid] = { pct: null, households: X, noCar: x, moePct: null, cv: null, band: null }
    bands.blank++
    continue
  }
  const p = x / X
  const pctFile = Number(pctS)
  if (pctS === '' || Math.abs(p * 100 - pctFile) > 0.06)
    throw new Error(`${geoid}: share ${p * 100} does not match the file value ${pctS}`)
  let rad = Mx * Mx - p * p * MX * MX
  if (rad < 0) rad = Mx * Mx + p * p * MX * MX
  const moeP = Math.sqrt(rad) / X
  const cv = p > 0 ? moeP / Z90 / p : null
  const band =
    cv === null || cv >= CV_VERY_ROUGH ? 'veryRough' : cv < CV_CLOSER ? 'closer' : 'rough'
  bands[band]++
  tracts[geoid] = {
    pct: round(p * 100, 1),
    households: X,
    noCar: x,
    moePct: round(moeP * 100, 1),
    cv: cv === null ? null : round(cv, 3),
    band,
  }
}
const count = Object.keys(tracts).length
if (count !== EXPECTED_TRACTS) throw new Error(`expected ${EXPECTED_TRACTS} tracts, got ${count}`)

const out = {
  source: 'DS-X7b: ACS 2024 5-year B08201 via the Census Reporter API',
  file: IN,
  rule: {
    share: 'no_vehicle_households / total_households',
    moe: 'ACS proportion formula; margins of error are at 90%',
    z: Z90,
    cvCloser: CV_CLOSER,
    cvVeryRough: round(CV_VERY_ROUGH, 4),
  },
  bands,
  tracts,
}
writeFileSync(OUT, JSON.stringify(out) + '\n')
console.log(`wrote ${OUT}: ${count} tracts`, bands)
