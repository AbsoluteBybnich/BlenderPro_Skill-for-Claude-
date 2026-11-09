"""Lighting, camera and render setup based on classic lighting theory (key / fill / rim, ratios, colour temperature).
Verified on Blender 5.2 LTS with Cycles on CPU (EEVEE needs an OpenGL context; do not expect it in pure headless).

    import lighting_rig as lr
    lr.setup_render(engine="CYCLES", samples=128, resolution=(1920, 1080))
    lr.three_point(target=(0, 0, 1), key_power=120, key_fill_ratio=4, rim_ratio=1.5, distance=4)
    cam = lr.setup_camera(location=(5, -6, 2.5), look_at=(0, 0, 1), focal_mm=85, fstop=2.8)
    lr.render_still("/tmp/out.png")
    lr.turntable(cam, target=(0, 0, 1), frames=120)           # camera orbits once; render frames 1..120

Principles encoded here (lighting is about *intent*: what do you want the viewer to look at and feel?):
* Key = main light, ~45 deg to the side and ~45 deg above the camera axis; it models the shape.
* Fill = soft, low power, opposite side, often cooler/less saturated; key:fill ratio sets contrast.
  Ratios (as stops of exposure = log2): 2:1 flat/commercial, 4:1 classic, 8:1 moody/dramatic, 16:1+ noir.
* Rim/back light = from behind and above, separates the subject from the background.
* Power obeys the inverse-square law: if you move a light twice as far, it needs 4x the power (done for you by
  scale_power_for_distance).
* Big source = soft shadows (relative to subject), small source = hard shadows. Area-light size is your softness dial.
* Warm key (3200-4500 K) + cool fill (6500-8000 K) is the default complementary scheme; mixed temperatures read as 'real'.
"""
import math
import sys

import bpy
from mathutils import Vector


# --------------------------------------------------------------------------- colour
def kelvin_to_rgb(k):
    """Approximate blackbody colour (linear-ish RGB 0-1) for 1000-40000 K (Tanner Helland fit)."""
    t = max(1000.0, min(40000.0, k)) / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    if t >= 66:
        b = 255.0
    elif t <= 19:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10) - 305.0447927307
    clamp = lambda x: max(0.0, min(255.0, x)) / 255.0  # noqa: E731
    return (clamp(r), clamp(g), clamp(b))


def scale_power_for_distance(power_at_1m, distance):
    """Inverse-square compensation: keep the same exposure when you move the light."""
    return power_at_1m * distance * distance


# --------------------------------------------------------------------------- objects
def _aim(obj, target):
    """Point -Z of `obj` (lights/cameras) at `target` (Vector/tuple) without needing an empty."""
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(name, power, size, color, location, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.size, data.color = power, size, color
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    _aim(obj, target)
    return obj


def three_point(target=(0, 0, 1), key_power=120.0, key_fill_ratio=4.0, rim_ratio=1.5, distance=4.0,
                key_azimuth_deg=-45, key_elevation_deg=40, key_kelvin=4500, fill_kelvin=7000, rim_kelvin=6500,
                key_size=2.0, fill_size=3.0, rim_size=1.0, camera_azimuth_deg=0):
    """Classic key/fill/rim rig around `target`. Angles are relative to the camera azimuth (0 = camera on -Y axis).

    key_power:      watts of the key area light at `distance`. 120 W @ 4 m with a 2 m area light exposes a mid-bright
                    diffuse subject sensibly in Cycles; it scales with 1/size and distance^2, so re-expose by eye or
                    with scale_power_for_distance, never by guessing.
    key_fill_ratio: key POWER : fill POWER, compensated for the fill's greater distance (2 = flat, 4 = classic,
                    8 = moody). It is not a light-meter reading: angle of incidence and surface shape change the
                    ratio you measure on the subject (on a sphere 2/4/8 measure roughly 1.04/1.2/1.4 in sRGB values).
    rim_ratio:      rim power relative to the key.
    Returns (key, fill, rim).
    """
    tgt = Vector(target)

    def place(az_deg, el_deg, dist):
        az = math.radians(camera_azimuth_deg + az_deg)
        el = math.radians(el_deg)
        # camera sits on -Y at az=0; azimuth rotates counter-clockwise seen from above
        return tgt + Vector((math.sin(az) * math.cos(el) * dist, -math.cos(az) * math.cos(el) * dist,
                             math.sin(el) * dist))

    key = add_area_light("Key", key_power, key_size, kelvin_to_rgb(key_kelvin),
                         place(key_azimuth_deg, key_elevation_deg, distance), tgt)
    fill = add_area_light("Fill", key_power / key_fill_ratio, fill_size, kelvin_to_rgb(fill_kelvin),
                          place(-key_azimuth_deg * 1.2, 15, distance * 1.1), tgt)
    rim = add_area_light("Rim", key_power * rim_ratio, rim_size, kelvin_to_rgb(rim_kelvin),
                         place(180 - key_azimuth_deg * 0.6, 50, distance), tgt)
    # fill is farther -> compensate so the *ratio on the subject* is what the user asked for
    fill.data.energy = key_power / key_fill_ratio * (1.1 ** 2)
    return key, fill, rim


def setup_world(color=(0.02, 0.02, 0.025), strength=1.0, hdri_path=None):
    """Plain colour world or an HDRI. A dark neutral world keeps the key/fill ratio you designed."""
    sc = bpy.context.scene
    if not sc.world:
        sc.world = bpy.data.worlds.new("World")
    w = sc.world
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    if hdri_path:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri_path)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (*color, 1.0)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return w


