"""
Build /Game/Arena/Maps/M_Arena from M_Demo + the imported arena props (run import_arena.py first).
Editor must be CLOSED. Headless:
  UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=tools/ue/build_arena_level.py -unattended -nosplash -nullrhi

Keeps M_Demo's gameplay actors (BP_Game_Manager, PlayerStart, stashes, nav bounds, lights, outer walls),
removes the grey prototype blocks, darkens the big ground cube and lays out the arena:
  - floor + 16 gingerbread border modules (arena top at z=55, ground cube top is z=50)
  - invisible ring wall at r=1560: blocks the player, ignores Enemy/Projectile/Spawn/Camera/Visibility
  - props: tall decor only on the far side (+X, the gameplay camera looks along +X), low decor all around
  - warm point lights on candles, candelabras and lanterns
"""
import math
import unreal

SRC_MAP = "/Game/SurvivorsTemplate/Maps/M_Demo"
DST_MAP = "/Game/Arena/Maps/M_Arena"
M = "/Game/Arena/Meshes/"
MAT = "/Game/Arena/Materials/"
ZG = 50.0           # top of the big ground cube (outside decor)
Z0 = 55.0           # arena floor top (planks dip up to 2 cm, keep clear of the ground cube)
ZB = Z0 + 35.0      # gingerbread border top
EAL = unreal.EditorAssetLibrary
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
MEL = unreal.MaterialEditingLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
CH = unreal.CollisionChannel
RESP = unreal.CollisionResponseType


def log(m):
    unreal.log_warning("[arena] " + str(m))


# ---------- map copy ----------
if EAL.does_asset_exist(DST_MAP):
    if not EAL.delete_asset(DST_MAP):
        raise RuntimeError("delete Content/Arena/Maps/M_Arena.umap by hand and rerun")
if not EAL.duplicate_asset(SRC_MAP, DST_MAP):
    raise RuntimeError("duplicate failed")
LES.load_level(DST_MAP)

# ---------- ground material ----------
gpath = MAT + "M_ArenaGround"
if EAL.does_asset_exist(gpath):
    ground_mat = unreal.load_asset(gpath)
else:
    ground_mat = AT.create_asset("M_ArenaGround", MAT[:-1], unreal.Material, unreal.MaterialFactoryNew())
    c = MEL.create_material_expression(ground_mat, unreal.MaterialExpressionVectorParameter, -400, 0)
    c.set_editor_property("parameter_name", "Color")
    c.set_editor_property("default_value", unreal.LinearColor(0.035, 0.02, 0.012, 1))
    MEL.connect_material_property(c, "", unreal.MaterialProperty.MP_BASE_COLOR)
    r = MEL.create_material_expression(ground_mat, unreal.MaterialExpressionConstant, -400, 200)
    r.set_editor_property("r", 0.9)
    MEL.connect_material_property(r, "", unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.recompile_material(ground_mat)
    EAL.save_loaded_asset(ground_mat)

# ---------- clean prototype blocks ----------
stashes = []
removed = 0
for a in EAS.get_all_level_actors():
    cn = a.get_class().get_name()
    if cn == "StaticMeshActor":
        sm = a.static_mesh_component.static_mesh
        p = sm.get_path_name() if sm else ""
        if "/LevelPrototyping/" in p:
            EAS.destroy_actor(a)
            removed += 1
        elif a.get_actor_label() == "Cube":          # big ground plane
            a.static_mesh_component.set_material(0, ground_mat)
    elif cn == "BP_Stash_C":
        stashes.append(a)
    elif cn == "PlayerStart":
        a.set_actor_location(unreal.Vector(-200, 0, 147), False, False)
log("removed %d prototype blocks" % removed)
# stashes into the arena (evenly on r=10 m)
for i, a in enumerate(stashes):
    ang = (i + 0.5) / len(stashes) * 2 * math.pi
    l = a.get_actor_location()
    a.set_actor_location(unreal.Vector(1000 * math.cos(ang), 1000 * math.sin(ang), l.z + 5), False, False)


# ---------- helpers ----------
FOLDER = "Arena"


def spawn_mesh(sm, loc, rot):
    act = EAS.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)
    if act is None:
        raise RuntimeError("spawn failed for %s" % sm.get_name())
    act.static_mesh_component.set_static_mesh(sm)
    return act


