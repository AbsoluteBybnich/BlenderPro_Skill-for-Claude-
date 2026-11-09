# Retopology, UV unwrapping and map baking (Blender + Marmoset Toolbag)

Contents: 1 Retopology · 2 UV · 3 Texel density and texture planning · 4 Baking concepts · 5 Blender bake (script + manual) ·
6 Marmoset Toolbag workflow · 7 Artefact troubleshooting · 8 Map set and packing · 9 Checklists

Scripts: `uv_retopo.py` (unwrap, pack, texel density, Quadriflow draft, shrinkwrap retopo rig) · `bake_maps.py` (Normal/AO/Curvature) · `qa_check.py` (UV overlap, density).

## 1. Retopology
**Goal depends on use**: animation-ready (loops follow deformation), real-time (silhouette-efficient, bake-friendly), SubD base (all quads, even flow).

Methods (pick by asset importance):
| Method | Use for | Notes |
|---|---|---|
| Manual (poly-build / snapping onto the sculpt) | hero characters, faces, anything that deforms | best flow, slowest. Blender: Shrinkwrap modifier + face snapping, or **RetopoFlow** (paid add-on) |
| Quadriflow (`object.quadriflow_remesh`, scripted in `uv_retopo.quad_remesh`) | blockouts, props, LOD bases, bases for cleanup | quads, no control over loops except sharp/boundary/symmetry |
| Guided auto-retopo (ZRemesher with guides, QuadRemesher add-on) | characters on a deadline | guide curves steer loops; cleanup still needed |
| Decimate (collapse) | LODs, static background, distant props | triangles, wrecks UVs/flow - never for deforming hero meshes |
| Voxel/Remesh modifier | sculpt stage only | not retopo |

Manual retopo rules:
1. Set up: `uv_retopo.shrinkwrap_for_manual_retopo(low, high)` (shrinkwrap with offset ~0.5 mm so the low sits just above; face snapping; wire + X-ray).
2. Place **structure first** (loops around eyes/mouth, joints, major silhouette), then fill.
3. **Quads** everywhere deformation or subdivision matters. **Poles**: 5-valence (E-pole) and 3-valence (N-pole) placed in low-stress, low-visibility areas; avoid poles on bend zones and focal points.
4. Density follows *curvature and deformation*, not uniformity: tight at joints/face, loose on flat thighs/back.
5. Keep loops continuous across mirrored halves; use Mirror modifier with clipping; stitch at the centre.
6. For game LODs: build LOD0 clean, derive LOD1-3 by removing edge loops (not Decimate) on characters; Decimate is OK for props.
7. After retopo: check `qa_check.py` (zero-area faces, doubles, non-manifold) and verify the low *encloses* the detail within the bake cage distance.

Budgets (rough; check platform): prop small 300-3k tris · prop hero 3-20k · weapon 10-40k · character stylised 8-40k · realistic hero 60-150k · environment modular piece 500-5k. With Nanite (UE5 static meshes) the budget loosens a lot for rigid geometry - see `04`.

