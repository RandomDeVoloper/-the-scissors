"""Diagnose enemies getting stuck in M_Arena. Read-only: changes nothing.

Run in the editor Output Log (Cmd -> Python):
    exec(open(r'C:/Users/Niyazi/-the-scissors/tools/ue/diagnose_enemy_stuck.py', encoding='utf-8').read())
Best: start Play, wait until an enemy is stuck, press Shift+F1 to free the mouse, run it.
Report: Saved/Logs/enemy_stuck_report.txt
"""
import unreal, math, os, datetime

OUT = 'C:/Users/Niyazi/-the-scissors/Saved/Logs/enemy_stuck_report_%s.txt' % datetime.datetime.now().strftime('%H%M%S')
lines = []


def w(s=''):
    lines.append(str(s))


def gp(o, *names):
    for n in names:
        try:
            return o.get_editor_property(n)
        except Exception:
            pass
    return '?'


def v(x):
    try:
        return '(%.0f,%.0f,%.0f)' % (x.x, x.y, x.z)
    except Exception:
        return str(x)


def safe(f, default='?'):
    try:
        return f()
    except Exception as e:
        return '%s<%s>' % (default, type(e).__name__ + ':' + str(e)[:80])


ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
game = ues.get_game_world()
world = game or ues.get_editor_world()
GS = unreal.GameplayStatics
NAV = unreal.NavigationSystemV1
w('time %s  world=%s  PIE=%s' % (datetime.datetime.now(), world.get_name(), bool(game)))
if 'Arena' not in world.get_name():
    unreal.log_error('[EnemyDiag] current world is %s, not M_Arena! Run it while playing M_Arena.' % world.get_name())
w('nav fns: %s' % [n for n in dir(NAV) if 'project' in n.lower() or 'path' in n.lower()])
PROJ_FN = None
for _n in ('project_point_to_navigation', 'k2_project_point_to_navigation'):
    if hasattr(NAV, _n):
        PROJ_FN = getattr(NAV, _n)
        break
ENEMY_CH = getattr(unreal.CollisionChannel, 'ECC_ENEMY', None)


def actors(cls):
    return list(GS.get_all_actors_of_class(world, cls))


# ---------- nav data ----------
w('\n== RecastNavMesh')
for n in actors(unreal.RecastNavMesh):
    w('%s radius=%s height=%s step=%s slope=%s cell=%s cellH=%s runtime=%s minRegion=%s' % (
        n.get_name(), gp(n, 'agent_radius'), gp(n, 'agent_height'), gp(n, 'agent_max_step_height'),
        gp(n, 'agent_max_slope'), gp(n, 'cell_size'), gp(n, 'cell_height'), gp(n, 'runtime_generation'),
        gp(n, 'min_region_area')))
w('== NavMeshBoundsVolume')
for b in actors(unreal.NavMeshBoundsVolume):
    o, e = b.get_actor_bounds(False)
    w('%s center=%s extent=%s' % (b.get_actor_label() if not game else b.get_name(), v(o), v(e)))


def project(p, ext=(50, 50, 250)):
    try:
        r = PROJ_FN(world, p, None, None, unreal.Vector(*ext))
    except Exception as e:
        return False, 'ERR %s' % e
    if isinstance(r, tuple):
        r = [x for x in r if isinstance(x, unreal.Vector)]
        r = r[0] if r else None
    if isinstance(r, unreal.Vector):
        return True, r
    return False, 'not on nav'


def path(a, b):
    p = safe(lambda: NAV.find_path_to_location_synchronously(world, a, b))
    if not isinstance(p, unreal.NavigationPath):
        return 'ERR %s' % p
    try:
        pts = list(p.get_editor_property('path_points'))
    except Exception:
        pts = []
    try:
        ln = float(p.get_path_length())
    except Exception:
        ln = -1.0
    return 'valid=%s partial=%s len=%.0f pts=%d end=%s' % (
        safe(p.is_valid), safe(p.is_partial), ln, len(pts), v(pts[-1]) if pts else '-')


