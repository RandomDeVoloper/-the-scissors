"""
Scissor Snip'i level-up kart sistemine baglar.

ON KOSUL (elle, editorde): E_ActiveAbilities'e Display Name'i "Scissor Snip" olan bir enumerator
ekleyip kaydedin. UE Python API'si enum'a deger ekleyemiyor.

Calistirma: editor KAPALIYKEN headless
    UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=".../integrate_scissor_snip_levelup.py"
Ortam degiskenleri:
    SNIP_DRY=1            hicbir sey kaydetme (sadece kur + derle + raporla)
    SNIP_TEST_ENUM=NewEnumerator3   (sadece DRY) enum eklenmeden test icin baska bir deger kullan
    SNIP_LOG=<dosya>      log dosyasi

Yaptiklari (her adim tekrar calistirildiginda zaten yapilmissa atlanir):
  1. BP_BabyDoll'da elle eklenmis ScissorSnip bileseni varsa kaldirir (artik kartla gelecek)
  2. BP_Ability_ScissorSnip'i SetSnipLevel fonksiyonuyla yeniden olusturur (create_scissor_snip.py)
  3. DT_ActiveAbilities'e ScissorSnip1..5 kart metinlerini ekler
  4. BP_Abilities_Component'e LevelUpScissorSnip ekler:
       ActiveAbilitiesMap[ScissorSnip] += 1  ->  bilesen yoksa AddComponentByClass  ->  SetSnipLevel(seviye)
  5. BP_Gameplay_PlayerController > Assign Ability: Switch on E_ActiveAbilities -> LevelUpScissorSnip
  6. BFL_Helper > FindActiveIcon: Scissor Snip ikonu
  7. Ilgili tum Blueprint'leri derler, hata varsa kaydetmez
"""
import os
import unreal

DRY = os.environ.get("SNIP_DRY") == "1"
B = "/Game/SurvivorsTemplate/Blueprints"
ENUM = B + "/Enums/E_ActiveAbilities"
DT = B + "/DataTables/DT_ActiveAbilities"
ABIL = B + "/Components/BP_Abilities_Component"
ABIL_C = ABIL + ".BP_Abilities_Component_C"
PC = B + "/System/BP_Gameplay_PlayerController"
BFL = B + "/BFL_Helper"
BABY = B + "/Character/BP_BabyDoll"
SNIP = B + "/Abilities/BP_Ability_ScissorSnip"
SNIP_C = SNIP + ".BP_Ability_ScissorSnip_C"
ICON = "/Game/SurvivorsTemplate/Textures/upgrade.upgrade"  # gecici ikon, nihai art gelince degistir
DISPLAY = "Scissor Snip"
ROW = "ScissorSnip"  # ExecuteLevelUp satir adini Display Name'den bosluklari silerek kurar
ROWS = [
    (ROW + "1", "Snip all enemies in a cone in front of you"),
    (ROW + "2", "Damage increased"),
    (ROW + "3", "Wider cone and longer reach"),
    (ROW + "4", "Damage increased, faster snips"),
    (ROW + "5", "Widest cone, maximum damage"),
]
FUNC = "LevelUpScissorSnip"
TOOLS = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "C:/Users/Niyazi/-the-scissors/tools"

BEL = unreal.BlueprintEditorLibrary
GE = unreal.BlueprintGraphEditor
EAL = unreal.EditorAssetLibrary
IN = unreal.EdGraphPinDirection.EGPD_INPUT
OUT = unreal.EdGraphPinDirection.EGPD_OUTPUT
LOG = []
TO_SAVE = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log("[SnipLevelUp] " + s)


class StepError(Exception):
    pass


def need(o, what):
    if o is None:
        raise StepError("Bulunamadi/olusturulamadi: " + what)
    return o


def pins(n):
    return list(BEL.list_all_pins(n))


