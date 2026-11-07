// Sidebar panel for the "Where our data has gaps" Compare-with layer (task T4).
import type { CompareContext } from './types'
import type { Tract } from '../model'
import { GROUP_QUARTERS_PCT, NO_MOE, SMALL_HOUSEHOLDS, fmt } from '../model'
import { COLORS } from '../mapStyle'
import type { GapLevel } from './blindspotsData'
import { FILL, LEVELS, LEVEL_LABEL, allPlaces, hatchSwatch, listText, plain, summarize } from './blindspotsData'

export function BlindspotsPanel({ ctx }: { ctx: CompareContext }) {
  const r = ctx.records
  const { regionWide, byGeoid } = summarize(r)
  const count = (pick: (t: Tract) => boolean) => {
    const c: Record<GapLevel, number> = { none: 0, some: 0, big: 0 }
    for (const t of r.tracts) if (pick(t)) c[byGeoid.get(t.geoid)!.level]++
    return c
  }
  const drawn = count((t) => t.drawn)
  const high = count((t) => t.cls === 'desert')
  const highTotal = high.none + high.some + high.big
  const notDrawn = r.tracts.filter((t) => !t.drawn)
  const ownBlanks = new Map<string, number>()
  for (const g of byGeoid.values())
    for (const m of g.own) ownBlanks.set(m, (ownBlanks.get(m) ?? 0) + 1)
  const fewHomes = [...byGeoid.values()].filter((g) => g.fewHomes).length
  const groupQuarters = [...byGeoid.values()].filter((g) => g.groupQuarters).length
  const swatch = (lvl: GapLevel) =>
    lvl === 'big'
      ? { backgroundColor: '#fff', backgroundImage: hatchSwatch(), backgroundSize: '4px 4px' }
      : { background: FILL[lvl] }

  return (
    <div className="blindspots">
      <p>
        {high.some + high.big} of {highTotal} high-need neighborhoods have some facts missing or
        less sure. {high.big} of {highTotal} are missing key facts. A missing fact never means low
        need.
      </p>
      <ul className="legend" aria-label="Data gaps legend">
        {LEVELS.map((lvl) => (
          <li key={lvl}>
            <span className="swatch" style={swatch(lvl)} />
            <span>{LEVEL_LABEL[lvl]}</span>
            <span className="count">{drawn[lvl]}</span>
          </li>
        ))}
        <li>
          <span
            className="swatch"
            style={{ background: 'transparent', border: `2px solid ${COLORS.desert}` }}
          />
          <span>High-need neighborhood (outline)</span>
          <span className="count">{highTotal}</span>
        </li>
      </ul>

      <div className="notice" style={{ marginTop: 10 }}>
        <strong>Gaps that cover the whole region</strong>
        <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
          {allPlaces(regionWide) && (
            <li>
              We do not have local numbers on how many people cannot get a ride or do not have
              enough food. A national health survey left these blank for all of Florida.
            </li>
          )}
          {regionWide.length > 0 && !allPlaces(regionWide) && (
            <li>No neighborhood has these facts: {listText(regionWide.map(plain))}.</li>
          )}
          <li>
            We only see how SNAP use changes for Florida as a whole, not for each county or
            neighborhood.
          </li>
          <li>
            Our pantry list comes from one food bank, Second Harvest. Other pantries, churches and
            stores are not on it.
          </li>
          <li>
            How far people travel to a pantry is a rough guess: {r.standinReachMiles} miles in a
            straight line, not real drive time.
          </li>
          <li>
            About 1 in 10 small business loans (SBA) could not be matched to a neighborhood, so loan
            counts are too low, more so outside Orange County.
          </li>
        </ul>
        <p style={{ margin: '6px 0 0' }}>
          These gaps are true everywhere, so they do not change the map colors.
        </p>
      </div>

      <details className="how-we-know">
        <summary>How we know this</summary>
        <p>
          <strong>Levels.</strong> "{LEVEL_LABEL.big}": a class input (poverty rate, ACS S1701; or
          the USDA SRAM driving-distance LILA flag) is blank, so the tract is Insufficient data
          (POST-CLS-2). "{LEVEL_LABEL.some}": another tract-level indicator is blank, or the tract
          has fewer than {fmt.format(SMALL_HOUSEHOLDS)} households, or more than{' '}
          {GROUP_QUARTERS_PCT}% of residents live in group quarters. These are the size tests of
          confidence rule A (model.ts). The thresholds are stand-ins and are not decided.{' '}
          {NO_MOE}
        </p>
        <p>
          <strong>Counts.</strong> Drawn tracts: {LEVELS.map((l) => `${LEVEL_LABEL[l]} ${drawn[l]}`).join(', ')}.
          Tracts under {fmt.format(SMALL_HOUSEHOLDS)} households: {fewHomes}. Tracts over{' '}
          {GROUP_QUARTERS_PCT}% group quarters: {groupQuarters}.
          {notDrawn.length > 0 &&
            ` Not drawn (water, no shape): ${notDrawn
              .map((t) => `${t.geoid} (${LEVEL_LABEL[byGeoid.get(t.geoid)!.level]})`)
              .join(', ')}.`}
        </p>
        <p>
          <strong>Blank for one or a few tracts:</strong>{' '}
          {ownBlanks.size === 0
            ? 'none.'
            : [...ownBlanks].map(([m, c]) => `${m}, ${c} of ${r.tracts.length} tracts`).join('; ') +
              '.'}
        </p>
        <p>
          <strong>Blank for all {r.tracts.length} tracts:</strong>{' '}
          {regionWide.length === 0 ? 'none.' : `${regionWide.join('; ')}.`}{' '}
          {allPlaces(regionWide) &&
            'CDC PLACES 2025 (DS-H7) has no values for Florida in FOODSTAMP, FOODINSECU or LACKTRPT (finding F-1). The ACS B08201 no-vehicle share (DS-X7b) is the stand-in for transportation. It is an estimate that is not proven to measure the same thing.'}
        </p>
        <ul>
          <li>
            SNAP over time: CBPP SNAP Tracker, Florida, monthly (DS-X3b). No county or tract series
            is in the repo (DS-X1 and DS-X2 are not downloaded).
          </li>
          <li>
            Pantries: Second Harvest food finder partner sites (DS-X12). Other food sources are not
            listed. Redistribution permission was not obtained.
          </li>
          <li>
            Reach is a stand-in: {r.standinReachMiles} miles straight-line from each populated 2020
            census block (DS-X24). The decided rule is a 30-minute drive (Z-2d), which needs routing
            data that is not in the repo.
          </li>
          <li>
            SBA 7(a) and 504 loans (DS-X5): 7,024 of 7,817 loans (89.9%) matched to an address in the
            Census geocoder. Unmatched share by county: Lake 14.2%, Seminole 13.2%, Osceola 12.4%,
            Orange 7.9% (data/external/sba-loans/README.md). Tract loan counts are undercounts.
          </li>
        </ul>
      </details>
    </div>
  )
}

