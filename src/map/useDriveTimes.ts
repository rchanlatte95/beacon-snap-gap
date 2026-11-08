import { useEffect, useState } from 'react'
import { DRIVE_TIME_FILE, parseDriveTimeCache, type DriveTimeCache } from './driveTimes'

export function useDriveTimes(enabled: boolean) {
  const [state, setState] = useState<{ cache: DriveTimeCache | null; now: number }>(() => ({
    cache: null,
    now: Date.now(),
  }))
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    let request: AbortController | null = null
    async function load() {
      request?.abort()
      request = new AbortController()
      const timeout = setTimeout(() => request?.abort(), 5000)
      let cache: DriveTimeCache | null = null
      try {
        const response = await fetch(DRIVE_TIME_FILE, { cache: 'no-store', signal: request.signal })
        if (response.ok) cache = parseDriveTimeCache(await response.json())
      } catch {
        // An unavailable cache uses the explicitly labeled heuristic in DriveTimeEstimate.
      } finally {
        clearTimeout(timeout)
      }
      if (!cancelled) setState({ cache, now: Date.now() })
    }
    void load()
    const interval = setInterval(() => {
      void load()
    }, 60_000)
    return () => {
      cancelled = true
      clearInterval(interval)
      request?.abort()
    }
  }, [enabled])
  return state
}