## 2. UV unwrapping
Principles (why): UVs store texture detail; distortion = blurry/stretched texels; seams = places where texture and normals can break; overlap = shared texels (OK only on purpose).
1. **Seam placement**: hidden or natural breaks (under arms, inside legs, back of head, along hard edges, behind objects). For hard-surface: **sharp edges become seams** (`uv_retopo.seams_from_sharp`) - one smoothing group per island makes normal maps clean.
2. **Unwrap method**: Angle Based (default), Conformal for organic stretch-free, Minimum Stretch for difficult islands; Smart UV Project only for quick props/lightmaps; "Follow Active Quads" to straighten panels.
3. **Straighten and square** hard-surface islands (grid-aligned UVs compress better, avoid stair-stepping, and make trims reusable).
4. **Uniform texel density** across the asset (see section 3); allow face/hands/hero parts 1.5-2x. `bpy.ops.uv.average_islands_scale()` first, then fine-tune.
5. **Padding (gutter)**: ~4 px @1k, 8 px @2k, 16 px @4k - mip-maps bleed neighbours otherwise (`uv_retopo.margin_fraction`). Bake margin (dilation) should be ≥ padding.
6. **Orientation**: axis-aligned islands, text/decals upright; consistent "up" for tiling textures.
7. **Mirrored UVs** save texture space and keep symmetrical detail identical, but: unique AO/curvature/dirt/baked lighting must not be mirrored; normal maps tolerate mirroring with consistent tangents (MikkTSpace) except at the mirror seam; text/logos break. Rule: mirror only for tileable/symmetric-by-design assets; hero assets get unique UVs (offset mirrored shells outside 0-1 into a second tile if needed).
8. **UDIMs** for hero characters/close-ups (face, body, clothing tiles) instead of 8k single maps.
9. **Second UV channel for lightmaps** (non-overlapping, 0-1, no tiling) only if the engine uses baked lighting; Lumen/virtual shadow maps in UE5 usually do not need it.
10. **Pack speed trap**: `uv.pack_islands` with rotation enabled and a CONCAVE/CONVEX shape method took minutes on a ~100-face beveled box (Blender 5.2, 4 cores); without rotation CONCAVE took 0.5 s and AABB+rotation was instant. Hard-surface islands are axis-aligned anyway - leave rotation off, or use AABB when you need it (`uv_retopo.unwrap(pack_shape=..., pack_rotate=...)`).
11. **Trim sheets / tiling**: UV props to a shared trim texture - high detail at low cost; planar-aligned islands whose width matches trim strips.

## 3. Texel density and texture planning
- Formula: `texel density (px/m) = sqrt(UV area / 3D area) * texture size`. Measure: `uv_retopo.texel_density(obj, 2048)`; set: `set_texel_density(obj, target, size)`; audit: `qa_check.py --tex-size 2048 --target-td 1024`.
- Rules of thumb for first-person/third-person games: background 256-512 px/m, props/environment 512-1024, hero props & weapons 1024-2048, character body 512-1024, face/hands 1024-2048. Match the *project's* standard; never mix densities in one scene.
- Choose texture size from density: `size = target_td * longest_UV_extent_in_m`. A 2 m prop at 1024 px/m needs 2048.
- Sizes in powers of two (UE streaming/mip), non-square OK (2048x1024). Check texture memory budget: 2048² BC7 ≈ 5.3 MB w/ mips.
- Texture sets: one set per material group, not per object part; fewer sets = fewer draw calls.

## 4. Baking concepts
A bake shoots rays from each low-poly surface point along its normal (or from a **cage**) toward the high poly and records what it hits (normal direction, occlusion, curvature, position, colour ID).
Requirements: (1) low has final, non-overlapping UVs; (2) low and high occupy the same space (same scale/location); (3) scale applied; (4) high is clean (no crazy intersections that matter); (5) **triangulate the low before baking**.
- **Ray distance / cage**: too small -> misses (black/flat patches); too large -> hits the wrong surface (blow-outs). Start with cage extrusion ≈ 1-3 % of the object size (e.g. 0.02 m for a 1 m prop) and adjust. A hand-tuned cage (`bake_maps.make_cage`) fixes concave areas.
- **Naming/exploding**: `Name_low` / `Name_high`; for assemblies, offset parts apart ("explode") so rays do not hit neighbouring parts, bake, then restore.
- **Tangent space**: use **MikkTSpace** consistently (Blender, Marmoset, Substance, UE5 all default to it). Normal maps only match if baker and renderer share the tangent basis and the same triangulation.
- **Normal Y convention**: OpenGL (+Y, "Y up") for Blender/glTF/Unity/Marmoset default; **DirectX (Y down)** for Unreal. `bake_maps.py --target ue` bakes green negated; or flip green later (verified: the DX map = 1 - GL green).
- **Smoothing vs UV**: hard edges must be UV seams; otherwise the normal map has to fight a gradient across the edge ("waviness").

