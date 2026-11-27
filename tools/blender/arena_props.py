"""
The Scissors - arena prop generator (Blender 4.5, headless).

Usage (from repo root):
  blender -b --factory-startup --python tools/blender/arena_props.py -- build floor border spool candle
  blender -b --factory-startup --python tools/blender/arena_props.py -- preview

Every prop is built procedurally from bmesh, coloured with a per-corner "Col"
attribute + a surface-type material (wood, stone, ginger, icing, thread, wax,
metal), then the hand-painted look (painted AO, top light, edge highlight,
grain) is baked into ONE diffuse texture per prop. Output:
  Art/Arena/Blend/SM_<Name>.blend
  Art/Arena/FBX/SM_<Name>.fbx      (1 Blender m = 100 UE cm)
  Art/Arena/Textures/T_<Name>_D.png
Arena layout constants below are already ~18% wider than the concept so the
growing scissor arc still fits.
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "Art", "Arena")
for sub in ("Blend", "FBX", "Textures", "Preview"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)

# ---------------- arena layout (metres) ----------------
R_PLANK = 10.8      # wooden plank disc
R_INRIM = 11.2      # dark wood ring around planks
R_STONE = 15.0      # flagstone ring outer edge
R_RIM = 15.7        # outer wood rim
R_GINGER = 19.5     # gingerbread border outer edge
BORDER_MODULES = 16
GINGER_TOP = 0.35

# ---------------- palette (linear) ----------------
C = dict(
    plank=(0.19, 0.095, 0.045), darkwood=(0.075, 0.038, 0.02), stone=(0.075, 0.085, 0.095),
    ginger=(0.40, 0.165, 0.05), icing=(0.86, 0.80, 0.72), spoolwood=(0.28, 0.14, 0.06),
    wax=(0.90, 0.80, 0.60), brass=(0.62, 0.40, 0.14), wick=(0.03, 0.025, 0.02),
)
THREADS = dict(green=(0.18, 0.38, 0.16), red=(0.55, 0.09, 0.07), blue=(0.12, 0.22, 0.50),
               yellow=(0.80, 0.55, 0.12), purple=(0.32, 0.16, 0.42), pink=(0.80, 0.30, 0.42))
TYPES = ["wood", "stone", "ginger", "icing", "thread", "wax", "metal"]


def jitter(c, amt=0.12, rnd=random):
    k = 1.0 + rnd.uniform(-amt, amt)
    return tuple(max(0.0, min(1.0, v * k * (1 + rnd.uniform(-amt, amt) * 0.3))) for v in c)


# ---------------- bmesh builder ----------------
class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.float_color.new("Col")
        self.mt = self.bm.faces.layers.int.new("mt")

    def _paint(self, faces, t, col):
        mi = TYPES.index(t)
        c = (col[0], col[1], col[2], 1.0)
        for f in faces:
            f.material_index = mi
            f[self.mt] = mi
            for l in f.loops:
                l[self.col] = c

    def _faces_of(self, verts):
        fs = set()
        for v in verts:
            fs.update(v.link_faces)
        return list(fs)

    def prism(self, poly, z0, z1, t, col):
        """convex 2D polygon (ccw) extruded from z0 to z1."""
        bm = self.bm
        b = [bm.verts.new((x, y, z0)) for x, y in poly]
        u = [bm.verts.new((x, y, z1)) for x, y in poly]
        fs = [bm.faces.new(u), bm.faces.new(list(reversed(b)))]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            fs.append(bm.faces.new((b[i], b[j], u[j], u[i])))
        self._paint(fs, t, col)
        return fs

    def star_prism(self, pts, center, z0, z1, t, col):
        """non-convex outline as triangle fan around center."""
        bm = self.bm
        cb, cu = bm.verts.new((*center, z0)), bm.verts.new((*center, z1))
        b = [bm.verts.new((x, y, z0)) for x, y in pts]
        u = [bm.verts.new((x, y, z1)) for x, y in pts]
        fs, n = [], len(pts)
        for i in range(n):
            j = (i + 1) % n
            fs.append(bm.faces.new((cu, u[i], u[j])))
            fs.append(bm.faces.new((cb, b[j], b[i])))
            fs.append(bm.faces.new((b[i], b[j], u[j], u[i])))
        self._paint(fs, t, col)

    def ring(self, r0, r1, a0, a1, z0, z1, t, col, seg=8, closed=False, ztop_fn=None):
        """annular sector prism made of quads (safe triangulation)."""
        bm = self.bm
        n = seg if closed else seg + 1
        angs = [a0 + (a1 - a0) * i / seg for i in range(n)]
        def zt(a, r):
            return z1 + (ztop_fn(a, r) if ztop_fn else 0.0)
        ib = [bm.verts.new((r0 * math.cos(a), r0 * math.sin(a), z0)) for a in angs]
        ob = [bm.verts.new((r1 * math.cos(a), r1 * math.sin(a), z0)) for a in angs]
        it = [bm.verts.new((r0 * math.cos(a), r0 * math.sin(a), zt(a, r0))) for a in angs]
        ot = [bm.verts.new((r1 * math.cos(a), r1 * math.sin(a), zt(a, r1))) for a in angs]
        fs = []
        m = seg
        for i in range(m):
            j = (i + 1) % n
            fs.append(bm.faces.new((it[i], ot[i], ot[j], it[j])))     # top
            fs.append(bm.faces.new((ib[j], ob[j], ob[i], ib[i])))     # bottom
            fs.append(bm.faces.new((ob[i], ob[j], ot[j], ot[i])))     # outer
            fs.append(bm.faces.new((ib[j], ib[i], it[i], it[j])))     # inner
        if not closed:
            fs.append(bm.faces.new((ib[0], ob[0], ot[0], it[0])))
            fs.append(bm.faces.new((ob[-1], ib[-1], it[-1], ot[-1])))
        self._paint(fs, t, col)
        return fs

    def cyl(self, r1, r2, z0, z1, t, col, seg=16, loc=(0, 0)):
        d = z1 - z0
        M = Matrix.Translation((loc[0], loc[1], z0 + d / 2))
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=seg,
                                    radius1=r1, radius2=r2, depth=d, matrix=M)
        self._paint(self._faces_of(res["verts"]), t, col)

    def blob(self, loc, scale, t, col, subdiv=1, stretch_top=1.0):
        M = Matrix.Translation(loc) @ Matrix.Diagonal((*scale, 1.0))
        res = bmesh.ops.create_icosphere(self.bm, subdivisions=subdiv, radius=1.0, matrix=M)
        if stretch_top != 1.0:
            for v in res["verts"]:
                if v.co.z > loc[2]:
                    v.co.z = loc[2] + (v.co.z - loc[2]) * stretch_top
        self._paint(self._faces_of(res["verts"]), t, col)

    def tube(self, pts, radius, t, col, sides=6, cap=True):
        bm = self.bm
        pts = [Vector(p) for p in pts]
        rings = []
        for i, p in enumerate(pts):
            a = pts[max(i - 1, 0)]
            b = pts[min(i + 1, len(pts) - 1)]
            T = (b - a).normalized()
            up = Vector((0, 0, 1)) if abs(T.z) < 0.9 else Vector((1, 0, 0))
            N = T.cross(up).normalized()
            B = T.cross(N).normalized()
            rr = radius(i / (len(pts) - 1)) if callable(radius) else radius
            rings.append([bm.verts.new(p + (N * math.cos(k * 2 * math.pi / sides) +
                                            B * math.sin(k * 2 * math.pi / sides)) * rr)
                          for k in range(sides)])
        fs = []
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            for k in range(sides):
                kk = (k + 1) % sides
                fs.append(bm.faces.new((r0[k], r0[kk], r1[kk], r1[k])))
        if cap:
            fs.append(bm.faces.new(list(reversed(rings[0]))))
            fs.append(bm.faces.new(rings[-1]))
        self._paint(fs, t, col)

    def to_object(self, name, coll):
        me = bpy.data.meshes.new(name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def clip_convex(poly, clip):
    """Sutherland-Hodgman: clip polygon by convex ccw clip polygon."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0
    def inter(p, q, a, b):
        x1, y1, x2, y2 = *p, *q
        x3, y3, x4, y4 = *a, *b
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        tt = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        return (x1 + tt * (x2 - x1), y1 + tt * (y2 - y1))
    out = poly
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        inp, out = out, []
        if not inp:
            break
        s = inp[-1]
        for e in inp:
            if inside(e, a, b):
                if not inside(s, a, b):
                    out.append(inter(s, e, a, b))
                out.append(e)
            elif inside(s, a, b):
                out.append(inter(s, e, a, b))
            s = e
    return out


