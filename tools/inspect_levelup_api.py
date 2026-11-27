import unreal
B=unreal.BlueprintEditorLibrary
bp=unreal.load_asset('/Game/SurvivorsTemplate/Widgets/WB_LevelUpMaster')
ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'OnPreviewKeyDown_0')
n=list(ed.list_all_nodes())[0]
p=list(B.list_all_pins(n))[0]
out=['EDITOR '+str(dir(ed)),'PIN '+str(dir(p)),'BLUEPRINT '+str(dir(bp))]
out.append('OBJECTS')
open('C:/Users/Niyazi/-the-scissors/Saved/levelup_api.txt','w',encoding='utf-8').write('\n'.join(out))
for o in unreal.ObjectIterator():
    if name_not_used := not o.get_path_name().startswith(bp.get_path_name()+':'):
        continue
    if isinstance(o,unreal.Widget):
        try: out.append(o.get_name()+' '+o.get_class().get_name()+' text='+str(o.get_editor_property('text')))
        except: out.append(o.get_name()+' '+o.get_class().get_name())
open('C:/Users/Niyazi/-the-scissors/Saved/levelup_api.txt','w',encoding='utf-8').write('\n'.join(out))