def pin(n, *names, direction=None):
    c = [p for p in pins(n) if direction is None or p.get_pin_direction() == direction]
    norm = lambda s: str(s).lower().replace(" ", "")
    for w in names:
        for p in c:
            if norm(p.get_pin_name()) == norm(w):
                return p
    for w in names:
        for p in c:
            if norm(w) in norm(p.get_pin_name()):
                return p
    raise StepError("Pin yok %s on %s; mevcut %s" % (names, BEL.get_node_title(n), [str(p.get_pin_name()) for p in pins(n)]))


def link(a, b, label):
    if not a.try_create_connection(b):
        raise StepError("Baglanamadi: " + label)


def X(n):
    return pin(n, "execute", "exec", direction=IN)


def T(n):
    return pin(n, "then", direction=OUT)


def R(n):
    return pin(n, "ReturnValue", direction=OUT)


def at(n, x, y):
    n.set_node_pos(unreal.IntPoint(x, y))
    return n


def title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def compile_ok(bp, label):
    BEL.compile_blueprint(bp)
    st = bp.get_editor_property("status")
    log("Derleme", label, st)
    if st == unreal.BlueprintStatus.BS_ERROR:
        for gname in BEL.list_graph_names(bp):
            ged = GE.get_graph_editor_by_name(bp, gname)
            for n in (list(ged.list_nodes_with_errors()) if ged else []):
                log("  HATA [%s] %s: %s" % (gname, title(n), n.get_editor_property("error_msg")))
    if st not in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
        raise StepError("Derleme basarisiz: %s (%s)" % (label, st))


# --------------------------------------------------------------------------
def find_enum_value():
    if DRY and os.environ.get("SNIP_TEST_ENUM"):
        v = os.environ["SNIP_TEST_ENUM"]
        log("TEST: enum degeri yerine", v, "kullaniliyor")
        return v
    # Python enum'un display name'lerini okuyamiyor: (1) dosyada "Scissor Snip" metni var mi,
    # (2) Switch on E_ActiveAbilities'te sablonun 4 degeri disinda tek yeni pin hangisi.
    need(unreal.load_asset(ENUM), ENUM)
    fpath = unreal.SystemLibrary.get_project_content_directory() + ENUM[len("/Game/"):] + ".uasset"
    with open(fpath, "rb") as f:
        if DISPLAY.encode("utf-8") not in f.read():
            raise StepError("E_ActiveAbilities'te '%s' Display Name'i yok; editorde ekleyip kaydedin." % DISPLAY)
    pc = need(unreal.load_asset(PC), PC)
    ed = need(GE.get_graph_editor_by_name(pc, "Assign Ability"), "Assign Ability graph")
    sw = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "K2Node_SwitchEnum" and "E_ActiveAbilities" in title(n)][0]
    known = {"NewEnumerator%d" % i for i in range(4)}
    new = [str(p.get_pin_name()) for p in pins(sw) if p.get_pin_direction() == OUT
           and str(p.get_pin_name()).startswith("NewEnumerator") and str(p.get_pin_name()) not in known]
    if len(new) != 1:
        raise StepError("Yeni enum degeri belirlenemedi: %s" % new)
    log("Enum degeri:", new[0], "=", DISPLAY)
    return new[0]


def step_remove_from_babydoll():
    bp = need(unreal.load_asset(BABY), BABY)
    cls = unreal.load_object(None, SNIP_C)
    if cls is None:
        return
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = sds.k2_gather_subobject_data_for_blueprint(bp)
    for h in handles:
        o = lib.get_object(lib.get_data(h))
        if o is not None and o.get_class() == cls:
            n = sds.delete_subobject(handles[0], h, bp)
            log("BP_BabyDoll'dan ScissorSnip bileseni kaldirildi:", n)
            compile_ok(bp, "BP_BabyDoll")
            TO_SAVE.append(bp)
            return
    log("BP_BabyDoll'da ScissorSnip bileseni yok (degisiklik yok)")


