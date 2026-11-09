# AI-assisted concepts and references: ComfyUI + FLUX

Contents: 1 Where AI helps (and where it does not) · 2 Setup · 3 The graph · 4 Settings that matter · 5 Prompting FLUX · 6 Prompt templates ·
7 Multi-view consistency · 8 From image to Blender · 9 Textures and materials · 10 Licensing, safety, ethics · 11 Troubleshooting

Files: `scripts/comfyui/flux_dev_t2i.api.json` (workflow, API format), `scripts/comfyui/comfy_submit.py` (patch + submit + download, stdlib only), `scripts/reference_setup.py` (bring images into Blender aligned to real height).
Status: the client was tested against a mock server; **no real ComfyUI/GPU was available**, so the first run on your install is the real test (node names or model file names may differ by version - open the JSON in the UI via *Load* and let ComfyUI point out differences).

## 1. Where AI helps (and where it does not)
- **Good**: ideation (many silhouettes/variants fast), mood/lighting/colour direction, material and surface references, costume/prop design exploration, quick environment key-art, a front-view starting point for orthographic reference.
- **Weak**: consistent multi-view turnarounds, precise proportions, mechanical logic (hinges, panel logic often impossible), hands/text/small details, repeatable character identity across images, production topology/UVs (use image-to-3D only for blockout).
- **Rule**: treat output as **reference you redraw/measure**, never as the final design you copy pixel-for-pixel. You are responsible for originality and licence compliance (section 10).

## 2. Setup (ComfyUI + FLUX)
- ComfyUI install, then models (names match the template; folders differ by version - modern: `models/diffusion_models`, `models/text_encoders`, `models/vae`; older: `unet`, `clip`, `vae`):
  `flux1-dev.safetensors` (or `flux1-schnell.safetensors`) · text encoders `clip_l.safetensors` + `t5xxl_fp16.safetensors` (or an fp8 variant) · VAE `ae.safetensors`.
- Hardware: FLUX.1 dev in fp16 is heavy (≈ 24 GB VRAM class); fp8 / GGUF quantised variants run in 8-16 GB at some quality/speed cost. CPU-only is impractical.
- Variants (verify current names and licences): **FLUX.1 [dev]** (quality, non-commercial weights licence), **[schnell]** (fast, 1-4 steps, Apache-2.0), **FLUX.1 Kontext** (instruction-based image editing - useful for "same character, side view"), **FLUX.1 Tools** (Fill/inpaint, Canny, Depth, Redux), and newer generations (e.g. FLUX.2) with their own nodes/licences.
- Run headless server: `python main.py --listen 127.0.0.1 --port 8188`. **Never expose it to the internet**; do not install unvetted custom nodes (they execute arbitrary code).

## 3. The graph (what each node does)
`UNETLoader` (diffusion model) + `DualCLIPLoader` (clip_l + t5xxl, type *flux*) + `VAELoader` -> `CLIPTextEncode` (prompt) -> `FluxGuidance` (strength) -> `KSampler` (positive; negative = `ConditioningZeroOut`) with `EmptySD3LatentImage` -> `VAEDecode` -> `SaveImage`.
Titles in the JSON ("Positive Prompt", "Latent", "KSampler", "FluxGuidance", "Save Image") are how `comfy_submit.py` finds nodes. Design variants in the UI, **Save (API Format)**, and reuse the script.
Extending: add `LoraLoaderModelOnly` after the UNET loader for style/character LoRAs; `LoadImage` + `VAEEncode` for img2img (denoise 0.4-0.7); Fill nodes for inpainting; Canny/Depth ControlNet-style tools for structure guidance; Kontext graph for edits.

## 4. Settings that matter
| Setting | Typical | Notes |
|---|---|---|
| Resolution | ~1 MP native (1024x1024, 1344x768, 768x1344), **multiples of 16** | too large = duplicated limbs/composition drift; upscale afterwards |
| Steps | dev 20-30 · schnell 1-4 | more steps rarely helps beyond ~30 |
| Guidance (FluxGuidance) | 3.5 (range 2-5) | higher = follows prompt more literally, can burn/over-saturate |
| KSampler cfg | **1.0** (FLUX uses guidance, not classic CFG) | negative prompt effectively unused |
| Sampler / scheduler | `euler` / `simple` | stable default; try `dpmpp_2m`/`beta` for variety |
| Seed | fixed while iterating the prompt | change seed to explore, lock once you like a composition |
| Batch size | 2-4 for exploration | use `--batch` in the script |

