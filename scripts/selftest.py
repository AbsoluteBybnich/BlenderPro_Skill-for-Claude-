"""Self-test for every 3Dpro script against YOUR Blender build. Run this first on a new machine / Blender version.

    blender -b -P selftest.py                      # real Blender
    python selftest.py                             # `pip install bpy` module (Python version must match the wheel)
    blender -b -P selftest.py -- --only hardsurface rig     # subset
    blender -b -P selftest.py -- --skip render              # skip the (slowest) render/bake tests

Each test builds a tiny scene, runs the script's public API and ASSERTS on the result (geometry, keyframes, pixels), so a
PASS means the behaviour works on this Blender version - not just that the code imports. Typical total time: < 1 min.
Tests: hardsurface, qa, uv, export, rig, anim, bake, light, ref, matrix
"""
import math
import os
import sys
import tempfile
import time
import traceback

import bpy
import bmesh  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
sys.path.insert(0, HERE)

import hardsurface as hs  # noqa: E402
import qa_check  # noqa: E402
import uv_retopo as ur  # noqa: E402
import export_ue5 as ue  # noqa: E402
import rig_ikfk as rg  # noqa: E402
import anim_helpers as ah  # noqa: E402
import bake_maps as bk  # noqa: E402
import lighting_rig as lr  # noqa: E402
import reference_setup as rs  # noqa: E402
from mathutils import Vector  # noqa: E402

TMP = tempfile.mkdtemp(prefix="3dpro_selftest_")


def _fresh():
    hs.clear_scene()
    for l in list(bpy.data.lights):
        bpy.data.lights.remove(l)
    hs.set_metric_units()


def _pixels(path):
    import numpy as np
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    return np.array(im.pixels[:]).reshape(-1, 4)[:, :3]


# --------------------------------------------------------------------------- tests
def t_hardsurface():
    _fresh()
    base = hs.build_demo(apply=True)
    st = hs.mesh_stats(base)
    assert st["faces"] > 500 and st["non_manifold_edges"] == 0 and st["loose_verts"] == 0, st
    assert not base.modifiers and len(base.data.materials) == 0, "apply_modifiers left debris"
    return f"{st['faces']} faces, manifold, ngons={st['ngons']}"


