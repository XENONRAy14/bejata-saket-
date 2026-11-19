# Main-route summit qualification

This is an isolated summit qualification, not a full-route rollout or AC acceptance.
The RN24 road, collision and timing remain the current main-route baseline.

```sh
.venv/bin/python scripts/build.py scenery --sector summit --scenery-render
.venv/bin/python scripts/validate_scenery_lock.py out/scenery_qualification/summit/bejaia_saket.kn5
```

The output defaults to `out/scenery_qualification/summit`; use
`--scenery-output <new-directory>` for subsequent builds. Existing output
directories are rejected. The main install is never overwritten. The optional
render uses the configured Blender binary and writes `before.png` / `after.png`
at 1030 m, 1.25 m above the road, with the same camera and lighting.
It also writes `before_exit_reverse.png` / `after_exit_reverse.png` at 1230 m.
That driver-height camera looks back into the treatment: a forward-facing camera
there would look away from the sector, which ends at 1180 m.
It approximates KN5 multilayer materials and TreeFX LODs, not CSP runtime shaders.
The renderer accepts `--reference <track-directory>` after Blender's `--` to
compare against a prior candidate instead of the main baseline. The saved
pine-pass BEFORE is `c313e15` (KN5 SHA-256
`f3ccf11188b218ee2089cca2389661c2a31a1298beaae2c144f30c1f85b8899e`),
retained locally at `/home/ubuntu/summit_pine_baseline`. The matching install
reference is `/home/ubuntu/summit_pine_reference_install`; the renderer resolves
its renamed KN5 through `models.ini`, not a hard-coded filename. Without a
manifest it tries the folder basename, then the legacy main-model basename.
The install copy retains the complete route; only summit 880–1180 m is treated.
The separate `summit` track folder includes `models.ini` referencing its KN5 and
a distinct qualification UI name. Install it as `content/tracks/summit`, not over
the main `bejaia_saket` folder.

For a clean runtime-only install folder plus ZIP, after qualification:

```sh
.venv/bin/python scripts/package_scenery.py
```

This creates `out/install_ready/bejaia_saket_summit/` and
`out/install_ready/bejaia_saket_summit.zip`, refusing existing outputs. The KN5
basename, folder ID and `models.ini` agree. UI metadata is distinct, and the ZIP
contains `content/tracks/bejaia_saket_summit/`. Preview caches/images are excluded;
credits and licenses are included. This remains a visually incomplete candidate.
Install-ready outputs and intermediate `out/scenery_cache/` archives are ignored
by Git; rebuild them rather than committing the large install ZIP.

## Implementation and lock

`qualify_scenery.py` removes existing TreeFX placements in the sector and any
legacy foliage triangles there and adds shared-atlas edge batches and TreeFX
placements. The foreground now uses cached three-dimensional Searsia radial
clusters, not atlas planes. Atlas filler starts 4.1/5.2 m beyond the road
edge, behind the shrubs. The rejected tall third-row silhouette meshes and
their atlas are no longer exported. Cards use smoothed upright normals and
orthogonal tangents. The two accepted low filler rows remain unchanged.
No pilot rail modules are imported. Forest-floor reassignment uses existing
physical `1GRASS*` geometry, without new ground overlays or UV changes.
The lateral corridor is 80 m plus half the maximum road width; selection uses
nearest active-route centreline stations. Trees are footprint-clearance checked
against every road leg by the shared planner.
For this pass, visual-only shrubs have a 0.45 m clearance target instead of the
previous 4 m setback; other vegetation remains at 4 m. The achieved minimum is
0.780540 m. Each shrub cluster's three rotated crown spheres are checked against
all road legs; no orientation-blind bounding-circle clearance is substituted.

`scenery_kn5.py` preserves untouched KN5 records verbatim and parent transforms.
Only the material assignment and material records of `1GRASS*` are exempt from
the lock; their names, flags, vertices (including UVs/normals), indices, bounds
and parent transforms remain locked. All other protected material records
remain locked. The lock covers every digit-prefixed
physical mesh, `AC_*` empty and `DETAIL_GUARD_*` visual. The required reference
SHA-256 is `7cceb8c8aeb9ec72b9031d1356b5450b7e1e38c335748964591d84036d13c61f`.
Other props are checked unchanged during generation. Source main ZIPs, the pilot
KN5 and the v1 rollback are not modified.

## Forest floor and composition

