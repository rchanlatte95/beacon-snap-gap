// Stand-in data for the planner-map mock-up. This is NOT the Build (REQ-9, Z-5).
// The Build is contract-first work: it writes public/data/tracts.geojson after its
// CONTRACTS and RED phases. This script only gives the mock-up realistic values.
//
// Run from the repo root:  node docs/mockups/planner-map/make-standin.mjs
// Reads data/** (never writes there). Writes docs/mockups/planner-map/data/*.json.
//
// Stand-in limits, shown in the mock-up UI:
// - Reach and load use straight-line distance (REACH_MILES from each populated 2020
//   block point to a Second Harvest site). The decided rule (Z-2, Z-2d) is a 30-minute
//   drive, which needs a routing engine that is not in the repo.
// - The confidence label rule is a placeholder. No rule is decided.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { inflateRawSync } from 'node:zlib'
import { join } from 'node:path'

const REACH_MILES = 10
const COUNTIES = { '069': 'Lake', '095': 'Orange', '097': 'Osceola', '117': 'Seminole' }
const H = 'data/hackathon/beacon-example-datasets'
const X = 'data/external'
const OUT = 'docs/mockups/planner-map/data'

// ---- tiny zip reader (deflate or stored entries, no zip64) ----
function readZipEntry(zipPath, entryName) {
  const buf = readFileSync(zipPath)
  let eocd = buf.length - 22
  while (eocd >= 0 && buf.readUInt32LE(eocd) !== 0x06054b50) eocd--
  if (eocd < 0) throw new Error(`${zipPath}: no zip end record`)
  const count = buf.readUInt16LE(eocd + 10)
  let p = buf.readUInt32LE(eocd + 16)
  for (let i = 0; i < count; i++) {
    const method = buf.readUInt16LE(p + 10)
    const size = buf.readUInt32LE(p + 20)
    const nameLen = buf.readUInt16LE(p + 28)
    const extraLen = buf.readUInt16LE(p + 30)
    const commentLen = buf.readUInt16LE(p + 32)
    const local = buf.readUInt32LE(p + 42)
    const name = buf.toString('utf8', p + 46, p + 46 + nameLen)
    if (name === entryName) {
      const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28)
      const raw = buf.subarray(start, start + size)
      return (method === 8 ? inflateRawSync(raw) : raw).toString('utf8')
    }
    p += 46 + nameLen + extraLen + commentLen
  }
  throw new Error(`${zipPath}: entry "${entryName}" not found`)
}

// ---- RFC 4180 CSV parser -> array of objects keyed by header ----
function parseCsv(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1)
  const rows = []
  let row = []
  let field = ''
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i++
        } else quoted = false
      } else field += c
    } else if (c === '"') quoted = true
    else if (c === ',') {
      row.push(field)
      field = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else field += c
  }
  if (field !== '' || row.length) {
    row.push(field)
    rows.push(row)
  }
  const [header, ...body] = rows
  return body
    .filter((r) => r.length > 1)
    .map((r) => Object.fromEntries(header.map((h, j) => [h, r[j] ?? ''])))
}

const inScope = (geoid) => geoid.startsWith('12') && COUNTIES[geoid.slice(2, 5)] !== undefined
const num = (v) => {
  if (v === undefined || v === null) return null
  const s = String(v).replace(/,/g, '').trim()
  if (s === '' || s === '-' || s === 'N' || s === '(X)' || s.includes('*')) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}
const csv = (path) => parseCsv(readFileSync(path, 'utf8'))
const byGeoid = (rows, key, fix = (g) => g) =>
  new Map(rows.map((r) => [fix(r[key]), r]).filter(([g]) => inScope(g)))
const acsGeoid = (g) => g.replace('1400000US', '')