def step_rebuild_snip():
    global SNIP, SNIP_C
    bp = unreal.load_asset(SNIP)
    if bp is not None and BEL.find_graph(bp, "SetSnipLevel") is not None:
        log("BP_Ability_ScissorSnip zaten SetSnipLevel iceriyor")
        return bp
    if DRY:  # gercek asset'e dokunma: gecici kopyayi /Game/__ClaudeTmp'e kur ve onu kullan
        SNIP = "/Game/__ClaudeTmp/BP_Ability_ScissorSnip"
        SNIP_C = SNIP + ".BP_Ability_ScissorSnip_C"
    else:
        os.environ["SNIP_OVERWRITE"] = "1"
        os.environ.pop("SNIP_DRY", None)
    sub_log = os.environ.get("SNIP_LOG", "") + ".create"
    os.environ["SNIP_LOG"], keep = sub_log, os.environ.get("SNIP_LOG")
    code = open(os.path.join(TOOLS, "create_scissor_snip.py"), encoding="utf-8").read()
    exec(compile(code, "create_scissor_snip.py", "exec"), {"__name__": "__main__"})
    if keep:
        os.environ["SNIP_LOG"] = keep
    bp = need(unreal.load_asset(SNIP), SNIP)
    if BEL.find_graph(bp, "SetSnipLevel") is None:
        raise StepError("BP_Ability_ScissorSnip yeniden olusturulamadi; bkz. " + sub_log)
    log("BP_Ability_ScissorSnip SetSnipLevel ile yeniden olusturuldu")
    return bp


def step_datatable():
    dt = need(unreal.load_asset(DT), DT)
    DTL = unreal.DataTableFunctionLibrary
    names = [str(n) for n in DTL.get_data_table_row_names(dt)]
    missing = [r for r in ROWS if r[0] not in names]
    if not missing:
        log("DT_ActiveAbilities satirlari zaten var")
        return
    csv = DTL.export_data_table_to_csv_string(dt).rstrip("\r\n")
    for rn, txt in missing:
        csv += '\n%s,"%s"' % (rn, txt.replace('"', '""'))
    before = len(names)
    if not DTL.fill_data_table_from_csv_string(dt, csv + "\n"):
        raise StepError("DT_ActiveAbilities doldurulamadi")
    after = [str(n) for n in DTL.get_data_table_row_names(dt)]
    if len(after) != before + len(missing) or any(r[0] not in after for r in missing):
        raise StepError("DT satir sayisi beklenmedik: %d -> %d" % (before, len(after)))
    log("DT_ActiveAbilities: eklendi", [r[0] for r in missing], "toplam", len(after))
    TO_SAVE.append(dt)