# ---------------- materials ----------------
PATTERN = {  # type: (mapping scale xyz, builder)
    "wood": ((7, 0.35, 7), "noise", 0.62, 1.08),
    "stone": ((0.9, 0.9, 0.9), "noise", 0.72, 1.06),
    "ginger": ((14, 14, 14), "speckle", 0.78, 1.0),
    "icing": ((3, 3, 3), "noise", 0.94, 1.02),
    "thread": ((2.5, 2.5, 26), "noise", 0.70, 1.08),
    "wax": ((3, 3, 1.2), "noise", 0.90, 1.0),
    "metal": ((2, 2, 2), "noise", 0.85, 1.1),
}


def type_material(prefix, t, scale_mul=1.0, grain=(7, 0.35, 7)):
    m = bpy.data.materials.new(f"{prefix}_{t}")
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        if n.type != "OUTPUT_MATERIAL":
            N.remove(n)
    out = [n for n in N if n.type == "OUTPUT_MATERIAL"][0]
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.85
    L.new(bsdf.outputs[0], out.inputs[0])
    sc, kind, lo, hi = PATTERN[t]
    if t == "wood":
        sc = grain
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = [s * scale_mul for s in sc]
    L.new(tc.outputs["Object"], mp.inputs[0])
    if kind.startswith("wave"):
        tx = N.new("ShaderNodeTexWave")
        tx.bands_direction = "X" if kind == "wave_x" else "Z"
        tx.inputs["Scale"].default_value = 2.5 if kind == "wave_x" else 9.0
        tx.inputs["Distortion"].default_value = 7.0 if kind == "wave_x" else 1.5
        tx.inputs["Detail"].default_value = 3.0
        val = tx.outputs["Fac"]
    else:
        tx = N.new("ShaderNodeTexNoise")
        tx.inputs["Scale"].default_value = 2.0
        tx.inputs["Detail"].default_value = 4.0
        tx.inputs["Distortion"].default_value = 0.35 if t in ("wood", "thread") else 0.0
        val = tx.outputs["Fac"]
    L.new(mp.outputs[0], tx.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    if kind == "speckle":
        e[0].position, e[1].position = 0.62, 0.70
        e[0].color, e[1].color = (1, 1, 1, 1), (lo, lo, lo, 1)
    else:
        e[0].position, e[1].position = 0.3, 0.7
        e[0].color, e[1].color = (lo, lo, lo, 1), (hi, hi, hi, 1)
    L.new(val, ramp.inputs[0])
    attr = N.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"

    def vmul(a, b):
        n = N.new("ShaderNodeVectorMath"); n.operation = "MULTIPLY"
        L.new(a, n.inputs[0]); L.new(b, n.inputs[1]); return n.outputs[0]

    def maprange(src, a, b, c, d):
        n = N.new("ShaderNodeMapRange"); n.clamp = True
        n.inputs[1].default_value, n.inputs[2].default_value = a, b
        n.inputs[3].default_value, n.inputs[4].default_value = c, d
        L.new(src, n.inputs[0]); return n.outputs[0]

    col = vmul(attr.outputs["Color"], ramp.outputs["Color"])
    ao = N.new("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.6 if t in ("stone", "wood") else 0.35
    col = vmul(col, maprange(ao.outputs["AO"], 0, 1, 0.45, 1.0))
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sep.inputs[0])
    col = vmul(col, maprange(sep.outputs["Z"], -1, 1, 0.72, 1.12))
    bev = N.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.04 if t != "metal" else 0.01
    dot = N.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
    L.new(bev.outputs[0], dot.inputs[0]); L.new(geo.outputs["Normal"], dot.inputs[1])
    edge_gain = 1.45 if t == "metal" else 1.22
    col = vmul(col, maprange(dot.outputs["Value"], 0.80, 0.995, edge_gain, 1.0))
    L.new(col, bsdf.inputs["Base Color"])
    return m


def assign_types(ob, prefix, **kw):
    ob.data.materials.clear()
    for t in TYPES:
        ob.data.materials.append(type_material(prefix, t, **kw))
    mt = ob.data.attributes["mt"]
    for p in ob.data.polygons:
        p.material_index = mt.data[p.index].value


def bevel_apply(ob, width, segs=1, angle=40):
    md = ob.modifiers.new("Bevel", "BEVEL")
    md.width, md.segments, md.limit_method = width, segs, "ANGLE"
    md.angle_limit = math.radians(angle)
    md.harden_normals = False
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def select_only(obs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]


def join(obs, name):
    select_only(obs)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def finalize(ob, name, tex=2048, variants=None, extra_export=()):
    """UV, bake hand-painted diffuse, swap to single material, save + export."""
    select_only([ob])
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4],
                          quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0015,
                             area_weight=0.0, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.use_pass_color = True
    sc.render.bake.margin = 8
    variants = variants or {"": None}
    textures = {}
    for vname, recolor in variants.items():
        if recolor:
            recolor(ob)
        img = bpy.data.images.new(f"T_{name}{vname}_D", tex, tex, alpha=False)
        for m in ob.data.materials:
            n = m.node_tree.nodes.new("ShaderNodeTexImage")
            n.image = img
            m.node_tree.nodes.active = n
        select_only([ob])
        bpy.ops.object.bake(type="DIFFUSE")
        path = os.path.join(OUT, "Textures", f"T_{name}{vname}_D.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        textures[vname] = img
        for m in ob.data.materials:
            for n in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"]:
                m.node_tree.nodes.remove(n)
    # final single material with the first texture
    first = list(textures.values())[0]
    fm = bpy.data.materials.new(f"M_{name}")
    fm.use_nodes = True
    bsdf = fm.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    it = fm.node_tree.nodes.new("ShaderNodeTexImage")
    it.image = first
    fm.node_tree.links.new(it.outputs[0], bsdf.inputs["Base Color"])
    ob.data.materials.clear()
    ob.data.materials.append(fm)
    for p in ob.data.polygons:
        p.material_index = 0
    for a in list(ob.data.color_attributes):
        ob.data.color_attributes.remove(a)
    for m in [m for m in bpy.data.materials if m.users == 0]:
        bpy.data.materials.remove(m)
    export_list = [ob] + list(extra_export)
    for o in export_list:
        select_only([o])
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "FBX", f"{o.name}.fbx"),
                                 use_selection=True, apply_scale_options="FBX_SCALE_UNITS",
                                 mesh_smooth_type="FACE", use_tspace=True,
                                 path_mode="AUTO", bake_anim=False, object_types={"MESH"})
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Blend", f"{name}.blend"))
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print(f"[arena] {name}: {tris} tris, textures={list(textures)}")
    return tris


