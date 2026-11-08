import {
  CUT_NAMES,
  cutPercentiles,
  percentileLabel,
  rateText,
  type CutName,
  type Cuts,
  type Percentiles,
} from '../wizard/gapRules'

const CUT_LABELS: Readonly<Record<CutName, string>> = {
  poverty: 'High poverty',
  no_vehicle: 'Many with no car',
  sba_rate_per_1000: 'Few business loans',
}

function cutText(name: CutName, value: number): string {
  return name === 'sba_rate_per_1000'
    ? `${value.toFixed(2)} or fewer per 1,000`
    : `${rateText(value)}% or more`
}

/** REQ-59 (Z-24 A): one choice per gap cut, from the percentiles the Build wrote. */
export function CutControls({
  cuts,
  percentiles,
  onChange,
  names = CUT_NAMES,
}: {
  readonly cuts: Cuts
  readonly percentiles: Percentiles
  readonly onChange: (name: CutName, percentile: number) => void
  readonly names?: readonly CutName[]
}) {
  return (
    <fieldset className="cut-controls">
      <legend>Gap rules</legend>
      {names.map((name) => (
        <label key={name} className="cut-control">
          <span>{CUT_LABELS[name]}</span>
          <select
            data-testid={`cut-select-${name}`}
            value={percentiles[name]}
            onChange={(event) => onChange(name, Number(event.currentTarget.value))}
          >
            {cutPercentiles(cuts, name).map((p) => (
              <option key={p} value={p}>
                {percentileLabel(name, p)} ({cutText(name, cuts[name][String(p)] ?? NaN)})
              </option>
            ))}
          </select>
        </label>
      ))}
    </fieldset>
  )
}
