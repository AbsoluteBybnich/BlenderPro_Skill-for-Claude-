"""UV + retopology helpers that work headless. Verified on Blender 5.2 LTS.

    import uv_retopo as ur
    ur.unwrap(obj, method="ANGLE_BASED", margin_px=8, tex_size=2048, seams="sharp")
    print(ur.texel_density(obj, 2048))                 # pixels per metre
    ur.set_texel_density(obj, target_px_per_m=1024, tex_size=2048)
    low = ur.quad_remesh(high, target_faces=3000)       # auto-retopo draft (Quadriflow)
    ur.shrinkwrap_for_manual_retopo(low, high)          # hand retopo / snap-to-surface setup

Why the explicit `activate()`: edit-mode operators (bpy.ops.mesh/uv) poll on the *view layer's* active
object, not on a temp_override. Without it you get "poll() failed, context is incorrect" in headless runs.
"""
import math
import sys

import bpy
import bmesh  # noqa: E402


# --------------------------------------------------------------------------- context
def activate(obj):
    """Make `obj` the only selected + active object (what edit-mode operators need)."""
    vl = bpy.context.view_layer
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = obj
    obj.select_set(True)
    return obj


def margin_fraction(px, tex_size):
    """UV margin as a fraction of 0-1 space for a given pixel gutter. Rule of thumb: 4 px @1k,
    8 px @2k, 16 px @4k - enough for mip-maps and the bake 'margin' dilation to stay inside the island."""
    return px / float(tex_size)


