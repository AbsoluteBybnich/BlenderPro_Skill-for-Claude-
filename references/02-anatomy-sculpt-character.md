# Anatomy, sculpting and character creation

Contents: 1 Proportions · 2 Surface landmarks and muscle groups · 3 Head and face · 4 Hands and feet · 5 Gesture and balance ·
6 Sculpting workflow in Blender · 7 Stylized characters · 8 Topology / edge flow for deformation · 9 Eyes, hair, clothing ·
10 Character pipeline · 11 Review checklist

Script: `scripts/reference_setup.py` (4 orthographic reference views aligned to real height + 8-head proportion guide).
Rules of thumb below are *canon for judging*, not law - real bodies vary and stylization breaks them on purpose, but only deliberately.

## 1. Proportions (adult, in head heights)
- Idealised/heroic figure: **8 heads**; average person ~7-7.5; stylised 3-6; chibi 2-3. Children: newborn ~4, toddler ~4.5, 6-year-old ~6, teen ~7.
- Measured from the top (8-head canon): chin 1 · nipples 2 · navel/elbows ~3 · crotch ~4 (body midpoint) · fingertips reach mid-thigh with arms hanging · knees ~6 · feet 8.
- Arm span ≈ height. Shoulder width ≈ 2 heads (male), ~1.5-1.75 (female). Hand ≈ face length (chin to hairline). Foot ≈ 1 head long.
- Male/female differences that matter for silhouette: shoulders vs hips (male wider shoulders, female hips ≈ shoulders), ribcage size, waist position, muscle mass, neck thickness.
- Build the proportion guide first: `reference_setup.proportion_guide(height_m=1.8, heads=8)` and align front/side references to the **same** height and Z=0 feet.

## 2. Surface landmarks (bones that show) and muscle groups
Landmarks are where skin sits directly on bone - they are the measuring stakes of the figure:
- Torso: sternal notch, clavicles, acromion (shoulder tip), C7 (neck/back bump), spine of scapula, iliac crest and ASIS (front hip points), sacral dimples.
- Arm: olecranon (elbow point), radial and ulnar styloid (wrist bumps), knuckle arc.
- Leg: patella, tibial crest (shin edge), tibial tuberosity, malleoli (inner ankle higher than outer).
Muscle groups to sculpt as *shapes with a function*, not as anatomy-chart detail:
- Neck/shoulder: sternocleidomastoid, trapezius, deltoid (three heads wrap the shoulder).
- Torso: pectoralis major, serratus anterior, rectus abdominis + obliques, latissimus dorsi, erector spinae.
- Arm: biceps/brachialis, triceps, brachioradialis (forearm top mass), flexor mass (inner) vs extensor mass (outer).
- Leg: glutes, quadriceps (rectus femoris + vastus lateralis/medialis), hamstrings, adductors, sartorius line, gastrocnemius + soleus, tibialis anterior.
Sculpt rule: **mass first, then the dominant 5-8 muscles, then transitions, then tiny fibres**. Overdefined anatomy on a stylised character looks wrong.
Muscles change with pose (relaxed vs flexed) and age/sex/body type - decide the body type before sculpting.

## 3. Head and face
- Skull planes: cranium, brow ridge, orbit, zygomatic arch/cheek, nasal bones, maxilla, mandible (jaw angle), chin. Sculpt the **skull first**, then add soft tissue.
- Frontal landmarks: eye line ≈ halfway down the head; eyes ≈ 1 eye-width apart; face width ≈ 5 eye-widths; nose base halfway eye-line -> chin; mouth ≈ 1/3 from nose base to chin;
  ear top ≈ brow, ear bottom ≈ nose base. Thirds: hairline-brow, brow-nose base, nose base-chin.
- Profile: the face sits in front of the ear; neck angles forward from the skull; Frankfurt plane level.
- Details that sell realism: eyelid thickness (upper lid overhangs), tear ducts, lip volume with philtrum, nostril wing shape, asymmetry (never perfectly symmetrical in the final).

## 4. Hands and feet
- Hand: palm ≈ square; finger lengths follow an arc at the knuckles and an arc at the tips; thumb base (thenar mass) is a big wedge; fingers taper and are not cylinders (flat on palm side).
- Feet: arches (medial longitudinal), toe length order varies; ankle bones as above. Both are the first places a model looks amateur - block them with box shapes, then refine.
- Game characters: mitten hand (thumb + one block) is a valid LOD; reserve full fingers for hero/close-ups.

## 5. Gesture and balance
- Start with a **line of action** (C/S/I curve) before volumes. Poses without a line of action read stiff.
- Contrapposto: weight on one leg -> hips tilt one way, shoulders counter-tilt, spine S-curves. Ribcage and pelvis are two rigid masses joined by a flexible spine; they move opposite.
- Weight: centre of mass over the supporting foot; check from the front/side that a plumb line from the pit of the neck falls near the weight-bearing ankle.

## 6. Sculpting workflow in Blender
Order of operations (works in Blender, ZBrush and Nomad alike): **primary -> secondary -> tertiary**.
1. **Base**: low-res mesh (Voxel Remesh with a large voxel size, or a Skin-modifier armature, or a box-modeled body). Symmetry on.
2. **Primary forms** (silhouette, proportions): big brushes - *Grab / Move / Clay Strips / Elastic Deform / Pose* - low resolution, view from front/side/top constantly. Do not add detail until the 8-head check passes.
3. **Increase resolution as the form earns it**: Voxel Remesh at progressively smaller voxel sizes, or Multires levels, or Dyntopo (detail size relative, ~8-12 px).
   - *Voxel Remesh*: uniform topology, loses nothing important, resets face sets/masks - best for form changes. 
   - *Dyntopo*: adds detail only under the brush - fast for detail passes, triangulates.
   - *Multires*: keeps a base-mesh topology (good for later bake and reprojection) but can't change large forms cleanly beyond the base.