def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc.collection


# ======================= PROPS =======================
def build_floor():
    coll = fresh_scene()
    rnd = random.Random(7)
    hard = Builder()
    # --- planks (run along Y, clipped to a 64-gon) ---
    circ = [(R_PLANK * math.cos(a * 2 * math.pi / 64), R_PLANK * math.sin(a * 2 * math.pi / 64))
            for a in range(64)]
    w, g = 0.95, 0.025
    x = -R_PLANK
    while x < R_PLANK:
        y = -R_PLANK - rnd.uniform(0, 3)
        pc = jitter(C["plank"], 0.18, rnd)
        while y < R_PLANK:
            L = rnd.uniform(3.0, 6.5)
            rect = [(x + g, y + g), (x + w - g, y + g), (x + w - g, y + L - g), (x + g, y + L - g)]
            poly = clip_convex(rect, circ)
            if len(poly) >= 3:
                top = rnd.uniform(-0.015, 0.012)
                hard.prism(poly, -0.25, top, "wood", jitter(pc, 0.08, rnd))
            y += L
        x += w
    # --- inner dark rim (segmented boards) ---
    n = 20
    for i in range(n):
        a0, a1 = i * 2 * math.pi / n + 0.004, (i + 1) * 2 * math.pi / n - 0.004
        hard.ring(R_PLANK + 0.02, R_INRIM, a0, a1, -0.25, 0.035, "wood",
                  jitter(C["darkwood"], 0.1, rnd), seg=6)
    # --- flagstones: two rows ---
    rows = [(R_INRIM + 0.04, (R_INRIM + R_STONE) / 2, 18), ((R_INRIM + R_STONE) / 2, R_STONE - 0.02, 22)]
    gap = 0.07
    for r0, r1, cnt in rows:
        step = 2 * math.pi / cnt
        off = rnd.uniform(0, step)
        cuts = [off + i * step + rnd.uniform(-0.28, 0.28) * step for i in range(cnt)]
        for i in range(cnt):
            a0 = cuts[i]
            a1 = cuts[(i + 1) % cnt] + (2 * math.pi if i == cnt - 1 else 0)
            ga0 = gap / 2 / r0
            top = rnd.uniform(-0.03, 0.02)
            tilt = rnd.uniform(-0.012, 0.012)
            hard.ring(r0 + gap / 2, r1 - gap / 2, a0 + ga0, a1 - ga0, -0.25, top, "stone",
                      jitter(C["stone"], 0.18, rnd), seg=max(3, int((a1 - a0) * r1 / 0.6)),
                      ztop_fn=lambda a, r, t=tilt, a0=a0: t * (a - a0) * r)
    # --- outer wood rim ---
    n = 28
    for i in range(n):
        a0, a1 = i * 2 * math.pi / n + 0.003, (i + 1) * 2 * math.pi / n - 0.003
        hard.ring(R_STONE, R_RIM, a0, a1, -0.3, 0.09, "wood", jitter(C["darkwood"], 0.12, rnd), seg=5)
    ob = hard.to_object("SM_ArenaFloor", coll)
    assign_types(ob, "P_Floor", grain=(6, 0.3, 6))
    bevel_apply(ob, 0.025, 1, 40)
    return finalize(ob, "SM_ArenaFloor", tex=4096)


def build_border():
    """One 22.5 degree gingerbread border module. Pivot = arena centre: in UE
    place 16 copies at the same location with yaw = k * 22.5."""
    coll = fresh_scene()
    rnd = random.Random(11)
    half = math.pi / BORDER_MODULES
    a0, a1 = -half, half
    hard, soft = Builder(), Builder()
    # gingerbread slab with a gently domed top
    hard.ring(R_RIM - 0.05, R_GINGER, a0, a1, -0.35, GINGER_TOP, "ginger", C["ginger"], seg=10,
              ztop_fn=lambda a, r: 0.06 * math.sin(math.pi * (r - R_RIM) / (R_GINGER - R_RIM)))
    zt = lambda r: GINGER_TOP + 0.06 * math.sin(math.pi * (r - R_RIM) / (R_GINGER - R_RIM))
    ic = C["icing"]
    # pearl bead row on the inner edge (integer count per module -> seamless)
    nb = 22
    rb = R_RIM + 0.17
    for i in range(nb):
        a = a0 + (i + 0.5) * (a1 - a0) / nb
        soft.blob((rb * math.cos(a), rb * math.sin(a), zt(rb) + 0.02), (0.14, 0.14, 0.11), "icing",
                  jitter(ic, 0.03, rnd))
    # wavy piping line
    def arc_pts(rfn, zfn, n=140):
        pts = []
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            r = rfn(a)
            pts.append((r * math.cos(a), r * math.sin(a), zfn(r)))
        return pts
    rw = R_RIM + 1.05
    soft.tube(arc_pts(lambda a: rw + 0.22 * math.sin(8 * 2 * math.pi * (a - a0) / (a1 - a0)),
                      lambda r: zt(r) + 0.03), 0.055, "icing", ic)
    # straight piping lines
    for rr in (R_RIM + 1.55, R_GINGER - 0.55):
        soft.tube(arc_pts(lambda a: rr, lambda r: zt(r) + 0.02, 40), 0.045, "icing", ic)
    # scalloped outer drape
    soft.tube(arc_pts(lambda a: R_GINGER - 0.08 - 0.1 * abs(math.sin(10 * math.pi * (a - a0) / (a1 - a0))),
                      lambda r: zt(r) + 0.01, 160), 0.075, "icing", ic)
    # centre star (gingerbread with icing outline)
    rs = (R_RIM + 1.55 + R_GINGER - 0.55) / 2
    cx, cy = rs, 0.0
    star = []
    for k in range(10):
        ang = math.pi / 2 + k * math.pi / 5
        rad = 0.62 if k % 2 == 0 else 0.27
        star.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    hard.star_prism(star, (cx, cy), zt(rs) - 0.05, zt(rs) + 0.07, "ginger", jitter(C["ginger"], 0.1, rnd))
    soft.tube([(x, y, zt(rs) + 0.08) for x, y in star + star[:1]], 0.035, "icing", ic, cap=False)
    # two swirls either side of the star
    for side in (-1, 1):
        ac = side * half * 0.55
        sx, sy = rs * math.cos(ac), rs * math.sin(ac)
        pts = []
        for i in range(60):
            th = i / 59 * 3.2 * math.pi
            r = 0.06 + 0.11 * th / math.pi
            pts.append((sx + side * r * math.cos(th), sy + r * math.sin(th), zt(rs) + 0.02))
        soft.tube(pts, 0.04, "icing", ic)
    # gumdrop candies on the outer band
    for i, acol in enumerate([THREADS["pink"], (0.3, 0.6, 0.45)]):
        a = (-0.5 + i) * half
        r = R_GINGER - 0.3 - 0.0
        soft.blob((r * math.cos(a) - 0.2, r * math.sin(a), zt(r) + 0.06), (0.13, 0.13, 0.1), "icing",
                  acol)
    obh = hard.to_object("hard", coll)
    obs = soft.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, "P_Border", scale_mul=1.0)
    bevel_apply(obh, 0.06, 2, 40)
    ob = join([obh, obs], "SM_ArenaBorder")
    return finalize(ob, "SM_ArenaBorder", tex=2048)


