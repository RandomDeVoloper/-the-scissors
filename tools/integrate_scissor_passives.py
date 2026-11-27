"""
Makas pasiflerini (Scissor Attack Speed / Scissor Area / Scissor Size) level-up sistemine baglar.

SORUN: E_PassiveAbilities'e NewEnumerator4/5/6 ve DT_PassiveAbilities'e satirlari eklenmisti, ama
BP_Gameplay_PlayerController > Assign Ability'deki "Switch on E_PassiveAbilities" bu uc degerde
hicbir yere bagli degildi. Kart secilince PassiveAbilitiesMap'e seviye yazilmiyordu, bu yuzden
kart her seferinde Level 1 = "New!" gosteriyordu ve stat da degismiyordu.

Calistirma: editor KAPALIYKEN headless
    UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=".../integrate_scissor_passives.py"
Ortam degiskenleri:
    PASSIVE_DRY=1     hicbir sey kaydetme (kur + derle + raporla; editor acikken guvenli)
    PASSIVE_LOG=<dosya>

Yaptiklari (zaten yapilmis adimlar atlanir):
  1. BP_Abilities_Component:
       - ScissorMeshBaseScale (Vector) degiskeni
       - ApplyScissorPassives(): seviyelerden carpanlari hesaplar (her seviye +%10)
            ScissorMesh olcegi   = baz olcek * (1 + 0.1 * SizeLv)
            ScissorSnip.SetSnipLevel(Level) ile baz statlar tablodan yeniden okunur, sonra
            Cooldown /= (1 + 0.1 * AttackSpeedLv), HalfAngleDegrees *= (1 + 0.1 * AreaLv),
            Range *= (1 + 0.1 * SizeLv), timer yeni Cooldown ile yeniden kurulur
       - LevelUpScissorAttackSpeed / LevelUpScissorArea / LevelUpScissorSize:
            PassiveAbilitiesMap[pasif] += 1  ->  ApplyScissorPassives
       - LevelUpScissorSnip sonuna ApplyScissorPassives (makas seviye atlayinca pasifler kaybolmasin)
  2. BP_Gameplay_PlayerController > Assign Ability: Switch on E_PassiveAbilities 4/5/6 -> yeni fonksiyonlar
  3. BFL_Helper > FindPassiveIcon: 4/5/6 icin gecici ikonlar
  4. Derler; hata varsa hicbir sey kaydetmez. Kaydetmeden once Saved/ScissorPassiveBackup'a yedek alir.
"""
import datetime
import os
import shutil

import unreal

DRY = os.environ.get("PASSIVE_DRY") == "1"
B = "/Game/SurvivorsTemplate/Blueprints"
ABIL = B + "/Components/BP_Abilities_Component"
ABIL_C = ABIL + ".BP_Abilities_Component_C"
PC = B + "/System/BP_Gameplay_PlayerController"
BFL = B + "/BFL_Helper"
BABY_C = B + "/Character/BP_BabyDoll.BP_BabyDoll_C"
SNIP_C = B + "/Abilities/BP_Ability_ScissorSnip.BP_Ability_ScissorSnip_C"
TEX = "/Game/SurvivorsTemplate/Textures/"
# enum degeri, DT satiri / fonksiyon adi, gecici ikon
PASSIVES = [
    ("NewEnumerator4", "ScissorAttackSpeed", TEX + "speedometer.speedometer"),
    ("NewEnumerator5", "ScissorArea", TEX + "upgrade.upgrade"),
    ("NewEnumerator6", "ScissorSize", TEX + "upgrade.upgrade"),
]
SPEED, AREA, SIZE = (p[0] for p in PASSIVES)
APPLY = "ApplyScissorPassives"
BASE_VAR = "ScissorMeshBaseScale"
PROJECT = unreal.SystemLibrary.get_project_directory()

BEL = unreal.BlueprintEditorLibrary
GE = unreal.BlueprintGraphEditor
EAL = unreal.EditorAssetLibrary
IN = unreal.EdGraphPinDirection.EGPD_INPUT
OUT = unreal.EdGraphPinDirection.EGPD_OUTPUT
KML = "/Script/Engine.KismetMathLibrary."
KSL = "/Script/Engine.KismetSystemLibrary."
LOG = []
TO_SAVE = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log("[ScissorPassives] " + s)


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
    raise StepError("Pin yok %s on %s; mevcut %s" % (names, title(n), [str(p.get_pin_name()) for p in pins(n)]))


def link(a, b, label):
    if not a.try_create_connection(b):
        raise StepError("Baglanamadi: " + label)


def X(n):
    return pin(n, "execute", "exec", direction=IN)


