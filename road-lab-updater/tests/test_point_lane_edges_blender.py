"""Single handles, isolated width drafts, independent edge gaps and stable tapers."""
import bpy,sys,json,math,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_editor as e,lane_add,point_settings as ps,road_edges
from RoadLab.native_extension import set_input
scene=bpy.context.scene;curve=bpy.data.curves.new('Point lanes','CURVE');curve.dimensions='3D'
for path in [[(-120,0,.02),(-60,0,.02),(0,0,.02),(120,0,.02)],[(0,-80,.02),(0,0,.02),(0,80,.02)]]:
 s=curve.splines.new('POLY');s.points.add(len(path)-1)
 for p,co in zip(s.points,path):p.co=(*co,1)
road=bpy.data.objects.new('Point lanes',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
lane=[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=lane,outgoing=lane,median=0,spacing=18) for _,_,a,b in e.segments(road)]);e.rebuild(road,scene,True)
for obj in bpy.context.selected_objects:obj.select_set(False)
road.select_set(True);bpy.context.view_layer.objects.active=road
for p in ps.points(road):p.select=False
ps.points(road)[0].select=True;bpy.ops.object.mode_set(mode='EDIT')
_,targets,junction=e.selection_targets(bpy.context);assert len(targets)==1 and not junction
# A single interior handle keeps both incident lane profiles accessible.
ps.points(road)[0].select=False;ps.points(road)[1].select=True
_,targets,junction=e.selection_targets(bpy.context);assert len(targets)==2 and junction
context=SimpleNamespace(scene=scene,mode=bpy.context.mode,edit_object=road,active_object=road,window_manager=SimpleNamespace(invoke_props_dialog=lambda *a,**k:{'RUNNING_MODAL'}),screen=None)
op=SimpleNamespace(approach='0',preview_status='');e.ROADLAB_OT_lane_window.invoke(op,context,None)
d=scene.roadlab_lane_draft;d.road_width=12;d.edge_left=1.25;d.edge_right=.2
original=ps.records(road);mesh=road['roadlab_core_mesh'].data;objects=set(bpy.data.objects)
e.tick_lane_preview();assert 'Live preview' in op.preview_status,op.preview_status
assert e._lane_preview.get('geometry_draft')
assert ps.records(road)==original and road['roadlab_core_mesh'].data==mesh
proxy=e._lane_preview['proxy'];draft_rows=ps.records(proxy)
assert draft_rows[1]['width']==12 and 'width' not in draft_rows[0]
assert draft_rows[1]['edge_left']==1.25 and abs(draft_rows[1]['edge_right']-.2)<1e-6
# Cancel releases everything and leaves the original scene unchanged.
e.ROADLAB_OT_lane_window.cancel(op,context);assert set(bpy.data.objects)==objects
assert ps.records(road)==original
# Apply commits the same point-scoped width and gaps, and keeps the editor usable.
e.set_draft(bpy.context,road,targets[:1]);d.road_width=12;d.edge_left=1.25;d.edge_right=.2
assert bpy.ops.roadlab.lane_apply()=={'FINISHED'}
rows=ps.records(road);assert rows[1]['width']==12 and 'width' not in rows[0] and 'width' not in rows[2]
assert not road.get('roadlab_core_error'),road.get('roadlab_core_error')
plans=json.loads(road['roadlab_generated_marking_catalog']);samples=0
for m in plans:
 if m['role'][0]!='outer':continue
 for p in m['path']:
  if not -100<p[0]<-75:continue
  # Both lines vary their own gap; neither uses the other side's value.
  t=(p[0]+120)/60;expected=(.5+(1.25-.5)*t) if p[1]>0 else (.5+(.2-.5)*t)
  q=__import__('mathutils').Vector(p)
  distances=[]
  for a,b in road_edges.boundary(road):
   a=__import__('mathutils').Vector(a);b=__import__('mathutils').Vector(b);v=b-a;t0=max(0,min(1,(q-a).dot(v)/max(v.length_squared,1e-9)));distances.append((q-a-v*t0).length)
  assert abs(min(distances)-expected)<.045,(p,min(distances),expected)
  samples+=1
assert samples>20
# A lane-count edit must ask before widening an unselected narrow endpoint.
d.incoming.add().width=3.5
request=SimpleNamespace(is_junction=False,connection_node='',expansion_batch='[]')
saved=road['roadlab_lanes'];e.apply_window_edits(request,bpy.context)
assert request.apply_status=='Review road expansion below.' and road['roadlab_lanes']==saved
assert json.loads(request.expansion_text)[0][1:]==[8.,11.5]
d.incoming.remove(len(d.incoming)-1)
bpy.ops.object.mode_set(mode='OBJECT')
with tempfile.TemporaryDirectory() as temp:
 name=road.name;bpy.ops.wm.save_as_mainfile(filepath=str(Path(temp)/'points.blend'));bpy.ops.wm.open_mainfile(filepath=str(Path(temp)/'points.blend'));road=bpy.data.objects[name]
 assert ps.records(road)[1]['edge_left']==1.25
# A one-sided turn pocket must not bend the opposite curb/line or yellow center.
rows=ps.records(road)
for row in rows:
 for field in ('width','edge_left','edge_right'):row.pop(field,None)
ps.save(road,rows);road['roadlab_lane_pockets']='[]';road_core.rebuild(road,True)
choice=dict(spline=0,anchors=[rows[2]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=-1)
candidate,pocket,_=lane_add.proposal(road,choice,-1,3.5,24,15);lane_add.ensure_baseline(road,pocket,'RIGHT');road['roadlab_lane_pockets']=json.dumps(candidate)
road_core.rebuild(road,True);e.rebuild(road,bpy.context.scene,True)
for mark in json.loads(road['roadlab_generated_marking_catalog']):
 if mark['center'][0]>=-12:continue
 if mark['role'][0]=='center-yellow':assert all(abs(p[1])<1e-5 for p in mark.get('path',[mark['center']]))
 if mark['role'][0]=='outer' and mark['center'][1]>0:assert all(abs(p[1]-3.5)<1e-5 for p in mark['path'])
assert not road.get('roadlab_core_error')
# Endpoint extensions inherit both independent edge gaps.
rows=ps.records(road);rows[3]['edge_left']=.85;rows[3]['edge_right']=.35;ps.save(road,rows)
spline=road.data.splines[0];spline.points.add(1);spline.points[-1].co=(160,0,.02,1)
road_core.rebuild(road,True);e.rebuild(road,bpy.context.scene,True)
new=ps.records(road)[4];assert abs(new['edge_left']-.85)<1e-6 and abs(new['edge_right']-.35)<1e-6
print('POINT_LANE_EDGES_PASS',flush=True)
