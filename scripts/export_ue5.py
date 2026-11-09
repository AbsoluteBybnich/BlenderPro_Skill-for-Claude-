"""Blender -> Unreal Engine 5 FBX export with pre-flight checks. Verified to run on Blender 5.2 LTS.
(FBX files were round-tripped back into Blender to check scale/size; they were NOT imported into Unreal here -
always verify the first import of a new asset type in the editor, see references/04-unreal-export.md.)

    blender -b scene.blend -P export_ue5.py -- --out ./Export --collection SM_Crate [--skeletal] [--no-triangulate]
    blender -b scene.blend -P export_ue5.py -- --out ./Export --selected

    import export_ue5 as ue
    problems = ue.preflight(objs)                    # [] == clean
    ue.export_static(objs, "Export/SM_Crate.fbx")
    ue.export_skeletal(armature, meshes, "Export/SK_Hero.fbx")
    ue.export_animation(armature, "Export/A_Hero_Walk.fbx", frame_start=1, frame_end=25)
    ue.make_box_collision(obj)                       # creates UBX_<name>_00

Settings and why (all are arguments if you disagree):
* apply_scale_options=FBX_SCALE_ALL + apply_unit_scale: Blender metres -> UE centimetres arrive 1:1 (1 BU = 100 uu)
  and objects carry scale 1, which avoids the infamous "armature at 100x / rotated -90" import.
* mesh_smooth_type=FACE: exports face smoothing + the custom normals, so hard edges survive.
* add_leaf_bones=False: no extra end bones in the UE skeleton. use_armature_deform_only=True: no control rig in UE.
* Triangulate (keep custom normals) on export: the triangulation baked into your normal map must equal the one
  the engine renders. Triangulate the LOW before baking if you want this exact.
* Textures are NOT embedded; export them from Blender/Substance and import separately.
"""
import math
import re
import sys

import bpy
import bmesh  # noqa: E402

UE_PREFIX = ("SM_", "SK_", "UCX_", "UBX_", "UCP_", "USP_", "SOCKET_")
COLLISION_PREFIX = ("UCX_", "UBX_", "UCP_", "USP_")


# --------------------------------------------------------------------------- pre-flight
def is_convex(obj, eps=1e-4):
    """True if every vertex lies on or behind every face plane. UCX_ hulls MUST be convex or UE shreds them."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    ok = True
    for f in bm.faces:
        n, p = f.normal, f.verts[0].co
        if any((v.co - p).dot(n) > eps for v in bm.verts):
            ok = False
            break
    bm.free()
    return ok


def preflight(objs, convention=True):
    """Return a list of 'ERROR: ...'/'WARN: ...' strings. Export refuses to run with ERRORs unless force=True."""
    probs = []
    for o in objs:
        if o.type not in ("MESH", "ARMATURE", "EMPTY"):
            continue
        if any(abs(s - 1) > 1e-4 for s in o.scale) and o.type == "MESH":
            probs.append(f"WARN: {o.name} has unapplied scale {tuple(round(s, 3) for s in o.scale)}")
        if any(s < 0 for s in o.scale):
            probs.append(f"ERROR: {o.name} has negative scale (flipped normals in engine)")
        if " " in o.name:
            probs.append(f"ERROR: {o.name!r} contains spaces")
        if convention and not o.name.startswith(UE_PREFIX) and not re.search(r"_LOD\d+$", o.name):
            probs.append(f"WARN: {o.name} lacks a UE prefix {UE_PREFIX}")
        if o.type == "MESH":
            if not o.data.uv_layers and not o.name.startswith(COLLISION_PREFIX):
                probs.append(f"WARN: {o.name} has no UV map")
            if o.name.startswith("UCX_") and not is_convex(o):
                probs.append(f"ERROR: {o.name} is not convex (UCX collision must be convex)")
            if not any(s.material for s in o.material_slots) and not o.name.startswith(COLLISION_PREFIX):
                probs.append(f"WARN: {o.name} has no material")
            for s in o.material_slots:
                if s.material and re.search(r"\.\d{3}$", s.material.name):
                    probs.append(f"WARN: material {s.material.name!r} looks duplicated (.001)")
    us = bpy.context.scene.unit_settings
    if abs(us.scale_length - 1.0) > 1e-6:
        probs.append(f"WARN: scene unit scale is {us.scale_length} (expected 1.0 with metres; UE scale may be off)")
    return probs


def make_box_collision(obj, index=0):
    """UBX_<name>_NN: axis-aligned box collision covering `obj`'s bounding box (wire display)."""
    bpy.context.view_layer.update()          # matrix_world of freshly created/moved objects is stale until updated
    corners = [obj.matrix_world @ __import__("mathutils").Vector(c) for c in obj.bound_box]
    mn = [min(c[i] for c in corners) for i in range(3)]
    mx = [max(c[i] for c in corners) for i in range(3)]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=[mx[i] - mn[i] for i in range(3)], verts=bm.verts)
    me = bpy.data.meshes.new(f"UBX_{obj.name}_{index:02d}")
    bm.to_mesh(me)
    bm.free()
    box = bpy.data.objects.new(me.name, me)
    box.location = [(mx[i] + mn[i]) / 2 for i in range(3)]
    box.display_type = "WIRE"
    (obj.users_collection[0] if obj.users_collection else bpy.context.scene.collection).objects.link(box)
    return box