## 5. Blender bake
Script: `scripts/run_headless.sh bake_maps.py scene.blend -- --low SM_Prop_low --high SM_Prop_high --out ./bakes --size 2048 --maps normal ao curvature --cage 0.02 --target ue`
Manual equivalent: Cycles engine -> Bake panel -> *Selected to Active* (high selected, low active) -> low has a material with an **Image Texture node selected/active** (new image, 16-bit float, `Non-Color`) -> Normal (Tangent; R+X G∓Y B+Z) / AO / Emit...-> save image as PNG16/EXR.
Details that bite:
- Denoising and low samples smear bakes; use 32-128 samples for normals (they converge fast), more for AO.
- **Margin type Extend** hides seams; margin ≥ UV padding.
- AO bake distance = world *AO distance* (script: `ao_distance`). Keep AO a *mask for texturing/dirt*, not baked-in lighting for PBR.
- **Curvature**: Blender has no curvature bake pass; the script approximates via the high poly's *Pointiness* (needs dense geometry; noisy on razor edges). For production curvature compute it from the normal map in Marmoset/Substance/xNormal.
- Colour maps/IDs: bake **Emit** from a material that outputs vertex colour/ID colour (or assign flat colours per part).
- Read data maps back as **Non-Color** (a frequent self-inflicted "bug").

## 6. Marmoset Toolbag workflow (UI names may shift between versions - verify)
1. Export low and high as FBX/OBJ with matching names (`*_low`, `*_high`), triangulated low, hard edges/UV splits already in place, units consistent.
2. Import both; create a **Bake Group** (low = *Low*, high = *High*); for multi-part assets create one group per part/material to avoid cross-hits.
3. Bake settings: output size (match the texel-density plan), **samples 8x-16x** (anti-alias), padding ≥ your UV gutter; geometry: smooth cage with **offset** until rays cover concave areas; use **skew painting** to correct stretched details.
4. Maps: **Normals** (Tangent space, *Mikk*; set **Flip Y** when targeting Unreal/DirectX), **Ambient Occlusion** (rays 512+, tune distance), **Curvature**, **Thickness**, **Position**, **Material/Mesh ID**, optionally **Height**.
5. Inspect in the viewport with the low-poly material using the baked normal; look for waviness, seam gradients, blown-out spots; iterate on cage/offset, not on the high.
6. Export PNG/TGA/EXR at 16-bit for normals/height; hand maps to Substance Painter or Blender texturing.
Blender and Marmoset are interchangeable for baking in a pipeline; Marmoset is generally faster, has skew painting and a better curvature/thickness set - choose per project.

## 7. Artefact troubleshooting
| Symptom | Likely cause | Fix |
|---|---|---|
| Waviness / bent straight lines in normal | low-poly normals smoothed across uneven topology; missing support edges; triangulation mismatch | add support edges on curves, harden normals + split UV, triangulate before bake, skew paint (Marmoset) |
| Black/flat patches | rays miss the high | increase cage extrusion/ray distance, move cage, check scale/offset |
| Strong blow-outs / spikes | rays hit another part or backfaces | decrease ray distance, explode parts, use cage, clean high |
| Seam lines on normal | hard edge not split in UV, low padding | split UV at hard edges, increase padding/margin, Extend margin |
| Inverted lighting (bumps look dents) | wrong green convention for the engine | flip green (DX <-> GL) |
| Noisy AO | low samples | raise samples/ray count; denoise only AO |
| Details skewed on cylinders | cap ngon/triangles skew rays | reroute triangulation, add loops, skew paint |
| Mirrored detail wrong | mirrored UV with inconsistent tangents/overlaps | unique UVs or offset mirror shell |

## 8. Map set and packing (PBR metal/roughness; typical for UE5)
| Map | Colour space | Notes |
|---|---|---|
| Base Color (Albedo) | sRGB | no baked lighting; 30-240 sRGB range for dielectrics (avoid pure black/white) |
| Normal | linear / Non-Color | DirectX for Unreal; 16-bit source, compress BC5 in UE |
| ORM packed: R = AO, G = Roughness, B = Metallic | linear | one texture sample instead of three; set sRGB off |
| Emissive / Opacity / Height | sRGB (emissive) / linear | only when needed |
| Masks (ID, curvature, thickness) | linear | live in Substance, not shipped |
Set import flags in UE (sRGB off for ORM/normal, compression NormalMap/Masks). Document the packing in the asset README so artists do not guess.

## 9. Checklists
**Before baking**: scale applied · low triangulated · UVs final, no overlap (unless intentional) · padding set · hard edges split in UV · high/low aligned · names `_low/_high` · cage/ray distance planned.
**After baking**: normal reads correct in engine lighting · no seams/waves at typical camera distance · AO/curvature usable as masks · files named `T_<Asset>_N/ORM/BC` (UE naming) · 16-bit sources archived.