Four existing physical grass meshes receive individual multilayer material
copies. A baked station/corridor mask selects forest litter in their existing
UV coordinates. Conflicting repeated UV texels are left unchanged, preventing
painting another part of the road. The original duplicate grass channel is
merged into its identical channel outside the floor mask; no extra ground
triangles, positions, indices, names, flags or UVs are introduced.

The budget is 117 road-aligned three-crown Searsia clusters, 29 midstory pines
and 34 adult pines: 180 TreeFX instances, plus 2,156 low filler clumps.
Per-100 m counts are hard-limited: 60 / 60 / 60. Whole-route count is 6,850,
or 44.08/100 m. This is a summit-only exception; the shared planner still caps
ordinary sectors at 51/100 m. Boulimat 10000–10300 m plans 53 instances
(18/18/17), reserving 100 below its 153 allowance. Against the uniform-51
whole-route ceiling of 7,926, the summit adds 27 and this sea-view reservation
saves 100: an allocated ceiling of 7,853 (50.53/100 m), below 8,000. This is
a planning allocation, not a claim that the rest of the route was regenerated.

`summit_scenery.natural_summit` uses a separate station-derived pine seed,
irregular spacing, paired clumps, varied 16–27 m heights and broader crowns.
Selection favours the locally classified mountain side. Lower buried crowns
and higher back-clump crowns stagger the canopy; roots never float above the
sampled ground. Every new pine uses an adult/midstory volume archive, not the
background impostor-only models. Its all-road-leg clearance remains at least
4 m. No tall planar rear mesh remains in the qualification KN5.

`data/summit_hedge_lock.json` locks the accepted `c313e15` shrub and filler
placement hashes and cluster archive SHA-256. The original layout is generated
with its original random stream before discarding the old rear layers; changing
that stream would reshuffle the accepted hedge. Generation fails if the lock
changes. Independent readback also found all 32 low filler mesh records and all
remaining KN5 textures byte-identical to `c313e15`, including the forest floor.
`summit_shrub_cluster.bin` contains three complete cached `PH_shrub_01` crowns
(351 source crowns total, not 117 unchanged prototypes). No global mesh collapse
is applied. Cluster dimensions are 2.6–3 m high and 6.5–7 m long, anchored at
road-edge height with buried bases; `PH_shrub_02` is not used. LOD triangle counts
are 47,736 / 8,058 / 48, at 12 / 75 / 900 m. Individual mesh groups remain below
65,536 vertices. This is more geometry per instance, not a free performance gain.

The cached prototypes have no vertex-colour layers. The clustered archive
copies whole source triangles, normals, UVs, textures and shading settings;
shading brightness is 1, with the same sphere/boost normal settings.
Visible leaf texture samples are warmer/brighter than the pines. An exported
per-instance `color=0.55,0.70,0.50` tint makes the shrubs a darker natural green.
The preview now reads and applies this same TreeFX colour, not a render-only
grade. Filler textures receive the same linear-light 0.55/0.70/0.50 tint.
Alpha is unchanged. The floor diffuse
is graded brown-green with seeded coarse/fine variation. A nominal 0.8 m verge
is excluded from forest-floor selection; no ground overlay is introduced.

## Saved pixel measurements: target not met

Current evidence is in `out/scenery_measurements/summit_pines/`: four beauty images,
`*_ids.png`, `*_left_band.png`, `*_right_band.png`, `*_bands_overlay.png`,
`*_foliage.png`, `*_terrain.png`, `*_fixed_barriers.png`, `*_hillside_roi.png`,
`*_pale_hillside.png`, per-view JSON and `visual_measurements.json`.
The renderer writes the same outputs alongside its normal previews on rebuild.
Texture caches are isolated per label and addressed by content hashes so a
previous candidate/rebuild cannot supply stale same-named textures to the view.

Bands project road-edge heights 0.3–1.8 m over the first 80 m of treated road in
the camera frustum: 1035.5–1115.5 m forward and 1100–1180 m reverse. Left/right
mean route sides, not screen sides. Blue overlay is route-left; magenta is
route-right. Band denominators are identical before/after and include visible
fixed obstacles and terrain; they are not restricted to successful foliage.
Cutout-aware emission IDs use green for vegetation foliage/impostor silhouettes,
red for grass/rock terrain, blue for protected guard/wall visuals, black for
other objects/background. Known bark textures are excluded. Pixel shares use
linearized emission-channel coverage. ID rendering disables denoising, adaptive
sampling and dithering, uses one sample and a 0.01-wide box filter. The four
new ID images contain only 0/255 channels and combined coverage never exceeds
1.0. Beauty renders explicitly restore their normal filter/dither settings.
The old `summit_density` measurements are historical denoised outputs and are
superseded by this remeasurement, including its freshly rendered BEFORE pair.