def T(n):
    return pin(n, "then", direction=OUT)


def R(n):
    return pin(n, "ReturnValue", direction=OUT)


def as_pin(n):
    for p in pins(n):
        if p.get_pin_direction() == OUT and str(p.get_pin_name()).startswith("As"):
            return p
    raise StepError("Cast cikis pini yok: " + title(n))


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


class G:
    """Kucuk dugum yardimcisi: yerlestir + olustur."""

    def __init__(self, ed):
        self.ed = ed

    def at(self, n, x, y):
        n.set_node_pos(unreal.IntPoint(x, y))
        return n

    def fn(self, path, x, y):
        return self.at(need(self.ed.add_call_function_node(path), path), x, y)

    def get(self, var, x, y, cls=""):
        return self.at(need(self.ed.add_get_member_variable_node(var, cls), "Get " + var), x, y)

    def set(self, var, x, y, cls=""):
        return self.at(need(self.ed.add_set_member_variable_node(var, cls), "Set " + var), x, y)

    def cast(self, base, cls, x, y):
        name = "Utilities|Casting|CastTo" + base.__name__
        n = self.at(need(self.ed.create_node_from_name(name, unreal.Vector2D(x, y), []), name), x, y)
        if not self.ed.retarget_node_class(n, base, cls):
            raise StepError("Cast hedefi degistirilemedi: " + cls.get_name())
        return n

    def level_of(self, enum_val, x, y):
        """PassiveAbilitiesMap.Find(enum).Value (yoksa 0) -> int pin."""
        m = self.get("PassiveAbilitiesMap", x, y)
        f = self.fn("/Script/Engine.BlueprintMapLibrary.Map_Find", x + 220, y)
        link(pin(m, "PassiveAbilitiesMap", direction=OUT), pin(f, "TargetMap", direction=IN), "map -> Find")
        pin(f, "Key", direction=IN).set_pin_value(enum_val)
        return pin(f, "Value", direction=OUT)

    def mult_of(self, enum_val, x, y):
        """1 + 0.1 * seviye -> float pin."""
        lv = self.level_of(enum_val, x, y)
        conv = self.fn(KML + "Conv_IntToDouble", x + 450, y)
        link(lv, pin(conv, "InInt", direction=IN), "lv -> float")
        mul = self.fn(KML + "Multiply_DoubleDouble", x + 650, y)
        link(R(conv), pin(mul, "A", direction=IN), "float -> *")
        pin(mul, "B", direction=IN).set_pin_value("0.1")
        add = self.fn(KML + "Add_DoubleDouble", x + 850, y)
        link(R(mul), pin(add, "A", direction=IN), "* -> +")
        pin(add, "B", direction=IN).set_pin_value("1.0")
        return R(add)


# --------------------------------------------------------------------------
def check_enum():
    path = PROJECT + "Content/SurvivorsTemplate/Blueprints/Enums/E_PassiveAbilities.uasset"
    data = open(path, "rb").read()
    for disp in (b"Scissor Attack Speed", b"Scissor Area", b"Scissor Size"):
        if disp not in data:
            raise StepError("E_PassiveAbilities'te '%s' yok" % disp.decode())
    dt = need(unreal.load_asset(B + "/DataTables/DT_PassiveAbilities"), "DT_PassiveAbilities")
    rows = [str(r) for r in unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)]
    missing = [p[1] for p in PASSIVES if p[1] not in rows]
    if missing:
        raise StepError("DT_PassiveAbilities satiri eksik: %s" % missing)
    log("Enum ve DT satirlari tamam:", rows)


