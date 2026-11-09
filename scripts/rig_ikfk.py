"""Procedural IK/FK limb rig + Rigify helper + auto-weight binding. Verified on Blender 5.2 LTS.

    import rig_ikfk as rg
    arm = rg.create_armature("Rig_Arm")
    names = rg.build_ik_fk_limb(arm, "arm.L", root=(0,0,0), mid=(0.3,0.05,0), end=(0.6,0,0), tip=(0.7,0,0))
    rg.bind_auto_weights(mesh_obj, arm)          # DEF- bones deform the mesh
    rg.set_ik_fk(arm, "arm.L", 1.0)              # 1 = IK, 0 = FK
    rg.snap_ik_to_fk(arm, "arm.L")               # match IK pose to the FK pose BEFORE flipping the switch
    rg.snap_fk_to_ik(arm, "arm.L")               # and the reverse
    rig = rg.generate_rigify_human()             # full biped in seconds (Rigify), for when you do not need custom
    rg.drive_shape_key_from_bone(face, "Blink_L", arm, "ctl.blink.L", "LOC_Z", lo=0, hi=0.02)   # face sliders
    rg.add_eye_aim(arm, "eye.L", "eye.target")                                    # gaze follows a target bone

Layout produced (the pattern used by Rigify and most studio rigs - controls and deformation are separate):
    DEF-<p>.upper/.lower/.hand   deform bones; skin weights live here; driven by constraints only
    FK-<p>.upper/.lower/.hand    animator rotates these
    IK-<p>.upper/.lower/.hand    IK solver chain (animators never touch)
    IK-<p>.target / IK-<p>.pole  animator moves these (hand/foot goal, elbow/knee direction)
    SW-<p>                       holds the custom property `ik_fk` (0..1); a driver blends DEF between FK and IK
Why separate DEF and control chains: you can change the control scheme (stretchy limbs, twist, fingers) without
re-skinning, and the export to a game engine keeps only DEF- bones (see export_ue5.py use_armature_deform_only).
"""
import math
import sys

import bpy
from mathutils import Matrix, Vector


def _activate(obj):
    vl = bpy.context.view_layer
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in vl.objects:
        o.select_set(False)
    vl.objects.active = obj
    obj.select_set(True)


def create_armature(name="Armature", location=(0, 0, 0)):
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _eval_pose_bone(arm_obj, name):
    bpy.context.view_layer.update()
    return arm_obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones[name]


