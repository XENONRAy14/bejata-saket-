# Béjaïa → Saket: Assetto Corsa track preparation

Phases 0–2: OSM route, Copernicus DSM elevation and procedural Blender track geometry. **Not yet an installable or AC-tested track.**

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
.venv/bin/python -m unittest discover -s scripts -p 'test_geometry.py' -v
.venv/bin/python -m unittest discover -s scripts -p 'test_route.py' -v
~/tools/blender-3.6.23-linux-x64/blender -b --python-exit-code 1 -P scripts/test_exporter.py
```

Run from project root. The initial country scan takes several minutes; subsequent runs use `data/area_cache.json` (remove it to refresh after replacing the PBF). `centerline` needs this cache for coastline detection; run `route` first on a fresh checkout. `dem` downloads two large GeoTIFFs, ignored by Git, and records exact URLs/checksums in `data/dem/sources.json`. `mesh` uses Blender's bundled numpy, not the project's venv; override its binary with `--blender /path/to/blender`. Committed centerline arrays allow regenerating the mesh without downloading the DEM again. Addon location for the independent exporter smoke check can be overridden with `AC_ADDON_SOURCE`. Smoke outputs: `blend/exporter_smoke.blend`, `out/exporter_smoke/smoke.kn5`, `out/exporter_smoke/settings.json`, `out/road.png`. Binary smoke outputs are not source assets.

## Phase 2 geometry

- `scripts/geometry.py`: rasterio bilinear pixel-center DSM sampling; pyproj EPSG:32631 projection; rounded start-point origin in `data/geo_origin.json`. Local Blender axes are east/north/elevation; metric units, scale 1.0.
- Approximately 2 m route sampling, fixed-endpoint XY smoothing constrained to a 2.8 m corridor around OSM segments. Deviation is point-to-polyline, **not displacement between equal-index samples**: corner cutback moves samples along the corridor by up to 14.65 m. Smoothed horizontal length is **24.008 km** versus the original geodesic **24.238 km**; 3D length is **24.034 km**.
- Elevation: median filter, approximately 48 m full Gaussian window, ±12% grades, maximum grade-change rate 0.001 per meter. Integrated grades are fitted with a constant vertical offset and a 1 m elevation floor. This can leave the road above/below the original DSM; the terrain ribbon blends to it rather than leaving the road floating locally. Elevations **1.00–320.94 m**, climb **446.24 m**. The raw/filtered profile is `out/preview/elevation_profile.png`.
- **Copernicus GLO-30 is a DSM, not bare-earth or surveyed road elevation: it includes buildings and trees.** Filtering does not reconstruct bridge decks, tunnels, retaining structures or true road elevations. The road profile remains provisional.
- Widths use OSM width, then lanes × 3.25 m, then highway-class defaults, with smoothed transitions. Nominal widths here are 6.5–7 m. **No banking or road crossfall.** Low 0.3 m kerb rises 2 cm outward; shoulder is normally 1.5 m. `1GRAVEL` is a custom physical key to define explicitly in Phase 3; do not assume a stock GRAVEL surface. See `docs/AC_NOTES.md`.
- Terrain uses five columns including its shared shoulder edge, normally extending 40 m beyond that edge on each side. Shared strip and chunk boundaries have identical coordinates. Inner offsets and nearby hairpins contract; actual triangle winding and the whole ribbon's boundary crossings are checked, not just an analytic radius bound.
- **Sharp urban turn limitation:** minimum discrete centerline radius is only **1.28 m** near chainage 1.18–1.20 km. To avoid intersecting ribbons, roughly **118 m** total is narrower than its nominal width; minimum generated road width is **3.09 m**, minimum one-side terrain extent **0.46 m**. Kerb/shoulder widths also contract there. This is not a verified car-drivable hairpin: a surveyed alignment or permission to depart farther from OSM is needed before claiming end-to-end drivability. These exceptions are not representative of the rural road.
- Coastline within 60 m on a side, or DSM 15 m out over 4 m below the road, triggers simple physical `1WALL_GUARD_*` beam/post barriers. Uphill DSM cuts over 4 m trigger `1WALL_CUT_*` rock faces. Gaps up to approximately 12 m merge; runs shorter than 30 m are removed. This is heuristic placement, not a survey; road/DSM mismatch can over-detect barriers. Walls are visible physical geometry, not unverified invisible colliders.
- All strips and barriers are chunked at approximately 200 m. Road/kerb/gravel/grass faces are explicit +Z-facing triangles. Road UVs span 0–1 across the width and repeat every 7 m along chainage, continuous at chunk seams. Six reproducible 1024² PNG textures under `textures/` use numpy seed 24024; asphalt includes edge lines and dashed center markings.
- `blend/bejaia_saket.blend` contains geometry and references the committed `textures/` assets. `data/centerline.npz` holds metric arrays; `data/geometry_info.json` reports centerline and mesh counts. Previews: `out/preview/top.png`, `road_10.png`, `road_40.png`, `road_70.png`, `road_95.png` (road cameras 1.2 m high). The blue surround is a background, **not a modelled sea**. Renders/profile were opened and visually inspected; they are coarse blockout geometry, not finished scenery.

## Untested / limitations

No Assetto Corsa or Windows runtime validation, ksEditor import, full-track KN5 export/round trip, surveyed physical road widths/elevations, driving/collision validation, AI lines, spawn/timing objects, pits, or packaging. Geometry names prepare physics surfaces but no Phase 3 surface configuration is supplied yet. Successful smoke binary writing does not demonstrate in-game correctness. OSM turn-restriction relations and conditional access/oneway tags are not modelled; this is not navigation certification. Route preview uses vector OSM roads and coastline, not raster tiles. Start/end are snapped to main-road nodes, not the exact square/beach centroid.

See [CREDITS.md](CREDITS.md) for attribution and licensing.
