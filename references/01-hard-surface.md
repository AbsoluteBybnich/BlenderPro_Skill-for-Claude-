# Hard-surface modeling (Blender)

Contents: 1 Mindset · 2 Boolean stack workflow · 3 SubD workflow · 4 Bevels · 5 Shading and its artefacts · 6 Add-on workflows
(Hard Ops, Boxcutter, MESHmachine) and vanilla equivalents · 7 Detailing and kitbashing · 8 Modeling for baking · 9 Checklist · 10 Mistakes

Script: `scripts/hardsurface.py` (cutters, Boolean, Bevel, Weighted Normal, sharp-by-angle, apply without ops).

## 1. Mindset
- **Read order of a hard-surface object**: silhouette -> primary forms -> secondary (panels, big cuts) -> tertiary (screws, seams, wear).
  Block out in that order; never model tertiary detail before the silhouette reads at thumbnail size.
- **Bevels are the lighting.** Real edges are never perfectly sharp; the highlight a bevel catches is what makes CG read as a
  physical object. Bevel every edge the eye can touch; vary width by part size (large edges wider, small details tiny).
- **Real-world scale first** (1 BU = 1 m). Panel gaps 2-5 mm, fillets 1-3 mm, bolt heads 8-24 mm. Wrong scale = wrong look at any polycount.
- **Function justifies form.** Cuts, vents and hinges should look like they do something; random greebles read as noise.
- **Density contrast.** Pair busy areas with quiet areas (rule of thirds for detail). Uniform detail = visual mud.

## 2. Boolean / modifier-stack workflow (mechanical parts)
Order matters; a good default stack is:
`Mirror -> Boolean(s) -> Bevel -> Weighted Normal -> (Triangulate last, only for export)`
1. **Block out with primitives** at real size (cube/cylinder). Keep each part its own object; parent cutters to the part.
2. **Cutters**: separate objects in a `Cutters` collection, display *Wire/Bounds*, `hide_render`, not selectable if you like.
   Make cutters **longer than the cut** so no faces are coplanar with the target (coplanar faces = Boolean artefacts).
   Arrays/mirrors *on the cutter* keep repeated holes editable (see `hardsurface.build_demo`).
3. **Solver** (names differ by version, `hardsurface.boolean` maps them):
   - `EXACT` - robust with overlaps and self-intersections, slowest; default for finals and complex cuts. `use_self` for overlapping cutters,
     `use_hole_tolerant` when the result has thin gaps.
   - `MANIFOLD` (4.5+) - fast, requires closed, manifold operands; great for interactive work.
   - `FLOAT` (older `FAST`) - fastest, fine for simple cuts, fails on coplanar faces and near-touching geometry.
4. **Bevel after the Booleans** so the cut edges get filleted. Limit method **Angle** (30-40 deg) needs no prep; **Weight** (attribute
   `bevel_weight_edge`) is art-directed; **Vertex group** for localized control.
5. **Weighted Normal** last of the shading modifiers (see section 5).
6. Apply only when needed: bake, export, sculpt, or when the modifier stack gets slow. Apply with `hardsurface.apply_modifiers(obj)`
   (no ops needed, strips the phantom empty material slot Booleans leave behind).
7. After applying, run `qa_check.py`: expect 0 non-manifold edges. Booleans leave n-gons on flat caps: fine for static hard-surface,
   must be fixed (or triangulated) if the mesh will be subdivided or deform.

Boolean failure triage: (a) non-manifold/open operand -> fix or switch solver; (b) coplanar faces -> make the cutter overshoot;
(c) scale/rotation unapplied on the cutter -> apply; (d) overlapping cutters with FLOAT -> use EXACT + `use_self`; (e) tiny sliver faces -> raise
`double_threshold` slightly or nudge the cutter by 0.1 mm.

## 3. SubD / support-loop workflow (sleek, curvy hard-surface: vehicles, consumer products, armour)
- Model low-poly cage -> Subdivision Surface level 2-3 for display. Control sharpness with **support loops** (two close edge loops hold an edge tight)
  or **edge crease** (`crease_edge` attribute, 4.0+). Creases are non-destructive and keep topology light; loops give more predictable shading.
- No n-gons, no poles on flat/high-visibility areas; put 5-poles where the surface is nearly flat or hidden.
- Use **Mirror** with *clipping* + merge threshold ~0.0001 m; fix the centre seam normals (Weighted Normal / data transfer).
- Choose SubD when forms are *organically hard* (compound curvature). Choose Booleans when forms are *mechanical* (flat panels, cylinders, slots).
  Hybrid (SubD body + Boolean details applied on the SubD result) is common: finish the body, apply, then cut details.

## 4. Bevel numbers (rules of thumb at 1 BU = 1 m)
| Situation | Width | Segments | Notes |
|---|---|---|---|
| Fine panel line / chamfer on small parts | 0.5-2 mm | 1-2 | game-res low poly: 1 segment (chamfer) |
| Standard hero edge | 2-6 mm | 3 | profile 0.5; most "CG realistic" edges |
| Large visible fillet / rounded housing | 10-30 mm | 4-8 | profile 0.5-0.7; use SubD if the surface is curved |
| Sharp-but-not-razor on blades, glass edges | 0.2-0.5 mm | 1-2 | still bevelled - zero is never right |
- **Miter outer: Arc** for clean corners; **Miter inner: Sharp**; enable *Clamp overlap*; *Harden normals* only if you are not using Weighted Normal.
- Bevel width relative to part: ~0.3-1 % of the longest dimension for primary edges. If bevels look too uniform, drive secondary parts at 50 % width.
- Game-res: keep bevels as *geometry only where silhouette/shading needs it*; the rest is normal-map. Hi-poly for baking: segments 3-4, width generous.

