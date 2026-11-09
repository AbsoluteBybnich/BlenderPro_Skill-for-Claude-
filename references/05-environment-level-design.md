# Environment art and level design

Contents: 1 Order of work · 2 Metrics · 3 Level-design principles · 4 Modular kits · 5 Trim sheets, tileables, blending · 6 Terrain, rocks, foliage ·
7 Art direction and readability · 8 Lighting hand-off · 9 Optimisation · 10 Level brief template · 11 Checklist

Tools: `qa_check.py --grid 1.0` (modular dimensions), `hardsurface.py` (walls/windows/props with Boolean cuts), `export_ue5.py`, `lighting_rig.py` (turntable/preview lights).
Content is general production practice; it does not reproduce any specific course.

## 1. Order of work (each step is a gate; do not skip ahead)
1. **Intent**: what should the player *feel* and *do* here? One sentence. References/moodboard (photos of real places, concept art, 3-5 images with notes on what you take from each).
2. **Paper layout** (top-down sketch): critical path, landmarks, encounter spaces, secrets.
3. **Greybox / blockout in-engine** with primitives at **real metrics** (section 2). Playtest the flow before any art. A bad layout cannot be saved by good props.
4. **Kit breakdown**: list the modular pieces and hero props needed (floors, walls, corners, trims, doors/windows, stairs, columns) from the blockout; count reuse.
5. **Kit production** (modeling, UV, bake, texture) with one texel density and one material system.
6. **Assembly + dressing** (set dressing, decals, vertex paint, storytelling props).
7. **Lighting + post** pass; then **optimisation** and **QA** (collision holes, navmesh, streaming, perf budgets).

## 2. Metrics (decide from *your* character controller; these are starting ranges)
- Measure: player height, eye height, crouch height, step-up height, max jump height and distance, sprint distance, capsule width.
- Architecture (realistic): ceiling 270-300 cm · door 90-100 cm wide x 200-220 tall (games often 120-150 wide for movement) · corridor 200-300 cm · stair riser 15-18 cm, tread 28-30 cm · window sill ~90 cm · waist-high cover 100-110 cm, full cover ≥ 180 cm.
- Gaps and jumps: keep required jumps ≤ ~70 % of the max so players don't fail by pixels; telegraph with lighting/geometry.
- Always place a **scale-reference mannequin** in blockout scenes and Blender files (180 cm).
- Pick a **modular grid** (100 cm is the friendly default; powers of two such as 128/256/512 also common) and never leave it.

## 3. Level-design principles
- **Readability first**: players must know *where to go*, *what is dangerous*, *what is interactive*. Tools: light (brighter = destination), colour accent, silhouette, shape language, sound, leading lines, framing.
- **Landmarks (weenies)**: a big distinctive silhouette visible from multiple points orients the player.
- **Pacing**: alternate compression (tight, tense) and expansion (open, reward/vista); vary vertical rhythm; vary intensity (combat/explore/story).
- **Flow**: critical path is obvious; optional branches reward; loops and shortcuts reduce backtracking. Gate with doors/tools/abilities.
- **Spaces for gameplay**: sightlines, cover distribution, flanking routes, verticality; 'rooms' have an entry, a purpose and an exit.
- **Prototype and playtest early**, with measured metrics. Change the blockout, not the art.
- **Teach, test, twist**: introduce a mechanic safely, test it, then complicate.
- **Performance is level design**: sightlines and streaming cells determine what is drawn; plan occlusion with architecture (doors, corners).

## 4. Modular kits
Why: reuse at scale = fewer unique textures and meshes, faster iteration, consistent look. Done badly it looks repetitive and has gaps.
- **Grid and pivots**: all pieces' dimensions are multiples of the grid (check: `qa_check.py --grid 1.0`); pivot at a corner/bottom-centre consistent across the kit so snapping works in the engine. Wall thickness constant (e.g. 20 cm).
- **Piece families**: floor, wall (solid/window/door), corner (inner/outer), trim (base, mid, cornice), column, ceiling, stairs, roof, props. Design joins first (how wall meets floor/corner) and make trims hide joins.
- **Variation**: 3-5 variants of the most visible pieces, vertex-colour or mask-driven wear, decals, unique hero pieces at focal points, rotation/mirroring where symmetry allows (mirror UVs only if texturing allows).
- **Texel density** identical across the kit; use trim sheets for edges and tileables for surfaces (section 5).
- **Collisions and navigation** per piece (simple boxes), then check seams between pieces for gaps (players catch on them).
- **Instancing**: use instanced static meshes; Nanite handles heavy triangle counts but not overdraw from masked foliage or too many unique materials.
- **Blender workflow**: one `.blend` per kit; each piece in a collection with the pivot at the origin; Asset Browser catalog; export one FBX per piece via `export_ue5.py`; a "kit test scene" assembling every join combination; Geometry Nodes generators for repetitive structures (fences along curves, wall runs) when authored values (height, bay width) are exposed.