def setup_camera(location=(5, -6, 2.5), look_at=(0, 0, 1), focal_mm=50.0, sensor_mm=36.0, fstop=None,
                 focus_on=None):
    """Camera aimed at `look_at`. Focal length guide: 24-35 mm environments, 50 mm neutral, 85-135 mm portraits/products.
    Pass `fstop` (e.g. 2.8) to enable depth of field; focus distance defaults to the look_at distance."""
    data = bpy.data.cameras.new("Camera")
    data.lens, data.sensor_width = focal_mm, sensor_mm
    obj = bpy.data.objects.new("Camera", data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    _aim(obj, look_at)
    if fstop:
        data.dof.use_dof = True
        data.dof.aperture_fstop = fstop
        if focus_on is not None:
            data.dof.focus_object = focus_on
        else:
            data.dof.focus_distance = (Vector(look_at) - Vector(location)).length
    bpy.context.scene.camera = obj
    return obj


def turntable(camera, target=(0, 0, 1), frames=120):
    """Orbit `camera` around `target` once over `frames` frames; render frames 1..frames for a seamless loop.

    Implementation: the camera is parented to an empty at the target, and the empty's Z rotation is driven by
    `frame * 2*pi/frames` - perfectly linear (no easing), loops without a duplicated end frame, and independent of the
    Blender version's animation data model. 120 frames (5 s @24) is a quick preview, 240-360 for portfolio quality."""
    pivot = bpy.data.objects.new("Turntable_Pivot", None)
    pivot.location = Vector(target)
    bpy.context.scene.collection.objects.link(pivot)
    bpy.context.view_layer.update()          # new objects have an identity matrix_world until the depsgraph runs
    world = camera.matrix_world.copy()
    camera.parent = pivot
    camera.matrix_parent_inverse = pivot.matrix_world.inverted()
    camera.matrix_world = world
    drv = pivot.driver_add("rotation_euler", 2).driver
    drv.type = "SCRIPTED"
    drv.expression = f"frame * {2 * math.pi / frames!r}"
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, frames
    return pivot


def setup_render(engine="CYCLES", samples=128, resolution=(1920, 1080), denoise=True, transparent=False,
                 view_transform_preference=("AgX", "Khronos PBR Neutral", "Filmic", "Standard"), device="CPU"):
    """Engine, samples, resolution and a sensible view transform chosen from what this build actually offers.

    View-transform names differ across versions/builds, so read them at runtime instead of hard-coding.
    Returns the chosen view transform name (or None if the build exposes none, e.g. bare `bpy` without OCIO data)."""
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.render.resolution_x, sc.render.resolution_y = resolution
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    if engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = denoise
        sc.cycles.device = device
    available = [e.identifier for e in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    chosen = next((v for v in view_transform_preference if v in available), None)
    if chosen:
        sc.view_settings.view_transform = chosen
        try:
            sc.view_settings.look = "None"
        except TypeError:
            pass
    return chosen


def render_still(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return path


def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


if __name__ == "__main__":
    print(__doc__)