def step_levelup_function(enum_val):
    bp = need(unreal.load_asset(ABIL), ABIL)
    if BEL.find_graph(bp, FUNC) is not None:
        log(FUNC, "zaten var")
        return bp
    ed = need(GE.create_and_edit_function_graph(bp, FUNC), FUNC)
    need(ed.add_local_variable("L_Level", BEL.get_basic_type_by_name("int"), "0") or True, "L_Level")
    entry = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "K2Node_FunctionEntry"][0]
    at(entry, 0, 0)

    m1 = at(need(ed.add_get_member_variable_node("ActiveAbilitiesMap"), "Get map"), 0, 250)
    find = at(need(ed.add_call_function_node("/Script/Engine.BlueprintMapLibrary.Map_Find"), "Map_Find"), 250, 250)
    link(pin(m1, "ActiveAbilitiesMap", direction=OUT), pin(find, "TargetMap", direction=IN), "map -> Find")
    pin(find, "Key", direction=IN).set_pin_value(enum_val)
    plus = at(need(ed.add_call_function_node("/Script/Engine.KismetMathLibrary.Add_IntInt"), "+"), 500, 250)
    link(pin(find, "Value", direction=OUT), pin(plus, "A", direction=IN), "Find.Value -> +")
    pin(plus, "B", direction=IN).set_pin_value("1")
    set_l = at(need(ed.add_set_local_variable_node("L_Level"), "Set L_Level"), 300, 0)
    link(ed.find_graph_entry_pin(), X(set_l), "Entry -> Set L_Level")
    link(R(plus), pin(set_l, "L_Level", direction=IN), "+ -> L_Level")

    m2 = at(need(ed.add_get_member_variable_node("ActiveAbilitiesMap"), "Get map 2"), 550, 150)
    add = at(need(ed.add_call_function_node("/Script/Engine.BlueprintMapLibrary.Map_Add"), "Map_Add"), 650, 0)
    link(T(set_l), X(add), "Set L_Level -> Map_Add")
    link(pin(m2, "ActiveAbilitiesMap", direction=OUT), pin(add, "TargetMap", direction=IN), "map -> Add")
    pin(add, "Key", direction=IN).set_pin_value(enum_val)

    def get_l(x, y):
        return pin(at(need(ed.add_get_local_variable_node("L_Level"), "Get L_Level"), x, y), "L_Level", direction=OUT)

    link(get_l(500, 120), pin(add, "Value", direction=IN), "L_Level -> Add.Value")

    snip_cls = need(unreal.load_object(None, SNIP_C), "ScissorSnip class")
    owner = at(need(ed.add_call_function_node("/Script/Engine.ActorComponent.GetOwner"), "GetOwner"), 650, 300)
    gcbc = at(need(ed.add_call_function_node("/Script/Engine.Actor.GetComponentByClass"), "GCBC"), 900, 300)
    link(R(owner), pin(gcbc, "self", direction=IN), "Owner -> GCBC")
    pin(gcbc, "ComponentClass", direction=IN).set_pin_value(snip_cls.get_path_name())
    valid = at(need(ed.add_call_function_node("/Script/Engine.KismetSystemLibrary.IsValid"), "IsValid"), 1150, 300)
    link(R(gcbc), pin(valid, "Object", direction=IN), "GCBC -> IsValid")
    br = at(need(ed.add_branch_node(), "Branch"), 1000, 0)
    link(T(add), X(br), "Map_Add -> Branch")
    link(R(valid), pin(br, "Condition", direction=IN), "IsValid -> Branch")

    # yoksa ekle
    addc = None
    for name in ("Components|AddComponentbyClass", "AddComponentbyClass"):
        try:
            addc = ed.create_node_from_name(name, unreal.Vector2D(1300, 150), [])
        except Exception as e:
            log("create", name, e)
        if addc is not None:
            break
    if addc is None:
        addc = ed.add_call_function_node("/Script/Engine.Actor.AddComponentByClass")
    addc = at(need(addc, "AddComponentByClass"), 1300, 150)
    log("AddComponent node:", addc.get_class().get_name(), [str(p.get_pin_name()) for p in pins(addc)])
    link(pin(br, "else", direction=OUT), X(addc), "Branch false -> AddComponent")
    link(R(owner), pin(addc, "self", "Target", direction=IN), "Owner -> AddComponent")
    pin(addc, "Class", direction=IN).set_pin_value(snip_cls.get_path_name())
    mkt = at(need(ed.add_call_function_node("/Script/Engine.KismetMathLibrary.MakeTransform"), "MakeTransform"), 1100, 450)
    link(R(mkt), pin(addc, "RelativeTransform", direction=IN), "Identity -> RelativeTransform")

    set_fn = snip_cls.get_path_name() + ":SetSnipLevel"
    for i, (src_exec, obj, y) in enumerate(((T(br), R(gcbc), -150), (T(addc), R(addc), 150))):
        cast = at(need(ed.create_node_from_name("Utilities|Casting|CastToActorComponent", unreal.Vector2D(1700, y), []), "Cast"), 1700, y)
        if not ed.retarget_node_class(cast, unreal.ActorComponent, snip_cls):
            raise StepError("Cast ScissorSnip'e cevrilemedi")
        link(src_exec, X(cast), "-> Cast %d" % i)
        link(obj, pin(cast, "Object", direction=IN), "obj -> Cast %d" % i)
        call = at(need(ed.add_call_function_node(set_fn), "SetSnipLevel call"), 2000, y)
        link(T(cast), X(call), "Cast -> SetSnipLevel %d" % i)
        link(pin(cast, "AsBP Ability Scissor Snip", "As", direction=OUT), pin(call, "self", "Target", direction=IN), "Cast -> self %d" % i)
        link(get_l(1850, y + 120), pin(call, "NewLevel", direction=IN), "L_Level -> NewLevel %d" % i)
    compile_ok(bp, "BP_Abilities_Component")
    TO_SAVE.append(bp)
    log(FUNC, "eklendi")
    return bp


