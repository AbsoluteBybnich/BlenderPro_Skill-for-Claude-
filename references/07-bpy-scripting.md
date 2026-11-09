# Blender Python (bpy): automation and add-ons

Contents: 1 Mental model · 2 Which API to use · 3 Running scripts headless · 4 Core patterns (snippets all tested on 5.2) · 5 Add-on skeleton ·
6 Performance · 7 Error decoder · 8 Introspection (stop guessing) · 9 Testing · 10 Practice projects

Files: `scripts/*.py` (worked examples of all of this), `scripts/selftest.py`, `assets/addon_template/` (operator + panel + property + manifest; tested register -> run -> unregister).
Lineage of the topics: book-style Blender Python coverage (meshes, materials, rigs, animation, UI) and project-based Blender courses; this file condenses working practice, not their text.

## 1. Mental model
- `bpy.data` = the database: objects, meshes, materials, actions, images... (everything, whether linked into a scene or not). `bpy.data.meshes.new()` creates a datablock; an *object* instances it and must be linked to a collection to appear.
- `bpy.context` = what the UI "currently" has (active object, selection, mode, area). It is *empty or partial in headless runs*; scripts that rely on it break.
- `bpy.ops` = the UI's operators (same as clicking buttons). They depend on context and **poll**; they are slow and fragile in scripts.
- `bpy.types` = classes with RNA metadata (properties, enums, functions) - the source of truth for what exists in *your* Blender version.
- The **depsgraph** evaluates modifiers/constraints/drivers. `obj.evaluated_get(depsgraph)` gives the final result; changing data from Python does not always tag the graph - `obj.update_tag()` + `view_layer.update()`.
- `bmesh` = fast mesh editing API outside edit mode (create/modify/free); `mathutils` = Vector/Matrix/Quaternion/Euler (live references into data!).

## 2. Which API to use
1. **Data API / bmesh first** (no context, deterministic, fast): create meshes (`from_pydata` or bmesh), set attributes, modifiers, constraints, materials, drivers, collections.
2. **Operators only when no data-API equivalent exists** (UV unwrap, bake, quadriflow, parenting with auto weights, import/export). Prepare context explicitly:
   - object operators: `with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj): bpy.ops.object.shade_smooth()` (works for object ops).
   - **edit-mode operators** (`bpy.ops.mesh.*`, `bpy.ops.uv.*`) need the *view-layer* active object, not an override: `view_layer.objects.active = obj; obj.select_set(True); bpy.ops.object.mode_set(mode='EDIT')` (see `uv_retopo.activate`).
3. Avoid `bpy.ops` inside loops over thousands of items; do the batch with data API.

## 3. Running scripts headless
```bash
blender -b file.blend -P script.py -- --opt value        # real Blender; args after -- are yours
blender -b --python-exit-code 1 -P script.py             # non-zero exit on exception (CI)
blender -b --factory-startup -P script.py                # ignore user prefs/add-ons -> reproducible
blender -b file.blend --python-expr "import bpy; print(bpy.app.version_string)"
python script.py file.blend --opt value                  # with the `pip install bpy` module (wheel's Python version must match)
```
- Parse args robustly: `argv = sys.argv; args = argv[argv.index("--")+1:] if "--" in argv else argv[1:]` (all repo scripts do this so they run in both modes).
- With the pip module: `import bpy` first, then `bmesh`, `mathutils`; `bpy.ops.wm.open_mainfile(filepath=...)` to load a `.blend`.
- No UI -> no EEVEE render/bake; use **Cycles (CPU)** for headless rendering/baking. Set `scene.cycles.device = 'CPU'` unless a GPU is configured.
- Add-ons that are enabled in your UI are *not* enabled headless: `addon_utils.enable("io_scene_fbx")` / `bpy.ops.preferences.addon_enable(module="rigify")`.
- Paths: use `bpy.path.abspath("//file")` for blend-relative paths; write outputs to explicit absolute folders.

