import bpy,sys,json
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import lane_editor as e,point_settings as ps
scene=bpy.context.scene
curve=bpy.data.curves.new('Selection regression','CURVE');curve.dimensions='3D'
for end in [(30,0,0),(-30,0,0),(0,30,0),(0,-30,0)]:
 s=curve.splines.new('POLY');s.points.add(1);s.points[0].co=(*end,1);s.points[1].co=(0,0,0,1)
road=bpy.data.objects.new('Selection regression',curve);scene.collection.objects.link(road);road['roadlab_new_core']=True
bpy.ops.object.select_all(action='DESELECT');road.select_set(True);bpy.context.view_layer.objects.active=road;scene.wb_native.road=road
from RoadLab import road_core;road_core.attach(road);ps.sync(road);bpy.ops.object.mode_set(mode='EDIT')
checks=[]
def select(indices):
 for i,p in enumerate(ps.points(road)):p.select=i in indices

def context():
 return SimpleNamespace(scene=scene,mode=bpy.context.mode,edit_object=road,active_object=road,window_manager=SimpleNamespace(invoke_props_dialog=lambda op,**kw: checks.append((op.has_selection,kw['confirm_text'])) or {'RUNNING_MODAL'}))
def window():
 op=SimpleNamespace(has_selection=False,selection_hint='',choices_json='[]',is_junction=False,junction_label='',approach='0')
 assert e.ROADLAB_OT_lane_window.invoke(op,context(),None)=={'RUNNING_MODAL'}
 return op
select({1});op=window();assert op.has_selection and op.is_junction and len(json.loads(op.choices_json))==4
select({1,3,5,7});op=window();assert op.has_selection and op.is_junction
select({0,1});op=window();assert op.has_selection and not op.is_junction
select(set());op=window();assert not op.has_selection and checks[-1][1]=='Close'
select({0});op=window();assert not op.has_selection
select({0,2,4});op=window();assert not op.has_selection
# A selected junction survives toolbar opening: no viewport selection is invoked.
select({1});before=ps.selected(bpy.context,road)
original=bpy.ops.roadlab.lane_window
# Test the actual operator invocation path through a window capture; no headless UI needed.
class Ops:
 def __call__(self,*args,**kwargs):
  assert ps.selected(bpy.context,road)==before
  window();return {'RUNNING_MODAL'}
bpy.ops.roadlab.lane_window=Ops()
try:
 result=e.ROADLAB_OT_lane_pick.invoke(SimpleNamespace(report=lambda *a:None),bpy.context,SimpleNamespace(shift=False,mouse_region_x=0,mouse_region_y=0))
 assert result=={'FINISHED'} and ps.selected(bpy.context,road)==before
finally:bpy.ops.roadlab.lane_window=original
# Active edited road wins over a stale scene assignment.
scene.wb_native.road=None;select({1});op=window();assert op.has_selection and scene.wb_native.road==road
bpy.ops.object.mode_set(mode='OBJECT')
print('LANE_WINDOW_GUIDANCE_PASS',json.dumps(checks),flush=True)
