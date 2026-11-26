import bpy
import os
from mathutils import Vector

FBX_PATH = r"C:\Users\Niyazi\Downloads\Sweat_baby\Meshy_AI_Patchwork_Sweetheart_20261125_texture_fbx\Meshy_AI_Patchwork_Sweetheart_20261125_texture.fbx"
OUT_BLEND = r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\Survivorffc2cbc15914V6\data\SweatBaby_Rigged.blend"
OUT_FBX = r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\Survivorffc2cbc15914V6\data\SweatBaby_Rigged.fbx"

if not os.path.exists(FBX_PATH):
    raise FileNotFoundError(FBX_PATH)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for datablocks in (bpy.data.armatures, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
    pass

bpy.ops.import_scene.fbx(filepath=FBX_PATH, automatic_bone_orientation=True)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes:
    raise RuntimeError('FBX imported without mesh objects')

# Put the asset into a predictable Unreal-friendly working orientation.
for obj in meshes:
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

corners = []
for obj in meshes:
    corners.extend([obj.matrix_world @ Vector(c) for c in obj.bound_box])
mn = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
mx = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
c = (mn + mx) * 0.5
w = max(mx.x - mn.x, 0.01)
h = max(mx.z - mn.z, 0.01)

arm_data = bpy.data.armatures.new('ARM_SweatBaby')
arm_obj = bpy.data.objects.new('ARM_SweatBaby', arm_data)
bpy.context.collection.objects.link(arm_obj)
arm_obj.show_in_front = True
bpy.context.view_layer.objects.active = arm_obj
arm_obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')

def bone(name, head, tail, parent=None, connected=False):
    b = arm_data.edit_bones.new(name)
    b.head = head
    b.tail = tail
    if parent:
        b.parent = arm_data.edit_bones.get(parent)
        b.use_connect = connected
    return b

z = lambda p: mn.z + h * p
bone('root', Vector((c.x, c.y, mn.z)), Vector((c.x, c.y, z(0.08))))
bone('pelvis', Vector((c.x, c.y, z(0.42))), Vector((c.x, c.y, z(0.52))), 'root')
bone('spine', Vector((c.x, c.y, z(0.52))), Vector((c.x, c.y, z(0.66))), 'pelvis', True)
bone('chest', Vector((c.x, c.y, z(0.66))), Vector((c.x, c.y, z(0.78))), 'spine', True)
bone('neck', Vector((c.x, c.y, z(0.78))), Vector((c.x, c.y, z(0.84))), 'chest', True)
bone('head', Vector((c.x, c.y, z(0.84))), Vector((c.x, c.y, z(1.00))), 'neck', True)

for side, sx in [('l', 1.0), ('r', -1.0)]:
    x0 = c.x + sx * w * 0.10
    x1 = c.x + sx * w * 0.30
    x2 = c.x + sx * w * 0.47
    x3 = c.x + sx * w * 0.57
    bone(f'clavicle_{side}', Vector((x0, c.y, z(0.75))), Vector((x1, c.y, z(0.74))), 'chest')
    bone(f'upperarm_{side}', Vector((x1, c.y, z(0.74))), Vector((x2, c.y, z(0.67))), f'clavicle_{side}', True)
    bone(f'forearm_{side}', Vector((x2, c.y, z(0.67))), Vector((x3, c.y, z(0.60))), f'upperarm_{side}', True)
    bone(f'hand_{side}', Vector((x3, c.y, z(0.60))), Vector((x3 + sx * w * 0.07, c.y, z(0.58))), f'forearm_{side}', True)

for side, sx in [('l', 1.0), ('r', -1.0)]:
    hip = c.x + sx * w * 0.10
    knee = c.x + sx * w * 0.12
    ankle = c.x + sx * w * 0.14
    foot = c.x + sx * w * 0.20
    bone(f'thigh_{side}', Vector((hip, c.y, z(0.43))), Vector((knee, c.y, z(0.25))), 'pelvis')
    bone(f'calf_{side}', Vector((knee, c.y, z(0.25))), Vector((ankle, c.y, z(0.08))), f'thigh_{side}', True)
    bone(f'foot_{side}', Vector((ankle, c.y, z(0.08))), Vector((foot, c.y - w * 0.10, z(0.04))), f'calf_{side}', True)

bpy.ops.object.mode_set(mode='POSE')
for pb in arm_obj.pose.bones:
    pb.rotation_mode = 'QUATERNION'
bpy.ops.object.mode_set(mode='OBJECT')

# Automatic weights for the body mesh(es), preserving separate mesh objects.
for obj in meshes:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    except RuntimeError:
        obj.parent = arm_obj
        mod = obj.modifiers.new('ArmatureDeform', 'ARMATURE')
        mod.object = arm_obj

bpy.ops.object.select_all(action='DESELECT')
arm_obj.select_set(True)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

# Export a UE-friendly FBX alongside the editable Blender file.
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
arm_obj.select_set(True)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.export_scene.fbx(
    filepath=OUT_FBX,
    use_selection=True,
    object_types={'ARMATURE', 'MESH'},
    add_leaf_bones=False,
    bake_anim=False,
    apply_unit_scale=True,
    axis_forward='-Z',
    axis_up='Y',
)
print('RIG_COMPLETE', OUT_BLEND, OUT_FBX)
