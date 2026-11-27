"""Run inside the live editor. Space follows Button_Intro without selecting a reward."""
import unreal, traceback, os, shutil, datetime
B=unreal.BlueprintEditorLibrary
G=unreal.BlueprintGraphEditor
ROOT='/Game/SurvivorsTemplate/Widgets/'
LOG=[]
def pin(n,name):
    return next(p for p in B.list_all_pins(n) if str(p.get_pin_name())==name)
def link(a,b):
    assert a.try_create_connection(b), (a.get_pin_name(),b.get_pin_name())
def fn(ed,path,x,y):
    n=ed.add_call_function_node(path)
    assert n,path
    n.set_node_pos(unreal.IntPoint(x,y))
    return n
def nodes(ed): return {n.get_name():n for n in ed.list_all_nodes()}
def wire(a,ap,b,bp): link(pin(a,ap),pin(b,bp))
def compile_save(bp):
    B.compile_blueprint(bp)
    status=bp.get_editor_property('status')
    LOG.append(bp.get_name()+' '+str(status))
    assert status in (unreal.BlueprintStatus.BS_UP_TO_DATE,unreal.BlueprintStatus.BS_UP_TO_DATE_WITH_WARNINGS)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
try:
    backup='C:/Users/Niyazi/-the-scissors/Saved/LevelUpBackup/'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(backup)
    for name in ('WB_LevelUpMaster','WB_LevelUpItems'):
        shutil.copy2('C:/Users/Niyazi/-the-scissors/Content/SurvivorsTemplate/Widgets/'+name+'.uasset',backup)
    bp=unreal.load_asset(ROOT+'WB_LevelUpMaster')
    assert 'ContinueToCards' not in [str(s) for s in B.list_graph_names(bp)], 'Already installed'
    ed=G.create_and_edit_function_graph(bp,'ContinueToCards')
    getter=ed.add_get_member_variable_node('WidgetSwitcher_LevelUp','')
    getter.set_node_pos(unreal.IntPoint(0,180))
    setidx=fn(ed,'/Script/UMG.WidgetSwitcher.SetActiveWidgetIndex',300,0)
    pin(setidx,'Index').set_pin_value('1')
    link(ed.find_graph_entry_pin(),pin(setidx,'execute'))
    wire(getter,'WidgetSwitcher_LevelUp',setidx,'self')
    sound=fn(ed,'/Script/Engine.GameplayStatics.PlaySound2D',600,0)
    pin(sound,'Sound').set_pin_value('/Game/SurvivorsTemplate/Demo/Sounds/Interaction/Cue_ChestGold.Cue_ChestGold')
    pin(sound,'bIsUISound').set_pin_value('true')
    wire(setidx,'then',sound,'execute')
    B.compile_blueprint(bp)
    ev=G.get_graph_editor_by_name(bp,'EventGraph')
    old=nodes(ev)
    click=old['K2Node_ComponentBoundEvent_0']
    call=fn(ev,ROOT+'WB_LevelUpMaster.WB_LevelUpMaster_C.ContinueToCards',300,1250)
    pin(click,'then').break_pin_links()
    wire(click,'then',call,'execute')
    # Focus the parent on construct and every queued level-up reset.
    cdo=unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property('bIsFocusable',True)
    for i,source in enumerate(('K2Node_CallFunction_1','K2Node_CallFunction_11')):
        focus=fn(ev,'/Script/UMG.Widget.SetKeyboardFocus',1200,-200+i*400)
        wire(old[source],'then',focus,'execute')
    ed=G.get_graph_editor_by_name(bp,'OnPreviewKeyDown_0')
    ns=nodes(ed)
    branch=ns['K2Node_IfThenElse_0']
    ret=ns['K2Node_FunctionResult_0']
    # Consume Space only while the intro page is active.
    getter=ed.add_get_member_variable_node('WidgetSwitcher_LevelUp','')
    getter.set_node_pos(unreal.IntPoint(0,450))
    active=fn(ed,'/Script/UMG.WidgetSwitcher.GetActiveWidgetIndex',250,450)
    wire(getter,'WidgetSwitcher_LevelUp',active,'self')
    eq=fn(ed,'/Script/Engine.KismetMathLibrary.EqualEqual_IntInt',500,450)
    wire(active,'ReturnValue',eq,'A')
    pin(eq,'B').set_pin_value('0')
    both=fn(ed,'/Script/Engine.KismetMathLibrary.BooleanAND',700,350)
    wire(eq,'ReturnValue',both,'A')
    wire(ns['K2Node_PromotableOperator_0'],'ReturnValue',both,'B')
    pin(branch,'Condition').break_pin_links()
    wire(both,'ReturnValue',branch,'Condition')
    call=fn(ed,ROOT+'WB_LevelUpMaster.WB_LevelUpMaster_C.ContinueToCards',1000,0)
    pin(branch,'then').break_pin_links()
    wire(branch,'then',call,'execute')
    wire(call,'then',ret,'execute')
    unhandled=fn(ed,'/Script/UMG.WidgetBlueprintLibrary.Unhandled',1000,550)
    ret2=ed.add_return_node()
    ret2.set_node_pos(unreal.IntPoint(1250,350))
    pin(branch,'else').break_pin_links()
    wire(branch,'else',ret2,'execute')
    wire(unhandled,'ReturnValue',ret2,'ReturnValue')
    ret.set_node_pos(unreal.IntPoint(1350,0))
    ed.remove_nodes([ns['K2Node_CallFunction_7'],ns['K2Node_CallFunction_12']])
    compile_save(bp)
    items=unreal.load_asset(ROOT+'WB_LevelUpItems')
    ed=G.get_graph_editor_by_name(items,'OnPreviewKeyDown')
    ns=nodes(ed)
    entry=ns['K2Node_FunctionEntry_0']; ret=ns['K2Node_FunctionResult_0']
    ed.remove_nodes([n for n in ed.list_all_nodes() if n not in (entry,ret)])
    uh=fn(ed,'/Script/UMG.WidgetBlueprintLibrary.Unhandled',200,150)
    wire(entry,'then',ret,'execute'); wire(uh,'ReturnValue',ret,'ReturnValue')
    compile_save(items)
    LOG.append('SUCCESS: shared ContinueToCards, intro-only Space, keyboard focus, Items passthrough.')
except Exception:
    LOG.append(traceback.format_exc())
finally:
    open('C:/Users/Niyazi/-the-scissors/Saved/levelup_fix.txt','w',encoding='utf-8').write('\n'.join(LOG))
