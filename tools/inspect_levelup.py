import unreal, traceback
out=[]
try:
    B=unreal.BlueprintEditorLibrary
    for name in ('WB_LevelUpMaster','WB_LevelUpItems'):
        bp=unreal.load_asset('/Game/SurvivorsTemplate/Widgets/'+name)
        out.append('ASSET '+name)
        for gn in B.list_graph_names(bp):
            ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,gn)
            out.append('GRAPH '+str(gn))
            for n in ed.list_all_nodes():
                out.append('NODE '+n.get_name()+' '+str(B.get_node_title(n)).replace('\n',' '))
                for p in B.list_all_pins(n):
                    out.append(' PIN %s %s = %s -> %s'%(p.get_pin_name(),p.get_pin_direction(),p.get_pin_value(),[(q.get_owning_node().get_name(),str(q.get_pin_name())) for q in p.list_connected_pins()]))
except Exception:
    out.append(traceback.format_exc())
open('C:/Users/Niyazi/-the-scissors/Saved/levelup_inspect.txt','w',encoding='utf-8').write('\n'.join(out))
