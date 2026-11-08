import {
  DEFAULT_REACH_MILES,
  DEFAULT_REACH_MINUTES,
  MAX_REACH_MILES,
  REACH_STEP_MILES,
  reachMiles,
  reachMinutes,
} from './proximity'
import { SourceLinks } from '../SourceCitations'

export interface ProximityControlsProps {
  readonly ready: boolean
  readonly enabled: boolean
  readonly miles: number
  readonly outsideCount: number
  readonly withinCount: number
  readonly unknownCount: number
  readonly onEnabled: (enabled: boolean) => void
  readonly onMiles: (miles: number) => void
  readonly onReset: () => void
}

export function ProximityControls(props: ProximityControlsProps) {
  const minutes = reachMinutes(props.miles)
  return (
    <section className="proximity-controls" aria-label="Explore pantry proximity">
      <div className="proximity-heading">
        <label className="proximity-switch">
          <input
            type="checkbox"
            checked={props.enabled}
            disabled={!props.ready}
            onChange={(event) => props.onEnabled(event.currentTarget.checked)}
          />
          Show gaps beyond this limit
        </label>
        <button type="button" className="linklike" onClick={props.onReset} disabled={!props.ready}>
          Reset proximity
        </button>
      </div>
      <div className="proximity-sliders">
        <label className="proximity-slider">
          <span>
            Distance limit <output>{props.miles} mi</output>
          </span>
          <input
            type="range"
            aria-label="Distance limit in miles"
            aria-valuetext={`${props.miles} miles`}
            min={0}
            max={MAX_REACH_MILES}
            step={REACH_STEP_MILES}
            value={props.miles}
            disabled={!props.ready}
            onChange={(event) => props.onMiles(event.currentTarget.valueAsNumber)}
          />
        </label>
        <label className="proximity-slider">
          <span>
            Estimated time limit <output>{minutes} min</output>
          </span>
          <input
            type="range"
            aria-label="Estimated time limit in minutes"
            aria-valuetext={`${minutes} minutes, estimated`}
            min={0}
            max={reachMinutes(MAX_REACH_MILES)}
            step={reachMinutes(REACH_STEP_MILES)}
            value={minutes}
            disabled={!props.ready}
            onChange={(event) => props.onMiles(reachMiles(event.currentTarget.valueAsNumber))}
          />
        </label>
      </div>
      <p className="proximity-result" id="proximity-result" role="status">
        {!props.ready
          ? 'Proximity needs site locations. The controls will be ready when map data loads.'
          : props.enabled
            ? `${props.outsideCount} beyond the limit; ${props.withinCount} within it; ${props.unknownCount} with no distance data.`
            : 'Move either slider to find gaps in the selected group. The map updates as you drag.'}
      </p>
      <p className="proximity-note">
        Straight-line distance from each neighborhood’s population center to the nearest Second
        Harvest site. Time uses {DEFAULT_REACH_MILES} miles = {DEFAULT_REACH_MINUTES} minutes: an
        assumption-based estimate, without road routes or traffic.
      </p>
      <SourceLinks ids={['DS-X12', 'DS-X24']} />
    </section>
  )
}
