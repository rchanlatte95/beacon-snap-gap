import { driveTimeEstimate, type DriveTimeCache } from './driveTimes'
import { populationAccess, populationAccessText } from './populationAccess'
import type { TractRecord } from '../wizard/alignmentWizard'

export function DriveTimeEstimate({
  geoid,
  originLabel,
  population,
  miles,
  cache,
  inputKey,
  now,
}: {
  readonly geoid: string
  readonly originLabel: string
  readonly population: Pick<TractRecord, 'pop2020' | 'reach_share' | 'nearest_block_miles'>
  readonly miles: number | null | undefined
  readonly cache: DriveTimeCache | null
  readonly inputKey: string | null
  readonly now: number
}) {
  const estimate = driveTimeEstimate(geoid, miles, cache, inputKey, now)
  const access = populationAccess(population)
  return (
    <div className="drive-time" role="status">
      <strong>
        Estimated drive to a Second Harvest site:{' '}
        {estimate.routed ? `${Math.round(estimate.minutes!)} min` : populationAccessText(access)}
        {!estimate.routed && ' (heuristic)'}
      </strong>
      <p className="proximity-note">
        {estimate.routed
          ? `From ${originLabel}’s population-weighted center.`
          : `For 80% of residents in ${originLabel}, using each populated block’s nearest listed partner site. The other 20% may need longer.`}
        {!estimate.routed &&
          access.status === 'beyond' &&
          ' Coverage exceeds the 20-mile data limit.'}
      </p>
      <p className="proximity-note">
        {estimate.routed ? (
          <>
            <a href="https://openrouteservice.org/" target="_blank" rel="noreferrer">
              openrouteservice
            </a>{' '}
            · {estimate.note.replace('openrouteservice · ', '')}. Shortest drive from the population
            center across listed sites. No live traffic.
          </>
        ) : (
          estimate.note
        )}
      </p>
      {estimate.routed && (
        <p className="proximity-note">
          Routing data:{' '}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
            OpenStreetMap contributors
          </a>
          . Results:{' '}
          <a
            href="https://creativecommons.org/licenses/by-sa/4.0/"
            target="_blank"
            rel="noreferrer"
          >
            CC BY-SA 4.0
          </a>
          .
        </p>
      )}
    </div>
  )
}