# --------------------------------------------------------------------------- core exporter
def _select(objs):
    vl = bpy.context.view_layer
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in vl.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = objs[0]


def _fbx(filepath, **over):
    kw = dict(
        filepath=filepath, use_selection=True, global_scale=1.0, apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL", use_space_transform=True, bake_space_transform=False,
        object_types={"MESH", "ARMATURE", "EMPTY"}, use_mesh_modifiers=True, mesh_smooth_type="FACE",
        use_tspace=False, use_triangles=False, add_leaf_bones=False, use_armature_deform_only=True,
        primary_bone_axis="Y", secondary_bone_axis="X", bake_anim=False, path_mode="AUTO", embed_textures=False,
        axis_forward="-Z", axis_up="Y",
    )
    kw.update(over)
    return bpy.ops.export_scene.fbx(**kw)


def _with_triangulate(objs, fn):
    added = []
    try:
        for o in objs:
            if o.type == "MESH" and not o.name.startswith(COLLISION_PREFIX):
                m = o.modifiers.new("_UE_TRI", "TRIANGULATE")
                m.quad_method, m.ngon_method, m.keep_custom_normals = "BEAUTY", "BEAUTY", True
                added.append((o, m))
        return fn()
    finally:
        for o, m in added:
            o.modifiers.remove(m)


def export_static(objs, filepath, triangulate=True, force=False, **fbx_over):
    """Static mesh(es) + collision + sockets in one FBX. Include UCX_/UBX_ shapes and SOCKET_ empties in `objs`."""
    probs = preflight(objs)
    for p in probs:
        print(p)
    if any(p.startswith("ERROR") for p in probs) and not force:
        raise RuntimeError("pre-flight errors; fix them or pass force=True")
    _select(objs)
    go = lambda: _fbx(filepath, **fbx_over)  # noqa: E731
    return _with_triangulate(objs, go) if triangulate else go()


def export_skeletal(armature, meshes, filepath, force=False, **fbx_over):
    """Skeletal mesh: armature + skinned meshes. Rest pose must be a clean A/T pose, scale applied, armature at origin."""
    objs = [armature, *meshes]
    probs = preflight(objs)
    if any(abs(c) > 1e-5 for c in armature.location):
        probs.append("WARN: armature origin is not at world origin")
    for p in probs:
        print(p)
    if any(p.startswith("ERROR") for p in probs) and not force:
        raise RuntimeError("pre-flight errors; fix them or pass force=True")
    _select(objs)
    return _fbx(filepath, object_types={"ARMATURE", "MESH"}, bake_anim=False, **fbx_over)


def export_animation(armature, filepath, frame_start=None, frame_end=None, step=1.0, simplify=0.0, **fbx_over):
    """Animation-only FBX: armature (no meshes) baked over a frame range. Use the same armature/rest pose as the mesh.

    Name the file/action A_<Character>_<Anim>; in UE import it as Animation and pick the character's Skeleton."""
    sc = bpy.context.scene
    if frame_start is not None:
        sc.frame_start = int(frame_start)
    if frame_end is not None:
        sc.frame_end = int(frame_end)
    _select([armature])
    return _fbx(filepath, object_types={"ARMATURE"}, bake_anim=True, bake_anim_use_all_actions=False,
                bake_anim_use_nla_strips=False, bake_anim_use_all_bones=True, bake_anim_step=step,
                bake_anim_simplify_factor=simplify, bake_anim_force_startend_keying=True, **fbx_over)


# --------------------------------------------------------------------------- CLI
def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def _opt(a, flag, default=None):
    return a[a.index(flag) + 1] if flag in a else default


if __name__ == "__main__":
    import os
    a = _args()
    out = _opt(a, "--out")
    if not out:
        print(__doc__)
        sys.exit(2)
    os.makedirs(out, exist_ok=True)
    if "--collection" in a:
        coll = bpy.data.collections[_opt(a, "--collection")]
        objs = [o for o in coll.all_objects]
        name = coll.name
    else:
        objs = list(bpy.context.selected_objects)
        name = objs[0].name if objs else "export"
    if "--skeletal" in a:
        arm = next(o for o in objs if o.type == "ARMATURE")
        export_skeletal(arm, [o for o in objs if o.type == "MESH"], os.path.join(out, f"{name}.fbx"))
    else:
        export_static(objs, os.path.join(out, f"{name}.fbx"), triangulate="--no-triangulate" not in a)
    print("exported ->", os.path.join(out, f"{name}.fbx"))