def spool_builder(rnd, palette):
    hard, soft = Builder(), Builder()
    H, FR, FT, TR, HOLE = 2.4, 1.0, 0.26, 0.78, 0.22
    wood = C["spoolwood"]
    # flanges (with a darker inner hole ring)
    for z0 in (0.0, H - FT):
        hard.ring(HOLE, FR, 0, 2 * math.pi, z0, z0 + FT, "wood", jitter(wood, 0.05, rnd), seg=24, closed=True)
    # hole bottom (hidden depth)
    hard.cyl(HOLE, HOLE, H - FT - 0.3, H - FT - 0.28, "wood", C["darkwood"], seg=12)
    # thread bands
    z = FT
    bands = []
    top = H - FT
    i = 0
    while z < top - 0.05:
        hgt = min(rnd.uniform(0.35, 0.7), top - z)
        bands.append((z, z + hgt, i % len(palette)))
        z += hgt
        i += 1
    for z0, z1, ci in bands:
        bulge = rnd.uniform(-0.03, 0.04)
        hard.ring(0.3, TR + bulge, 0, 2 * math.pi, z0, z1, "thread", palette[ci], seg=24, closed=True)
    # loose thread end hanging down to the floor
    zz = bands[-1][0] + 0.15
    pts = []
    for k in range(30):
        tt = k / 29
        rr = TR + 0.03 + 0.7 * tt
        ang = 0.9 * tt
        pts.append((rr * math.cos(ang), rr * math.sin(ang), max(0.03, zz * (1 - tt) ** 1.6) + 0.02))
    soft.tube(pts, 0.035, "thread", palette[bands[-1][2]], sides=5)
    return hard, soft, bands


def build_spool():
    coll = fresh_scene()
    rnd = random.Random(3)
    base_pal = [THREADS["green"], THREADS["red"], THREADS["blue"], THREADS["yellow"], THREADS["purple"]]
    hard, soft, bands = spool_builder(rnd, base_pal)
    obh, obs = hard.to_object("hard", coll), soft.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, "P_Spool")
    bevel_apply(obh, 0.04, 2, 40)
    ob = join([obh, obs], "SM_Spool")

    def recolor_to(col):
        def f(o):
            layer = o.data.attributes["Col"]
            tids = {i for i, m in enumerate(o.data.materials) if m.name.split(".")[0].endswith("_thread")}
            for p in o.data.polygons:
                if p.material_index in tids:
                    for li in p.loop_indices:
                        layer.data[li].color = (*col, 1.0)
        return f
    variants = {"": None, "_Red": recolor_to(THREADS["red"]), "_Blue": recolor_to(THREADS["blue"]),
                "_Yellow": recolor_to(THREADS["yellow"])}
    return finalize(ob, "SM_Spool", tex=1024, variants=variants)


def build_candle():
    coll = fresh_scene()
    rnd = random.Random(5)
    hard, soft = Builder(), Builder()
    # brass dish
    hard.cyl(0.46, 0.5, 0.0, 0.05, "metal", C["brass"], seg=20)
    hard.ring(0.42, 0.5, 0, 2 * math.pi, 0.05, 0.12, "metal", C["brass"], seg=20, closed=True)
    soft.tube([(0.5 + 0.12 * math.cos(t / 11 * 2 * math.pi), 0, 0.07 + 0.12 * math.sin(t / 11 * 2 * math.pi))
               for t in range(12)], 0.022, "metal", C["brass"], sides=5, cap=False)
    # wax body
    R, H = 0.2, 1.35
    wax = C["wax"]
    hard.cyl(R, R * 0.97, 0.05, H, "wax", wax, seg=14)
    # melted rim and drips
    soft.tube([(R * 0.95 * math.cos(a / 15 * 2 * math.pi), R * 0.95 * math.sin(a / 15 * 2 * math.pi), H)
               for a in range(16)], 0.035, "wax", wax, sides=5, cap=False)
    for i in range(9):
        a = i / 9 * 2 * math.pi + rnd.uniform(-0.2, 0.2)
        ln = rnd.uniform(0.08, 0.45)
        soft.blob((R * 0.93 * math.cos(a), R * 0.93 * math.sin(a), H - ln / 2), (0.045, 0.045, ln / 2 + 0.03),
                  "wax", jitter(wax, 0.03, rnd))
    # wax puddle on the dish
    soft.blob((0, 0, 0.06), (0.32, 0.32, 0.035), "wax", wax, subdiv=2)
    # wick
    soft.tube([(0, 0, H - 0.01), (0.005, 0, H + 0.06), (0.02, 0.005, H + 0.11)], 0.012, "metal", C["wick"], sides=4)
    obh, obs = hard.to_object("hard", coll), soft.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, "P_Candle")
    bevel_apply(obh, 0.015, 1, 40)
    ob = join([obh, obs], "SM_Candle")
    # flame: separate mesh, emissive material in UE (not baked)
    fb = Builder()
    fb.blob((0.02, 0.005, H + 0.2), (0.055, 0.055, 0.08), "wax", (1, 0.6, 0.2), subdiv=2, stretch_top=2.2)
    fl = fb.to_object("SM_CandleFlame", coll)
    fm = bpy.data.materials.new("M_CandleFlame")
    fm.use_nodes = True
    nt = fm.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.55, 0.15, 1)
    em.inputs["Strength"].default_value = 12.0
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs[0])
    fl.data.materials.append(fm)
    for p in fl.data.polygons:
        p.material_index = 0
    for a in list(fl.data.color_attributes):
        fl.data.color_attributes.remove(a)
    select_only([fl]); bpy.ops.object.shade_smooth()
    return finalize(ob, "SM_Candle", tex=512, extra_export=[fl])


# ======================= BATCH 2 =======================
METAL = (0.55, 0.57, 0.62)
PEARL = (0.86, 0.84, 0.80)
CREAM = (0.90, 0.82, 0.70)
SPONGE = (0.46, 0.21, 0.07)
CHERRY = (0.55, 0.03, 0.04)
BUTTONS = dict(Pink=(0.80, 0.30, 0.40), Mint=(0.25, 0.60, 0.45), Yellow=(0.85, 0.60, 0.12),
               Blue=(0.20, 0.38, 0.70))