def build_ik_fk_limb(arm_obj, prefix, root, mid, end, tip, pole_distance=0.5, parent_bone=None):
    """Create a 3-bone limb (upper, lower, hand) with FK, IK and a driven IK/FK switch.

    root/mid/end/tip: joint positions in armature space (shoulder, elbow, wrist, fingertip).
    The limb must be slightly bent at `mid` so the solver knows which way the joint folds; the pole target
    is placed on that side automatically and the pole angle is calibrated numerically so the rest pose is preserved.
    """
    root, mid, end, tip = (Vector(v) for v in (root, mid, end, tip))
    line = (end - root).normalized()
    bend = (mid - root) - line * (mid - root).dot(line)
    if bend.length < 1e-5:
        raise ValueError("limb is perfectly straight: offset `mid` slightly (1-5 % of limb length) toward the bend direction")
    bend.normalize()
    N = {
        "def": [f"DEF-{prefix}.upper", f"DEF-{prefix}.lower", f"DEF-{prefix}.hand"],
        "fk": [f"FK-{prefix}.upper", f"FK-{prefix}.lower", f"FK-{prefix}.hand"],
        "ik": [f"IK-{prefix}.upper", f"IK-{prefix}.lower", f"IK-{prefix}.hand"],
        "target": f"IK-{prefix}.target", "pole": f"IK-{prefix}.pole", "switch": f"SW-{prefix}",
    }
    joints = [(root, mid), (mid, end), (end, tip)]

    # ---- edit bones
    _activate(arm_obj)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_obj.data.edit_bones
    parent = eb[parent_bone] if parent_bone else None
    for group, deform in (("def", True), ("fk", False), ("ik", False)):
        prev = parent if group != "ik" else None
        for name, (h, t) in zip(N[group], joints):
            b = eb.new(name)
            b.head, b.tail, b.roll = h, t, 0.0
            b.use_deform = deform
            if prev:
                b.parent = prev
                b.use_connect = prev.tail == b.head or (prev.tail - b.head).length < 1e-6
            prev = b
    tgt = eb.new(N["target"])
    tgt.head, tgt.tail, tgt.roll, tgt.use_deform = end, tip, 0.0, False
    pole = eb.new(N["pole"])
    pole.head = mid + bend * pole_distance
    pole.tail = pole.head + Vector((0, 0, 0.05)) if abs(bend.z) < 0.9 else pole.head + Vector((0.05, 0, 0))
    pole.use_deform = False
    sw = eb.new(N["switch"])
    sw.head = root + Vector((0, 0, 0.08))
    sw.tail = root + Vector((0, 0, 0.16))
    sw.use_deform = False
    bpy.ops.object.mode_set(mode="POSE")

    pb = arm_obj.pose.bones
    # ---- IK solver
    ik = pb[N["ik"][1]].constraints.new("IK")
    ik.target, ik.subtarget = arm_obj, N["target"]
    ik.pole_target, ik.pole_subtarget = arm_obj, N["pole"]
    ik.chain_count = 2
    rot = pb[N["ik"][2]].constraints.new("COPY_ROTATION")
    rot.target, rot.subtarget = arm_obj, N["target"]

    # calibrate pole angle so the IK elbow sits where the rest-pose elbow is
    best, best_err = 0.0, 1e9
    for ang in (0.0, math.pi / 2, math.pi, -math.pi / 2):
        ik.pole_angle = ang
        err = (_eval_pose_bone(arm_obj, N["ik"][1]).head - mid).length
        if err < best_err:
            best, best_err = ang, err
    ik.pole_angle = best

    # ---- switch property + blend of FK/IK into DEF
    pb[N["switch"]]["ik_fk"] = 1.0
    pb[N["switch"]].id_properties_ui("ik_fk").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                                                    description="0 = FK, 1 = IK")
    for d, f, i in zip(N["def"], N["fk"], N["ik"]):
        c_fk = pb[d].constraints.new("COPY_TRANSFORMS")
        c_fk.target, c_fk.subtarget, c_fk.name = arm_obj, f, "FK"
        c_ik = pb[d].constraints.new("COPY_TRANSFORMS")
        c_ik.target, c_ik.subtarget, c_ik.name = arm_obj, i, "IK"
        drv = c_ik.driver_add("influence").driver
        drv.type = "AVERAGE"
        var = drv.variables.new()
        var.name = "ik_fk"
        var.type = "SINGLE_PROP"
        var.targets[0].id = arm_obj
        var.targets[0].data_path = f'pose.bones["{N["switch"]}"]["ik_fk"]'
    bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj["_ikfk_" + prefix] = best          # remember calibration for the snap helpers
    return N


def set_ik_fk(arm_obj, prefix, value):
    """Set the IK/FK blend (0 = FK, 1 = IK). Writing a custom property from Python does NOT tag the
    dependency graph, so the driver would not re-evaluate until something else changes; update_tag() forces it."""
    arm_obj.pose.bones[f"SW-{prefix}"]["ik_fk"] = float(value)
    arm_obj.update_tag()
    bpy.context.view_layer.update()


def _names(prefix):
    return ([f"DEF-{prefix}.{k}" for k in ("upper", "lower", "hand")],
            [f"FK-{prefix}.{k}" for k in ("upper", "lower", "hand")])