## 5. Prompting FLUX
- Natural-language sentences; the T5 encoder understands long, specific descriptions. Order: **subject -> action/pose -> design details -> materials -> setting -> lighting -> camera/medium**.
- No reliance on `(word:1.3)` weights or long negative lists; state what you want ("plain grey background") instead of what you do not.
- Be concrete about *shape language, materials, era, proportions* ("stocky 5-heads proportions, oversized hands, riveted brass armour plates"). Avoid vague quality words ("masterpiece").
- Do not use living artists' names or protected characters/IP as style shortcuts (section 10). Describe the look instead.

## 6. Prompt templates
**Character front reference**: "full-body character design, front view, neutral A-pose, stylised orc blacksmith with 5-head proportions, broad shoulders, leather apron over riveted steel plates, flat grey background, even soft studio lighting, clean silhouette, concept art sheet, no text."
**Hard-surface prop orthographic**: "orthographic front view of a sci-fi crate with panel lines, vents and two latches, flat shaded concept drawing, neutral grey background, even lighting, no perspective, no text."
**Environment mood**: "wide shot of an abandoned seaside lighthouse at dusk, overcast, warm window glow against cold blue fog, painterly, strong value contrast, clear focal point."
**Material swatch**: "seamless tileable texture of worn dark-green painted steel with scratched edges and light rust streaks, top-down, perfectly flat, even lighting, no perspective, no shadows."
**Silhouette exploration**: "six distinct silhouettes of a fantasy knight, black shapes on white background, varied proportions and weapons, side by side."
Run: `python scripts/comfyui/comfy_submit.py scripts/comfyui/flux_dev_t2i.api.json --prompt "<one of the above>" --seed 7 --size 1024x1024 --out ./concepts`.

## 7. Multi-view consistency (the hard problem)
- Single-image "turnaround sheets" from text are unreliable (views disagree). More dependable approaches:
  1. Generate the **front view**, pick the best; then use **Kontext**/Redux/img2img with the instruction "same character, side view, same outfit, same flat background".
  2. Establish proportions and key shapes yourself in a quick 2D/3D blockout, then use AI only for surface/costume ideas.
  3. For props: generate several views separately but model from the shared **design logic**, not from pixel details.
  4. Image-to-3D services exist and give a blockout mesh quickly; output topology/UVs are not production-ready - treat as a base to retopologise.
- Always verify consistency by overlaying views in Blender (below); resolve disagreements in favour of the front view and your own design decisions.

## 8. From image to Blender
1. Pick the final image; **crop/straighten** so the figure is vertical and the feet touch the bottom edge. Note what fraction of the image height the figure fills.
2. In Blender: `reference_setup.add_reference(path, view="FRONT", height_m=1.8, image_height_fraction=0.9)` and the side view likewise; `proportion_guide(1.8, 8)` to compare head-unit proportions with your target (an AI figure is rarely 8 heads - decide intentionally).
3. Block out primitives to the silhouette (`02`), check against the overlay from front and side; fix proportion disagreements in the model, not by trusting the picture.
4. Redesign the details you will really model (AI detail is incoherent); keep a "design rules" list (shapes, bevels, material zones) for consistency.
5. Keep the source prompt/seed/model/licence in the asset's README for provenance.

## 9. Textures and materials
- Use generated images as **look references** or paint-over bases for hand-painted textures; for PBR, derive roughness/normal from procedural/Substance workflows rather than trusting an AI colour map's lighting.
- Tileability: verify by offsetting 50 % (Blender image editor *Image > Offset* via nodes/Mapping, or any editor) and fixing the cross; AI "seamless" claims often fail.
- Remove baked lighting/shadows before using as base colour; keep values in a physical range (no pure black/white).

## 10. Licensing, safety, ethics
- Read the **exact licence of the model** you run (FLUX.1 dev: non-commercial weights licence with separate terms on commercial use of outputs/hosting; schnell: Apache-2.0; others vary) and of any LoRA/checkpoint/custom node. If a project is commercial, get a commercial licence or use a permissive model.
- Copyright status of AI outputs differs by jurisdiction and platform rules (asset stores and game platforms increasingly require AI disclosure). Keep records; avoid prompting with living artists' names or others' IP.
- Do not generate or use likenesses of real people without consent.
- Security: local server only, vetted custom nodes, no secrets in workflow JSON.

## 11. Troubleshooting
| Symptom | Fix |
|---|---|
| `Required input is missing`/unknown node | open JSON in the UI; update ComfyUI; nodes renamed (e.g. folder `unet` vs `diffusion_models`) |
| Out of VRAM | fp8/GGUF model variant, smaller resolution, close other apps, `--lowvram` |
| Washed-out/over-saturated | lower guidance (3.0-3.5), shorten prompt, different seed |
| Anatomy/duplicate limbs | resolution closer to 1 MP, simpler pose prompt, inpaint the region (Fill) |
| Text garbage | avoid text in the image; add in 2D editor |
| Script: connection refused | server not running / wrong `--server` URL; check `COMFY_SERVER` env |
