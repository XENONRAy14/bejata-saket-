# Visual upgrade research and v2 material implementation

## Scope, baseline and source notation

Sections 1–8 preserve the original audit/proposal. Section 9 records the applied
v2 material pass; section 10 records the subsequent CSP extension configuration.
No assets from other tracks are to be imported; examples below establish syntax only.

The local backup and annotated `v1` tag preserve commit
`8c91a90831e36aa8f6cccde21b20017aa6cda4b4`; hashes, paths and copy/ZIP checks
are recorded in [`data/v1_backup_info.json`](../data/v1_backup_info.json):2–15.
The large backup folder and ZIP are local, ignored artifacts, not Git objects.
The earlier all-stage clean-rebuild evidence remains at
`v1:data/clean_rebuild_info.json`:2–17.
Basic AC loading/driving is user-reported; **UNVERIFIED locally**. There are no
AC/CSP/Pure screenshots or runtime tests in this research pass.

Source prefixes used in file:line citations:

* **P**: this project at `v1` (except this document and the new backup manifest).
* **C**: cloned [CSP config repository](https://github.com/ac-custom-shaders-patch/acc-extension-config),
  commit `4a0d860a5688fe162fcf142cf93fa8436030d0e2`, local
  `/home/ubuntu/tools/acc-extension-config-text`.
* **W**: cloned [official CSP wiki](https://github.com/ac-custom-shaders-patch/acc-extension-config/wiki),
  commit `cd2d2d9894ad2905d221bf91211441859e47f5cd`, local
  `/home/ubuntu/tools/acc-extension-config-wiki`. Filenames below are wiki page names
  with `.md`; the separator is an en dash.
* **S**: [CSP shader source](https://gitlab.com/ac-custom-shaders-patch/public/acc-shaders),
  commit `165f58194014521237b34b6e690f070f2b288ae8`, local
  `/home/ubuntu/tools/acc-shaders`. These are **CSP recreations**, not a claim that
  unmodified Kunos binaries behave identically in every case. This is the source
  linked by C:README.md:18–21.
* **E**: installed [Moppius exporter](https://github.com/Moppius/blender-assetto-corsa-tools),
  commit `5f0c163cd75f071b21b7f8f98651d50870cf8e85`, local
  `/home/ubuntu/tools/blender-assetto-corsa-tools`.

These are inspected snapshots, not guarantees for the user's unspecified CSP
Patreon preview version. Version-specific rendering/performance remains
**UNVERIFIED** until tested in AC.

## 1. Backup and network checks

| Target | Observed result and source |
|---|---|
| Poly Haven API | Web fetch of <https://api.polyhaven.com/info/worn_asphalt> and <https://api.polyhaven.com/files/worn_asphalt> returned metadata and download URLs. A default Python urllib request from this VM received HTTP 403; do not equate web-fetch reachability with every client working. |
| Poly Haven downloads | `curl -L --fail --user-agent 'bejaia_saket-research/1.0'` downloaded the [1K diffuse JPG](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/worn_asphalt/worn_asphalt_diff_1k.jpg): 914719 bytes, MD5 `8777234b139e454eaabcda0eb8115e45`, matching the files API. SHA-256 `3bf71ad290730092ad2aee85e246b2e43318bc1f32261826ba91250e815b5f72`. |
| ambientCG API | <https://ambientcg.com/api/v2/full_json?id=Asphalt012&include=downloadData,licenseData&limit=1> returned exactly `Asphalt012` and its files. **Use `id=`, not `include=Asphalt012`**: the latter returned an unrelated popular asset in the first probe. |
| ambientCG downloads | Same curl client downloaded <https://ambientcg.com/get?file=Asphalt012_1K-JPG.zip>: 8507722 bytes, SHA-256 `c077e5d1b21a4333829bb655043ee6a45ddcf82fef850528f91f4305ac11193d`; Python ZipFile CRC test passed for all 11 members. |
| CSP GitHub | Git clone worked, but initial checkout hit a Git LFS authorization error on `ks_highlands__buildings.kn5`: `batch response: Resource not accessible by personal access token`. This is binary LFS access, not a missing Python environment. A fresh `GIT_LFS_SKIP_SMUDGE=1 git clone` completed: all config text is available; no track model is needed or imported. Source: C:README.md:10,31–35 and the observed clone output. |
| CSP wiki / shader source | Both Git clones completed at the W/S revisions above; files cited below were read locally. |
| Pure | [Peter Boese's Patreon landing page](https://www.patreon.com/peterboese) and [his Pure Gumroad page](https://peterboese.gumroad.com/l/pure) were readable. Specific [release-post request](https://www.patreon.com/peterboese/posts/pure-3-59-3-50-9-164418722) returned HTTP 403; no authenticated manual was obtained. See §6. |

Downloads and DDS probes are isolated under `data/research_cache/`, not the
track's `textures/` or install folder. The above hashes refer to actual downloads,
not thumbnails; license evidence is in §7. Reproduce v1 using the tagged code and
the raw-cache procedure already recorded in P:data/clean_rebuild_info.json:2–17.

## 2. Ranked visual audit

Opened the existing renders directly: [town](../out/preview/decor_town.png),
[Saket](../out/preview/decor_saket.png), [road 40%](../out/preview/road_40.png),
[top](../out/preview/top.png). The ranking below is an **audit inference from
these Blender images and code**, not a measured cause ranking for Pure in AC.

| Rank | Cause and visible evidence | Reachable pipeline evidence / proposed priority |
|---|---|---|
| 1 | Surface appearance: large uniform green/tan/grey regions; essentially no granular relief, convincing dirt/rock variation or near/far detail. | P:scripts/blender_mesh.py:13–24 connects only image color to Principled base color. P:blend/settings.json:2–30 starts the exported diffuse-only `ksPerPixel` setup. Prioritize coherent albedo, physical texture scale, normals and appropriate detail layers together, not just increasing resolution. |
| 2 | Vegetation: extremely recognizable stacked polygon blobs, trunks, and sparse repeated silhouettes, especially near Saket. | P:scripts/blender_decor.py:52–69 constructs canopies as solid blobs. Alpha cards/LOD silhouettes are the proposed replacement, with procedural Mediterranean variants rather than blindly placing a photogrammetry tree. |
| 3 | Empty horizon/world: narrow ribbons leave absent terrain and floating/slab edges. Top image shows the scene is not a continuous landscape. | P:scripts/blender_mesh.py:48–58 creates strips; the top render is direct extent evidence. Proposed distant low-resolution land/shore context would matter more than a shader tweak at these edges. Geographic fidelity and budget for that new context are **UNVERIFIED**. |
| 4 | Hard edges: abrupt grass/shoulder joins, broad cut faces and angular trees look modeled rather than natural. | Strip topology and one UV set are explicit at P:scripts/blender_mesh.py:28–58; guard/cut objects at :137–138. Proposed mask blending and selected mesh/normal treatment; do not smooth physical boundaries indiscriminately. |
| 5 | UV scale/tiling: road marks and surface features repeat uniformly; all strips share normalized across-strip UV and longitudinal `s/7`, so a wide terrain ribbon and narrow shoulder do not have equal texel scale. | P:scripts/blender_mesh.py:48–58, especially :57. Proposed separate macro masks and meter-scaled detail UV/world tiling; 2K alone cannot fix stretched mapping. |
| 6 | Sea/sky: featureless blue sea, abrupt beach band and plain backdrop; no wave cues in the Saket render. | Saket/top images; P:scripts/blender_mesh.py:143–153 creates a constant-color world and sun. Proposed CSP water and coastline detail, but Pure already owns the in-game atmosphere: do not export this Blender sky as a replacement. Water source in §5. |
| 7 | Road detail: immaculate repeated white markings, no repairs, wear, grime accumulation or edge breakup. | Road 40%/town images and the repeated UV construction above. Proposed separately controlled marking masks/decals and restrained patches; do not add a fictional racing rubber line to the entire public road. |
| 8 | Flat lighting/ambient and shader choice: the previews have weak contextual contrast; all these material changes need in-game evaluation. | The render path is Eevee with constant background, sun and fixed roughness (P:scripts/blender_mesh.py:13–24,143–161), **not AC's shaders or Pure**. Export `ksAmbient=.4` is not evidence Pure is misconfigured. See §3/§6 before changing global ambient. |

**Disproof check on the leading hypothesis:** missing normal maps cannot explain
the absent horizon or polygonal tree outlines. The current road still has visible
diffuse noise and crisp marks, so it is not a wholly missing-texture failure.
Moreover, `settings.json` does not control the Eevee material shader used for
these renders (separate material construction cited above). Thus “wrong AC shader
caused these previews” is not established. No current AC screenshot was available
to determine how much Pure already improves lighting, sky or contrast.

## 3. Track shaders, slots and properties

All shader recommendations in this section are **proposals**, not tested winners.
The exact engine feature set on the installed preview remains **UNVERIFIED**.
Shared names are declared at S:recreated/include_new/base/textures_ps.fx:6–23;
that declaration does not mean every shader consumes every declared slot.

| Shader | Verified reads / important properties | Proposed use / limits |
|---|---|---|
| `ksPerPixel` | `txDiffuse`, lit color with diffuse alpha returned; S:recreated/ksPerPixel_ps.fx:23–25,57–84. Common coefficients `ksAmbient`, `ksDiffuse`, `ksSpecular`, `ksSpecularEXP` are also the existing E material defaults/settings (E:exporter/material_writer.py:125–150; P:blend/settings.json:8–20). | Distant opaque props and fallback, not a normal/detail solution. |
| `ksPerPixelNM` | `txDiffuse` plus `txNormal` through `getNormalW`; S:recreated/ksPerPixelNM_ps.fx:16–35 and S:recreated/include_new/base/utils_ps.fx:189–202. Normal alpha is used in the returned alpha path, not simply diffuse alpha. | Simple kerbs, gravel, plaster, rock where one texture scale suffices; validate tangent and normal convention in AC. |
| `ksPerPixelMultiMap` | `txDiffuse`, `txNormal`, `txMaps`, `txDetail`; `getNormalW`/`considerDetails` and map application at S:recreated/ksPerPixelMultiMap_ps.fx:19–38; slots at textures_ps.fx:6–20. Fresnel/detail scalars include `fresnelC`, `fresnelEXP`, `fresnelMaxLevel`, `useDetail`, `detailUVMultiplier` (S:recreated/include_new/base/cbuffers_ps.fx:147–158). | Useful general reflective/detail material, not necessarily the best road-blending shader. |
| `ksPerPixelMultiMap_detail`, `ksPerPixelMultiMap_detail_NM` | **UNVERIFIED names**: exact strings were not found in the inspected shader/config sources. Do not emit guessed suffixes. The verified name is `ksPerPixelMultiMap_NMDetail` (S:recreated/ksPerPixelMultiMap_NMDetail_ps.fx:1–29). | For NMDetail, reads base maps plus `txNormalDetail`; verified slot name at textures_ps.fx:20 and normal-detail call at NMDetail_ps.fx:29. |
| `ksMultilayer` | `txDiffuse`, `txMask`, `txDetailR/G/B/A`; mask RGBA weights the four detail colors, multiplied into diffuse; detail sampling uses **world XZ** times `multR/G/B/A`. `magicMult` and diffuse/detail alpha affect brightness/specular. S:recreated/ksMultilayer_ps.fx:13–54. | Terrain blend candidate, not a promise to follow road UV orientation for details. |
| `ksMultilayer_fresnel_nm4` | Four detail layers plus `txNormalR/G/B/A`, `txMask`, `txDiffuse`; Fresnel, `multR/G/B/A`, `magicMult`, `tarmacSpecularMultiplier`, `detailNMMult`, `tilingFixR/G/B/A`. S:recreated/ksMultilayer_fresnel_nm4_ps.fx:10–47,103–151; S:docs/ksMultilayer_fresnel_nm4.md:1–5. | Strong terrain/road blend candidate: macro diffuse/mask in mesh UV, detailed colors and normals at world scale. Road-direction and steep-cliff mapping need a prototype, not an assumption. Four layers/normals and optional tiling fix cost samples (same doc :5). |
| `ksPerPixelAT` | Diffuse-alpha cutout path/A2C defines and returned alpha: S:recreated/ksPerPixelAT_ps.fx:1–14,30–31. Export alpha flags remain separate (§4). | Opaque leaf-card cutouts/fences, rather than large overlapping blended transparent cards. |
| `ksTree` | `txDiffuse`, foliage lighting and alpha-to-coverage; S:recreated/ksTree_ps.fx:9–27,45,90–91. | Billboard/card foliage candidate; not an automatic upgrade for solid blob canopies. |
| `ksGrass` | `txDiffuse`, `txVariation`; `scale`, `gain`, `boh` and A2C; S:recreated/ksGrass_ps.fx:17–30,45–47. | Existing modeled grass cards; **not** a terrain material that automatically generates GrassFX. W:Tracks-–-Grass-FX.md:1–18 distinguishes these. |
| `ksPerPixelAlpha` | Diffuse alpha multiplied by float property `alpha`, S:recreated/ksPerPixelAlpha_ps.fx:6–15,32. | Special blended overlays where necessary, not the default foliage shader; blending/depth flags still matter. |
| Sea | Verified CSP `smWaterSurface` through `Material_Water`, **not a verified `ksSeaWater`**; see §5. | Keep a vanilla fallback mesh/material, then optional CSP replacement. |

### Map/channel cautions

* `txMaps` is **not a glTF metallic/roughness/occlusion pack**. Historical shader
  documentation gives R = specular strength, G = specular exponent, B = Fresnel
  maximum (and related sun specular): [shader author's explanation](https://ascobash.wordpress.com/2015/10/06/some-suggestions-about-models-and-other-things-part-2/).
  CSP's shader calls `applyTxMaps(txMapsValue.xyz)` (S:recreated/ksPerPixelMultiMap_ps.fx:31):
  R multiplies specular and G scales its exponent, with a `+1` offset, in
  S:recreated/include_new/base/utils_ps.fx:892–900. B enters reflection strength
  in that same file :711–737, so the old article is guidance, not an exact current
  LCS equation.
  Exact current LCS response/numeric conversion from CC0 roughness remains
  **UNVERIFIED**; author and inspect packed maps rather than rename a PBR ARM file.
* In multilayer, mask **R/G/B/A** corresponds to detail **R/G/B/A**, not road type
  enums (S:recreated/ksMultilayer_ps.fx:42–48). Design normalized masks to avoid
  unintended brightness changes; this is a proposal derived from the weighted sum.
* Alpha is shader-specific, not universally transparency. MultiMap diffuse/detail
  alpha behavior is discussed in [the author's alpha notes](https://ascobash.wordpress.com/2015/12/17/about-alpha-channel/),
  which use some historical slot spellings; use actual `txNormal`/`txDetail` names
  from S:recreated/include_new/base/textures_ps.fx:8,19, not guessed plurals.
* Proposed assignments: road = prototype multilayer Fresnel NM; kerbs/rock = NM
  initially; landscape = multilayer NM4; leaf cards = AT/tree; sea = CSP water.
  These are design choices based on the reads above, **not verified AC appearance**.

## 4. Moppius exporter and DDS

### Code-verified schema

`settings.json` is read **beside the exported KN5** (E:exporter/exporter_utils.py:74–80).
Our build keeps its working settings in `blend/`, not the install folder
(P:scripts/blender_acdata.py:95–105; see also P:README.md:99).
The following is an illustrative, deliberately incomplete asset binding, **not
an install-ready material**. Numbers are assumptions for demonstrating the schema,
not recommended calibrated values. Source: E:exporter/material_writer.py:163–219,240–309.

```json
{
  "materials": {
    "asphalt": {
      "shaderName": "ksPerPixelMultiMap",
      "alphaBlendMode": "Opaque",
      "alphaTested": false,
      "depthMode": "DepthNormal",
      "properties": {
        "ksAmbient": {"valueA": 0.4},
        "ksDiffuse": {"valueA": 0.4},
        "ksSpecular": {"valueA": 0.1},
        "ksSpecularEXP": {"valueA": 10},
        "fresnelC": {"valueA": 0.02},
        "fresnelEXP": {"valueA": 5},
        "fresnelMaxLevel": {"valueA": 0.2},
        "useDetail": {"valueA": 1},
        "detailUVMultiplier": {"valueA": 7}
      },
      "textures": {
        "txDiffuse": {"textureName": "road_macro.dds"},
        "txNormal": {"textureName": "road_normal.dds"},
        "txMaps": {"textureName": "road_maps.dds"},
        "txDetail": {"textureName": "road_detail.dds"}
      }
    }
  },
  "nodes": {
    "DECOR_*": {
      "visible": true, "renderable": true, "castShadows": true,
      "transparent": false, "lodIn": 0, "lodOut": 1000
    }
  }
}
```

* `shaderName` is written as a string without a shader-name whitelist. Arbitrary
  named properties/texture slots are serialized; **serialization does not prove
  the shader exists or consumes those names**. E:exporter/material_writer.py:62–84,173–219,240–242.
* Float scalars use `valueA`; vectors use `valueB` (2), `valueC` (3), `valueD` (4).
  Thus `multR/G/B/A` have the same scalar JSON structure when used with the
  verified multilayer shader, not a new exporter feature.
  E:exporter/material_writer.py:110–116,260–309; S:recreated/ksMultilayer_fresnel_nm4_ps.fx:10–19.
* **Important trap:** nonempty property and texture dictionaries **clear** the
  existing sets before filling them. Supply the complete required set, not just
  overrides. All mapped images must actually be represented by image texture
  nodes so the texture writer can embed them; settings do not load filenames.
  E:exporter/material_writer.py:187–219; E:exporter/texture_writer.py:46–61;
  E:exporter/exporter_utils.py:46–60.
* Blend enums: `Opaque=0`, `AlphaBlend=1`, `AlphaToCoverage=2`; depth enums:
  `DepthNormal=0`, `DepthNoWrite=1`, `DepthOff=2`. `alphaTested` is a separate bool.
  E:exporter/material_writer.py:27–37,62–67,245–257.
* **Falsy override bug:** `if alpha_blend_mode`, `if alpha_tested`, and
  `if depth_mode` mean JSON cannot force a pre-existing nonzero/true material
  back to `Opaque`, `false`, or `DepthNormal`. A clean default can still export
  these values. Scalar writes also use truthiness; a newly created property has
  default zero, but do not rely on zero overriding an existing value generally.
  This is code-verified, not a change made here: E:exporter/material_writer.py:110–116,177–207.
* Node flags are `visible`, `renderable`, `castShadows`, `transparent`, `lodIn`,
  `lodOut`, `layer`; **not** `isVisible`/`isRenderable`. Node setter uses `is not None`,
  so `false`/zero work there. E:exporter/node_writer.py:38–46,341–370.
* PNG/DDS bytes are packed and returned without recompression when recognized;
  the exporter has no BC1/BC3/BC5 codec whitelist. **BC5 in Blender/KN5/AC remains
  UNVERIFIED end-to-end**: source pass-through alone does not prove decoder or
  shader compatibility. E:exporter/texture_writer.py:63–75. No full track was
  re-exported or modified for this handoff.

### Linux DDS tests actually performed

Observed installed tools: Pillow **12.3.0**, `/usr/bin/convert` with `DDS rw+`,
`DXT1 rw+`, `DXT5 rw+`; `texconv`, `compressonatorcli`, `CompressonatorCLI`,
`nvcompress` were absent from PATH. This is availability here, not a claim they
cannot run on Linux. API references: [Pillow DDS support](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#dds),
[ImageMagick DDS options](https://imagemagick.org/script/formats.php#dds).

Downloaded Worn Asphalt was resized to **64×64 solely for a codec probe**:
`Image.open(...).resize((64,64)).convert(mode).save(path, pixel_format=fmt)`.
Then each DDS was reopened and fully decoded with Pillow. Actual results:

| `fmt` / mode | FourCC | Bytes | Header mip count | Result |
|---|---|---:|---:|---|
| `DXT1` / RGB (BC1) | DXT1 | 2176 | 0 | write/read OK |
| `DXT5` / RGBA (BC3) | DXT5 | 4224 | 0 | write/read OK |
| `BC5` / RGB | DX10 | 4244 | 0 | write/read OK; not an AC compatibility test |

The Pillow writer's mip count is hard-coded zero in this installed version
(`.venv/lib/python3.10/site-packages/PIL/DdsImagePlugin.py`:532–609, `_save`); do not
ship these nonmipmapped probe files as production hero textures.
The ImageMagick command below also succeeded and decoded as 64×64:

```sh
convert data/research_cache/worn_asphalt_diff_1k.jpg -resize 64x64 \
  -define dds:compression=dxt1 data/research_cache/im_dxt1.dds
```

It produced **2872 bytes**, DXT1 FourCC, **7 mip levels**. Proposed production
policy: 2K hero/1K secondary, mipmaps, BC1 for opaque color, BC3 where full alpha
is required; validate normals and channels separately. Those budgets are project
choices, not engine requirements. BC5 normal reconstruction, compression quality,
sRGB interpretation and mip/alpha coverage in AC remain **UNVERIFIED**.

## 5. Verified CSP track configuration syntax

Local track path is **`content/tracks/bejaia_saket/extension/ext_config.ini`**:
W:Tracks-–-RainFX.md:25 explicitly documents creating `extension/ext_config.ini`
inside a track. Nothing was added there in this handoff.

| Section | Verified keys / behavior | Evidence (not copied implementation blocks) |
|---|---|---|
| `[GRASS_FX]` | `GRASS_MATERIALS`, `GRASS_MESHES`, `OCCLUDING_MATERIALS`, `OCCLUDING_MESHES`, alpha-occlusion variants, `ORIGINAL_GRASS_MATERIALS`; mask keys `MASK_MAIN_THRESHOLD`, `MASK_RED_THRESHOLD`, `MASK_MIN_LUMINANCE`, `MASK_MAX_LUMINANCE`; `SHAPE_SIZE`, `SHAPE_TIDY`, `SHAPE_CUT`, `SHAPE_WIDTH`, `TRIM_PERIOD`. | W:Tracks-–-Grass-FX.md:5–54; real C:config/tracks/ks_nordschleife.ini:166–187 and C:config/tracks/putnam_park.ini:87–90. These mask keys control spawn color selection, **not a verified arbitrary `COLOR` key**. |
| `[GRASS_FX_CONFIGURATION_A]`…`_D`, `[GRASS_FX_ADJUSTMENT_...]` | Local shape/mask profiles; adjustment `MATERIALS`, `MESHES`, `MAP`. | W:Tracks-–-Grass-FX.md:79–129. Proposal: reserve verge grass for suitable terrain, occlude road/shoulder/buildings; avoid blanket grass over the dry coast. |
| `[RAIN_FX]` | `PUDDLES_MATERIALS`, `SOAKING_MATERIALS`, `SMOOTH_MATERIALS`, `ROUGH_MATERIALS`, `LINES_MATERIALS`, `LINES_FILTER_MATERIALS`, mesh counterparts; `STREAM_EDGE_...`, `STREAM_POINT_...`. | W:Tracks-–-RainFX.md:3–18,34–49; real C:config/tracks/putnam_park.ini:77–85. The wiki labels relief control broken; do not rely on it. |
| `[LIGHTING]` | `ENABLE_TREES_LIGHTING`, `TRACK_AMBIENT_GROUND_MULT`, `BOUNCED_LIGHT_MULT`, `LIT_MULT`, `SPECULAR_MULT`, `CAR_LIGHTS_LIT_MULT`. | W:Tracks-–-General-options.md:10–17; real C:config/tracks/ks_brands_hatch.ini:28–30. Values must be evaluated in AC/Pure, not copied. |
| `[LIGHT_...]`, `[LIGHT_SERIES_...]` | Single `POSITION` or `MESH`/`OFFSET`, `DIRECTION`; series mesh/position targeting; `COLOR`, `RANGE`, `SPOT`, fade controls in real examples. | W:Tracks-–-Lights.md:1–55; C:config/tracks/ks_brands_hatch.ini:183–200. Put lights only on intended fixtures, not every utility pole; limit ranges/count for performance (project proposal). |
| `[MATERIAL_ADJUSTMENT_...]` | `MATERIALS`, `CONDITION`, `KEY_n`, `VALUE_n`, `OFF_VALUE_n`, `ACTIVE`. Dynamic per-frame adjustment. | Real C:config/tracks/ks_brands_hatch.ini:658–670; W:General-–-Shader-replacements.md:1–5. |
| `[SHADER_REPLACEMENT_...]` | `MATERIALS` or `MESHES`, `SHADER`, `PROP_n`, or paired `KEY_n`/`VALUE_n`; `RESOURCE_n` with `RESOURCE_TEXTURE_n` (KN5), `RESOURCE_FILE_n` (disk), `RESOURCE_REF_n` (slot), `RESOURCE_COLOR_n`; blend/depth/culling/shadow flags. | W:General-–-Shader-replacements.md:9–79. Static replacements are preferred for static changes; targeting meshes can duplicate materials and draw calls (:14–16). Do not confuse its uppercase CSP blend/depth enums with the exporter's enums. |
| `[BASIC]` | `SUPPORTS_WIND`, `RALLY_TRACK`, `PITBOXES`, `IGNORE_OTHER_CONFIGS`. | W:Tracks-–-General-options.md:4–8. These are real names, not a recommendation to suppress other configs by default. |
| `[WIND]` | **Real section**: `IGNORE`, `DYNAMIC_FLAGS`, `TREES_NORMALIZATION`, `GRASS_NORMALIZATION`; documented randomized-offset keys have uncertain semantics. | W:Tracks-–-General-options.md:39–47; real C:config/tracks/ks_brands_hatch.ini:32–33 uses `DYNAMIC_FLAGS=AUTO`. Appropriate deformation/weights for our merged solid trees are **UNVERIFIED**. |
| `[WEATHER_FX]` | `SKY_BELOW_HORIZON` is documented; not a substitute for missing hills. | W:Tracks-–-General-options.md:23–24. No generic track `[SKY]` was verified here. |

Road rain proposal: asphalt in puddles + soaking; dry vegetation/soil in rough;
smooth clean metals/glass in smooth; paint in lines. The road currently bakes
paint into asphalt, so listing the entire asphalt as `LINES_MATERIALS` would mark
everything as paint: consider verified `LINES_FILTER_MATERIALS` or separate paint
geometry instead. These are design inferences from W:Tracks-–-RainFX.md:3–18,
not a runtime physics promise for every CSP preview.

Seasonal tint is not a guessed `[SEASON]` section: real configs use conditions and
adjustments of `seasonAutumn`, `ksDiffuse`, `ksAmbient`
(C:config/tracks/ks_brands_hatch.ini:658–669). Our Mediterranean seasonal palette
needs local references; copying a British autumn palette would be inappropriate
(proposal). CSP tree-specific replacement `ksTree_ppshadows` is documented at
W:General-–-Shader-replacements.md:20–25. TreeFX is a separate instancing/LOD system:
W:Tracks-–-Trees.md:1–25 documents FBX models, LODs, alpha/normal requirements and
CM tree conversion; it is not a magic shader for current blob geometry.

### Water answer — verified, not guessed

The verified route is the `common/materials_track.ini` include and
**`[Material_Water]`**, with target `Materials` and **`Type = SEA`** or `OCEAN`.
This is documented by W:Tracks-–-Water-shader.md:5–15 and
C:config/tracks/common/materials_track.ini:53–69. The template sets
**`SHADER = smWaterSurface`**, **`TAGS = NEW_WATER`** at :349–352.
Additional verified template keys include `UseNormalMapTwice`,
`UseAlphaFromDiffuse`, `UseAlphaFromNormal`, `UseRecommendedTextures`,
`FirstNormalMap`, `SecondNormalMap`, `DepthAware`, `CausticsMultiplier`,
`RainOffset` (:57–69). Caustics depend on ExtraFX bounced lighting
(W:Tracks-–-Water-shader.md:25).

A real config uses the template at C:config/tracks/californiacoast.ini:29–35,
but spells its selector `Mode`; **prefer the documented `Type`**, not that
unverified alias. Do not infer that every old example is correct.
No exact `ksSeaWater` shader or standalone `[WATER]` section was found in the
inspected track configs. Their existence elsewhere is **UNVERIFIED**, not disproven.
The shader source itself also documents water at S:docs/smWaterSurface.md.

Proposal: use our own CC0/procedural normal textures rather than redistributing
CSP's recommended texture files; disable recommended-texture substitution when
binding those. Keep sea visual-only, validate shoreline/reflection settings in
AC and check large-plane overdraw. No sea geometry/shader change has been made.
Template parameter evidence is the cited material library; suitability/performance
for this route remains **UNVERIFIED**.

## 6. Pure documentation status and boundaries

Official publicly readable material found: [Peter Boese's Patreon](https://www.patreon.com/peterboese)
describes Pure as his WeatherFX successor to Sol; [his Gumroad product](https://peterboese.gumroad.com/l/pure)
describes weather/graphics, skydomes, lighting, ground fog, landscape and
sunblinding shaders. **An official, freely readable track-author configuration
manual was not obtained.** The attempted release-post URL in §1 returned 403;
that is not evidence all documentation is Discord-only or that no manual exists.

A [third-party ARC guide](https://arcmite.github.io/arc-website/guides/visuals/pure-config.html)
lists a Track tab and exported track-specific controls, but labels itself
“Under Review”. It is **not official verification** of section/key syntax.
No official Pure GitHub/OverTake track-author manual or accessible Discord manual
was verified in this investigation. Patreon/download-bundled documentation and
any exact per-track export syntax remain **UNVERIFIED**; do not use reposted
paywalled documentation as a substitute.

Proposal: initially keep Pure's atmosphere/exposure under user control, author
reasonable material albedo/normals and CSP surface/water/light definitions, then
compare a fixed camera/time/weather in AC. Do **not** invent `[SKY]`, `[PURE]`, fog
or ambient keys, and do not claim Pure requires no track configuration. The known
CSP lighting keys are in §5, but Pure-specific requirements and LCS/Gamma numeric
calibration remain **UNVERIFIED**.

## 7. CC0 asset plan and actual license checks

Every Poly Haven row below had its **individual asset page opened and its CC0
label checked**; the [site asset license](https://polyhaven.com/license) additionally
states all its assets are CC0. ambientCG's [license](https://docs.ambientcg.com/license)
states CC0 1.0 Universal; its [Asphalt012 page](https://ambientcg.com/view?id=Asphalt012)
also explicitly states CC0. Website/code licenses are not asset licenses.
Only the two isolated download tests in §1 occurred; **none of these assets is
installed in the track yet**. Credits distinguish research from shipped assets.

| Category | Specific checked CC0 asset / approach | Selection caution / proposed budget |
|---|---|---|
| Worn/cracked asphalt | [PH `worn_asphalt`](https://polyhaven.com/a/worn_asphalt); [ambientCG `Asphalt012`](https://ambientcg.com/view?id=Asphalt012). Both downloaded successfully (§1). | PH has leaf litter; do not blanket the whole clean lane. ambientCG is procedurally cracked. Derive a 2K hero material/detail set, not a stretched 24 km photo. |
| Road markings | Procedural paint alpha/masks, no external asset selected. | Keep wear separate from asphalt normals; rain line filtering discussed in §5. This is a design choice. |
| Gravel | [PH `gravel_floor`](https://polyhaven.com/a/gravel_floor) | 1K secondary; verify actual shoulder pebble scale. |
| Dirt | [PH `dry_ground_01`](https://polyhaven.com/a/dry_ground_01) | 1K secondary; color-match local dry soil rather than copy the preview lighting. |
| Grass/terrain | [PH `aerial_grass_rock`](https://polyhaven.com/a/aerial_grass_rock) | Mixed landscape candidate, not a leaf atlas; combine restrained procedural dry vegetation. 1K/2K depending on visible area. |
| Rock/cliff | [PH `rock_boulder_dry`](https://polyhaven.com/a/rock_boulder_dry) | 2K hero on near cuts; **UNVERIFIED geological match** to Gouraya limestone and steep-face mapping. |
| Sand | [PH `coast_sand_05`](https://polyhaven.com/a/coast_sand_05) | 1K secondary, macro beach variation; assess real-world scale. |
| Concrete/plaster facade | [PH `rough_plaster_03`](https://polyhaven.com/a/rough_plaster_03) | Weathered plaster candidate, not automatically clean white Bejaia plaster. Procedural whitewash variation may be better; 1K secondary. |
| Guardrail metal | [PH `rusty_metal_sheet`](https://polyhaven.com/a/rusty_metal_sheet) | Use only restrained rust variation; procedural galvanized base preferred. [PH `galvanized_sheet_metal`](https://polyhaven.com/a/galvanized_sheet_metal) is CC0 but **vaulted/not publicly released** at check time: do not plan on that download. |
| Bark | [PH `pine_bark`](https://polyhaven.com/a/pine_bark) | 1K secondary; does not establish olive bark suitability. |
| Pine twig/leaf alpha | [PH `pine_tree_01`](https://polyhaven.com/a/pine_tree_01) | Page explicitly lists **Twig Alpha**, diffuse and normals. Source tree is **17M triangles**: do not import it directly. Evaluate its twig texture for our own low-poly cards/LODs. A ready AC billboard was **not verified**. |
| Olive foliage / billboard | No suitable ready CC0 olive atlas/billboard verified in this search. | Keep olive cards/atlas procedural unless a later specifically licensed asset is checked. This is **not** a claim neither library contains one. |

Performance proposal (not measured): shared 2K hero and 1K secondary maps,
mipmapped DDS, meter-based detail scale, merged chunk/material meshes and LODs;
prioritize silhouettes and horizon before increasing mesh density. The template
water and TreeFX/LOD references in §5 identify verified mechanisms, not a tested
FPS budget. No borrowed AC track textures, meshes or full config blocks are
included in this work.

## 8. Outstanding UNVERIFIED checklist

* Installed CSP preview compatibility, actual AC/Pure appearance/FPS, rain physics,
  map channel response under current LCS/Gamma, and new material numeric values.
* Guessed `ksPerPixelMultiMap_detail(_NM)` names, `ksSeaWater`, standalone `[WATER]`,
  generic track `[SKY]` and any Pure-only INI syntax: **do not implement these**.
* Full Blender → KN5 → AC BC5 support; DDS normal convention/reconstruction,
  color-space flags and mip/alpha quality in the user's rendering configuration.
* Exporter falsy-override repair (identified only, no exporter code changed),
  end-to-end multiple-map test for new shaders and complete required property sets.
* Wind weights/deformation for merged vegetation; TreeFX conversion on Windows;
  a ready CC0 olive atlas or pine/olive billboard.
* Local realism of the proposed textures, exact coastline/water blend behavior,
  large water-plane rendering cost, distant-terrain accuracy and final LOD budgets.
* Official Pure track-author/manual availability beyond the public creator pages;
  no authenticated Patreon/download or Discord documentation was read.

## 9. Implemented v2 material decisions (material phase only)

This section supersedes the earlier research-only status for material export,
not for AC runtime verification. Implemented recipes and measured evidence are
in `scripts/materials.py`, `scripts/blender_materials.py` and
`data/materials_info.json`; source downloads are locked in `data/assets.lock.json`.
Numeric tuning, masks, wear, tile scales and the galvanised-style finish are
project artistic choices, not claims about real RN24 appearance or AC defaults.

**Road and terrain:** `ksMultilayer_fresnel_nm4` uses world XZ multiplied by
`multR/G/B/A` for its detail and normal samples
(`S:recreated/ksMultilayer_fresnel_nm4_ps.fx:116–151`). This avoids a scalar
detailUVMultiplier stretching grain between the road's ~7 m width and 140 m
atlas period. Its four mask channels weight both normals and colors
(`S:recreated/ksMultilayer_fresnel_nm4_ps.fx:154–183`). Road RGB weights select
asphalt/repair/gravel-edge; A selects white paint with a flat normal. Terrain
weights grass and dry dirt. `magicMult`, Fresnel controls and tiling controls
are declared in `S:recreated/ksMultilayer_fresnel_nm4_ps.fx:10–34`.
The shader uses diffuse alpha for Fresnel/specular intensity and explicitly
does **not** use `ksSpecular`
(`S:recreated/ksMultilayer_fresnel_nm4_ps.fx:187–200`), so detail textures carry
a restrained roughness-derived alpha; it is not a guessed txMaps convention.
Whether this numeric tuning looks correct under the user's LCS/Pure is
**UNVERIFIED**. No guessed `_detail_NM` shader is used.

**Other surfaces:** `ksPerPixelMultiMap` reads diffuse, normal, maps and optional
detail (`S:recreated/ksPerPixelMultiMap_ps.fx:19–38`). Our txMaps is deliberately
authored from roughness for artistic specular strength/exponent/reflection
control, **not** a direct PBR ORM map. Current source scales specular by R and
exponent by G (`S:recreated/include_new/base/utils_ps.fx:892–900`); B also affects
reflection-related behavior (`S:recreated/include_new/base/utils_ps.fx:711–737`).
Uniform wetness is not baked in; RainFX configuration remains deferred.

**Critical binding detail:** the exporter emits numeric texture slots in JSON
insertion order (`E:exporter/material_writer.py:63–84`). Therefore multilayer
bindings are explicitly **diffuse, mask, detail R/G/B/A, normal R/G/B/A**, matching
`S:recreated/include_new/base/textures_ps.fx:6–19` and
`S:recreated/ksMultilayer_fresnel_nm4_ps.fx:38–47`. MultiMap order is diffuse,
normal, maps, detail. KN5 readback checks names **and numeric indices**, complete
property sets, values and opacity/depth flags against the generated recipe.
Blender material UI flags are explicitly set to 0/false/0 before applying
settings, avoiding the exporter's falsy-override problem; UI enums are declared
in `E:ui/materials_ui.py:44–63`. Existing property dictionaries are not partially
patched: complete intended sets are supplied.

**DDS:** ImageMagick writes full mip chains for DXT1 and DXT5; generated headers
and payload sizes are checked by `scripts/check_kn5.py:inspect_dds` and embedded
bytes are SHA-256 compared to the recipe. RGB normals use DXT5, not unverified
BC5 reconstruction. `_nm4` decodes RGB using xzy*2−1
(`S:recreated/ksMultilayer_fresnel_nm4_ps.fx:156–173`). GL green is inverted for
the authored DirectX convention; **actual AC tangent handedness and compressed
normal quality remain UNVERIFIED**. Blender previews reverse green for their approximation;
its output is not evidence of AC shader behavior.

**Additional exporter defect found during implementation:**
`E:exporter/node_writer.py:254–267` converts positions/normals but assigns the
unconverted Blender loop tangent. The shader consumes that tangent and forms
its bitangent via a cross product
(`S:recreated/include_new/base/_include_vs.fx:241–243`,
`S:recreated/include_new/base/utils_vs.fx:5–11`), so leaving a Blender-XY tangent
beside an AC-Y-up normal is unsuitable for new normal maps. Our **local writer
adapter**, not a change to the addon checkout, derives ordinary mapped tangents
from the already-converted triangle positions and UVs. It does not retain the
addon's wrapped `loop.tangent` vectors after `obj.to_mesh_clear()`
(`E:exporter/node_writer.py:263–284`); readback caught zero tangents in mapped
meshes when those vectors were reused. Multilayer tangents instead use projected
AC +X to align with that shader's world-XZ detail coordinates. They are
orthogonalised/normalised; KN5 readback checks finite, unit, orthogonal bases
for every mapped mesh. Unchanged diffuse-only foliage/water retain v1 tangents.
This verifies serialized bases, **not** the final in-game normal appearance.

**CC0 provenance:** each asset's page URL and the provider CC0 license link are
in CREDITS and the lock. Individual pages were downloaded and checked for CC0;
Poly Haven map downloads were additionally checked against API MD5 metadata
before SHA-256 locking. ambientCG Metal003 archive integrity was checked before
locking. Metal003 is silver steel, not provider-verified galvanisation
(https://ambientcg.com/view?id=Metal003); zinc spangling is procedural. No vaulted
Poly Haven asset, track texture or paid-mod content was downloaded.

**Data-channel mip correction found by visual inspection:** the installed
ImageMagick encoder's automatic mips treated mask A as transparency: decoding
our initial terrain mask gave RGB=(0,0,0), A=0 from mip 1 onward despite R+G=1
at level 0. That output was rejected. Masks and color/specular-alpha textures
now downsample channels independently, compress each level with ImageMagick
`dds:mipmaps=0`, then assemble the full legacy DDS chain. That define is verified
in https://github.com/ImageMagick/ImageMagick6/blob/main/coders/dds.c
(`GetImageOption(image_info,"dds:mipmaps")`, zero disables mip generation).
The validator decodes and samples **every mask mip** to check mean channel
weights stay close to one; BC3 can locally alter independent RGB/alpha weights,
so pointwise sums are not required to be exact. Header validity alone would
not detect the lost RGB fault. Header/caps/format constants follow
https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-header and
https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-pixelformat.
Preview DDS images use `CHANNEL_PACKED`, so RGB and data alpha do not affect each
other (https://docs.blender.org/api/3.6/bpy.types.Image.html#bpy.types.Image.alpha_mode).
The installed Blender 3.6 loader also emits an enum warning when the addon reads
the DDS image's `file_format`; the local texture-writer adapter instead reads
the verified original DDS bytes directly, bypassing that enum access and image
copy. PNG handling still delegates to the addon. Embedded DDS SHA-256 comparison
checks that the adapter does not transcode the files.

**Optional comparison rendering:** `build.py render` uses Cycles CPU for both
tagged-v1 and v2 scenes, 16 samples and denoising, with identical camera/light
settings. Cycles sampling/denoising controls are documented at
https://docs.blender.org/manual/en/3.6/render/cycles/render_settings/sampling.html.
The renderer is an approximation of the maps, not AC shader execution. Headless
Eevee stalled on later views here; its underlying cause remains **UNVERIFIED**.
Rendering is excluded from `materials`/`all`, including legacy preview calls.
Grey asphalt/repair targets, green-olive grass and grey-beige gravel are artistic
color grades, not new shader properties. A 140 m strip spaces small soft repairs;
background macro detail repeats at 28 m. Dry patches cover 25% of the inland/left
terrain mask and 35% of the coastal/right mask; the side assignment is a broad
artistic approximation rather than a survey-derived classification.

## 10. Shipped CSP extension config and sand correction

`scripts/ext_config.ini.template` is original project tuning, generated by
`build.py csp` using the exported `kn5_materials` inventory. Every selector is
an exact name; standalone validation rejects missing names. No other track's
configuration block is copied. Sources (also cited beside each INI section):

* GrassFX syntax/color thresholds/shapes: W:Tracks-–-Grass-FX.md:5–54;
  C:config/tracks/putnam_park.ini:87–90 is a real section example. Only our two
  terrain materials spawn blades; road/kerb/gravel/cuts/beach/buildings/metal
  occlude. Green-olive terrain with dry patches supplies the intended palette;
  exact multilayer color masking needs runtime inspection. No invented COLOR.
  Color rejection is disabled for neutral macro diffuse; the verified
  multilayer mask adjustment maps our soil G channel to shorter grass, using
  W:Tracks-–-Grass-FX.md:79–129,187–204 and
  C:config/tracks/ks_silverstone.ini (multilayer GrassFX adjustment example).
* RainFX classification and baked paint brightness filtering:
  W:Tracks-–-RainFX.md:3–18; C:config/tracks/putnam_park.ini:77–85.
  `LINES_FILTER_MATERIALS`, not `LINES_MATERIALS`, is used for atlas paint.
  No arbitrary alpha/mask-channel selector was verified. The source describes
  future paint physics; present CSP preview wet-grip behavior is UNVERIFIED.
* Water include and Type: W:Tracks-–-Water-shader.md:5–15;
  C:config/tracks/common/materials_track.ini:53–69,310–364;
  C:config/tracks/monaco_2017.ini:16–23. Recommended normals come from the
  user's installed CSP (`UseRecommendedTextures=1`), not redistributed files.
  Our sea is flat, upward, visual-only, ~6.23×4.26 km with finite planar UVs.
  No depth-aware transparency, caustics or geometry displacement is assumed.
* Lighting deliberately omitted: W:Tracks-–-General-options.md:10–17 says to
  override ground ambient only if needed. No lamp fixtures exist yet; lighting
  series wait for Phase 4. Wind on solid merged trees likewise deferred
  (W:Tracks-–-General-options.md:39–47). No BASIC/seasonal/Pure overrides.

Sand diagnosis on the accepted v2 scene: actual KN5 txDiffuse correctly bound
`sand_diffuse.dds`; decoded mean RGB ~65/58/44, matching CC0 source ~66/58/45.
V1 procedural sand averaged ~207/189/138. Blender beach normals have positive Z
(.383–1), UVs are finite/nondegenerate, and Base Color links to that exact DDS.
This disproves missing binding or inverted geometry as the primary explanation.
The normal map is near neutral on average (~128/127/249). Only the sand diffuse
is regraded to pale warm sand, with unchanged UV/normal/map inputs; the two
requested Cycles views test this correction independently of CSP rendering.
Asphalt/repair grading is reduced 12% in sRGB as a project artistic adjustment.
Runtime GrassFX/RainFX/water/Pure appearance and performance remain UNVERIFIED.
