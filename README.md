# Béjaïa → Saket: Assetto Corsa track preparation

Phases 0–5 plus v2 materials: a 24.24 km OSM-derived Béjaïa city-center → Saket coastal RN24 track, with Copernicus DSM elevation, procedural Blender geometry/decor, validated KN5 install folder and ZIP. **The user reports v1 loads and drives in AC; v2 materials still require AC/CSP/Pure acceptance testing.** This is a provisional, unsurveyed low-poly reconstruction, not a claim of racing accuracy.

## CSP / Content Manager settings

`scripts/build.py csp` generates `out/bejaia_saket/extension/ext_config.ini`
from `scripts/ext_config.ini.template`, reading the exact KN5 inventory in
`data/materials_info.json`. The default `all` and `materials` builds include it.
Reinstall the whole folder, including `extension/`, not just the KN5.

In Content Manager **Settings > Custom Shaders Patch**, enable **Grass FX**,
**Rain FX** and **Weather FX**; select the installed **Pure** weather script in
Weather FX. RainFX requires a compatible preview build (the user's Patreon
preview provides it). Enable **Lighting FX** for CSP lighting features;
**Extra FX** is optional for richer reflections and is not required for this
basic config. Menu labels can vary by preview/CM/Pure version; these are human
setup instructions, not INI keys. Pure's exact current UI remains UNVERIFIED
locally; no guessed Pure track keys or atmospheric overrides are shipped.

