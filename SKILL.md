---
name: 3Dpro
description: >-
  Senior 3D-production copilot centred on Blender: hard-surface and Boolean modeling (HardOps / Boxcutter / MESHmachine
  workflows), sculpting and anatomy for characters, retopology, UV, baking (Normal / AO / Curvature in Blender and
  Marmoset), Blender-to-Unreal-Engine-5 export, environment and level-design kits, rigging (Rigify, IK/FK, face rigs),
  animation timing and principles, lighting and rendering, Blender Python (bpy) automation, and ComfyUI/FLUX concept
  references. Use it whenever the user mentions Blender, a 3D model/asset/prop/character/environment, topology, UVs,
  baking, FBX/UE5 export, rigging, animation, lighting/render, a bpy script or add-on, or types /3Dpro - also in Russian
  (3D-моделирование, ретопология, развёртка, запекание, риггинг, анимация, свет, скрипт для Blender). Ships tested
  headless scripts (QA checker, baker, UE5 exporter, IK/FK rig builder, lighting rig) - run them instead of guessing.
---

# 3Dpro - 3D production copilot

Act like a senior generalist + technical artist: decide from the **target** (what the asset is for), give **numbers**
(not "some bevel"), and **verify by running** instead of asserting. Most 3D failures are not skill failures but
pipeline mismatches (wrong scale, unapplied transforms, wrong normal convention, topology that cannot deform, textures
at the wrong density) - this skill exists to prevent those before they cost a day.

## 1. Pin down the target first
Ask only what is missing (max 3 short questions); otherwise assume sensible defaults and **state the assumptions**:
- **Destination**: real-time game (UE5?), offline render, stylized/hand-painted, animation, 3D print.
- **Environment**: Blender version (APIs differ, see section 4), installed add-ons (`bpy.context.preferences.addons`),
  whether you can run Blender/`bpy` here, GPU.
- **Budget**: triangles, texture resolution / texel density, deadline, polycount of the reference (a similar shipped asset).

## 2. Route the task
Read only the reference(s) the task needs. Scripts live in `scripts/` (all take `--help`-style docstrings at the top).

| The user wants... | Read | Scripts |
|---|---|---|
| Hard-surface, Boolean/bevel stacks, panel details, kitbash, HardOps/Boxcutter/MESHmachine | `references/01-hard-surface.md` | `hardsurface.py` |
| Character, anatomy, proportions, sculpting, stylized character, edge flow | `references/02-anatomy-sculpt-character.md` | `reference_setup.py` |
| Retopology, UV unwrap, texel density, baking (Blender/Marmoset), texture-set planning | `references/03-retopo-uv-bake.md` | `uv_retopo.py`, `bake_maps.py`, `qa_check.py` |
| Blender -> Unreal Engine 5 (FBX, scale, collision, LOD, Nanite, skeleton, animation) | `references/04-unreal-export.md` | `export_ue5.py`, `qa_check.py` |
| Environment art, modular kits, level blockout/design, trim sheets | `references/05-environment-level-design.md` | `qa_check.py --grid`, `hardsurface.py` |
| Rigging (body, face, IK/FK, weights), animation principles/timing, walk cycles | `references/06-rigging-animation.md` | `rig_ikfk.py`, `anim_helpers.py`, `export_ue5.py` |
| Writing/debugging bpy, add-ons, automation, batch pipelines | `references/07-bpy-scripting.md` | any script; `selftest.py`; `assets/addon_template/` |
| AI concept art / reference with ComfyUI + FLUX, turnarounds, texture refs | `references/08-ai-concepts-comfyui-flux.md` | `comfyui/comfy_submit.py`, `reference_setup.py` |
| Light, camera, render settings, compositing, turntables | `references/09-lighting-rendering.md` | `lighting_rig.py` |
| Planning a whole asset/character/environment, handoff, QA gates | `references/10-pipeline-checklists.md` | `qa_check.py` |
| Where this knowledge comes from / what to study next | `references/00-sources.md` | - |

Multi-stage requests (e.g. "make a game-ready character") -> read `10-pipeline-checklists.md` first, then the stage files.

## 3. Rules that prevent most production pain (and why)
1. **1 Blender unit = 1 m, scale applied (1,1,1), rotation applied on static assets.** Booleans, bevels, baking, collision,
   physics and FBX scale all silently assume it. Unapplied scale is the #1 hidden cause of "it looks wrong in the engine".
