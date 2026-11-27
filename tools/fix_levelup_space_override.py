"""Make Space skip the level-up intro ("Continue") page.

Why the earlier fix did nothing: WB_LevelUpMaster's key handler graph was named
OnPreviewKeyDown_0, which compiles to a plain function the engine never calls.
This script replaces it with a real override of UserWidget.OnPreviewKeyDown:

    Space pressed AND WidgetSwitcher_LevelUp index == 0  -> ContinueToCards, Handled
    otherwise                                             -> Unhandled (key passes on)

It also removes the debug "Space Bar" InputKey + PrintString("Hello") nodes from
the EventGraph. Run headless with the editor CLOSED:
    UnrealEditor-Cmd.exe SurvivorsTemplate.uproject -run=pythonscript -script=tools/fix_levelup_space_override.py
Set LEVELUP_DRY=1 to compile in memory without saving (safe while editor is open).
"""
import unreal, traceback, os, shutil, datetime

B = unreal.BlueprintEditorLibrary
G = unreal.BlueprintGraphEditor
PROJ = 'C:/Users/Niyazi/-the-scissors/'
PATH = '/Game/SurvivorsTemplate/Widgets/WB_LevelUpMaster'
DRY = os.environ.get('LEVELUP_DRY') == '1'
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
    names = [str(s) for s in B.list_graph_names(bp)]
    LOG.append('graphs before ' + str(names))

    # 1) Drop the dead OnPreviewKeyDown_0 function.
    old = B.find_graph(bp, 'OnPreviewKeyDown_0')
    if old:
        B.remove_function_graph(bp, 'OnPreviewKeyDown_0')

    # 2) Real override.
    g = B.add_function_override(bp, 'OnPreviewKeyDown')
    assert g, 'override failed'
    ed = G.get_graph_editor_by_name(bp, str(g.get_name()))
    ns = list(ed.list_all_nodes())
    LOG.append('override nodes ' + str([(n.get_name(), str(B.get_node_title(n))) for n in ns]))
    entry = next(n for n in ns if 'FunctionEntry' in n.get_name())
    result = next(n for n in ns if 'FunctionResult' in n.get_name())
    for p in (pin(entry, 'then'),):
        p.break_pin_links()
    pin(result, 'execute').break_pin_links()
    pin(result, 'ReturnValue').break_pin_links()

    getkey = fn(ed, '/Script/Engine.KismetInputLibrary.GetKey', 250, 200)
    wire(entry, 'InKeyEvent', getkey, 'Input')
    eqkey = fn(ed, '/Script/Engine.KismetInputLibrary.EqualEqual_KeyKey', 500, 200)
    wire(getkey, 'ReturnValue', eqkey, 'A')
    pin(eqkey, 'B').set_pin_value('SpaceBar')
    LOG.append('key B = ' + str(pin(eqkey, 'B').get_pin_value()))

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

    br = None
    for cand in ('Utilities|FlowControl|Branch', 'Branch'):
        try:
            br = ed.create_node_from_name(cand, unreal.Vector2D(1000, 0), [])
        except Exception as e:
            LOG.append('branch %s: %s' % (cand, e))
        if br:
            break
    assert br, 'branch'
    wire(entry, 'then', br, 'execute')
    wire(both, 'ReturnValue', br, 'Condition')

    cont = fn(ed, PATH + '.WB_LevelUpMaster_C.ContinueToCards', 1250, 0)
    wire(br, 'then', cont, 'execute')
    handled = fn(ed, '/Script/UMG.WidgetBlueprintLibrary.Handled', 1250, 150)
    result.set_node_pos(unreal.IntPoint(1550, 0))
    wire(cont, 'then', result, 'execute')
    wire(handled, 'ReturnValue', result, 'ReturnValue')

    unhandled = fn(ed, '/Script/UMG.WidgetBlueprintLibrary.Unhandled', 1250, 450)
    ret2 = ed.add_return_node()
    ret2.set_node_pos(unreal.IntPoint(1550, 300))
    wire(br, 'else', ret2, 'execute')
    wire(unhandled, 'ReturnValue', ret2, 'ReturnValue')

    # 3) Remove debug Space InputKey + PrintString from EventGraph.
    ev = G.get_graph_editor_by_name(bp, 'EventGraph')
    dbg = [n for n in ev.list_all_nodes()
           if n.get_name().startswith('K2Node_InputKey')
           or (n.get_name().startswith('K2Node_CallFunction') and 'PrintString' in str(B.get_node_title(n)).replace(' ', ''))]
    LOG.append('removing ' + str([n.get_name() for n in dbg]))
    ev.remove_nodes(dbg)

    B.compile_blueprint(bp)
    status = bp.get_editor_property('status')
    LOG.append('status ' + str(status))
    assert status in (unreal.BlueprintStatus.BS_UP_TO_DATE, unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS)
    cls = PATH + '.WB_LevelUpMaster_C:'
    f = unreal.find_object(None, cls + 'OnPreviewKeyDown')
    LOG.append('override function ' + str(f))
    assert f, 'OnPreviewKeyDown not compiled into class'
    assert not unreal.find_object(None, cls + 'OnPreviewKeyDown_0')
    LOG.append('graphs after ' + str([str(s) for s in B.list_graph_names(bp)]))

    if not DRY:
        backup = PROJ + 'Saved/LevelUpBackup/' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_override'
        os.makedirs(backup)
        shutil.copy2(PROJ + 'Content/SurvivorsTemplate/Widgets/WB_LevelUpMaster.uasset', backup)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
        LOG.append('saved, backup in ' + backup)
    LOG.append('SUCCESS')
except Exception:
    LOG.append(traceback.format_exc())
finally:
    open(PROJ + 'Saved/levelup_override.txt', 'w', encoding='utf-8').write('\n'.join(LOG))
