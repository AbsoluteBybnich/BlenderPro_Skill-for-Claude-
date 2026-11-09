"""Asset QA gate for mesh objects. Run it before baking, exporting or handing off.

Usage (any one):
    blender -b model.blend -P qa_check.py -- [options]
    python qa_check.py model.blend [options]            # with the `bpy` pip module
    exec(open("qa_check.py").read())  then  qa_check.run(selected_only=True)   # inside a session

Options:
    --selected          only selected objects (default: all mesh objects in the file)
    --include-helpers   also check wire/bounds-display objects (cutters, collision hulls); skipped by default
    --max-tris N        triangle budget per object (after triangulation)
    --tex-size PX       texture resolution to evaluate texel density against (e.g. 2048)
    --target-td PX_M    target texel density in pixels/metre; flags objects off by >20 %
    --grid M            modular-kit check: dimensions must be multiples of M metres (e.g. 1.0 for a 100 cm kit)
    --convention ue     naming prefix check (SM_/SK_ and UCX_/UBX_/UCP_/USP_ collision shapes)
    --json out.json     also write the full report as JSON
Exit status 1 if any ERROR was found (usable in CI / pre-export hooks).

Severity model: ERROR = will break export/bake/shading; WARN = probably a mistake;
INFO = worth knowing. Intentional exceptions (mirrored UVs, tiling UVs, open meshes for decals)
are expected - read the message, then decide.
"""
import json
import math
import re
import sys

import bpy
import bmesh  # noqa: E402  (after bpy on purpose)

try:
    import numpy as np
except Exception:  # numpy ships with bpy, but stay safe
    np = None

UE_PREFIXES = ("SM_", "SK_", "UCX_", "UBX_", "UCP_", "USP_", "SOCKET_")


