"""Animation helpers that work across Blender 3.x -> 5.x (including the 4.4+ slotted-action data model).

    import anim_helpers as ah
    ah.bounce_ball(ball, height=1.5, period=24, bounces=4)      # Williams-style spacing + squash & stretch
    ah.shift_keys(obj, 3, path_contains="rotation")              # overlap / follow-through: delay a chain by 3 frames
    ah.set_interpolation(obj, "BEZIER", handle="AUTO_CLAMPED")
    ah.make_cyclic(obj)                                          # loop without duplicating the first key
    for fc in ah.iter_fcurves(obj): print(fc.data_path, fc.array_index, len(fc.keyframe_points))

API note: up to 4.3 an Action owned its F-curves (`action.fcurves`). From 4.4 an Action has layers -> strips ->
channelbags (one per slot) and the F-curves live in the channelbag for the object's slot; in 5.0 `action.fcurves`
is gone. `iter_fcurves` hides this so scripts survive upgrades.
"""
import math
import sys

import bpy


# --------------------------------------------------------------------------- fcurve access
def iter_fcurves(obj):
    """Yield every F-curve of `obj`'s active action on any Blender version."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    act = ad.action
    if hasattr(act, "layers"):                        # slotted actions (4.4+)
        slot = getattr(ad, "action_slot", None)
        for layer in act.layers:
            for strip in layer.strips:
                if strip.type != "KEYFRAME":
                    continue
                if slot is not None:
                    cb = strip.channelbag(slot)
                    if cb:
                        yield from cb.fcurves
                else:
                    for cb in strip.channelbags:
                        yield from cb.fcurves
    else:                                             # legacy
        yield from act.fcurves


def clear_animation(obj):
    if obj.animation_data and obj.animation_data.action:
        act = obj.animation_data.action
        obj.animation_data.action = None
        bpy.data.actions.remove(act)


def set_interpolation(obj, interpolation="BEZIER", handle=None, path_contains=None):
    """Set interpolation (and optionally handle type) on all or a subset of F-curves.

    interpolation: BEZIER (smooth), LINEAR (mechanical), CONSTANT (stepped - use for blocking pass).
    handle: AUTO_CLAMPED (default, no overshoot), AUTO, VECTOR, FREE, ALIGNED."""
    n = 0
    for fc in iter_fcurves(obj):
        if path_contains and path_contains not in fc.data_path:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
            if handle:
                kp.handle_left_type = kp.handle_right_type = handle
        fc.update()
        n += 1
    return n


def shift_keys(obj, frames, path_contains=None):
    """Move keys of matching F-curves by `frames` (can be fractional/negative).

    Overlapping action: tails, ears, antennas, loose cloth and the *children* in a chain lag the parent by 1-3 frames
    (the 'drag'); apply an increasing shift down the chain (spine 0, chest 1, neck 2, head 3)."""
    n = 0
    for fc in iter_fcurves(obj):
        if path_contains and path_contains not in fc.data_path:
            continue
        for kp in fc.keyframe_points:
            kp.co.x += frames
            kp.handle_left.x += frames
            kp.handle_right.x += frames
        fc.update()
        n += 1
    return n


def make_cyclic(obj):
    """Add a Cycles modifier to every F-curve so the animation loops. The first and last key must hold the same value."""
    for fc in iter_fcurves(obj):
        if not any(m.type == "CYCLES" for m in fc.modifiers):
            fc.modifiers.new("CYCLES")


def key_summary(obj):
    """{data_path[index]: [(frame, value), ...]} - handy for asserting what a script produced."""
    return {f"{fc.data_path}[{fc.array_index}]": [(round(k.co.x, 3), round(k.co.y, 4)) for k in fc.keyframe_points]
            for fc in iter_fcurves(obj)}


# --------------------------------------------------------------------------- bouncing ball
def bounce_ball(obj, height=1.5, floor=0.0, radius=0.5, period=24, bounces=4, decay=0.6,
                squash=0.6, max_stretch=0.25, start_frame=1):
    """Keyframe a bouncing ball on every frame with physically-correct spacing (the classic Williams exercise).

    * Height follows a parabola per bounce: slow, closely-spaced frames at the apex, wide spacing near the floor.
      That spacing - not just 'ease in/out' - is what makes the weight read.
    * Each bounce is `decay` x as high as the previous one; flight time scales with sqrt(height), so bounces get quicker.
    * Squash on contact (scale Z = `squash`), stretch in the air proportional to speed (up to 1 + max_stretch);
      X/Y compensate so the volume is preserved. The ball's bottom never goes below `floor`.
    * Origin must be the ball centre; `radius` is its resting half-height. Keys are on every frame, LINEAR interpolation
      (the curve itself already encodes the easing).

    Returns the last frame keyed (a contact frame).
    """
    obj.rotation_mode = "XYZ"
    clear_animation(obj)
    vmax = 4.0 * height / period                      # fastest speed (units per frame) of the first bounce

    def pose(hh, TT, t, frame):
        para = 4.0 * hh * t * (1.0 - t)
        speed = abs(4.0 * hh * (1.0 - 2.0 * t)) / TT
        on_floor = t <= 1e-9 or t >= 1.0 - 1e-9
        sz = squash if on_floor else 1.0 + max_stretch * min(speed / vmax, 1.0)
        sxy = 1.0 / math.sqrt(sz)                     # volume preservation
        obj.location.z = floor + radius * sz + para
        obj.scale = (sxy, sxy, sz)
        obj.keyframe_insert("location", index=2, frame=frame)
        obj.keyframe_insert("scale", frame=frame)

    hh, TT = float(height), float(period)
    frame = float(start_frame)
    n0 = max(int(round(TT / 2.0)), 1)                 # first segment: apex -> floor (half a period)
    for k in range(n0 + 1):
        pose(hh, TT, 0.5 + 0.5 * k / n0, frame + k)
    frame += n0
    for _ in range(bounces - 1):
        hh *= decay
        TT *= math.sqrt(decay)
        n = max(int(round(TT)), 2)
        for k in range(1, n + 1):                     # k=0 is the previous contact frame, already keyed
            pose(hh, TT, k / n, frame + k)
        frame += n
    set_interpolation(obj, "LINEAR")
    return frame


def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


if __name__ == "__main__":
    print(__doc__)
