"""Reference images + proportion guides for character / prop modelling. Verified on Blender 5.2 LTS.

    import reference_setup as rs
    rs.add_reference("/path/front.png", view="FRONT", height_m=1.8, opacity=0.5)   # also SIDE, BACK, TOP
    rs.add_reference("/path/side.png",  view="SIDE",  height_m=1.8)
    rs.proportion_guide(height_m=1.8, heads=8)           # horizontal lines at every 1/8 of the figure height

Why image empties: they are not renderable, do not pollute exports, can be scaled/aligned to real dimensions and
dimmed - the standard way to model against orthographic references. Align ALL views to the same real-world height
(feet at Z=0), otherwise front and side drift apart and the model ends up distorted.

Rule-of-thumb canon (idealised adult, 8 heads): chin 7/8, nipples ~6/8, navel ~5/8, crotch ~4/8, knee ~2/8 (a bit above),
feet 0. Heroic figures stretch to 8-9 heads, average people are ~7-7.5, stylised characters 3-6 heads, chibi 2-3.
Use it to catch errors, not as law: real bodies vary and stylisation deliberately breaks it.
"""
import math
import os
import sys

import bpy
import bmesh  # noqa: E402

VIEWS = {
    # rotation of the image plane so it faces the camera that looks at it; images lie in a vertical plane
    "FRONT": ((math.pi / 2, 0, 0), (0, 1.5, 0)),                 # seen from -Y, plane behind the model (+Y)
    "BACK": ((math.pi / 2, 0, math.pi), (0, -1.5, 0)),
    "SIDE": ((math.pi / 2, 0, math.pi / 2), (-1.5, 0, 0)),       # right view: camera on +X, image right = +Y
    "TOP": ((0, 0, 0), (0, 0, -0.5)),
}


def add_reference(path, view="FRONT", height_m=1.8, opacity=0.5, name=None, depth_offset=None, bottom_z=0.0,
                  image_height_fraction=1.0):
    """Add an orthographic reference as an image empty.

    height_m: real height the *image* represents. If the subject only fills part of the image, pass
    image_height_fraction (e.g. 0.9 when the figure is 90 % of the image height) so the figure - not the picture -
    ends up `height_m` tall.
    bottom_z: Z of the image's bottom edge (0 = feet on the ground). Returns the empty.
    """
    view = view.upper()
    rot, off = VIEWS[view]
    img = bpy.data.images.load(os.path.abspath(path), check_existing=True)
    w, h = img.size
    img_h = height_m / image_height_fraction            # world height of the whole image
    emp = bpy.data.objects.new(name or f"REF_{view}", None)
    emp.empty_display_type = "IMAGE"
    emp.data = img
    emp.empty_display_size = img_h                      # size = image height (for non-square images the longer side)
    if w > h:                                           # display size applies to the longer side
        emp.empty_display_size = img_h * (w / h)
    emp.use_empty_image_alpha = True
    emp.color[3] = opacity
    emp.empty_image_depth = "BACK"                     # draw behind the mesh, not through it
    emp.show_empty_image_only_axis_aligned = True      # hide when viewed from the side (clutter-free)
    emp.rotation_euler = rot
    emp.location = off
    if depth_offset is not None:
        emp.location = [o if o == 0 else math.copysign(abs(depth_offset), o) for o in off]
    # empty origin is the image centre by default: lift so the bottom edge sits at bottom_z
    if view != "TOP":
        emp.location.z = bottom_z + img_h / 2
    emp.hide_render = True
    emp.show_in_front = False
    bpy.context.scene.collection.objects.link(emp)
    return emp


def proportion_guide(height_m=1.8, heads=8, width_m=None, name="GUIDE_Proportions", axis="Y"):
    """Wire object with a horizontal line at every 1/heads of `height_m` (and a vertical centre line).

    Lines lie in the XZ plane at Y=0 so they show up in front view; they are edges only (not renderable)."""
    width = width_m or height_m / 3.0
    bm = bmesh.new()
    verts = []
    for i in range(heads + 1):
        z = height_m * i / heads
        verts.append((bm.verts.new((-width / 2, 0, z)), bm.verts.new((width / 2, 0, z))))
    for a, b in verts:
        bm.edges.new((a, b))
    top = bm.verts.new((0, 0, height_m))
    bot = bm.verts.new((0, 0, 0))
    bm.edges.new((top, bot))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.display_type = "WIRE"
    obj.hide_render = True
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


if __name__ == "__main__":
    print(__doc__)