def step_assign_ability(enum_val):
    bp = need(unreal.load_asset(PC), PC)
    ed = need(GE.get_graph_editor_by_name(bp, "Assign Ability"), "Assign Ability graph")
    nodes = list(ed.list_all_nodes())
    sw = [n for n in nodes if n.get_class().get_name() == "K2Node_SwitchEnum" and "E_ActiveAbilities" in title(n)]
    sw = need(sw[0] if sw else None, "Switch on E_ActiveAbilities")
    out = pin(sw, enum_val, direction=OUT)
    linked = list(out.list_connected_pins())
    if linked and FUNC in title(linked[0].get_owning_node()):
        log("Assign Ability zaten bagli")
        return
    if linked and not DRY:
        raise StepError("Switch pini %s baska bir seye bagli: %s" % (enum_val, title(linked[0].get_owning_node())))
    hammer = [n for n in nodes if "LevelUpHammer" in title(n)]
    target_src = list(pin(need(hammer[0] if hammer else None, "LevelUpHammer node"), "self", "Target", direction=IN).list_connected_pins())[0]
    call = at(need(ed.add_call_function_node(ABIL_C + ":" + FUNC), FUNC + " call"), 900, 700)
    link(out, X(call), "Switch -> " + FUNC)
    link(target_src, pin(call, "self", "Target", direction=IN), "AbilityComponent -> " + FUNC)
    compile_ok(bp, "BP_Gameplay_PlayerController")
    TO_SAVE.append(bp)
    log("Assign Ability: Switch.%s -> %s" % (enum_val, FUNC))


def step_icon(enum_val):
    bp = need(unreal.load_asset(BFL), BFL)
    ed = need(GE.get_graph_editor_by_name(bp, "FindActiveIcon"), "FindActiveIcon graph")
    sel = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "K2Node_Select"]
    p = pin(need(sel[0] if sel else None, "Select"), enum_val, direction=IN)
    if str(p.get_pin_value()) not in ("", "None") and not DRY:
        log("Ikon zaten ayarli:", p.get_pin_value())
        return
    p.set_pin_value(ICON)
    compile_ok(bp, "BFL_Helper")
    TO_SAVE.append(bp)
    log("FindActiveIcon:", enum_val, "->", ICON)


def step_compile_dependents():
    for path in (B + "/Character/BP_Base_Character", BABY, B + "/Character/BP_Lobby_Character",
                 "/Game/SurvivorsTemplate/Widgets/WB_LevelUpMaster", "/Game/SurvivorsTemplate/Widgets/WB_LevelUpCard",
                 "/Game/SurvivorsTemplate/Widgets/WB_PlayerHud", "/Game/SurvivorsTemplate/Widgets/WB_ChestMaster",
                 B + "/System/Lobby/BP_Lobby_PlayerController"):
        bp = unreal.load_asset(path)
        if bp is not None:
            compile_ok(bp, path.split("/")[-1])


def main():
    enum_val = find_enum_value()
    step_remove_from_babydoll()
    step_rebuild_snip()
    step_datatable()
    step_levelup_function(enum_val)
    step_assign_ability(enum_val)
    step_icon(enum_val)
    step_compile_dependents()
    if DRY:
        log("DRY: kaydedilmedi. Degisecek asset'ler:", [a.get_path_name() for a in TO_SAVE])
        return
    for a in TO_SAVE:
        if not EAL.save_loaded_asset(a, only_if_is_dirty=False):
            raise StepError("Kaydedilemedi: " + a.get_path_name())
        log("Kaydedildi:", a.get_path_name())


try:
    main()
    log("SONUC: OK")
except Exception as e:  # noqa
    import traceback
    log("SONUC: HATA", e)
    log(traceback.format_exc())
finally:
    out = os.environ.get("SNIP_LOG")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