def build_apply(bp):
    if BEL.find_graph(bp, APPLY) is not None:
        log(APPLY, "zaten var")
        return
    if not BEL.add_member_variable(bp, BASE_VAR, BEL.get_struct_type(unreal.Vector.static_struct())):
        log(BASE_VAR, "eklenemedi (zaten var olabilir)")
    BEL.set_blueprint_variable_category(bp, BASE_VAR, "Abilities|Passive")
    snip_cls = need(unreal.load_object(None, SNIP_C), "ScissorSnip class")
    baby_cls = need(unreal.load_object(None, BABY_C), "BP_BabyDoll class")
    ed = need(GE.create_and_edit_function_graph(bp, APPLY), APPLY)
    g = G(ed)
    entry = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "K2Node_FunctionEntry"][0]
    g.at(entry, 0, 0)

    # ---- 1) Makas mesh olcegi (BP_BabyDoll.ScissorMesh) ----
    owner = g.fn("/Script/Engine.ActorComponent.GetOwner", 0, 200)
    cbaby = g.cast(unreal.Character, baby_cls, 250, 0)
    link(ed.find_graph_entry_pin(), X(cbaby), "Entry -> Cast BabyDoll")
    link(R(owner), pin(cbaby, "Object", direction=IN), "Owner -> Cast BabyDoll")
    as_baby = as_pin(cbaby)

    def mesh(x, y):
        m = g.get("ScissorMesh", x, y, BABY_C)
        link(as_baby, pin(m, "self", "Target", direction=IN), "BabyDoll -> ScissorMesh")
        return pin(m, "ScissorMesh", direction=OUT)

    base_get = g.get(BASE_VAR, 600, 250)
    eq = g.fn(KML + "EqualEqual_VectorVector", 850, 250)
    link(pin(base_get, BASE_VAR, direction=OUT), pin(eq, "A", direction=IN), "base -> ==")
    br_base = g.at(need(ed.add_branch_node(), "Branch base"), 650, 0)
    link(T(cbaby), X(br_base), "Cast -> Branch base")
    link(R(eq), pin(br_base, "Condition", direction=IN), "== -> Branch")
    # ilk seferde baz olcegi yakala
    try:
        scale_get = g.get("RelativeScale3D", 900, -250, "/Script/Engine.SceneComponent")
        link(mesh(700, -250), pin(scale_get, "self", "Target", direction=IN), "mesh -> RelativeScale3D")
        scale_out = pin(scale_get, "RelativeScale3D", direction=OUT)
    except Exception as e:  # noqa
        log("RelativeScale3D getter olmadi, K2_GetComponentScale kullaniliyor:", e)
        sg = g.fn("/Script/Engine.SceneComponent.K2_GetComponentScale", 900, -250)
        link(mesh(700, -250), pin(sg, "self", "Target", direction=IN), "mesh -> scale")
        scale_out = R(sg)
    base_set = g.set(BASE_VAR, 950, -100)
    link(T(br_base), X(base_set), "Branch true -> Set base")
    link(scale_out, pin(base_set, BASE_VAR, direction=IN), "scale -> base")
    set_scale = g.fn("/Script/Engine.SceneComponent.SetRelativeScale3D", 1300, 0)
    link(T(base_set), X(set_scale), "Set base -> SetScale")
    link(pin(br_base, "else", direction=OUT), X(set_scale), "Branch false -> SetScale")
    link(mesh(1100, 200), pin(set_scale, "self", "Target", direction=IN), "mesh -> SetScale")
    vmul = g.fn(KML + "Multiply_VectorFloat", 1100, 350)
    link(pin(g.get(BASE_VAR, 900, 350), BASE_VAR, direction=OUT), pin(vmul, "A", direction=IN), "base -> v*f")
    link(g.mult_of(SIZE, 0, 500), pin(vmul, "B", direction=IN), "size mult -> v*f")
    link(R(vmul), pin(set_scale, "NewScale3D", direction=IN), "v*f -> NewScale3D")

    # ---- 2) ScissorSnip statlari ----
    X0 = 1700
    owner2 = g.fn("/Script/Engine.ActorComponent.GetOwner", X0, 250)
    gcbc = g.fn("/Script/Engine.Actor.GetComponentByClass", X0 + 200, 250)
    link(R(owner2), pin(gcbc, "self", direction=IN), "Owner -> GCBC")
    pin(gcbc, "ComponentClass", direction=IN).set_pin_value(snip_cls.get_path_name())
    csnip = g.cast(unreal.ActorComponent, snip_cls, X0 + 450, 0)
    link(T(set_scale), X(csnip), "SetScale -> Cast Snip")
    link(pin(cbaby, "CastFailed", "Failed", direction=OUT), X(csnip), "Cast BabyDoll failed -> Cast Snip")
    link(R(gcbc), pin(csnip, "Object", direction=IN), "GCBC -> Cast Snip")
    as_snip = as_pin(csnip)

    def sget(var, x, y):
        n = g.get(var, x, y, SNIP_C)
        link(as_snip, pin(n, "self", "Target", direction=IN), "snip -> get " + var)
        return pin(n, var, direction=OUT)

    def sset(var, x, y):
        n = g.set(var, x, y, SNIP_C)
        link(as_snip, pin(n, "self", "Target", direction=IN), "snip -> set " + var)
        return n

    lvl = g.fn(SNIP_C + ":SetSnipLevel", X0 + 750, 0)
    link(T(csnip), X(lvl), "Cast -> SetSnipLevel")
    link(as_snip, pin(lvl, "self", "Target", direction=IN), "snip -> SetSnipLevel")
    link(sget("Level", X0 + 600, 200), pin(lvl, "NewLevel", direction=IN), "Level -> NewLevel")
    prev = lvl
    x = X0 + 1050
    for var, op, which in (("Cooldown", "Divide_DoubleDouble", SPEED),
                           ("HalfAngleDegrees", "Multiply_DoubleDouble", AREA),
                           ("Range", "Multiply_DoubleDouble", SIZE)):
        s = sset(var, x + 300, 0)
        link(T(prev), X(s), "-> Set " + var)
        o = g.fn(KML + op, x + 100, 250)
        link(sget(var, x - 100, 250), pin(o, "A", direction=IN), var + " -> op")
        link(g.mult_of(which, x - 900, 500 + (x - X0) // 2), pin(o, "B", direction=IN), "mult -> " + var)
        link(R(o), pin(s, var, direction=IN), "op -> Set " + var)
        prev = s
        x += 700
    clr = g.fn(KSL + "K2_ClearAndInvalidateTimerHandle", x, 0)
    link(T(prev), X(clr), "-> Clear timer")
    link(sget("SnipTimer", x - 200, 200), pin(clr, "Handle", direction=IN), "SnipTimer -> Clear")
    br_auto = g.at(need(ed.add_branch_node(), "Branch auto"), x + 300, 0)
    link(T(clr), X(br_auto), "Clear -> Branch auto")
    link(sget("bAutoFire", x + 100, 200), pin(br_auto, "Condition", direction=IN), "bAutoFire -> Branch")
    timer = g.fn(KSL + "K2_SetTimer", x + 550, 0)
    link(T(br_auto), X(timer), "auto -> SetTimer")
    link(as_snip, pin(timer, "Object", direction=IN), "snip -> SetTimer.Object")
    pin(timer, "FunctionName", direction=IN).set_pin_value("Snip")
    pin(timer, "bLooping", direction=IN).set_pin_value("true")
    link(sget("Cooldown", x + 350, 250), pin(timer, "Time", direction=IN), "Cooldown -> Time")
    seth = sset("SnipTimer", x + 900, 0)
    link(T(timer), X(seth), "SetTimer -> Set SnipTimer")
    link(R(timer), pin(seth, "SnipTimer", direction=IN), "handle -> SnipTimer")
    log(APPLY, "kuruldu")


def build_levelup(bp, enum_val, row):
    fname = "LevelUp" + row
    if BEL.find_graph(bp, fname) is not None:
        log(fname, "zaten var")
        return
    ed = need(GE.create_and_edit_function_graph(bp, fname), fname)
    g = G(ed)
    ed.add_local_variable("L_Level", BEL.get_basic_type_by_name("int"), "0")
    entry = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "K2Node_FunctionEntry"][0]
    g.at(entry, 0, 0)
    plus = g.fn(KML + "Add_IntInt", 500, 250)
    link(g.level_of(enum_val, 0, 250), pin(plus, "A", direction=IN), "lv -> +1")
    pin(plus, "B", direction=IN).set_pin_value("1")
    setl = g.at(need(ed.add_set_local_variable_node("L_Level"), "Set L_Level"), 300, 0)
    link(ed.find_graph_entry_pin(), X(setl), "Entry -> Set L_Level")
    link(R(plus), pin(setl, "L_Level", direction=IN), "+1 -> L_Level")
    add = g.fn("/Script/Engine.BlueprintMapLibrary.Map_Add", 650, 0)
    link(T(setl), X(add), "Set -> Map_Add")
    link(pin(g.get("PassiveAbilitiesMap", 450, 150), "PassiveAbilitiesMap", direction=OUT),
         pin(add, "TargetMap", direction=IN), "map -> Add")
    pin(add, "Key", direction=IN).set_pin_value(enum_val)
    getl = g.at(need(ed.add_get_local_variable_node("L_Level"), "Get L_Level"), 450, 300)
    link(pin(getl, "L_Level", direction=OUT), pin(add, "Value", direction=IN), "L_Level -> Value")
    call = g.fn(ABIL_C + ":" + APPLY, 1000, 0)
    link(T(add), X(call), "Map_Add -> " + APPLY)
    log(fname, "kuruldu (", enum_val, ")")


def hook_snip_levelup(bp):
    ed = need(GE.get_graph_editor_by_name(bp, "LevelUpScissorSnip"), "LevelUpScissorSnip graph")
    nodes = list(ed.list_all_nodes())
    if any(APPLY in title(n) for n in nodes):
        log("LevelUpScissorSnip zaten", APPLY, "cagiriyor")
        return
    ends = [n for n in nodes if "SetSnipLevel" in title(n)]
    if len(ends) != 2:
        raise StepError("LevelUpScissorSnip'te 2 SetSnipLevel bekleniyordu: %d" % len(ends))
    call = G(ed).fn(ABIL_C + ":" + APPLY, 2400, 0)
    for n in ends:
        if list(T(n).list_connected_pins()):
            raise StepError("SetSnipLevel.then zaten bagli")
        link(T(n), X(call), "SetSnipLevel -> " + APPLY)
    log("LevelUpScissorSnip ->", APPLY, "eklendi")


def step_component():
    bp = need(unreal.load_asset(ABIL), ABIL)
    build_apply(bp)
    BEL.compile_blueprint(bp)  # yeni fonksiyon, cagri dugumlerinden once sinifta olsun
    for enum_val, row, _ in PASSIVES:
        build_levelup(bp, enum_val, row)
    hook_snip_levelup(bp)
    compile_ok(bp, "BP_Abilities_Component")
    TO_SAVE.append(bp)


def step_assign_ability():
    bp = need(unreal.load_asset(PC), PC)
    ed = need(GE.get_graph_editor_by_name(bp, "Assign Ability"), "Assign Ability graph")
    nodes = list(ed.list_all_nodes())
    sw = [n for n in nodes if n.get_class().get_name() == "K2Node_SwitchEnum" and "E_PassiveAbilities" in title(n)]
    sw = need(sw[0] if sw else None, "Switch on E_PassiveAbilities")
    ref = [n for n in nodes if "LevelUpSpeedBonus" in title(n)]
    target_src = list(pin(need(ref[0] if ref else None, "LevelUpSpeedBonus node"), "self", "Target", direction=IN).list_connected_pins())[0]
    changed = False
    for i, (enum_val, row, _) in enumerate(PASSIVES):
        out = pin(sw, enum_val, direction=OUT)
        linked = list(out.list_connected_pins())
        if linked:
            log("Switch.%s zaten bagli: %s" % (enum_val, title(linked[0].get_owning_node())))
            continue
        call = G(ed).fn(ABIL_C + ":LevelUp" + row, 900, 1000 + i * 150)
        link(out, X(call), "Switch -> LevelUp" + row)
        link(target_src, pin(call, "self", "Target", direction=IN), "AbilityComponent -> LevelUp" + row)
        log("Assign Ability: Switch.%s -> LevelUp%s" % (enum_val, row))
        changed = True
    compile_ok(bp, "BP_Gameplay_PlayerController")
    if changed:
        TO_SAVE.append(bp)


def step_icons():
    bp = need(unreal.load_asset(BFL), BFL)
    ed = need(GE.get_graph_editor_by_name(bp, "FindPassiveIcon"), "FindPassiveIcon graph")
    sel = [n for n in ed.list_all_nodes() if n.get_class().get_name() == "K2Node_Select"]
    sel = need(sel[0] if sel else None, "Select")
    changed = False
    for enum_val, row, icon in PASSIVES:
        p = pin(sel, enum_val, direction=IN)
        if str(p.get_pin_value()) not in ("", "None"):
            log("Ikon zaten ayarli:", enum_val, p.get_pin_value())
            continue
        p.set_pin_value(icon)
        log("FindPassiveIcon:", enum_val, "->", icon)
        changed = True
    compile_ok(bp, "BFL_Helper")
    if changed:
        TO_SAVE.append(bp)


def step_compile_dependents():
    for path in (B + "/Character/BP_Base_Character", B + "/Character/BP_BabyDoll",
                 B + "/Abilities/BP_Ability_ScissorSnip",
                 "/Game/SurvivorsTemplate/Widgets/WB_LevelUpMaster", "/Game/SurvivorsTemplate/Widgets/WB_LevelUpCard",
                 "/Game/SurvivorsTemplate/Widgets/WB_PlayerHud", "/Game/SurvivorsTemplate/Widgets/WB_ChestMaster"):
        bp = unreal.load_asset(path)
        if bp is not None:
            compile_ok(bp, path.split("/")[-1])


def backup():
    dst = PROJECT + "Saved/ScissorPassiveBackup/" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(dst)
    for a in TO_SAVE:
        rel = a.get_path_name().split(".")[0][len("/Game/"):]
        shutil.copy2(PROJECT + "Content/" + rel + ".uasset", dst)
    log("Yedek:", dst)


def main():
    check_enum()
    step_component()
    step_assign_ability()
    step_icons()
    step_compile_dependents()
    if DRY:
        log("DRY: kaydedilmedi. Degisecek asset'ler:", [a.get_path_name() for a in TO_SAVE])
        return
    backup()
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
    out = os.environ.get("PASSIVE_LOG")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