def snap_fk_to_ik(arm_obj, prefix):
    """Copy the current *deform* result onto the FK controls (use after posing in IK, before switching to FK)."""
    defs, fks = _names(prefix)
    for d, f in zip(defs, fks):                 # parent -> child so each matrix is set in the right space
        m = _eval_pose_bone(arm_obj, d).matrix.copy()
        arm_obj.pose.bones[f].matrix = m
        bpy.context.view_layer.update()


def snap_ik_to_fk(arm_obj, prefix, pole_distance=0.5):
    """Place IK target + pole where the current deform result is (use after posing in FK, before switching to IK)."""
    defs, fks = _names(prefix)
    hand = _eval_pose_bone(arm_obj, defs[2]).matrix.copy()
    elbow = _eval_pose_bone(arm_obj, defs[1]).head.copy()
    root = _eval_pose_bone(arm_obj, defs[0]).head.copy()
    wrist = hand.to_translation()
    line = (wrist - root).normalized()
    bend = (elbow - root) - line * (elbow - root).dot(line)
    bend.normalize()
    arm_obj.pose.bones[f"IK-{prefix}.target"].matrix = hand
    bpy.context.view_layer.update()
    pole = arm_obj.pose.bones[f"IK-{prefix}.pole"]
    m = pole.matrix.copy()
    m.translation = elbow + bend * pole_distance
    pole.matrix = m
    bpy.context.view_layer.update()


def drive_shape_key_from_bone(mesh_obj, key_name, arm_obj, bone_name, transform_type="LOC_Z",
                              space="LOCAL_SPACE", lo=0.0, hi=0.02):
    """Drive a shape key (blink, brow raise, smile...) from a control bone's movement.

    The bone's `transform_type` channel is remapped from [lo, hi] to the key value [0, 1] and clamped.
    Typical face-rig recipe: a slider bone limited to a small range along local Z (Limit Location constraint,
    lo=0, hi=0.02 m) -> shape key. Animators move one bone, the mesh does the complex deformation.
    Uses a simple (non-Python) driver expression, so it also works when 'auto-run Python scripts' is off.
    """
    kb = mesh_obj.data.shape_keys.key_blocks[key_name]
    drv = kb.driver_add("value").driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = "v"
    var.type = "TRANSFORMS"
    t = var.targets[0]
    t.id = arm_obj
    t.bone_target = bone_name
    t.transform_type = transform_type
    t.transform_space = space
    drv.expression = f"max(0.0, min(1.0, (v - ({lo})) / (({hi}) - ({lo}))))"
    return drv


def add_eye_aim(arm_obj, eye_bone, target_bone, track_axis="TRACK_Y"):
    """Make an eye bone keep pointing at an 'eye target' bone (Damped Track). One target bone aims both eyes
    when you add the constraint to each eye bone - the standard way to get consistent gaze and easy 'look at' animation."""
    pb = arm_obj.pose.bones[eye_bone]
    c = pb.constraints.new("DAMPED_TRACK")
    c.target, c.subtarget, c.track_axis = arm_obj, target_bone, track_axis
    return c


def bind_auto_weights(mesh_obj, arm_obj):
    """Parent with automatic (heat) weights. Only bones with use_deform=True (the DEF- bones) get weights."""
    _activate(mesh_obj)
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type="ARMATURE_AUTO", keep_transform=True)
    return mesh_obj


def generate_rigify_human():
    """Add Rigify's human metarig and generate the control rig. Returns the generated rig object.

    Position/scale the metarig's bones to your mesh *before* generating (edit mode, Armature > Symmetrize
    helps). Then bind your mesh to the generated rig's DEF- bones with automatic weights."""
    bpy.ops.preferences.addon_enable(module="rigify")
    bpy.ops.object.armature_human_metarig_add()
    meta = bpy.context.object
    bpy.ops.pose.rigify_generate()
    rig = meta.data.rigify_target_rig if hasattr(meta.data, "rigify_target_rig") else None
    return rig or next(o for o in bpy.data.objects if o.type == "ARMATURE" and o is not meta)


if __name__ == "__main__":
    print(__doc__)
