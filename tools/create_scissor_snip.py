"""
Makas kirpma (Scissor Snip) yetenegi: konik alan hasari.

Calistirma (editor icinden):  Output Log > Cmd > Python:
    py "C:/Users/Niyazi/-the-scissors/tools/create_scissor_snip.py"
veya headless:
    UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=".../create_scissor_snip.py"

Olusan asset'ler (mevcut hicbir asset degistirilmez; hedef varsa script durur):
  /Game/SurvivorsTemplate/Blueprints/DataTables/CT_ScissorSnip      (Curve Table, seviye -> stat)
  /Game/SurvivorsTemplate/Blueprints/Abilities/BP_Ability_ScissorSnip (ActorComponent)

Neden Curve Table: UE Python API'si Blueprint struct'ina alan ekleyemiyor, bu yuzden
DataTable + ST_ satiri headless olusturulamiyor. Curve Table ayni editorde tablo olarak
duzenlenir ve seviye basina deger tutar (satir = stat, sutun = seviye):
    Range, HalfAngleDegrees, Damage, Cooldown

BP_Ability_ScissorSnip
  BeginPlay: CT_ScissorSnip'ten Level sutununu oku -> Range/HalfAngleDegrees/Damage/Cooldown
             bAutoFire ise Set Timer by Function Name("Snip", Cooldown, loop)
             (Survivors sablonundaki Hammer/FrostBolt ile ayni otomatik atesleme modeli)
  Snip:      Owner BP_Base_Character ve olu degilse
             -> BP_Abilities_Component.AbilityDamageMultiplier'i al (pasif hasar bonusu)
             -> Sphere Overlap Actors(Range, ObjectTypeQuery7 = dusmanlar, Hammer ile ayni)
             -> yon = hareket ediyorsa hiz yonu, degilse aktorun baktigi yon
             -> her aktor: Dot(Normal2D(hedef - merkez), yon) >= Cos(HalfAngleDegrees)
                -> ApplyDamage(Damage * carpan, PlayerController 0, Owner)  (BFL_Helper.DamageEnemiesOnce ile ayni)
             -> bDebugDraw: koni + vurulan dusmanlara kirmizi kure
"""
import os
import unreal

DRY_RUN = os.environ.get("SNIP_DRY") == "1"
ROOT = "/Game/__ClaudeTmp" if DRY_RUN else "/Game/SurvivorsTemplate/Blueprints"
BP_PKG = ROOT + ("" if DRY_RUN else "/Abilities")
CT_PKG = ROOT + ("" if DRY_RUN else "/DataTables")
BP_NAME = "BP_Ability_ScissorSnip"
CT_NAME = "CT_ScissorSnip"
CHAR_CLASS = "/Game/SurvivorsTemplate/Blueprints/Character/BP_Base_Character.BP_Base_Character_C"
ABIL_CLASS = "/Game/SurvivorsTemplate/Blueprints/Components/BP_Abilities_Component.BP_Abilities_Component_C"
ENEMY_OBJECT_TYPE = "ObjectTypeQuery7"  # BP_Abilities_Component > Hammer ile ayni kanal

# satir = stat, sutun = yetenek seviyesi
CT_CSV = """---,1,2,3,4,5
Range,350,380,410,440,480
HalfAngleDegrees,35,35,40,40,45
Damage,15,20,25,30,40
Cooldown,1.5,1.4,1.3,1.2,1.0
"""

BEL = unreal.BlueprintEditorLibrary
GE = unreal.BlueprintGraphEditor
V = unreal.Vector2D
IN = unreal.EdGraphPinDirection.EGPD_INPUT
OUT = unreal.EdGraphPinDirection.EGPD_OUTPUT
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    unreal.log("[ScissorSnip] " + s)


class StepError(Exception):
    pass


def need(obj, what):
    if obj is None:
        raise StepError("Olusturulamadi: " + what)
    return obj


def pins(node):
    return list(BEL.list_all_pins(node))


