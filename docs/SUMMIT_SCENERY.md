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

## Implementation and lock

`qualify_scenery.py` removes existing TreeFX placements in the sector and any
legacy foliage triangles there and adds shared-atlas edge batches and TreeFX
placements. The low atlas combines smaller cached shrub silhouettes and twig
clusters; upward card normals avoid hard lighting changes between planes.
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

The summit has 148 TreeFX placements (50/50/48 per successive 100 m), below
153, plus 1,446 low atlas clumps. Near pines, lowered midstory crowns and wider
16-triangle silhouettes overlap instead of repeating a sparse tall-tree row.
Midstory/background tree roots are deliberately buried to bring crowns down
to the hillside. These are visual-only plants; their horizontal footprint
clearance is still checked against every road leg.

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

The pine shards are repaired, but **visual qualification is still incomplete**:
the hillside is not fully masked and the foreground cards still read as flat,
pale cutouts. Three composition passes did not achieve the closed forest-wall
target. The report deliberately retains `qualification_complete: false` and
`visual_review_required: true`; passing the geometry/budget checks is not art
acceptance. A next composition pass should allocate part of the existing tree
budget to close three-dimensional shrub clusters rather than more atlas cards.

The previews are Cycles approximations, not in-game acceptance. Native AC
collision, CSP/Pure appearance, wet
weather, FPS and VRAM remain untested. Existing main KN5 grass-tangent and
roadside-LOD validator failures are not repaired by this sector pass.
