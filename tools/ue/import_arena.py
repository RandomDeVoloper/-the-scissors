"""
Import the Blender arena props (Art/Arena) into /Game/Arena.
Run headless with the editor CLOSED:
  UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=tools/ue/import_arena.py -unattended -nosplash -nullrhi

Creates:
  /Game/Arena/Textures/T_*            (all baked diffuse textures)
  /Game/Arena/Materials/M_ArenaProp   (master: BaseColor texture param, rough 0.85)
  /Game/Arena/Materials/M_ArenaFlame  (unlit emissive)
  /Game/Arena/Materials/MI_*          (one instance per texture)
  /Game/Arena/Meshes/SM_*             (static meshes with MI + collision)
"""
import os
import unreal

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ART = os.path.join(REPO, "Art", "Arena")
ROOT = "/Game/Arena"
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log_warning("[arena] " + str(msg))


def import_files(files, dest, options=None):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask()
        t.filename = f
        t.destination_path = dest
        t.automated = True
        t.replace_existing = True
        t.save = False
        if options:
            t.options = options
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    out = []
    for t in tasks:
        out += list(t.imported_object_paths)
    return out


# ---------------- textures ----------------
tex_dir = os.path.join(ART, "Textures")
pngs = [os.path.join(tex_dir, f) for f in sorted(os.listdir(tex_dir)) if f.endswith(".png")]
import_files(pngs, ROOT + "/Textures")
log("textures: %d" % len(pngs))

# ---------------- materials ----------------
def make_master():
    path = ROOT + "/Materials/M_ArenaProp"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    m = AT.create_asset("M_ArenaProp", ROOT + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
    tex = MEL.create_material_expression(m, unreal.MaterialExpressionTextureSampleParameter2D, -500, 0)
    tex.set_editor_property("parameter_name", "BaseColor")
    tex.set_editor_property("texture", unreal.load_asset(ROOT + "/Textures/T_SM_Spool_D"))
    MEL.connect_material_property(tex, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -300, 200)
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", 0.85)
    MEL.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    spec = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -300, 300)
    spec.set_editor_property("parameter_name", "Specular")
    spec.set_editor_property("default_value", 0.25)
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m)
    return m


def make_flame():
    path = ROOT + "/Materials/M_ArenaFlame"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    m = AT.create_asset("M_ArenaFlame", ROOT + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    col = MEL.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -500, 0)
    col.set_editor_property("parameter_name", "FlameColor")
    col.set_editor_property("default_value", unreal.LinearColor(1.0, 0.55, 0.15, 1.0))
    k = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -500, 200)
    k.set_editor_property("parameter_name", "Intensity")
    k.set_editor_property("default_value", 20.0)
    mul = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -250, 50)
    MEL.connect_material_expressions(col, "", mul, "A")
    MEL.connect_material_expressions(k, "", mul, "B")
    MEL.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(m)
    return m


master = make_master()
flame = make_flame()
mis = {}
for p in pngs:
    tname = os.path.splitext(os.path.basename(p))[0]          # T_SM_Spool_Red_D
    mi_name = "MI_" + tname[2:-2]                               # MI_SM_Spool_Red
    path = ROOT + "/Materials/" + mi_name
    if EAL.does_asset_exist(path):
        mi = unreal.load_asset(path)
    else:
        mi = AT.create_asset(mi_name, ROOT + "/Materials", unreal.MaterialInstanceConstant,
                             unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, master)
    MEL.set_material_instance_texture_parameter_value(mi, "BaseColor", unreal.load_asset(ROOT + "/Textures/" + tname))
    mis[tname[2:-2]] = mi
log("material instances: %s" % sorted(mis))

# ---------------- meshes ----------------
fbx_dir = os.path.join(ART, "FBX")
fbxs = [os.path.join(fbx_dir, f) for f in sorted(os.listdir(fbx_dir)) if f.endswith(".fbx")]
opts = None
try:
    ui = unreal.FbxImportUI()
    ui.import_materials = False
    ui.import_textures = False
    ui.import_as_skeletal = False
    ui.import_mesh = True
    ui.static_mesh_import_data.combine_meshes = True
    ui.static_mesh_import_data.auto_generate_collision = False
    ui.static_mesh_import_data.generate_lightmap_u_vs = True
    opts = ui
