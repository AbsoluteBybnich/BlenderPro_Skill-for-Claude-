#!/usr/bin/env python3
"""Submit an API-format ComfyUI workflow to a running ComfyUI server and download the results. Stdlib only.

    python comfy_submit.py flux_dev_t2i.api.json --prompt "stylized orc blacksmith, front/side/back turnaround" \
        --seed 7 --size 1344x768 --steps 25 --guidance 3.5 --out ./concepts [--server http://127.0.0.1:8188]
    python comfy_submit.py flux_dev_t2i.api.json --dry-run          # print the patched workflow, send nothing

How it finds the nodes to patch: by `_meta.title` ("Positive Prompt", "Latent", "KSampler", "FluxGuidance", "Save Image").
Workflows exported from the ComfyUI UI with "Save (API Format)" keep these titles, so you can design in the UI and
reuse this script; rename the titles in the UI if you want other nodes patchable.

The template follows the structure of ComfyUI's official FLUX example (UNETLoader + DualCLIPLoader(flux) + VAELoader +
FluxGuidance + KSampler/euler/simple + EmptySD3LatentImage). Model file names (flux1-dev.safetensors, clip_l, t5xxl_fp16,
ae.safetensors) must exist in your ComfyUI models folders; the first run against your install is the real test - if a
node is reported as missing, open the JSON in the UI (Load) and let it tell you what differs in your version.

Licence reminder: FLUX.1 [dev] weights are non-commercial unless you hold a commercial licence; FLUX.1 [schnell] is
Apache-2.0 (use 4 steps, guidance is ignored). Check the licence of the exact model you use before shipping output.
"""
import argparse
import copy
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid


def patch(workflow, prompt=None, negative=None, seed=None, size=None, steps=None, guidance=None, prefix=None,
          unet=None, batch=None):
    wf = copy.deepcopy(workflow)

    def by_title(title_part):
        return [(nid, n) for nid, n in wf.items() if title_part.lower() in n.get("_meta", {}).get("title", "").lower()]

    def need(title_part, class_type):
        hits = [(i, n) for i, n in by_title(title_part) if n["class_type"] == class_type]
        if not hits:
            raise KeyError(f"no node titled like {title_part!r} with class {class_type}")
        return hits

    if prompt is not None:
        for _, n in need("Positive Prompt", "CLIPTextEncode"):
            n["inputs"]["text"] = prompt
    if negative is not None:
        for _, n in need("Negative Prompt", "CLIPTextEncode"):
            n["inputs"]["text"] = negative
    if seed is not None or steps is not None:
        for _, n in need("KSampler", "KSampler"):
            if seed is not None:
                n["inputs"]["seed"] = int(seed)
            if steps is not None:
                n["inputs"]["steps"] = int(steps)
    if guidance is not None:
        for _, n in need("FluxGuidance", "FluxGuidance"):
            n["inputs"]["guidance"] = float(guidance)
    if size or batch:
        for _, n in need("Latent", "EmptySD3LatentImage"):
            if size:
                w, h = (int(x) for x in size.lower().split("x"))
                n["inputs"]["width"], n["inputs"]["height"] = w, h
            if batch:
                n["inputs"]["batch_size"] = int(batch)
    if prefix:
        for _, n in need("Save Image", "SaveImage"):
            n["inputs"]["filename_prefix"] = prefix
    if unet:
        for _, n in need("Load Diffusion Model", "UNETLoader"):
            n["inputs"]["unet_name"] = unet
    return wf


def _http(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def run(workflow, server, out_dir, poll=1.0, timeout=900):
    client_id = uuid.uuid4().hex
    resp = json.loads(_http(f"{server}/prompt", json.dumps({"prompt": workflow, "client_id": client_id}).encode()))
    if "prompt_id" not in resp:
        raise RuntimeError(f"server rejected the workflow: {resp}")
    pid = resp["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        hist = json.loads(_http(f"{server}/history/{pid}"))
        if pid in hist and hist[pid].get("outputs"):
            break
        time.sleep(poll)
    else:
        raise TimeoutError(f"no result for {pid} after {timeout}s")
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for node_out in hist[pid]["outputs"].values():
        for img in node_out.get("images", []):
            q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                        "type": img.get("type", "output")})
            path = os.path.join(out_dir, os.path.basename(img["filename"]))
            with open(path, "wb") as fh:
                fh.write(_http(f"{server}/view?{q}"))
            saved.append(path)
    return saved


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow")
    ap.add_argument("--server", default=os.environ.get("COMFY_SERVER", "http://127.0.0.1:8188"))
    ap.add_argument("--prompt"), ap.add_argument("--negative"), ap.add_argument("--seed", type=int)
    ap.add_argument("--size", help="WxH, multiples of 16, e.g. 1344x768"), ap.add_argument("--steps", type=int)
    ap.add_argument("--guidance", type=float), ap.add_argument("--prefix"), ap.add_argument("--unet")
    ap.add_argument("--batch", type=int)
    ap.add_argument("--out", default="./comfy_out"), ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    with open(a.workflow) as fh:
        wf = patch(json.load(fh), a.prompt, a.negative, a.seed, a.size, a.steps, a.guidance, a.prefix, a.unet, a.batch)
    if a.dry_run:
        print(json.dumps(wf, indent=2))
        return 0
    for p in run(wf, a.server.rstrip("/"), a.out):
        print("saved", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
