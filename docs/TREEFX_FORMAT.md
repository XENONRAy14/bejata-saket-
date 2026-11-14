# Source-verified external TreeFX contract

Primary source: Content Manager, commit
`e5e5c94b8dee7511def0b670bfd5dbb233831c11`:
https://github.com/gro-ove/actools/blob/e5e5c94b8dee7511def0b670bfd5dbb233831c11/AcTools.ExtraKn5Utils/Helpers/AcTreeModelConverter.cs
(abbreviated **Converter** below). Local research checkout:
`/home/ubuntu/tools/actools-treefx-research`. No third-party tree assets copied.

The CSP wiki [Tracks–Trees](https://github.com/ac-custom-shaders-patch/acc-extension-config/wiki/Tracks-%E2%80%93-Trees)
(`Tracks-–-Trees.md:1,9–25,29–69`) verifies external BIN models, FBX→CM conversion,
`extension/trees`, `[TREES] LIST_0`, text positions, size, angle and colour overrides.
It is **not** limited to converting existing KN5 trees. The config checkout was
searched for `[TREES]`/list examples; no additional useful track examples were
found. Binary layout is taken from CM source, not guessed from config examples.

## Writer and independent structural reader

`scripts/treefx.py` writes and reads the following fields. Little-endian .NET
BinaryWriter scalars are used. No opaque CM-native converter is required.

| Field | Contract | Exact source |
|---|---|---|
| Container | ZIP: LOD mesh files, `tree.ini`, referenced textures | Converter:120–152 |
| `BASIC` | HEIGHT=max Y, WIDTH=2×max absolute horizontal coordinate | Converter:90–106,130–137 |
| Other defaults | SHADING, NORMALS, LEAVES, FAKE_SHADOW from converter defaults | Converter:131–137 |
| LOD references | `[LOD_n] MODEL`, `DISTANCE` | Converter:143–147 |
| Mesh header | int32 version=1, byte=0, int32 texture count | Converter:242–244 |
| Texture table | uint32 xxHash32, string basename | Converter:165–171,238–248 |
| String | int32 UTF-8 byte length, then bytes (not 7-bit .NET default) | `AcTools/ExtendedBinaryWriter.cs:65–68` |
| Material group | int32 diffuse index, int32 normal index | Converter:333–343 |
| Indices | int32 count, count×uint16 | Converter:45–56 |
| Vertices | int32 count | Converter:58–59 |
| Position | 3×float32, normalized X/Z by horizontal radius, Y by height | Converter:90–106,308–312,60 |
| Normal | 3×float32 | Converter:61,307 |
| UV | 2×float32; source FBX V converted to 1−V | Converter:62,312; `Helpers/FbxDataAccessor.cs:52–54` |
| Tangent | 3×uint8, each truncated clamp(t×127.5+127.5) | Converter:51,64–67 |
| Element | uint8=0 | Converter:68 |
| UV2 | 2×float16=0 | Converter:69–70; `AcTools/ExtendedBinaryWriter.cs:61–63` |
| AO0/AO1/wet/extra | four bytes: 255,255,255,0 | Converter:71–74 |
| Optional trailer | int32 −1, int32 4, float32 normalized trunk radius | Converter:315–317,347–352; TrunkWidth:100–102 |

Source paths for the last two helper references are relative to the same pinned
repository. The mesh vertex record is 44 bytes. Per-material arrays may keep
duplicate vertices: deduplication at Converter:33–42 is an optimization, not a
different wire type. Our generated AC coordinates are `(x,z,-y)`, matching the
existing KN5 exporter (`exporter/exporter_utils.py:36–37`). Tangents are derived
from normalized geometry and atlas UVs and orthogonalized against canopy normals.
Both sides of foliage are explicit faces, not an undocumented renderer flag.
Texture checksums use system `libxxhash.so.0` (Ubuntu `libxxhash0`), XXH32 seed 0;
the standard empty-string vector is checked in tests.

Every emitted archive is read back before KN5 trees are removed. Reader checks
ZIP CRCs, header, textures/checksums, indices, complete 44-byte vertex records,
finite/unit normals, packed defaults, optional trailer and LOD references/ranges.
Decoded vertex/triangle counts must match source prototype counts. Validator also
reconstructs each model's horizontal radius and checks list-instance canopy
clearance against actual KN5 road triangles. Truncation and checksum corruption
are negative tests. This verifies the source-derived format, **not CSP runtime
acceptance**; no human conversion step is needed for these validated outputs.

## Native runtime and fallback

Two LODs request transitions at 150/600 m. TreeFX, rather than merged KN5 chunks,
owns per-instance instancing, distance culling and billboards (wiki:1,9–25).
The native shader sources consume normalized geometry and instance transforms:
`acc-shaders/custom/trees2/flgTree_model_mainobj_vs.fx:13–32,42` and
`flgTree_model_mainobj_ps.fx:18–25,59`. The vertex shader contains height-driven
`applyWindModel` calls at :18,32,36; this establishes a real TreeFX wind mechanism,
not verified dispatch/runtime appearance for our generated trees. No guessed
wind keys or custom weights are added. KN5 fallback wind stays deferred.

GrassFX custom atlases/groups support low tufts and bushes:
`Tracks-–-Grass-FX.md:211–255`. Our procedural 4×2 atlas uses dry grass at column 3,
row 1, and maquis at column 1, row 1 (columns start at 1, rows at 0: :228).
GrassFX now owns their scattering/culling; exact original shrub/tuft positions
are **not** retained. Surface coverage is terrain-only, inheriting the accepted
road/kerb/gravel/sand/building occluders. TreeFX retains trees and reeds from the
terrain-snapped plan. No vegetation beyond 300 m is generated.

Fallback: `build.py vegetation --kn5-vegetation` (or `all --kn5-vegetation`)
disables TreeFX/extra GrassFX groups and exports all seven species as regular
visual KN5 meshes, grouped by 400 m chunk/material with 0–150/150–600 m LODs.
Re-run default `build.py vegetation` to restore TreeFX. Never enable both paths
simultaneously. The ignored persistent preview blend retains procedural mesh
stand-ins; Cycles cannot render TreeFX or GrassFX runtime shaders/scattering.
