import type { ReactNode } from 'react'

import { MAX_REACH_MILES, REACH_STEP_MILES, milesText } from './reach'
import { SourceLinks } from '../SourceCitations'

export interface ProximityControlsProps {
  readonly enabled: boolean
  readonly miles: number
  readonly beyondCount: number
  readonly withinCount: number
  readonly unknownCount: number
  readonly onEnabled: (enabled: boolean) => void
  readonly onMiles: (miles: number) => void
  readonly onReset: () => void
  /** Controls shown beside the distance control (the gap cuts). */
  readonly children?: ReactNode
  readonly driveTime?: ReactNode
}

/** REQ-57 (Z-25 A): one distance control, in straight-line miles only. */
export function ProximityControls(props: ProximityControlsProps) {
  const distance = milesText(props.miles)
  return (
    <section
      className="proximity-controls"
      data-testid="reach-controls"
      aria-label="Distance and gap rules"
    >
      <div className="proximity-heading">
        <label className="proximity-switch">
          <input
            type="checkbox"
            checked={props.enabled}
            onChange={(event) => props.onEnabled(event.currentTarget.checked)}
          />
          Show only gaps beyond this distance
        </label>
        <button type="button" className="linklike" onClick={props.onReset}>
          Reset rules
        </button>
      </div>
      <div className="proximity-sliders">
        <label className="proximity-slider">
          <span>
            Distance to a Second Harvest site <output>{distance}</output>
          </span>
          <input
            type="range"
            aria-label="Distance limit in miles"
            aria-valuetext={distance}
            min={0}
            max={MAX_REACH_MILES}
            step={REACH_STEP_MILES}
            value={props.miles}
            onChange={(event) => props.onMiles(event.currentTarget.valueAsNumber)}
          />
        </label>
        {props.children}
      </div>
      {props.driveTime}
      <p className="proximity-result" data-testid="proximity-result" role="status">
        {props.enabled
          ? `Showing the ${props.beyondCount} beyond ${distance}. ${props.withinCount} within; ${props.unknownCount} with no distance data.`
          : `In this group: ${props.withinCount} within ${distance}, ${props.beyondCount} beyond, ${props.unknownCount} with no distance data.`}
      </p>
      <SourceLinks ids={['DS-X12', 'DS-X24']} />
    </section>
  )
}
