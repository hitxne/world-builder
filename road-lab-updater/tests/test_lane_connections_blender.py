import bpy,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab;RoadLab.register()
from RoadLab import road_core,point_settings as ps,lane_editor as e,lane_markings
from RoadLab.native_extension import set_input
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;curve=bpy.data.curves.new('Triangle','CURVE');curve.dimensions='3D'
for path in [[(0,0,.12),(-80,0,.12),(0,-80,.12),(0,0,.12)],[(0,0,.12),(0,65,.12)],[(0,0,.12),(65,0,.12)]]:
 s=curve.splines.new('POLY');s.points.add(len(path)-1)
 for p,co in zip(s.points,path):p.co=(*co,1)
road=bpy.data.objects.new('Triangle',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road)
set_input(road_core.modifier(road),'road width',15);road_core.rebuild(road,True)
rows=lambda n:[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS') for _ in range(n)]
configs=[dict(endpoints=[a,b],incoming=rows(2),outgoing=rows(2),median=0,spacing=18) for _,_,a,b in e.segments(road)]
# Turning branches at actual central junction must advertise legal turns.
configs[0]['outgoing']=rows(2)
for config in configs:
 for field in ('incoming','outgoing'):
  for row in config[field]:row['movement']='THROUGH'
# Validate appropriate movements using actual topology.
from RoadLab import lane_logic
nodes,_,_=road_core.graph([([tuple(p.co[:3]) for p in s.points],[1]*len(s.points)) for s in curve.splines],15)
lookup={x['id']:i for i,x in enumerate(ps.records(road))};points=ps.points(road)
for config in configs:
 a,b=[tuple(points[lookup[i]].co[:3]) for i in config['endpoints']]
 for field,start,end in [('incoming',a,b),('outgoing',b,a)]:
  if len(nodes.get(end,[]))>=3:
   available=lane_logic.available_movements(start,end,nodes[end]);move='THROUGH' if 'THROUGH' in available else 'LEFT' if 'LEFT' in available else 'RIGHT'
   for row in config[field]:row['movement']=move
road['roadlab_lanes']=json.dumps(configs);e.rebuild(road,scene,True)
marks=json.loads(road['roadlab_generated_marking_catalog']);curves=[m for m in marks if m.get('path')]
assert len(curves)>=10
# Bends are not intersections and must not receive approach arrows or stop lines.
for m in marks:
 if m['asset'].startswith('arrow'):assert min(abs(m['center'][0]),abs(m['center'][1]))<10 and max(abs(m['center'][0]),abs(m['center'][1]))<50
assert not json.loads(road['roadlab_marking_warnings'])

from types import SimpleNamespace
bpy.ops.object.select_all(action='DESELECT');road.select_set(True);bpy.context.view_layer.objects.active=road;bpy.ops.object.mode_set(mode='EDIT')
def select(indices):
 for i,p in enumerate(ps.points(road)):p.select=i in indices
context=SimpleNamespace(scene=scene,mode=bpy.context.mode,edit_object=road,active_object=road,window_manager=SimpleNamespace(invoke_props_dialog=lambda *a,**k:{'RUNNING_MODAL'}))
operator=SimpleNamespace(approach='0',preview_status='')
select({1});assert e.ROADLAB_OT_lane_window.invoke(operator,context,None)=={'RUNNING_MODAL'}
assert operator.has_selection and operator.is_junction and len(json.loads(operator.choices_json))==2 and operator.connection_mode=='CONTINUOUS'
original_configs=road['roadlab_lanes'];original_records=road['roadlab_point_settings'];original_mesh=road['roadlab_marking_object'].data.as_pointer()
assert e.tick_lane_preview()==.12 and e._lane_preview['proxy'] is not None
preview=e._lane_preview['proxy'];first_catalog=preview['roadlab_generated_marking_catalog']
scene.roadlab_lane_draft.arrow_approach=0;e.tick_lane_preview()
assert preview['roadlab_generated_marking_catalog']!=first_catalog
assert road['roadlab_lanes']==original_configs and road['roadlab_point_settings']==original_records and road['roadlab_marking_object'].data.as_pointer()==original_mesh
# Idle preview polls do not replace meshes.
preview_mesh=preview['roadlab_marking_object'].data.as_pointer();e.tick_lane_preview()
assert preview['roadlab_marking_object'].data.as_pointer()==preview_mesh
# Stop mode previews across both sides without changing the stored vertex.
operator.connection_mode='STOP';e.tick_lane_preview()
preview_marks=json.loads(preview['roadlab_generated_marking_catalog'])
assert len([m for m in preview_marks if m['asset']=='stop_bar'])==2
assert road['roadlab_point_settings']==original_records
# Preview objects are removed for a file save and regenerated afterward.
e.preview_before_save();assert e._lane_preview is None and not any(o.get('roadlab_temporary_preview') for o in bpy.data.objects)
e.preview_after_save();e.tick_lane_preview();assert e._lane_preview is not None
# Apply commits the vertex choice, but keeps the live session active.
e.apply_window_edits(operator,context)
assert operator.apply_status.startswith('Applied'),operator.apply_status
assert sum(row.get('connection_mode')=='STOP' for row in ps.records(road))==1
assert len([m for m in json.loads(road['roadlab_generated_marking_catalog']) if m['asset']=='stop_bar'])==2
e.tick_lane_preview();assert road['roadlab_marking_object'].hide_get()
# Unapplied change back to continuous is reverted on close.
operator.connection_mode='CONTINUOUS';e.tick_lane_preview();e.ROADLAB_OT_lane_window.cancel(operator,context)
assert not road['roadlab_marking_object'].hide_get() and not any(o.get('roadlab_temporary_preview') for o in bpy.data.objects)
select({1});reopened=SimpleNamespace(approach='0',preview_status='');e.ROADLAB_OT_lane_window.invoke(reopened,context,None)
assert reopened.connection_mode=='STOP'
reopened.connection_mode='CONTINUOUS';e.apply_window_edits(reopened,context)
assert reopened.apply_status.startswith('Applied')
assert not [m for m in json.loads(road['roadlab_generated_marking_catalog']) if m['asset']=='stop_bar']
assert [m for m in json.loads(road['roadlab_generated_marking_catalog']) if m.get('path')]
e.ROADLAB_OT_lane_window.cancel(reopened,context)
bpy.ops.object.mode_set(mode='OBJECT')
# Endpoint extrusion inherits the profile and width; a third branch does not guess.
curve2=bpy.data.curves.new('Extension','CURVE');curve2.dimensions='3D';spl=curve2.splines.new('POLY');spl.points.add(1)
for p,co in zip(spl.points,[(120,0,0),(160,0,0)]):p.co=(*co,1)
ext=bpy.data.objects.new('Extension',curve2);scene.collection.objects.link(ext);scene.wb_native.road=ext;road_core.attach(ext)
set_input(road_core.modifier(ext),'road width',15);road_core.rebuild(ext,True)
a,b=ps.records(ext);ext['roadlab_lanes']=json.dumps([dict(endpoints=[a['id'],b['id']],incoming=rows(2),outgoing=rows(1),median=0,spacing=18)])
spl.points.add(1);spl.points[2].co=(200,0,0,1);road_core.rebuild(ext,True)
assert len(e.state(ext))==2 and len(e.state(ext)[1]['incoming'])==2 and len(e.state(ext)[1]['outgoing'])==1
# Change a straight continuation from two lanes to one: create a bounded taper.
configs=e.state(ext);configs[1]['incoming']=rows(1);ext['roadlab_lanes']=json.dumps(configs);e.rebuild(ext,scene,True)
transitions=[m for m in json.loads(ext['roadlab_generated_marking_catalog']) if m.get('path')]
assert transitions and any(m['role'][1]=='divider' for m in transitions)
assert not json.loads(ext['roadlab_marking_warnings']),ext['roadlab_marking_warnings']
# A future branch preserves the explicit stop choice without inheriting an arbitrary lane layout.
records=ps.records(ext);records[1]['connection_mode']='STOP';ps.save(ext,records)
branch=curve2.splines.new('POLY');branch.points.add(1);branch.points[0].co=(160,0,0,1);branch.points[1].co=(160,40,0,1);road_core.rebuild(ext,True)
assert len(e.state(ext))==2 and any(row.get('connection_mode')=='STOP' for row in ps.records(ext))
print('LIVE_BENDS_EXTENSIONS_PASS',flush=True)
