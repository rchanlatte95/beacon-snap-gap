# Handling large data files: LFS and references

Status: **decided 2026-11-07 (Ketema): tiers 1 and 2 only.** Tier 3 (LFS) and tier 4 (external snapshot) are deferred until a real file needs them. Ryan's agent proposed this smaller scheme as the efficient one; Ketema had approved the four-tier scheme on condition that it was efficient. Git LFS patterns remain enabled in this repo (commit `3f11cee`) as a safe failure; no file is tracked through LFS.

## Decision record
| Item | Decision |
|---|---|
| Tier 1 (derived extract, under about 10 MB) | Keep. Any new file of 50 MB or more goes to tier 2, not tier 1 (GitHub warns above 50 MB and blocks above 100 MB) |
| Tier 2 (reference pointer) | Keep the pointer record: URL, bytes, SHA-256, as-of date, license. The fetch script is optional: write one only when a second person needs the raw files |
| Tier 3 (LFS) | Deferred. No file needs it; Ryan has no Git LFS; Ketema's pushes need a manual step |
| Tier 4 (external snapshot) | Deferred to the submission decision |
| `.gitattributes` LFS patterns | Stay. They match no file today |

The sections below are the original proposal. Where they disagree with this table, this table governs.

## What is enabled now
- `.gitattributes` routes `data/large/**`, `*.parquet`, `*.gpkg` and `*.pbf` through Git LFS.
- Existing files (the 74.6 MB PLACES CSV and the other hackathon files) were committed before LFS and stay as normal files. Moving them into LFS would rewrite history, which is destructive for everyone with a clone. Not done.
- `data/cache/` is git-ignored, for raw downloads that are referenced, not committed.
- Each person who wants LFS files needs `git lfs install` on their machine.

## Two cautions before using LFS
1. **Pushes need an extra step on Ketema's machine.** His global git hooks (`[hooks dir]`) have no LFS `pre-push` hook, and a repo can have only one hooks directory. A plain `git push` sends only the pointer file, not the content. Until the global hook is fixed, run `git lfs push origin <branch>` before `git push`. Ryan's setup may differ. A pointer pushed without its content breaks checkouts for everyone.
2. **Quota.** In a public repo, other people's clones and forks draw LFS bandwidth from the repo owner's quota. Check the current free allowance at github.com/settings/billing before relying on it. A hackathon audience downloading large LFS files can exhaust it.

## Recommended default: tiers
| Tier | Use for | Where it lives | Example |
|---|---|---|---|
| 1. Derived extract | Anything the app or tests need, under about 10 MB | Normal files in `data/` | SBA loans for the four counties, aggregated by tract |
| 2. Reference pointer | Large raw sources we can re-download | A small pointer file in the repo plus a fetch script; the bytes go to `data/cache/` (ignored) | The three SBA FOIA CSVs, about 504 MB |
| 3. LFS | A large file that must be versioned with the code and cannot be rebuilt | `data/large/` | A tract polygon file in GeoPackage form |
| 4. External snapshot | A frozen copy for the submission | GitHub Release asset or a public cloud bucket | The final built dataset |

### Tier 2 pointer format
One JSON file per source in `data/references/`, for example `sba-foia-7a-fy2020-present.json`:
```json
{
  "id": "DS-X5",
  "name": "SBA FOIA 7(a), FY2020 to present",
  "url": "https://data.sba.gov/sites/default/files/uploaded_resources/FOIA_7a_FY2020_Present_asof_260930.csv",
  "bytes": 188484797,
  "sha256": "<recorded at download>",
  "as_of": "2026-09-30",
  "license": "U.S. Government Works",
  "retrieved": "2026-11-07",
  "rebuild": "scripts/build-sba-extract.py"
}
```
A fetch script downloads each pointer to `data/cache/`, checks the byte count and hash, and fails loudly on a mismatch. The extract builder reads only from `data/cache/`. This keeps the repo small and every number traceable to a hash.

### Why not DVC
It adds a tool, a remote and an account for every contributor. For this project the tiers above give the same result with a script and a JSON file. We can revisit if the data grows.

## External homes for tier 4, compared
| Option | Limit and cost | Strength | Weakness |
|---|---|---|---|
| GitHub Release asset | 2 GiB per file, no LFS quota | Same place as the repo; stable URL; attached to a tag | Manual upload; no folders |
| Google Cloud Storage public bucket | Pennies per GB; egress costs apply | Ketema already has Google Cloud; a `gs://` path works from Cloud Run | Needs a project and public-access setting; ongoing cost |
| Zenodo or Figshare | Free, citable DOI | Good for a final dataset in a submission | Slow to publish; not for working files |

Recommendation: a GitHub Release for the frozen submission snapshot. A bucket only if the deployed app needs to read data at runtime, which the manifest currently forbids (REQ-6).

## Worked example: SBA loans (DS-X5)
- **Source:** https://data.sba.gov/dataset/7a-504-foia, three files, about 504 MB in total (7(a) FY2020 to present 188 MB, 7(a) FY2010 to 2019 255 MB, 504 FY2010 to present 60 MB), as of 2026-09-30, plus a data dictionary.
- **Central Florida share:** 7,817 loans in Orange, Seminole, Lake and Osceola counties ($4.5 billion gross approval).
- **Plan:** tier 2 pointers for the three raw files; tier 1 for an extract aggregated to census tract (counts and dollars by program and period). The extract carries no borrower names or street addresses, which keeps it consistent with REQ-4 (no data about individuals). Geocoding borrower addresses to tracts uses the Census Bureau batch geocoder, which sends addresses to a government service and needs an explicit go-ahead.

## Decisions for the humans
1. Approve the tier scheme, or keep it simpler (tiers 1 and 2 only).
2. Who fixes the missing LFS `pre-push` hook in Ketema's global hooks. That file is under his governance repo, so it needs a branch and PR there, not an edit from this project.
3. Whether the final submission snapshot goes in a GitHub Release or elsewhere.
