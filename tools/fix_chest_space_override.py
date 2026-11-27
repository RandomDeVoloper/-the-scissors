"""Make Space skip the "CHEST FOUND!" intro (Continue) page in WB_ChestMaster.

Adds a real UserWidget.OnPreviewKeyDown override:
    Space AND WidgetSwitcher_LevelUp index == 0 -> SetActiveWidgetIndex(1) + Cue_ChestGold, Handled
    otherwise                                     -> Unhandled
(the same thing the Button_Intro click does). Run headless with the editor CLOSED.
Set CHEST_DRY=1 to compile in memory without saving.
"""
import unreal, traceback, os, shutil, datetime

B = unreal.BlueprintEditorLibrary
G = unreal.BlueprintGraphEditor
PROJ = 'C:/Users/Niyazi/-the-scissors/'
PATH = '/Game/SurvivorsTemplate/Widgets/WB_ChestMaster'
DRY = os.environ.get('CHEST_DRY') == '1'
LOG = ['DRY' if DRY else 'APPLY']


def pin(n, name):
    for p in B.list_all_pins(n):
        if str(p.get_pin_name()) == name:
            return p
    raise AssertionError('pin %s not on %s: %s' % (name, n.get_name(), [str(p.get_pin_name()) for p in B.list_all_pins(n)]))


def wire(a, ap, b, bp):
    assert pin(a, ap).try_create_connection(pin(b, bp)), (a.get_name(), ap, b.get_name(), bp)


def fn(ed, path, x, y):
    n = ed.add_call_function_node(path)
    assert n, path
    n.set_node_pos(unreal.IntPoint(x, y))
    return n


try:
    bp = unreal.load_asset(PATH)
    assert 'OnPreviewKeyDown' not in [str(s) for s in B.list_graph_names(bp)], 'already installed'
    g = B.add_function_override(bp, 'OnPreviewKeyDown')
    assert g, 'override failed'
    ed = G.get_graph_editor_by_name(bp, str(g.get_name()))
    ns = list(ed.list_all_nodes())
    entry = next(n for n in ns if 'FunctionEntry' in n.get_name())
    result = next(n for n in ns if 'FunctionResult' in n.get_name())
    pin(entry, 'then').break_pin_links()
    pin(result, 'execute').break_pin_links()
    pin(result, 'ReturnValue').break_pin_links()

    getkey = fn(ed, '/Script/Engine.KismetInputLibrary.GetKey', 250, 200)
    wire(entry, 'InKeyEvent', getkey, 'Input')
    eqkey = fn(ed, '/Script/Engine.KismetInputLibrary.EqualEqual_KeyKey', 500, 200)
    wire(getkey, 'ReturnValue', eqkey, 'A')
    pin(eqkey, 'B').set_pin_value('SpaceBar')

    sw = ed.add_get_member_variable_node('WidgetSwitcher_LevelUp', '')
    sw.set_node_pos(unreal.IntPoint(250, 400))
    idx = fn(ed, '/Script/UMG.WidgetSwitcher.GetActiveWidgetIndex', 500, 400)
    wire(sw, 'WidgetSwitcher_LevelUp', idx, 'self')
    eqi = fn(ed, '/Script/Engine.KismetMathLibrary.EqualEqual_IntInt', 750, 400)
    wire(idx, 'ReturnValue', eqi, 'A')
    pin(eqi, 'B').set_pin_value('0')
    both = fn(ed, '/Script/Engine.KismetMathLibrary.BooleanAND', 750, 200)
    wire(eqkey, 'ReturnValue', both, 'A')
    wire(eqi, 'ReturnValue', both, 'B')

    br = ed.create_node_from_name('Utilities|FlowControl|Branch', unreal.Vector2D(1000, 0), [])
    assert br, 'branch'
    wire(entry, 'then', br, 'execute')
    wire(both, 'ReturnValue', br, 'Condition')

    sw2 = ed.add_get_member_variable_node('WidgetSwitcher_LevelUp', '')
    sw2.set_node_pos(unreal.IntPoint(1000, 250))
    setidx = fn(ed, '/Script/UMG.WidgetSwitcher.SetActiveWidgetIndex', 1250, 0)
    wire(br, 'then', setidx, 'execute')
    wire(sw2, 'WidgetSwitcher_LevelUp', setidx, 'self')
    pin(setidx, 'Index').set_pin_value('1')
    sound = fn(ed, '/Script/Engine.GameplayStatics.PlaySound2D', 1550, 0)
    pin(sound, 'Sound').set_pin_value('/Game/SurvivorsTemplate/Demo/Sounds/Interaction/Cue_ChestGold.Cue_ChestGold')
    pin(sound, 'bIsUISound').set_pin_value('true')
    wire(setidx, 'then', sound, 'execute')
    handled = fn(ed, '/Script/UMG.WidgetBlueprintLibrary.Handled', 1550, 250)
    result.set_node_pos(unreal.IntPoint(1900, 0))
    wire(sound, 'then', result, 'execute')
    wire(handled, 'ReturnValue', result, 'ReturnValue')

    unhandled = fn(ed, '/Script/UMG.WidgetBlueprintLibrary.Unhandled', 1550, 500)
    ret2 = ed.add_return_node()
    ret2.set_node_pos(unreal.IntPoint(1900, 400))
    wire(br, 'else', ret2, 'execute')
    wire(unhandled, 'ReturnValue', ret2, 'ReturnValue')

    B.compile_blueprint(bp)
    status = bp.get_editor_property('status')
    LOG.append('status ' + str(status))
    assert status in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS)
    f = unreal.find_object(None, PATH + '.WB_ChestMaster_C:OnPreviewKeyDown')
    LOG.append('override function ' + str(f))
    assert f
    LOG.append('sound pin ' + str(pin(sound, 'Sound').get_pin_value()))
    if not DRY:
        backup = PROJ + 'Saved/ChestBackup/' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(backup)
        shutil.copy2(PROJ + 'Content/SurvivorsTemplate/Widgets/WB_ChestMaster.uasset', backup)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
        LOG.append('saved, backup in ' + backup)
    LOG.append('SUCCESS')
except Exception:
    LOG.append(traceback.format_exc())
finally:
    open(PROJ + 'Saved/chest_override.txt', 'w', encoding='utf-8').write('\n'.join(LOG))
