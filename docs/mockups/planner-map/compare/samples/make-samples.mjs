// Makes the two SAMPLE files for the "Your own data" Compare-with layer (compare/imported.tsx).
// They are made from public data already in the repo. They are NOT partner data.
//
//   node docs/mockups/planner-map/compare/samples/make-samples.mjs
//
// Inputs (read only):
//   data/external/census-acs/acs2024_s1901_median_household_income_central_fl_tracts.csv
//     Census ACS 2020-2024 table S1901 (DS-H3), checked against B19013 (DS-X28).
//   docs/mockups/planner-map/data/sites.standin.geojson
//     Second Harvest food finder site locations (DS-X12). Redistribution permission was not
//     obtained; the data is already public (issue #4).
// Outputs (in this folder):
//   SAMPLE-census-median-household-income.csv
//   SAMPLE-second-harvest-sites-subset.geojson
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '../../../../..')

// ---- CSV: tract median household income (one number column per tract, plus households) ----
const incomePath = join(
  repo,
  'data/external/census-acs/acs2024_s1901_median_household_income_central_fl_tracts.csv',
)
const lines = readFileSync(incomePath, 'utf8').replace(/\r\n/g, '\n').trim().split('\n')
const header = lines[0].split(',')
const col = (name) => {
  const i = header.indexOf(name)
  if (i < 0) throw new Error(`column ${name} not found in ${incomePath}`)
  return i
}
const [iGeoid, iHouseholds, iIncome] = [
  col('geoid'),
  col('households'),
  col('median_household_income'),
]
// Quoted fields (for example "250,000+") occur only after the columns we use; stop if a quote
// ever comes before them, because the plain split below would then shift the columns.
const lastUsed = Math.max(iGeoid, iHouseholds, iIncome)
const out = ['geoid,median_household_income,households,sample_note']
const note = 'SAMPLE from Census ACS S1901 (DS-H3) - not partner data'
for (const line of lines.slice(1)) {
  const q = line.indexOf('"')
  if (q >= 0 && line.slice(0, q).split(',').length <= lastUsed + 1)
    throw new Error(`quoted field before a used column: ${line}`)
  const f = line.split(',')
  // A blank income stays blank (the 1 lower-bound and 3 unavailable tracts), so the import
  // panel shows how it reports rows with no number.
  out.push([f[iGeoid], f[iIncome], f[iHouseholds], note].join(','))
}
if (out.length !== 491) throw new Error(`expected 490 tract rows, got ${out.length - 1}`)
writeFileSync(join(here, 'SAMPLE-census-median-household-income.csv'), out.join('\n') + '\n')

// ---- GeoJSON: every 10th public site location (some fall outside the four counties) ----
const sites = JSON.parse(
  readFileSync(join(repo, 'docs/mockups/planner-map/data/sites.standin.geojson'), 'utf8'),
)
const picked = sites.features
  .filter((_, i) => i % 10 === 0)
  .map((f) => ({
    type: 'Feature',
    properties: { name: f.properties.name },
    geometry: f.geometry,
  }))
const fc = {
  type: 'FeatureCollection',
  name: 'SAMPLE - Second Harvest site locations (subset)',
  description:
    'SAMPLE, not partner data. Every 10th public Second Harvest food finder site (DS-X12) from ' +
    'docs/mockups/planner-map/data/sites.standin.geojson. Redistribution permission was not obtained.',
  features: picked,
}
writeFileSync(
  join(here, 'SAMPLE-second-harvest-sites-subset.geojson'),
  JSON.stringify(fc, null, 1) + '\n',
)
console.log(`CSV rows: ${out.length - 1}. GeoJSON points: ${picked.length}.`)
