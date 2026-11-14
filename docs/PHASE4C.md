# Phase 4c: enclosed, quality-first RN24 corridor

## Focused art pass after checkpoint `9ca71cd`

The functional checkpoint was committed before the art pass. The user replaced
the former 1.6M expanded-both-LOD soft limit with **KN5 ≤2.0M vertices**, **≤8,000
TreeFX instances**, all roots **within 80m of the road edge**. The validator checks
these directly. Expanded triangle totals remain diagnostics, not a hard limit:
TreeFX instances share model buffers and select LODs rather than drawing both
LODs for every instance. This is not a measured FPS/VRAM guarantee.

The revised plan uses DEM-sided, noise-modulated bands: overlapping four-mound
maquis groups behind both verges, with staggered pine/olive bands behind them
(mostly 10–40m from the verge). Sea-side scrub is slightly lower, with tree and
scrub bands broken by deliberate sea-view openings. Native GrassFX scattering remains
enabled for low weeds/tufts; it is not represented by thousands of extra KN5 meshes.

Pine and olive terminal branch clusters now have eighteen overlapping, larger cards
instead of four. Pine card textures combine twelve photographic sprigs; slight
alpha expansion retains needle coverage at the 0.5 mip-test threshold; the existing
Blender cutout preview uses 0.3, without adding an AC/CSP cutoff key.
The coverage-preserving mip tests and external archive checks remain in place.
Golden-angle orientations and wider cluster scatter avoid stacks of nearly
parallel cards. RGB bleeding excludes black pixels introduced by alpha dilation.
Maquis groups have four dense ground-touching mounds. Physics is unchanged.
The verge belt roots sit around 6.5m from the road edge, with full trees around
12.5m and a second layer near 25m. Elongated maquis follow the road tangent;
their far LOD uses two overlapping tangent-facing cards rather than a wide
cross-road card. Planning and exported-archive validation measure their rotated
convex footprint across both LODs, preserving at least 4m canopy clearance without
mistaking the hedge's along-road length for its cross-road width. Other species
retain the conservative enclosing-radius clearance check.

Terrain macros gain stronger low-frequency olive/yellow-green/brown hue variation.
Procedural soil/needle-litter patches conform to actual terrain beneath a sampled
subset of tree/shrub roots; they use the already verified alpha-test shader,
with no collision or shadow casting. More small corridor stones reuse the existing
rock material. RainFX classifies litter as rough, and GrassFX treats it as occluding.
The low-sun camera looks along road_40 with the mountain band between sun and road.
The resumed style pass adds procedural base-stained concrete panels among the
moss/strata stone walls and reflector caps to extended rail posts. Existing rubber,
wear, repair patches and junction arrows are retained. There are no copied banners,
brands or third-party tree models. Denser preview batches are split below 60k vertices
instead of exceeding Blender/export mesh limits; external TreeFX geometry stays instanced.

The initially requested 2–3× density increase was cancelled after the user's
in-game TreeFX/GrassFX test. Existing 4b TreeFX loading and GrassFX operation are
user-reported working; the revised models/placement still require acceptance.
The visual reference is an enclosed touge corridor, not Japanese geography or
signage. Real DEM elevations and the existing road triangles remain authoritative.

## What changed

- Concentrate trees/maquis within 80m of the road edge, with mountain-side verge
  belts, clustered pockets, illustrative town grove rows and larger hero trees.
  Beyond that, no full trees; retain the cheap DEM backdrop and sea views.
- Tapered, leaning pines, thick twisted olives and narrow layered cypress use
  original procedural trunks and recursive bifurcating branches. Many smaller
  alpha cards have canopy-outward normals and softened edges. Full trees and
  taller maquis use TreeFX; low scrub/tufts continue through GrassFX. The regular
  KN5 fallback remains opt-in and retains its original simpler models/300m plan.
