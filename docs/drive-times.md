# Drive-time estimates

This PoC uses the hosted [openrouteservice Matrix API](https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/).
The endpoint is `https://api.heigit.org/openrouteservice/v2/matrix/driving-car`, following the
[provider's URL migration](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912).
It works with the existing MapLibre map and permits storing results under its
[current terms](https://account.heigit.org/info/tos). Result data is CC BY-SA 4.0.
The app credits openrouteservice and OpenStreetMap and links to the result license.
These are road-network estimates, without live traffic.

## Setup

1. Run the normal data Build: `python -m src.data_prep.alignment_bundle`.
2. Copy `.env.example` to `.env.local` and set `ORS_API_KEY`, or set that environment variable
   in the process that prepares the data. The key stays in the Node process. Do not use `VITE_`.
3. Run `npm run dev`. Vite prepares the cache and checks it every five minutes. An unchanged,
   successful cache is reused for 24 hours. Failed requests use the labeled fallback and retry
   on the next check. The browser checks the static file every minute.

`npm run routes:refresh` prepares the cache once. `npm run build` runs this command before
the frontend build. Both require the normal data files. No API key is required to run the app:
without one it shows the explicit heuristic fallback.

## Server deployment

The container serves the app through nginx and runs the Node cache builder with `--watch`.
It checks every five minutes and refreshes expired or failed entries. Successful results last
24 hours. The server-side builder contains the supplied PoC key; `ORS_API_KEY` can override it,
and an empty `ORS_API_KEY` disables provider calls. The key is excluded from browser assets and
cache responses. `.env*` files stay excluded from the image build context.

Run the normal data Build before building the image. Image builds make no provider requests;
the running container refreshes the cache. During initial preparation or provider failure,
the app shows its labeled heuristic fallback. Each instance has its own cache. No external
scheduled job is needed. Refresh runs while the instance has CPU available. No deployment is
performed by this code change.

## Meaning and failure behavior

- The distance slider retains the existing block-based reach rule: a neighborhood is within
  the distance if any populated block is within it. It reads the prepared reach shares and site
  counts from the data Build. The poverty, vehicle and lending dropdowns retain their live
  group calculations. Drive time is a separate fact for the selected neighborhood;
  changing a distance limit does not change the actual route time.
- The route matrix uses every listed site with valid coordinates. It displays the shortest
  returned duration, which can be to a different site from the closest straight-line site.
- Cache reuse requires identical origins and destinations, profile and version, plus a fresh
  timestamp. Changes to locations invalidate it even within 24 hours.
- Null route cells are unreachable, not zero minutes. A real zero duration is preserved.
  Missing coordinates, missing routes, invalid payloads, timeouts and HTTP failures each produce
  a fallback reason. The fallback uses the first prepared straight-line radius that covers 80%
  of the tract's residents and the original 10 miles = 30 minutes rule. It rounds up to one
  whole-minute estimate. Residents beyond that coverage can need longer. Coverage beyond the
  prepared 20-mile limit shows "Over 60 min"; missing population or distance data stays "No data".
  A cached road result still describes a trip from the tract's population-weighted center.
  The display shows one time and states which basis it uses.
- The builder uses batches of at most 3,500 matrix cells and pauses 1.7 seconds between requests
  to stay below the hosted Standard plan's 40 requests/minute limit. With 489 origins and 424
  sites, a full refresh needs 62 requests. Account quota and endpoint restrictions still apply.
  Requests stop on the first failed batch; completed batches remain available and the rest use
  fallback. No provider response body or API key is logged.

Sources: [matrix limits](https://giscience.github.io/openrouteservice/hosted-api-restrictions),
[plans](https://account.heigit.org/info/plans),
[storage permission](https://ask.openrouteservice.org/t/persistent-storage-and-reuse-of-matrix-api-duration-results/8010),
[OpenStreetMap attribution](https://www.openstreetmap.org/copyright),
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