## 5. Shading and artefacts
- Blender 4.1+ has **no Auto Smooth checkbox**. The recipe: shade smooth, mark **sharp edges** where angle > ~30 deg
  (`hardsurface.mark_sharp_by_angle` or `object.shade_smooth_by_angle`), add **Weighted Normal** (mode Face Area, weight 50, *Keep Sharp*).
  Result: flat panels stay flat, bevels shade cleanly, no per-edge hand-tuning.
- Typical artefacts and fixes:
  | Symptom | Cause | Fix |
  |---|---|---|
  | Dark wedge/pinching across a flat face | n-gon or triangle fan on a curved normal field | Weighted Normal; dissolve limited; or add a few edge loops |
  | Wavy highlights on a flat plate | non-planar quad / unevenly distributed verts | flatten (`Scale 0 Z`), even the loops, Weighted Normal |
  | Gradient across a cylinder cap | cap n-gon with smooth normals | mark cap boundary edges sharp |
  | Black faces after mirror | negative scale or flipped normals | apply scale, Recalculate Outside |
  | Bevel breaks on thin parts | width > thickness/2 | reduce width, use *Clamp overlap* |
- Triangulate **only as the final step** for export/bake (`keep_custom_normals=True`); triangulating earlier makes editing worse.

## 6. Add-on workflows (paid, interactive - cannot run headless)
Detect what is installed: `list(bpy.context.preferences.addons.keys())`. Lineages (names as users know them; hotkeys/menus change per
version - always defer to the add-on's current docs):

| Add-on | What it automates conceptually | Vanilla Blender equivalent |
|---|---|---|
| **Hard Ops** | one-menu access to: mark sharp + bevel weight, set bevel width/segments live, Boolean ops (difference/union/slash/inset) with non-destructive cutters, array/mirror helpers, clean n-gon tools, "sharpen" presets | `mark_sharp_by_angle` + Bevel (limit=Weight/Angle) + Boolean modifiers + Weighted Normal (see `hardsurface.py`) |
| **Boxcutter** | draw 2D shapes (box/circle/n-gon) directly on a surface, set depth, choose operation (cut / slice / inset / join / knife / make / extract) | create cutter object + Boolean (`hardsurface.make_cutter`, `boolean`); Knife Project for 2D line cuts; Inset/Extrude for panels |
| **MESHmachine** | topology-level surgery: *plugs* (reusable boolean-ready detail pieces), chamfer/fuse/unfuse/refuse surfaces with controlled flow, unbevel/unchamfer, flatten, normal transfer/straighten | Bevel (vertex-only / edge) + Merge/Dissolve + Data Transfer (custom normals) + Shrinkwrap; Asset Browser for reusable parts |
- Typical combined flow: Boxcutter (rough cuts) -> Hard Ops (sharpen, bevel, clean) -> MESHmachine (fix shading seams, plug in details). The point is *speed
  of iteration*; the output is still ordinary meshes/modifiers, so the vanilla route yields the same result with more clicks.
- Without the add-ons give the user the vanilla steps first; mention add-ons as accelerators, never as requirements.

## 7. Detailing and kitbashing
- **Hierarchy of scale**: ~3 sizes of detail (large/medium/small, ratio ~1:3:10). Detail only where function or focal interest justifies it.
- **Instancing**: linked duplicates (`Alt+D`) or collection instances for repeated parts (bolts, vents). One edit updates all; low memory.
- **Kitbash libraries**: keep a catalogued Asset Browser library (bolts, vents, hinges, pipes, panels) at real scale with origins at the mounting point.
  Re-skin kit parts with a consistent bevel width so they feel like one object.
- **Decals / trim sheets** for tertiary detail (panel lines, labels, wear) - far cheaper than geometry in real-time; geometry detail only if it breaks the silhouette.
- **Wear logic**: edge wear where things get touched/hit (bevel edges, corners), dirt in crevices (AO/curvature), streaks following gravity. Bake curvature/AO to drive masks.
- **Geometry Nodes** for scatter (rivets along a curve, greeble fill) once the manual approach is proven; keep it controllable (seed, density, mask).

## 8. Modeling for baking (game/real-time)
- Make **high** (bevelled, all details, may have floaters/intersections) and **low** (clean silhouette, support edges on curved parts).
- Low-poly hard edges: split smoothing at hard edges and **UV-seam them** so the normal map has no gradient across a hard edge.
- Keep small details out of the low unless they affect silhouette. Float details above the surface (no need to weld) for bake only.
- Triangulate low before baking; name `*_low` / `*_high`; explode overlapping parts if rays cross-contaminate. See `03-retopo-uv-bake.md`.

## 9. Checklist
- [ ] Real-world scale, scale/rotation applied, origin at a meaningful pivot
- [ ] Silhouette reads; no unmotivated detail; consistent bevel language
- [ ] 0 non-manifold edges (`qa_check.py`); n-gons only on flat static faces
- [ ] Shading clean from 3 light angles (rotate a light or use MatCap); no pinching
- [ ] Cutters/modifiers kept in `_source` version; export version applied + triangulated
- [ ] Names: `SM_` prefix etc. if going to UE (see `04`)

## 10. Common mistakes
Bevelling before booleans (cuts stay sharp) · coplanar cutters · uniform bevel width everywhere · trusting FLOAT solver on tight tolerances ·
applying modifiers too early (lose editability) · modelling bolts as 2000-poly cylinders · ignoring normals/shading while chasing wireframe cleanliness.