- Retaining blocks, rock cut/cliff facings, visual guardrail extensions and posts,
  reflector delineators, U-channel drains, small stones, chevrons, speed boards,
  fences and two bus shelters. Old power poles/km markers/physical rail collisions
  are retained. All new meshes are visual-only, merged by 400m route chunk/material;
  visual rails are not new crash barriers. The U-drains sit on the verge instead
  of excavating or changing the accepted physical terrain ribbon.
- Cut/cliff overlays are copies of actual steep ribbon triangles, offset 25mm
  along their normals. Higher terrain determines the mountain side; outer-ribbon
  drops determine supplementary rail locations. No invented mountain elevations.
- Moss/strata detail and multi-scale color variation reuse CC0 rock/grass/dirt/
  gravel maps. Dry soil is less beige; dry-mask mips reduce distant contrast while
  preserving mean weights. Rubber grooves/cracks/worn paint stay subtle. A few
  OSM junction approaches get unique 400m road atlases with arrows, so arrows do
  not repeat every 140m on unrelated road chunks. No road geometry is moved.
- Lower the existing landscape/beach support shadow ledge from 100mm to 15mm
  beneath the preserved ribbon. This changes the new landscape only, not original
  road/kerb/shoulder/ribbon meshes or `surfaces.ini`.

## Beige-band identification

`scripts/blender_mesh.py:107–116` assigns the narrow strip between terrain columns
1–2 to `1GRAVEL_*`/`gravel`: it is 1.5m wide. The much broader flat strip beyond
column 2 belongs to `1GRASS_*`/`grass` or `grass_mountain`, not asphalt/shoulder.
For example, at road_40 the left offsets are 3.5, 3.8, 5.3, 13.3, 21.3, 31.3,
45.3m: the first 8m beyond the gravel is nearly flat terrain. The matched Cycles
4b view shows the narrow pale gravel band and the broader plain green ribbon.
No in-game screenshot was supplied to prove which pixels were called beige;
both materials now receive variation, and the terrain dirt blend is greener.
Physical names, widths and original triangle positions stay unchanged.

## Asset research (models NOT integrated)

Verified against Poly Haven's asset pages/API and
https://polyhaven.com/license (all downloadable assets are **CC0-1.0**):

| Candidate | Exact license / URL | Suitability and limitation |
|---|---|---|
| Poly Haven Pine Tree 01 | CC0-1.0 — https://polyhaven.com/a/pine_tree_01 | Pine branch/bark reference and texture islands; original high-poly model is unsuitable as-is for AC. Only its twig texture is used, no model. |
| Poly Haven Island Tree 01 | CC0-1.0 — https://polyhaven.com/a/island_tree_01 | Gnarled trunk and dense small-leaf crown; not verified as olive or locally native; requires retopology/LOD work. No files integrated. |
| Poly Haven Fir Tree 01 | CC0-1.0 — https://polyhaven.com/a/fir_tree_01 | Three branched conifers/needle textures; fir is not Aleppo pine; reference/candidate only. No files integrated. |

No TreeFX-ready CC0 pack was verified in the checked Poly Haven catalog/wiki;
these are source-model candidates, not claimed drop-in TreeFX assets. AmbientCG's
previously credited Metal003 remains the verified steel base; existing Poly Haven
Pine Bark remains in use. No model/texture from another track is copied.

The **only new downloaded art used** is Pine Tree 01's 1K RGBA twig diffuse:
https://dl.polyhaven.org/file/ph-assets/Models/png/1k/pine_tree_01/pine_tree_01_twig_diff_1k.png
SHA-256 `d02c031de64b8ad671f3dd0da19870fa4783d912ae6674aeab0702871deeaeaa`.
`data/foliage_assets.lock.json` pins it for the assets/vegetation stages. Crop the
needle twig island, not cones or extruded transparent RGB; resample into the 1K
BC3 atlas and preserve alpha coverage in mips. Olive/cypress/maquis remain
procedural art, not claimed photographs of those species.

## Verified rendering/settings evidence

