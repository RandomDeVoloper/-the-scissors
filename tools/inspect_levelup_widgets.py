import unreal,traceback
out=[]
for name in ('WB_LevelUpMaster','WB_LevelUpItems'):
    bp=unreal.load_asset('/Game/SurvivorsTemplate/Widgets/'+name)
    try:
        tree=bp.get_editor_property('WidgetTree')
        out.append(str(tree))
        widgets=tree.get_editor_property('AllWidgets')
        for w in widgets:
            out.append(w.get_name()+' '+w.get_class().get_name())
            try: out.append(' TEXT '+str(w.get_editor_property('Text')))
            except: pass
    except: out.append(traceback.format_exc())
    for gn in unreal.BlueprintEditorLibrary.list_graph_names(bp):
        if 'PreviewKey' in str(gn):
            ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,gn)
            for n in ed.list_all_nodes():
                if 'FunctionEntry' in n.get_name():
                    try: out.append(str(n.get_editor_property('FunctionReference')))
                    except: out.append(traceback.format_exc())
open('C:/Users/Niyazi/-the-scissors/Saved/levelup_widgets.txt','w',encoding='utf-8').write('\n'.join(out))
