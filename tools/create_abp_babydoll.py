"""
Bez bebek (BabyDoll) icin Animation Blueprint olusturur.

Calistirma (editor icinden):  Output Log > Cmd > Python:
    py "C:/Users/Niyazi/-the-scissors/tools/create_abp_babydoll.py"
veya headless:
    UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=".../create_abp_babydoll.py"

Olusan asset: /Game/SurvivorsTemplate/Blueprints/Character/BabyDoll/ABP_BabyDoll_Locomotion
Mevcut hicbir asset degistirilmez; hedef asset zaten varsa script durur.

Yapi
  EventGraph:
    BlueprintUpdateAnimation -> Cast To BP_Base_Character(TryGetPawnOwner)
      -> Set Speed    = VectorLengthXY(GetVelocity)
      -> Set IsMoving = Speed > 10
      -> Set IsDead   = BP_Base_Character.IsDead
  AnimGraph:
    Play AS_Idle --(False)--\
                             Blend Poses by bool (IsMoving) --(False)--\
    Play AS_Run  --(True)---/                                           Blend Poses by bool (IsDead)
    Play AS_Dead (loop yok) ---------------------------------(True)----/        |
                                                                         Slot 'DefaultSlot' -> Output Pose
  Not: UE Python API'si state machine'in ICINE state/transition eklemeyi desteklemiyor.
  Ayni mantik (Idle<->Run Speed>10, her durumdan Death) "Blend Poses by bool" ile kuruldu.
  Attack / Death montage'lari DefaultSlot uzerinden oynar (Montage Play).
"""
import os
import unreal

DRY_RUN = os.environ.get("ABP_DRY") == "1"
PKG = "/Game/__ClaudeTmp" if DRY_RUN else "/Game/SurvivorsTemplate/Blueprints/Character/BabyDoll"
NAME = "ABP_BabyDoll_Locomotion"
SKELETON = "/Game/SurvivorsTemplate/Blueprints/Character/BabyDoll/Meshy_AI_Patchwork_Sweetheart_20261126_animated_mixamo_Run_03_Skeleton"
CHAR_CLASS = "/Game/SurvivorsTemplate/Blueprints/Character/BP_Base_Character.BP_Base_Character_C"
RUN_THRESHOLD = "10.0"

BEL = unreal.BlueprintEditorLibrary
GE = unreal.BlueprintGraphEditor
V = unreal.Vector2D
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log("[ABP_BabyDoll] " + s)


class StepError(Exception):
    pass


def need(obj, what):
    if obj is None:
        raise StepError("Olusturulamadi: " + what)
    return obj


def pins(node):
    return list(BEL.list_all_pins(node))


def pin(node, *names, direction=None):
    """Isme gore pin bul (buyuk/kucuk harf ve bosluk duyarsiz, once tam eslesme)."""
    cands = pins(node)
    if direction is not None:
        cands = [p for p in cands if p.get_pin_direction() == direction]
    norm = lambda s: str(s).lower().replace(" ", "")
    for want in names:
        for p in cands:
            if norm(p.get_pin_name()) == norm(want):
                return p
    for want in names:
        for p in cands:
            if norm(want) in norm(p.get_pin_name()):
                return p
    raise StepError("Pin bulunamadi %s on %s; mevcut: %s" % (
        names, BEL.get_node_title(node), [str(p.get_pin_name()) for p in pins(node)]))


IN = unreal.EdGraphPinDirection.EGPD_INPUT
OUT = unreal.EdGraphPinDirection.EGPD_OUTPUT


def link(a, b, label):
    if not a.try_create_connection(b):
        raise StepError("Baglanti kurulamadi: " + label)


def by_name(ed, name, pos):
    return need(ed.create_node_from_name(name, V(*pos), []), name)