# ---------- grid: arena floor connectivity ----------
w('\n== Floor grid: project + path to (0,0) (only problems listed)')
center = unreal.Vector(0, 0, 60)
okc, cpt = project(center)
w('center projected ok=%s %s' % (okc, v(cpt) if okc else cpt))
bad = 0
total = 0
for r in range(0, 1800, 150):
    steps = max(1, int(2 * math.pi * r / 150)) if r else 1
    for k in range(steps):
        a = 2 * math.pi * k / steps
        p = unreal.Vector(r * math.cos(a), r * math.sin(a), 60)
        total += 1
        ok, pt = project(p)
        if not ok:
            if PROJ_FN:
                continue
            pt = p
        res = path(pt, cpt if okc else center)
        if 'partial=False' not in res or 'valid=True' not in res:
            bad += 1
            w('  r=%4d ang=%3.0f  proj=%s  %s' % (r, math.degrees(a), v(pt), res))
w('grid points=%d  path problems=%d' % (total, bad))

# ---------- enemy classes ----------
w('\n== Enemy class defaults')
ENEMY_CLASSES = ['/Game/SurvivorsTemplate/Blueprints/Enemies/BP_Base_Enemy',
                 '/Game/SurvivorsTemplate/Blueprints/Enemies/BP_Enemy_Biohazard',
                 '/Game/SurvivorsTemplate/Blueprints/Enemies/BP_Enemy_Spiker']
for pth in ENEMY_CLASSES:
    try:
        bpc = unreal.EditorAssetLibrary.load_blueprint_class(pth)
        d = unreal.get_default_object(bpc)
        cap = gp(d, 'capsule_component', 'CapsuleComponent')
        mv = gp(d, 'character_movement', 'CharacterMovement')
        if cap == '?':
            w('   (CDO components not readable; see runtime section)')
            continue
        w('%s ctrl=%s' % (pth.split('/')[-1], gp(d, 'ai_controller_class')))
        w('   capsule r=%s hh=%s profile=%s affectNav=%s area=%s' % (
            safe(cap.get_unscaled_capsule_radius), safe(cap.get_unscaled_capsule_half_height),
            safe(cap.get_collision_profile_name), gp(cap, 'can_ever_affect_navigation'), gp(cap, 'area_class')))
        w('   move land=%s step=%s walkSpeed=%s floorAngle=%s rvo=%s rvoR=%s projNav=%s navAgent=%s' % (
            gp(mv, 'default_land_movement_mode'), gp(mv, 'max_step_height'), gp(mv, 'max_walk_speed'),
            gp(mv, 'walkable_floor_angle'), gp(mv, 'use_rvo_avoidance', 'b_use_rvo_avoidance'),
            gp(mv, 'avoidance_consideration_radius'), gp(mv, 'project_nav_mesh_walking', 'b_project_nav_mesh_walking'),
            gp(mv, 'nav_agent_props')))
    except Exception as e:
        w('%s ERR %s' % (pth, e))

# ---------- static props ----------
w('\n== Static mesh actors within r<2700 that have collision')
for a in actors(unreal.StaticMeshActor):
    l = a.get_actor_location()
    if math.hypot(l.x, l.y) > 2700:
        continue
    c = a.static_mesh_component
    ce = safe(c.get_collision_enabled)
    if str(ce).endswith('NO_COLLISION'):
        continue
    sm = c.static_mesh
    o, e = a.get_actor_bounds(True)
    enemy_resp = safe(lambda: c.get_collision_response_to_channel(ENEMY_CH))
    w('%-26s %-22s loc=%s r=%4.0f ext=%s coll=%s prof=%s affectNav=%s enemyResp=%s hidden=%s' % (
        a.get_actor_label() if not game else a.get_name(), sm.get_name() if sm else None, v(l), math.hypot(l.x, l.y),
        v(e), str(ce).split('.')[-1], safe(c.get_collision_profile_name), gp(c, 'can_ever_affect_navigation'),
        str(enemy_resp).split('.')[-1], a.is_hidden_ed() if not game else gp(a, 'hidden')))