Sources for each shipped section (paths relative to CSP's config repo/wiki):
- `[GRASS_FX]`: wiki `Tracks-–-Grass-FX.md:5–54`; real example
  `config/tracks/putnam_park.ini`. Only `grass` and `grass_mountain` spawn grass.
  Multilayer txMask G selects shorter grass over dry soil, using
  `[GRASS_FX_CONFIGURATION_A]` / `[GRASS_FX_ADJUSTMENT_0]` from wiki
  `Tracks-–-Grass-FX.md:79–129,187–204` and real example
  `config/tracks/ks_silverstone.ini` (multilayer GrassFX adjustments).
  Color rejection is disabled because the macro diffuse is neutral; material
  selectors still prevent blades on roads or beaches.
  Ground's green-olive/dry-soil textures provide the intended palette; no
  unverified blade COLOR property is invented. Color masking/shape values are
  artist tuning requiring an in-game check, especially with multilayer terrain.
- `[RAIN_FX]`: wiki `Tracks-–-RainFX.md:3–18`; real example
  `config/tracks/putnam_park.ini`. Roads puddle; porous surfaces soak; vegetation,
  rock and sand stay rough; metal is smooth. Markings are baked into road atlases:
  `LINES_FILTER_MATERIALS` selects bright texels, rather than classifying the
  entire asphalt as paint. No arbitrary atlas-mask-channel binding was verified.
  Bright repairs/aggregate can also be picked up; exact filtering on our
  multilayer road shader and wet grip require AC testing.
- `[INCLUDE: common/materials_track.ini]` and `[Material_Water]`:
  `config/tracks/common/materials_track.ini:53–69,310–364`, real example
  `config/tracks/monaco_2017.ini:16–23`; wiki `Tracks-–-Water-shader.md:5–15`.
  SEA mode uses CSP's installed recommended normal textures, not copied assets.
  Existing visual-only sea is flat at datum zero, upward-facing, ~6.23×4.26 km,
  with finite planar UVs (~4 m repeat); no displacement geometry is added.
  Reflections/wave scale and shore blending still require CSP runtime inspection.

No `[LIGHTING]` overrides: wiki `Tracks-–-General-options.md:10–17` says ground
ambient should only be overridden if needed. With Pure and no lamps, default
lighting is retained. Lamp posts and `[LIGHT_SERIES_...]` are deferred to Phase 4.
Wind/tree conversion is also deferred: current trees are merged solid blobs,
not weighted cards (`Tracks-–-General-options.md:39–47`, `Tracks-–-Trees.md`).
No `[BASIC]` or seasonal/ambient overrides are needed; defaults/Pure remain in
control. Source links and runtime limitations are expanded in `docs/CSP_NOTES.md`.

Sand correction: the bound CC0 diffuse itself averaged ~66/58/45 sRGB, versus
v1's ~207/189/138. Bindings, upward normals and finite UVs were checked; the
warm pale grade restores the beach while retaining its normal/detail maps.
Asphalt and repair diffuse targets are now 12% darker (~84/84/84 and ~62/62/63).
Only `road_95` and `decor_saket` were re-rendered for this pass, under
`out/preview/csp_material_fixes/`; the earlier complete v2 comparison is retained
as an accepted historical snapshot. Reproduce this subset with:
`scripts/build.py render --views road_95 decor_saket`.

## v2 material build and comparison (previous pass)

`v1` remains tagged and its install/ZIP are locally backed up under
`out_backup_v1/`. These large ignored backups are not part of a clone; the tag
retains the v1 scripts, pinned dependencies and clean-rebuild evidence.

The default full build now runs **assets → route → dem → centerline → mesh →
acdata → decor → materials → csp → ZIP → validate**. Linux additionally needs `curl`
and ImageMagick's `convert` with its DDS encoder. Development commands:

```sh
.venv/bin/python scripts/build.py assets       # pinned CC0 downloads, SHA-256 checked
.venv/bin/python scripts/build.py materials    # requires existing decor scene
.venv/bin/python scripts/build.py render       # optional matched Cycles CPU comparisons
```

`data/assets.lock.json` records exact source IDs, licenses, URLs and SHA-256.
Raw maps are cached in ignored `data/asset_cache/`. Missing files are downloaded
atomically; corrupt cached files are rejected and must be explicitly removed
before re-downloading. Builds never refresh checksums from the network.
Generated `textures/v2/` is ignored and reproducible from the lock and seeded
`scripts/materials.py`. The installed KN5 embeds the used textures: no external
texture folder is needed. See `data/materials_info.json` for the exact exported
shader/slot/property recipe, per-texture dimensions, format, mip count and bytes.

Road and terrain use verified `ksMultilayer_fresnel_nm4`, chosen because its
world-XZ detail coordinates avoid anisotropic grain when road UVs span width
versus chainage. Road uses three 2K atlas/mask variants, 1.75 m CC0 detail,
normal maps, tyre wear, lighter lane centers, procedural repair masks and worn
paint. The original **7 m dash period / 440÷1024 painted fraction** is retained;
this is preservation of v1, **not a verified Algerian road-marking standard**.
Terrain uses a 256 m low-frequency grass/dry-soil mask and 4 m detail. Other
surface tiles: gravel/kerb 2 m, rock 6 m, sand 4 m, plaster 3 m, metal 1 m, bark
2 m. A 140 m strip keeps repairs occasional (one small, feathered repair per
strip); background macro variation still repeats at 28 m. Detail is neutral
grey (worn ~95/95/95 sRGB, repairs ~70/70/72), with subtle tyre wear. Gravel is
grey-beige. Grass is green-olive; dry patches cover 25% of the inland/left
ribbon and 35% of the coastal/right ribbon. Treating left as mountain-side is
a route-wide artistic approximation, not a surveyed slope classification.
Source assets and procedural-derivative qualifications are in CREDITS.

Opaque RGB textures use DXT1; channel masks, detail color/specular-alpha and
RGB XYZ normals use DXT5. Every DDS has a full mip chain. **No BC5 is used**.
DirectX-oriented normal RGB is stored explicitly (GL green flipped); AC/CSP
normal handedness and final gloss still require runtime inspection. DDS memory
is the exact sum of compressed mip payloads; untouched PNGs are estimated as
RGBA8 base levels in `texture_gpu_bytes`. Driver overhead/PNG runtime mip
generation is not measured VRAM. Artist-chosen properties are not stock defaults.

Physical names, surfaces.ini, mesh coordinates/topology/transforms, all foliage,
and water geometry remain unchanged. Bark, buildings and beach change **materials/UVs
only**; decor placement and geometry are untouched. The previous material pass
added no CSP configuration; the section above supersedes that status. See `docs/CSP_NOTES.md` §9 for
new source citations, verified sampler order and exporter trap handling.

Comparisons: `out/preview/v2_materials/before/` and `after/` contain the same six
v1 camera views; `side_by_side.jpg` pairs them. These are **Cycles CPU approximations
using the same maps**, not AC shader/CSP/Pure screenshots. Lighting, camera
positions, resolution and scene geometry are held fixed. Distant terrain slabs
and foliage silhouettes are intentionally not fixed here.
Both sides use 16 samples and denoising, with identical camera/light settings.
Previews blend all four detail colors and approximate normal mapping; they
are not proof of AC/CSP shader behavior.
Material texture generation was tested with ImageMagick 6.9.11-60 Q16.
Preview rendering is optional and never invoked by `materials` or `all`.
The optional comparison stage needs the local `v1` tag to read its baseline scene.
Legacy Blender preview calls are also disabled by the build driver. Existing
UI thumbnails remain until `render` refreshes them. Cycles replaces the headless
Eevee comparison path that stalled on this VM (underlying cause UNVERIFIED).

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
.venv/bin/python scripts/build.py                 # default: all
# Equivalent: .venv/bin/python scripts/build.py all
.venv/bin/python scripts/validate.py              # standalone package check
# Individual stages for development:
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

### Linux prerequisites and complete build

Building on Windows is **UNVERIFIED**; scripts currently use Linux runtime-directory handling. On Linux install Python 3.10+ with venv support, official [Blender 3.6.23](https://download.blender.org/release/Blender3.6/) at `~/tools/blender-3.6.23-linux-x64/blender` (or pass `--blender`), and clone the [exporter](https://github.com/moppius/blender-assetto-corsa-tools) to `~/tools/blender-assetto-corsa-tools` (or set `AC_ADDON_SOURCE`). The export stage imports/registers the addon headlessly; no interactive addon setup is needed. Optional comparison rendering uses Cycles CPU, not an OpenGL renderer. The pinned Python dependencies are in `scripts/requirements.txt`; Blender uses its own bundled Python/numpy.

`all` runs **assets → route → dem → centerline → mesh → acdata → decor → materials → landscape → csp → ZIP → validate**, failing immediately on a stage error. It creates missing output directories and downloads missing `data/algeria-latest.osm.pbf` plus `data/dem/N36E004.tif` and `N36E005.tif`. These raw downloads and `data/asset_cache/` may be copied to another checkout to avoid bandwidth; do not copy generated arrays, Blender scenes, extracted area caches or outputs for a clean-rebuild proof. Upstream `algeria-latest` is mutable: identical results require the same PBF/DEM bytes and pinned tools, not a later live download. Preserve `data/source_info.json` and `data/dem/sources.json` as provenance; v2 material downloads additionally enforce `data/assets.lock.json`.

Deliverables: `out/bejaia_saket/` and `out/bejaia_saket.zip`, whose root is `bejaia_saket/`, not loose install files. ZIP entries have normalized timestamps/permissions and sorted order. `scripts/package.py` recreates only the ZIP. `scripts/validate.py [folder]` needs no Blender or generated centerline arrays: it independently reads the exported KN5 and install files, checks naming/surfaces, UI/pits, logical transforms and raycasts road triangles for spawn/gate heights, physical-track bounds (excluding visual sea), sampled road-triangle cross-width edges, vertex limits, texture signatures/references and map dimensions. **PASS is static validation, not proof of engine compatibility.**

Regression tests: `PYTHONPATH=scripts .venv/bin/python -m unittest test_build test_route test_geometry test_acdata test_decor test_materials test_validate -v`. Do not use a blanket `test_*.py` discovery: `test_exporter.py` is a separate Blender smoke script requiring `bpy`, invoked with Blender as shown above, not a pure-Python unittest.

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
| `ui/preview.png` / `ui/outline.png` | **355×200** following the inspected sample: resized road-level preview (latest selected view, otherwise road_70); white route on transparent RGBA. Mandatory dimension claims **UNVERIFIED**. |
| `extension/ext_config.ini` | Generated CSP GrassFX, RainFX and SEA water setup; template, sources and CM settings are documented above. |
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

## Phase 4a — continuous DEM landscape and horizon

Existing road, kerb, shoulder, terrain ribbons, beach, props and AC spawns are
preserved. `scripts/build.py landscape` adds terrain to the existing v2 scene;
`all` runs it after `materials`, then regenerates CSP configuration and validates.
The stage replaces its own tiles and sea rather than stacking geometry.

- Copernicus GLO-30 **interpolated at 11 m** within 400 m of the route, 30 m
  to 2.5 km, and 90 m to 8 km. The 11 m near grid keeps the added landscape
  below 600k triangles; it does **not** imply an 11 m elevation survey.
- A 250 m DEM backdrop continues to approximately 14 km using the same two
  cached TIFF tiles. This models local inland foothills, not more distant
  Babors peaks outside the domain. No invented mountain silhouettes/assets.
- One global triangulation includes every domain-boundary vertex before
  clipping. All bands and tile groups share edge positions and smooth normals;
  no LOD-band skirts or separate overlapping resolution surfaces are needed.
- The union/valid polygon of both ribbons is inset 1 m to allow a hidden
  underlap. An explicit road-polygon exclusion also protects route end caps.
  Border vertices follow the original ribbon edges about 0.1 m below them.
  Existing beach faces are supported by terrain just below the sand surface.
  Tight hairpins are treated as a single polygon, not independent strips.
- Deterministic noise has maximum amplitude 1.45 m, fading in only beyond
  100 m from the road. Terrain intersecting the 150 m route buffer is physical
  `1GRASS_LAND_*`; outside it `LAND_*` is visual-only. Boundary triangles are
  conservatively physical. Near tiles are 400 m, medium 800 m, far 2000 m.
- Coastlines come from all coastline ways in the cached Algeria PBF, not the
  smaller route-area cache. Seaward ground is pulled below Z=0; coastal DEM
  drops above 10 m steepen through a 10 m coastal transition. Slopes over 35° use
  the existing `rock`; gentler ground reuses `grass`. GrassFX already references
  that exact material, so no new shader, texture or CSP key was introduced.
- The visual-only sea is replaced by a flat coastline-clipped plane extending
  approximately 15 km offshore in the route area, with 4 m UV repeats. Landscape
  and sea have 60 km export draw distances (exporter `NODE_SETTINGS` / `lodOut`
  in `exporter/node_writer.py`); the old corridor retains its export settings.

`data/landscape_info.json` records geometry budgets, physical/visual counts and
the identical corridor hashes before/after scene assembly. `validate.py` checks
road overlap, below-ribbon border heights, physical/visual separation, terrain
budget and the existing per-mesh vertex limits. The global boundary audit and
hairpin-hole test check that no unmatched internal edges cross resolution bands.

Optional **Cycles CPU** previews (not part of `all`):
```sh
.venv/bin/python scripts/build.py render --terrain
```
Nine images and `contact_sheet.jpg` are under `out/preview/v2_terrain/` (individual
PNGs in `after/`): top, the six standard views, elevated Boulimat and city start.
These approximate materials only; AC/CSP/Pure water, collision performance,
grass density, long-range culling and FPS require a new Windows drive test.

## Known issues

- The old 40 m floating-ribbon horizon is superseded by the Phase 4a landscape.
  Source DSM trees/buildings, coarse far slopes and non-surveyed coastline/datum
  remain limitations; runtime terrain acceptance still needs a Windows drive.
- Thin dark contact-shadow seams remain along some preserved ribbon/beach edges
  in Cycles (not open holes); the support terrain is deliberately below them.
- No AI fast lane is bundled; use **Practice**, not an AI race. Timing, launcher acceptance without AI and pit servicing remain **UNVERIFIED on Windows**.
- Decor is pass-through, sea/beach are simplified visual placeholders, and there is a crude physical end wall. Do not approach the finish at racing speed during initial tests.
- DSM includes trees/buildings; widths, elevations, local intersection realignment and generic props are not surveyed. The KN5 split branch, map overlay alignment, runtime shaders, surface response and collisions remain **UNVERIFIED** despite static validation.

## HUMAN STEPS — install

Back up any existing version. Extract `out/bejaia_saket.zip` directly into `<Steam>/steamapps/common/assettocorsa/content/tracks/`, or copy `out/bejaia_saket/` there. Final path must be **`<Steam>/steamapps/common/assettocorsa/content/tracks/bejaia_saket`**, with `bejaia_saket.kn5` directly inside it, not another nested `bejaia_saket/`. This conventional track-folder location is documented in the [basic guide](https://assettocorsamods.net/threads/build-your-first-track-basic-guide.12/). No CSP dependency is intentionally required; vanilla compatibility is **UNVERIFIED**.

## HUMAN STEPS — first Windows test and logs

This is an acceptance checklist, **not an observed Windows result**:

1. In Content Manager or the vanilla launcher choose **Béjaïa – Saket (RN24)**, an official Kunos road car, **Practice**, no opponents, daylight/dry conditions. Avoid Race/AI modes; [modding troubleshooting recommends Practice when no fast lane exists](https://assettocorsamods.net/threads/cant-load-my-own-track.1543/). Exact launcher UI/version behavior is **UNVERIFIED locally**.
2. On spawn, wait for the assumed 1.5 m drop: check the car settles on asphalt rather than falling through, is on the right-hand lane, faces down-road and has plausible lane/car scale. Check return-to-pits and hotlap spawns separately when basic loading works.
3. Drive slowly first. Check road/kerb/shoulder contact, seams, slopes, guardrails/end-wall collision at walking speed, scenery clearances and visible ocean height. Record FPS/resolution, car, GPU and AC/CM/CSP versions; monitor town and coastal stretches. Pass-through decor is intentional, not a collision bug.
4. Drive through AB start at 200 m, both intermediate timing lines (~8.146/16.091 km), and finish 50 m before the end. Check timer start, sector capture, finish and whether a saved time survives restarting. All A2B timing behavior is **UNVERIFIED** until this test. Brake early; 50 m runoff is not adequate at racing speeds.
5. Immediately after failure (before another session replaces evidence), send **`Documents/Assetto Corsa/logs/log.txt`** and the other files in that logs folder, plus screenshot/error text and the exact install path. This filename/location is explicitly identified in [Can't load my own track](https://assettocorsamods.net/threads/cant-load-my-own-track.1543/). Use your actual Windows Documents location, including OneDrive/redirection if applicable.
6. If using CM, also send its recent **`%LOCALAPPDATA%\AcTools Content Manager\Logs\`** files. Verified from CM source: [EntryPoint.cs](https://github.com/gro-ove/actools/blob/master/AcManager/EntryPoint.cs) selects `LocalApplicationData/AcTools Content Manager`, and [App.xaml.cs](https://github.com/gro-ove/actools/blob/master/AcManager/App.xaml.cs) initializes logging under `Logs`. EntryPoint also supports a custom data directory and a local/portable executable mode; these override that default, so collect `Logs` from the actual CM data directory in those cases. Exact current-build log filenames are **UNVERIFIED**; send the folder's recent files rather than guessing one.

Review logs for personal filesystem paths/usernames before sharing. The rebuild/validator logs and `data/kn5_export_info.json` are useful companion evidence, but do not replace Windows logs.

## HUMAN STEPS — record an AI line (not bundled)

Sources: administrator luchian's [AI recording procedure, post #2](https://assettocorsamods.net/threads/how-can-i-make-ai-path.234/) and [hill-climb recording tutorial/correction](https://assettocorsamods.net/threads/basic-fast_lane-and-cameras-tutorial.1265/). Back up game configuration first.

1. Edit **`<Steam>/steamapps/common/assettocorsa/system/cfg/assetto_corsa.ini`** and set the documented section/key (not an invented `[AUTOSPAWN]` switch):
   ```ini
   [AC_APPS]
   ENABLE_DEV_APPS=1
   ```
2. Load this track in Practice with a car, open the in-game **AI** developer app, and press **start recording**. Drive a smooth continuous line staying on valid asphalt; lap speed is less important than smoothness.
3. For this open stage, the hill-climb tutorial says to finish the run and exit the track. The circuit guide alternatively describes stopping via the **recording** button and **Save ai**, then exiting; saving can take time on a long track. The circuit guide's “at least two laps” instruction does **not** apply literally to this open road. Recording start/end relative to this track's AB gates and reliable A2B saving remain **UNVERIFIED**; do not drive through the end wall or invent a closing loop.
4. Inspect **`content/tracks/bejaia_saket/ai/fast_lane.ai.candidate`**. With Windows file extensions visible, rename the candidate to **`fast_lane.ai`** (back up an existing line). The cited guide also suggests copying the chosen ideal line to `data/ideal_line.ai`. No such generated file is currently supplied.
5. Test the recorded line before enabling AI opponents. [Reported A2B spline-closing problems](https://assettocorsamods.net/threads/is-it-possible-to-do-a-proper-ai-lane-in-a_to_b-track-hill-climb.1077/) mean successful recording alone is not proof of correct hill-climb AI. Pit-line recording uses **start pits** according to the guide, but this track has no modeled pit lane: pit AI and race use are **UNVERIFIED**, not recommended yet. Restore the dev-app setting when finished.

## HUMAN STEPS — fallback if KN5 will not load

First check folder nesting and Practice mode, collect the logs above, and run `scripts/validate.py` on the exact installed folder if Python dependencies are available. A static PASS cannot rule out runtime/exporter incompatibility.

The sourced alternative workflow is **Blender/modeler → FBX → KsEditor → KN5** ([workflow discussion](https://assettocorsamods.net/threads/need-some-advices-to-start-workflow.2757/), [FBX import/shader/export explanation](https://assettocorsamods.net/threads/is-there-a-guide-to-adding-cones-to-a-mod-track.1682/)). On a Windows machine with the AC SDK, use the supplied `blend/bejaia_saket.blend` as the source, export an FBX, import that FBX in KsEditor, assign/check shaders/textures and logical objects, and export a replacement KN5 under the same filename; preserve the original and revalidate/retest. This is a high-level fallback, **not a verified click-by-click recipe**. Directly opening this KN5 in KsEditor, exact FBX export settings/axis conversion, material persistence, UI menu labels and a full KsEditor round trip are **UNVERIFIED** here. Do not blindly reuse the direct exporter's empty rotations for a different FBX conversion; recheck axes against repository `docs/AC_NOTES.md` and the basic guide before testing.

### Phase 4b baseline: procedural Mediterranean vegetation

The following records the accepted 4b baseline; current 4c behavior supersedes its
counts, tree prototypes and planting band as described in the next section.

`build.py vegetation` replaces the old solid foliage from a 5,000-plant deterministic,
clustered, terrain-snapped plants: Aleppo/stone pines, olives, Italian cypress,
maquis, reeds and dry grass, each with three shape variants and three atlas tints.
Placement favours the mountain side, rejects slopes above 35 degrees, sea/beach
and buildings, and leaves at least 4 m between the complete canopy and road edge.
Roots sample actual exported terrain triangles; foliage is visual-only. Road,
kerb, shoulder and terrain geometry and physical surface definitions are retained.
Far planting beyond 300 m from the route is deliberately skipped. **TreeFX is the
default**: 3,272 terrain-snapped tree/reed instances in 41 external model archives.
Low maquis and dry tufts move to terrain-only GrassFX custom atlas groups, replacing
1,728 explicit placements with native surface scattering (not the same positions).
Enable Grass FX and TreeFX support in a current CSP build. No CM model conversion
step is required: the Linux writer and reader follow the pinned open-source CM
converter field by field; see [docs/TREEFX_FORMAT.md](docs/TREEFX_FORMAT.md).
The Linux build uses system `libxxhash.so.0` (Ubuntu package `libxxhash0`) for
the exact texture checksum required by that format; it is installed on this VM.

Six procedural 1024-square BC3/DXT5 atlases (canopy/impostor in three tints) have
11 mip levels with per-species alpha-coverage scaling. Cards have explicit
reversed back faces and canopy-outward custom normals. For the fallback, `ksPerPixelAT`,
`alphaTested=true`, AlphaToCoverage (2), normal depth writes and `txDiffuse`
are verified against the shader/exporter sources cited in `docs/CSP_NOTES.md`.
Bark reuses the accepted PBR material. Default tree shaders are native TreeFX;
they are not KN5 material replacements. TreeFX's source has native height-driven
wind, but actual runtime dispatch/appearance remains unverified; no custom wind
keys/weights are added. Fallback wind is deferred. GrassFX uses the verified
`TEXTURE`, `TEXTURE_GRID`, `GRASS_FX_TEXTURE_GROUP_0` and chance/size keys; syntax
sources are cited beside the generated sections and in the format document.

External models provide full LOD0 and two-card LOD1 with distances 150/600 m;
TreeFX owns per-instance culling, instancing and native distant billboards.
`build.py vegetation --kn5-vegetation` (also supported by `all`) instead exports
all species in merged 400 m route chunks, full LOD0 at 0–150 m and two crossed,
double-sided impostor cards at 150–600 m, then cull. These are object-distance ranges, not
individual-tree distances: chunk-level popping and final transitions need AC
testing. Exporter support: `exporter/node_writer.py:39–40,182–183` in
[blender-assetto-corsa-tools](https://github.com/moppius/blender-assetto-corsa-tools).
The fallback has 427 vegetation objects; 1,057,188 → 1,517,726 total triangles
(LOD0 519,138, LOD1 40,000), under the approximately 1.6M target.
Fallback KN5 has 1,711 meshes, 20 materials, 46 textures and 201,061,253 bytes.
Default TreeFX KN5 reduces the accepted 4a file from 155,241,351 to 141,232,395
bytes, 1,506 → 1,284 meshes, 1,795,971 → 1,508,297 vertices and
1,057,188 → 958,588 triangles. Counting every external tree instance's two LODs
as if expanded adds 898,332 vertices / 449,166 triangles, giving 2,406,629 vertices
and 1,407,754 triangles including the base KN5. Actual TreeFX uses instancing and
selects LODs; GrassFX geometry is generated dynamically and is not in those counts.
The default package has 14 KN5 materials / 40 embedded textures, plus external
TreeFX assets. Unique texture payload including decoded PNGs is 78,994,184 bytes
(about 75.3 MiB), versus 73,751,144 bytes in accepted 4a; this is a content estimate,
not measured CSP GPU allocation (cross-model/GrassFX cache behavior is unverified).
Fallback DDS GPU payload increases from 68,508,264 to 76,897,032 bytes; two
retained PNG textures are additional decoded GPU memory. Primary-path metrics
are in `data/kn5_export_info.json`, `data/materials_info.json` and `data/treefx_info.json`.

Optional `build.py render --vegetation` writes the six standard views and
`trees_closeup.png` to `out/preview/v2_veg/after/`, plus `contact_sheet.jpg`.
These use Cycles CPU, 16 samples and denoising, with alpha-clipped mesh stand-ins
for the same TreeFX prototypes and representative GrassFX tufts/scrub, not AC
shaders or exact GrassFX scattering. The inspected set has irregular cutout silhouettes,
no opaque card rectangles and no visible trees crossing the road; density remains
sparse on some stretches. Terrain seam shadows and dry-patch masks are unchanged.
AC alpha-to-coverage/MSAA appearance, mip shimmer, LOD transitions, wind, collisions
and FPS remain runtime-unverified; Cycles previews show LOD0, not AC LOD switching.

### Phase 4c: quality-first enclosed roadside corridor

Functional checkpoint: **`9ca71cd`**. The subsequent focused art pass uses overlapping
DEM-sided maquis groups and staggered pine/olive bands on both sides, fuller crowns, stronger
terrain hue variation and conforming visual litter patches under vegetation.
The current limits are **KN5 ≤2.0M vertices**, **TreeFX ≤8,000 instances**, all roots
within **80m of the road edge** (maquis near 6.5m, full trees mostly within 10–40m). Expanded-both-LOD triangles
are reported only: instancing shares models and LOD selection does not draw both
LODs simultaneously. The former 1.6M expanded-geometry budget is superseded.

TreeFX remains the default. The proposed density increase was cancelled in favor
of tapered, bent trunks, recursive branching and many smaller canopy cards.
Pines use a checksum-pinned CC0 photographic Poly Haven twig crop; olive, cypress
and maquis textures remain procedural, with soft alpha edges. Full trees and
tall maquis are clustered within **80m of the road edge**, with town grove rows,
mountain-side verge pockets and occasional 1.38× hero trees. Distant trees are
omitted; the DEM backdrop is retained. Low scrub/tufts also use GrassFX. The KN5
fallback retains the original lower-detail, 300m-band plan. Both paths preserve
4m canopy clearance, actual terrain snapping and a 35° root-slope limit.
The [TreeFX wiki](https://github.com/ac-custom-shaders-patch/acc-extension-config/wiki/Tracks-%E2%80%93-Trees)
(`Tracks-–-Trees.md:1`) describes hundreds of thousands of instances with instancing;
no smaller track-wide instance cap is documented there. This is not an FPS guarantee.

`build.py roadside` (also in `all`) adds terraced rock retaining walls along
existing road cuts, DEM-sided rock facings, visual cliff-side rail extensions,
reflector delineators, precast concrete U-drains, small rocks, curve chevrons,
generic 50 km/h boards, timber fences and two town bus shelters. Signs use one procedural
1K DXT1/mipped atlas and the previously verified `ksPerPixel`; other meshes reuse
rock, bark, metal and plaster. Signs are illustrative, not surveyed traffic controls.
All new `DETAIL_*` meshes are visual-only and have a 1,400m draw distance. Existing
physical road-edge `1WALL_CUT_*` and guardrail meshes are retained unchanged;
setback walls and rail extensions do not add collision or surface keys. The drains
are shallow above-ground precast channels, not excavations of the accepted corridor.

The two terrain dry-mask octaves now have lower contrast; distant mask mips fade
contrast toward their preserved mean. Landscape/beach support at the untouched
ribbon edge is now 15mm below it instead of 100mm, reducing the shadow ledge
without changing any road/kerb/shoulder/inner-ribbon triangles. The validator
retains a positive below-ribbon clearance test. Cycles cannot establish the
appearance of this join under CSP/Pure lighting.

Multi-scale terrain/detail color noise, greener dry soil and moss/strata variation
break up the plain ribbon. The narrow pale shoulder is the 1.5m `1GRAVEL_*` strip;
the wider flat band is the unchanged `1GRASS_*` terrain ribbon. Both receive
texture-only variation; physics keys and corridor geometry are unchanged. Road
atlases gain subtle rubber grooves/cracks and unique 400m chunk atlases with worn
painted arrows on a few OSM junction approaches, without moving road triangles.

Run `build.py render --roadside` for the six standard Cycles CPU views, tree/hero,
wall/guardrail closeups and a low-sun shadow view under `out/preview/v2_roadside/after/`, with
`out/preview/v2_roadside/contact_sheet.jpg`. Rendering remains optional and is
never invoked by `all` or `materials`.

See [Phase 4c sources and in-game checklist](docs/PHASE4C.md) for licensed model
candidates (not integrated), shadow-source evidence and explicit runtime caveats.

### Remaining runtime limitations

No Assetto Corsa or Windows runtime validation, ksEditor import/round trip, surveyed physical road widths/elevations, driving/collision validation, AI lines or pit-lane/repair-zone geometry. A full KN5/data package now exists; successful binary writing/readback does not demonstrate in-game correctness. OSM turn-restriction relations and conditional access/oneway tags are not modelled; this is not navigation certification. Route preview uses vector OSM roads and coastline, not raster tiles. Start/end are snapped to main-road nodes, not the exact square/beach centroid.

See [CREDITS.md](CREDITS.md) for attribution and licensing.
