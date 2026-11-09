"""Hard-surface kit: non-destructive boolean cuts -> bevel -> weighted normals.

Works with the `bpy` pip module and with `blender -b -P`. Verified on Blender 5.2 LTS.
Data-API/bmesh only (no context-dependent bpy.ops), so it runs headless without a UI.

Library use (inside Blender, or `import` after adding this folder to sys.path):
    import hardsurface as hs
    base = hs.add_box("Panel", (1.2, 0.8, 0.1))
    cut  = hs.make_cutter("Cut_Slot", "BOX", (0.5, 0.1, 0.2), location=(0.2, 0, 0.05))
    hs.boolean(base, cut, "DIFFERENCE")
    hs.bevel_stack(base, width=0.006, segments=3)
    hs.apply_modifiers(base)            # only when you need real geometry (export, bake)

CLI demo (builds a sample panel, applies, prints a QA summary, optionally saves .blend):
    blender -b -P hardsurface.py -- --demo [--out demo.blend] [--apply]
    python hardsurface.py --demo --apply            # with the bpy pip module

Why this shape: boolean + bevel + weighted normals is the non-destructive stack that the
Hard Ops / Boxcutter workflow automates. Keeping cutters as live, wire-display objects means
the design stays editable until the very last step.
"""
import math
import sys

import bpy  # must come before bmesh: with the pip module, importing bpy puts bmesh on sys.path
import bmesh  # noqa: E402


# --------------------------------------------------------------------------- scene
def clear_scene():
    """Remove every object and orphan datablock so repeated runs are reproducible."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.images):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def set_metric_units(scale=1.0):
    """1 Blender unit = 1 m. Keep scale 1.0 for game/film assets; many tools assume it."""
    us = bpy.context.scene.unit_settings
    us.system, us.scale_length, us.length_unit = "METRIC", scale, "METERS"


# --------------------------------------------------------------------------- primitives
def _link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def add_box(name, size=(1.0, 1.0, 1.0), location=(0, 0, 0), collection=None):
    """Axis-aligned box with real dimensions `size` (metres), via bmesh (no ops)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    return _link(obj, collection)


def make_cutter(name, kind="BOX", size=(0.2, 0.2, 0.2), location=(0, 0, 0),
                rotation=(0, 0, 0), segments=32, collection=None):
    """Create a boolean cutter: wire display, hidden from render, not selectable by accident.

    kind: 'BOX' | 'CYLINDER' (size = (diameter_x, diameter_y, depth)).
    Make the cutter longer than the target in the cut direction so faces never end up
    coplanar with the target (coplanar faces are the #1 cause of boolean artefacts).
    """
    bm = bmesh.new()
    if kind == "BOX":
        bmesh.ops.create_cube(bm, size=1.0)
    elif kind == "CYLINDER":
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                              radius1=0.5, radius2=0.5, depth=1.0)
    else:
        raise ValueError(f"unknown cutter kind {kind!r}")
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location, obj.rotation_euler = location, rotation
    obj.display_type = "WIRE"
    obj.hide_render = True
    obj.visible_shadow = False
    return _link(obj, collection)


# --------------------------------------------------------------------------- modifiers
def _solver_for(requested):
    """Map solver names across versions: FAST (<=4.1) -> FLOAT (4.2+); MANIFOLD exists in 4.5+."""
    available = {e.identifier for e in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items}
    if requested in available:
        return requested
    if requested == "FLOAT" and "FAST" in available:
        return "FAST"
    if requested == "FAST" and "FLOAT" in available:
        return "FLOAT"
    return "EXACT"


def boolean(target, cutter, operation="DIFFERENCE", solver="EXACT", name=None, use_self=False):
    """Add a Boolean modifier to `target` using object `cutter`.

    EXACT: robust, handles overlapping/self-intersecting input, slower.
    MANIFOLD (4.5+): faster, needs closed manifold operands.
    FLOAT: fastest, fine for simple cuts, can leave artefacts on coplanar faces.
    """
    mod = target.modifiers.new(name or f"Bool_{cutter.name}", "BOOLEAN")
    mod.operation = operation
    mod.operand_type = "OBJECT"
    mod.object = cutter
    mod.solver = _solver_for(solver)
    if mod.solver == "EXACT":
        mod.use_self = use_self
    return mod


def mark_sharp_by_angle(obj, angle_deg=30.0, bevel_weight=True):
    """Shade smooth, then mark edges sharper than `angle_deg` as sharp (+ optional bevel weight).

    Replaces the pre-4.1 'Auto Smooth' checkbox (removed in Blender 4.1). Sharp edges are the
    signal that both Weighted Normal and Bevel(limit=WEIGHT) read.
    """
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    thr = math.radians(angle_deg)
    for f in bm.faces:
        f.smooth = True
    n_sharp = 0
    for e in bm.edges:
        ang = e.calc_face_angle(None)
        if ang is not None and ang > thr:
            e.smooth = False  # smooth=False == sharp
            n_sharp += 1
    bm.to_mesh(mesh)
    bm.free()
    if bevel_weight:
        attr = mesh.attributes.get("bevel_weight_edge") or mesh.attributes.new(
            "bevel_weight_edge", "FLOAT", "EDGE")
        sharp = mesh.attributes.get("sharp_edge")
        for i, a in enumerate(attr.data):
            a.value = 1.0 if (sharp is not None and sharp.data[i].value) else 0.0
    mesh.update()
    return n_sharp