- TreeFX wiki `Tracks-–-Trees.md:1` describes hundreds of thousands of trees using
  instancing/LODs/billboards, and does not document a smaller track-wide cap.
  This is not a performance measurement or a reason to raise this track's count.
- TreeFX fake-shadow opacity is documented at `Tracks-–-Trees.md:61`. Optional VAO
  bakery ambient shadows/list compilation are documented at `:113–127`; no VAO
  bake was attempted on Linux. Existing BIN `FAKE_SHADOW` defaults follow the CM
  converter, documented in `TREEFX_FORMAT.md` (Converter:131–137).
- `acc-shaders/custom_objects/ksTreeFX_ppshadows_ps.fx:1–2` includes the tree
  shader; `ksTree_ppshadows_ps.fx:1–3,22–23,52–53` provides alpha coverage, shadow
  sampling and alpha output. These sources do not establish this CSP version's
  runtime shadow-pass dispatch; test shadows in-game.
- `blender-assetto-corsa-tools/exporter/node_writer.py:42,162` verifies KN5
  `castShadows`; solid kit meshes explicitly enable it and KN5 readback checks it;
  ground-conforming litter patches explicitly disable it.
- Existing verified RainFX groups include metal/signs/reflectors as smooth,
  rock/bark as rough and plaster/concrete as soaking. GrassFX still uses only
  grass/grass_mountain surfaces and verified custom atlas groups; no guessed
  per-rail spawn keys or Pure overrides were added.
- Asphalt keeps the reviewed multilayer shader, ksAmbient=.4 / ksDiffuse=.6,
  fresnelMaxLevel=.16 / tarmacSpecularMultiplier=.16. Texture targets stay neutral
  grey. The low-sun render uses Cycles CPU stand-ins, not AC/CSP/Pure lighting.

## Concrete in-game acceptance checklist

### Linux visual review and remaining limitations

The eleven-view contact sheet is `out/preview/v2_roadside/contact_sheet.jpg`.
Repeated Cycles CPU renders show stronger overlapping verge belts on both sides,
retained sea openings, stained concrete panels and vegetation shadows crossing
the roadway at low sun. This is not a fully roofed forest tunnel: open sky and
some grass remain visible, and close-up crowns still expose dark, faceted
alpha-card clusters. Treat those as remaining art limitations, not proven native
TreeFX appearance. Windows acceptance is still required before visual sign-off.

### Windows checklist

1. Install the whole ZIP (including KN5 and `extension/trees`), not only the KN5.
   Confirm TreeFX and GrassFX still load; note missing-model/config warnings.
2. Drive start/town, road_40 hills, Boulimat coast and Saket in daytime. Check
   distinct branched silhouettes, no opaque card rectangles, soft leaf edges,
   no floating roots and no canopy crossing the carriageway. Verify the close
   corridor feels enclosed without hiding the intentional sea-view openings.
3. At low sun, inspect tree/bush/wall shadows on the road: silhouettes should
   follow alpha, not full rectangular cards; inspect pop-in around 150/600m and
   distant TreeFX billboards. Compare MSAA and watch for shimmer/dark leaf halos.
4. Check retaining/cut faces, original and extended rails, reflector spacing,
   bus shelter scale, drain intersections and signs from both driving directions.
   New visual rails/walls/furniture are not guaranteed collision barriers.
5. Inspect broad grass ribbon and narrow gravel separately at noon/overcast.
   Look for improved variation and reduced joins, not a change of road width.
   Stop if landscape appears above the roadway. Inspect switchback joins.
6. Enable preview RainFX and test dry → wet: asphalt/paint, metal rails/signs,
   rough rock and concrete drains. Check Pure sunrise/noon/overcast without
   adding track-specific Pure keys. Capture screenshots if colors disagree.
7. Record FPS/frame-time and VRAM versus accepted 4b from the same car/camera,
   weather/time and CSP settings, including dense pockets and wet low sun.
   This Linux build cannot certify FPS, allocation, native wind or shadow behavior.