def pin(node, *names, direction=None):
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


def link(a, b, label):
    if not a.try_create_connection(b):
        raise StepError("Baglanti kurulamadi: " + label)


def X(n):  # exec in / out
    return pin(n, "execute", "exec", direction=IN)


def T(n):
    return pin(n, "then", direction=OUT)


def R(n):
    return pin(n, "ReturnValue", direction=OUT)


class G:
    """Kucuk yardimci: dugum olustur + konumla."""

    def __init__(self, ed):
        self.ed = ed

    def at(self, n, x, y):
        n.set_node_pos(unreal.IntPoint(x, y))
        return n

    def fn(self, path, x, y):
        return self.at(need(self.ed.add_call_function_node(path), path), x, y)

    def get(self, var, x, y, cls=""):
        return self.at(need(self.ed.add_get_member_variable_node(var, cls), "Get " + var), x, y)

    def set(self, var, x, y):
        return self.at(need(self.ed.add_set_member_variable_node(var), "Set " + var), x, y)

    def branch(self, x, y):
        return self.at(need(self.ed.add_branch_node(), "Branch"), x, y)

    def named(self, name, x, y):
        return self.at(need(self.ed.create_node_from_name(name, V(x, y), []), name), x, y)


KML = "/Script/Engine.KismetMathLibrary."
KSL = "/Script/Engine.KismetSystemLibrary."
GPS = "/Script/Engine.GameplayStatics."


def make_curve_table():
    path = CT_PKG + "/" + CT_NAME
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        raise StepError(path + " zaten var; hicbir sey degistirilmedi.")
    ct = need(unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        CT_NAME, CT_PKG, unreal.CurveTable, unreal.CurveTableFactory()), "CurveTable")
    ok = unreal.DataTableFunctionLibrary.fill_curve_table_from_csv_string(ct, CT_CSV) \
        if hasattr(unreal.DataTableFunctionLibrary, "fill_curve_table_from_csv_string") else None
    if not ok:
        # yedek yol: tek tek egri ekle
        lines = [l.split(",") for l in CT_CSV.strip().splitlines()]
        levels = [float(x) for x in lines[0][1:]]
        for row in lines[1:]:
            unreal.DataTableFunctionLibrary.add_simple_curve_to_table(ct, row[0])
            for lv, val in zip(levels, row[1:]):
                unreal.DataTableFunctionLibrary.add_curve_table_key(ct, row[0], lv, float(val))
    for rn in ("Range", "HalfAngleDegrees", "Damage", "Cooldown"):
        r = unreal.DataTableFunctionLibrary.evaluate_curve_table_row(ct, rn, 1.0, "check")
        log("CT", rn, "@1 =", r)
    return ct, path


def curve_table_pin_type():
    # get_object_reference_type(CurveTable) 'int' donduruyor; pin tipini elle kur
    t = unreal.EdGraphPinType()
    t.import_text('(PinCategory="object",PinSubCategoryObject="/Script/CoreUObject.Class\'/Script/Engine.CurveTable\'")')
    return t


def set_defaults(bp, ct):
    cdo = unreal.get_default_object(bp.generated_class())
    for k, v in (("StatsTable", ct), ("Level", 1), ("Range", 350.0), ("HalfAngleDegrees", 35.0),
                 ("Damage", 15.0), ("Cooldown", 1.5), ("DamageMultiplier", 1.0),
                 ("bAutoFire", True), ("bDebugDraw", True)):
        cdo.set_editor_property(k, v)