| Camera | Route-left before → after | Route-right before → after |
| --- | --- | --- |
| 1030 m forward | 69.11% → 60.59% | 64.90% → 57.05% |
| 1230 m reverse | 88.11% → 85.78% | 62.20% → 60.59% |

None reaches the requested 90%. In the reverse route-right band, fixed
guard/wall coverage is 11.70%, putting even theoretical raw foliage coverage
below 90%; excluding those obstacles still only yields 68.61%, not acceptance.
The accepted hedge geometry is unchanged: these bands also count foliage behind
hedge gaps, so removing the opaque rear wall reduces their total foliage share.

Pale hillside uses the fixed image region above the projected bands, terrain
IDs, RGB mean >0.38 and HSV saturation <0.32. Visible pale-terrain share of
the complete frame is 0.05241% → 0.94835% forward and 0.87836% → 0.56651%
reverse. The former dark wall hid much more forward rock than the new volumes;
the exposed slope toward the bend is still a visual shortfall. Occlusion credit
is now capped by the actual loss of pale coverage as well as foliage growth:
`min(max(old_pale-new_pale, 0), max(new_foliage-old_foliage, 0))`.
Only 307/483 baseline pale pixels forward and 810/8095 reverse are credited;
those figures must not obscure the newly exposed forward terrain. These are
explicitly scoped image regions, not a claim that every visible cliff is hidden.

Terrain masks are four independent weights, not opacity images. Resizing,
DXT5 colour-block encoding and mip generation preserve RGB even when the fourth
weight is zero. All four forest-floor masks retain litter at every mip level.

## Pine LOD defect

The cached adult/midstory pine LOD1 was not preview-only: its global collapse
decimation turned foliage cards into dark triangular shards and distorted
trunks. An isolated same-renderer comparison of the native prototype, decoded
LOD0 and decoded LOD1 exposes this, independently of the preview material.
`out/preview/pine_native_lod0_lod1.png` is that comparison, left to right.
`out/preview/pine_lod1_repair.png` compares old and repaired LOD1.

This qualification copies the complete sound 20,000-triangle adult LOD0 into
the medium slot, including for midstory archives, and retains that volume until
150 m. The old whole-atlas-view medium repair remains the default helper path,
but this summit opt-in no longer thins its crowns. It repairs only its own
cached archives. The pilot compiler retains its
validated 9,003-triangle medium-LOD cap and does not use this higher-cost repair.
Pilot output archives are not overwritten. Summit adult/midstory LOD ranges
are 28/150/900 m; both intervals below 150 m use full volumetric geometry, then
the 16-triangle impostor. Readback verifies three-dimensional vertex rank and
the 20,000/16 transition for all six used pine archives. These larger near/mid
LODs cost more geometry; no FPS improvement is claimed. Preview selection uses
the actual archive DISTANCE ranges (new shrub clusters remain 12/75/900).

## Cached assets and limitations

This build needs no raw Blender asset rebake. It reads the pilot's compiled
KN5 textures and cached TreeFX archives/model metadata; only used archives are kept.
Pilot source credits/licenses accompany the candidate as
`PILOT_ASSET_CREDITS.md` and `PILOT_ASSET_LICENSES.json`.

The following raw inputs were absent under `/home/ubuntu/repos/assets`:

- `optimized_pines.blend`
- `searsia_lucida/searsia_lucida_1k.blend`
- `pine_forest/textures/forest_ground_04_diff.png`
- `guard-rail.glb` (not needed by this qualification)

The report deliberately retains `qualification_complete: false` and
`visual_review_required: true`; passing geometry/budget checks is not art
acceptance. Matched summit and reverse exit renders accompany this pass.
Critical inspection of both final views finds no tall planar silhouette wall.
The accepted front row is unchanged, with real pine volumes and natural canopy
gaps behind it. Exposed rock toward the forward bend remains conspicuous;
complete low-slope masking and the earlier 90% band target are **not achieved**.
After three composition attempts this remains partial. Do not roll this pass out
route-wide. The installable copy is a qualification candidate, not accepted art.

The previews are Cycles approximations, not in-game acceptance. Native AC
collision, CSP/Pure appearance, wet
weather, FPS and VRAM remain untested. Existing main KN5 grass-tangent and
roadside-LOD validator failures are not repaired by this sector pass.
