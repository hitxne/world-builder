import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,core_terrain,examples
previous=bpy.context.scene;originals=set(previous.objects)
assert bpy.ops.roadlab.load_example()=={'FINISHED'}
scene=bpy.context.scene;road=scene.wb_native.road;terrain=scene.wb_native.terrain
assert scene!=previous and set(previous.objects)==originals
assert bpy.context.active_object==road and road.type=='CURVE'
assert len(road.data.splines)==2 and sum(len(s.points) for s in road.data.splines)==6
assert terrain.type=='MESH' and len(terrain.data.vertices)==4 and len(terrain.data.polygons)==1
assert terrain.roadlab_core_terrain_enabled and road.roadlab_core_ground_contact
assert not road.get('roadlab_core_error') and not terrain.get('roadlab_core_terrain_error')
assert json.loads(terrain['roadlab_core_terrain_report'])['maximum_seam_error']<1e-4
from RoadLab import lane_editor
marks=json.loads(road['roadlab_generated_marking_catalog'])
assert len([m for m in marks if m['role'][0]=='tactile'])==4
assert len({(tuple(m['source_endpoints']),m['role'][1]) for m in marks if m['role'][0]=='crosswalk'})==2
assert any('tactile_pad' in mat.name for mat in road['roadlab_marking_object'].data.materials)
helper=road['roadlab_core_mesh'];assert helper.hide_get() and helper.hide_render
assert helper.name in scene.objects
bpy.ops.object.mode_set(mode='EDIT');assert bpy.context.mode=='EDIT_CURVE'
for p in road.data.splines[0].points:p.select=False
road.data.splines[0].points[0].select=True;road.data.splines[0].points[0].co.z=4
bpy.ops.object.mode_set(mode='OBJECT');road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
report=json.loads(terrain['roadlab_core_terrain_report']);assert report['maximum_seam_error']<1e-4 and report['triangles']==0 and report['ngons']==0
assert len(terrain.data.vertices)==4 and len(terrain.data.polygons)==1
assert max(v.co.z for v in terrain['roadlab_core_terrain_mesh'].data.vertices)>3.5
configs=lane_editor.state(road);configs[2]['crosswalk_a']=4;road['roadlab_lanes']=json.dumps(configs);lane_editor.rebuild(road,scene,True)
crossings=[m for m in json.loads(road['roadlab_generated_marking_catalog']) if m['role'][0]=='crosswalk' and m['source_endpoints']==configs[2]['endpoints']]
assert crossings and abs(crossings[0]['crosswalk_ends'][0][1]-crossings[0]['crosswalk_ends'][1][1])>3.9
# A second load is isolated and each scene owns its references.
old_scene=scene;old_objects=set(scene.objects)
assert bpy.ops.roadlab.load_example()=={'FINISHED'}
assert bpy.context.scene!=old_scene and set(old_scene.objects)==old_objects
assert bpy.context.scene.wb_native.road['roadlab_core_mesh'].name in bpy.context.scene.objects
assert RoadLab.WB_PT_panel.bl_category=='RoadLab Debug'
print('EDITABLE_EXAMPLE_PASS',flush=True)
