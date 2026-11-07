# 2020 Census block population: 4 Central Florida counties

`central-fl-blocks-2020.csv` has one row for each 2020 Census block in the 4 Central Florida counties: 39,751 blocks, 2,673,376 people, 1,087,949 housing units. Each row has the population, the housing units and one interior latitude/longitude point.

Source IDs: DS-X24 (block file), DS-X25 (verification), DS-X26 (2025 growth factors). See `docs/data-sources.md`.

## Motivation

We want a map of Central Florida that gives a rough answer to this question: **how many people live near a landmark or an arbitrary latitude/longitude?**

The census block is the smallest area that the Census Bureau publishes counts for. Tracts and block groups are too large for small-radius questions. Census blocks are small where people live close together. In these counties, the median populated urban block has 21,156 m² of land (about 5.2 acres, approximately one city block). The median populated rural block has 143,337 m² (about 35 acres). The median populated block has 46 people.

To estimate the population near a point, add `pop20` for all blocks whose `lat`/`lon` point is within the radius.

## Counties selected

We use the same 4 counties that the hackathon data (DS-H1 to DS-H5) calls Central Florida. Together they are the Orlando-Kissimmee-Sanford metropolitan area. The blocks fall in 490 tracts, the same as the 490 Central Florida tracts in DS-H1. Because of this, each block joins to a hackathon tract.

We first selected 3 more counties: Brevard, Polk and Volusia. We removed them because the hackathon files have no tract data for them.

| County | FIPS | Main cities | Blocks | Blocks with 0 people | Population 2020 | Housing units 2020 |
|---|---|---|---:|---:|---:|---:|
| Orange | 12095 | Orlando | 17,794 | 4,578 | 1,429,908 | 561,851 |
| Seminole | 12117 | Sanford, Lake Mary | 6,125 | 1,394 | 470,856 | 193,790 |
| Osceola | 12097 | Kissimmee | 5,769 | 1,566 | 388,656 | 154,680 |
| Lake | 12069 | Tavares, Leesburg | 10,063 | 3,212 | 383,956 | 177,628 |
| **Total** | | | **39,751** | **10,750** | **2,673,376** | **1,087,949** |

## Columns

| Column | Meaning |
|---|---|
| `geoid20` | 15-digit block ID: state (2) + county (3) + tract (6) + block (4) |
| `county_fips` | 3-digit county code (state code 12 not included) |
| `county_name` | County name |
| `tract` | 6-digit tract code. Join to hackathon tract data with `"12" + county_fips + tract` (the first 11 digits of `geoid20`) |
| `block` | 4-digit block code |
| `urban_rural` | `U` urban, `R` rural (2020 Census definition) |
| `aland_m2`, `awater_m2` | Land and water area, square meters |
| `lat`, `lon` | Census internal point of the block (decimal degrees, NAD83) |
| `housing20` | Housing units, 2020 Census |
| `pop20` | Total population, 2020 Census |

## Limits

1. **The data shows April 1, 2020.** These counties grew about 11% by July 2025 (2,673,372 to 2,957,672). For a rough 2025 number, multiply `pop20` by the county factor below. This assumes that all blocks in a county grew at the same rate. That is not true: new subdivisions grew faster than older areas.

   | County | 2020 estimates base | July 1, 2025 estimate | Factor |
   |---|---:|---:|---:|
   | Orange | 1,429,910 | 1,528,002 | 1.0686 |
   | Seminole | 470,856 | 491,884 | 1.0447 |
   | Osceola | 388,647 | 481,718 | 1.2395 |
   | Lake | 383,959 | 456,068 | 1.1878 |

   Source: Census Bureau Vintage 2025 county estimates (DS-X26). The Census Bureau's estimates base is a little different from the census count (for example, Orange 1,429,910 against 1,429,908).
2. **The Census Bureau added privacy noise to the counts of a single block.** In the 2020 Census, it used differential privacy, so the count for one block can be wrong by a few people. When you add up many blocks, as for a radius, most of the noise cancels. Do not report a count for one block.
3. **Each block is counted as one point.** At a radius of about 1 mile or more in urban areas, the error is small. At a small radius in rural areas, a large block at the edge is counted fully in or fully out.
4. **Points near the edge of the 4 counties.** The file has no blocks outside the 4 counties. A radius that crosses into Brevard, Polk, Volusia, Sumter, Marion or another neighboring county will count too few people.
5. **10,750 blocks have 0 people** (water, parks, commercial and industrial land). They are in the file. Filter on `pop20 > 0` if you do not need them.
6. **The file has no polygons.** Block boundaries are in the source zip (DS-X24) if a map needs them.

## Provenance and verification

- **Source file:** `https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_12_tabblock20.zip`. 353,358,123 bytes, server Last-Modified 2023-01-06, SHA-256 `CE5D7A02E47DF17DADFA9C889EDB6D35A89DFB520B8669BC4D302C2C0E100418`. Downloaded 2026-11-07. Not committed, because it is too large for git.
- **Extract:** `central-fl-blocks-2020.csv`, UTF-8 with LF line endings (as stored in git), 3,076,711 bytes, SHA-256 `AFE75BE857699518AC50ECAB6E0E0E18A35B9F5478F1A0BE91ABCFFA372FF710`. On Windows with `core.autocrlf=true`, git checks the file out with CRLF line endings, so its checksum on disk will be different.
- **To make the CSV again:** Read the `.dbf` attribute table in the source zip. Keep the rows where `STATEFP20` is `12` and `COUNTYFP20` is `069`, `095`, `097` or `117`. Copy `GEOID20`, `COUNTYFP20`, `TRACTCE20`, `BLOCKCE20`, `UR20`, `ALAND20`, `AWATER20`, `INTPTLAT20`, `INTPTLON20`, `HOUSING20` and `POP20`, in that order, to the columns in the table above. Put the county name in `county_name`, after `county_fips`. You do not need the polygon geometry. The result must have the row count, totals and checksum given in this section.

- **Verification (2026-11-07):** For each county, the block sums of `pop20` and `housing20` agree exactly with the official 2020 Census redistricting file. The fields used are `P0010001` (total population) and `H0010001` (housing units), from `fl2020.pl.zip` (DS-X25). The check script also confirmed that `H0010001` equals occupied plus vacant units for each county, which shows that it read the correct column. All 39,751 block points are inside the box from 27.0 to 29.5 N and 82.5 to 80.0 W. The blocks fall in 490 distinct tracts. Result: `RESULT: ALL MATCH`.