# other actor types near arena
w('\n== Other actors (non-StaticMesh) near arena')
for a in actors(unreal.Actor):
    cn = a.get_class().get_name()
    if cn in ('StaticMeshActor', 'PointLight', 'NavMeshBoundsVolume', 'RecastNavMesh'):
        continue
    l = a.get_actor_location()
    if math.hypot(l.x, l.y) < 3000:
        w('  %-30s %-28s %s' % (cn, a.get_name(), v(l)))

# ---------- runtime enemies ----------
if game:
    w('\n== Runtime pawns')
    players = list(GS.get_all_actors_of_class(world, unreal.Character))
    pc = GS.get_player_character(world, 0)
    ppos = pc.get_actor_location() if pc else unreal.Vector(0, 0, 60)
    w('player at %s' % v(ppos))
    for e in players:
        if e == pc:
            continue
        ctrl = e.get_controller()
        mv = e.get_movement_component()
        l = e.get_actor_location()
        mesh = gp(e, 'mesh')
        ai = safe(lambda: mesh.get_anim_instance())
        mont = safe(lambda: ai.get_current_active_montage())
        ok, pt = project(l, (60, 60, 300))
        w('%s loc=%s r=%.0f distToPlayer=%.0f vel=%.0f mode=%s' % (
            e.get_name(), v(l), math.hypot(l.x, l.y), (l - ppos).length(), e.get_velocity().length(),
            safe(lambda: mv.get_editor_property('movement_mode'))))
        w('   ctrl=%s moveStatus=%s montage=%s anim=%s' % (
            ctrl.get_class().get_name() if ctrl else None,
            safe(lambda: ctrl.get_move_status()) if ctrl else '-',
            mont.get_name() if hasattr(mont, 'get_name') else mont,
            ai.get_class().get_name() if hasattr(ai, 'get_class') else ai))
        try:
            cap = e.get_editor_property('capsule_component')
            w('   capsule r=%.0f hh=%.0f profile=%s affectNav=%s | step=%s land=%s rvo=%s walk=%s' % (
                cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height(), cap.get_collision_profile_name(),
                gp(cap, 'can_ever_affect_navigation'), gp(mv, 'max_step_height'), gp(mv, 'default_land_movement_mode'),
                gp(mv, 'use_rvo_avoidance', 'b_use_rvo_avoidance'), gp(mv, 'max_walk_speed')))
        except Exception as ex:
            w('   cap err %s' % ex)
        w('   onNav=%s proj=%s pathToPlayer: %s' % (ok, v(pt) if ok else '-', path(pt if ok else l, ppos)))
        for var in ('IsAlive', 'Is Alive', 'IsDead', 'EnemyState', 'PlayerToDamage', 'AllowDespawn'):
            try:
                w('   %s=%s' % (var, e.get_editor_property(var)))
            except Exception:
                pass
        try:
            for comp in e.get_components_by_class(unreal.SphereComponent):
                ov = [x.get_name() for x in comp.get_overlapping_actors()]
                w('   sphere %s r=%.0f overlaps=%s' % (comp.get_name(), comp.get_scaled_sphere_radius(), ov))
            cap = e.get_editor_property('capsule_component')
            ov = [x.get_name() for x in unreal.SystemLibrary.capsule_overlap_actors(
                world, l, cap.get_scaled_capsule_radius() + 15, cap.get_scaled_capsule_half_height() + 5,
                [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2], None, [e])]
            w('   touching static/dynamic: %s' % ov)
        except Exception as ex:
            w('   comp err %s' % ex)
        try:
            bb = unreal.AIBlueprintHelperLibrary.get_blackboard(e)
            w('   BB Target=%s State=%s' % (safe(lambda: bb.get_value_as_object('Target')),
                                         safe(lambda: bb.get_value_as_enum('EnemyState'))))
        except Exception as ex:
            w('   bb err %s' % ex)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(lines))
unreal.log_warning('[EnemyDiag] wrote %d lines -> %s' % (len(lines), OUT))
