"""Endpoint movement updates real curb/sidewalk geometry and live preview rolls back."""
import bpy,sys,json
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import lane_editor as e,crosswalk_ramps as ramps,point_settings as ps
from RoadLab.native_extension import set_input
scene=bpy.context.scene;road=scene.wb_native.road
marks=json.loads(road['roadlab_generated_marking_catalog'])
crossing=next(m for m in marks if m['role'][0]=='crosswalk' and m['source_endpoints']==e.state(road)[2]['endpoints'])
y=crossing['crosswalk_ends'][0][1]
def height(x,y):
    tree=ramps.surface_tree(road);hit=tree.ray_cast(Vector((x,y,20)),Vector((0,0,-1)),40)[0] if tree else None
    assert hit is not None
    return hit.z
assert height(4.15,y)<.06 and height(4.15,-25)>.16
assert height(4.6,y)<.1 and height(6.3,y)>.16
configs=e.state(road);configs[2]['crosswalk_a']=4;road['roadlab_lanes']=json.dumps(configs);e.rebuild(road,scene,True)
assert height(-4.15,y)>.1 and height(-4.15,y-4)<.06 and height(4.15,y)<.06
# Pads sit on the actual lowered layer, rather than being buried at terrain height.
target=road['roadlab_marking_object'];slots={i for i,m in enumerate(target.data.materials) if 'tactile_pad' in m.name};tree=ramps.surface_tree(road)
checked=0
for face in target.data.polygons:
    if face.material_index not in slots:continue
    for i in face.vertices:
        v=target.data.vertices[i].co;hit=tree.ray_cast(Vector((v.x,v.y,20)),Vector((0,0,-1)),40)[0]
        if hit is not None:assert .001<v.z-hit.z<.006;checked+=1
assert checked>0
# A live unsaved endpoint adjustment deforms layers, then closing restores them.
bpy.ops.object.mode_set(mode='EDIT')
for p in ps.points(road):p.select=False
road.data.splines[0].points[1].select=True
context=SimpleNamespace(scene=scene,mode=bpy.context.mode,edit_object=road,active_object=road,window_manager=SimpleNamespace(invoke_props_dialog=lambda *a,**k:{'RUNNING_MODAL'}),screen=None)
operator=SimpleNamespace(approach='0',preview_status='')
e.ROADLAB_OT_lane_window.invoke(operator,context,None);operator.approach='2';e.approach_changed(operator,context)
before=road['roadlab_lanes'];guide=road['roadlab_crosswalk_guide']
scene.roadlab_lane_draft.crosswalk_a=8;e.tick_lane_preview()
assert road['roadlab_lanes']==before and height(-4.15,y-8)<.06
assert e._lane_preview['proxy']['roadlab_crosswalk_guide']!=guide
e.preview_before_save();assert height(-4.15,y-4)<.06
e.preview_after_save();e.tick_lane_preview();assert height(-4.15,y-8)<.06
e.ROADLAB_OT_lane_window.cancel(operator,context)
assert height(-4.15,y-4)<.06 and height(-4.15,y-8)>.1
bpy.ops.object.mode_set(mode='OBJECT')
# The ramp lowers the layer's own height, including custom profile scaling.
for layer in ramps.layers(road):
    for mod in layer.object.modifiers:
        if mod.type=='NODES':set_input(mod,'Profile height scale',2.)
e.rebuild(road,scene,True)
assert height(4.15,y)<.08 and height(4.15,-25)>.3 and height(6.3,y)>.3
print('CROSSWALK_RAMPS_PASS',flush=True)