4. **Secondary forms**: muscle groups, ribcage, brow, mouth planes. *Clay Strips, Draw, Crease, Smooth, Flatten/Scrape*.
5. **Tertiary**: skin pores, wrinkles, scars via small brushes or alpha/noise textures; keep micro-detail for the normal map, not geometry.
6. **Polish**: symmetry break (subtle), cloth folds, tension lines.
Blender specifics: `F` radius, `Shift+F` strength, `Ctrl` inverts the brush, `Shift` smooths; **Mask** and **Face Sets** isolate regions; the **Pose** brush re-poses a limb without breaking proportions;
since 4.3 brushes are *assets* (Essentials library) so presets are chosen from the asset shelf. Use a pressure tablet if you can; otherwise lower strength and stroke more.
Habits: rotate constantly, work at the lowest resolution that does the job, save versions at each stage (`_sculpt_v01..`), check the silhouette in a flat-colour matcap.

## 7. Stylized characters
- **Shape language**: circles = friendly/soft, squares = stable/strong, triangles = dynamic/dangerous. Pick a dominant shape and echo it in the silhouette, hair, clothing.
- **Silhouette test**: fill black; if you cannot tell who/what it is, redesign. Distinguish characters by silhouette first, colour second.
- **Exaggerate deliberately**: head 1/3-1/4 of height for cartoony, big hands/feet for readability, thick limbs; simplify forms into big-medium-small (1:3:10).
- **Costs of stylisation**: the less realistic, the more consistent the design language must be (same bevel/roundness, same stroke weight in texture).
- **Box-modeling beginner path** (common in beginner low-poly courses): reference in front/side -> half-body box with Mirror + Subdivision -> extrude limbs from torso -> separate head, hands, shoes as clean shells -> add loops only where needed -> unwrap -> hand-paint or vertex colour.
  Keep quads, uniform density, proportions from the reference grid.
- **Texturing for stylised**: hand-painted gradients + hard shadow shapes baked into colour; limited palette (≤ 8 colours per character); rim colour accents.

## 8. Topology / edge flow for deformation
- **Rule**: edge loops follow the *direction of muscle fibres and the lines of skin movement*; put extra loops where joints bend and where expressions deform.
- Face: concentric loops around eyes and mouth (orbicularis), loops for nasolabial fold, horizontal forehead loops, jaw-line loop, nostril loop. Poles (5-star / 3-star) away from high-stress areas (cheek and temple are common homes).
- Body: 2-3 loops across elbow/knee/knuckles/wrist (extra on the inside of the bend); shoulder: loops radiate around the deltoid and arm-pit; torso: waist loops, hip star.
- Quads in deforming areas; triangles tolerated in flat/hidden zones and for LOD. Uniform quad size where stretch is uniform.
- Budgets (rough, project-dependent): mobile stylised character 3-10k tris; PC/console stylised hero 15-40k; realistic hero 60-150k (body+head+clothing); LOD1 ≈ 50 %, LOD2 ≈ 25 %.
- Retopo methods and bake details: `03-retopo-uv-bake.md`.

## 9. Eyes, hair, clothing
- **Eyes**: separate spheres for eyeball (sclera + iris) with a transparent cornea shell; place pupil depth; eyes drive the "alive" read - add slight reflections.
- **Hair**: game = hair cards (alpha-textured strips, layered from scalp outward, 3-5 layers) or curves/Geometry Nodes hair in Blender for renders; model the hair *mass shape* first.
- **Clothing**: separate shells (don't copy the body), thickness offset (1-3 mm for skin-tight, more for coats), cloth-simulate big folds then retopo or sculpt the rest; seams & stitching as normal-map detail.
- **Accessories** as separate objects with clean origins for swapping.

## 10. Character pipeline (typical stages; each ends with a gate)
1. Concept/reference (turnaround, mood, proportion decisions; see `08` for AI-assisted reference) - gate: silhouette & proportion approved.
2. Blockout (primitives/low sculpt, scale, T/A-pose) - gate: reads at thumbnail size, polycount budget set.
3. High-poly sculpt - gate: anatomy/stylisation consistent, symmetry broken subtly.
4. Retopology - gate: loops at joints & face, budget met, quads.
5. UV + bake (normal/AO/curv/ID) - gate: no stretching, consistent texel density (face/hands higher), clean bakes. See `03`.
6. Texturing - gate: reads in engine lighting, material IDs correct.
7. Rig + skin weights - gate: stress poses (arm raise, deep squat, head turn) deform cleanly. See `06`.
8. Pose/render or engine integration - gate: `qa_check.py`, export test (`04`).
Rough effort for one stylised game character by an intermediate artist (highly variable): reference 2-4 h · blockout 2-4 h · sculpt 8-20 h · retopo 4-8 h · UV 2-3 h · bake/texture 8-16 h · rig 4-8 h · weights 3-6 h.

## 11. Review checklist (anatomy and form)
- [ ] Proportions measured against the head-unit grid in front **and** side
- [ ] Silhouette from front/side/3-4 reads; gesture has a line of action
- [ ] Flip the canvas horizontally and compare (errors jump out)
- [ ] Landmarks present at correct heights; joints placed on bones not mid-muscle
- [ ] Muscle masses overlap and flow (no isolated "lumps"); transitions soft where fat/skin, crisp where tendon/bone
- [ ] Hands/feet intentionally designed, not afterthoughts
- [ ] Subtle asymmetry in final; micro detail deferred to maps
- [ ] Topology shows loops at all deformation zones; budget respected
