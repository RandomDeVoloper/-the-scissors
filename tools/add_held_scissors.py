"""
Bez bebegin (BP_BabyDoll) sag eline makas takar.

Mesh : /Game/Art/Scissors/SK_Scissor_Rigid  (olcek kucultulur, orijinali ~8 m)
Anim : /Game/Art/Scissors/SK_Scissor_Rigid_Anim  (bicaklar acilip kapanir, dongu)
Bone : righthand  (socket/skeleton'a dokunulmaz, dogrudan bone adina baglanir)

EDITOR ACIKKEN editorun kendi konsolundan calistirin (Output Log > Cmd > Python):
    py "C:/Users/Niyazi/-the-scissors/tools/add_held_scissors.py"
Headless calistirmayin: editorde acik olan BP_BabyDoll'un uzerine yazar.

Zaten ekliyse hicbir sey yapmaz. Konum/donus tahminidir: BP_BabyDoll'u acip
HeldScissors bilesenini Viewport'ta elin icine oturtmak yeterli (asagidaki sabitler).
Test icin HELD_TARGET ortam degiskeniyle baska bir BP verilebilir.
"""
import os
import unreal

TARGET = os.environ.get("HELD_TARGET", "/Game/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll")
MESH = "/Game/Art/Scissors/SK_Scissor_Rigid"
ANIM = "/Game/Art/Scissors/SK_Scissor_Rigid_Anim"
NAME = "HeldScissors"
BONE = "righthand"

# Tahmini yerlesim (el kemiginde parmaklar yerel -Y yonune uzaniyor)
SCALE = 0.08                      # ~65 cm makas, bebek ~170 cm
LOCATION = unreal.Vector(0.0, -4.0, 0.0)
ROTATION = unreal.Rotator(roll=0.0, pitch=0.0, yaw=-90.0)

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log("[HeldScissors] " + s)


def main():
    bp = unreal.load_asset(TARGET)
    mesh = unreal.load_asset(MESH)
    anim = unreal.load_asset(ANIM)
    if bp is None or mesh is None or anim is None:
        raise RuntimeError("Bulunamadi: %s / %s / %s" % (TARGET, MESH, ANIM))
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)

    mesh_handle = None
    for h in handles:
        obj = lib.get_object(lib.get_data(h))
        if obj is None:
            continue
        if obj.get_name() == NAME:
            log("Zaten ekli:", NAME, "- degisiklik yok")
            return
        if mesh_handle is None and isinstance(obj, unreal.SkeletalMeshComponent):
            mesh_handle = h
    if mesh_handle is None:
        raise RuntimeError("Karakterin Mesh bileseni bulunamadi")

    params = unreal.AddNewSubobjectParams(
        parent_handle=mesh_handle, new_class=unreal.SkeletalMeshComponent, blueprint_context=bp)
    handle, fail = sds.add_new_subobject(params)
    if not lib.is_handle_valid(handle):
        raise RuntimeError("Bilesen eklenemedi: %s" % fail)
    sds.rename_subobject(handle, unreal.Text(NAME))
    comp = lib.get_object(lib.get_data(handle))

    comp.set_editor_property("skeletal_mesh_asset", mesh)
    comp.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    data = comp.get_editor_property("animation_data")
    data.set_editor_property("anim_to_play", anim)
    data.set_editor_property("saved_looping", True)
    data.set_editor_property("saved_playing", True)
    comp.set_editor_property("animation_data", data)
    comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    comp.set_editor_property("cast_shadow", True)
    comp.set_editor_property("relative_scale3d", unreal.Vector(SCALE, SCALE, SCALE))
    comp.set_editor_property("relative_location", LOCATION)
    comp.set_editor_property("relative_rotation", ROTATION)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)  # yeni degisken graph'larda gorunsun

    # Python SCS node'unun AttachToName'ine erisemiyor; bone'a baglamayi
    # Construction Script'te Attach To Component(Mesh, "righthand") ile yapiyoruz.
    GE = unreal.BlueprintGraphEditor
    ed = GE.get_graph_editor_by_name(bp, "UserConstructionScript")
    if ed is None:
        raise RuntimeError("UserConstructionScript graph'i bulunamadi")
    IN, OUT = unreal.EdGraphPinDirection.EGPD_INPUT, unreal.EdGraphPinDirection.EGPD_OUTPUT

    def pin(node, name, direction):
        for p in unreal.BlueprintEditorLibrary.list_all_pins(node, direction):
            if str(p.get_pin_name()).lower() == name.lower():
                return p
        raise RuntimeError("Pin yok: %s (%s)" % (name, [str(p.get_pin_name()) for p in unreal.BlueprintEditorLibrary.list_all_pins(node)]))

    attach = ed.add_call_function_node("/Script/Engine.SceneComponent.K2_AttachToComponent")
    if attach is None:
        raise RuntimeError("K2_AttachToComponent node'u olusturulamadi")
    held = ed.add_get_member_variable_node(NAME)
    mesh_var = ed.add_get_member_variable_node("Mesh", "/Script/Engine.Character")
    entry = ed.find_graph_entry_pin()
    start = entry.get_owning_node().get_node_pos()
    attach.set_node_pos(unreal.IntPoint(start.x + 400, start.y))
    held.set_node_pos(unreal.IntPoint(start.x + 120, start.y + 220))
    mesh_var.set_node_pos(unreal.IntPoint(start.x + 120, start.y + 320))
    # Construction Script'in mevcut akisinin sonuna ekle (varsa)
    nxt = entry.list_connected_pins()
    if nxt:
        target = nxt[0]
        entry.break_pin_links()
        entry.try_create_connection(pin(attach, "execute", IN))
        pin(attach, "then", OUT).try_create_connection(target)
    else:
        entry.try_create_connection(pin(attach, "execute", IN))
    for ok, label in (
        (pin(held, NAME, OUT).try_create_connection(pin(attach, "self", IN)), "self"),
        (pin(mesh_var, "Mesh", OUT).try_create_connection(pin(attach, "Parent", IN)), "Parent"),
    ):
        if not ok:
            raise RuntimeError("Baglanti kurulamadi: " + label)
    pin(attach, "SocketName", IN).set_pin_value(BONE)
    for rule in ("LocationRule", "RotationRule", "ScaleRule"):
        pin(attach, rule, IN).set_pin_value("KeepRelative")
    log("Construction Script: Attach To Component(Mesh,", BONE, ")")

    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    status = bp.get_editor_property("status")
    log("Eklendi, derleme:", status)
    if status not in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
        raise RuntimeError("Derleme basarisiz: %s" % status)
    if os.environ.get("HELD_DRY") != "1":
        if not unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False):
            raise RuntimeError("Kaydedilemedi")
        log("Kaydedildi:", TARGET)
    else:
        log("DRY: kaydedilmedi")


try:
    main()
    log("SONUC: OK")
except Exception as e:  # noqa
    import traceback
    log("SONUC: HATA", e)
    log(traceback.format_exc())
finally:
    out = os.environ.get("HELD_LOG")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
