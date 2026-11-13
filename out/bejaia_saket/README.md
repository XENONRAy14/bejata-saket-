# Béjaïa → Saket: Assetto Corsa track preparation

Phases 0–4: OSM route, Copernicus DSM elevation, procedural Blender geometry/decor and a provisional AC data/KN5 package. **Not yet AC-tested.**

## What exists / works

- Official Blender **3.6.23**, installed at `~/tools/blender-3.6.23-linux-x64/blender`.
- Unmodified KN5 addon copied from the supplied clone to `~/tools/blender-assetto-corsa-tools`, installed/enabled by `scripts/test_exporter.py` in Blender's user addons directory.
- Headless export of a textured plane `1ROAD` and empty `AC_START_0` succeeds: **884-byte KN5**, correct `sc6969` header. `settings.json` is read from the output KN5 directory; absent settings default to `{}` (`exporter/exporter_utils.py:read_settings`). An explicit `{}` works; no shader/node overrides needed. The operator is `bpy.ops.exporter.kn5(filepath=...)`. It catches exceptions and can return FINISHED on failure, so the smoke check also asserts file existence/size/header.
- Generated-image copying initially failed in addon texture packing. Saving and reloading the generated PNG as a file-backed image fixes the smoke fixture, without patching the addon. No Blender downgrade was needed.
- Geofabrik Algeria PBF parsed using pyosmium, spatially filtered to `4.85,36.68,5.10,36.85`. Northern bound expanded because the actual named Saket beach is north of the suggested bbox. Cache and raw PBF are ignored by git.
- Directed road-node graph, oneway and roundabout direction, no/private access filtering; shortest weighted path prefers RN24. Exact source way tags, lengths and IDs are preserved in `data/route_info.json`; the original route remains unchanged.
- `data/route.geojson`, `data/route.gpx`, `data/route_info.json`, `out/preview/route_preview.png` are committed.

## Route facts / important scope discrepancy

OSM **Plage de Saket** is node **3010071431**, **36.8287488 N, 4.9434521 E**. Start is main-road node **2146361829**, **36.7525243 N, 5.0858924 E**, near the requested city-center location. Finish is RN24 node **13020911593**, **36.8267329 N, 4.9432964 E**, about **225 m** from the beach label (not an off-road line onto the sand).

Actual road route is **24.238 km**, not the estimated 10–15 km. Do not truncate it to match that estimate: this is the path to the named Saket destination, past Boulimat. The PNG was opened and inspected: continuous west/northwest path, winding RN24/Route de Boulimat inland of the coast before reaching the coastal section; no rural side-street shortcuts. Short city-center connectors are needed to reach RN24 and respect directed streets. OSM road name/ref inspection confirms the rural portion stays on RN24.

Road names: Rue Bouchebbah Youcef; Avenue Mustapha Ben Boulaid; Avenue Touati Larbi (RN 24); Rue Frères Meziani (RN 24); Rue de la Liberté / Rue de la Liberté شارع الحرية (RN 24); Boulevard de l'ALN (RN 24); Route de Boulimat (RN 24); a few unnamed urban junction/link segments. Per-way lanes/width may be null where OSM has no tag; no invented widths.

## Reproduce on Linux

```sh
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
curl -fL https://download.geofabrik.de/africa/algeria-latest.osm.pbf -o data/algeria-latest.osm.pbf
.venv/bin/python scripts/build.py route
.venv/bin/python scripts/build.py route --list-places
.venv/bin/python scripts/build.py dem
.venv/bin/python scripts/build.py centerline
.venv/bin/python scripts/build.py mesh
.venv/bin/python scripts/build.py acdata
.venv/bin/python scripts/build.py decor
.venv/bin/python -m unittest discover -s scripts -p 'test_decor.py' -v
.venv/bin/python -m unittest discover -s scripts -p 'test_acdata.py' -v
.venv/bin/python -m unittest discover -s scripts -p 'test_geometry.py' -v
.venv/bin/python -m unittest discover -s scripts -p 'test_route.py' -v
~/tools/blender-3.6.23-linux-x64/blender -b --python-exit-code 1 -P scripts/test_exporter.py
```

