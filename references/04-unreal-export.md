# Blender -> Unreal Engine 5 pipeline

Contents: 1 Units and axes · 2 Naming · 3 Static mesh export · 4 Collision, LODs, sockets · 5 Nanite and lighting · 6 Materials and textures ·
7 Skeletal mesh and animation · 8 Importing (UE side) · 9 Verification · 10 Automation · 11 Troubleshooting

Script: `scripts/export_ue5.py` (pre-flight + FBX). Round-tripped through Blender in testing; **never imported into Unreal Editor in this build** - verify the first import of every new asset type.

## 1. Units and axes
- Unreal: **1 unit = 1 cm**, Z-up, X-forward, left-handed. Blender: 1 unit = 1 m (keep scene scale 1.0), Z-up, right-handed.
- Export settings used by `export_ue5.py`: `apply_unit_scale=True`, `apply_scale_options='FBX_SCALE_ALL'` ("FBX All"), `use_space_transform=True`, defaults `axis_forward='-Z'`, `axis_up='Y'`.
  Effect: a 1 m cube arrives as 100 uu with object scale 1. (The round trip into Blender confirmed 1:1 size and scale 1.)
- Orientation of **characters**: the UE Mannequin faces +X. After the first import, check which way the mesh faces; if rotated, fix by rotating in Blender *and applying* (not by compensating in UE), or use the importer's front-axis option. Verify per project.
- Sanity-check scale in-engine against the Mannequin (~180 cm), doors (200-220 cm), stair step (15-20 cm).

## 2. Naming (Epic / community style)
`SM_` static mesh · `SK_`/`SKM_` skeletal mesh · `T_` texture (suffix `_BC` base color, `_N` normal, `_ORM` packed, `_E` emissive) · `M_` material · `MI_` material instance ·
`A_` animation · `SKEL_` skeleton · `PHYS_` physics asset · `BP_` blueprint. Collision: `UCX_`/`UBX_`/`UCP_`/`USP_` prefix + render-mesh name + `_NN`.
No spaces, no `.001` suffixes (Blender duplicates), no non-ASCII. Material names become **material slot names** in UE - make them meaningful (`M_Metal_Painted`), not `Material.003`.

## 3. Static mesh export (what to prepare)
1. Real scale, **scale and rotation applied**, origin at the intended pivot (prop: base centre; modular piece: corner/bottom per grid; hinged door: at the hinge).
2. Modifiers applied or intentionally exported (`use_mesh_modifiers=True` applies them); Mirror seams welded; no loose geometry; normals correct.
3. Smoothing: export **face smoothing + custom normals** (`mesh_smooth_type='FACE'`). Hard edges must already be UV seams (`03`).
4. **Triangulate** on export (script adds a temporary Triangulate modifier with *keep custom normals*) so the engine's triangulation equals the baked one.
5. UV map 0 = texture UVs; UV map 1 = lightmap (only if baked lighting is used; UE can generate it on import).
6. Run `qa_check.py --convention ue --tex-size ... --target-td ... --max-tris ...` then export:
   `scripts/run_headless.sh export_ue5.py scene.blend -- --out ./Export --collection SM_Crate`
   One FBX per asset (mesh + collision + sockets + LODs inside the same file), not one giant FBX of the scene.

## 4. Collision, LODs, sockets (all inside the same FBX)
- **Collision**: separate meshes named `UBX_<Mesh>_00` (box), `UCX_<Mesh>_00` (convex hull; **must be convex**, `export_ue5.is_convex` checks), `UCP_` (capsule), `USP_` (sphere). Same origin/orientation as the render mesh. Hide/wire in Blender. Or let UE auto-generate; hand-made collision is better for complex props and anything players touch.
- **LODs**: name `<Mesh>_LOD0`, `<Mesh>_LOD1`, ... in one FBX; import with "Import mesh LODs". Reduction guide: LOD1 ≈ 50 %, LOD2 ≈ 25 %, LOD3 ≈ 10-12 % of tris; keep UV and material slots identical across LODs. Or generate in UE (Static Mesh Editor reduction) for background props.
- **Sockets**: Empty objects named `SOCKET_<Name>` parented to the mesh -> static mesh sockets (attach points for weapons, VFX).
- **Pivot / origin** = what you see in the Static Mesh Editor; fix in Blender (Origin to Geometry/3D cursor) before export.

## 5. Nanite and lighting (UE5)
- **Nanite** (virtualised geometry) suits high-poly rigid static meshes (rocks, buildings, kit pieces): enable at import / in the mesh editor; budgets for triangles loosen dramatically, but UVs/texel density, material complexity and overdraw (masked/translucent materials) still cost. Skeletal Nanite is limited/experimental in recent versions - verify for your engine version.
- Keep a sane fallback: Nanite builds a fallback mesh for non-Nanite paths (shadows on old settings, mobile).
- **Lumen / Virtual Shadow Maps** mean lightmap UVs are usually unnecessary; Nanite + Lumen reward clean watertight, consistently-scaled meshes (thin double-sided geometry shades poorly).
- Do not bake lighting into textures for PBR; AO bake belongs in the ORM or masks only.