// ---- inputs ----
const s2201 = byGeoid(
  parseCsv(readZipEntry(`${H}/Households and Households Receiving SNAP Census, S2201.zip`, 'ACSST5Y2024.S2201-Data.csv')),
  'GEO_ID',
  acsGeoid,
)
const s1701 = byGeoid(
  parseCsv(readZipEntry(`${H}/Population - Below Poverty Level.zip`, 'ACSST5Y2024.S1701-Data.csv')),
  'GEO_ID',
  acsGeoid,
)
const sramZip = `${H}/Low Grocery Access - 1_2 or 10 miles_2025-sram-fara-data.zip`
const sramDD = byGeoid(parseCsv(readZipEntry(sramZip, 'SRAM Driving Distance Data.csv')), 'CensusTract20')
const sramGen = byGeoid(parseCsv(readZipEntry(sramZip, 'SRAM General Tract Characteristics Data.csv')), 'CensusTract20')
const places = byGeoid(
  csv(`${H}/Transportation_PLACES__Census_Tract_Data_(GIS_Friendly_Format),_2025_release .csv`),
  'TractFIPS',
)
const coverage = byGeoid(csv(`${X}/second-harvest-food-finder/central_fl_tract_pantry_coverage.csv`), 'geoid')
const noVehicle = byGeoid(csv(`${X}/census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv`), 'geoid')
const nri = byGeoid(csv(`${X}/fema-nri/fema_nri_central_fl_tracts.csv`), 'TRACTFIPS')
const sites = csv(`${X}/second-harvest-food-finder/second_harvest_food_finder_locations.csv`)
const blocks = csv(`${X}/census-2020-blocks/central-fl-blocks-2020.csv`)
const shapes = JSON.parse(readFileSync(`${X}/geography/central_fl_tracts_2020.geojson`, 'utf8'))
const cbpp = csv(`${X}/cbpp-snap-tracker/cbpp_florida_snap_monthly.csv`)
const meals = csv(`${X}/feeding-america/feeding_america_map_the_meal_gap_2024_central_fl_counties.csv`)

// ---- distance (straight-line, miles) ----
const R_MI = 3958.8
const rad = (d) => (d * Math.PI) / 180
function miles(lat1, lon1, lat2, lon2) {
  const a =
    Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return 2 * R_MI * Math.asin(Math.sqrt(a))
}
const sitePts = sites.map((s) => ({ id: s.storeid, lat: num(s.lat), lng: num(s.lng), tract: s.tract_geoid }))

// Tract sums only. No block-level value leaves this loop (REQ-4, REQ-17).
const popSum = new Map()
for (const b of blocks) {
  const g = b.geoid20.slice(0, 11)
  const pop = num(b.pop20) ?? 0
  const t = popSum.get(g) ?? { pop: 0, inReach: 0, sites: new Set(), latW: 0, lonW: 0 }
  t.pop += pop
  if (pop > 0) {
    const lat = num(b.lat)
    const lon = num(b.lon)
    t.latW += lat * pop
    t.lonW += lon * pop
    let reached = false
    for (const s of sitePts) {
      if (miles(lat, lon, s.lat, s.lng) <= REACH_MILES) {
        reached = true
        t.sites.add(s.id)
      }
    }
    if (reached) t.inReach += pop
  }
  popSum.set(g, t)
}

// ---- Z-1 cut: Python statistics.quantiles(n=4), default exclusive method ----
const allGeoids = [...coverage.keys()].sort()
const povertyOf = (g) => num(s1701.get(g)?.S1701_C03_001E)
const povVals = allGeoids
  .map(povertyOf)
  .filter((v) => v !== null)
  .sort((a, b) => a - b)
function quantileExclusive(data, i, n) {
  const m = data.length + 1
  const j = Math.floor((i * m) / n)
  const delta = i * m - j * n
  return (data[j - 1] * (n - delta) + data[j] * delta) / n
}
const p75 = quantileExclusive(povVals, 3, 4)