Run from project root. The initial country scan takes several minutes; subsequent runs use `data/area_cache.json` (remove it to refresh after replacing the PBF). `centerline` needs this cache for coastline detection; run `route` first on a fresh checkout. `dem` downloads two large GeoTIFFs, ignored by Git, and records exact URLs/checksums in `data/dem/sources.json`. `mesh` uses Blender's bundled numpy, not the project's venv; override its binary with `--blender /path/to/blender`. Committed centerline arrays allow regenerating the mesh without downloading the DEM again. Addon location for the independent exporter smoke check can be overridden with `AC_ADDON_SOURCE`. Smoke outputs: `blend/exporter_smoke.blend`, `out/exporter_smoke/smoke.kn5`, `out/exporter_smoke/settings.json`, `out/road.png`. Binary smoke outputs are not source assets.

## Phase 2 geometry

- `scripts/geometry.py`: rasterio bilinear pixel-center DSM sampling; pyproj EPSG:32631 projection; rounded start-point origin in `data/geo_origin.json`. Local Blender axes are east/north/elevation; metric units, scale 1.0.
- Approximately 2 m route sampling with fixed endpoints. A 2 m polyline simplification identifies corner tangents; overlapping short corners are merged, then rounded with 19.2 m nominal-radius fillets. A 4 m Gaussian pass eases straight/arc transitions, and a C2 cubic-spline curvature check enforces at least 12 m radius before final resampling. This replaces the previous hard 2.8 m corridor clipping, which produced curvature kinks. Smoothed horizontal length is **24.087 km** versus the original geodesic **24.238 km**; 3D length is **24.114 km**.
- Elevation: median filter, approximately 48 m full Gaussian window, then a **symmetric least-squares cubic B-spline QP** (OSQP, 10 m control spacing). Derivative-control bounds guarantee ±14% grade and maximum grade-change rate 0.001 per meter throughout the spline. There is no integrated-grade drift correction or arbitrary elevation floor. Elevations **6.00–323.24 m**, climb **464.44 m**. Against the median/Gaussian DEM target, mean/max absolute error is **0.283/5.107 m**; against median-only DEM it is **0.399/6.355 m**. Mean signed target error over 11–19 km is **+0.00029 m**, rather than the previous sustained upward bias. Raw DSM, filtered target and fitted road are plotted in `out/preview/elevation_profile.png`.
- **Copernicus GLO-30 is a DSM, not bare-earth or surveyed road elevation: it includes buildings and trees.** Filtering does not reconstruct bridge decks, tunnels, retaining structures or true road elevations. The road profile remains provisional.
- Widths use OSM width, then lanes × 3.25 m, then highway-class defaults, with smoothed transitions. **The road retains its full nominal 6.5–7 m width everywhere**; minimum generated width is **6.50 m**, narrowed length **0 m**. **No banking or road crossfall.** Low 0.3 m kerb rises 2 cm outward; shoulder remains 1.5 m. `1GRAVEL` uses the explicit custom physical key supplied in Phase 3; do not assume a stock GRAVEL surface. See `docs/AC_NOTES.md`.
- Terrain uses five columns including its shared shoulder edge, normally extending 40 m beyond that edge on each side. Shared strip and chunk boundaries have identical coordinates. Only the terrain extent contracts at tight curves/nearby hairpins (minimum centerline offset **8.18 m**); road, kerb and shoulder widths do not. Actual triangle winding and the whole ribbon's boundary crossings are checked, not just an analytic radius bound.
- **Approved intersection realignment:** the sharp urban reversal formerly near 1.19 km and other tight corners are rounded rather than narrowed. Global minimum discrete centerline radius is now **18.80 m**. Maximum revised-centerline distance to OSM is **14.72 m**; conversely, the omitted OSM corner tip is up to **37.09 m** from the revised centerline (two-sided maximum deviation **37.09 m**, sampled at approximately 1 m). This is an intentional local departure, not surveyed junction geometry. Maximum sampled heading change is **0.05329 rad/m (3.053°/m)**, and maximum curvature-change rate is **0.00489 m⁻²**. The regenerated 70% road view was checked for the earlier sharp center-marking kink.
- Coastline within 60 m on a side, or DSM 15 m out over 4 m below the road, triggers simple physical `1WALL_GUARD_*` beam/post barriers. Uphill DSM cuts over 4 m trigger `1WALL_CUT_*` rock faces. Gaps up to approximately 12 m merge; runs shorter than 30 m are removed. This is heuristic placement, not a survey; road/DSM mismatch can over-detect barriers. Walls are visible physical geometry, not unverified invisible colliders.
- All strips and barriers are chunked by actual chainage at approximately **400 m** (61 chunks, **516 mesh objects**, down from 1,051). Largest object: **2,400 vertices**, below the 65k cap. Total: **301,052 vertices / 381,972 triangles**. Road/kerb/gravel/grass faces are explicit +Z-facing triangles. Road UVs span 0–1 across the width and repeat every 7 m along chainage, continuous at chunk seams. Six reproducible 1024² PNG textures under `textures/` use numpy seed 24024; asphalt includes edge lines and dashed center markings.
- `blend/bejaia_saket.blend` contains geometry and references the committed `textures/` assets. `data/centerline.npz` holds metric arrays; `data/geometry_info.json` reports centerline and mesh counts. Previews: `out/preview/top.png`, `road_10.png`, `road_40.png`, `road_70.png`, `road_95.png` (road cameras 1.2 m high). The blue surround is a background, **not a modelled sea**. Renders/profile were opened and visually inspected; they are coarse blockout geometry, not finished scenery.

