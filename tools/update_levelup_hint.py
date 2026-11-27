import unreal,traceback
out=[]
try:
    path='/Game/SurvivorsTemplate/Widgets/WB_LevelUpMaster.WB_LevelUpMaster'
    label=unreal.load_object(None,path+':WidgetTree.TextBlock_224')
    assert label, 'Label not found'
    label.set_editor_property('Text',unreal.Text('Continue [Space]'))
    bp=unreal.load_asset(path)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    out.append('Hint updated: '+str(label.get_editor_property('Text')))
    out.append(str(unreal.ObjectIterator.__doc__))
except: out.append(traceback.format_exc())
open('C:/Users/Niyazi/-the-scissors/Saved/levelup_hint.txt','w',encoding='utf-8').write('\n'.join(out))