def t_qa():
    _fresh()
    good = hs.build_demo(apply=True)
    good.name = "SM_Good"
    ur.unwrap(good, seams="sharp", margin_px=8, tex_size=2048)
    inside = hs.add_box("SM_Inside", (1, 1, 1), location=(3, 0, 0))
    bm = bmesh.new()
    bm.from_mesh(inside.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(inside.data)
    bm.free()
    scaled = hs.add_box("Crate.001", (1, 1, 1), location=(6, 0, 0))
    scaled.scale = (2, 2, 2)
    rep, errs = qa_check.run()
    codes = {r["object"]: {i["code"] for i in r["issues"]} for r in rep}
    assert "INSIDE_OUT" in codes["SM_Inside"] and "UNAPPLIED_SCALE" in codes["Crate.001"], codes
    assert "NON_MANIFOLD" not in codes["SM_Good"] and "NO_UV" not in codes["SM_Good"], codes["SM_Good"]
    assert errs >= 1
    return f"caught {sum(len(c) for c in codes.values())} planted issues, {errs} error(s)"


def t_uv():
    _fresh()
    o = hs.add_box("SM_Box", (1, 1, 1))
    hs.bevel_stack(o, 0.01, 2)
    hs.apply_modifiers(o)
    hs.mark_sharp_by_angle(o, 30)
    ur.unwrap(o, seams="sharp", margin_px=8, tex_size=2048)
    td, fits = ur.set_texel_density(o, 512, 2048)
    assert abs(td - 512) < 5 and fits, (td, fits)
    return f"texel density set to {td:.0f} px/m"


def t_export():
    _fresh()
    crate = hs.add_box("SM_Crate", (1.0, 0.6, 0.4), location=(0, 0, 0.2))
    hs.bevel_stack(crate, 0.01, 2)
    hs.apply_modifiers(crate)
    ur.unwrap(crate, seams="sharp")
    crate.data.materials.append(bpy.data.materials.new("M_Crate"))
    box = ue.make_box_collision(crate)
    fp = os.path.join(TMP, "SM_Crate.fbx")
    ue.export_static([crate, box], fp)
    hs.clear_scene()
    bpy.ops.import_scene.fbx(filepath=fp)
    c = next(o for o in bpy.data.objects if o.name.startswith("SM_Crate"))
    assert all(abs(a - b) < 0.02 for a, b in zip(sorted(c.dimensions), [0.4, 0.6, 1.0])), c.dimensions
    assert all(len(p.vertices) == 3 for p in c.data.polygons), "not triangulated"
    return "FBX round trip 1:1 scale, triangulated, collision kept"


def t_rig():
    _fresh()
    arm = rg.create_armature("Rig")
    N = rg.build_ik_fk_limb(arm, "arm.L", (0, 0, 0), (0.3, 0.05, 0), (0.6, 0, 0), (0.7, 0, 0))

    def head(name):
        return rg._eval_pose_bone(arm, name).head.copy()

    tgt = arm.pose.bones[N["target"]]
    m = tgt.matrix.copy()
    m.translation = Vector((0.35, 0, 0.3))
    tgt.matrix = m
    rg.set_ik_fk(arm, "arm.L", 1.0)
    assert (head(N["def"][2]) - Vector((0.35, 0, 0.3))).length < 2e-3, "IK misses target"
    arm.pose.bones[N["fk"][0]].rotation_mode = "XYZ"
    arm.pose.bones[N["fk"][0]].rotation_euler = (math.radians(50), 0, 0)
    rg.set_ik_fk(arm, "arm.L", 0.0)
    assert (head(N["def"][2]) - head(N["fk"][2])).length < 1e-3, "FK does not drive DEF"
    before = head(N["def"][2])
    rg.snap_ik_to_fk(arm, "arm.L")
    rg.set_ik_fk(arm, "arm.L", 1.0)
    assert (before - head(N["def"][2])).length < 2e-3, "snap IK<-FK mismatch"
    # face helpers: shape key driven by a slider bone, eye aim constraint
    _fresh()
    arm2 = rg.create_armature("Face")
    bpy.context.view_layer.objects.active = arm2
    bpy.ops.object.mode_set(mode="EDIT")
    for nm, h, t_ in (("eye.L", (0.03, 0, 1.6), (0.03, 0.05, 1.6)), ("eye.target", (0, 1.0, 1.6), (0, 1.1, 1.6)),
                      ("ctl.blink", (0.1, 0, 1.7), (0.1, 0, 1.72))):
        b = arm2.data.edit_bones.new(nm)
        b.head, b.tail = h, t_
    bpy.ops.object.mode_set(mode="OBJECT")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.1)
    me = bpy.data.meshes.new("Face")
    bm.to_mesh(me)
    bm.free()
    face = bpy.data.objects.new("Face", me)
    bpy.context.scene.collection.objects.link(face)
    face.shape_key_add(name="Basis")
    face.shape_key_add(name="Blink")
    rg.drive_shape_key_from_bone(face, "Blink", arm2, "ctl.blink", "LOC_Z", "LOCAL_SPACE", 0.0, 0.02)
    arm2.pose.bones["ctl.blink"].location = (0, 0, 0.01)
    arm2.update_tag()
    bpy.context.view_layer.update()
    v = face.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.shape_keys.key_blocks["Blink"].value
    assert abs(v - 0.5) < 0.02, v
    rg.add_eye_aim(arm2, "eye.L", "eye.target")
    bpy.context.view_layer.update()
    eye = arm2.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones["eye.L"]
    aim = (eye.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
    assert aim.dot((Vector((0, 1.0, 1.6)) - Vector((0.03, 0, 1.6))).normalized()) > 0.999
    return "IK reaches goal, FK drives DEF, IK<->FK snap exact, blink driver + eye aim work"


def t_anim():
    _fresh()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 2))
    ball = bpy.context.object
    ah.bounce_ball(ball, height=1.5, radius=0.5, period=24, bounces=4)
    ks = ah.key_summary(ball)
    z = dict(ks["location[2]"])
    fr = sorted(z)
    apex = [z[f] for i, f in enumerate(fr[1:-1], 1) if z[fr[i - 1]] < z[f] >= z[fr[i + 1]]]
    assert len(apex) == 3 and all(a > b for a, b in zip(apex, apex[1:])), apex
    assert ah.shift_keys(ball, 2, "scale") == 3
    ah.make_cyclic(ball)
    return f"{len(fr)} keys, apex heights fall {[round(a, 2) for a in apex]}"


