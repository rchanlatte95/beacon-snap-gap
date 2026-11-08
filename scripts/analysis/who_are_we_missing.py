"""Numbers for the "who are we missing" design: people in high-need places, and the near-miss test.

Reads repo files only. Writes nothing. Prints every number in
docs/mockups/planner-map/DESIGN-who-are-we-missing.md, sections 2 and 7 and appendix A.

Run from any directory:
    python scripts/analysis/who_are_we_missing.py
"""
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
recs = json.load(open(ROOT / "docs/mockups/planner-map/data/records.standin.json"))["tracts"]
geo = json.load(open(ROOT / "data/external/geography/central_fl_tracts_2020.geojson"))
sba = {r["geoid"]: int(r["loans_total"]) for r in csv.DictReader(open(ROOT / "data/external/sba-loans/sba_loans_by_tract_central_fl.csv"))}

T = {r["geoid"]: r for r in recs if r["cls"] in ("desert", "nogap")}

# Queen adjacency: tracts that share at least one exact vertex.
vert = defaultdict(set)
for f in geo["features"]:
    g = f["properties"]["TRACTFIPS"]
    polys = f["geometry"]["coordinates"]
    if f["geometry"]["type"] == "Polygon":
        polys = [polys]
    for poly in polys:
        for ring in poly:
            for x, y in ring:
                vert[(round(x, 5), round(y, 5))].add(g)
nb = defaultdict(set)
for gs in vert.values():
    for a in gs:
        nb[a] |= gs - {a}
nb_counts = [len(nb[g]) for g in T]
print(f"tracts in analysis: {len(T)}; with 0 neighbors: {sum(c == 0 for c in nb_counts)}; median neighbors: {median(nb_counts)}")

rate = {g: 1000 * sba.get(g, 0) / T[g]["pop2020"] for g in T}
cut = median(rate.values())
print(f"median loans per 1,000 (cut): {cut:.2f}")

desert = {g for g in T if T[g]["cls"] == "desert"}

# Clusters of contiguous desert tracts.
seen, clusters = set(), []
for g in desert:
    if g in seen:
        continue
    stack, comp = [g], set()
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        comp.add(x)
        stack += [y for y in nb[x] if y in desert and y not in seen]
    clusters.append(comp)
clusters.sort(key=len, reverse=True)
print(f"desert clusters: {len(clusters)}; sizes: {[len(c) for c in clusters[:10]]} ...; singletons: {sum(len(c) == 1 for c in clusters)}")


def near_miss(rate_map):
    low = [g for g in desert if rate_map[g] < cut]
    nm = [g for g in low if any(y in T and T[y]["cls"] == "nogap" and rate_map[y] >= cut for y in nb[g])]
    return len(low), len(nm)


low, nm = near_miss(rate)
print(f"desert tracts with low lending: {low}; of these, next to a high-lending nogap tract: {nm} ({100*nm/low:.0f}%)")

# Chance baseline: shuffle the lending rates across the 488 tracts, keep the map fixed.
random.seed(1)
gs, vals = list(T), list(rate.values())
sims = []
for _ in range(2000):
    random.shuffle(vals)
    sims.append(near_miss(dict(zip(gs, vals)))[1])
sims.sort()
p = sum(s >= nm for s in sims) / len(sims)
print(f"near misses by chance: median {median(sims)}, 95% range {sims[50]} to {sims[1949]}; share of shuffles >= observed: {p:.2f}")

# Cluster view: lending per 1,000 inside each big cluster versus its ring of nogap neighbors.
print("\nlargest clusters: inside vs ring (loans per 1,000 residents)")
for c in clusters[:6]:
    ring = {y for x in c for y in nb[x] if y in T and y not in c}
    pin = sum(T[g]["pop2020"] for g in c)
    pr = sum(T[g]["pop2020"] for g in ring)
    lin = sum(sba.get(g, 0) for g in c)
    lr = sum(sba.get(g, 0) for g in ring)
    cty = sorted({T[g]["county"] for g in c})
    print(f"  {len(c):>2} tracts {cty}: inside {1000*lin/pin:.2f} ({lin} loans); ring of {len(ring)} tracts {1000*lr/pr:.2f} ({lr} loans)")

# Targeting ratio: share of loans in desert tracts / share of people below poverty in desert tracts.
pov = {g: T[g]["pop2020"] * T[g]["pctPoverty"] / 100 for g in T}
loans_d = sum(sba.get(g, 0) for g in desert) / sum(sba.get(g, 0) for g in T)
pov_d = sum(pov[g] for g in desert) / sum(pov.values())
print(f"\nshare of loans in desert tracts: {100*loans_d:.1f}%; share of people below poverty (approx.) in desert tracts: {100*pov_d:.1f}%; ratio {loans_d/pov_d:.2f}")

# People in high-need places (ACS estimates summed over tracts; tract level only, REQ-4).
# "No site inside" is manifest Z-2 option A, a stand-in for the decided 30-minute drive rule.
NV_CUT = 6.9  # stand-in no-vehicle cut from T7 rule S1 (needs human approval, H-5)
D = [T[g] for g in desert]
none = [t for t in D if t["sitesInTract"] == 0]
hh = lambda L, k: sum(t.get(k) or 0 for t in L)
print(f"\nhigh-need tracts: {len(D)}; households {hh(D, 'households'):,}; SNAP households {hh(D, 'snapHouseholds'):,}")
print(f"  with no Second Harvest site inside: {len(none)} tracts; households {hh(none, 'households'):,}; SNAP households {hh(none, 'snapHouseholds'):,}")
nv = [t for t in none if (t.get("noVehiclePct") or 0) >= NV_CUT]
print(f"  of these, no-vehicle share >= {NV_CUT}%: {len(nv)} tracts; est. households without a car {round(sum(t['households'] * t['noVehiclePct'] / 100 for t in nv)):,}")
