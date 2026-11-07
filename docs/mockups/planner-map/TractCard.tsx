// The tract card. Owner: the plain-language task (T9).
// Explore level at the top (plain sentences: what is here, why it matters, how sure we are),
// then the active Compare-with lines. Everything technical is inside "How we know this".
import { CLASS_LABEL, CONF_RULES, NO_SITE_TEXT, confidence, n, pct } from './model'
import type { ConfRule, Records, Tract } from './model'
import {
  BASE_SOURCES,
  UI,
  cardHowSure,
  cardLoad,
  cardMissing,
  cardSites,
  cardWhatIsHere,
  cardWhyItMatters,
  plainName,
} from './copy'

// ---------------- Tract card ----------------

// The sources that the card's own facts come from (the sidebar has the full list).
const CARD_SOURCE_IDS = ['DS-H2', 'DS-H1', 'DS-H6', 'DS-X7b', 'DS-X12', 'DS-X24', 'DS-X16b', 'DS-H7']

export function TractCard(props: {
  t: Tract
  r: Records
  confRule: ConfRule
  onClose: () => void
  // Plain sentences from the active Compare-with layer, if any.
  compareLines?: string[]
}) {
  const { t, r, confRule, onClose, compareLines } = props
  const cut = r.povertyCut.value
  const povertyMet = t.pctPoverty !== null && t.pctPoverty >= cut
  const lilaMet = t.lilaDD === 1
  const conf = confidence(t, cut, confRule)
  const ruleName = CONF_RULES.find((c) => c.id === confRule)!.name
  const noSite = t.sitesInTract === 0 || t.standinReachPct === 0
  // The two class inputs (POST-CLS-2). Other blanks are listed under Missing indicators.
  const core = t.missing.filter((m) => /S1701|SRAM/.test(m))
  const sites = cardSites(t)
  const load = t.cls === 'desert' ? cardLoad(t) : null
  const missing = cardMissing(t)
  return (
    <aside className="card" aria-label={`Tract card for ${t.name}`}>
      <div className="card-head">
        <div>
          <h3>{plainName(t)}</h3>
          <div className="secondary">{t.county} County</div>
        </div>
        <button className="close" onClick={onClose} aria-label="Close tract card">
          ×
        </button>
      </div>
      <div className="class-badge">
        <span className={`swatch ${t.cls}`} />
        {CLASS_LABEL[t.cls]}
      </div>

      {/* ---------- Explore ---------- */}
      <section className="card-plain">
        <p>{cardWhatIsHere(t, cut)}</p>
        {t.drawn && <p>{cardWhyItMatters(t)}</p>}
        {t.drawn && sites && <p>{sites}</p>}
        {noSite && <p className="callout">{NO_SITE_TEXT}</p>}
        {load && <p>{load}</p>}
        <p className={`how-sure ${conf.level === 'Not rated' ? 'not-rated' : conf.level.toLowerCase()}`}>
          {cardHowSure(t, cut, conf.level)}
        </p>
        {missing && <p className="missing-note">{missing}</p>}
      </section>

      {compareLines && compareLines.length > 0 && (
        <section className="compare-lines">
          {compareLines.map((l) => (
            <p key={l}>{l}</p>
          ))}
        </section>
      )}

      {/* ---------- Detail ---------- */}
      <details className="how-we-know">
        <summary>{UI.howWeKnow}</summary>

        <section>
          <h4>Tract</h4>
          <p className="rule">
            {t.name}, {t.county} County, GEOID <span className="mono">{t.geoid}</span>
            {!t.drawn && '. Not drawn: water, no shape'}. A neighborhood on this page is one census
            tract.
          </p>
        </section>

        <section>
          <h4>Why this class</h4>
          {t.cls === 'insufficient' ? (
            <p className="rule">
              Insufficient data: {core.join(', ') || 'a core indicator'} is blank in the source. This is
              not a low-need result.
            </p>
          ) : (
            <>
              <dl className="facts">
                <dt>Poverty rate (top quartile is {cut.toFixed(3)}% or more)</dt>
                <dd>
                  {pct(t.pctPoverty)}{' '}
                  <span className={`check ${povertyMet ? 'yes' : 'no'}`}>
                    {povertyMet ? 'meets' : 'below'}
                  </span>
                </dd>
                <dt>LILA, driving distance (½ mi urban, 10 mi rural)</dt>
                <dd>
                  <span className={`check ${lilaMet ? 'yes' : 'no'}`}>{lilaMet ? 'Yes' : 'No'}</span>
                </dd>
              </dl>
              <p className="rule">
                Classic Food Desert needs both. Cut: 75th percentile of {r.povertyCut.tracts} tracts (
                {r.povertyCut.method}).
              </p>
            </>
          )}
        </section>

        <section>
          <h4>Pantry coverage</h4>
          <dl className="facts">
            <dt>Second Harvest sites inside the tract</dt>
            <dd>{t.sitesInTract}</dd>
            <dt>
              Reach: residents within reach of a site <span className="standin">stand-in</span>
            </dt>
            <dd>{pct(t.standinReachPct)}</dd>
            <dt>
              Load: residents per site within reach <span className="standin">stand-in</span>
            </dt>
            <dd>{n(t.standinLoad)}</dd>
          </dl>
          <p className="rule">
            Stand-in reach is {r.standinReachMiles} miles straight-line from each populated 2020 block.
            The decided rule is a 30-minute drive (Z-2d), which needs routing data that is not in the
            repo yet. Sites are Second Harvest partner sites only; other pantries and stores are not in
            the list, and hours change.
          </p>
        </section>

        <section>
          <h4>Context (not used in the class)</h4>
          <dl className="facts">
            <dt>Households on SNAP</dt>
            <dd>
              {pct(t.pctSnap)} ({n(t.snapHouseholds)} of {n(t.households)})
            </dd>
            <dt>No-vehicle households (proxy, not validated, F-1)</dt>
            <dd>{pct(t.noVehiclePct)}</dd>
            <dt>Group quarters share of residents</dt>
            <dd>{pct(t.groupQuartersPct)}</dd>
            <dt>Population, 2020 (tract sum)</dt>
            <dd>{n(t.pop2020)}</dd>
            <dt>Area type (USDA)</dt>
            <dd>{t.urban === null ? 'blank' : t.urban === 1 ? 'Urban' : 'Rural'}</dd>
            <dt>FEMA risk / social vulnerability</dt>
            <dd>
              {t.nriRisk ?? 'blank'} / {t.socialVulnerability ?? 'blank'}
            </dd>
          </dl>
        </section>

        <section className="confidence">
          <h4>Confidence</h4>
          <div>
            <strong>{conf.level}</strong> under rule {ruleName}{' '}
            <span className="standin">rule not decided</span>
          </div>
          <ul className="conf-why">
            {conf.why.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <p className="rule">Change the rule under How we know this in the sidebar.</p>
        </section>

        <section>
          <h4>Missing indicators ({t.missing.length})</h4>
          {t.missing.length === 0 ? (
            <p className="rule">None.</p>
          ) : (
            <ul className="missing">
              {t.missing.map((m) => (
                <li key={m}>
                  {m}: blank in the source
                  {m.includes('CDC PLACES') && ' (blank for all of Florida, finding F-1)'}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="sources">
          Sources:{' '}
          {BASE_SOURCES.filter((s) => CARD_SOURCE_IDS.includes(s.id))
            .map((s) => `${s.label} (${s.id})`)
            .join('; ')}
          .
        </section>
      </details>
    </aside>
  )
}