# --------------------------------------------------------------------------- seams / unwrap
def seams_from_sharp(obj, clear_existing=False):
    """Hard-surface shortcut: every sharp edge becomes a UV seam (hard edge == material/shading break)."""
    activate(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    n = 0
    for e in bm.edges:
        if clear_existing:
            e.seam = False
        if not e.smooth:
            e.seam = True
            n += 1
    bm.to_mesh(obj.data)
    bm.free()
    return n


def unwrap(obj, method="ANGLE_BASED", margin_px=8, tex_size=2048, seams="keep", pack=True,
           smart_angle_deg=66.0, pack_shape="CONCAVE", pack_rotate=False):
    """Unwrap + average island scale + pack.

    seams: 'keep'    - use the seams already on the mesh (organic: mark them yourself first)
           'sharp'   - promote sharp edges to seams first (hard-surface)
           'smart'   - Smart UV Project (angle based, ignores seams; quick props / lightmaps)
    method: ANGLE_BASED (default, good all-round), CONFORMAL (organic, low distortion), MINIMUM_STRETCH.
    pack_shape / pack_rotate: island fitting. Defaults (CONCAVE, no rotation) pack tightly in well under a second.
    WARNING (measured on Blender 5.2): rotation with CONCAVE or CONVEX shapes on beveled meshes took minutes even
    for ~100 faces. If you need rotation use pack_shape="AABB" (instant, looser) or rotate by hand / UVPackmaster.
    """
    activate(obj)
    margin = margin_fraction(margin_px, tex_size)
    if seams == "sharp":
        seams_from_sharp(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    if seams == "smart":
        bpy.ops.uv.smart_project(angle_limit=math.radians(smart_angle_deg), margin_method="FRACTION",
                                 island_margin=margin)
    else:
        bpy.ops.uv.unwrap(method=method, margin_method="FRACTION", margin=margin)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()          # same texel density on every island
    if pack:
        bpy.ops.uv.pack_islands(margin_method="FRACTION", margin=margin, rotate=pack_rotate, shape_method=pack_shape)
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


# --------------------------------------------------------------------------- texel density
def _areas(obj):
    bpy.context.view_layer.update()              # make sure matrix_world (scale) is current
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)               # world-space area -> honours unapplied scale
    uv = bm.loops.layers.uv.active
    if uv is None:
        bm.free()
        raise ValueError(f"{obj.name} has no UV map")
    a3 = a2 = 0.0
    for f in bm.faces:
        a3 += f.calc_area()
        pts = [l[uv].uv for l in f.loops]
        s = 0.0
        for i in range(len(pts)):
            s += pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
        a2 += abs(s) * 0.5
    bm.free()
    return a3, a2


def texel_density(obj, tex_size=2048):
    """Average texel density in pixels per metre (square texture of `tex_size`)."""
    a3, a2 = _areas(obj)
    return math.sqrt(a2 / a3) * tex_size if a3 > 0 and a2 > 0 else 0.0


def set_texel_density(obj, target_px_per_m, tex_size=2048):
    """Uniformly scale all UVs (about their centre) to hit a texel density.

    Returns (new_density, fits_in_0_1). If it does not fit, lower the target or add a texture set -
    never squeeze different assets to different densities in the same scene (it reads as mismatched detail).
    Reference densities (rules of thumb): 512 px/m background, 1024 px/m props & environment,
    2048 px/m hero props, characters 1024-2048 px/m on the face/hands.
    """
    cur = texel_density(obj, tex_size)
    if cur <= 0:
        raise ValueError("cannot compute current texel density")
    k = target_px_per_m / cur
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.active
    us = [l[uv].uv.x for f in bm.faces for l in f.loops]
    vs = [l[uv].uv.y for f in bm.faces for l in f.loops]
    cx, cy = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
    for f in bm.faces:
        for l in f.loops:
            p = l[uv].uv
            p.x, p.y = cx + (p.x - cx) * k, cy + (p.y - cy) * k
    us = [l[uv].uv.x for f in bm.faces for l in f.loops]
    vs = [l[uv].uv.y for f in bm.faces for l in f.loops]
    fits = min(us) >= -1e-6 and max(us) <= 1 + 1e-6 and min(vs) >= -1e-6 and max(vs) <= 1 + 1e-6
    bm.to_mesh(obj.data)
    bm.free()
    return texel_density(obj, tex_size), fits


# --------------------------------------------------------------------------- retopology
def quad_remesh(high, target_faces=3000, preserve_sharp=True, symmetry=False, name=None):
    """Auto-retopo draft with Quadriflow on a *duplicate*; the original is untouched.

    Good for: quick LODs-from-sculpt, bases for further manual cleanup, blockouts.
    Not good for: hero characters (edge loops will not follow muscles/facial flow). Do those by hand
    (shrinkwrap_for_manual_retopo) or with guide curves in Quadriflow/ZRemesher.
    """
    dup = high.copy()
    dup.data = high.data.copy()
    dup.name = name or f"{high.name}_low"
    dup.modifiers.clear()
    (high.users_collection[0] if high.users_collection else bpy.context.scene.collection).objects.link(dup)
    activate(dup)
    bpy.ops.object.quadriflow_remesh(mode="FACES", target_faces=target_faces,
                                     use_preserve_sharp=preserve_sharp, use_mesh_symmetry=symmetry)
    return dup


def decimate(obj, ratio=0.5, apply=True):
    """Collapse decimate (triangulates). For LOD chains: LOD1 ~50 %, LOD2 ~25 %, LOD3 ~10-12 %."""
    mod = obj.modifiers.new("Decimate", "DECIMATE")
    mod.ratio = ratio
    if apply:
        activate(obj)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return mod


def shrinkwrap_for_manual_retopo(low, high, offset=0.0005):
    """Set up the standard manual-retopo rig: low-poly sticks to the high-poly surface.

    Adds a Shrinkwrap(project nearest surface) modifier visible in edit mode, enables face snapping,
    and shows the low mesh as wire/X-ray so you can see the sculpt underneath.
    """
    mod = low.modifiers.new("Retopo_Shrinkwrap", "SHRINKWRAP")
    mod.target, mod.wrap_method, mod.offset = high, "NEAREST_SURFACEPOINT", offset
    mod.show_in_editmode = mod.show_on_cage = True
    low.show_in_front = True
    low.display_type = "WIRE"
    ts = bpy.context.scene.tool_settings
    ts.use_snap = True
    try:  # 4.x/5.x naming
        ts.snap_elements_base = {"FACE_PROJECT"}
    except Exception:
        try:
            ts.snap_elements = {"FACE_PROJECT"}
        except Exception:
            pass
    return mod


def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


if __name__ == "__main__":
    print(__doc__)