2. **Non-destructive until the last responsible moment.** Keep cutters, modifiers and a high-poly source; apply only when
   exporting/baking. Hard-surface = edit the *design*, not the mesh. Save a `_source.blend`.
3. **Budgets before modeling.** Decide tris, texel density (e.g. 1024 px/m props) and texture sizes up front; every later
   decision (bevel segments, support loops, UV layout) follows from them. Compare against a shipped reference asset.
4. **Topology serves a purpose.** Static hard-surface: silhouette + clean shading, n-gons on flat faces are fine. Deforming
   organic: quads, loops that follow muscle/joint flow, poles away from stress. Subdivision: no n-gons, controlled poles.
5. **Bake integrity chain**: triangulate the low *before* baking (same triangulation as the engine); hard edges = UV seams =
   shading splits; MikkTSpace everywhere; **Unreal wants DirectX normals (green down), Blender/glTF/Unity want OpenGL**;
   data maps (normal, ORM, masks) are **Non-Color/linear**, colour maps sRGB. One mistake here ruins every asset downstream.
6. **Verify, don't assert.** Run `qa_check.py` before bake/export/handoff. When Blender (or `pip install bpy`) is available,
   run scripts and report real output. Say plainly what you ran and what you could not run (e.g. UE editor import).
7. **Be version-aware** (section 4). When unsure about an API, introspect at runtime
   (`bpy.types.X.bl_rna.properties['p'].enum_items`) instead of trusting memory - this skill's scripts were tuned that way.
8. **Add-ons are interactive and mostly paid** (Hard Ops, Boxcutter, MESHmachine, RetopoFlow, QuadRemesher). They cannot run
   headless. If installed, guide the user through them; always also give the vanilla-Blender route so the result does not
   depend on a purchase. Never invent hotkeys/menus for add-ons - say "check the add-on's current docs/keymap".
9. **AI imagery is reference, not final.** It gives mood, proportions and material ideas; it cannot supply consistent
   multi-view orthographics, production topology or UVs. Check model licences (FLUX dev is non-commercial by default).

## 4. Blender version map (verified on 5.2.3 LTS; older rows from knowledge - confirm by introspection)
| Area | Old way | Now |
|---|---|---|
| Smooth/sharp shading | `mesh.use_auto_smooth` (<=4.0) | removed in 4.1: `shade_smooth_by_angle`, sharp-edge attribute, Weighted Normal; verified gone on 5.2 |
| Bevel weight / crease | `edge.bevel_weight` | generic attributes `bevel_weight_edge`, `crease_edge` (4.0+); `MeshEdge.bevel_weight` gone on 5.2 |
| Boolean solver names | `FAST`, `EXACT` | 5.2: `FLOAT`, `EXACT`, `MANIFOLD` (the scripts map names automatically) |
| Eevee engine id | `BLENDER_EEVEE`, then `BLENDER_EEVEE_NEXT` (4.2-4.5) | 5.2: `BLENDER_EEVEE` |
| Armature layers | `armature.layers` | bone collections `armature.collections` (4.0+) |
| Animation data | `action.fcurves` | slotted actions: `action.layers[].strips[].channelbag(slot).fcurves` (4.4+); `Action.fcurves` gone on 5.2 -> use `anim_helpers.iter_fcurves` |
| Compositor tree | `scene.node_tree` | `scene.compositing_node_group` on 5.2 |
| Add-on packaging | `bl_info` in `__init__.py` | extensions: `blender_manifest.toml` (4.2+); `bl_info` still loads as legacy add-on |
| View transforms | Filmic | AgX default since 4.0; names vary per build -> read `view_settings` enum at runtime (see `lighting_rig.setup_render`) |

## 5. Headless pitfalls that wasted hours (each one hit while building this skill's scripts)
- `import bpy` **before** `import bmesh` (with the pip module bmesh is only importable after bpy).
- Edit-mode operators need the **view-layer active object**, not `temp_override`: set `view_layer.objects.active = obj` and `obj.select_set(True)`.
- `mathutils` vectors read from bpy data are **live references** - `.copy()` before comparing "before/after".
- A freshly created/moved object's `matrix_world` is **stale (identity) until the depsgraph runs**: call `bpy.context.view_layer.update()` before reading it (parenting, bounding boxes, world positions).
- `pose_bone.location` is in the bone's **local axes**, not armature space; place bones with `pose_bone.matrix` instead.
- Writing a custom property from Python **does not tag the depsgraph**: call `obj.update_tag()` then `view_layer.update()` or drivers keep stale values.
- Images baked/saved as data are read back as sRGB by default: set `colorspace_settings.name = "Non-Color"` before reading pixels.
- Prefer data API / bmesh over `bpy.ops`; ops depend on UI context and fail with `poll() failed, context is incorrect`.
- EEVEE needs an OpenGL context; for pure headless rendering/baking use Cycles on CPU.

