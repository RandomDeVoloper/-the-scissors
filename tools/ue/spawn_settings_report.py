"""Dusman spawn ayarlarini raporlar. Salt okunur: hicbir seyi degistirmez.

Editor Output Log (Cmd -> Python) icinde calistir:
    exec(open(r'C:/Users/Niyazi/-the-scissors/tools/ue/spawn_settings_report.py', encoding='utf-8').read())
M_Arena acikken calistir (PIE gerekmez). Rapor: Saved/Logs/spawn_settings_report.txt
"""
import unreal

OUT = 'C:/Users/Niyazi/-the-scissors/Saved/Logs/spawn_settings_report.txt'
BP = '/Game/SurvivorsTemplate/Blueprints/System/BP_Game_Manager'
PROPS = ['MaxEnemies', 'MinEnemiesPerWave', 'MaxEnemiesPerWave', 'SpawnInterval',
         'PhaseIndexTimer', 'MaxGameTime', 'MaxLevel', 'EnemySpawnDT', 'EnemyEliteSpawnDT']
lines = []


def w(s=''):
    lines.append(str(s))
    unreal.log('[SPAWN] ' + str(s))


def dump(obj, title):
    w('== ' + title)
    for p in PROPS:
        try:
            w('  %-20s = %s' % (p, obj.get_editor_property(p)))
        except Exception as e:
            w('  %-20s = ?  (%s)' % (p, str(e)[:80]))


cls = unreal.EditorAssetLibrary.load_blueprint_class(BP)
dump(unreal.get_default_object(cls), 'BP_Game_Manager Class Defaults')

world = unreal.EditorLevelLibrary.get_editor_world()
w('Level: ' + (world.get_name() if world else '?'))
found = 0
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_class() == cls or a.get_class().get_name().startswith('BP_Game_Manager'):
        found += 1
        dump(a, 'Level instance: ' + a.get_actor_label())
if not found:
    w('Levelde BP_Game_Manager instance bulunamadi (GameMode spawn ediyor olabilir).')

for dt_path in ['/Game/SurvivorsTemplate/Blueprints/DataTables/DT_ExampleSpawn',
                '/Game/SurvivorsTemplate/Blueprints/DataTables/DT_ExampleEliteSpawn']:
    dt = unreal.load_asset(dt_path)
    w('== ' + dt_path.split('/')[-1])
    try:
        names = unreal.DataTableFunctionLibrary.get_data_table_row_names(dt)
        w('  satir sayisi: %d -> %s' % (len(names), [str(n) for n in names]))
        try:
            csv = dt.export_to_csv_string() if hasattr(dt, 'export_to_csv_string') else unreal.DataTableFunctionLibrary.export_data_table_to_csv_string(dt)
            for l in csv.splitlines()[:40]:
                w('  ' + l[:300])
        except Exception as e:
            w('  csv yok: %s' % e)
    except Exception as e:
        w('  okunamadi: %s' % e)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
unreal.log('[SPAWN] Rapor yazildi: ' + OUT)
