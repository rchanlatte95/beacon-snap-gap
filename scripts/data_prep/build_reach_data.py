"""Build the static data file for the "Are we reaching the people who need us?" experience.

Reads repo files only. Writes one file: public/data/reach.json (Z-5: public/data/ is
generated and git-ignored). Tract-level fields only (REQ-17).

Inputs
- docs/analysis/tract_gap_types.csv            need class (Z-1 rule, unchanged), 2020 population,
                                               poverty rate, SNAP share, LILA driving flag
- data/external/second-harvest-food-finder/central_fl_tract_pantry_coverage.csv
                                               households, SNAP households, Second Harvest sites in tract
- data/external/second-harvest-food-finder/second_harvest_food_finder_locations.csv
                                               site points (name, lat, lng, tract)
- data/external/census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv
                                               no-vehicle households and margins of error
- data/external/geography/central_fl_tracts_2020.geojson
                                               489 tract polygons (12095990000 is water, no geometry)

Run from any directory:
    python -I scripts/data_prep/build_reach_data.py
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import quantiles

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public" / "data" / "reach.json"

COUNTY_NAMES = {"12095": "Orange", "12117": "Seminole", "12069": "Lake", "12097": "Osceola"}

# Orientation labels for the map and the neighborhood list. Approximate town centers,
# general knowledge, not a dataset. They are labels only and carry no numbers.
TOWNS = [
    ("Orlando", 28.5384, -81.3789),
    ("Kissimmee", 28.2920, -81.4076),
    ("St. Cloud", 28.2489, -81.2812),
    ("Sanford", 28.8029, -81.2695),
    ("Oviedo", 28.6700, -81.2081),
    ("Altamonte Springs", 28.6611, -81.3656),
    ("Apopka", 28.6934, -81.5322),
    ("Winter Garden", 28.5653, -81.5862),
    ("Clermont", 28.5494, -81.7729),
    ("Leesburg", 28.8108, -81.8779),
    ("Tavares", 28.8042, -81.7256),
    ("Mount Dora", 28.8025, -81.6445),
    ("Eustis", 28.8528, -81.6853),
    ("Poinciana", 28.1406, -81.4584),
    ("Winter Park", 28.5999, -81.3392),
    ("Pine Hills", 28.5578, -81.4534),
    ("Bithlo", 28.5547, -81.1073),
    ("Celebration", 28.3253, -81.5334),
    ("Four Corners", 28.3330, -81.6450),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(s: str | None) -> float | None:
    if s is None or s.strip() == "":
        return None
    return float(s)


def simplify(ring: list[list[float]], tol: float) -> list[list[float]]:
    """Douglas-Peucker on a closed ring (first point == last point)."""
    if len(ring) <= 4:
        return ring

    def dist(p, a, b):
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def dp(pts):
        if len(pts) < 3:
            return pts
        a, b = pts[0], pts[-1]
        idx, dmax = 0, 0.0
        for i in range(1, len(pts) - 1):
            d = dist(pts[i], a, b)
            if d > dmax:
                idx, dmax = i, d
        if dmax > tol:
            return dp(pts[: idx + 1])[:-1] + dp(pts[idx:])
        return [a, b]

    # Split the ring at its farthest point so the end-points are not the same point.
    far = max(range(1, len(ring) - 1), key=lambda i: math.hypot(ring[i][0] - ring[0][0], ring[i][1] - ring[0][1]))
    part1 = dp(ring[: far + 1])
    part2 = dp(ring[far:])
    out = part1[:-1] + part2
    if len(out) < 4:
        return ring
    return out


def main() -> None:
    gap = {r["geoid"]: r for r in read_csv(ROOT / "docs/analysis/tract_gap_types.csv")}
    cov = {r["geoid"]: r for r in read_csv(ROOT / "data/external/second-harvest-food-finder/central_fl_tract_pantry_coverage.csv")}
    nov = {r["geoid"]: r for r in read_csv(ROOT / "data/external/census-acs/acs2024_b08201_no_vehicle_central_fl_tracts.csv")}
    sites = read_csv(ROOT / "data/external/second-harvest-food-finder/second_harvest_food_finder_locations.csv")
    geo = json.load(open(ROOT / "data/external/geography/central_fl_tracts_2020.geojson", encoding="utf-8"))

    assert len(gap) == 490 and len(cov) == 490, (len(gap), len(cov))

    # Queen adjacency from exact shared vertices of the original polygons.
    vert: dict[tuple[float, float], set[str]] = defaultdict(set)
    geoms: dict[str, list] = {}
    for f in geo["features"]:
        g = f["properties"]["TRACTFIPS"]
        polys = f["geometry"]["coordinates"]
        if f["geometry"]["type"] == "Polygon":
            polys = [polys]
        geoms[g] = polys
        for poly in polys:
            for ring in poly:
                for x, y in ring:
                    vert[(round(x, 5), round(y, 5))].add(g)
    nb: dict[str, set[str]] = defaultdict(set)
    for gs in vert.values():
        for a in gs:
            nb[a] |= gs - {a}

    class_map = {"Classic Food Desert": "high", "No gap flagged": "other", "Insufficient data": "unknown"}

    tracts = []
    for geoid, r in sorted(gap.items()):
        c = cov[geoid]
        v = nov.get(geoid, {})
        county = COUNTY_NAMES[geoid[:5]]
        tract_no = geoid[5:9].lstrip("0") + ("." + geoid[9:] if geoid[9:] != "00" else "")
        polys = geoms.get(geoid)
        centroid = None
        rings_out = None
        if polys:
            xs, ys, n = 0.0, 0.0, 0
            rings_out = []
            for poly in polys:
                outer = poly[0]
                for x, y in outer[:-1]:
                    xs += x
                    ys += y
                    n += 1
                rings_out.append([[round(x, 4), round(y, 4)] for x, y in simplify(outer, 0.0002)])
            centroid = [round(xs / n, 5), round(ys / n, 5)]
        near = None
        if centroid:
            lon, lat = centroid
            near = min(TOWNS, key=lambda t: math.hypot((t[2] - lon) * math.cos(math.radians(lat)), t[1] - lat))[0]
        households = int(c["households"]) if c["households"] else None
        nv_pct = num(v.get("pct_no_vehicle"))
        tracts.append(
            {
                "id": geoid,
                "county": county,
                "tractNo": tract_no,
                "near": near,
                "need": class_map[r["food_class"]],
                "pop2020": int(r["population_2020"]) if r["population_2020"] else None,
                "povertyPct": num(r["poverty_rate_pct"]),
                "snapPct": num(r["snap_share_pct"]),
                "lilaDriving": r["lila_driving_flag"] == "1",
                "households": households,
                "snapHouseholds": int(c["snap_households"]) if c["snap_households"] else None,
                "noVehiclePct": nv_pct,
                "noVehicleHouseholds": int(v["no_vehicle_households"]) if v.get("no_vehicle_households") else None,
                "noVehicleMoe": int(v["moe_no_vehicle_households"]) if v.get("moe_no_vehicle_households") else None,
                "sitesInside": int(c["second_harvest_sites"]),
                "neighbors": sorted(nb.get(geoid, set())),
                "centroid": centroid,
                "rings": rings_out,
            }
        )

    # No-vehicle cut: the top quarter (75th percentile, inclusive method, as in the Z-1 rule) of the
    # no-vehicle share over the 488 tracts with a value. Gives 6.9%. A stand-in rule that needs human approval.
    nv_values = [t["noVehiclePct"] for t in tracts if t["noVehiclePct"] is not None and t["need"] != "unknown"]
    nv_cut = round(quantiles(nv_values, n=4, method="inclusive")[2], 1)

    # Clusters of touching high-need neighborhoods.
    high = {t["id"] for t in tracts if t["need"] == "high"}
    seen: set[str] = set()
    clusters: list[list[str]] = []
    for g in sorted(high):
        if g in seen:
            continue
        stack, comp = [g], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.append(x)
            stack += [y for y in nb[x] if y in high and y not in seen]
        clusters.append(sorted(comp))
    clusters.sort(key=lambda c: (-len(c), c[0]))

    site_points = [
        {
            "id": s["storeid"],
            "name": s["name"],
            "tract": s["tract_geoid"],
            "lat": round(float(s["lat"]), 5),
            "lng": round(float(s["lng"]), 5),
        }
        for s in sites
        if s["tract_geoid"][:5] in COUNTY_NAMES
    ]

    out = {
        "builtFrom": {
            "needRule": "Z-1 option B: poverty rate at or above the 75th percentile of the 488 Central Florida neighborhoods (census areas) with a value (ACS 2024 5-year, S1701) AND the USDA driving-distance low-income low-access flag (DD_SRAM_LILATracts_halfAnd10). Taken as is from docs/analysis/tract_gap_types.csv.",
            "reachRule": "A Second Harvest partner site inside the neighborhood (Z-2 option A). The decided 30-minute drive rule (Z-2 option C) needs a routing step that is not in the repo.",
            "noVehicleCut": nv_cut,
            "sources": ["DS-H1", "DS-H2", "DS-H6", "DS-X7b", "DS-X12", "DS-X24", "DS-X15"],
        },
        "counties": sorted(COUNTY_NAMES.values()),
        "towns": [{"name": n, "lat": la, "lng": lo} for n, la, lo in TOWNS],
        "clusters": clusters,
        "sites": site_points,
        "tracts": tracts,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    # Report, so the numbers can be checked against the design brief.
    h = [t for t in tracts if t["need"] == "high"]
    none = [t for t in h if t["sitesInside"] == 0]
    s = lambda L, k: sum(t[k] or 0 for t in L)
    nv = [t for t in none if (t["noVehiclePct"] or 0) >= nv_cut]
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    print(f"tracts {len(tracts)}; high-need {len(h)}; drawn {sum(1 for t in tracts if t['rings'])}")
    print(f"high-need with no site inside: {len(none)}; households {s(none, 'households'):,}; SNAP households {s(none, 'snapHouseholds'):,}")
    print(f"no-vehicle cut (top quarter) {nv_cut}%: {len(nv)} of those; est. no-car households {round(sum(t['households'] * t['noVehiclePct'] / 100 for t in nv)):,}")
    print(f"clusters {len(clusters)}; sizes {[len(c) for c in clusters[:6]]}")
    print(f"sites in four counties {len(site_points)}; tracts with a site {sum(1 for t in tracts if t['sitesInside'])}")


if __name__ == "__main__":
    main()