// ---- per-tract records ----
const shapeById = new Map(shapes.features.map((f) => [f.properties.TRACTFIPS, f]))
const round = (v, d = 1) => (v === null ? null : Math.round(v * 10 ** d) / 10 ** d)
const records = allGeoids.map((g) => {
  const snap = s2201.get(g)
  const gen = sramGen.get(g)
  const pl = places.get(g)
  const nv = noVehicle.get(g)
  const fz = nri.get(g)
  const ps = popSum.get(g) ?? { pop: 0, inReach: 0, sites: new Set(), latW: 0, lonW: 0 }
  const households = num(snap?.S2201_C01_001E)
  const pctSnap = num(snap?.S2201_C04_001E)
  const pctPoverty = povertyOf(g)
  const lilaDD = num(sramDD.get(g)?.DD_SRAM_LILATracts_halfAnd10)
  const sitesInTract = sitePts.filter((s) => s.tract === g).length
  const highNeed = pctPoverty !== null && lilaDD !== null && pctPoverty >= p75 && lilaDD === 1
  const insufficient = pctPoverty === null || pctSnap === null || lilaDD === null
  const indicators = {
    'Poverty rate (ACS S1701)': pctPoverty,
    'SNAP households (ACS S2201)': pctSnap,
    'Low income, low access, driving distance (USDA SRAM)': lilaDD,
    'No-vehicle households (ACS B08201)': num(nv?.pct_no_vehicle),
    'Food stamps, adults (CDC PLACES)': num(pl?.FOODSTAMP_CrudePrev),
    'Food insecurity (CDC PLACES)': num(pl?.FOODINSECU_CrudePrev),
    'Lack of transportation (CDC PLACES)': num(pl?.LACKTRPT_CrudePrev),
    'FEMA National Risk Index rating': fz?.RISK_RATNG || null,
  }
  const missing = Object.entries(indicators)
    .filter(([, v]) => v === null)
    .map(([k]) => k)
  const sitesInReach = ps.sites.size
  return {
    geoid: g,
    name: (coverage.get(g)?.NAME ?? '').split(';')[0],
    county: COUNTIES[g.slice(2, 5)],
    cls: insufficient ? 'insufficient' : highNeed ? 'desert' : 'nogap',
    drawn: shapeById.has(g),
    households,
    snapHouseholds: num(snap?.S2201_C03_001E),
    pctSnap,
    pctPoverty,
    lilaDD,
    urban: num(gen?.Urban),
    medianFamilyIncome: num(gen?.MedianFamilyIncome),
    groupQuartersPct: num(gen?.PCTGQTRS),
    noVehiclePct: num(nv?.pct_no_vehicle),
    placesFoodInsecurity: num(pl?.FOODINSECU_CrudePrev),
    nriRisk: fz?.RISK_RATNG || null,
    socialVulnerability: fz?.SOVI_RATNG || null,
    pop2020: Math.round(ps.pop),
    sitesInTract,
    standinReachPct: ps.pop > 0 ? round((100 * ps.inReach) / ps.pop) : null,
    standinSitesInReach: sitesInReach,
    standinLoad: sitesInReach > 0 && ps.pop > 0 ? Math.round(ps.pop / sitesInReach) : null,
    missing,
    centroid: ps.pop > 0 ? [round(ps.lonW / ps.pop, 4), round(ps.latW / ps.pop, 4)] : null,
  }
})

// ---- cross-checks against the files the manifest counts come from ----
for (const r of records) {
  const c = coverage.get(r.geoid)
  if (num(c.pct_hh_snap) !== r.pctSnap || num(c.pct_poverty) !== r.pctPoverty)
    throw new Error(`${r.geoid}: rates differ from the coverage CSV`)
  if (num(c.second_harvest_sites) !== r.sitesInTract)
    throw new Error(`${r.geoid}: site count differs from the coverage CSV`)
}
const counts = { desert: 0, nogap: 0, insufficient: 0 }
for (const r of records) counts[r.cls]++
if (records.length !== 490 || counts.desert !== 97 || counts.nogap !== 391 || counts.insufficient !== 2)
  throw new Error(`class counts ${JSON.stringify(counts)} do not match the manifest (97/391/2)`)