except Exception as e:
    log("FbxImportUI unavailable: %s" % e)
import_files(fbxs, ROOT + "/Meshes", opts)

COMPLEX = {"SM_ArenaFloor", "SM_ArenaBorder"}
NO_COLLISION = {"SM_Button", "SM_CandleFlame", "SM_CandelabraFlames", "SM_Pin", "SM_Strawberry"}
CAPSULE = {"SM_Spool", "SM_CakeTower", "SM_Candle"}


def box_elem(cx, cy, cz, sx, sy, sz):
    e = unreal.KBoxElem()
    e.set_editor_property("center", unreal.Vector(cx, cy, cz))
    e.set_editor_property("x", sx)
    e.set_editor_property("y", sy)
    e.set_editor_property("z", sz)
    return e


def sphyl_elem(cx, cy, cz, radius, length):
    e = unreal.KSphylElem()
    e.set_editor_property("center", unreal.Vector(cx, cy, cz))
    e.set_editor_property("radius", radius)
    e.set_editor_property("length", max(0.0, length))
    return e


def set_simple_collision(sm, name):
    """Editor-only collision helpers don't work in the commandlet, so write AggGeom directly."""
    bs = sm.get_editor_property("body_setup")
    ag = unreal.KAggregateGeom()
    flag = unreal.CollisionTraceFlag.CTF_USE_DEFAULT
    b = sm.get_bounding_box()
    c = (b.min + b.max) * 0.5
    ext = b.max - b.min
    boxes, sphyls = [], []
    if name in COMPLEX:
        flag = unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    elif name in NO_COLLISION:
        pass
    elif name == "SM_Needle":            # shaft + eye only, not the hanging thread
        sphyls.append(sphyl_elem(0, 0, 420, 22, 800))
    elif name == "SM_WallArch":
        for sx in (-1, 1):
            boxes.append(box_elem(sx * 275, 0, 350, 65, 65, 700))
        boxes.append(box_elem(0, 0, 720, 660, 60, 50))
    elif name in CAPSULE:
        r = 0.5 * max(ext.x, ext.y) * 0.92
        sphyls.append(sphyl_elem(c.x, c.y, c.z, r, ext.z - 2 * r))
    else:
        boxes.append(box_elem(c.x, c.y, c.z, ext.x, ext.y, ext.z))
    ag.set_editor_property("box_elems", boxes)
    ag.set_editor_property("sphyl_elems", sphyls)
    bs.set_editor_property("agg_geom", ag)
    bs.set_editor_property("collision_trace_flag", flag)
    return len(boxes) + len(sphyls)


for f in fbxs:
    name = os.path.splitext(os.path.basename(f))[0]
    path = ROOT + "/Meshes/" + name
    sm = unreal.load_asset(path)
    if not isinstance(sm, unreal.StaticMesh):
        log("MISSING mesh %s" % path)
        continue
    mat = flame if "Flame" in name else mis.get(name)
    if mat:
        sm.set_material(0, mat)
    n = set_simple_collision(sm, name)
    sm.modify()
    b = sm.get_bounding_box()
    log("mesh %s min=(%.0f,%.0f,%.0f) max=(%.0f,%.0f,%.0f) shapes=%d" % (
        name, b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z, n))

# drop anything else the importer generated next to the meshes (materials/textures)
for a in EAL.list_assets(ROOT + "/Meshes", recursive=True, include_folder=False):
    obj = EAL.load_asset(a)
    if not isinstance(obj, unreal.StaticMesh):
        log("removing importer extra %s" % a)
        EAL.delete_asset(a)

EAL.save_directory(ROOT, only_if_is_dirty=False, recursive=True)
log("IMPORT DONE")
