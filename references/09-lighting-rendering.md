# Lighting, cameras and rendering

Contents: 1 What lighting is for · 2 Light qualities · 3 Key/fill/rim and ratios · 4 Colour · 5 Shadows · 6 Exposure and colour management ·
7 Cycles settings · 8 EEVEE notes · 9 Cameras and composition · 10 Passes and compositing · 11 Turntables and asset beauty shots · 12 Troubleshooting · 13 Checklist

Script: `scripts/lighting_rig.py` (`three_point`, `kelvin_to_rgb`, `setup_world`, `setup_camera`, `setup_render`, `turntable`, `render_still`). Cycles-on-CPU verified: raising `key_fill_ratio` from 2 to 8 raised measured key-side/fill-side contrast
from 1.09:1 to 1.96:1 (linear light, white sphere). The theory condenses standard lighting-for-CG practice (as taught in *Digital Lighting & Rendering*-style texts); it is not a quotation.

## 1. What lighting is for
1. **Visibility** - the viewer must see what matters. 2. **Form** - light and shadow reveal shape and material. 3. **Focus** - bright, high-contrast, saturated areas pull the eye. 4. **Mood/story** - time of day, emotion, genre.
Ask before placing any light: *what is this light's motivation (sun, window, lamp), and what job does it do (model, separate, fill, accent)?* Lights without a job get deleted.

## 2. Qualities of light (the five dials)
Direction (where from) · Intensity · Colour · Softness (source size relative to subject and distance) · Shape/pattern (gobos, windows, cookies).
- **Softness**: bigger source or closer source relative to the subject = softer shadows; small/far (sun) = hard. Area-light `size` is your softness dial.
- **Falloff**: intensity follows the inverse-square law (`scale_power_for_distance`). Doubling the distance needs 4x power. This is why a "fill" far away is dimmer than expected.
- **Direction conventions**: top-front-side key = flattering and readable; low front key (under chin) = horror; backlight = silhouette/rim; top-down = dramatic/harsh.

## 3. Key / fill / rim and ratios
- **Key**: main light, ~30-60 deg to the side and above the camera axis; defines shape and shadow direction.
- **Fill**: softer, lower power, opposite side or near the camera; sets shadow density. **Ratio** = how much brighter key side is than shadow side.
  | Ratio (key:fill) | Look |
  |---|---|
  | 1:1 - 2:1 | flat, high-key (beauty, comedy, product) |
  | 3:1 - 4:1 | classic, natural |
  | 6:1 - 8:1 | moody, dramatic |
  | 16:1+ | noir, hard chiaroscuro |
- **Rim/back light**: from behind and above, separates the subject from the background; place so the edge glows without lighting the face.
- **Bounce/ambient**: environment colour fills shadows in reality. A dark world with explicit fills gives control (`setup_world((0,0,0))`); an HDRI gives realism.
- In the script `key_fill_ratio` is the *power* ratio (fill power compensated for its greater distance); the ratio you *measure* on a curved subject is lower because of angle of incidence. Tune by eye using the viewport/preview.
- Starting point (Cycles, 2 m area key at 4 m): ~120 W key; fill = key/ratio; rim = 1-1.5x key. Re-expose by adjusting **exposure** rather than all light powers.

## 4. Colour
- **Colour temperature**: warm ≈ 2700-4500 K (tungsten, sunset), neutral ≈ 5500-6500 K (daylight), cool ≈ 7000-10000 K (shade, overcast, sky). `kelvin_to_rgb(4500)` etc.; Blender's *Blackbody* node does the same for emission.
- Classic scheme: **warm key + cool fill** (or reverse) = depth and appeal. Keep saturation low on lights (0.1-0.3) and let the environment/materials carry colour.
- Avoid unmotivated rainbow lights; limit to a dominant hue + one accent.
- Beware mixed white-balance: set the render's white balance by the key light; the compositor/colour balance can shift the whole image.

## 5. Shadows
Shadows give depth cues, anchor objects to the ground (contact shadows), and shape forms. Check: contact shadows exist where objects touch surfaces; shadow edges are softer farther from the occluder; shadows are not pure black (add fill/bounce); shadow colour is the complementary of the key (cool shadows under warm sun).

## 6. Exposure and colour management
- Work **scene-referred linear**; the *view transform* maps it to the display. Modern default: **AgX** (4.0+); alternatives: Filmic (older), Standard (clips highlights), Khronos PBR Neutral (product colour fidelity). Names differ by build - `lighting_rig.setup_render` reads what the build offers and picks the first available of AgX/Neutral/Filmic/Standard.
- **Exposure** (Color Management panel) in stops: +1 doubles brightness. Use it to set overall brightness; use light power for balance.
- Sun strength in Blender: ~1-5 W/m² range is common with AgX; HDRI strength 1.0 as baseline; adjust until a 18 % grey card reads mid-grey.
- Colour textures **sRGB**, data textures **Non-Color** (`03`). Save beauty renders as PNG 16-bit or EXR; use EXR (16-bit half) for compositing.

