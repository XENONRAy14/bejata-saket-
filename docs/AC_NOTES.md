# Assetto Corsa track checklist — before geometry

Research date: 2026-11-13. **Scope:** documented conventions and exporter behavior, not an in-game certification. `UNVERIFIED` means no adequate evidence or no runtime test; examples are not claims about universal defaults.

## Evidence key

Every bracketed reference below resolves to a URL or a code inspection. Exporter line references are **verified by reading exporter code** under `/tmp/blender-assetto-corsa-tools`, revision `5f0c163cd75f071b21b7f8f98651d50870cf8e85`; upstream [source](https://github.com/moppius/blender-assetto-corsa-tools/tree/5f0c163cd75f071b21b7f8f98651d50870cf8e85).

| Ref | Source |
|---|---|
| G | [Build your FIRST track — BASIC GUIDE](https://assettocorsamods.net/threads/build-your-first-track-basic-guide.12/), posts #1 (guide), #2 (troubleshooting), #3 (pit surface), #7/#9 (default surfaces). Fetched successfully with curl, including spoiler text. |
| H | [Hagn exporter page](https://site.hagn.io/assettocorsa/blender-kn5-exporter), older Blender exporter; links to the maintained fork. |
| S | Hagn's actual [sampletrack.zip](https://drive.google.com/uc?export=download&id=1z4qb3Pk3_jMIPvX1NvqUbCHA5q-kgqjh), found through its [embedded Drive folder](https://drive.google.com/embeddedfolderview?id=11Z3a-eEpCM70_AluyTLpPH6c7ohcmB8p). Downloaded to `~/tools/hagn-sampletrack.zip`; inspected ZIP contents directly, not run in AC. Paths below are inside this archive. |
| HS | [Hagn surfaces.ini](https://site.hagn.io/assettocorsa/modding/tracks/data/surfaces-ini) |
| HT | [Hagn track.kn5 logical objects](https://site.hagn.io/assettocorsa/modding/tracks/track-kn5) |
| HU | [Hagn ui_track.json](https://site.hagn.io/assettocorsa/modding/tracks/ui/ui_track-json) |
| HM | [Hagn map.ini](https://site.hagn.io/assettocorsa/modding/tracks/data/map-ini) |
| HC | [Hagn cameras.ini](https://site.hagn.io/assettocorsa/modding/tracks/data/cameras-ini) |
| HL | [Hagn lighting.ini](https://site.hagn.io/assettocorsa/modding/tracks/data/lighting-ini) |
| A | [A2B beginner advice, OverTake/RaceDepartment](https://www.overtake.gg/threads/absolute-newbie-needs-help-creating-track.208864/), indexed text retrieved by web search (full-page reader returned no content). |
| P | [A2B practice spawn report](https://assettocorsamods.net/threads/pits-scale-car-spawn-problem-making-track-in-blender.2656/) |
| T | [A2B timing discussion, guide page 61](https://assettocorsamods.net/threads/build-your-first-track-basic-guide.12/page-61) |
| U | [Example UI with author/year/version/url](https://assettocorsamods.net/threads/ui-for-hayato-touge.3588/) |
| D | [“Main layout is damaged” example: Coronet Peak](https://assettocorsamods.net/resources/coronet-peak-hill-climb-nz.158/), comments identify KN5/folder name mismatch. |

## 1. Physical mesh and surfaces checklist

- [ ] Use names such as `1ROAD`, `2ROAD_x`, `1GRASS_003`: positive numeric prefix enables physical rolling surfaces; the surface keyword maps to `KEY=ROAD`, `KEY=GRASS`, etc. Suffixes do not change the surface. The number is **not** the `[SURFACE_n]` index; uniqueness or additional numeric meaning is not established (Hagn explicitly says unclear). [G §1A; HT]
- [ ] Do not mix two surface keywords in one name (`1GRASS_road_blah`, etc.). [G #2, item 4]
- [ ] Confirmed documented built-in rolling keys: **ROAD, GRASS, KERB, SAND**, defined in AC `system/data/surfaces.ini`. **GRAVEL is not established as built-in**: guide demonstrates it as a custom surface. `WALL` is a special collision keyword, not a confirmed standard rolling-surface parameter set. [G §1A; HS]
- [ ] `WALL` anywhere in a mesh name makes a collision obstacle, even without a digit; use `1WALL`, `2WALL`, etc. for consistency. Naming the collision mesh, not setting a material shader or `IS_VALID_TRACK`, is the documented trigger. [G §1A; HS]
- [ ] Track-local `data/surfaces.ini` is **not required when using default surfaces**; add custom surfaces (including a pit-lane surface) when needed. No need to duplicate all system defaults. Exact override/merge precedence if repeating built-in keys is **UNVERIFIED**. [G #7/#9, §folder structure]
- [ ] Pit-lane recipe: custom `KEY=PITS-ZONE`, mesh `1PITS-ZONE`, `IS_PITLANE=1`; spawn empties alone do not define the pit-lane rolling surface. [G #3]

### Surface parameters — sourced examples, NOT a dump of stock defaults

The following values are the **ASPHALT/KERB examples** in HS and `S:mytrack/data/surfaces.ini`. Exact installed Kunos defaults for ROAD/GRASS/KERB/SAND and any WALL/GRAVEL parameter set are **UNVERIFIED**: no Windows AC system file was available here. Do not label the ASPHALT sample as stock ROAD. [HS; S]

| Parameter | Meaning / uncertainty | ASPHALT / KERB example |
|---|---|---|
| `KEY` | Surface name used by meshes [HS] | `ASPHALT` / `KERB` |
| `FRICTION` | Surface friction [HS] | `1` / `0.92` |
| `DAMPING` | Slow-down factor [HS] | `0` / `0` |
| `WAV`, `WAV_PITCH` | Contact sound file and playback-rate multiplier [HS] | empty, `0` / `kerb.wav`, `1.3` |
| `FF_EFFECT` | Meaning **UNVERIFIED** (source calls it unknown) [HS] | `NULL` / `1` |
| `DIRT_ADDITIVE` | Dirty surface flag, 1 enabled / 0 disabled [HS] | `0` / `0` |
| `IS_VALID_TRACK` | Valid track versus penalty-triggering surface [HS] | `1` / `1` |
| `BLACK_FLAG_TIME` | Exact semantics/units **UNVERIFIED** (source calls unknown) [HS] | `0` / `0` |
| `SIN_HEIGHT` | Simulated bump height, meters [HS] | `0` / `0` |
| `SIN_LENGTH` | Source describes inverse-length behavior: 1 → 1 m; 2 → 0.5 m; runtime **UNVERIFIED** [HS] | `0` / `0` |
| `IS_PITLANE` | Pit-lane flag enabling limiter [HS; G #3] | `0` / `0` |
| `VIBRATION_GAIN`, `VIBRATION_LENGTH` | Exact effect/units **UNVERIFIED** (source calls unknown) [HS] | `0`, `0` / `0.1`, `0.2` |

## 2. Spawn and timing empties — A2B is not a closed circuit

| Exact name | Purpose / necessity according to sources |
|---|---|
| `AC_START_n` | Race/grid positions, zero-based integer suffix (`0`, `1`, not `01`). Circuit guide minimum includes 0 and 1. A2B guide says **no starting grid**, but A recommends `AC_START_0` for “on the grid” spawn. **Not proven universally mandatory for A2B**; include `AC_START_0` defensively if supporting that launcher choice. [G §1B; HT; A; P] |
| `AC_PIT_n` | Pit spawn per car, same zero-based naming. A2B explicitly retains pit spawns. Keep pits even for an A2B track. Guide's circuit minimum uses two; whether one is sufficient in every mode is explicitly untested there. [G §1B; HT] |
| `AC_HOTLAP_START_0` | Hotlap spawn; retained for A2B. [G §1B; HT] |
| `AC_TIME_n_L`, `AC_TIME_n_R` | Paired timing poles, left/right viewed in driving direction; imaginary line between origins. Circuit: 0=start/finish, 1=first intermediate, 2=second intermediate, at most two intermediates per guide. Axis orientation unnecessary for gates. [G §1B] |
| `AC_AB_START_L`, `AC_AB_START_R` | A2B start-line pair, not a car spawn. [G §1B; A] |
| `AC_AB_FINISH_L`, `AC_AB_FINISH_R` | A2B finish-line pair. [G §1B; A] |

- [ ] Use Blender **empties**, avoiding visible cube geometry; the guide permits invisible cubes too. Place origins **1–2 m above road**, its recommendation rather than a measured engine minimum. [G §1B, #2 troubleshooting]
- [ ] At the **AC/KN5 side**, spawn pivot **+Y up, +Z forward**. [G §1B, developer “DETAILS by Simone”]
- [ ] **Direct exporter conversion is not the FBX workflow.** `exporter/exporter_utils.py:23–43` maps position `(x,y,z)` → `(x,z,-y)`, converts quaternion axes likewise, and swaps Y/Z scales. `node_writer.py:116,127–132` converts `matrix_local` and writes it; `kn5_writer.py:61–64` serializes by column. [verified by reading exporter code]
- [ ] Consequently, for an unparented, unit-scale empty on level ground, **identity rotation gives AC +Z forward**, corresponding to Blender world **−Y**. To face Blender road tangent `(dx,dy,0)`, use only Blender Z yaw `atan2(dx,-dy)`, keep X/Y rotation zero; local −Y points down-road and local Z points up in Blender. This is a **code-derived convention**, not an AC driving test. Do **not** blindly add the guide's FBX-oriented 90° X rotation to this direct exporter. [code above + G axis requirement; in-game result **UNVERIFIED**]

Numerical Blender 3.6.23 probe of `convert_matrix`, no geometry created (AC unit forward `(0,0,1)` and up `(0,1,0)` transformed):

```text
IDENTITY_AC_FORWARD (0.0, 0.0, 1.0)
YAW90_AC_FORWARD (1.0, 0.0, 0.0)
YAW90_AC_UP (0.0, 1.0, 0.0)
```

Evidence: direct execution of `exporter_utils.convert_matrix(Matrix.Identity(4))` and `convert_matrix(Matrix.Rotation(pi/2,4,'Z'))` using installed Blender; mathematical orientation only, **UNVERIFIED in AC**.

**Exporter gotcha:** `utils/constants.py:17–30` recognizes `AC_OPEN_START_*`/`AC_OPEN_FINISH_*`, **not `AC_AB_*`**. It is a warning allowlist, not a name translation: `node_writer.py:85–94,112–125` still writes other empties with their original names, warning “Unknown logical object”. Keep the guide's `AC_AB_*` names; do not rename them to OPEN just to suppress the warning. **AC runtime compatibility remains UNVERIFIED.** [verified by reading exporter code; G]

## 3. UI metadata and loading checklist

| `ui/ui_track.json` field | Evidence / intended use |
|---|---|
| `name`, `description` | Display name and hover description; strings. [HU; S:mytrack/ui/ui_track.json] |
| `tags`, `country` | Category filtering; string array / string. [HU] |
| `geotags`, `city` | Example uses `["lat", "lon"]` and city string; Hagn marks behavior unknown. Numeric/string coordinate parsing and vanilla geotag behavior **UNVERIFIED**. [HU] |
| `length`, `width` | Display dimensions, example strings `"0m"`, `"0m-0m"`; do not infer physics dimensions from these. [HU; physics role **UNVERIFIED**] |
| `pitboxes` | Available pit count, limits AI selection; sample is string `"2"`. Set it to the actual contiguous `AC_PIT_0…n` count (consistency recommendation). Exact mismatch failure behavior **UNVERIFIED**. [HU; HT; G troubleshooting #6] |
| `run` | Hover text according to Hagn (“No other change observed”). **`"run":"A2B"` is NOT verified as a mode switch.** Use AB timing objects for the documented A2B setup; runtime mode detection algorithm **UNVERIFIED**. [HU; G §1B] |
| `author`, `version`, `url`, `year` | Present in a community example (`author` string, `year` integer, `version`/`url` null). Meaning as metadata is evident, but mandatory status, type restrictions and vanilla-vs-CM interpretation **UNVERIFIED**. [U] |

- [ ] Single-model starter: folder and main KN5 basename must match, use lowercase. Guide says folder names latin letters/digits/underscores, no accented characters; track folder max 32 characters, extra layout max 15. [G folder restrictions, §2C; Hagn [Tracks](https://site.hagn.io/assettocorsa/modding/tracks)]
- [ ] “Track main layout is damaged” is **not a diagnosis of bad geometry**: a documented example is mismatched folder/KN5 name. Check this first; a complete catalog of causes, including whether malformed UI JSON alone produces that exact message, is **UNVERIFIED**. [D; G §2C]
- [ ] Guide's actual troubleshooting checklist: re-read setup; broken wheels → spawn axes, scale, 1–2 m height; wrong proportions → apply scale to 1:1; invisible road from above → normals; unexpected surface behavior → avoid two surface keywords; `CANNOT HAVE 0 CARS IN RACE.INI` → spawn names/axes, UI pit count, remove suspect AI line. It also links SDK low-res/B&W remedies. These are distinct symptoms, not all asserted causes of “layout damaged”. [G #2]

## 4. Packaging files — don't confuse map, outline, preview

| File | Requirement / verified format |
|---|---|
| `<track>.kn5` | Main geometry/material/texture file for the guide's simple single-model layout. [G] |
| `ui/ui_track.json`, `ui/preview.png`, `ui/outline.png` | Track-selection metadata, preview, overlaid track outline. Sample PNG headers are **355×200 for BOTH preview and outline**; these are working-example dimensions, not a proven hard size limit. [G; S:mytrack/ui/*, read PNG IHDR dimensions] |
| `map.png` + `data/map.ini` | In-game map and its coordinate transform, **not** `ui/outline.png`. Not required for initial basic driving: guide permits empty data; sample is an example of a configured map, not proof it is mandatory. [G; HM; S:mytrack/data/map.ini] |
| `data/cameras.ini` | Optional TV replay cameras; additional sets `cameras_1.ini`, etc. Camera switching needs an AI line; otherwise first camera stays selected. Format: `[HEADER] VERSION=3, CAMERA_COUNT=1, SET_NAME=TV 1`; `[CAMERA_0]` with `NAME`, `POSITION`, `FORWARD`, `UP`, FOV, clip planes, timing and exposure fields. Use full source/sample rather than treating these abbreviated keys as a minimal complete file. [G; HC; S:mytrack/data/cameras.ini] |
| `data/lighting.ini` | Optional custom sun placement: `[LIGHTING]`, `SUN_PITCH_ANGLE=35`, `SUN_HEADING_ANGLE=45` example. Guide spells it “lightning.ini”; actual sample and Hagn page use **lighting.ini**. [G; HL; S:mytrack/data/lighting.ini] |
| `data/groove.ini`, `crew.ini`, `audio_sources.ini`, `overlays.ini` | Optional/customization at this stage (guide permits empty data). Groove darkening behavior; crew side; audio emitters per G. Sample groove is `[HEADER] GROOVES_NUMBER=0`; overlays semantics **UNVERIFIED**. [G; S:mytrack/data/*] |
| `ai/fast_lane.ai`, `ai/pit_lane.ai` | AI route / pit route roles per [Hagn Tracks](https://site.hagn.io/assettocorsa/modding/tracks). **Empty `ai/` directory is allowed**, no working AI; sample also has empty ai. Do not create zero-byte `.ai` placeholders and assume usable AI. [G; S; placeholder validity **UNVERIFIED**] |
| `texture/` | Authoring input textures; textures are embedded in final KN5, so not needed as a runtime folder per guide. [G] |

Map example, directly from `S:mytrack/data/map.ini` / HM (numbers apply to that sample only):

```ini
[PARAMETERS]
WIDTH=512
HEIGHT=512
MARGIN=20
SCALE_FACTOR=1
MAX_SIZE=1600
X_OFFSET=256
Z_OFFSET=256
DRAWING_SIZE=10
```

`WIDTH/HEIGHT` are image dimensions; offsets/scale align map and car position. HM's prose says `Y_OFFSET` but its actual example and sample use **Z_OFFSET**; use the file spelling. Exact meanings of MARGIN/MAX_SIZE/DRAWING_SIZE remain **UNVERIFIED** (source itself calls unknown). [HM; S]

## 5. Exporter settings / headless checklist

Verified by reading `exporter/exporter_utils.py:74–80`: `settings.json` is read **beside the output KN5**, absence returns `{}`. The following illustrative schema uses the **current fork's** names, not all names from the old Hagn sample. [verified by reading exporter code]

```json
{
  "materials": {
    "Road*": {
      "shaderName": "ksPerPixel",
      "alphaBlendMode": "Opaque",
      "alphaTested": false,
      "depthMode": "DepthNormal",
      "properties": {
        "ksDiffuse": {"valueA": 0.4},
        "ksAmbient": {"valueA": 0.4}
      },
      "textures": {"txDiffuse": {"textureName": "road.png"}}
    }
  },
  "nodes": {
    "1ROAD_PHYS*": {
      "lodIn": 0,
      "lodOut": 1000,
      "layer": 0,
      "castShadows": false,
      "visible": true,
      "transparent": false,
      "renderable": false
    }
  }
}
```

| Setting / constraint | Verified behavior (code paths relative to addon root) |
|---|---|
| Matching | Material/node selectors support case-insensitive `*` wildcard and `|` alternatives, anchored whole-name match. [verified by reading `material_writer.py:221–238`, `node_writer.py:349–366`, both under `exporter/`] |
| Materials | `shaderName`; `alphaBlendMode`: `Opaque`, `AlphaBlend`, `AlphaToCoverage`; `depthMode`: `DepthNormal`, `DepthNoWrite`, `DepthOff`; `alphaTested` boolean. Shader properties use scalar `valueA` / 2-, 3-, 4-number arrays `valueB/C/D`. Providing properties replaces default property list. **Gotcha:** truthiness tests ignore some zero/false overrides, including blend/depth enum 0 and `alphaTested=false`. [verified by reading `exporter/material_writer.py:27–41,170–208,240–319`] |
| Textures | `textures.<shaderInput>.textureName` maps to Blender image name; image nodes supply embedded textures. Slot numbers are assigned sequentially while writing; old sample's `slot` field is not read by current schema. [verified by reading `exporter/material_writer.py:62–77,151–160,210–219,270–277`; `exporter/texture_writer.py:47–60`] |
| Node flags | Exact keys: `lodIn`, `lodOut`, `layer`, `castShadows`, `visible`, `transparent`, `renderable` — **not** old sample's `isVisible/isRenderable`. UI describes `renderable` as rendering toggle; `visible` behavior explicitly unknown. For physics-only geometry, retain physical name, propose `renderable=false`, `castShadows=false`, `visible=true`; collision with these flags **UNVERIFIED in AC**. [verified by reading `exporter/node_writer.py:38–46,156–185,341–347`; `ui/nodes_ui.py:25–55`; G naming rule] |
| Image formats | PNG **and DDS** passed through explicitly; other formats take a conversion-to-PNG path. DDS is not the only format the writer accepts. Local smoke test embedded PNG and wrote 884 bytes; AC rendering of it **UNVERIFIED**. [verified by reading `exporter/texture_writer.py:63–81`; project `scripts/test_exporter.py:23–42`] |
| Vertex limit | Writer uses unsigned-short indices (0…65535), checks **more than 65536 vertices**, not more than 65535. Splits by material and then vertex limit; chunking breaks around `limit-3` to retain whole triangles. This counts expanded exported vertices (position/normal/UV/tangent), not just Blender control points. Large-mesh execution **UNVERIFIED**; splitting exists in code rather than unconditional failure. [verified by reading `exporter/kn5_writer.py:40–41`; `exporter/node_writer.py:134–136,165–175,248–278,283–306,374–410`] |
| Scene restrictions | Mesh children cause exception; `__` prefix suppresses object export. Non-mesh objects become logical nodes (use empties, no lights/cameras left in scene). [verified by reading `exporter/node_writer.py:85–94,112–115`; HT warns unknown logical nodes can interrupt loading] |

Exact headless invocation already exercised in Phase 0 (project fixture, not a track build):

```sh
cd /home/ubuntu/repos/bejaia_saket
~/tools/blender-3.6.23-linux-x64/blender -b --python-exit-code 1 -P scripts/test_exporter.py
```

The script installs/enables addon, constructs the fixture, writes `{}` beside output, then calls `bpy.ops.exporter.kn5(filepath=str(output / 'smoke.kn5'))`. Output previously observed: `KN5_SMOKE_OK Blender=3.6.23 bytes=884 file=/home/ubuntu/repos/bejaia_saket/out/exporter_smoke/smoke.kn5`. [project `scripts/test_exporter.py:9–42`; Phase 0 execution]

**Do not trust FINISHED alone:** operator catches exceptions, deletes failed output and still returns FINISHED; assert nonempty file and `sc6969` header as fixture does. It invokes a report operator even headlessly. [verified by reading `exporter/__init__.py:105–143`; project `scripts/test_exporter.py:38–42`]

## 6. A2B runtime acceptance checklist (future Windows check)

- [ ] Retain pits and hotlap spawn, choose “start from pits” for initial practice. A user report specifically needed that option without `AC_START_0`; this is a **scenario report**, not proof every launcher requires a grid empty. [G; P]
- [ ] Verify practice timing as well as hotlap: page-61 reports pit-exit laps not saved when `AC_TIME_0` overlaps AB start. Replies advise A2B intermediate gates numbered from 0, placed inside stage (two gates for three sectors), unlike circuit start/finish numbering. This is **community advice, UNVERIFIED locally**; do not copy circuit TIME_0-at-start uncritically. [T]
- [ ] Test practice pit/grid choices, hotlap orientation, AB start/finish crossing and saved times, restart/return-to-pits, wall collisions and hidden physical road. These remain **UNVERIFIED** because AC runs on the user's Windows PC; exporter success alone cannot answer them. [P; T; code limitations above]