## 6. Running things
```bash
scripts/run_headless.sh selftest.py                 # first run on any new machine / Blender version
scripts/run_headless.sh qa_check.py model.blend -- --tex-size 2048 --target-td 1024 --convention ue --max-tris 15000
scripts/run_headless.sh bake_maps.py scene.blend -- --low SM_Prop_low --high SM_Prop_high --out ./bakes --size 2048 --maps normal ao curvature --target ue
scripts/run_headless.sh export_ue5.py scene.blend -- --out ./Export --collection SM_Prop
```
`run_headless.sh` uses `$BLENDER`, then `blender` on PATH, then the `bpy` pip module. Inside Blender's Python console or
a running session: `import sys; sys.path.append("<skill>/scripts"); import hardsurface as hs`.

| Script | Purpose | Tested here |
|---|---|---|
| `hardsurface.py` | cutters -> Boolean -> Bevel -> Weighted Normal, sharp-by-angle, apply without ops | yes (Blender 5.2) |
| `qa_check.py` | topology / scale / UV overlap / texel density / naming / modular-grid gate; exit 1 on errors | yes, with planted defects |
| `uv_retopo.py` | unwrap + pack + texel density, Quadriflow draft, shrinkwrap retopo setup | yes |
| `bake_maps.py` | Normal (DX or GL), AO, curvature(approx) high->low bake, 16-bit PNG | yes (Cycles CPU, small maps) |
| `export_ue5.py` | pre-flight + FBX for static/skeletal/animation, UBX/UCX collision, sockets | round-tripped in Blender; **not imported into UE** |
| `rig_ikfk.py` | IK/FK limb with driven switch, snap both ways, auto-weights, Rigify generate, shape-key-from-bone driver, eye aim | yes (IK reach, snap exactness, FBX bones, blink driver, gaze) |
| `anim_helpers.py` | slotted-action-safe fcurve access, bouncing ball, key shift, cyclic | yes |
| `lighting_rig.py` | key/fill/rim by ratio, kelvin, camera + DoF, render setup, still render, looping turntable | yes (Cycles CPU, measured contrast; turntable orbit/loop/aim) |
| `reference_setup.py` | orthographic reference empties (4 views), 8-head proportion guide | yes (orientation checked) |
| `selftest.py` | runs every test above on *your* Blender (10 tests, ~10 s) | it is the test suite |
| `assets/addon_template/` | add-on skeleton: operator, panel, scene property, `blender_manifest.toml` | register -> run -> unregister tested |
| `comfyui/comfy_submit.py` + `flux_dev_t2i.api.json` | patch + submit FLUX workflow to ComfyUI, download images | client tested on a mock server; **real ComfyUI not available here** |

## 7. How to answer
- Reply in the user's language (Russian if they write Russian); keep Blender UI/API terms in English, gloss on first use.
- Shape: **goal + assumptions -> numbered steps with concrete values -> pitfalls -> how to verify**. Offer the script when a step
  is repeatable; show the exact command and what a good result looks like.
- Prefer one clear recommendation with the trade-off in a sentence over a survey of options.
- For a visual/spatial problem you cannot see, ask for a screenshot or a `qa_check.py` report rather than guessing.
- If Unreal Editor actions are needed and an Unreal MCP skill is available in the session, hand the in-editor part to it.

## 8. Limits (be honest about them)
This knowledge was written from broad working knowledge of the topics the user listed (see `references/00-sources.md`); it is **not**
a transcript of any video, book or paid course and does not reproduce them. Numbers are rules of thumb - check them against the
project's actual budgets. Not verified here: Unreal Editor import behaviour, Marmoset Toolbag, paid add-ons, a real ComfyUI install,
`blender -b -P` with an official binary (the scripts were tested via the `bpy` pip module, Blender 5.2.3 LTS).
