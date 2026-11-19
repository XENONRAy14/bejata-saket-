# Main-route summit qualification

This is a **partial qualification**, not a full-route rollout or AC acceptance.
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
It approximates KN5 multilayer materials and TreeFX LODs, not CSP runtime shaders.
The install copy retains the complete route; only summit 880–1180 m is treated.
The separate `summit` track folder includes `models.ini` referencing its KN5 and
a distinct qualification UI name. Install it as `content/tracks/summit`, not over
the main `bejaia_saket` folder.

## Implementation and lock

`qualify_scenery.py` removes existing TreeFX placements in the sector and any
legacy foliage triangles there, imports the cached pilot edge atlas/material,
and adds the shared planner's edge batches and TreeFX placements. No pilot rail
modules are imported. Forest-floor reassignment is allowed only on existing
visual `LAND_*` grass triangles with all vertices inside the sector corridor.
The lateral corridor is 80 m plus half the maximum road width; selection uses
nearest active-route centreline stations. Trees are footprint-clearance checked
against every road leg by the shared planner.

`scenery_kn5.py` preserves untouched KN5 records verbatim, including protected
mesh materials and parent transforms. The lock covers every digit-prefixed
physical mesh, `AC_*` empty and `DETAIL_GUARD_*` visual. The required reference
SHA-256 is `7cceb8c8aeb9ec72b9031d1356b5450b7e1e38c335748964591d84036d13c61f`.
Other props are checked unchanged during generation. Source main ZIPs, the pilot
KN5 and the v1 rollback are not modified.

## Unresolved forest floor

The current baseline has **zero visual-only grass triangles** inside this
summit corridor, but 3,625 physical `1GRASS*` triangles. There are distant
`LAND_*` grass triangles associated with these stations; the nearest centroid
is 154.13 m from the road. Recolouring those would not mask roadside seams.

The build therefore reports `SCENERY_QUALIFICATION_PARTIAL`,
`forest_floor_applied: false`, and `qualification_complete: false`. It does not
silently change physical materials/geometry or add a new coplanar ground layer.
Completing the requested floor treatment needs authorization for a new
visual-only overlay following the existing ground, or a different ground scope.

## Cached assets and limitations

This build needs no raw Blender asset rebake. It reads the pilot's compiled
KN5 atlas and cached TreeFX archives/model metadata; only used archives are kept.
Pilot source credits/licenses accompany the candidate as
`PILOT_ASSET_CREDITS.md` and `PILOT_ASSET_LICENSES.json`.

The following raw inputs were absent under `/home/ubuntu/repos/assets`:

- `optimized_pines.blend`
- `searsia_lucida/searsia_lucida_1k.blend`
- `pine_forest/textures/forest_ground_04_diff.png`
- `guard-rail.glb` (not needed by this qualification)

The preview shows continuous low shrub edges but a looser upper canopy than
the old foliage. Cards remain visibly faceted. Visual quality is not accepted
as a finished forest corridor. Native AC collision, CSP/Pure appearance, wet
weather, FPS and VRAM remain untested. Existing main KN5 grass-tangent and
roadside-LOD validator failures are not repaired by this sector pass.