## 7. Cycles settings (defaults verified on 5.2: max bounces 12, diffuse 4, glossy 4, transmission 12, clamp indirect 10, adaptive threshold 0.01)
| Goal | Setting |
|---|---|
| Quality | Samples 128-512 with a denoiser (OpenImageDenoise on CPU, OptiX on NVIDIA); **noise threshold 0.01** (adaptive sampling) |
| Fireflies | clamp indirect ≈ 10 (default), reduce glossy roughness extremes, avoid tiny bright emitters, filter glossy 1.0 |
| Interiors | raise total bounces (12-16), use light portals/window area lights, higher samples |
| Speed | lower resolution %, adaptive sampling, light tree (default), denoise, limit transmission bounces, simplify subdivision |
| Baking | disable denoising, fixed samples (`03`) |
Headless: Cycles CPU works without a GPU; `scene.cycles.device = 'CPU'`.

## 8. EEVEE (real-time render engine)
Fast, great for look-dev and stylised output. In 4.2+ the rewritten engine (id `BLENDER_EEVEE_NEXT` in 4.2-4.5, `BLENDER_EEVEE` again in 5.x) supports ray tracing options, virtual shadow maps and light probes. It needs an OpenGL context: not available in pure headless containers. Don't promise EEVEE renders in CI; use Cycles there.

## 9. Cameras and composition
- **Focal length**: 14-24 mm dramatic wide; 28-35 mm environments/documentary; 50 mm neutral; 85-135 mm portraits/products (flattering compression). Sensor 36 mm full-frame equivalent.
- **Depth of field**: f/1.4-2.8 shallow (portrait), f/8-11 deep (architecture). Set the focus object/distance (`setup_camera(fstop=2.8)`).
- **Composition**: rule of thirds, leading lines, framing, foreground/mid/background layers, headroom and lead room, avoid tangents (edges touching edges), keep horizon level unless intentional.
- **Aspect**: 16:9 video, 2.39:1 cinematic, 4:5 or 1:1 social, 3:2 stills. **Motion blur**: shutter 180 deg of the frame time.
- Use the **camera lens** to sell scale: low wide-angle = heroic/large; telephoto = flattened, intimate.

## 10. Passes and compositing
- Useful Cycles passes: Combined, Diffuse (Direct/Indirect/Color), Glossy, Transmission, Emission, Environment, **AO**, **Z/Depth**, **Mist**, Normal, Position, Shadow catcher, **Cryptomatte** (Object/Material) for masking.
- Compositor basics: Glare (bloom, subtle), Color Balance/ Curves (grade), Lens Distortion (tiny chromatic aberration), Vignette (ellipse mask + blur), Defocus using Z, denoise node for passes. In Blender 5.x the compositor tree lives in `scene.compositing_node_group` (the old `scene.node_tree` is gone).
- Render **multilayer EXR** when you plan serious compositing; otherwise bake the grade in via view transform + Color Management Look.

## 11. Turntables and asset beauty shots
- Neutral grey backdrop (shadow-catcher plane or infinite curve), **3-point + soft HDRI** or HDRI only, 50-85 mm lens, camera slightly above eye level of the object.
- `lighting_rig.turntable(camera, target, frames=120)`: camera parented to a pivot driven by `frame * 2π/frames`; render frames 1..frames for a seamless loop (120 = quick, 240-360 = portfolio).
- Provide 3 stills (3/4 front, side, detail) + wireframe/clay render + texture sheet for portfolios and handoff; keep the same lights across assets for comparability.
- Real-time alternative: Marmoset Toolbag / engine viewer with the same camera and lighting.

## 12. Troubleshooting
| Problem | Fix |
|---|---|
| Looks flat | more key:fill contrast, add rim, create light/dark shapes with flags/gobos, vary background value |
| Muddy/dirty shadows | too much ambient/fill, tint shadows cooler, raise key, check bounce colours |
| Blown highlights | lower light/exposure; AgX/Filmic instead of Standard; check albedo values (no white 1.0) |
| Fireflies | clamp indirect, lower emissive intensity, more samples + denoise |
| Noisy shadows | larger lights are noisier in dark areas: raise samples, denoise, light tree on |
| Colour cast | check light temperatures, white-balance in compositor, world colour |
| Texture too dark/bright | colour space sRGB vs Non-Color; exposure vs light power |
| Render slow | lower samples + denoise, resolution %, simplify, bake/optimise heavy materials |

## 13. Checklist
- [ ] Every light has a motivation and a job; key/fill/rim ratio chosen on purpose
- [ ] Exposure ok (histogram not clipped), colour management set, colour/data textures correct
- [ ] Camera focal length/DoF justified; composition has a clear focal point
- [ ] Contact shadows present; shadows coloured and not pure black
- [ ] Output format and bit depth match the next step (EXR for comp, PNG16 for stills)