def recolor_type(tname, col):
    def f(o):
        layer = o.data.attributes["Col"]
        ids = {i for i, m in enumerate(o.data.materials) if m.name.split(".")[0].endswith("_" + tname)}
        for p in o.data.polygons:
            if p.material_index in ids:
                for li in p.loop_indices:
                    layer.data[li].color = (*col, 1.0)
    return f


def box(b, center, size, t, col, rot=(0, 0, 0)):
    M = (Matrix.Translation(center) @ Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y")
         @ Matrix.Rotation(rot[0], 4, "X") @ Matrix.Diagonal((*size, 1.0)))
    res = bmesh.ops.create_cube(b.bm, size=1.0, matrix=M)
    b._paint(b._faces_of(res["verts"]), t, col)


def prism_y(b, poly_xz, y0, y1, t, col):
    """convex polygon in the XZ plane extruded along Y."""
    fs = b.prism(poly_xz, y0, y1, t, col)
    vs = {v for f in fs for v in f.verts}
    for v in vs:
        x, y, z = v.co
        v.co = Vector((x, z, y))


def torus(b, center, R, r, t, col, seg=20, sides=6, zscale=1.0):
    pts = [(center[0] + R * math.cos(i / seg * 2 * math.pi), center[1] + R * math.sin(i / seg * 2 * math.pi),
            center[2]) for i in range(seg + 1)]
    n0 = len(b.bm.verts)
    b.tube(pts, r, t, col, sides=sides, cap=False)
    if zscale != 1.0:
        b.bm.verts.ensure_lookup_table()
        for v in b.bm.verts[n0:]:
            v.co.z = center[2] + (v.co.z - center[2]) * zscale


def drips_ring(b, rnd, R, z, col, n=14, rmin=0.12, rmax=0.45, thick=0.09):
    """icing rim + hanging drops around a cylinder edge."""
    torus(b, (0, 0, z), R, thick, "icing", col, seg=max(16, n * 2), sides=6)
    for i in range(n):
        a = i / n * 2 * math.pi + rnd.uniform(-0.15, 0.15)
        ln = rnd.uniform(rmin, rmax)
        b.blob((R * math.cos(a), R * math.sin(a), z - ln / 2), (thick * 0.95, thick * 0.95, ln / 2 + 0.04),
               "icing", col)


def build_needle():
    """Giant sewing needle, ~8 m. Pivot at the tip: sink the tip into the floor and tilt in UE."""
    coll = fresh_scene()
    b, s = Builder(), Builder()
    L = 6.6
    prof = lambda u: 0.02 + 0.17 * min(1.0, u / 0.35) ** 0.8
    pts = [(0, 0, L * u) for u in [i / 24 for i in range(25)]]
    b.tube(pts, lambda u: prof(u), "metal", METAL, sides=12)
    # eye: stadium loop on the XZ plane
    hw, z0, z1, tr = 0.17, L - 0.15, L + 1.45, 0.1
    eye = []
    for i in range(13):  # bottom arc
        a = math.pi + i / 12 * math.pi
        eye.append((hw * math.cos(a), 0, z0 + 0.25 + 0.25 * math.sin(a)))
    for i in range(13):  # top arc
        a = i / 12 * math.pi
        eye.append((hw * math.cos(a), 0, z1 - 0.25 + 0.25 * math.sin(a)))
    eye.append(eye[0])
    b.tube(eye, tr, "metal", METAL, sides=8, cap=False)
    # red thread through the eye, falling to the floor
    th = [(-0.6, 0.25, 0.04), (-0.55, 0.3, 1.8), (-0.3, 0.2, 4.6), (0, 0.0, L + 0.6), (0.12, -0.05, L + 0.75),
          (0.35, -0.12, L + 0.5), (0.8, -0.3, 3.5), (1.1, -0.35, 1.2), (1.5, -0.5, 0.05), (2.2, -0.3, 0.04)]
    fine = []
    for i in range(len(th) - 1):
        for k in range(6):
            tt = k / 6
            fine.append(tuple(th[i][j] * (1 - tt) + th[i + 1][j] * tt for j in range(3)))
    fine.append(th[-1])
    s.tube(fine, 0.045, "thread", THREADS["red"], sides=6)
    obh, obs = b.to_object("hard", coll), s.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, "P_Needle")
    ob = join([obh, obs], "SM_Needle")
    return finalize(ob, "SM_Needle", tex=1024)


def build_pin():
    """Pearl-head pin, 3.2 m. Pivot at the tip. Variants: pearl / red / blue head."""
    coll = fresh_scene()
    b = Builder()
    L = 3.0
    pts = [(0, 0, L * i / 10) for i in range(11)]
    b.tube(pts, lambda u: 0.006 + 0.034 * min(1.0, u / 0.12), "metal", METAL, sides=8)
    b.blob((0, 0, L + 0.13), (0.2, 0.2, 0.2), "icing", PEARL, subdiv=2)
    ob = b.to_object("SM_Pin", coll)
    assign_types(ob, "P_Pin")
    variants = {"": None, "_Red": recolor_type("icing", (0.65, 0.06, 0.06)),
                "_Blue": recolor_type("icing", (0.15, 0.25, 0.65))}
    return finalize(ob, "SM_Pin", tex=512, variants=variants)


def build_button():
    """Four-hole sewing button, 0.8 m wide, with a stitched thread cross."""
    coll = fresh_scene()
    rnd = random.Random(9)
    b, s = Builder(), Builder()
    R = 0.4
    col = BUTTONS["Pink"]
    b.cyl(R, R * 0.97, 0.0, 0.1, "wax", col, seg=24)
    b.ring(R * 0.78, R, 0, 2 * math.pi, 0.08, 0.15, "wax", col, seg=24, closed=True)
    # holes: painted dark discs (type "stone" so recolouring the body leaves them alone)
    for hx, hy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        s.cyl(0.055, 0.055, 0.085, 0.103, "stone", (0.05, 0.035, 0.03), seg=10, loc=(hx * 0.11, hy * 0.11))
    tc = (0.85, 0.75, 0.55)
    for a, c in (((0.11, 0.11), (-0.11, -0.11)), ((-0.11, 0.11), (0.11, -0.11))):
        pts = [(a[0] + (c[0] - a[0]) * k / 8, a[1] + (c[1] - a[1]) * k / 8, 0.12 + 0.03 * math.sin(math.pi * k / 8))
               for k in range(9)]
        s.tube(pts, 0.025, "thread", tc, sides=5)
    obh, obs = b.to_object("hard", coll), s.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, "P_Button")
    bevel_apply(obh, 0.02, 2, 40)
    ob = join([obh, obs], "SM_Button")
    variants = {"": None}
    for k in ("Mint", "Yellow", "Blue"):
        variants["_" + k] = recolor_type("wax", BUTTONS[k])
    return finalize(ob, "SM_Button", tex=512, variants=variants)


HOUSES = {
    "A": dict(w=2.6, d=2.2, h=1.5, rh=1.2, chimney=0.6, windows=1, seed=21),
    "B": dict(w=2.0, d=2.6, h=2.3, rh=1.3, chimney=-0.4, windows=2, seed=22),
}