# --------------------------------------------------------------------------- helpers
def _poly_area_2d(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def _uv_islands(bm, uv_layer):
    """Union faces that share a vertex *and* the same UV coordinate -> island id per face."""
    parent = list(range(len(bm.faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    seen = {}
    for f in bm.faces:
        for l in f.loops:
            uv = l[uv_layer].uv
            key = (l.vert.index, round(uv.x, 5), round(uv.y, 5))
            if key in seen:
                ra, rb = find(f.index), find(seen[key])
                if ra != rb:
                    parent[ra] = rb
            else:
                seen[key] = f.index
    roots = {}
    ids = []
    for f in bm.faces:
        ids.append(roots.setdefault(find(f.index), len(roots)))
    return ids, len(roots)


def _uv_overlap(bm, uv_layer, island_of_face, res=256, max_tris=40000):
    """Rasterise UV triangles; return number of grid cells covered by >1 island (or None if skipped)."""
    if np is None:
        return None
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    if tris > max_tris:
        return None
    grid = np.full((res, res), -1, dtype=np.int32)
    overlap_cells = 0
    for f in bm.faces:
        isl = island_of_face[f.index]
        uvs = [l[uv_layer].uv for l in f.loops]
        for k in range(1, len(uvs) - 1):
            a, b, c = uvs[0], uvs[k], uvs[k + 1]
            minx = max(int(math.floor(min(a.x, b.x, c.x) * res)), 0)
            maxx = min(int(math.ceil(max(a.x, b.x, c.x) * res)), res - 1)
            miny = max(int(math.floor(min(a.y, b.y, c.y) * res)), 0)
            maxy = min(int(math.ceil(max(a.y, b.y, c.y) * res)), res - 1)
            if maxx < minx or maxy < miny:
                continue
            xs = (np.arange(minx, maxx + 1) + 0.5) / res
            ys = (np.arange(miny, maxy + 1) + 0.5) / res
            X, Y = np.meshgrid(xs, ys)
            den = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
            if abs(den) < 1e-12:
                continue
            w1 = ((b.y - c.y) * (X - c.x) + (c.x - b.x) * (Y - c.y)) / den
            w2 = ((c.y - a.y) * (X - c.x) + (a.x - c.x) * (Y - c.y)) / den
            w3 = 1 - w1 - w2
            # shrink slightly so shared island borders do not count
            m = (w1 > 0.02) & (w2 > 0.02) & (w3 > 0.02)
            if not m.any():
                continue
            sub = grid[miny:maxy + 1, minx:maxx + 1]
            existing = sub[m]
            overlap_cells += int(((existing != -1) & (existing != isl)).sum())
            sub[m] = isl
    return overlap_cells


# --------------------------------------------------------------------------- per-object
def check_object(obj, opts):
    issues = []

    def add(sev, code, msg, **extra):
        issues.append(dict(severity=sev, code=code, message=msg, **extra))

    name = obj.name
    # transforms
    if any(s < 0 for s in obj.scale):
        add("ERROR", "NEG_SCALE", f"negative scale {tuple(round(s, 3) for s in obj.scale)} flips normals; apply scale")
    if any(abs(s - 1.0) > 1e-4 for s in obj.scale):
        add("WARN", "UNAPPLIED_SCALE", f"scale {tuple(round(s, 4) for s in obj.scale)} not applied (breaks bake, "
            "collision, modifiers, FBX scale)")
    if any(abs(r) > 1e-4 for r in obj.rotation_euler):
        add("INFO", "UNAPPLIED_ROTATION", "rotation not applied (fine for movable props, wrong for modular kit pieces)")
    dims = obj.dimensions
    if opts.get("grid"):
        g = opts["grid"]
        off = [d for d in dims if min(d % g, g - d % g) > 0.005 + 1e-6]
        if off:
            add("WARN", "MODULAR_GRID", f"dimensions {[round(d, 3) for d in dims]} are not multiples of {g} m "
                "(modular pieces must snap; fix before the kit is built, not after)")
    longest = max(dims)
    if 0 < longest < 0.01:
        add("WARN", "TINY", f"longest dimension {longest * 1000:.2f} mm - wrong unit scale?")
    if longest > 200:
        add("WARN", "HUGE", f"longest dimension {longest:.1f} m - wrong unit scale?")

    # modifiers
    live = [m.name for m in obj.modifiers if m.show_viewport]
    if live:
        add("INFO", "LIVE_MODIFIERS", f"{len(live)} live modifier(s): {', '.join(live)} (applied on export only if the exporter is told to)")

    # topology on the evaluated-free base mesh
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    bm.verts.index_update()

    n_tri = sum(1 for f in bm.faces if len(f.verts) == 3)
    n_quad = sum(1 for f in bm.faces if len(f.verts) == 4)
    n_ngon = sum(1 for f in bm.faces if len(f.verts) > 4)
    tri_total = sum(len(f.verts) - 2 for f in bm.faces)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    loose_v = sum(1 for v in bm.verts if not v.link_edges)
    loose_e = sum(1 for e in bm.edges if not e.link_faces)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    doubles = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-5)["targetmap"])

    if tri_total == 0:
        add("ERROR", "EMPTY", "mesh has no faces")
    if nonman:
        add("ERROR", "NON_MANIFOLD", f"{nonman} non-manifold edge(s) (edges with >2 faces / wire edges); boolean, "
            "voxel remesh and watertight exports need this at 0")
    if boundary and not obj.name.lower().startswith(("decal", "card", "plane")):
        add("INFO", "OPEN_BOUNDARY", f"{boundary} boundary edge(s): mesh is open (OK for planes/cards/decals, wrong for solids)")
    if loose_v or loose_e:
        add("WARN", "LOOSE", f"{loose_v} loose vert(s), {loose_e} loose/wire edge(s)")
    if zero:
        add("WARN", "ZERO_AREA", f"{zero} zero-area face(s) (bake artefacts, degenerate tangents)")
    if doubles:
        add("WARN", "DOUBLES", f"{doubles} duplicate vertices within 0.01 mm - Merge by Distance")
    if n_ngon:
        add("INFO", "NGONS", f"{n_ngon} n-gon(s) - fine on flat hard-surface, fatal if they will deform or be subdivided")
    if opts.get("max_tris") and tri_total > opts["max_tris"]:
        add("WARN", "OVER_BUDGET", f"{tri_total} tris > budget {opts['max_tris']}")

    # inside-out heuristic (closed meshes only)
    if not nonman and not boundary and bm.faces:
        try:
            vol = bm.calc_volume(signed=True)
            if vol < 0:
                add("ERROR", "INSIDE_OUT", f"signed volume {vol:.4f} < 0: normals point inward; Recalculate Outside")
        except Exception:
            pass

    # UVs
    td = None
    uv_layer = bm.loops.layers.uv.active
    islands = None
    if not mesh.uv_layers:
        add("WARN", "NO_UV", "no UV map")
    else:
        if len(mesh.uv_layers) > 2:
            add("INFO", "MANY_UV", f"{len(mesh.uv_layers)} UV maps: {[u.name for u in mesh.uv_layers]}")
        outside = 0
        uv_area = 0.0
        mesh_area = 0.0
        flipped = 0
        for f in bm.faces:
            pts = [(l[uv_layer].uv.x, l[uv_layer].uv.y) for l in f.loops]
            if any(x < -1e-4 or x > 1 + 1e-4 or y < -1e-4 or y > 1 + 1e-4 for x, y in pts):
                outside += 1
            uv_area += _poly_area_2d(pts)
            mesh_area += f.calc_area() * abs(obj.scale.x * obj.scale.y)  # approximate if unapplied
        if outside:
            add("INFO", "UV_OUTSIDE_0_1", f"{outside} face(s) have UVs outside 0-1 (OK for UDIM/tiling, bad for a single baked atlas)")
        ids, n_isl = _uv_islands(bm, uv_layer)
        islands = n_isl
        cells = _uv_overlap(bm, uv_layer, ids)
        if cells:
            add("WARN", "UV_OVERLAP", f"UV islands overlap (~{cells} cells at 256 px grid). Intentional for mirrored/tiling "
                "UVs; must be fixed before baking")
        if mesh_area > 0 and uv_area > 0 and opts.get("tex_size"):
            td = math.sqrt(uv_area / mesh_area) * opts["tex_size"]
            if opts.get("target_td"):
                dev = td / opts["target_td"] - 1
                if abs(dev) > 0.2:
                    add("WARN", "TEXEL_DENSITY", f"texel density {td:.0f} px/m vs target {opts['target_td']:.0f} ({dev:+.0%})")
        if uv_area < 1e-6:
            add("ERROR", "UV_COLLAPSED", "UV area is ~0 (all UVs collapsed)")

    bm.free()

    # materials
    slots = obj.material_slots
    if len(slots) and any(s.material is None for s in slots):
        add("WARN", "EMPTY_SLOT", "empty material slot(s)")
    if len(slots) > 4:
        add("INFO", "MANY_MATERIALS", f"{len(slots)} material slots (each = a draw call in engine)")
    for s in slots:
        if s.material and re.search(r"\.\d{3}$", s.material.name):
            add("WARN", "MAT_DUP_SUFFIX", f"material '{s.material.name}' has .001-style suffix (duplicate material?)")

    # naming
    if re.search(r"\.\d{3}$", name):
        add("INFO", "NAME_SUFFIX", f"object name '{name}' has .001-style suffix")
    if " " in name:
        add("WARN", "NAME_SPACE", f"object name '{name}' contains spaces")
    if opts.get("convention") == "ue" and not name.startswith(UE_PREFIXES):
        add("WARN", "NAME_CONVENTION", f"'{name}' does not start with one of {UE_PREFIXES} (Unreal naming convention)")

    return dict(
        object=name,
        tris=tri_total, quads=n_quad, tri_faces=n_tri, ngons=n_ngon,
        dimensions_m=[round(d, 4) for d in dims],
        uv_islands=islands, texel_density_px_per_m=None if td is None else round(td, 1),
        issues=issues,
    )


# --------------------------------------------------------------------------- driver
def _is_helper(o):
    """Cutters, collision hulls and bounds boxes are wire/bounds-display helpers, not deliverable meshes."""
    return o.display_type in ("WIRE", "BOUNDS")


def run(selected_only=False, include_helpers=False, **opts):
    objs = [o for o in (bpy.context.selected_objects if selected_only else bpy.data.objects) if o.type == "MESH"]
    helpers = [o for o in objs if _is_helper(o)]
    if not include_helpers:
        objs = [o for o in objs if not _is_helper(o)]
        if helpers:
            print(f"(skipped {len(helpers)} helper object(s) with wire/bounds display: "
                  f"{', '.join(sorted(h.name for h in helpers))}; use --include-helpers to check them)")
    report = [check_object(o, opts) for o in sorted(objs, key=lambda o: o.name)]
    n_err = sum(1 for r in report for i in r["issues"] if i["severity"] == "ERROR")
    n_warn = sum(1 for r in report for i in r["issues"] if i["severity"] == "WARN")
    print(f"\n=== 3Dpro QA: {len(report)} mesh object(s) | {n_err} error(s) | {n_warn} warning(s) ===")
    for r in report:
        print(f"\n[{r['object']}] tris={r['tris']} quads={r['quads']} ngons={r['ngons']} "
              f"dims(m)={r['dimensions_m']} uv_islands={r['uv_islands']} td={r['texel_density_px_per_m']}")
        if not r["issues"]:
            print("  OK - no issues")
        for i in r["issues"]:
            print(f"  {i['severity']:5} {i['code']:16} {i['message']}")
    return report, n_err


def _args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def _opt(args, flag, cast=str, default=None):
    return cast(args[args.index(flag) + 1]) if flag in args else default


if __name__ == "__main__":
    a = _args()
    blend = next((x for x in a if x.endswith(".blend")), None)
    if blend and bpy.data.filepath != blend:
        bpy.ops.wm.open_mainfile(filepath=blend)
    rep, errs = run(
        selected_only="--selected" in a, include_helpers="--include-helpers" in a,
        max_tris=_opt(a, "--max-tris", int), tex_size=_opt(a, "--tex-size", int),
        target_td=_opt(a, "--target-td", float), convention=_opt(a, "--convention"),
        grid=_opt(a, "--grid", float),
    )
    if "--json" in a:
        with open(_opt(a, "--json"), "w") as fh:
            json.dump(rep, fh, indent=2)
    sys.exit(1 if errs else 0)