## 6. Materials and textures
- Do **not** rely on importing Blender materials. Create a **master material** in UE with parameters and use **material instances** per asset; slot names from FBX map to instances.
- Texture settings in UE: Base Color sRGB on; **Normal map** compression *NormalMap* (BC5) and **DirectX green** (bake with `--target ue`, or flip green); **ORM/mask** textures: sRGB **off**, compression *Masks* (or Default with sRGB off).
- Texture sizes power-of-two, matched to texel density (`03`). Use Virtual Textures for huge sets; texture groups for LOD bias.
- Trim sheets / tileables: set `Tiling` in the material, not through UV scale hacks, to keep density consistent.

## 7. Skeletal mesh and animation
Prepare the rig (see `06`):
- **Skeleton**: a single clean root (`root` bone at origin), A- or T-pose rest (match the Mannequin A-pose if you will retarget with UE5's **IK Rig / IK Retargeter**), bone names without spaces, consistent `.L/.R` or `_l/_r`.
- Export **deform bones only** (`use_armature_deform_only=True`), no leaf bones (`add_leaf_bones=False`). Control rigs (IK/FK, Rigify controls) stay in Blender; the engine gets the DEF skeleton. (Verified: the FBX contained exactly the `DEF-` bones.)
- Armature at origin, scale (1,1,1), rotation 0 applied; mesh parented with an Armature modifier; weights normalised, ≤ 4 influences per vertex for broad compatibility (UE5 can use more per project settings).
- **Shape keys -> Morph Targets**: FBX exports shape keys; avoid topology-changing modifiers on the mesh (they drop shape keys). Keep face shapes named by ARKit/FACS conventions if you want ready-made facial animation compatibility.
- `export_skeletal(armature, meshes, path)` for the mesh+skeleton; `export_animation(armature, path, frame_start, frame_end)` for animation-only FBX.
- **Animation**: set the Blender FPS to the project's (24/30/60) *before* keyframing; bake with `bake_anim_simplify_factor=0`; one action per FBX (`A_<Char>_<Anim>`); trim to range. **Loops**: do not include a duplicate final frame equal to the first, or the loop hitches. Root motion: animate the root bone for locomotion distance if the project uses root motion; otherwise keep the root stationary and move in the engine.
- Retargeting: UE5 IK Retargeter maps chains between skeletons; export the same rest pose to avoid offsets.

## 8. Importing (UE side)
Recent UE5 versions are moving from the legacy FBX importer to the **Interchange** framework; dialog names differ. What to set regardless of importer:
- Static mesh: *Combine Meshes* off if you export several assets in one file; *Generate Lightmap UVs* only if needed; *Normal Import Method*: **Import Normals** (or **Import Normals and Tangents** when you baked with MikkTSpace and want exact match); *Import Mesh LODs* on; *Auto Generate Collision* off if you provide `UCX_/UBX_`.
- Skeletal mesh: choose/create the Skeleton, enable *Import Morph Targets* if shape keys exist; materials: don't import; textures imported separately.
- Epic's own Blender tools (e.g. "Send to Unreal") can automate export + import - check the current repository/docs before relying on them.

## 9. Verification (do this on the first asset of each type)
- [ ] Size vs Mannequin correct; pivot where intended; no unexpected rotation/scale in the Static Mesh Editor
- [ ] Normal map lighting right (bumps not inverted); no seam lines; tangents consistent
- [ ] Collision shows (Show -> Collision) and is convex where required
- [ ] LODs switch correctly; sockets present; material slot names sensible
- [ ] Skeletal: stress poses deform well; no extra root bone; morph targets listed; animation plays at correct speed
- [ ] Texture sRGB/compression flags correct; ORM channels read as AO/Roughness/Metallic

## 10. Automation (UE Python) - UNTESTED TEMPLATE (needs the Unreal Editor; legacy FBX importer API)
```python
import unreal
task = unreal.AssetImportTask()
task.filename = r"C:/Export/SM_Crate.fbx"
task.destination_path = "/Game/Props/Crate"
task.automated, task.save, task.replace_existing = True, True, True
ui = unreal.FbxImportUI()
ui.import_mesh, ui.import_as_skeletal = True, False
ui.import_materials = ui.import_textures = False
task.options = ui
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
```
In sessions where an Unreal MCP skill is available, delegate in-editor work to it (spawn actors, set materials, import) rather than hand-writing this.

## 11. Troubleshooting
| Symptom in UE | Cause | Fix |
|---|---|---|
| Mesh 100x too big/small | unit scale / apply-scale option mismatch | scene unit scale 1.0, `FBX_SCALE_ALL`, `apply_unit_scale=True`; never "fix" by scaling the actor |
| Skeleton rotated -90°/scaled 100 | armature exported with scale/rotation | apply; `FBX_SCALE_ALL`; armature object at identity |
| Extra "Armature" root bone | armature object imported as a node | name object `Armature`, ensure your own `root` bone, leave `armature_nodetype` default; verify with retargeter |
| Smooth/flat shading wrong | smoothing not exported / normals recomputed | `mesh_smooth_type='FACE'`, import normals, not "compute" |
| Normal map looks inverted | OpenGL vs DirectX | bake `--target ue` or flip green |
| Faceted shading after import | tangents recalculated differently | triangulate before bake, MikkTSpace, import normals+tangents |
| Collision ignored | not convex / wrong prefix / name mismatch | `UCX_<ExactMeshName>_00`, convex, same origin |
| Animation too fast/slow | FPS mismatch | set Blender FPS = UE sequence rate before baking |
| Black/white textures | sRGB flag on data maps | ORM/normal sRGB off, correct compression |
