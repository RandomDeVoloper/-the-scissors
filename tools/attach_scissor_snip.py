"""
BP_Ability_ScissorSnip bilesenini oyuncu karakterine ekler (BP_BabyDoll).

EDITOR ACIKKEN editorun kendi konsolundan calistirin (Output Log > Cmd > Python):
    py "C:/Users/Niyazi/-the-scissors/tools/attach_scissor_snip.py"
Headless calistirmayin: editorde acik olan BP_BabyDoll'un uzerine yazar.

Zaten ekliyse hicbir sey yapmaz. Bilesen derlenir ve BP kaydedilir.
Test icin ATTACH_TARGET ortam degiskeniyle baska bir BP verilebilir.
"""
import os
import unreal

TARGET = os.environ.get("ATTACH_TARGET", "/Game/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll")
COMP = "/Game/SurvivorsTemplate/Blueprints/Abilities/BP_Ability_ScissorSnip.BP_Ability_ScissorSnip_C"
NAME = "ScissorSnip"
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log("[ScissorSnip attach] " + s)


def main():
    bp = unreal.load_asset(TARGET)
    comp_cls = unreal.load_object(None, COMP)
    if bp is None or comp_cls is None:
        raise RuntimeError("Bulunamadi: %s / %s" % (TARGET, COMP))
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    for h in handles:
        obj = lib.get_object(lib.get_data(h))
        if obj is not None and obj.get_class() == comp_cls:
            log("Zaten ekli:", obj.get_name(), "- degisiklik yok")
            return
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=comp_cls, blueprint_context=bp)
    handle, fail = sds.add_new_subobject(params)
    if not lib.is_handle_valid(handle):
        raise RuntimeError("Bilesen eklenemedi: %s" % fail)
    sds.rename_subobject(handle, unreal.Text(NAME))
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    status = bp.get_editor_property("status")
    log("Eklendi, derleme:", status)
    if status not in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
        raise RuntimeError("Derleme basarisiz: %s" % status)
    if not unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False):
        raise RuntimeError("Kaydedilemedi")
    log("Kaydedildi:", TARGET)


try:
    main()
    log("SONUC: OK")
except Exception as e:  # noqa
    import traceback
    log("SONUC: HATA", e)
    log(traceback.format_exc())
finally:
    out = os.environ.get("ATTACH_LOG")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
