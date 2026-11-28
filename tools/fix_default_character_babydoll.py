"""Make the default character (DT_AvailableCharacters / Char1) use SKM_BabyDoll instead of SKM_Quinn_Simple.

Why: BFL_Helper > LoadPlayerData creates a fresh save when no save slot exists and fills
SaveData.Character from DT_AvailableCharacters row "Char1". Char1 never overrode
"Character SK", so it inherits the ST_AvailableCharacters struct default = SKM_Quinn_Simple.
LoadLastCharacterClass -> S_SetCharacterData -> OnRep then swaps the mesh to Quinn.

Run inside the open editor (Output Log, switch "Cmd" to "Python"):
    exec(open(r'C:/Users/Niyazi/-the-scissors/tools/fix_default_character_babydoll.py', encoding='utf-8').read())
Set CHAR_DRY=1 (env) to only print, without changing/saving.
"""
import unreal, json, os, shutil, datetime

PROJ = 'C:/Users/Niyazi/-the-scissors/'
DT_PATH = '/Game/SurvivorsTemplate/Blueprints/DataTables/DT_AvailableCharacters'
ROW = 'Char1'
MESH = "/Script/Engine.SkeletalMesh'/Game/SurvivorsTemplate/Blueprints/Character/BabyDoll/SKM_BabyDoll.SKM_BabyDoll'"
DRY = os.environ.get('CHAR_DRY') == '1'
L = unreal.DataTableFunctionLibrary


def norm(k):
    return k.replace(' ', '').replace('_', '').lower()


def find_key(row, wanted):
    for k in row:
        if norm(k).startswith(wanted):
            return k
    raise AssertionError('no %s field in row keys %s' % (wanted, list(row)))


dt = unreal.load_asset(DT_PATH)
assert dt, DT_PATH
rows = json.loads(L.export_data_table_to_json_string(dt))
sk = find_key(rows[0], 'charactersk')
for r in rows:
    unreal.log('[CharFix] before  %-6s %s' % (r.get('Name'), r.get(sk)))

target = [r for r in rows if r.get('Name') == ROW]
assert target, 'row %s not found' % ROW
target[0][sk] = MESH

if DRY:
    unreal.log('[CharFix] DRY run, nothing saved')
else:
    src = PROJ + 'Content/SurvivorsTemplate/Blueprints/DataTables/DT_AvailableCharacters.uasset'
    bak = PROJ + 'Saved/Backups/DT_AvailableCharacters_%s.uasset' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    os.makedirs(os.path.dirname(bak), exist_ok=True)
    shutil.copy2(src, bak)
    assert L.fill_data_table_from_json_string(dt, json.dumps(rows)), 'fill_data_table_from_json_string failed'
    assert unreal.EditorAssetLibrary.save_loaded_asset(dt, only_if_is_dirty=False), 'save failed'
    unreal.log('[CharFix] backup: ' + bak)
    for r in json.loads(L.export_data_table_to_json_string(dt)):
        unreal.log('[CharFix] after   %-6s %s' % (r.get('Name'), r.get(sk)))
