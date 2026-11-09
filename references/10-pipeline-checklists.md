# Pipelines, stage gates and checklists

Contents: 1 Defaults when the user is vague · 2 Project folders and naming · 3 Asset brief · 4 Stage gates per asset type · 5 Quality gates and thresholds ·
6 Versioning and backups · 7 Effort and risk · 8 Handoff package · 9 Review etiquette

Use this file first for multi-stage requests ("game-ready character", "environment kit", "make this asset for UE5"), then open the stage references.

## 1. Defaults when the user is vague (state them as assumptions)
| Topic | Default |
|---|---|
| Units | metric, 1 BU = 1 m, scale 1.0 |
| Target | real-time PBR (metal/roughness) for Unreal Engine 5 |
| Texel density | 1024 px/m props & environment; characters 512-1024 body, 1024-2048 face/hands |
| Texture size | 2048 per set (4096 for hero/UDIM close-ups) |
| Normal map | DirectX (green down) for UE; OpenGL otherwise |
| Texture packing | BaseColor sRGB · Normal linear · ORM (R=AO G=Roughness B=Metallic) linear |
| Tri budget | small prop 0.5-3k · hero prop 3-20k · weapon 10-40k · stylised character 8-40k · realistic hero 60-150k (Nanite loosens rigid props) |
| Rig for humanoids | Rigify for speed; custom IK/FK for special limbs; export DEF bones only |
| FPS | 30 for UE gameplay unless the project says 24/60 |
| Render | Cycles, 128-256 samples + denoise, AgX |

## 2. Project folders and naming
```
Project/
  00_Reference/   moodboards, concepts, AI generations (+prompt/seed/licence notes)
  01_Source/      .blend working files: Asset_blockout / _high / _low / _bake / _rig / _anim
  02_Export/      FBX/glTF per asset (SM_/SK_/A_), collision & LODs inside
  03_Textures/    bakes, Substance/Painter sources, finals T_*
  04_Renders/     turntables, stills, comp
  05_Docs/        asset briefs, style sheet, QA reports, README per asset
```
File naming: `Asset_Stage_v###.blend` (e.g. `Crate_high_v012.blend`). Engine assets: `SM_Crate`, `SK_Hero`, `A_Hero_Walk`, `T_Crate_BC/N/ORM`, `M_/MI_` (see `04`).
Never overwrite published files; bump versions; keep a `_source.blend` with live modifiers/cutters.

## 3. Asset brief (fill before modelling)
Name · Purpose/where seen (distance, camera) · Platform & budgets (tris, texture sets, texel density, LODs) · Style references (3-5 images + one sentence each) · Dimensions (real-world) ·
Deformation? (static/skeletal/morphs) · Material list · Variants · Deliverables (files, formats, naming) · Owner · Review dates · Licence/provenance notes (esp. AI references).

## 4. Stage gates per asset type
**A. Hard-surface prop (game)**
1. Brief + references -> *gate: budget and style approved*
2. Blockout (primitives, real scale) -> *silhouette reads at thumbnail size* (`01`)
3. High poly (Boolean/bevel stack) -> *`qa_check`: manifold, shading clean*
4. Low poly -> *tri budget, hard edges = seams, triangulated copy*
5. UV (texel density) -> *`qa_check --tex-size --target-td`, no overlap*
6. Bake (Normal/AO/Curvature/ID) -> *no waviness, seams hidden* (`03`)
7. Texture (Substance/Blender) -> *reads under engine lighting*
8. Export + engine test -> *`export_ue5` pre-flight clean, size vs Mannequin, collision OK* (`04`)
9. Handoff package (section 8)

**B. Character**: concept/refs -> blockout -> sculpt -> retopo -> UV/bake -> texture -> rig -> weights -> pose/animation test -> export (`02`, `03`, `06`, `04`).
**C. Environment kit / level**: intent -> paper layout -> greybox playtest -> kit breakdown -> kit production -> assembly/dressing -> lighting -> optimisation (`05`).
**D. Animation shot or cycle**: reference -> thumbnails -> blocking (stepped) -> blocking plus -> splining -> polish -> export/bake (`06`, `04`).
**E. Render / portfolio piece**: concept -> model -> materials -> lighting -> camera -> test renders -> final render -> comp/grade (`09`).
**F. Script/tool**: define input/output -> small working version -> tests with planted defects (`selftest` pattern) -> docs/usage -> version compatibility check (`07`).

## 5. Quality gates and thresholds (tools in `scripts/`)
| Gate | Command / tool | Pass condition |
|---|---|---|
| Topology & scale | `qa_check.py` | 0 ERROR; WARNs justified in writing |
| Budget | `qa_check.py --max-tris N` | within budget (triangulated count) |
| Texel density | `qa_check.py --tex-size S --target-td D` | within ±20 % of target |
| Modular kit | `qa_check.py --grid 1.0` | all pieces on grid |
| UE naming/collision | `qa_check.py --convention ue`, `export_ue5.preflight` | no ERROR |
| Tool integrity | `selftest.py` | ALL PASS on the Blender version used |
| Visual | turntable/clay render, matcap shading check, engine screenshot | no shading artefacts at 3 light angles |

## 6. Versioning and backups
- Blender files are binary: use Perforce, or Git + **Git LFS**; commit `.blend`, exports and textures separately from scripts.
- Save incrementally (`v001`, `v002`...) at every gate; keep one "known good" per gate. Enable Blender auto-save and file versions.
- Keep the **source of truth** (high poly, cutters, rig, Substance project) - exports are derived data and can be regenerated by script.
- Scripts live in the repo, run headless in CI (`blender -b --python-exit-code 1 -P qa_check.py`) to block bad assets.

## 7. Effort and risk (rough planning numbers; very project-dependent)
| Asset | Intermediate artist | Biggest risks |
|---|---|---|
| Hard-surface prop (mid detail) | 1-3 days | scope creep in tertiary detail, bake artefacts, texel density mismatch |
| Stylised character (game) | 1-2 weeks | proportions drift, topology for deformation, weighting time |
| Realistic hero character | 3-8 weeks | likeness/anatomy, hair, skin shading, rig/face complexity |
| Modular environment kit (20-40 pieces) | 2-6 weeks | grid/pivot mistakes, repetition, texel density |
| Walk/run cycle | 0.5-1 day | foot sliding, loop pop, timing feel |
Reduce risk by gating early (silhouette/proportions), testing the **engine round trip with the first piece**, and not polishing before the layout/proportion is approved.

## 8. Handoff package (per asset)
`.blend` source (live stack) · exports (FBX etc.) · texture set with naming + packing note · LOD list · collision notes · QA report (`qa_check --json report.json`) ·
engine settings used (Nanite, compression, sRGB flags) · provenance/licence notes (AI references, third-party assets) · known issues · contact/owner.

## 9. Review etiquette (useful for any team)
Review at gates, not continuously. Give feedback as *problem + evidence + suggestion* ("the shoulder width reads 2.4 heads vs 2.0 target - see overlay"). Attach screenshots with the same camera/lighting. Prioritise: blockers (budget, scale, naming) -> silhouette/proportions -> shading -> polish.
