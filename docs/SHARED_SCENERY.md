# Shared scenery generators (planning only)

This step does not enable new scenery in `build.py`, change physical geometry,
rebuild KN5s, refresh install/source ZIPs, or relax the main validator's budgets.

## Pure API

`scenery_placement.plan_sector(data, models, s0, s1, zones=profile)` returns
`trees`, `edges`, and a JSON-serializable `report`, without writing files.
Stations are absolute **active-route 3D metres**, with half-open sector ownership.
Pass the complete main centerline, not a sliced sector: clearance must see every
road leg. Model dimensions come from the already compiled TreeFX metadata.

`plan_sectors` rejects overlapping intervals. Each disjoint sector receives at
most `floor(length * effective_density / 100)` trees, where effective density is
the smaller of 51 and `8000 * 100 / full_route_length`. Thus even a full tiling
cannot exceed 8,000 instances (7,926 at the current route length). Individual
100 m bins may vary; the cap is the requested **sector average**.

Seeds derive from millimetre-rounded absolute sector start, base seed and layer
using SHA256, never Python's randomized hash or a shared RNG. Rebuilding another
sector has no effect. Changing sector boundaries intentionally changes that
sector's seed/placements.

Sea side is the lower outer DEM cross-section side after a 30 m Gaussian filter
on a uniform station grid. It can change along the route. This is a terrain-side
heuristic, not a visibility/raycast claim.

`data/scenery_zones.json` records vista and exclusion intervals in this station
system, with sea/mountain/both or explicit side selectors and optional layer
selectors. Exclusions also reject footprints overlapping an interval boundary.
Initial main zones are a Boulimat coastal opening and a Saket village-core
exclusion; they are explicit starting annotations, not a completed geographic
scenery survey.

Clearance checks all nearby points in the **full** centerline using a KD-tree,
including each point's road width, and also checks the continuous buffered road
polyline so gaps between samples cannot hide another leg. The buffer uses the
maximum road width conservatively. Tree footprints use a conservative bounding
circle including scale and width multipliers; edge cards use half their width.
No part of an accepted footprint may approach any road leg closer than 4 m.

## Pilot compatibility and Blender adapters

`pilot_tree_layout` is the preserved pure pilot profile. Existing pilot calls to
`edge_layout` keep their original random sequence. The historical adult/sapling/
edge sea openings are separate explicit intervals, preserving their deliberately
different boundaries. The compatibility profile is not subject to the new main
sector thinning or 4 m all-leg filtering. Applying those would change the pilot.
Regression tests compare all 330 tree and 327 edge dictionaries to the committed
pre-refactor `data/pilot300/plants.json` and `edge_layout.json` within 1e-6.

`edge_batches` supplies the pure near/far card geometry used by `forest_edges`.
Blender `forest_edges`/`scatter_trees` accept `s0`, `s1`, `zones`, and explicit
cache/output/texture directories. `pilot_treefx.compile_models` accepts
`output_dir`, `cache_dir`, `texture_dir`; `impostors` accepts cache/texture
directories. Default paths preserve existing pilot calls. Model compilation and
impostor baking are still Blender operations; placement planning is not.

## Representative report

Run `.venv/bin/python scripts/plan_scenery.py`. It reads config/model/centerline
paths supplied by CLI options and prints reports only. It writes no assets.

- Summit: 880–1180 m straddles the summit at 1030 m (spawn + 1000 m).
- Hairpin: 4163.445–4463.445 m centres on the maximum absolute heading change
  over a 20 m window (43.455 degrees; approximate radius 26.37 m).
- Sea view: 10000–10300 m is the annotated Boulimat opening on the retained coast.
- Saket approach: 14900–15200 m exercises the transition into the excluded village
  core beginning at 15100 m.

This is a placement/count/clearance report, not visual or FPS acceptance. No full
route Blender build is needed for this phase.