def main():
    bp_path = BP_PKG + "/" + BP_NAME
    if os.environ.get("SNIP_OVERWRITE") == "1":  # bu script'in kendi olusturdugu asset'leri yeniden kur
        for p in (bp_path, CT_PKG + "/" + CT_NAME):
            if unreal.EditorAssetLibrary.does_asset_exist(p):
                log("Siliniyor (yeniden olusturulacak):", p, unreal.EditorAssetLibrary.delete_asset(p))
    if unreal.EditorAssetLibrary.does_asset_exist(bp_path):
        raise StepError(bp_path + " zaten var; hicbir sey degistirilmedi.")
    ct, ct_path = make_curve_table()
    log("CurveTable olusturuldu:", ct_path)

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.ActorComponent)
    bp = need(unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        BP_NAME, BP_PKG, unreal.Blueprint, factory), "Blueprint")
    log("Blueprint olusturuldu:", bp.get_path_name())

    eg = need(GE.get_graph_editor_by_name(bp, "EventGraph"), "EventGraph editor")
    real = BEL.get_basic_type_by_name("real")
    variables = (
        ("StatsTable", curve_table_pin_type(), ct.get_path_name()),
        ("Level", BEL.get_basic_type_by_name("int"), "1"),
        ("Range", real, "350.0"),
        ("HalfAngleDegrees", real, "35.0"),
        ("Damage", real, "15.0"),
        ("Cooldown", real, "1.5"),
        ("DamageMultiplier", real, "1.0"),
        ("bAutoFire", BEL.get_basic_type_by_name("bool"), "true"),
        ("bDebugDraw", BEL.get_basic_type_by_name("bool"), "true"),
        ("SnipTimer", BEL.get_struct_type(unreal.TimerHandle.static_struct()), ""),
    )
    for vname, vtype, val in variables:
        if not BEL.add_member_variable(bp, vname, vtype):
            raise StepError("Degisken eklenemedi: " + vname)
        BEL.set_blueprint_variable_category(bp, vname, "ScissorSnip")
        log("Var", vname, BEL.get_member_variable_type(bp, vname).to_tuple() if hasattr(BEL.get_member_variable_type(bp, vname), "to_tuple") else "")
    for vname in ("StatsTable", "Level", "bAutoFire", "bDebugDraw"):
        BEL.set_blueprint_variable_instance_editable(bp, vname, True)
    BEL.compile_blueprint(bp)
    set_defaults(bp, ct)
    log("Degiskenler eklendi")

    g = G(eg)

    # ======= SetSnipLevel(NewLevel): stat oku + timer'i (yeniden) kur =======
    # Level-up kartlari (BP_Abilities_Component.LevelUpScissorSnip) bunu cagirir.
    fed = need(GE.create_and_edit_function_graph(bp, "SetSnipLevel"), "SetSnipLevel graph")
    need(fed.add_graph_input_parameter("NewLevel", BEL.get_basic_type_by_name("int"), "1"), "NewLevel param")
    entry = [n for n in fed.list_all_nodes() if n.get_class().get_name() == "K2Node_FunctionEntry"][0]
    fg = G(fed)
    g.at(entry, 0, 0)
    set_lvl = fg.set("Level", 250, 0)
    link(fed.find_graph_entry_pin(), X(set_lvl), "Entry -> Set Level")
    link(pin(entry, "NewLevel", direction=OUT), pin(set_lvl, "Level", direction=IN), "NewLevel -> Level")
    pending = [T(set_lvl)]  # bir sonraki dugumun exec girisine baglanacak cikislar
    g_main, g = g, fg
    x = 600
    for stat in ("Range", "HalfAngleDegrees", "Damage", "Cooldown"):
        evn = g.fn("/Script/Engine.DataTableFunctionLibrary.EvaluateCurveTableRow", x, 0)
        if stat == "Range":
            log("Eval pinleri:", [(str(p.get_pin_name()), p.get_pin_type_display_string()) for p in pins(evn)])
        for p in pending:
            link(p, X(evn), "-> Eval " + stat)
        tbl = pin(g.get("StatsTable", x - 220, 180), "StatsTable", direction=OUT)
        link(tbl, pin(evn, "CurveTable", direction=IN), "StatsTable(%s) -> Eval %s" % (tbl.get_pin_type_display_string(), stat))
        pin(evn, "RowName", direction=IN).set_pin_value(stat)
        lvl = g.get("Level", x - 220, 260)
        link(pin(lvl, "Level", direction=OUT), pin(evn, "InXY", direction=IN), "Level -> InXY " + stat)
        st = g.set(stat, x + 300, 0)
        link(pin(evn, "RowFound", "Found", direction=OUT), X(st), "RowFound -> Set " + stat)
        link(pin(evn, "OutXY", direction=OUT), pin(st, stat, direction=IN), "OutXY -> " + stat)
        # satir yoksa Set atlanir, BP'deki default deger kalir
        pending = [T(st), pin(evn, "RowNotFound", "NotFound", direction=OUT)]
        x += 650

    clr = g.fn(KSL + "K2_ClearAndInvalidateTimerHandle", x, 0)
    for p in pending:
        link(p, X(clr), "Stats -> Clear Timer")
    link(pin(g.get("SnipTimer", x - 200, 200), "SnipTimer", direction=OUT), pin(clr, "Handle", direction=IN), "SnipTimer -> Clear")
    x += 350
    br_auto = g.branch(x, 0)
    link(T(clr), X(br_auto), "Clear -> Branch AutoFire")
    link(pin(g.get("bAutoFire", x - 200, 160), "bAutoFire", direction=OUT),
         pin(br_auto, "Condition", direction=IN), "bAutoFire -> Branch")
    timer = g.fn(KSL + "K2_SetTimer", x + 250, 0)
    link(T(br_auto), X(timer), "AutoFire -> SetTimer")
    pin(timer, "FunctionName", direction=IN).set_pin_value("Snip")
    pin(timer, "bLooping", direction=IN).set_pin_value("true")
    link(pin(g.get("Cooldown", x, 200), "Cooldown", direction=OUT), pin(timer, "Time", direction=IN), "Cooldown -> Time")
    set_h = g.set("SnipTimer", x + 600, 0)
    link(T(timer), X(set_h), "SetTimer -> Set SnipTimer")
    link(R(timer), pin(set_h, "SnipTimer", direction=IN), "Handle -> SnipTimer")
    g = g_main
    BEL.compile_blueprint(bp)
    log("SetSnipLevel kuruldu")

    # ================= BeginPlay -> SetSnipLevel(Level) =================
    ev = eg.find_event_node("ReceiveBeginPlay")
    if ev is None:
        ev = g.named("AddEvent|EventBeginPlay", 0, 0)
    g.at(ev, 0, 0)
    call = None
    gen = bp.generated_class().get_path_name()
    for fp in (gen + ":SetSnipLevel", gen + ".SetSnipLevel"):
        try:
            call = eg.add_call_function_node(fp)
        except Exception as e:
            log("call path", fp, "->", e)
        if call is not None:
            break
    call = g.at(need(call, "SetSnipLevel call"), 300, 0)
    link(T(ev), X(call), "BeginPlay -> SetSnipLevel")
    link(pin(g.get("Level", 100, 150), "Level", direction=OUT), pin(call, "NewLevel", direction=IN), "Level -> NewLevel")
    log("BeginPlay kuruldu")

    # ================= Snip ===========================================
    Y = 700
    snip = g.at(need(eg.add_custom_event_node("Snip"), "Custom Event Snip"), 0, Y)
    owner = g.fn("/Script/Engine.ActorComponent.GetOwner", 0, Y + 200)

    char_cls = need(unreal.load_object(None, CHAR_CLASS), "BP_Base_Character class")
    cast_c = g.named("Utilities|Casting|CastToCharacter", 250, Y)
    if not eg.retarget_node_class(cast_c, unreal.Character, char_cls):
        raise StepError("Cast BP_Base_Character'a cevrilemedi")
    link(T(snip), X(cast_c), "Snip -> Cast Char")
    link(R(owner), pin(cast_c, "Object", direction=IN), "Owner -> Cast Char")
    as_char = pin(cast_c, "AsBP Base Character", "As", direction=OUT)

    dead = g.get("IsDead", 500, Y + 200, CHAR_CLASS)
    link(as_char, pin(dead, "self", "Target", direction=IN), "Char -> IsDead")
    br_dead = g.branch(550, Y)
    link(T(cast_c), X(br_dead), "Cast -> Branch IsDead")
    link(pin(dead, "IsDead", direction=OUT), pin(br_dead, "Condition", direction=IN), "IsDead -> Branch")

    gcbc = g.fn("/Script/Engine.Actor.GetComponentByClass", 800, Y + 200)  # pure
    link(as_char, pin(gcbc, "self", direction=IN), "Char -> GetComponentByClass")
    abil_cls = need(unreal.load_object(None, ABIL_CLASS), "BP_Abilities_Component class")
    pin(gcbc, "ComponentClass", direction=IN).set_pin_value(abil_cls.get_path_name())

    cast_a = g.named("Utilities|Casting|CastToActorComponent", 1100, Y)
    if not eg.retarget_node_class(cast_a, unreal.ActorComponent, abil_cls):
        raise StepError("Cast BP_Abilities_Component'e cevrilemedi")
    link(pin(br_dead, "else", direction=OUT), X(cast_a), "Alive -> Cast Abil")
    link(R(gcbc), pin(cast_a, "Object", direction=IN), "Comp -> Cast Abil")
    as_abil = pin(cast_a, "AsBP Abilities Component", "As", direction=OUT)
    mult_get = g.get("AbilityDamageMultiplier", 1350, Y + 200, ABIL_CLASS)
    link(as_abil, pin(mult_get, "self", "Target", direction=IN), "Abil -> AbilityDamageMultiplier")
    set_mult = g.set("DamageMultiplier", 1400, Y)
    link(T(cast_a), X(set_mult), "Cast Abil -> Set Mult")
    link(pin(mult_get, "AbilityDamageMultiplier", direction=OUT), pin(set_mult, "DamageMultiplier", direction=IN), "mult -> DamageMultiplier")

    # --- merkez ve yon ---
    loc = g.fn("/Script/Engine.Actor.K2_GetActorLocation", 1500, Y + 400)
    link(as_char, pin(loc, "self", direction=IN), "Char -> Location")
    vel = g.fn("/Script/Engine.Actor.GetVelocity", 1500, Y + 550)
    link(as_char, pin(vel, "self", direction=IN), "Char -> Velocity")
    fwd = g.fn("/Script/Engine.Actor.GetActorForwardVector", 1500, Y + 700)
    link(as_char, pin(fwd, "self", direction=IN), "Char -> Forward")
    vn = g.fn(KML + "Vector_Normal2D", 1750, Y + 550)
    link(R(vel), pin(vn, "A", direction=IN), "Vel -> Normal2D")
    vs = g.fn(KML + "VSizeXY", 1750, Y + 650)
    link(R(vel), pin(vs, "A", direction=IN), "Vel -> VSizeXY")
    moving = g.fn(KML + "Greater_DoubleDouble", 1950, Y + 650)
    link(R(vs), pin(moving, "A", direction=IN), "VSizeXY -> >")
    pin(moving, "B", direction=IN).set_pin_value("10.0")
    fwd2d = g.fn(KML + "Vector_Normal2D", 1750, Y + 750)
    link(R(fwd), pin(fwd2d, "A", direction=IN), "Fwd -> Normal2D")
    sel = g.fn(KML + "SelectVector", 2150, Y + 600)
    link(R(vn), pin(sel, "A", direction=IN), "VelDir -> Select A")
    link(R(fwd2d), pin(sel, "B", direction=IN), "Fwd -> Select B")
    link(R(moving), pin(sel, "bPickA", direction=IN), "moving -> bPickA")
    direction = R(sel)
    origin = R(loc)

    # --- overlap ---
    ov = g.fn(KSL + "SphereOverlapActors", 1700, Y)
    link(T(set_mult), X(ov), "Set Mult -> Overlap")
    link(pin(cast_a, "CastFailed", direction=OUT), X(ov), "Cast Abil Failed -> Overlap")
    link(origin, pin(ov, "SpherePos", direction=IN), "Origin -> SpherePos")
    link(pin(g.get("Range", 1500, Y + 250), "Range", direction=OUT), pin(ov, "SphereRadius", direction=IN), "Range -> Radius")
    mk = g.named("Utilities|Array|MakeArray", 1500, Y + 300)
    link(pin(mk, "Array", direction=OUT), pin(ov, "ObjectTypes", direction=IN), "MakeArray -> ObjectTypes")
    pin(mk, "[0]", "0", direction=IN).set_pin_value(ENEMY_OBJECT_TYPE)

    # --- debug koni ---
    br_dbg = g.branch(2000, Y)
    link(T(ov), X(br_dbg), "Overlap -> Branch Debug")
    link(pin(g.get("bDebugDraw", 1850, Y + 150), "bDebugDraw", direction=OUT), pin(br_dbg, "Condition", direction=IN), "bDebugDraw -> Branch")
    cone = g.fn(KSL + "DrawDebugConeInDegrees", 2300, Y - 250)
    link(T(br_dbg), X(cone), "Debug -> Cone")
    link(origin, pin(cone, "Origin", direction=IN), "Origin -> Cone")
    link(direction, pin(cone, "Direction", direction=IN), "Dir -> Cone")
    link(pin(g.get("Range", 2100, Y - 150), "Range", direction=OUT), pin(cone, "Length", direction=IN), "Range -> Cone Length")
    link(pin(g.get("HalfAngleDegrees", 2100, Y - 100), "HalfAngleDegrees", direction=OUT), pin(cone, "AngleWidth", direction=IN), "Angle -> Cone Width")
    pin(cone, "AngleHeight", direction=IN).set_pin_value("3.0")
    pin(cone, "NumSides", direction=IN).set_pin_value("24")
    pin(cone, "LineColor", direction=IN).set_pin_value("(R=1.000000,G=0.850000,B=0.100000,A=1.000000)")
    pin(cone, "Duration", direction=IN).set_pin_value("0.25")
    pin(cone, "Thickness", direction=IN).set_pin_value("2.0")

    # --- ForEach dusman ---
    loop = None
    for mp in ("/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop",
               "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros.ForEachLoop"):
        try:
            loop = eg.add_macro_node(mp)
        except Exception as e:
            log("add_macro_node", mp, "->", e)
        if loop is not None:
            break
    loop = g.at(need(loop, "ForEachLoop"), 2650, Y)
    link(T(cone), X(loop), "Cone -> ForEach")
    link(pin(br_dbg, "else", direction=OUT), X(loop), "NoDebug -> ForEach")
    link(pin(ov, "OutActors", direction=OUT), pin(loop, "Array", direction=IN), "OutActors -> ForEach")
    elem = pin(loop, "Array Element", "Element", direction=OUT)

    eloc = g.fn("/Script/Engine.Actor.K2_GetActorLocation", 2700, Y + 300)
    link(elem, pin(eloc, "self", direction=IN), "Elem -> Location")
    sub = g.fn(KML + "Subtract_VectorVector", 2950, Y + 300)
    link(R(eloc), pin(sub, "A", direction=IN), "EnemyLoc -> -")
    link(origin, pin(sub, "B", direction=IN), "Origin -> -")
    tn = g.fn(KML + "Vector_Normal2D", 3150, Y + 300)
    link(R(sub), pin(tn, "A", direction=IN), "Delta -> Normal2D")
    dot = g.fn(KML + "Dot_VectorVector", 3350, Y + 300)
    link(R(tn), pin(dot, "A", direction=IN), "ToEnemy -> Dot")
    link(direction, pin(dot, "B", direction=IN), "Dir -> Dot")
    cosn = g.fn(KML + "DegCos", 3350, Y + 450)
    link(pin(g.get("HalfAngleDegrees", 3150, Y + 450), "HalfAngleDegrees", direction=OUT), pin(cosn, "A", direction=IN), "Angle -> DegCos")
    ge_ = g.fn(KML + "GreaterEqual_DoubleDouble", 3550, Y + 350)
    link(R(dot), pin(ge_, "A", direction=IN), "Dot -> >=")
    link(R(cosn), pin(ge_, "B", direction=IN), "Cos -> >=")

    br_in = g.branch(3800, Y)
    link(pin(loop, "LoopBody", "Loop Body", direction=OUT), X(br_in), "LoopBody -> Branch InCone")
    link(R(ge_), pin(br_in, "Condition", direction=IN), ">= -> Branch")

    dmg = g.fn(GPS + "ApplyDamage", 4050, Y)
    link(T(br_in), X(dmg), "InCone -> ApplyDamage")
    link(elem, pin(dmg, "DamagedActor", direction=IN), "Elem -> DamagedActor")
    mul = g.fn(KML + "Multiply_DoubleDouble", 3850, Y + 250)
    link(pin(g.get("Damage", 3650, Y + 200), "Damage", direction=OUT), pin(mul, "A", direction=IN), "Damage -> *")
    link(pin(g.get("DamageMultiplier", 3650, Y + 260), "DamageMultiplier", direction=OUT), pin(mul, "B", direction=IN), "Mult -> *")
    link(R(mul), pin(dmg, "BaseDamage", direction=IN), "* -> BaseDamage")
    pc = g.fn(GPS + "GetPlayerController", 3850, Y + 400)
    link(R(pc), pin(dmg, "EventInstigator", direction=IN), "PC -> Instigator")
    link(as_char, pin(dmg, "DamageCauser", direction=IN), "Char -> Causer")

    br_dbg2 = g.branch(4350, Y)
    link(T(dmg), X(br_dbg2), "ApplyDamage -> Branch Debug")
    link(pin(g.get("bDebugDraw", 4200, Y + 150), "bDebugDraw", direction=OUT), pin(br_dbg2, "Condition", direction=IN), "bDebugDraw -> Branch2")
    sph = g.fn(KSL + "DrawDebugSphere", 4600, Y)
    link(T(br_dbg2), X(sph), "Debug -> Sphere")
    link(R(eloc), pin(sph, "Center", direction=IN), "EnemyLoc -> Sphere")
    pin(sph, "Radius", direction=IN).set_pin_value("40.0")
    pin(sph, "Segments", direction=IN).set_pin_value("8")
    pin(sph, "LineColor", direction=IN).set_pin_value("(R=1.000000,G=0.000000,B=0.000000,A=1.000000)")
    pin(sph, "Duration", direction=IN).set_pin_value("0.25")
    log("Snip kuruldu")

    # --- derle & kaydet ---
    BEL.compile_blueprint(bp)
    status = bp.get_editor_property("status")
    log("Derleme durumu:", status)
    for n in eg.list_nodes_with_errors():
        log("  HATA:", BEL.get_node_title(n), n.get_editor_property("error_msg") if hasattr(n, "get_editor_property") else "")
    for n in eg.list_nodes_with_warnings():
        log("  UYARI:", BEL.get_node_title(n))
    if status not in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS):
        raise StepError("Derleme basarisiz: %s" % status)
    cdo = unreal.get_default_object(bp.generated_class())
    for p in ("StatsTable", "Level", "bAutoFire", "bDebugDraw", "Range", "DamageMultiplier"):
        try:
            log("CDO", p, "=", cdo.get_editor_property(p))
        except Exception as e:
            log("CDO", p, "okunamadi:", e)
    for a in (ct, bp):
        if not unreal.EditorAssetLibrary.save_loaded_asset(a, only_if_is_dirty=False):
            raise StepError("Kaydedilemedi: " + a.get_path_name())
    log("Kaydedildi:", ct_path, bp_path, "(DRY)" if DRY_RUN else "")


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
