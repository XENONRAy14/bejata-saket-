# Béjaïa → Saket: Assetto Corsa track preparation

Phases 0–1 only. **No track geometry has been built.** Blender smoke-test geometry is only a disposable exporter check, not the track.

## What exists / works

- Official Blender **3.6.23**, installed at `~/tools/blender-3.6.23-linux-x64/blender`.
- Unmodified KN5 addon copied from the supplied clone to `~/tools/blender-assetto-corsa-tools`, installed/enabled by `scripts/test_exporter.py` in Blender's user addons directory.
- Headless export of a textured plane `1ROAD` and empty `AC_START_0` succeeds: **884-byte KN5**, correct `sc6969` header. `settings.json` is read from the output KN5 directory; absent settings default to `{}` (`exporter/exporter_utils.py:read_settings`). An explicit `{}` works; no shader/node overrides needed. The operator is `bpy.ops.exporter.kn5(filepath=...)`. It catches exceptions and can return FINISHED on failure, so the smoke check also asserts file existence/size/header.
- Generated-image copying initially failed in addon texture packing. Saving and reloading the generated PNG as a file-backed image fixes the smoke fixture, without patching the addon. No Blender downgrade was needed.
- Geofabrik Algeria PBF parsed using pyosmium, spatially filtered to `4.85,36.68,5.10,36.85`. Northern bound expanded because the actual named Saket beach is north of the suggested bbox. Cache and raw PBF are ignored by git.
- Directed road-node graph, oneway and roundabout direction, no/private access filtering; shortest weighted path prefers RN24. Exact source way tags, lengths and IDs are preserved in `data/route_info.json`. No resampling or smoothing yet.
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
.venv/bin/python -m unittest discover -s scripts -p 'test_route.py' -v
~/tools/blender-3.6.23-linux-x64/blender -b --python-exit-code 1 -P scripts/test_exporter.py
```

Run from project root. Only route is supported by the entry script. The initial country scan takes several minutes; subsequent runs use `data/area_cache.json` (remove it to refresh after replacing the PBF). Addon location can be overridden with `AC_ADDON_SOURCE`. Smoke outputs: `blend/exporter_smoke.blend`, `out/exporter_smoke/smoke.kn5`, `out/exporter_smoke/settings.json`, `out/road.png`. Binary smoke outputs are not source assets.

## Untested / limitations

No Assetto Corsa or Windows runtime validation, ksEditor import, KN5 round trip, physical road-width verification, elevation, terrain, driving physics, collision meshes, AI lines, pits, or packaging. Successful binary writing does not demonstrate in-game correctness. OSM turn-restriction relations and conditional access/oneway tags are not modelled; this is a route-planning centerline, not navigation certification. Preview uses vector OSM roads and coastline, not raster tiles. Start/end are snapped to main-road nodes, not the exact square/beach centroid.

See [CREDITS.md](CREDITS.md) for attribution and licensing.
