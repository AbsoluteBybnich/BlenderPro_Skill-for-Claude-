"""High -> low-poly map baking in Blender Cycles (Normal, AO, Curvature, optional Thickness-free set).

    blender -b scene.blend -P bake_maps.py -- --low SM_Prop_low --high SM_Prop_high --out //bakes \
        --size 2048 --maps normal ao curvature --cage 0.02 --samples 32 --target ue

    import bake_maps as bk
    bk.bake(low_obj, high_obj, "/tmp/bakes", size=2048, maps=("normal", "ao"), cage_extrusion=0.02)

Prereqs the script cannot fix for you: (1) low has non-overlapping UVs, (2) low and high occupy the same
space, (3) object scale applied, (4) high is closed/clean. Run qa_check.py first.

--target ue   -> normal map in DirectX convention (green channel down / -Y), what Unreal expects.
--target gl   -> OpenGL (+Y), what Blender/Unity/glTF/Marmoset-default expect.
Files: <out>/<low>_normal.png, _ao.png, _curvature.png. All saved as Non-Color data (no view transform).

Notes
* Curvature here is an approximation (Cycles Pointiness of the *high* mesh -> ramp -> emission bake). It needs a
  reasonably dense high poly and is noisy on sharp hard-surface edges. For production curvature use Marmoset
  Toolbag / Substance Painter / xNormal, which compute it from the normal map.
* Cycles bakes on CPU here; set `--device gpu` only on machines with a configured GPU.
* Marmoset Toolbag is the usual alternative: same inputs (low, high, cage), but it needs the GUI or its own
  Python API, which this script does not cover.
"""
import os
import sys

import bpy
import bmesh  # noqa: E402

MAPS = ("normal", "ao", "curvature")


# --------------------------------------------------------------------------- helpers
def _activate_pair(low, high):
    vl = bpy.context.view_layer
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in vl.objects:
        o.select_set(False)
    high.select_set(True)
    low.select_set(True)
    vl.objects.active = low          # selected-to-active: low must be ACTIVE, high merely selected


def make_cage(low, extrusion=0.02, name=None):
    """Duplicate `low` and push every vertex along its normal by `extrusion` (scene units).

    Use when a plain extrusion value produces rays that miss/pierce on concave areas: a hand-tuned cage
    gives per-region control. Returns the cage object (hidden from render)."""
    cage = low.copy()
    cage.data = low.data.copy()
    cage.name = name or f"{low.name}_cage"
    cage.modifiers.clear()
    bm = bmesh.new()
    bm.from_mesh(cage.data)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * extrusion
    bm.to_mesh(cage.data)
    bm.free()
    (low.users_collection[0] if low.users_collection else bpy.context.scene.collection).objects.link(cage)
    cage.hide_render = True
    cage.display_type = "WIRE"
    return cage


def _bake_material(obj):
    """Ensure `obj` has a material whose node tree we can add bake-target image nodes to."""
    if obj.material_slots and obj.material_slots[0].material:
        mat = obj.material_slots[0].material
    else:
        mat = bpy.data.materials.new(f"{obj.name}_bake")
        if not obj.material_slots:
            obj.data.materials.append(mat)
        else:
            obj.material_slots[0].material = mat
    mat.use_nodes = True
    return mat


def _target_image(mat, name, size, float_buffer=True):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=float_buffer)
    img.colorspace_settings.name = "Non-Color"
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    node.name = node.label = f"BAKE_{name}"
    mat.node_tree.nodes.active = node    # Blender bakes into the *active* image node
    return img, node


def _curvature_material(strength=0.5):
    mat = bpy.data.materials.new("BAKE_curvature_tmp")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.5 - 0.5 * strength * 0.5
    ramp.color_ramp.elements[1].position = 0.5 + 0.5 * strength * 0.5
    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(geo.outputs["Pointiness"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def _save(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return path


# --------------------------------------------------------------------------- main API
def bake(low, high, out_dir, size=2048, maps=("normal", "ao"), samples=32, cage_extrusion=0.02,
         max_ray_distance=0.0, cage_object=None, margin_px=16, target="ue", ao_distance=0.5,
         curvature_strength=0.6, device="cpu"):
    """Bake `maps` from `high` onto `low`'s UVs. Returns {map_name: png_path}."""
    os.makedirs(out_dir, exist_ok=True)
    for m in maps:
        if m not in MAPS:
            raise ValueError(f"unknown map {m!r}; choose from {MAPS}")
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False          # denoising smears bake results
    sc.cycles.device = "GPU" if device == "gpu" else "CPU"
    sc.render.bake.target = "IMAGE_TEXTURES"
    if not sc.world:
        sc.world = bpy.data.worlds.new("World")
    sc.world.light_settings.distance = ao_distance   # AO bake ray length (world AO distance)

    mat = _bake_material(low)
    results = {}
    common = dict(use_selected_to_active=True, margin=margin_px, margin_type="EXTEND", use_clear=True,
                  cage_extrusion=cage_extrusion, max_ray_distance=max_ray_distance)
    if cage_object:
        common.update(use_cage=True, cage_object=cage_object.name if hasattr(cage_object, "name") else cage_object,
                      cage_extrusion=0.0)

    for m in maps:
        img, node = _target_image(mat, f"{low.name}_{m}", size)
        _activate_pair(low, high)
        mat.node_tree.nodes.active = node
        if m == "normal":
            bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", normal_r="POS_X",
                                normal_g="NEG_Y" if target == "ue" else "POS_Y", normal_b="POS_Z", **common)
        elif m == "ao":
            bpy.ops.object.bake(type="AO", **common)
        elif m == "curvature":
            saved = [s.material for s in high.material_slots]
            cmat = _curvature_material(curvature_strength)
            if not high.material_slots:
                high.data.materials.append(cmat)
            else:
                for s in high.material_slots:
                    s.material = cmat
            try:
                bpy.ops.object.bake(type="EMIT", **common)
            finally:
                if saved:
                    for s, old in zip(high.material_slots, saved):
                        s.material = old
                else:
                    high.data.materials.clear()
                bpy.data.materials.remove(cmat)
        results[m] = _save(img, os.path.join(out_dir, f"{low.name}_{m}.png"))
    return results


# --------------------------------------------------------------------------- CLI
def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def _opt(a, flag, cast=str, default=None):
    return cast(a[a.index(flag) + 1]) if flag in a else default


if __name__ == "__main__":
    a = _args()
    if "--low" not in a or "--high" not in a:
        print(__doc__)
        sys.exit(2)
    maps = []
    if "--maps" in a:
        for tok in a[a.index("--maps") + 1:]:
            if tok.startswith("--"):
                break
            maps.append(tok)
    out = bake(bpy.data.objects[_opt(a, "--low")], bpy.data.objects[_opt(a, "--high")],
               bpy.path.abspath(_opt(a, "--out", default="//bakes")),
               size=_opt(a, "--size", int, 2048), maps=tuple(maps) or ("normal", "ao"),
               samples=_opt(a, "--samples", int, 32), cage_extrusion=_opt(a, "--cage", float, 0.02),
               max_ray_distance=_opt(a, "--ray", float, 0.0), target=_opt(a, "--target", default="ue"),
               device=_opt(a, "--device", default="cpu"))
    for k, v in out.items():
        print("baked", k, "->", v)