## Phase 3 AC package

Conventions, source URLs and runtime caveats: repository **`docs/AC_NOTES.md`**, especially sections 1–6. `scripts/build.py acdata` uses pure-Python `scripts/acdata.py` for files/placements and Blender `scripts/blender_acdata.py` for actual empties, end wall and full export. Run it **after mesh**; rerunning mesh resets the scene and requires rerunning acdata/decor. `AC_ADDON_SOURCE` can override `~/tools/blender-assetto-corsa-tools`. Export-only **`blend/settings.json`** lives beside staging output **`blend/bejaia_saket.kn5.partial`**; the completed KN5 alone is moved to the install folder. Neither settings nor a docs copy is shipped under `out/bejaia_saket/`.

### Staging / timing / end protection

- First 0–120 m changes heading by **21.205°**: not a good staging straight. Chose the first 120 m window with heading range ≤3°, scanning in 5 m increments and measuring at 1 m intervals including endpoints: **120–240 m**, range **2.391°**. Pits at **135, 143, 151, 159 m**, staggered within the right-hand lane. Grid pole at **183 m**, second car at **175 m**. Hotlap at **190 m**, AB start at **200 m**. Actual names/Blender east,north,height coordinates/Z yaw and nearest seam distances are in `data/acdata_info.json`.
- All 15 logical objects are uppercase, unparented, unit scale, with **Z yaw only** and **1.5 m above road**. Source: [Build your FIRST track — BASIC GUIDE](https://assettocorsamods.net/threads/build-your-first-track-basic-guide.12/), posts #1/§1B and #2 troubleshooting, recommends **1–2 m above the road** (also transcribed in repository AC_NOTES §2). **The exact +1.5 m is our midpoint assumption, not an engine requirement.** Spawns sit on the right; gate L/R are at opposite road edges, perpendicular to the road. Level, no banking. Direct exporter matrix conversion is checked numerically; actual car spawn/drop/orientation remains **UNVERIFIED in AC**.
- **Deliberate timing choice allowed by the request's sector-convention option:** AC_NOTES §6 warns against circuit-style `AC_TIME_0` overlapping the AB start. Thus `AC_AB_START_L/R` and `AC_AB_FINISH_L/R` mark stage ends, while `AC_TIME_0_L/R` is at **8145.666 m** and `AC_TIME_1_L/R` at **16091.331 m**, two intermediate thirds. This community A2B timing convention, sector capture, practice/hotlap persistence and restart behavior remain **UNVERIFIED in AC**.
- AB finish at **24036.997 m**; modeled road continues **50.000 m** to 24086.997 m. Timed stage length **23836.997 m**; UI length **24087m** describes the full modeled road, including staging/runoff. No dummy is within 2 m of an actual approximately 400 m chunk seam; actual minimum clearance **35.998 m**.
- Added **visible physical `1WALL_END`**, rock material, 0.5 m thick, following the final terrain/road cross-section end to end. Its center is 0.5 m before the modeled endpoint, top 1.2 m above the sampled cross-section, base 0.2 m below. Existing 50 m road provides runoff; no invented road extension. This is a crude safety boundary, not a realistic Saket feature or a safe stopping distance at racing speed. End-to-end wall geometry was rendered in `out/preview/end_barrier.png`; collision effectiveness remains **UNVERIFIED in AC**. Existing guardrails/cuts remain visible physical barriers; there are **no physics-only/invisible colliders**.

### Files / sourced values vs assumptions

Output is **`out/bejaia_saket/`**. Copy that folder under Windows `assettocorsa/content/tracks/` for the eventual runtime check; installation/loading is **UNVERIFIED**. Generated KN5 files are ignored (this full export exceeds 50 MB); regenerate locally with `acdata`.

| File | Content / provenance |
|---|---|
| `bejaia_saket.kn5` | Full current scene, 517 mesh objects (516 original + end wall), 15 AC empties. Blender cameras/lights retain `__` prefixes to exclude them. |
| `data/surfaces.ini` | Every actual physical key, checked against mesh prefixes: **ROAD, KERB, GRASS, GRAVEL, WALL**. Source: [Hagn example](https://site.hagn.io/assettocorsa/modding/tracks/data/surfaces-ini), also AC_NOTES §1. |
| `ui/ui_track.json` | UTF-8 requested name/geotags, Algeria/Béjaïa, full-road meter length, width 6.5–7.0m, pitboxes `"4"`, frite, v0.1, 2026. `run` is descriptive **“Béjaïa → Saket · point-to-point”** per Hagn, **not a mode switch**. |
| `ui/preview.png` / `ui/outline.png` | **355×200** following the inspected sample: resized road-level 70% Eevee render; white route on transparent RGBA. Mandatory dimension claims **UNVERIFIED**. |
| `map.png` / `data/map.ini` | North-up white route on transparent RGBA; dimensions/transform below. |
| `ai/README.txt` | No AI line, no fake zero-byte `.ai` file. AI racing unsupported. Empty AI directory allowed by the basic guide, but runtime loading without lines **UNVERIFIED locally**. |
| `CREDITS.md`, `README.md` | Attribution and limitations bundled with the install package. Settings (`blend/settings.json`), convention sources (`docs/AC_NOTES.md`) and detailed placement/export JSON evidence (`data/`) remain in the repository, not the install folder. All texture-named materials use explicit `ksPerPixel` settings with embedded `txDiffuse` PNGs. |

Surface values are **sourced examples, not verified installed Kunos defaults**. ROAD copies Hagn's ASPHALT block under a different KEY; KERB copies its KERB block. GRASS/GRAVEL/WALL inherit the ASPHALT block as an **ASSUMED** base. For GRASS: friction .65, damping .1, dirt 1, validity 0 are **ASSUMED**. For GRAVEL: friction .75, damping .05, dirt 1, validity 0 are **ASSUMED**. WALL's rolling parameters are **ASSUMED** (WALL is a special obstacle name). All differences are also annotated in `surfaces.ini`. Runtime traction/penalties, local/default merge/override behavior, `kerb.wav` availability and FF-effect semantics are **UNVERIFIED**. No separate pit-lane surface/limiter/repair zone was modeled; pit spawns are on ROAD, and pit servicing behavior is **UNVERIFIED**.

Material `ksAmbient=.4`, `ksDiffuse=.4` follow exporter defaults (AC_NOTES §5); explicit specular **.1** for road/terrain/rock/kerb and **.5** for metal, specular exponent **10/20**, and mesh `lodOut=10000` are **ASSUMED appearance/performance choices**, not measured real-world values. PNG shader appearance/shadows and all material behavior remain **UNVERIFIED in AC**, although texture embedding/material references are read back from the exported binary. There are no physics-only colliders to hide. Cameras are skipped: although a Hagn format example exists, no valid route-specific camera splines/set was established, so **no `data/cameras.ini`** is shipped. Lighting/groove configuration and runtime defaults are **UNVERIFIED** and not fabricated.

### Map transform

AC_NOTES §4 links Hagn's sample and the independently inspected [assetto-server-manager transform](https://github.com/cj123/assetto-server-manager/blob/master/cmd/server-manager/typescript/src/RaceControl.ts#L491-L497). That third-party implementation adds offsets **in meters** then divides by meters/pixel. For Blender `(x,y,z)`, exported world `(X,Z)=(x,-y)`:

```text
px = (X + X_OFFSET) / SCALE_FACTOR
py = (Z + Z_OFFSET) / SCALE_FACTOR
scale = max(world X span, world Z span) / (1600 - 2*20)
offset = 20*scale - minimum_world_coordinate
image dimensions = ceil(world span / scale + 2*20), capped at 1600
```

Generated **WIDTH=1600**, **HEIGHT=1033**, **SCALE_FACTOR=8.2680681163 m/pixel**, **X_OFFSET=13063.5095051 m**, **Z_OFFSET=8130.9675505 m**. A 20-pixel border is baked into the offsets, independent of the INI margin field. Round-trip map/world positions and containment are checked, and images inspected; actual car-overlay alignment in vanilla AC remains **UNVERIFIED**. `MARGIN=0` is an **ASSUMED** defensive choice to avoid applying padding twice; its exact engine meaning is **UNVERIFIED**. `MAX_SIZE=1600` and `DRAWING_SIZE=10` are copied from the sample (1600 also chosen as this generator's pixel cap); their engine semantics remain **UNVERIFIED**, not claimed to control rendering here.

### Full export / validation evidence

The stage invokes Blender 3.6.23 headlessly, loads the current scene and enables the unmodified addon. It calls the addon's actual `exporter.KN5FileWriter(...).write()` with settings from `blend/settings.json` beside the temporary output, rather than the operator that can swallow exceptions (AC_NOTES §5). An in-memory NodeWriter subclass only records before/after split counts; no addon files are modified. Exceptions propagate; the staged file is moved into the install folder only after successful writing and header validation.

`data/kn5_export_info.json` records the **latest** file bytes, writer-only elapsed seconds, SHA-256, warnings and actual split counters. The **Phase 3 baseline** was **58,994,247 bytes (58.99 MB / 56.26 MiB)**, **517 mesh nodes**, no vertex-limit splits, maximum 10,526 expanded vertices before splitting. This verifies that scene's full export, **not** the oversized-mesh split branch, which remains **UNVERIFIED by execution**. Four expected unknown-logical-object warnings are the requested **AC_AB_START/FINISH_L/R** names absent from the addon's allowlist (AC_NOTES §2); names are deliberately retained. Marking existing image nodes active avoids UV fallback warnings. All meshes have UV maps.

Independent `scripts/check_kn5.py` reads the writer's KN5 v5 subset: header, textures, material properties/references, logical matrices, meshes/indices/flags, exact EOF. It does not constitute a Blender/ksEditor round trip or runtime validation. Unit tests cover normal/empty/error inputs for placements/map generation, file generation and binary readback. Windows acceptance must still cover loading, right-lane spawn/drop and facing, both AB gates/two intermediate sectors, saved practice/hotlap times, return to pits, surface grip and all wall collisions. **`run: "A2B"` as a runtime mode switch is UNVERIFIED and intentionally not used**; the AB object names declare the intended layout, but functioning A2B sessions are still **UNVERIFIED**.

## Phase 4 light decor

Run **`scripts/build.py decor`** after geometry (it also rebuilds AC metadata/empties and exports). Seed **24024** controls placement, variants, scale/yaw and textures. `scripts/decor.py` does terrain-triangle sampling and corridor checks outside Blender; `scripts/blender_decor.py` builds the low-poly meshes in bpy, merging decor into **one object per material per actual approximately 400 m chunk**, not individual tree objects. Re-running decor replaces its own objects rather than stacking them. Generated source plan/evidence: `data/decor_plan.npz`, `data/decor_info.json`; latest export: `data/kn5_export_info.json`.

- **Vegetation:** 3 shape variants each of umbrella/stone-Aleppo-style pines, short twisted-trunk grey-green olives and maquis shrubs. Trunks/canopies are solid low-poly geometry, no alpha. Scatter probability in the first 2 km and last Saket section is one fifth of rural density. Roots lie exactly on the existing triangular terrain surface, with a small embedded trunk base. Conservative full-footprint road clearance is ≥4 m beyond the road edge (therefore outside shoulder/guardrails), including nearby hairpin roads; terrain slopes over .55 and cut-flagged sides are rejected. Footprint corners must also lie on the modeled ribbons. Geometry is generic Mediterranean blockout, not surveyed species locations.
- **Props:** wooden/concrete-style poles with crossbars/insulators on the right at approximately 50 m intervals in town, the assumed Boulimat vicinity (18–20.5 km) and Saket (>23.1 km); unsuitable cut/terrain sites are skipped. White/red RN24-style stone markers at every kilometer, allowing ±8 m to find terrain. Generic white plaster flat-roof buildings occupy 28 city and 12 Saket sites, their conservative footprint ≥8 m from every road edge. Foundations extend below the lowest sampled footprint corner to avoid floating. Locations, town bounds and pole styles are **ASSUMED**, not OSM building/utility surveys.
- **Sea / beach:** uses the joined, projected **OSM coastline** from the route cache; coastline nearest the 18.5 km road anchor through Saket, extended approximately 1.2 km along shore at both ends. A triangulated flat sea polygon closes that shoreline **1.5 km north/offshore**, at **Z=0 m in the unshifted DEM datum**. All existing road/terrain vertices are above zero (minimum **1.848 m**), hence their linear triangles cannot be submerged; the build refuses nonpositive terrain rather than silently flooding it. Mean sea level / exact local vertical datum alignment is **UNVERIFIED**. A sloping visual sand ribbon bridges the last approximately 550 m of sea-side terrain outer edge to OSM coastline, ending at Z=.12 m; it is a simplified inferred beach, not surveyed bathymetry. Sand faces covering sampled road/kerb footprints are rejected. Both beach and sea are **visual-only**, so no SAND surface key is needed.
- **All decor is visual-only** (`DECOR_*`, no digit/surface physics prefix): **cars can pass through trees, buildings, poles, markers, beach and sea**. Existing physical track/terrain/barriers remain unchanged. Vegetation/prop collision and actual AC material appearance remain **UNVERIFIED**; there is no water simulation or CSP-specific shader.
- Eight seeded 512² noise textures: bark, pine foliage, olive foliage, maquis, plaster, sand, water and marker red. All are embedded PNGs using `ksPerPixel`; water is an opaque blue low-cost placeholder. Total decor triangles are asserted **≤150,000**, each object below 65k vertices. Actual counts and export growth are recorded in the JSON evidence, not inferred from instance counts.
- Updated previews: `out/preview/top.png`, `road_10.png`, `road_40.png`, `road_70.png`, `road_95.png`; new road-level views `decor_town.png`, `decor_saket.png`, plus the end barrier check. `ui/preview.png` is refreshed from the decorated road-level render. The sea polygon is limited to the coastal section; the blue world background elsewhere is still not modeled water.

## Untested / limitations

No Assetto Corsa or Windows runtime validation, ksEditor import/round trip, surveyed physical road widths/elevations, driving/collision validation, AI lines or pit-lane/repair-zone geometry. A full KN5/data package now exists; successful binary writing/readback does not demonstrate in-game correctness. OSM turn-restriction relations and conditional access/oneway tags are not modelled; this is not navigation certification. Route preview uses vector OSM roads and coastline, not raster tiles. Start/end are snapped to main-road nodes, not the exact square/beach centroid.

See [CREDITS.md](CREDITS.md) for attribution and licensing.