def build_ginger_house(var="A"):
    p = HOUSES[var]
    coll = fresh_scene()
    rnd = random.Random(p["seed"])
    b, s = Builder(), Builder()
    w, d, h, rh = p["w"], p["d"], p["h"], p["rh"]
    gc = C["ginger"]
    ic = C["icing"]
    # body with gable ends (pentagon extruded along Y)
    prism_y(b, [(-w / 2, 0), (w / 2, 0), (w / 2, h), (0, h + rh), (-w / 2, h)], -d / 2, d / 2, "ginger", gc)
    # roof panels with icing "snow"
    half = w / 2 + 0.25
    ang = math.atan2(rh, w / 2)
    plen = math.hypot(w / 2, rh) + 0.3
    for side in (-1, 1):
        cx = side * (plen / 2 - 0.18) * math.cos(ang)
        cz = h + rh - (plen / 2 - 0.18) * math.sin(ang) + 0.08
        box(b, (cx, 0, cz), (plen, d + 0.5, 0.14), "ginger", jitter(gc, 0.06, rnd), rot=(0, side * ang, 0))
        nz = Vector((side * math.sin(ang), 0, math.cos(ang)))
        box(b, Vector((cx, 0, cz)) + nz * 0.1, (plen * 0.96, d + 0.56, 0.07), "icing", ic, rot=(0, side * ang, 0))
        # eave drips
        ex = side * (w / 2 + 0.25)
        ez = h - 0.03
        for k in range(9):
            y = -d / 2 - 0.2 + (d + 0.4) * (k + 0.5) / 9
            ln = rnd.uniform(0.12, 0.35)
            s.blob((ex, y, ez - ln / 2), (0.07, 0.07, ln / 2 + 0.04), "icing", ic)
    # ridge piping + gumdrops
    s.tube([(0, -d / 2 - 0.28, h + rh + 0.2), (0, d / 2 + 0.28, h + rh + 0.2)], 0.08, "icing", ic)
    gum = [THREADS["pink"], (0.3, 0.6, 0.45), THREADS["yellow"], THREADS["red"]]
    for k in range(4):
        y = -d / 2 + d * (k + 0.5) / 4
        s.blob((0, y, h + rh + 0.32), (0.13, 0.13, 0.11), "wax", gum[k % 4])
    # chimney
    cxp = p["chimney"]
    czb = h + rh * (1 - abs(cxp) / (w / 2))
    box(b, (cxp, d * 0.2, czb + 0.35), (0.35, 0.35, 0.9), "ginger", jitter(gc, 0.1, rnd))
    box(s, (cxp, d * 0.2, czb + 0.83), (0.42, 0.42, 0.08), "icing", ic)
    # door (front = -Y), arched with icing outline
    door = [(-0.32, 0.0), (0.32, 0.0), (0.32, 0.75)] + \
           [(0.32 * math.cos(a), 0.75 + 0.32 * math.sin(a)) for a in [i / 6 * math.pi for i in range(1, 6)]] + \
           [(-0.32, 0.75)]
    prism_y(b, door, -d / 2 - 0.04, -d / 2 + 0.02, "ginger", tuple(c * 0.45 for c in gc))
    s.tube([(x, -d / 2 - 0.05, z) for x, z in door[1:] + door[:1]], 0.04, "icing", ic, cap=False)
    s.blob((0.2, -d / 2 - 0.07, 0.45), (0.05, 0.05, 0.05), "wax", THREADS["yellow"])
    # candy windows (front and sides)
    wins = []
    rows = [h * 0.55] if p["windows"] == 1 else [h * 0.42, h * 0.8]
    for z in rows:
        for x in (-w * 0.3, w * 0.3):
            if abs(x) < 0.45 and z < 1.2:
                continue
            wins.append(("front", x, z))
        wins.append(("side", 0.0, z))
    for kind, x, z in wins:
        sz = 0.34
        if kind == "front":
            box(b, (x, -d / 2 - 0.02, z), (sz, 0.06, sz), "wax", (0.95, 0.65, 0.2))
            for dx, dz, sx, szz in ((0, sz / 2, sz + 0.1, 0.06), (0, -sz / 2, sz + 0.1, 0.06),
                                    (sz / 2, 0, 0.06, sz), (-sz / 2, 0, 0.06, sz), (0, 0, 0.04, sz), (0, 0, sz, 0.04)):
                box(s, (x + dx, -d / 2 - 0.06, z + dz), (sx, 0.05, szz), "icing", ic)
        else:
            for sd in (-1, 1):
                box(b, (sd * (w / 2 + 0.02), x, z), (0.06, sz, sz), "wax", (0.95, 0.65, 0.2))
                box(s, (sd * (w / 2 + 0.06), x, z), (0.05, sz + 0.1, 0.05), "icing", ic)
                box(s, (sd * (w / 2 + 0.06), x, z), (0.05, 0.05, sz + 0.1), "icing", ic)
    # icing trim along the base and the gable edges
    for y in (-d / 2 - 0.03, d / 2 + 0.03):
        s.tube([(-w / 2, y, 0.06), (w / 2, y, 0.06)], 0.05, "icing", ic)
        s.tube([(-w / 2 - 0.02, y, h), (0, y, h + rh), (w / 2 + 0.02, y, h)], 0.06, "icing", ic)
    # zigzag icing band on the walls
    zz = []
    for k in range(17):
        zz.append((-w / 2 + w * k / 16, -d / 2 - 0.035, h * 0.18 + (0.08 if k % 2 else -0.08)))
    s.tube(zz, 0.035, "icing", ic)
    obh, obs = b.to_object("hard", coll), s.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, f"P_House{var}")
    bevel_apply(obh, 0.04, 2, 40)
    name = f"SM_GingerHouse_{var}"
    ob = join([obh, obs], name)
    return finalize(ob, name, tex=1024)