def put(mesh, x, y, z, yaw=0.0, pitch=0.0, roll=0.0, mat=None, folder="Props", block_camera=False, scale=1.0):
    sm = unreal.load_asset(M + mesh)
    act = spawn_mesh(sm, unreal.Vector(x, y, z), unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw))
    act.set_actor_label(mesh.replace("SM_", ""))
    act.set_folder_path(FOLDER + "/" + folder)
    if scale != 1.0:
        act.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    comp = act.static_mesh_component
    comp.set_mobility(unreal.ComponentMobility.STATIC)
    if mat:
        comp.set_material(0, unreal.load_asset(MAT + mat))
    if not block_camera:
        comp.set_collision_response_to_channel(CH.ECC_CAMERA, RESP.ECR_IGNORE)
    return act


def polar(r, deg):
    a = math.radians(deg)
    return r * math.cos(a), r * math.sin(a)


def facing_center(deg):
    """props are modelled with their front on local +Y (UE)."""
    return deg + 90.0


def light(x, y, z, intensity=40.0, radius=700.0, color=(255, 160, 80)):
    act = EAS.spawn_actor_from_class(unreal.PointLight, unreal.Vector(x, y, z))
    act.set_folder_path(FOLDER + "/Lights")
    lc = act.point_light_component
    lc.set_intensity(intensity)
    lc.set_attenuation_radius(radius)
    lc.set_light_color(unreal.LinearColor(color[0] / 255, color[1] / 255, color[2] / 255, 1))
    lc.set_cast_shadows(False)
    return act


# ---------- floor + border ----------
put("SM_ArenaFloor", 0, 0, Z0, folder="Structure", block_camera=True)
for k in range(16):
    put("SM_ArenaBorder", 0, 0, Z0, yaw=k * 22.5, folder="Structure", block_camera=True)

# ---------- invisible wall ring ----------
cube = unreal.load_asset("/Engine/BasicShapes/Cube")
N, R = 32, 1560.0
seg = 2 * R * math.sin(math.pi / N) / 100.0 + 0.05
for i in range(N):
    deg = i * 360.0 / N
    x, y = polar(R + 10, deg)
    w = spawn_mesh(cube, unreal.Vector(x, y, Z0 + 200), unreal.Rotator(yaw=deg + 90))
    w.set_actor_label("ArenaWall_%02d" % i)
    w.set_folder_path(FOLDER + "/Wall")
    w.set_actor_scale3d(unreal.Vector(seg, 0.2, 4.0))
    w.set_actor_hidden_in_game(True)
    c = w.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.STATIC)
    c.set_cast_shadow(False)
    c.set_editor_property("can_ever_affect_navigation", False)
    c.set_collision_profile_name("BlockAll")
    for ch in (CH.ECC_ENEMY, CH.ECC_PROJECTILE, CH.ECC_SPAWN,
               CH.ECC_PICK_UP_ITEM, CH.ECC_CAMERA, CH.ECC_VISIBILITY):
        c.set_collision_response_to_channel(ch, RESP.ECR_IGNORE)

# ---------- inside the arena ----------
put("SM_Needle", 450, 380, Z0 - 60, yaw=35, pitch=12, roll=-10)
put("SM_Spool", -550, -700, Z0, yaw=20)
put("SM_Spool", 700, -950, Z0, yaw=140, mat="MI_SM_Spool_Blue")
put("SM_Pin", 300, -450, Z0 + 6, yaw=30, pitch=-72)
put("SM_Pin", -750, 300, Z0 + 6, yaw=-60, pitch=-70, mat="MI_SM_Pin_Red")
for (x, y), m in zip([(-200, 420), (-330, 560), (160, -260), (-80, -380), (520, 120)],
                     ["MI_SM_Button", "MI_SM_Button_Mint", "MI_SM_Button_Yellow", "MI_SM_Button_Blue", "MI_SM_Button_Mint"]):
    put("SM_Button", x, y, Z0, yaw=(x * 7 + y) % 360, mat=m)

