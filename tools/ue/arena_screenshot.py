"""Editor-side preview: spawns temporary cameras in M_Arena, saves high-res screenshots, quits.
Run:  UnrealEditor.exe SurvivorsTemplate.uproject /Game/Arena/Maps/M_Arena -ExecutePythonScript=tools/ue/arena_screenshot.py
Shots land in Saved/Screenshots/WindowsEditor/. Nothing is saved to the map."""
import unreal

EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
LES.load_level("/Game/Arena/Maps/M_Arena")
shots = [
    # name, camera location, rotation (gameplay-like: pitch -35, looking +X)
    ("arena_overview", unreal.Vector(-3400, -2600, 3600), unreal.Rotator(roll=0, pitch=-42, yaw=37)),
    ("arena_gameplay_view", unreal.Vector(-2050, 0, 1500), unreal.Rotator(roll=0, pitch=-35, yaw=0)),
    ("arena_far_side", unreal.Vector(300, -700, 900), unreal.Rotator(roll=0, pitch=-22, yaw=20)),
]
cams = []
for name, loc, rot in shots:
    c = EAS.spawn_actor_from_class(unreal.CameraActor, loc, rot)
    c.camera_component.set_editor_property("field_of_view", 50.0)
    cams.append((name, c))
state = {"i": 0, "last": 0}
WARMUP, GAP = 400, 150   # engine frames (loading blocks frames, so count frames, not seconds)


def tick(dt):
    f = unreal.SystemLibrary.get_frame_count()
    if f < WARMUP:
        return
    i = state["i"]
    if i < len(cams):
        if f - state["last"] >= GAP:
            name, cam = cams[i]
            unreal.AutomationLibrary.take_high_res_screenshot(1920, 1080, name + ".png", camera=cam)
            state["i"] += 1
            state["last"] = f
    elif f - state["last"] > 300:
        for _, c in cams:
            EAS.destroy_actor(c)
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()


handle = unreal.register_slate_post_tick_callback(tick)
