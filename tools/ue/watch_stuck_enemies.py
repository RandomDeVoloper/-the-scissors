"""Watch enemies for ~20 s during Play and dump the ones that really get stuck. Read-only.

Run while PLAYING M_Arena (Shift+F1, Output Log, Python):
    exec(open(r'C:/Users/Niyazi/-the-scissors/tools/ue/watch_stuck_enemies.py', encoding='utf-8').read())
Keep playing; after ~20 s it writes Saved/Logs/stuck_watch_HHMMSS.txt
"""
import unreal, math, time, datetime

OUT = 'C:/Users/Niyazi/-the-scissors/Saved/Logs/stuck_watch_%s.txt' % datetime.datetime.now().strftime('%H%M%S')
DURATION, WINDOW, MINMOVE = 20.0, 2.5, 25.0
GS = unreal.GameplayStatics
NAV = unreal.NavigationSystemV1
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
CH = unreal.CollisionChannel
CHANNELS = [(n, getattr(CH, n)) for n in ('ECC_WORLD_STATIC', 'ECC_WORLD_DYNAMIC', 'ECC_PAWN', 'ECC_ENEMY', 'ECC_PHYSICS_BODY', 'ECC_VEHICLE', 'ECC_DESTRUCTIBLE') if hasattr(CH, n)]


def v(x):
    return '(%.0f,%.0f,%.0f)' % (x.x, x.y, x.z)


def safe(f):
    try:
        return f()
    except Exception as e:
        return '<%s>' % str(e)[:90]


def gp(o, *names):
    for n in names:
        try:
            return o.get_editor_property(n)
        except Exception:
            pass
    return '?'


hist = {}       # name -> list of (t, loc)
reported = {}
lines = []
t0 = time.time()
state = {'h': None}


def dump(world, e, moved):
    L = []
    ctrl = e.get_controller()
    mv = e.get_movement_component()
    cap = e.get_editor_property('capsule_component')
    l = e.get_actor_location()
    pc = GS.get_player_character(world, 0)
    ppos = pc.get_actor_location() if pc else unreal.Vector()
    L.append('### %s  t=%.1fs  moved %.0fcm in %.1fs  loc=%s r=%.0f distToPlayer=%.0f vel=%.0f' % (
        e.get_name(), time.time() - t0, moved, WINDOW, v(l), math.hypot(l.x, l.y), (l - ppos).length(), e.get_velocity().length()))
    L.append('  mode=%s active=%s tick=%s actorTick=%s dilation=%s maxSpeed=%s' % (
        safe(lambda: mv.get_editor_property('movement_mode')), safe(mv.is_active), safe(mv.is_component_tick_enabled),
        safe(e.is_actor_tick_enabled), safe(lambda: e.get_editor_property('custom_time_dilation')), safe(mv.get_max_speed)))
    L.append('  capsule objType=%s profile=%s responses=%s' % (
        safe(cap.get_collision_object_type), safe(cap.get_collision_profile_name),
        ', '.join('%s=%s' % (n[4:], str(safe(lambda c=c: cap.get_collision_response_to_channel(c))).split('.')[-1].split(':')[0]) for n, c in CHANNELS)))
    if ctrl:
        dest = safe(ctrl.get_immediate_move_destination)
        L.append('  ctrl=%s moveStatus=%s immediateDest=%s focus=%s' % (
            ctrl.get_class().get_name(), safe(ctrl.get_move_status), v(dest) if isinstance(dest, unreal.Vector) else dest,
            safe(lambda: ctrl.get_focus_actor().get_name() if ctrl.get_focus_actor() else None)))
        pfc = gp(ctrl, 'path_following_component')
        L.append('  pathFollowing=%s' % (pfc.get_class().get_name() if hasattr(pfc, 'get_class') else pfc))
        brain = gp(ctrl, 'brain_component')
        L.append('  brain=%s running=%s paused=%s' % (
            brain.get_class().get_name() if hasattr(brain, 'get_class') else brain,
            safe(brain.is_running) if hasattr(brain, 'is_running') else '?', safe(brain.is_paused) if hasattr(brain, 'is_paused') else '?'))
        if isinstance(dest, unreal.Vector):
            d = dest - l
            d.z = 0
            ln = d.length()
            if ln > 1:
                d = d * (60.0 / ln)
                hit = safe(lambda: unreal.SystemLibrary.capsule_trace_single_for_objects(
                    world, l, l + d, cap.get_scaled_capsule_radius(), cap.get_scaled_capsule_half_height() - 2,
                    [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2,
                     unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY3, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY4,
                     unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY5, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY6,
                     unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY7, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY8],
                    False, [e], unreal.DrawDebugTrace.NONE, True))
                if hasattr(hit, 'to_tuple'):
                    t = list(hit.to_tuple())
                    act = [x for x in t if isinstance(x, unreal.Actor)]
                    cmp = [x for x in t if isinstance(x, unreal.ActorComponent)]
                    L.append('  sweep60 toward dest: blocking=%s initialOverlap=%s actor=%s comp=%s' % (
                        t[0], t[1], act[0].get_name() if act else None, cmp[0].get_name() if cmp else None))
                else:
                    L.append('  sweep60 toward dest: %s' % hit)
    p = safe(lambda: NAV.find_path_to_location_synchronously(world, l, ppos))
    if isinstance(p, unreal.NavigationPath):
        pts = list(p.get_editor_property('path_points'))
        L.append('  pathToPlayer valid=%s partial=%s pts=%s' % (safe(p.is_valid), safe(p.is_partial), [v(x) for x in pts[:6]]))
    mesh = gp(e, 'mesh')
    ai = safe(lambda: mesh.get_anim_instance())
    L.append('  anim=%s montage=%s' % (ai.get_class().get_name() if hasattr(ai, 'get_class') else ai,
                                     safe(lambda: ai.get_current_active_montage())))
    for var in ('IsDead', 'PlayerToDamage', 'AllowDespawn'):
        try:
            L.append('  %s=%s' % (var, e.get_editor_property(var)))
        except Exception:
            pass
    try:
        ov = unreal.SystemLibrary.capsule_overlap_actors(world, l, cap.get_scaled_capsule_radius() + 10,
                                                         cap.get_scaled_capsule_half_height(), [
            unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY2,
            unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY3, unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY7], None, [e])
        L.append('  near: %s' % ([a.get_name() for a in ov] if ov else []))
    except Exception as ex:
        L.append('  near err %s' % ex)
    return L