# ---------- on the gingerbread border ----------
put("SM_CakeTower", *polar(1760, 0), ZB, yaw=facing_center(0), block_camera=True)
put("SM_GingerHouse_A", *polar(1740, 38), ZB, yaw=facing_center(38))
put("SM_GingerHouse_B", *polar(1740, -38), ZB, yaw=facing_center(-38))
for deg in (20, 62, 105, 145, 180, 215, 255, 298, 340):
    x, y = polar(1830, deg)
    put("SM_Candle", x, y, ZB, yaw=deg * 3, folder="Candles")
    put("SM_CandleFlame", x, y, ZB, yaw=deg * 3, folder="Candles")
    light(x, y, ZB + 190)
for deg, m in ((120, None), (128, "MI_SM_Spool_Red"), (196, "MI_SM_Spool_Yellow"), (232, "MI_SM_Spool_Blue"),
               (240, None), (275, "MI_SM_Spool_Red"), (80, "MI_SM_Spool_Yellow")):
    put("SM_Spool", *polar(1700 + (deg % 7) * 20, deg), ZB, yaw=deg * 5, mat=m)

# ---------- outside, far side (+X): tall backdrop ----------
for i in range(13):
    deg = -80 + i * (160 / 12)
    put("SM_WallArch", *polar(2600, deg), ZG, yaw=facing_center(deg), folder="Backdrop")
put("SM_Mirror_A", *polar(2300, -52), ZG, yaw=facing_center(-52), folder="Backdrop")
put("SM_Mirror_B", *polar(2300, 52), ZG, yaw=facing_center(52), folder="Backdrop")
put("SM_Bookshelf", *polar(2380, -25), ZG, yaw=facing_center(-25), folder="Backdrop")
put("SM_Bookshelf", *polar(2380, 25), ZG, yaw=facing_center(25), folder="Backdrop")
for deg in (-68, -12, 12, 68, 95, -95):
    x, y = polar(2160, deg)
    put("SM_Candelabra", x, y, ZG, yaw=facing_center(deg), folder="Backdrop")
    put("SM_CandelabraFlames", x, y, ZG, yaw=facing_center(deg), folder="Backdrop")
    light(x, y, ZG + 260, intensity=60, radius=900)
for deg, m in ((-36, "MI_SM_FabricRoll_Purple"), (36, "MI_SM_FabricRoll_Red"), (-40, None), (40, "MI_SM_FabricRoll_Pink")):
    r = 2160 if abs(deg) < 38 else 2230
    put("SM_FabricRoll", *polar(r, deg), ZG, yaw=facing_center(deg), mat=m, folder="Backdrop")
put("SM_Strawberry", *polar(2180, -5), ZG, yaw=40)
put("SM_Strawberry", *polar(2200, 7), ZG, yaw=200)

# ---------- outside, near/side: low decor only (camera side) ----------
for deg in (90, 125, 160, 200, 235, 270):
    x, y = polar(2120, deg)
    lan = put("SM_CandyCaneLantern", x, y, ZG, yaw=deg + 180, folder="Lanterns")
    # lantern body hangs ~90 cm along the post's local +X
    yawr = math.radians(deg + 180)
    light(x + 90 * math.cos(yawr), y + 90 * math.sin(yawr), ZG + 240, intensity=50, radius=800,
          color=(255, 120, 90))
for deg, m in ((140, None), (146, "MI_SM_Spool_Blue"), (180, "MI_SM_Spool_Red"), (218, "MI_SM_Spool_Yellow"),
               (250, None), (110, "MI_SM_Spool_Red")):
    put("SM_Spool", *polar(2250, deg), ZG, yaw=deg * 3, mat=m, folder="Outer")
for deg, m in ((150, "MI_SM_FabricRoll_Pink"), (208, None), (262, "MI_SM_FabricRoll_Purple")):
    put("SM_FabricRoll", *polar(2380, deg), ZG, yaw=facing_center(deg), mat=m, folder="Outer")
for deg in (132, 228, 170):
    put("SM_Strawberry", *polar(2350, deg), ZG, yaw=deg)

LES.save_current_level()
counts = {}
for a in EAS.get_all_level_actors():
    k = a.get_class().get_name()
    counts[k] = counts.get(k, 0) + 1
log("level actors: %s" % counts)
log("LEVEL DONE " + DST_MAP)
