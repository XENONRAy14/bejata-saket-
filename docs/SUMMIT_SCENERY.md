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

## Implementation and lock

`qualify_scenery.py` removes existing TreeFX placements in the sector and any
legacy foliage triangles there and adds shared-atlas edge batches and TreeFX
placements. The foreground now uses cached three-dimensional Searsia radial
clusters, not atlas planes. Darkened atlas filler starts 16/21 m beyond the road
edge, behind the shrubs, with smoothed upright normals and orthogonal tangents.
No pilot rail modules are imported. Forest-floor reassignment uses existing
physical `1GRASS*` geometry, without new ground overlays or UV changes.
The lateral corridor is 80 m plus half the maximum road width; selection uses
nearest active-route centreline stations. Trees are footprint-clearance checked
against every road leg by the shared planner.

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

The budget is reallocated to 86 dense `PH_shrub_01` clusters, 40 midstory pines
and 26 background silhouettes: 152 TreeFX instances, below 153, plus 282 rear
atlas clumps. Each cached Searsia model already contains three radial branches.
The sparser `PH_shrub_02` is not used. Physical shrub dimensions are 2.8–3.5 m
high and 6.4–6.8 m wide. Taller pines and buried crown bases form the mid/back
rows. Horizontal footprint clearance is checked against every road leg.

The cached prototypes have no vertex-colour layers. TreeFX packed vertex
colours, geometry, normals, textures and shading settings are preserved from
the pilot; shading brightness is 1, with the same sphere/boost normal settings.
Visible leaf texture samples are warmer/brighter than the pines. An exported
per-instance `color=0.55,0.70,0.50` tint makes the shrubs a darker natural green.
The preview now reads and applies this same TreeFX colour, not a render-only
grade. Atlas filler has its own subdued texture grade; alpha is unchanged.

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

Qualification derives pine LOD1 from sound LOD0 geometry, removing complete
atlas views rather than collapsing surviving triangles. It repairs only its
own cached archives, including midstory models. The pilot compiler retains its
validated 9,003-triangle medium-LOD cap and does not use this higher-cost repair.
Pilot output archives are not overwritten. Repaired medium LODs have
12,896–13,698 triangles; this costs more than the broken old medium LOD.
No FPS improvement is claimed. Preview LOD selection uses each archive's real
DISTANCE intervals (including shrubs 20/75/900 and midstory 28/110/900).

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
Critical inspection after three composition attempts still finds exposed pale
hillside at 1030 m and individual open shrub forms rather than a fully closed
hedge. The pale foreground atlas wall is gone and the 3D shrubs are darker, but
the closed forest-wall target is **not achieved**. Do not roll this pass out
route-wide. The installable copy is a qualification candidate, not accepted art.

The previews are Cycles approximations, not in-game acceptance. Native AC
collision, CSP/Pure appearance, wet
weather, FPS and VRAM remain untested. Existing main KN5 grass-tangent and
roadside-LOD validator failures are not repaired by this sector pass.