def finish():
    if state['h'] is not None:
        unreal.unregister_slate_post_tick_callback(state['h'])
        state['h'] = None
    head = ['watch %.0fs, stuck rule: MOVING/any status, moved < %.0fcm in %.1fs; reported %d enemies' % (
        DURATION, MINMOVE, WINDOW, len(reported))]
    open(OUT, 'w', encoding='utf-8').write('\n'.join(head + lines))
    unreal.log_warning('[StuckWatch] DONE, %d stuck enemies -> %s' % (len(reported), OUT))


def tick(dt):
    try:
        world = ues.get_game_world()
        now = time.time()
        if world is None or now - t0 > DURATION:
            finish()
            return
        pc = GS.get_player_character(world, 0)
        for e in GS.get_all_actors_of_class(world, unreal.Character):
            if e == pc:
                continue
            n = e.get_name()
            h = hist.setdefault(n, [])
            h.append((now, e.get_actor_location()))
            while h and now - h[0][0] > WINDOW:
                h.pop(0)
            if n in reported or len(h) < 2 or now - h[0][0] < WINDOW * 0.9:
                continue
            moved = (h[-1][1] - h[0][1]).length()
            if moved < MINMOVE:
                ppos = pc.get_actor_location() if pc else h[-1][1]
                if (h[-1][1] - ppos).length() < 180:     # next to the player = attacking, fine
                    continue
                reported[n] = True
                lines.extend(dump(world, e, moved))
    except Exception as ex:
        lines.append('tick err %s' % ex)
        finish()


if ues.get_game_world() is None:
    unreal.log_error('[StuckWatch] not playing! Start Play in M_Arena first.')
else:
    state['h'] = unreal.register_slate_post_tick_callback(tick)
    unreal.log_warning('[StuckWatch] watching for %.0f s, keep playing...' % DURATION)