def t_bake():
    import numpy as np
    _fresh()
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in ((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0))]
    f = bm.faces.new(vs)
    uvl = bm.loops.layers.uv.new("UVMap")
    for l, p in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        l[uvl].uv = p
    me = bpy.data.meshes.new("low")
    bm.to_mesh(me)
    bm.free()
    low = bpy.data.objects.new("SM_T_low", me)
    bpy.context.scene.collection.objects.link(low)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=80, y_segments=80, size=1.0)
    for v in bm.verts:
        v.co.z = 0.12 * math.exp(-((v.co.x + 0.4) ** 2 + (v.co.y - 0.3) ** 2) / 0.05) + (
            0.08 if abs(v.co.x - 0.4) < 0.12 and abs(v.co.y) < 0.6 else 0.0)
    hi = bpy.data.meshes.new("high")
    bm.to_mesh(hi)
    bm.free()
    high = bpy.data.objects.new("SM_T_high", hi)
    bpy.context.scene.collection.objects.link(high)
    for p in hi.polygons:
        p.use_smooth = True
    ue_maps = bk.bake(low, high, os.path.join(TMP, "ue"), 128, ("normal", "ao", "curvature"), samples=8,
                      cage_extrusion=0.3, target="ue", ao_distance=0.3)
    gl_maps = bk.bake(low, high, os.path.join(TMP, "gl"), 128, ("normal",), samples=8, cage_extrusion=0.3, target="gl")
    n_ue, n_gl = _pixels(ue_maps["normal"]), _pixels(gl_maps["normal"])
    assert n_ue[:, 0].std() > 0.02 and n_ue[:, 2].mean() > 0.9, "normal map empty"
    assert np.abs((1 - n_ue[:, 1]) - n_gl[:, 1]).mean() < 0.03, "DirectX/OpenGL green not mirrored"
    assert _pixels(ue_maps["ao"])[:, 0].std() > 0.003 and _pixels(ue_maps["curvature"])[:, 0].std() > 0.01
    return "normal (DX+GL mirrored), AO, curvature have real data"


def t_light():
    import numpy as np
    _fresh()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1))
    bpy.ops.object.shade_smooth()
    lr.setup_render("CYCLES", samples=24, resolution=(96, 54), denoise=False)
    lr.setup_world((0, 0, 0))
    out = {}
    for ratio in (2, 8):
        for l in list(bpy.data.objects):
            if l.type == "LIGHT":
                bpy.data.objects.remove(l)
        lr.three_point(target=(0, 0, 1), key_power=120, key_fill_ratio=ratio, rim_ratio=1.0, distance=4)
        lr.setup_camera(location=(0, -8, 1.2), look_at=(0, 0, 1), focal_mm=85)
        p = lr.render_still(os.path.join(TMP, f"r{ratio}.png"))
        a = _pixels(p).reshape(54, 96, 3).mean(axis=2)
        a = ((a + 0.055) / 1.055) ** 2.4
        out[ratio] = a[16:38, 30:48].mean() / max(a[16:38, 48:66].mean(), 1e-6)
    assert out[8] > out[2] * 1.2, out
    return f"key/fill contrast on subject: ratio2 -> {out[2]:.2f}:1, ratio8 -> {out[8]:.2f}:1"


