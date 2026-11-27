import unreal,traceback
out=[]
try:
    bp=unreal.load_asset('/Game/SurvivorsTemplate/Blueprints/System/BP_Gameplay_PlayerController')
    out.append('PC graphs '+str(unreal.BlueprintEditorLibrary.list_graph_names(bp)))
    for o in unreal.ObjectIterator():
        try: path=o.get_path_name()
        except: continue
        if 'WB_LevelUp' in path or ('UEDPIE' in path and 'PlayerController' in path):
            out.append(path)
            if 'TextBlock' in path:
                try:
                    text=str(o.get_editor_property('Text'))
                    out.append(text)
                    if 'Space to skip' in text:
                        o.set_editor_property('Text',unreal.Text('Select one item'))
                except: pass
    items=unreal.load_asset('/Game/SurvivorsTemplate/Widgets/WB_LevelUpItems')
    unreal.BlueprintEditorLibrary.compile_blueprint(items)
    unreal.EditorAssetLibrary.save_loaded_asset(items,False)
except: out.append(traceback.format_exc())
open('C:/Users/Niyazi/-the-scissors/Saved/levelup_runtime.txt','w',encoding='utf-8').write('\n'.join(out))
