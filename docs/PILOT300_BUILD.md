# Rebuilding the separate 300 m pilot

This is a development candidate, not an Assetto Corsa runtime certification or a completed full-route remaster. Installation is a separate, approval-gated step. The town and beach are not part of this pass.

## Development layout

The Windows build used this layout, independently of the AC installation:

```text
WORK/
  project/                         # this repository
  assets/
    optimized_pines.blend
    pine_forest/textures/
    guard-rail.glb
    worn_asphalt_4k.blend/textures/
    searsia_lucida/
  tools/blender-3.6.23-windows-x64/
  bake_pine_cards.py
  optimize_pines.py
  fetch_cc0_shrubs.py
  asset_licenses.json
```

Use Git LFS when cloning: compiled tracks, textures, TreeFX archives and Blender scenes are binary assets, not the small pointer files shown by some source ZIP downloads. Raw asset downloads and Blender itself are not vendored. No TrackTools pack or reference-track content is redistributed.

The helper sources and license manifest are versioned under `development_support/`. They are the copies used in `WORK/`, not scripts to execute from inside that subfolder: their paths are deliberately relative to the development root. Preserve any local helper revisions before restoring them there. The shrub downloader verifies the upstream byte counts and MD5 checksums; its recorded source manifest is also included.

The supplied source ZIP is an overlay for this layout, **not a standalone project or installer**. Its DDS files, prototype scene and pilot scene retain their project-relative paths. The actual source species are Scots pine and a South African small-leaf shrub surrogate; neither is advertised as native Aleppo pine or Algerian local vegetation.

## Verified pipeline

From the repository root, with the existing portable environment and its NumPy/Pillow dependencies:

```bat
"..\tools\blender-3.6.23-windows-x64\3.6\python\bin\python.exe" scripts\build_pilot.py --stages build,audit,test,after,validate,package
```

This snapshots the full-route source hashes **before** building the pilot, checks geometry/material data and Blender texture paths, executes Python and Blender regressions, exports and reads back KN5/TreeFX binaries, and CRC-checks both packages. It does not launch AC or write into its installation. Blender 5.x is intentionally not used by this exporter pipeline.

The optional `review` stage renders three matched driver viewpoints. It requires the previously saved pilot scene identified by `data/pilot300/baseline.json`; that local historical backup is not distributed. Without it, do not call the old native Blender scene a complete previous in-game view: it does not automatically show external TreeFX instances. The packaging script labels that fallback as incomplete.

See [PILOT300.md](PILOT300.md) for measured build statistics, source credits and the in-game checklist. Static checks do not establish working collision, FPS/VRAM, Pure, RainFX or GrassFX behavior. Use the same car, weather, camera position and settings for the next AC comparison.