## 4. Core patterns (all executed on Blender 5.2.3)
```python
import bpy, bmesh, numpy as np

# create a mesh from raw data and link it
me = bpy.data.meshes.new("Tri"); me.from_pydata([(0,0,0),(1,0,0),(0,1,0)], [], [(0,1,2)]); me.update()
ob = bpy.data.objects.new("Tri", me); bpy.context.collection.objects.link(ob)

# fast vertex edits with numpy (100x faster than Python loops)
n = len(me.vertices); co = np.empty(n*3, dtype=np.float32)
me.vertices.foreach_get("co", co); co = co.reshape(n, 3); co[:, 2] += 1.0
me.vertices.foreach_set("co", co.ravel()); me.update()

# generic attributes (bevel weight, crease, custom data are attributes since 4.0)
a = me.attributes.new("my_weight", "FLOAT", "POINT"); a.data.foreach_set("value", [0.1, 0.2, 0.3])
col = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")      # vertex colours

# bmesh edit cycle
bm = bmesh.new(); bm.from_mesh(me)
for v in bm.verts: v.co.x *= 2
bm.to_mesh(me); bm.free()                                        # always free; never use bm after free

# modifiers, constraints, drivers
mod = ob.modifiers.new("Bevel", "BEVEL"); mod.width, mod.segments = 0.005, 3
drv = ob.driver_add("location", 2).driver; drv.expression = "frame * 0.01"

# evaluated (final) geometry, e.g. to measure or export after modifiers
dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); mesh_eval = ev.to_mesh(); ...; ev.to_mesh_clear()

# handlers and timers
def on_frame(scene, depsgraph=None): print(scene.frame_current)
bpy.app.handlers.frame_change_post.append(on_frame)               # remove on unregister!
bpy.app.timers.register(lambda: print("tick") or None, first_interval=1.0)  # return seconds to repeat, None to stop

# Geometry Nodes group from Python (4.0+ interface API)
ng = bpy.data.node_groups.new("GN", "GeometryNodeTree")
ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
ob.modifiers.new("GN", "NODES").node_group = ng
```
More patterns: materials via `mat.use_nodes = True; mat.node_tree.nodes[...]`; custom props `ob["x"] = 1.0` + `ob.id_properties_ui("x").update(min=0, max=1)`; collections `bpy.data.collections.new(); scene.collection.children.link()`; instancing with `empty.instance_type='COLLECTION'`; images `bpy.data.images.new(..., float_buffer=True)`; saving `bpy.ops.wm.save_as_mainfile(filepath=...)`.
Decorate hot paths with comments that say *why* (e.g. "Non-Color: data map"), future-you will thank you.

## 5. Add-on skeleton (tested)
`assets/addon_template/__init__.py` shows: `PropertyGroup` on the scene (`PointerProperty`), an **Operator** (`bl_idname`, `bl_options={'REGISTER','UNDO'}`, `poll`, `execute`, `invoke`), a sidebar **Panel**, and `register`/`unregister` (delete the scene property, unregister in reverse order). Test headless:
`m.register(); bpy.ops.object.threedpro_add_crate(); m.unregister()`.
- **Extensions (Blender 4.2+)**: ship `blender_manifest.toml` (id, version, name, tagline, maintainer, type=`add-on`, blender_version_min, license SPDX, permissions for files/network). Legacy `bl_info` still works for local add-ons. Extension code must not install packages at runtime - bundle wheels declared in the manifest.
- Naming: operators `CATEGORY_OT_name`, panels `CATEGORY_PT_name`, menus `CATEGORY_MT_name`; ids lowercase with dots/underscores.
- UI: `layout.prop`, `layout.operator`, `col = layout.column(align=True)`; use `unit='LENGTH'` and `subtype` so values show in scene units.
- Keymaps: register in `bpy.context.window_manager.keyconfigs.addon`; remove on unregister. Preferences: `AddonPreferences` with `bl_idname = __package__`.
- Packaging for users: zip the folder; test install in a clean profile (`--factory-startup`).