def bevel_stack(obj, width=0.005, segments=3, angle_deg=30.0, profile=0.5,
                harden_normals=False, weighted_normals=True, limit="ANGLE"):
    """Bevel (+ Weighted Normal) on top of whatever is already in the stack.

    width    : metres. Rule of thumb - 0.5-2 mm for fine panel lines, 3-10 mm for visible chamfers.
    segments : 1 = chamfer (game, cheap); 2-3 = standard hero edge; 4+ only for close-ups.
    limit    : 'ANGLE' (no prep needed) or 'WEIGHT' (art-directed; uses the bevel_weight_edge attribute).
    Weighted Normal needs smooth shading + sharp edges to be meaningful -> call mark_sharp_by_angle
    first on the *final* mesh, or use limit='ANGLE' and rely on the modifier to read face weights.
    """
    bev = obj.modifiers.new("Bevel", "BEVEL")
    bev.width, bev.segments, bev.profile = width, segments, profile
    bev.limit_method = limit
    if limit == "ANGLE":
        bev.angle_limit = math.radians(angle_deg)
    bev.harden_normals = harden_normals
    bev.miter_outer = "MITER_ARC"
    bev.use_clamp_overlap = True
    wn = None
    if weighted_normals:
        wn = obj.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        wn.mode, wn.weight, wn.keep_sharp = "FACE_AREA", 50, True
        wn.use_face_influence = False
    return bev, wn


# --------------------------------------------------------------------------- apply / stats
def apply_modifiers(obj, only=None):
    """Bake the modifier stack into real geometry without bpy.ops (works headless, any context).

    `only`: optional iterable of modifier names; others are kept (they must come *after* the
    applied ones in the stack, or results change). Shape keys are not preserved.
    """
    dg = bpy.context.evaluated_depsgraph_get()
    if only is None:
        eval_obj = obj.evaluated_get(dg)
        new = bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True, depsgraph=dg)
        old = obj.data
        obj.modifiers.clear()
        obj.data = new
        new.name = old.name
        if new.materials and all(m is None for m in new.materials):
            new.materials.clear()      # Boolean leaves a phantom empty slot when the cutter has no material
        if old.users == 0:
            bpy.data.meshes.remove(old)
        return new
    names = set(only)
    saved = [(m.name, m.show_viewport) for m in obj.modifiers if m.name not in names]
    for m in obj.modifiers:
        if m.name not in names:
            m.show_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    for m in list(obj.modifiers):
        if m.name in names:
            obj.modifiers.remove(m)
    obj.data = new
    new.name = old.name
    for name, vis in saved:
        obj.modifiers[name].show_viewport = vis
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return new


def mesh_stats(obj):
    """Quick topology summary: verts, tris, quads, ngons, non-manifold edges, loose verts."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tris = sum(1 for f in bm.faces if len(f.verts) == 3)
    quads = sum(1 for f in bm.faces if len(f.verts) == 4)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    tri_equiv = sum(len(f.verts) - 2 for f in bm.faces)
    out = dict(verts=len(bm.verts), faces=len(bm.faces), tris=tris, quads=quads, ngons=ngons,
               non_manifold_edges=nonman, loose_verts=loose, triangles_after_triangulation=tri_equiv)
    bm.free()
    return out


# --------------------------------------------------------------------------- demo
def build_demo(apply=False):
    clear_scene()
    set_metric_units()
    base = add_box("HS_Panel", (1.2, 0.8, 0.1))
    slot = make_cutter("Cut_Slot", "BOX", (0.5, 0.08, 0.3), location=(0.15, 0.2, 0.0))
    hole = make_cutter("Cut_Holes", "CYLINDER", (0.08, 0.08, 0.3), location=(-0.45, -0.2, 0.0), segments=24)
    arr = hole.modifiers.new("Array", "ARRAY")           # live array on the cutter: 4 holes
    arr.count, arr.use_relative_offset, arr.use_constant_offset = 4, False, True
    arr.constant_offset_displace = (0.12, 0.0, 0.0)
    boolean(base, slot, "DIFFERENCE")
    boolean(base, hole, "DIFFERENCE")
    bevel_stack(base, width=0.004, segments=3, angle_deg=30)
    if apply:
        apply_modifiers(base)
        mark_sharp_by_angle(base, 30)
    return base


def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


if __name__ == "__main__":
    args = _args()
    if "--demo" in args:
        obj = build_demo(apply="--apply" in args)
        if "--apply" in args:
            print("stats:", mesh_stats(obj))
        else:
            print("modifier stack:", [m.name for m in obj.modifiers])
        if "--out" in args:
            path = args[args.index("--out") + 1]
            bpy.ops.wm.save_as_mainfile(filepath=path)
            print("saved", path)
    else:
        print(__doc__)