// ---- geometry: tracts and county outlines (edges not shared inside a county) ----
const r5 = (c) => [Math.round(c[0] * 1e5) / 1e5, Math.round(c[1] * 1e5) / 1e5]
const recById = new Map(records.map((r) => [r.geoid, r]))
const tractFeatures = []
const edges = new Map()
for (const f of shapes.features) {
  const g = f.properties.TRACTFIPS
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates
  const rounded = polys.map((poly) => poly.map((ring) => ring.map(r5)))
  tractFeatures.push({
    type: 'Feature',
    id: Number(g.slice(2)),
    properties: { geoid: g, cls: recById.get(g).cls },
    geometry: { type: 'MultiPolygon', coordinates: rounded },
  })
  const county = g.slice(2, 5)
  for (const poly of rounded)
    for (const ring of poly)
      for (let i = 0; i < ring.length - 1; i++) {
        const a = ring[i].join(',')
        const b = ring[i + 1].join(',')
        const key = `${county}|${a < b ? a + ';' + b : b + ';' + a}`
        const e = edges.get(key) ?? { n: 0, seg: [ring[i], ring[i + 1]], county }
        e.n++
        edges.set(key, e)
      }
}
const countyLines = Object.keys(COUNTIES).map((c) => ({
  type: 'Feature',
  properties: { county: COUNTIES[c] },
  geometry: {
    type: 'MultiLineString',
    coordinates: [...edges.values()].filter((e) => e.county === c && e.n === 1).map((e) => e.seg),
  },
}))
const countyLabels = Object.entries(COUNTIES).map(([c, name]) => {
  const rs = records.filter((r) => r.geoid.slice(2, 5) === c && r.centroid)
  const w = rs.reduce((s, r) => s + r.pop2020, 0)
  return {
    name,
    lngLat: [
      round(rs.reduce((s, r) => s + r.centroid[0] * r.pop2020, 0) / w, 3),
      round(rs.reduce((s, r) => s + r.centroid[1] * r.pop2020, 0) / w, 3),
    ],
  }
})

// All 424 sites, including the 7-county sites outside the 4 counties: they count for reach.
const sitesOut = sites.map((s) => ({
    type: 'Feature',
    properties: { name: s.name, address: s.address, hours: s.hours_text, county: s.county },
    geometry: { type: 'Point', coordinates: [num(s.lng), num(s.lat)] },
  }))

mkdirSync(OUT, { recursive: true })
const write = (name, obj) => writeFileSync(join(OUT, name), JSON.stringify(obj))
write('tracts.standin.geojson', { type: 'FeatureCollection', features: tractFeatures })
write('counties.standin.geojson', { type: 'FeatureCollection', features: countyLines })
write('sites.standin.geojson', { type: 'FeatureCollection', features: sitesOut })
write('records.standin.json', {
  note: 'Stand-in data for the planner-map mock-up. Not the Build output.',
  generated: new Date().toISOString().slice(0, 10),
  povertyCut: { value: round(p75, 3), method: 'Python statistics.quantiles(n=4), exclusive', tracts: povVals.length },
  standinReachMiles: REACH_MILES,
  counts,
  countyLabels,
  snapTrend: cbpp.map((r) => ({ month: r.month, participants: num(r.usda_total_participants) })),
  mealGap: meals
    .filter((m) => m.demographic === 'overall')
    .map((m) => ({ county: m.county, rate: m.food_insecurity_rate, people: num(m.food_insecure_population) })),
  tracts: records,
})
console.log('poverty cut', p75, 'counts', counts, 'drawn', tractFeatures.length, 'sites', sitesOut.length)
