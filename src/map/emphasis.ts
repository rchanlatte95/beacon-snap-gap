export type EmphasisState = {
  /** Not in the chosen group. */
  readonly dimmed: boolean
  /** In the chosen group while gap emphasis is on: drawn with an outline. */
  readonly emphasized: boolean
  /** Not in the chosen group while gap emphasis is on: drawn faded. */
  readonly muted: boolean
}

/** REQ-63: the map feature state of each drawn tract. Tracts with no map shape get none. */
export function emphasisStates(
  records: readonly { readonly geoid: string; readonly drawn: boolean }[],
  focusedGeoids: readonly string[],
  emphasizeGaps: boolean,
): ReadonlyMap<string, EmphasisState> {
  const include = new Set(focusedGeoids)
  const active = emphasizeGaps && include.size > 0
  const states = new Map<string, EmphasisState>()
  for (const record of records) {
    if (!record.drawn) continue
    const inGroup = include.has(record.geoid)
    states.set(record.geoid, {
      dimmed: !inGroup,
      emphasized: active && inGroup,
      muted: active && !inGroup,
    })
  }
  return states
}