## 5. Trim sheets, tileables, blending
- **Trim sheet**: one texture containing horizontal strips of reusable surface details (bevelled metal edge, wood plank, rivet line, cable). UV your pieces onto the strips; benefits: high resolution detail, few textures, cheap. Plan strip heights (e.g. 64/128/256 px on a 2k-4k sheet) and keep the UV straight/rectangular.
- **Tileable materials** (brick, concrete, ground): break repetition with macro-variation masks, UV-scale-mixed layers, texture bombing/stochastic sampling, vertex-colour or height-blend between two materials, and decals for grime/cracks.
- **Vertex painting** (UE) blends material layers on a mesh; keep a clean vertex density in Blender where you need smooth transitions.
- **Decals**: dirt, stains, signage, damage; placed after kit assembly; cheapest way to make repetition look unique.
- Texture scale sanity: bricks real size (~21x6.5x10 cm) at the correct world scale tell the eye the scale of everything.

## 6. Terrain, rocks, foliage
- **Terrain**: engine landscape tools for large terrain; Blender for hero cliffs/rock formations that need unique silhouettes.
- **Rocks/cliffs**: sculpt big forms -> decimate/retopo -> bake normal/AO/curvature -> tile triplanar materials in-engine; use a few variants (3-5) rotated and scaled; Nanite fits well.
- **Foliage**: alpha cards cost overdraw; build 2-3 LODs, billboards at distance; scatter with Geometry Nodes (Blender) or the engine's procedural content/foliage tools; use density maps and exclusion masks; wind via vertex colour masks.
- **Water, fog, volumetrics**: engine features; Blender provides meshes and vertex data only.

## 7. Art direction and readability
- **Value structure first**: squint (or desaturate) the screenshot; focal areas should have the highest contrast. Squint-test every screenshot.
- **Colour script**: dominant hue + accent + neutral (60/30/10). Temperature contrast guides the eye (warm destination in a cool corridor).
- **Depth layering**: foreground (dark framing), midground (action), background (atmospheric haze, lower contrast).
- **Storytelling through props**: wear, tracks, objects arranged by cause (someone lived/fought/left).
- **Scale cues**: repeating human-scale elements (doors, railings, chairs) so players read size.
- **Consistency**: shape language, bevel language, texel density, wear level, colour palette must agree across all authors - document them in a one-page style sheet.

## 8. Lighting hand-off (see `09`)
Light the blockout early with placeholder lights to validate readability; final lighting after kit assembly. Use emissive and light shapes to guide, sunlight direction to model forms, fog for depth. Keep one hero light per space.

## 9. Optimisation
- Budgets per scene: draw calls, unique materials (merge into atlases/kit materials), triangles (less critical with Nanite), texture memory (streaming), shadow cost (lights with shadows, overlap), overdraw (foliage, particles, translucent).
- Tools: LODs/HLOD, culling/cull-distance, instancing, texture streaming budgets, profiling (`stat unit`, `stat gpu` in UE), occlusion planning in the level design.
- Fix at the cause: reduce unique materials and overdraw before cutting triangles.

## 10. One-page level brief (template)
Title · Intent (feeling + player goal) · Duration · Beats (sequence of moments) · Metrics (player stats) · Layout sketch · Critical path · Landmarks · Encounters/gameplay spaces · Secrets/optional · Kit list · Style sheet (colour/shape/texel density) · Tech constraints (streaming, perf budgets) · Milestones: greybox -> gameplay complete -> art complete -> lit/polished.

## 11. Checklist
- [ ] Blockout playtested at real metrics, mannequin reference present
- [ ] Kit on grid, pivots consistent, `qa_check.py --grid` clean, joins tested in a kit scene
- [ ] One texel density; trim sheets + tileables + decals, no unique 4k per prop
- [ ] Readability: path, hazards, interactables clear; landmark visible
- [ ] Collisions and navmesh without holes at module joins
- [ ] Performance profiled on target hardware; LOD/HLOD/culling set