def build_cake_tower():
    """3-tier cake tower landmark (~5.5 m) with arched door, turrets, cream swirl and cherry."""
    coll = fresh_scene()
    rnd = random.Random(31)
    b, s = Builder(), Builder()
    ic = CREAM
    tiers = [(2.3, 0.0, 1.5), (1.7, 1.5, 2.7), (1.15, 2.7, 3.65)]
    for R, z0, z1 in tiers:
        b.cyl(R, R * 0.98, z0, z1, "ginger", jitter(SPONGE, 0.05, rnd), seg=28)
        drips_ring(s, rnd, R * 0.99, z1, ic, n=int(R * 9), rmax=0.55 if R > 2 else 0.4, thick=0.1)
        # icing disc on top of the tier
        b.cyl(R * 0.99, R * 0.99, z1, z1 + 0.06, "icing", ic, seg=28)
        # pearl row at the base
        nb = int(2 * math.pi * R / 0.32)
        for i in range(nb):
            a = i / nb * 2 * math.pi
            s.blob((R * math.cos(a), R * math.sin(a), z0 + 0.08), (0.1, 0.1, 0.09), "icing", ic)
    # gingerbread cross decorations + windows on tiers
    for R, z0, z1 in tiers:
        n = 6 if R > 2 else 5
        for i in range(n):
            a = -math.pi / 2 + (i + 0.5) / n * 2 * math.pi
            if R > 2 and abs(a + math.pi / 2) < 0.6:
                continue
            zc = (z0 + z1) / 2
            px, py = (R + 0.01) * math.cos(a), (R + 0.01) * math.sin(a)
            if i % 2 == 0:  # window: candy pane in icing frame
                box(b, (px, py, zc), (0.06, 0.38, 0.45), "wax", (0.95, 0.62, 0.18), rot=(0, 0, a))
                box(s, (px + 0.03 * math.cos(a), py + 0.03 * math.sin(a), zc + 0.27), (0.06, 0.5, 0.06), "icing", ic, rot=(0, 0, a))
                box(s, (px + 0.03 * math.cos(a), py + 0.03 * math.sin(a), zc - 0.27), (0.06, 0.5, 0.06), "icing", ic, rot=(0, 0, a))
            else:           # cookie cross
                box(b, (px, py, zc), (0.08, 0.14, 0.5), "ginger", (0.55, 0.26, 0.09), rot=(0, 0, a))
                box(b, (px, py, zc + 0.05), (0.08, 0.42, 0.14), "ginger", (0.55, 0.26, 0.09), rot=(0, 0, a))
    # arched door on the bottom tier, facing -Y
    R0 = tiers[0][0]
    door = [(-0.5, 0.0), (0.5, 0.0), (0.5, 0.75)] + \
           [(0.5 * math.cos(a), 0.75 + 0.5 * math.sin(a)) for a in [i / 8 * math.pi for i in range(1, 8)]] + [(-0.5, 0.75)]
    prism_y(b, door, -R0 - 0.06, -R0 + 0.25, "ginger", (0.06, 0.03, 0.015))
    s.tube([(x * 1.08, -R0 - 0.08, z * 1.04) for x, z in door[1:] + door[:1]], 0.07, "icing", ic, cap=False)
    # side turrets with cream tops
    for sd in (-1, 1):
        tx, ty = sd * (R0 + 0.15), 0.35
        b.cyl(0.55, 0.5, 0.0, 1.9, "ginger", jitter(SPONGE, 0.08, rnd), seg=16, loc=(tx, ty))
        for k in range(4):
            torus(s, (tx, ty, 1.95 + k * 0.17), 0.45 - k * 0.1, 0.12 - k * 0.015, "icing", ic, seg=14, sides=6)
        s.blob((tx, ty, 2.6), (0.08, 0.08, 0.1), "icing", ic, stretch_top=2.0)
    # cream swirl on top + cherry
    zt = tiers[-1][2] + 0.06
    for k in range(6):
        torus(s, (0, 0, zt + 0.18 + k * 0.26), 0.85 - k * 0.14, 0.22 - k * 0.022, "icing", ic, seg=20, sides=7)
    s.blob((0, 0, zt + 1.78), (0.12, 0.12, 0.14), "icing", ic, stretch_top=2.2)
    s.blob((0, 0, zt + 2.12), (0.32, 0.32, 0.3), "wax", CHERRY, subdiv=2)
    s.tube([(0, 0, zt + 2.38), (0.05, 0.02, zt + 2.6), (0.18, 0.05, zt + 2.8)], 0.03, "wood", (0.15, 0.25, 0.05), sides=5)
    # strawberries on the second tier
    for a in (0.7, 2.6, 4.4):
        R1, z1 = tiers[1][0], tiers[1][2]
        s.blob(((R1 - 0.2) * math.cos(a), (R1 - 0.2) * math.sin(a), z1 + 0.3), (0.22, 0.22, 0.28), "wax", (0.7, 0.05, 0.05))
    obh, obs = b.to_object("hard", coll), s.to_object("soft", coll)
    for o in (obh, obs):
        assign_types(o, "P_Cake")
    bevel_apply(obh, 0.05, 2, 40)
    ob = join([obh, obs], "SM_CakeTower")
    return finalize(ob, "SM_CakeTower", tex=2048)