## 6. Performance
- Replace per-vertex Python loops with `foreach_get/set` + numpy; avoid `bpy.ops` and `view_layer.update()` inside loops (call once after the batch).
- Reuse evaluated depsgraph; do not rebuild modifiers each iteration. Free `bmesh` objects. Use `bpy.data.batch_remove` for many deletions.
- Large imports: disable undo (`bpy.context.preferences.edit.use_global_undo=False`) for batch jobs; avoid UI redraws (`-b`).

## 7. Error decoder
| Error | Meaning / fix |
|---|---|
| `RuntimeError: Operator bpy.ops.X.poll() failed, context is incorrect` | wrong mode/active object/area. Set active via view layer, enter the right mode, or use data API |
| `AttributeError: 'Mesh' object has no attribute 'use_auto_smooth'` | removed in 4.1: `shade_smooth_by_angle` / sharp edges / Weighted Normal |
| `AttributeError: ... 'fcurves'` on Action | slotted actions: `anim_helpers.iter_fcurves(obj)` |
| `KeyError: bpy_prop_collection[key]: key "..." not found` | wrong name or add-on not enabled (e.g. `preferences.addons["rigify"]`); introspect |
| `ReferenceError: StructRNA of type X has been removed` | you kept a reference to data that was freed/removed (bmesh after `free()`, removed object); re-fetch by name |
| `TypeError: enum "X" not found in (...)` | enum identifiers change per version (`FAST`->`FLOAT`, `BLENDER_EEVEE_NEXT`->`BLENDER_EEVEE`); read the enum at runtime |
| Value compare fails (`0.02 != 0.0199999995`) | properties are float32; compare with a tolerance |
| Before/after vectors look identical | `mathutils` objects from data are live; `.copy()` |
| New object sits at the origin / parent math is off | `matrix_world` is stale until `view_layer.update()`; call it before using world matrices |
| Driver/constraint result stale | tag + update: `obj.update_tag(); view_layer.update()` |
| `ModuleNotFoundError: bmesh` (pip module) | import `bpy` first |
| Image reads back wrong | set `image.colorspace_settings.name = "Non-Color"` for data maps before reading pixels |
| `Cannot render: no OpenGL / EEVEE` headless | use Cycles CPU |
| Add-on works in UI, not headless | it is disabled headless: enable via `addon_utils.enable` |

## 8. Introspection (stop guessing, ask Blender)
```python
import bpy
def enum(rna, prop): return [e.identifier for e in rna.bl_rna.properties[prop].enum_items]
print(enum(bpy.types.BooleanModifier, "solver"))                       # FLOAT, EXACT, MANIFOLD on 5.2
print([p.identifier for p in bpy.types.BevelModifier.bl_rna.properties])    # every property the modifier has
print(bpy.ops.export_scene.fbx.get_rna_type().properties.keys())       # operator parameters in THIS version
print(hasattr(bpy.types.Mesh.bl_rna.properties, "get") and 'use_auto_smooth' in bpy.types.Mesh.bl_rna.properties.keys())
```
Also: Python Console (`Window > Toggle System Console` / Scripting workspace) - hover a UI field, `Ctrl+C` copies its data path; Info editor shows the operator calls the UI just made (copy-paste them into scripts, then replace with data API).

## 9. Testing scripts
- Write scripts so the logic is importable (functions) and the CLI is under `if __name__ == "__main__"`.
- Test on a **real scene**: build tiny fixtures, run the function, **assert on results** (counts, positions, pixels). `scripts/selftest.py` is the pattern - run it on each new Blender version: `scripts/run_headless.sh selftest.py`.
- Plant defects deliberately to prove a checker catches them (done for `qa_check.py`).
- For batch jobs: log what changed, make it idempotent, never overwrite originals (write to a new file).

## 10. Practice projects (ordered by difficulty) and where this repo helps
1. Batch rename/organise by prefix + collection · 2. Auto-unwrap + texel density + export (`uv_retopo`, `export_ue5`) · 3. Turntable generator (`lighting_rig`) ·
4. Asset QA report (`qa_check`) · 5. Procedural prop generator (`hardsurface`) · 6. Rig builder (`rig_ikfk`) · 7. Bake pipeline (`bake_maps`) · 8. Add-on UI that wraps your tools (`assets/addon_template`).