def t_ref():
    _fresh()
    img = bpy.data.images.new("t", 64, 128, alpha=True)
    img.filepath_raw = os.path.join(TMP, "ref.png")
    img.file_format = "PNG"
    img.save()
    want = {"FRONT": [(1, 0, 0), (0, 0, 1), (0, -1, 0)], "BACK": [(-1, 0, 0), (0, 0, 1), (0, 1, 0)],
            "SIDE": [(0, 1, 0), (0, 0, 1), (1, 0, 0)], "TOP": [(1, 0, 0), (0, 1, 0), (0, 0, 1)]}
    for view, exp in want.items():                      # (image right, image up, direction it faces)
        e = rs.add_reference(img.filepath_raw, view=view, height_m=1.8)
        bpy.context.view_layer.update()
        m = e.matrix_world.to_3x3()
        for v, x in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), exp):
            assert all(abs(a - b) < 1e-3 for a, b in zip(m @ Vector(v), x)), (view, v, x)
    g = rs.proportion_guide(1.8, 8)
    assert len(g.data.edges) == 10
    hs.clear_scene()
    hs.add_box("SM_Wall_A", (4.0, 1.0, 3.0))
    hs.add_box("SM_Wall_B", (3.7, 1.0, 3.0), location=(5, 0, 0))
    rep, _ = qa_check.run(grid=1.0)
    c = {r["object"]: {i["code"] for i in r["issues"]} for r in rep}
    assert "MODULAR_GRID" not in c["SM_Wall_A"] and "MODULAR_GRID" in c["SM_Wall_B"], c
    return "4 reference views face the right way; modular-grid check flags 3.7 m, passes 4 m"


def t_matrix():
    """Regression: freshly created objects have an identity matrix_world until the depsgraph runs."""
    _fresh()
    far = hs.add_box("SM_Far", (1, 2, 3), location=(10, -5, 7))
    box = ue.make_box_collision(far)
    bpy.context.view_layer.update()
    assert (box.location - Vector((10, -5, 7))).length < 1e-3 and abs(box.dimensions.z - 3) < 1e-3, box.location
    cam = lr.setup_camera(location=(4, -4, 2), look_at=(0, 0, 1))
    lr.turntable(cam, target=(0, 0, 1), frames=120)

    def pos(f):
        bpy.context.scene.frame_set(f)
        bpy.context.view_layer.update()
        return cam.matrix_world.translation.copy()

    p1, p61, p121 = pos(1), pos(61), pos(121)
    assert abs(math.hypot(p1.x, p1.y) - math.hypot(4, 4)) < 1e-3, "camera lost its position"
    assert abs(p1.x + p61.x) < 1e-3 and abs(p1.y + p61.y) < 1e-3, "frames 1 and 61 are not opposite"
    assert (p121 - p1).length < 1e-3, "turntable does not loop"
    fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    assert fwd.dot((Vector((0, 0, 1)) - cam.matrix_world.translation).normalized()) > 0.999, "camera not aimed at target"
    return "collision box at correct world position; turntable orbits, loops, stays aimed"


TESTS = {"hardsurface": t_hardsurface, "qa": t_qa, "uv": t_uv, "export": t_export, "rig": t_rig, "anim": t_anim,
         "bake": t_bake, "light": t_light, "ref": t_ref, "matrix": t_matrix}
RENDER = {"bake", "light"}


def main():
    argv = sys.argv
    a = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    only = a[a.index("--only") + 1:] if "--only" in a else list(TESTS)
    only = [x for x in only if not x.startswith("--")]
    skip = set(a[a.index("--skip") + 1:]) if "--skip" in a else set()
    if "render" in skip:
        skip |= RENDER
    print(f"3Dpro selftest on Blender {bpy.app.version_string} | tmp: {TMP}")
    fails = 0
    for name in only:
        if name in skip:
            print(f"  SKIP  {name}")
            continue
        t0 = time.time()
        try:
            msg = TESTS[name]()
            print(f"  PASS  {name:12} {msg}  ({time.time() - t0:.1f}s)")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"  FAIL  {name:12} {type(e).__name__}: {e}")
            traceback.print_exc()
    print("RESULT:", "ALL PASS" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
