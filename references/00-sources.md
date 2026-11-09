# Sources, provenance and how to extend this skill

## Read this first (honest provenance)
This skill was **not** built by watching the videos, reading the books or taking the courses listed below. I (Claude) cannot access paid courses, cannot read copyrighted books I was not given, and cannot watch hundreds of hours of video.
What the skill contains is:
1. **Working knowledge of each topic area** - the techniques that are widely taught under these headings - written in my own words, and
2. **Tested tooling**: every script in `scripts/` was executed on Blender 5.2.3 LTS (via the `bpy` pip module) with assertions on the results (see `scripts/selftest.py`).
It is therefore a *starting framework*, not a replacement for the originals. Where a source teaches something more specific (exact tool settings, hotkeys, project files, art direction), trust the source over this skill.
Numbers are rules of thumb; hotkeys/menus of paid add-ons are intentionally not given because they change per version.

## The sources you listed -> what the skill took from the topic -> what to study in the original
| # | Source (as listed) | Topic area used here | Where it lives | Study the original for |
|---|---|---|---|---|
| 1 | YouTube: Josh Gambrell, Ponte Ryuurui (Blender Bros) | hard-surface and Boolean modeling | `01` | live demonstrations of workflow speed, design taste, panel/greeble language, real project breakdowns |
| 2 | Advanced modifiers and add-ons: Hard Ops, Boxcutter, MESHmachine | modifier-stack automation, interactive cutting, topology surgery | `01` section 6 | current hotkeys/menus, add-on specific features and updates (paid, interactive) |
| 3 | Book: *Anatomy for 3D Artists: The Essential Guide for CG Professionals* (3dtotal Publishing) | proportions, landmarks, muscle groups, face/hand structure | `02` | illustrations, muscle diagrams, detailed regional anatomy, reference photos |
| 4 | YouTube: FlippedNormals, SpeedChar, Grant Abbitt | sculpting, anatomy, stylised characters, box-modeling | `02` | full sculpting sessions, brush technique, stylised design decisions |
| 5 | CG Cookie character creation learning path | end-to-end character pipeline | `02` section 10, `10` | the complete guided project with checkpoints and feedback |
| 6 | Retopology, UV, baking (Normal/AO/Curvature) in Marmoset Toolbag and Blender | retopo, UV, texel density, bake setup, troubleshooting | `03` | Marmoset UI details, skew painting, advanced cage control |
| 7 | YouTube: Victor3D, CG Boost - Blender to Unreal Engine 5 | export/import pipeline | `04` | engine-version-specific import dialogs, material setups, project workflow |
| 8 | CG LAB environment and level-design courses | environment kits, level-design principles | `05` | genre-specific level design, kit design critique, production examples |
| 9 | Pierrick Picaut / p2design - *The Art of Effective Rigging*, *Alive! Animation course* | rigging for animators, animation craft | `06` | the full rig architectures and animation exercises |
| 10 | YouTube: Royal Skies - face, body, IK/FK rigging shorts | quick rigging recipes | `06` | exact bone/driver setups shown step by step |
| 11 | Blender Python API (`bpy`) | automation, API patterns | `07`, `scripts/` | official API docs (always the version-matched ones) |
| 12 | Book: *Python Scripting in Blender* (Thomas Larsson) | scripting meshes, materials, rigs, UI | `07` | complete worked scripts, deeper bpy coverage |
| 13 | Book: *Blender 3D By Example* (Oscar Baechler, Xury Greer) | project-based Blender learning | `07` section 10, `10` | the step-by-step projects |
| 14 | ComfyUI node environment and FLUX models | AI concept/reference generation | `08`, `scripts/comfyui/` | current model cards/licences, community workflows, node documentation |
| 15 | Book: *Digital Lighting & Rendering* (Jeremy Birn) | lighting theory, ratios, shadows, rendering | `09` | the complete theory, case studies, render-pass workflows |
| 16 | Book: *The Animator's Survival Kit* (Richard Williams) | principles, timing, spacing, walk/run cycles | `06` | the drawings: the real teaching is in the visual examples |

## How to make the skill better with real source material
- **Notes you own**: paste your own notes/transcripts/summaries of a course into the right `references/` file (or ask Claude to merge them) - then the skill can quote *your* lessons rather than generic practice.
- **Specific videos**: give specific URLs; a video-transcription tool (for example the `watch` skill, if configured in your Claude environment - it needed dependency setup in this session) can produce transcripts and key frames that I then distil into `references/`. Do it per video; do not expect all channels at once.
- **Your own project files**: share a `.blend` and I will run `qa_check.py` and calibrate budgets/defaults to your project.
- **Version drift**: re-run `scripts/selftest.py` after every Blender upgrade; a failing test tells you exactly which API changed.
- **Add-ons**: if you own Hard Ops / Boxcutter / MESHmachine, keep a short `references/addon-notes.md` with your keymap and preferred operations; the skill will use it.

## Known gaps (not verified in this build)
Unreal Editor import behaviour (settings are standard practice, not tested in-editor) · Marmoset Toolbag · paid add-ons · a real ComfyUI install and FLUX weights · EEVEE rendering and GPU paths ·
`blender -b -P` with the official binary (scripts ran through the `bpy` pip module; argument handling for both modes is implemented and `--` parsing logic is shared) · Blender versions other than 5.2.3 (older-version notes are from knowledge).