def main():
    asset_path = PKG + "/" + NAME
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        raise StepError(asset_path + " zaten var; hicbir sey degistirilmedi.")

    skel = need(unreal.load_asset(SKELETON), "skeleton")
    factory = unreal.AnimBlueprintFactory()
    factory.set_editor_property("target_skeleton", skel)
    factory.set_editor_property("parent_class", unreal.AnimInstance)
    bp = need(unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        NAME, PKG, unreal.AnimBlueprint, factory), "AnimBlueprint")
    log("AnimBP olusturuldu:", bp.get_path_name())

    # --- Degiskenler -------------------------------------------------------
    for vname, tname in (("Speed", "real"), ("IsMoving", "bool"), ("IsDead", "bool")):
        if not BEL.add_member_variable(bp, vname, BEL.get_basic_type_by_name(tname)):
            raise StepError("Degisken eklenemedi: " + vname)
        BEL.set_blueprint_variable_category(bp, vname, "BabyDoll")
    BEL.compile_blueprint(bp)  # degiskenler graph'larda gorunsun
    log("Degiskenler: Speed(float), IsMoving(bool), IsDead(bool)")

    # --- EventGraph --------------------------------------------------------
    eg = need(GE.get_graph_editor_by_name(bp, "EventGraph"), "EventGraph editor")
    ev = eg.find_event_node("BlueprintUpdateAnimation")
    if ev is None:
        ev = by_name(eg, "AddEvent|EventBlueprintUpdateAnimation", (0, 0))
    ev.set_node_pos(unreal.IntPoint(0, 0))
    # Template'in kendiliginden ekledigi bos TryGetPawnOwner'i yeniden kullan
    pawn = None
    for n in eg.list_all_nodes():
        if "TryGetPawnOwner" in str(BEL.get_node_title(n)):
            pawn = n
    if pawn is None:
        pawn = need(eg.add_call_function_node("/Script/Engine.AnimInstance.TryGetPawnOwner"), "TryGetPawnOwner")
    pawn.set_node_pos(unreal.IntPoint(0, 220))

    char_cls = need(unreal.load_object(None, CHAR_CLASS), "BP_Base_Character class")
    cast = by_name(eg, "Utilities|Casting|CastToCharacter", (320, 0))
    if not eg.retarget_node_class(cast, unreal.Character, char_cls):
        raise StepError("Cast BP_Base_Character'a cevrilemedi")
    link(pin(pawn, "ReturnValue", direction=OUT), pin(cast, "Object", direction=IN), "Pawn -> Cast")
    link(pin(ev, "then", direction=OUT), pin(cast, "execute", direction=IN), "Event -> Cast")
    as_char = pin(cast, "AsBP Base Character", "As", direction=OUT)

    get_vel = need(eg.add_call_function_node("/Script/Engine.Actor.GetVelocity"), "GetVelocity")
    get_vel.set_node_pos(unreal.IntPoint(640, 220))
    link(as_char, pin(get_vel, "self", direction=IN), "Char -> GetVelocity")
    vlen = need(eg.add_call_function_node("/Script/Engine.KismetMathLibrary.VSizeXY"), "VectorLengthXY")
    vlen.set_node_pos(unreal.IntPoint(900, 220))
    link(pin(get_vel, "ReturnValue", direction=OUT), pin(vlen, "A", direction=IN), "Velocity -> VSizeXY")

    set_speed = need(eg.add_set_member_variable_node("Speed"), "Set Speed")
    set_speed.set_node_pos(unreal.IntPoint(1150, 0))
    link(pin(cast, "then", direction=OUT), pin(set_speed, "execute", direction=IN), "Cast -> Set Speed")
    link(pin(vlen, "ReturnValue", direction=OUT), pin(set_speed, "Speed", direction=IN), "VSizeXY -> Speed")

    greater = need(eg.add_call_function_node("/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"), "Greater")
    greater.set_node_pos(unreal.IntPoint(1450, 220))
    link(pin(set_speed, "Speed", "Output_Get", direction=OUT), pin(greater, "A", direction=IN), "Speed -> >")
    pin(greater, "B", direction=IN).set_pin_value(RUN_THRESHOLD)

    set_moving = need(eg.add_set_member_variable_node("IsMoving"), "Set IsMoving")
    set_moving.set_node_pos(unreal.IntPoint(1700, 0))
    link(pin(set_speed, "then", direction=OUT), pin(set_moving, "execute", direction=IN), "Set Speed -> Set IsMoving")
    link(pin(greater, "ReturnValue", direction=OUT), pin(set_moving, "IsMoving", direction=IN), "> -> IsMoving")

    get_dead = need(eg.add_get_member_variable_node("IsDead", CHAR_CLASS), "Get Character.IsDead")
    get_dead.set_node_pos(unreal.IntPoint(1700, 260))
    link(as_char, pin(get_dead, "self", "Target", direction=IN), "Char -> IsDead getter")

    set_dead = need(eg.add_set_member_variable_node("IsDead"), "Set IsDead")
    set_dead.set_node_pos(unreal.IntPoint(2000, 0))
    link(pin(set_moving, "then", direction=OUT), pin(set_dead, "execute", direction=IN), "Set IsMoving -> Set IsDead")
    link(pin(get_dead, "IsDead", direction=OUT), pin(set_dead, "IsDead", direction=IN), "Char.IsDead -> IsDead")
    log("EventGraph kuruldu (Cast -> Speed -> IsMoving -> IsDead)")

    # --- AnimGraph ---------------------------------------------------------
    ag = need(GE.get_graph_editor_by_name(bp, "AnimGraph"), "AnimGraph editor")
    root = [n for n in ag.list_all_nodes() if n.get_class().get_name() == "AnimGraphNode_Root"][0]
    root.set_node_pos(unreal.IntPoint(1400, 0))

    idle = by_name(ag, "Animation|Sequences|Play'AS_Idle'", (0, -200))
    run = by_name(ag, "Animation|Sequences|Play'AS_Run'", (0, 0))
    dead = by_name(ag, "Animation|Sequences|Play'AS_Dead'", (300, 260))
    dn = dead.get_editor_property("node")
    dn.set_editor_property("loop_animation", False)
    dead.set_editor_property("node", dn)

    move_blend = by_name(ag, "Animation|Blends|BlendPosesbybool", (350, -100))
    dead_blend = by_name(ag, "Animation|Blends|BlendPosesbybool", (750, 0))
    for b, t in ((move_blend, 0.2), (dead_blend, 0.15)):
        bn = b.get_editor_property("node")
        try:
            bn.set_editor_property("blend_time", [t, t])
        except Exception as e:
            log("Uyari: blend_time ayarlanamadi:", e)
        if b is dead_blend:
            try:  # olum animasyonu her seferinde bastan baslasin
                bn.set_editor_property("child_upate_mode", unreal.BlendListChildUpdateMode.RESET_CHILD_ON_ACTIVATE)
            except Exception as e:
                log("Uyari: child update mode ayarlanamadi:", e)
        b.set_editor_property("node", bn)
        for i in (0, 1):  # BlendTime pinleri gorunur, onlara da ayni degeri yaz
            pin(b, "BlendTime_%d" % i, direction=IN).set_pin_value(str(t))
        log("Blend node:", bn.export_text()[:300])

    slot = by_name(ag, "Animation|Montage|Slot'DefaultSlot'", (1100, 0))

    get_moving = need(ag.add_get_member_variable_node("IsMoving"), "Get IsMoving")
    get_moving.set_node_pos(unreal.IntPoint(150, -260))
    get_isdead = need(ag.add_get_member_variable_node("IsDead"), "Get IsDead")
    get_isdead.set_node_pos(unreal.IntPoint(550, -120))

    # Blend Poses by bool: BlendPose_0 = True Pose, BlendPose_1 = False Pose
    link(pin(idle, "Pose", direction=OUT), pin(move_blend, "BlendPose_1", direction=IN), "Idle -> False")
    link(pin(run, "Pose", direction=OUT), pin(move_blend, "BlendPose_0", direction=IN), "Run -> True")
    link(pin(get_moving, "IsMoving", direction=OUT), pin(move_blend, "bActiveValue", "Active Value", direction=IN), "IsMoving -> Active")
    link(pin(move_blend, "Pose", direction=OUT), pin(dead_blend, "BlendPose_1", direction=IN), "Locomotion -> False")
    link(pin(dead, "Pose", direction=OUT), pin(dead_blend, "BlendPose_0", direction=IN), "Dead -> True")
    link(pin(get_isdead, "IsDead", direction=OUT), pin(dead_blend, "bActiveValue", "Active Value", direction=IN), "IsDead -> Active")
    link(pin(dead_blend, "Pose", direction=OUT), pin(slot, "Source", direction=IN), "Blend -> Slot")
    link(pin(slot, "Pose", direction=OUT), pin(root, "Result", direction=IN), "Slot -> Output Pose")
    log("AnimGraph kuruldu (Idle/Run/Dead + Blend by bool + DefaultSlot)")

    # --- Derle & kaydet ----------------------------------------------------
    BEL.compile_blueprint(bp)
    status = bp.get_editor_property("status")
    log("Derleme durumu:", status)
    if status not in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
        raise StepError("Derleme basarisiz: %s" % status)
    if DRY_RUN:
        log("DRY RUN: kaydedilmedi")
    else:
        if not unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False):
            raise StepError("Kaydedilemedi")
        log("Kaydedildi:", asset_path)


try:
    main()
    log("SONUC: OK")
except Exception as e:  # noqa
    import traceback
    log("SONUC: HATA", e)
    log(traceback.format_exc())
finally:
    out = os.environ.get("ABP_LOG")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
