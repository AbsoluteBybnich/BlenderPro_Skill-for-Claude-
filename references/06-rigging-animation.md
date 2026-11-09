# Rigging and animation

Contents: 1 Rig philosophy · 2 Rigify quick path · 3 Custom IK/FK limb · 4 Body mechanics · 5 Face rigging · 6 Skin weights ·
7 Rig acceptance tests · 8 Animation principles and workflow · 9 Timing tables · 10 Walk cycle recipe · 11 Blender animation tooling · 12 Export notes

Scripts: `rig_ikfk.py` (IK/FK limb, snapping, auto-weights, Rigify, shape-key driver, eye aim) · `anim_helpers.py` (bouncing ball, key shift, cyclic, fcurve access across versions) · `export_ue5.py` (skeletal/animation FBX).
All verified on Blender 5.2.3 LTS: IK reaches its target, FK drives deform bones, IK<->FK snap error 0, blink driver maps 0-0.02 m to 0-1, eyes aim exactly.
The principles condense widely-taught practice (rigging-for-animators courses, face/IK-FK quick guides, *The Animator's Survival Kit*); they are not quotations.

## 1. Rig philosophy
- **A rig is a tool for animators, not a showpiece.** Fewer, clearer controls beat more. Every control must have an obvious purpose, a consistent colour (left/right/centre), a good custom shape, and sit where the animator expects it.
- **Separate deformation from control.** DEF bones carry skin weights and are driven by constraints; control bones are what animators touch. You can rebuild controls without re-skinning, and engines receive only DEF bones.
- **Clean transforms**: bones at scale 1, armature at origin, rest pose symmetrical and in a neutral A/T pose, no negative scale. Use `.L/.R` suffixes so mirroring/pose-flip works.
- **Rotation modes**: Quaternion for roots/spine/free joints (avoids gimbal), Euler (XYZ/ZXY) for hinge joints where you want clean F-curves; lock channels animators should not touch.
- **Keep it fast**: minimal constraints/drivers per bone, no dependency cycles, avoid heavy Python drivers; test playback at target FPS.
- Decide early: **Rigify (fast, standard), custom (full control), or hybrid** (Rigify body + custom face).

## 2. Rigify quick path (≈ minutes for a standard biped)
1. Enable the Rigify add-on. Add -> Armature -> **Human (Meta-Rig)**.
2. Edit Mode: scale/move meta-rig bones to fit your mesh (use X-mirror; move heads/tails, avoid rolling randomly; fingers and spine joint positions matter most).
3. Object Data -> Rigify -> **Generate Rig** (scripted: `rig_ikfk.generate_rigify_human()` for the default meta-rig; verified headless, ≈700 bones).
4. Select the mesh, then the generated rig -> Parent **With Automatic Weights** (weights go to the `DEF-` bones; control bones are not deform).
5. Pose-test (section 7), fix weights, then bake/export only DEF bones for engines (the Rigify DEF skeleton is not identical to the UE Mannequin; retarget with UE5's IK Retargeter or use a game-oriented Rigify variant/Epic's tools - verify current options).
6. Re-generate whenever the meta-rig changes; never hand-edit the generated rig you intend to regenerate.

## 3. Custom IK/FK limb (`rig_ikfk.build_ik_fk_limb`)
Structure created: `DEF-<p>.upper/.lower/.hand`, `FK-...`, `IK-...`, `IK-<p>.target`, `IK-<p>.pole`, `SW-<p>` (holds custom property `ik_fk` 0..1).
- A driver on the second Copy-Transforms constraint blends FK->IK per DEF bone, so animators can switch (or blend) at any time.
- **Pole target**: placed on the bend side automatically; the script calibrates `pole_angle` numerically so the rest pose is preserved. The limb must be *slightly bent* in the rest pose (1-5 % off the straight line) or the solver has no preferred plane - the script rejects a perfectly straight limb.
- **Snapping**: before switching modes call `snap_ik_to_fk` (pose in FK, then match IK controls) or `snap_fk_to_ik`. Without snapping the limb pops. Rigify provides snap buttons; for custom rigs expose them as operators/buttons.
- Extensions to add when needed: stretch (scale along bone with limits), twist bones (forearm/upper arm), IK-FK lock, finger-curl custom property driving all finger joints, hand space-switch (parent to world/body/head).
- Pole vector rules: elbow pole behind the elbow, knee pole in front of the knee, on the same plane as shoulder-elbow-wrist; keep it ~ limb-length away to avoid flips.
- Pitfall list: moving `pose_bone.location` is in local bone axes (use `pose_bone.matrix` to place in armature space); custom-property edits from Python need `obj.update_tag()` for drivers to refresh (`set_ik_fk` does this).

## 4. Body mechanics
- **Spine**: FK chain with optional IK/Bezier curve; hips and chest controls independent (ribcage and pelvis counter-rotate).
- **Neck/head**: head rotation can inherit from chest or be world-space (space switch) - animators need both.
- **Legs**: IK with **reverse-foot** (heel, toe tip, ball pivots with roll custom property) for stable foot plants; foot controller at ground; knee pole.
- **Arms**: IK for pushing/holding/weapons, FK for swings/gestures; clavicle controls for shrugs; shoulder bone separate from arm.
- **Fingers**: bone chains with a single "curl" slider (custom property -> drivers) plus individual overrides.
- **Root**: a root bone at the origin (world position) separate from the hips so you can move the character as a whole and do root motion.

## 5. Face rigging (bones, shape keys, or both)
| Approach | Strengths | Weaknesses | Use for |
|---|---|---|---|
| Bones only (jaw, lids, brows, cheeks, lip corners, tongue) | cheap, performant, game-friendly | limited shape control, needs good weights | game characters, stylised faces |
| Shape keys only (visemes, expressions, FACS/ARKit) | exact shapes, art-directed | many keys, memory, harder to extend | realistic, MetaHuman-like, mocap targets |
| **Hybrid**: control bones/sliders drive shape keys via drivers | best animator UX + exact shapes | more setup | most production faces |
Recipes:
1. **Jaw**: one bone, rotation X limited (≈ 0-25°); skin weights smooth around the chin/mouth; lower lip follows.
2. **Eyes**: eye bones with `rig_ikfk.add_eye_aim(arm, "eye.L", "eye.target")` so a single target bone controls gaze; eyelids follow eye rotation via drivers/constraints (upper lid follows more than lower).
3. **Blink / brows / smile by sliders**: create shape keys (`Blink_L`, `Brow_Up_L`, `Smile`...); make a slider bone limited to a tiny local-Z range (Limit Location 0..0.02 m); drive with `rig_ikfk.drive_shape_key_from_bone(face, "Blink_L", arm, "ctl.blink.L", "LOC_Z", lo=0, hi=0.02)` (verified 0->0, 0.01->0.5, 0.02->1, clamped).
4. **Visemes** (A/E/I/O/U, M/B/P, F/V, etc.): 8-12 shape keys covers lip-sync; combine with jaw rotation for scale.
5. **Corrective shapes** for extremes (lip corners with jaw open) driven by combined bone values.
6. Keep face rig controls on a clean UI (custom bone shapes arranged like a face, or a Python panel) so animators never hunt for them.
Topology reminder: concentric loops around eyes/mouth are what make these deform well (`02`).

## 6. Skin weights
- Start with automatic weights; then **clean up**: normalise all, limit to 4 influences per vertex for game targets, remove tiny weights (<0.01), mirror weights (X-axis topology mirror), and use the weight gradient tool for broad blends.
- Problem zones: shoulders, hips, elbows/knees, neck, twist of forearm/thigh. Fixes: extra topology loops, twist bones, corrective shape keys, helper bones, Corrective Smooth modifier (renders), dual quaternion skinning (watch for bulging).
- Hard-surface/mechanical parts: weight 100 % to one bone; avoid spreading to neighbours (no squishy armour).
- Weights live in vertex groups named exactly like the DEF bones; renaming a bone without renaming its group breaks deformation.

## 7. Rig acceptance tests (do before animators see it)
- [ ] Range-of-motion pose set: arms up/down/forward/back, deep squat, torso bend/twist, head turn/tilt, finger curl; no pinching/candy-wrapper
- [ ] IK/FK switch at 0, 0.5, 1 with snapping: no pop
- [ ] Left/right symmetrical behaviour; pose copy/paste flipped works
- [ ] No scale on bones, no gimbal in normal use, no dependency cycles, playback at full FPS
- [ ] Export test: FBX has only DEF bones, correct root, A/T pose, scale 1 (`export_ue5.py`)

## 8. Animation principles and workflow (Animator's Survival Kit lineage)
The 12 principles, with how to apply them in 3D:
1. **Squash & stretch** - volume preservation conveys flexibility/weight; subtle in realistic, strong in cartoony (`anim_helpers.bounce_ball`).
2. **Anticipation** - a small opposite move before the main action (2-6 frames); bigger action -> bigger anticipation.
3. **Staging** - one clear idea per shot; silhouette readable; camera and pose support it.
4. **Straight-ahead vs pose-to-pose** - 3D is mostly pose-to-pose: key poses, breakdowns, in-betweens.
5. **Follow-through & overlapping action** - parts lag the body and settle after it stops (tails, hair, cloth, hands, head); offset curves by 1-3 frames (`anim_helpers.shift_keys`).
6. **Slow in & slow out** - more frames near extremes, fewer in the middle; spacing is the language of weight (see the bouncing-ball test: spacing tight at apex, wide near the floor).
7. **Arcs** - natural motion follows curved paths; check with motion paths / ghosting.
8. **Secondary action** - supports the main action (blink, breath, finger twitch).
9. **Timing** - frame counts set weight, speed and mood (section 9).
10. **Exaggeration** - push poses and timing beyond naturalism, within the style.
11. **Solid drawing (solid posing)** - volume, weight, balance, clear silhouettes in 3D.
12. **Appeal** - clear, interesting, believable character in pose and motion.
Williams' vocabulary: **key** (story-telling pose), **breakdown** (defines the arc/path between keys), **in-between**; **spacing** charts show how drawings are distributed on a path.
Workflow (shot): reference (video/acting) -> thumbnails/line of action -> **blocking** (stepped/CONSTANT keys on story poses; judge timing here) -> **blocking plus** (breakdowns, overlap, arcs) -> **splining** (switch to Bezier, fix curves) -> **polish** (offsets, micro-motion, facial, contact points). Do not spline before timing and poses are approved.

## 9. Timing and spacing rules of thumb (24 fps unless stated; scale for other frame rates)
- One second = 24 frames; animating "on ones" (every frame) for fast actions, "on twos" for most body animation in stylised work, "on threes" for slow/limited.
- Half the frames between the same two poses = double the speed; halving the interval is the quickest way to check the timing feel.
- Anticipation 2-6 frames · hold on a readable pose ≥ 6-8 frames (≈ ¼-⅓ s) for the audience to register · overlap offsets 1-3 frames · eye dart 2-3 frames · blink ≈ 4-6 frames total (close ~2, open ~3).
- Heavy things: slow start (long ease out of the first pose), fast through the middle, abrupt stop with a little settle; light things: quicker start, floaty ease.
- Lip-sync: key mouth shapes to *dominant vowels/consonants*, start shapes 1-2 frames before the sound; not every phoneme.
- Frame-rate changes mean re-timing: do not just change FPS in a finished shot; set the rate first (24/30/60) to match the project/engine.

## 10. Walk cycle recipe (biped, side-view logic; "contact, down, passing, up")
Classic structure for a **normal walk**: ~12 frames per step, 24 frames for a full left+right cycle at 24 fps.
| Frame | Pose | Notes |
|---|---|---|
| 1 | **Contact** (front heel strikes) | legs max spread, arms swung opposite to legs, body at mid height |
| 4 | **Down** (weight settles) | front knee bends, body lowest point, back foot still on ground |
| 7 | **Passing** (free leg swings through) | support leg straight under body, free leg passes it, body rising from the Down pose |
| 10 | **Up** (push off) | push-off toe, body high point, front foot reaching |
| 13 | **Contact** (opposite foot) | mirror of frame 1; repeat to frame 25 = frame 1 |
- Hips rotate and tilt opposite to shoulders; head stays comparatively level with a small bob; arms swing opposite to the same-side leg with 1-2 frame lag (overlap).
- Tempo guide (frames per step): strolling 16-20 · normal 12-14 · brisk 8-10 · run 4-8 with a flight phase (both feet off the ground). Adjust to the character's weight and mood.
- Build in Blender: block 5 poses -> mirror to complete the cycle -> `anim_helpers.make_cyclic(obj)` so the curves loop (first and last key equal) -> offset arms/head/tail for overlap with `shift_keys` -> check arcs of feet and hips.
- For engine export, loop cycles without a duplicate end frame equal to the first (`04`).

## 11. Blender animation tooling
Dope Sheet (timing), Graph Editor (curves; handle types Auto-clamped to avoid overshoot; Normalize view; Euler Filter), NLA (layering/loops), Action Editor, Pose Library (assets), Auto-Key, Motion Paths and ghosting for arcs, copy/paste **flipped** pose (`Ctrl+C`/`Ctrl+Shift+V`), slider tools (Blend to Neighbor, Push/Relax, Breakdown), Bake Action (visual keying) to convert constraint/IK results to deform-bone keys before export.
Since Blender 4.4 actions are **slotted** (layers->strips->channelbags); 5.x removed `Action.fcurves`; use `anim_helpers.iter_fcurves(obj)` for portable scripts.

## 12. Export notes (details in `04`)
Bake animation onto DEF bones (visual keying, only deform bones), clear constraints in the baked action if needed, set FPS, one action per file `A_<Char>_<Anim>`, root bone at origin, keys simplified at 0 to avoid curve loss, loops without a duplicate end frame.