# ======================= PREVIEW =======================
def append_objects(blend):
    with bpy.data.libraries.load(blend, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    return [o for o in dst.objects if o]


def set_engine(sc):
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = e
            return e
        except TypeError:
            pass


def preview():
    coll = fresh_scene()
    sc = bpy.context.scene
    B = lambda n: os.path.join(OUT, "Blend", f"{n}.blend")
    floor = append_objects(B("SM_ArenaFloor"))
    border = append_objects(B("SM_ArenaBorder"))[0]
    spool = append_objects(B("SM_Spool"))[0]
    cand = append_objects(B("SM_Candle"))
    for o in floor:
        coll.objects.link(o)
    coll.objects.link(border)
    for k in range(1, BORDER_MODULES):
        c = border.copy()
        c.rotation_euler.z = k * 2 * math.pi / BORDER_MODULES
        coll.objects.link(c)
    # spool variants (separate materials using each baked texture)
    def variant_mat(base, tex):
        m = base.copy()
        m.node_tree.nodes["Image Texture"].image = bpy.data.images.load(
            os.path.join(OUT, "Textures", tex), check_existing=True)
        return m
    spools = []
    rnd = random.Random(2)
    positions = [(7.0, -6.0, 0, 0.0), (-17.5, -6.5, GINGER_TOP, 0), (-16.8, -8.4, GINGER_TOP, 0),
                 (6.5, -17.8, GINGER_TOP, 0), (8.4, -17.0, GINGER_TOP, 0), (17.2, 7.5, GINGER_TOP, 0),
                 (-5, 17.6, GINGER_TOP, 0)]
    texs = ["T_SM_Spool_D.png", "T_SM_Spool_Red_D.png", "T_SM_Spool_Blue_D.png", "T_SM_Spool_Yellow_D.png"]
    base_mat = spool.data.materials[0]
    for i, (x, y, z, _) in enumerate(positions):
        o = spool.copy(); o.data = spool.data.copy()
        o.data.materials[0] = variant_mat(base_mat, texs[i % 4])
        o.location = (x, y, z)
        o.rotation_euler.z = rnd.uniform(0, 6.28)
        coll.objects.link(o)
        spools.append(o)
    candle, flame = (cand[0], cand[1]) if cand[0].name.startswith("SM_Candle") and "Flame" not in cand[0].name else (cand[1], cand[0])
    cpos = [(-12.0, 13.6), (-13.0, 12.2), (16.6, -3.0), (-17.8, 1.5), (3.0, 18.0), (12.5, -12.0)]
    for x, y in cpos:
        for src in (candle, flame):
            o = src.copy()
            o.location = (x, y, GINGER_TOP)
            coll.objects.link(o)
        lt = bpy.data.lights.new("candle", "POINT")
        lt.energy, lt.color, lt.shadow_soft_size = 900, (1.0, 0.6, 0.3), 0.3
        lo = bpy.data.objects.new("candleL", lt); lo.location = (x, y, GINGER_TOP + 1.9)
        coll.objects.link(lo)
    # ---- batch 2 props, if built ----
    b2 = {}
    for n in ("SM_Needle", "SM_Pin", "SM_Button", "SM_GingerHouse_A", "SM_GingerHouse_B", "SM_CakeTower"):
        if os.path.exists(B(n)):
            b2[n] = [o for o in append_objects(B(n)) if o.type == "MESH"][0]
    def place(n, loc, rot=(0, 0, 0), tex=None):
        o = b2[n].copy()
        if tex:
            o.data = b2[n].data.copy()
            o.data.materials[0] = variant_mat(b2[n].data.materials[0], tex)
        o.location, o.rotation_euler = loc, rot
        coll.objects.link(o)
        return o
    placed2 = []
    if b2:
        placed2 += [
            place("SM_CakeTower", (2.5, 15.2, 0), (0, 0, 0.15)),
            place("SM_GingerHouse_A", (-8.5, 13.6, GINGER_TOP * 0), (0, 0, -0.5)),
            place("SM_GingerHouse_B", (11.5, 11.2, 0), (0, 0, 0.6)),
            place("SM_Needle", (-4.0, 1.5, -0.6), (math.radians(-12), math.radians(-14), 0)),
            place("SM_Pin", (5.2, -2.0, -0.3), (math.radians(70), 0, math.radians(30))),
            place("SM_Pin", (6.0, -3.6, -0.3), (math.radians(65), 0, math.radians(55)), "T_SM_Pin_Red_D.png"),
        ]
        for (x, y), tx in zip([(-3.2, -5.0), (-2.0, -6.0), (-4.4, -6.3), (2.4, -7.6), (0.6, -4.2)],
                              ["T_SM_Button_D.png", "T_SM_Button_Mint_D.png", "T_SM_Button_Yellow_D.png",
                               "T_SM_Button_Blue_D.png", "T_SM_Button_Mint_D.png"]):
            placed2.append(place("SM_Button", (x, y, 0.0), (0, 0, rnd.uniform(0, 6.28)), tx))
    # doll-sized reference capsule (1.8 m)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.8, location=(0, 0, 0.9))
    ref = bpy.context.active_object
    rm = bpy.data.materials.new("ref"); rm.use_nodes = True
    rm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.35, 0.5, 1)
    ref.data.materials.append(rm)
    # lights & world
    world = bpy.data.worlds.new("W"); sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.010, 0.016, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 0.8; sun.color = (1.0, 0.85, 0.7); sun.angle = 0.2
    so = bpy.data.objects.new("sun", sun); so.rotation_euler = (math.radians(40), 0, math.radians(30))
    coll.objects.link(so)
    key = bpy.data.lights.new("key", "AREA"); key.energy = 4500; key.size = 18; key.color = (1.0, 0.75, 0.5)
    ko = bpy.data.objects.new("key", key); ko.location = (0, 0, 16)
    coll.objects.link(ko)
    # isometric camera
    tgt = bpy.data.objects.new("tgt", None); coll.objects.link(tgt)
    cam = bpy.data.cameras.new("cam"); cam.type = "ORTHO"; cam.ortho_scale = 44
    co = bpy.data.objects.new("cam", cam); coll.objects.link(co)
    pitch, yaw, dist = math.radians(42), math.radians(-90 + 0), 80
    co.location = (dist * math.cos(pitch) * math.cos(yaw), dist * math.cos(pitch) * math.sin(yaw), dist * math.sin(pitch))
    tc = co.constraints.new("TRACK_TO"); tc.target = tgt; tc.track_axis = "TRACK_NEGATIVE_Z"; tc.up_axis = "UP_Y"
    sc.camera = co
    eng = set_engine(sc)
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    try:
        sc.eevee.use_shadows = True
        sc.eevee.use_raytracing = True
    except Exception:
        pass
    sc.render.filepath = os.path.join(OUT, "Preview", "arena_overview.png")
    bpy.ops.render.render(write_still=True)
    # close-up of props
    cam.ortho_scale = 9
    tgt.location = (7.0, -6.0, 1.0)
    for o in spools[1:]:
        o.hide_render = True
    sp2 = []
    for i, tex in enumerate(texs[1:]):
        o = spool.copy(); o.data = spool.data.copy()
        o.data.materials[0] = variant_mat(base_mat, tex)
        o.location = (7.0 + (i - 1) * 2.4, -8.6, 0)
        coll.objects.link(o)
    for dx in (-1.2, 1.4):
        for src in (candle, flame):
            o = src.copy(); o.location = (7.0 + dx * 2.2, -4.2, 0); coll.objects.link(o)
    co.location = (7.0, -6.0 - 40 * math.cos(math.radians(35)), 1 + 40 * math.sin(math.radians(35)))
    ref.location = (5.0, -5.0, 0.9)
    sc.render.filepath = os.path.join(OUT, "Preview", "props_closeup.png")
    bpy.ops.render.render(write_still=True)
    if b2:
        # batch 2 line-up on a clean spot of the plank floor
        for o in coll.objects:
            if o.type == "MESH" and not o.name.startswith(("SM_ArenaFloor", "SM_ArenaBorder")):
                o.hide_render = True
        ref.hide_render = False
        lineup = [("SM_CakeTower", (0.0, 3.5, 0), (0, 0, 0), None),
                  ("SM_GingerHouse_A", (-5.2, 2.2, 0), (0, 0, 0.35), None),
                  ("SM_GingerHouse_B", (5.0, 2.2, 0), (0, 0, -0.35), None),
                  ("SM_Needle", (-7.6, -0.6, 0), (0, 0, 0.3), None),
                  ("SM_Pin", (7.2, -1.2, 0), (0, 0, 0), None),
                  ("SM_Pin", (7.9, -0.4, 0), (0, 0, 0), "T_SM_Pin_Red_D.png"),
                  ("SM_Pin", (8.6, 0.4, 0), (0, 0, 0), "T_SM_Pin_Blue_D.png")]
        for i, tx in enumerate(["T_SM_Button_D.png", "T_SM_Button_Mint_D.png", "T_SM_Button_Yellow_D.png",
                                "T_SM_Button_Blue_D.png"]):
            lineup.append(("SM_Button", (-1.8 + i * 1.2, -2.6, 0.0), (math.radians(-35), 0, 0), tx))
        for n, loc, rot, tx in lineup:
            o = place(n, loc, rot, tx)
            if n == "SM_Button":
                o.location.z = 0.32
        ref.location = (-2.6, -0.6, 0.9)
        cam.ortho_scale = 19
        tgt.location = (0.3, 0.8, 2.6)
        co.location = (0.3, 0.8 - 40 * math.cos(math.radians(28)), 2.6 + 40 * math.sin(math.radians(28)))
        for lo in [o for o in coll.objects if o.name.startswith("candleL")]:
            lo.hide_render = True
        sc.render.filepath = os.path.join(OUT, "Preview", "props2_lineup.png")
        bpy.ops.render.render(write_still=True)
    print("[arena] preview done with", eng)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        argv = ["build", "floor", "border", "spool", "candle"]
    if argv[0] == "build":
        fns = dict(floor=build_floor, border=build_border, spool=build_spool, candle=build_candle,
                   needle=build_needle, pin=build_pin, button=build_button,
                   houseA=lambda: build_ginger_house("A"), houseB=lambda: build_ginger_house("B"),
                   cake=build_cake_tower)
        for n in argv[1:]:
            fns[n]()
    elif argv[0] == "preview":
        preview()
