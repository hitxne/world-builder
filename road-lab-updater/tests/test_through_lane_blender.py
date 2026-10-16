"""A through-lane addition receives its own lane across the junction and merges later."""
import bpy,sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import lane_add,road_core,point_settings as ps,lane_editor,lane_pockets
from RoadLab.native_extension import set_input
scene=bpy.context.scene
for separate in (False,True):
 data=bpy.data.curves.new('Through test','CURVE');data.dimensions='3D'
 paths=[[(-160,0,.02),(0,0,.02),(160,0,.02)],[(0,-160,.02),(0,0,.02),(0,160,.02)]]
 if separate:paths=[[(-160,0,.02),(0,0,.02)],[(160,0,.02),(0,0,.02)],paths[1]]
 for coords in paths:
  spline=data.splines.new('POLY');spline.points.add(len(coords)-1)
  for p,co in zip(spline.points,coords):p.co=(*co,1)
 obj=bpy.data.objects.new('Through test',data);scene.collection.objects.link(obj);scene.wb_native.road=obj;road_core.attach(obj);set_input(road_core.modifier(obj),'road width',8);road_core.rebuild(obj,True)
 rows=ps.records(obj);before=[tuple(p.co) for p in ps.points(obj)]
 choice=dict(spline=0,anchors=[rows[1]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=-1)
 for traffic_side,side in [('RIGHT',-1),('LEFT',1)]:
  scene.roadlab_map_settings.traffic_side=traffic_side;obj['roadlab_lane_pockets']='[]'
  candidate,pocket,_=lane_add.proposal(obj,choice,side,3.5,24,15)
  candidate,pocket=lane_add.with_receiving_lane(obj,candidate,pocket,'THROUGH',71.46,traffic_side)
  assert len(candidate)==2 and len({p['link_group'] for p in candidate})==1
  receiver=next(p for p in candidate if p.get('receiving'))
  assert lane_add.pocket_turn(obj,pocket,traffic_side)[0]=='THROUGH'
  lane_add.validate_turn(obj,pocket,traffic_side)
  for part in candidate:lane_add.ensure_baseline(obj,part,traffic_side)
  obj['roadlab_lane_pockets']=json.dumps(candidate);road_core.rebuild(obj,True);lane_editor.rebuild(obj,scene,True)
  plans=json.loads(obj['roadlab_generated_marking_catalog'])
  paint=obj['roadlab_marking_object'].data
  north_center=[p for p in paint.polygons if paint.materials[p.material_index].name.endswith('double_yellow') and p.center.y>20]
  assert north_center,'A shifted junction must not erase long markings on the adjacent street'
  assert any(m['role'][0]=='pocket-arrow' and m['asset']=='arrow_through' for m in plans),set(m['asset'] for m in plans)
  coords,ids=lane_add.source_for_pocket(obj,receiver);spec=lane_add.resolved_spec(obj,coords,ids,receiver)
  ss=lane_pockets.stations(coords);j=ss[ids.index(receiver['junction_anchor'])];direction=spec['junction_direction']
  assert abs(lane_pockets.amount(j+direction*10,spec)-3.5)<1e-6
  assert abs(lane_pockets.amount(j+direction*120,spec))<1e-6
  # Linked halves widen by one lane at the shared junction, not two.
  if not separate:
   specs=[lane_add.resolved_spec(obj,coords,ids,p) for p in candidate]
   assert abs(sum(lane_pockets.offsets(j,specs))-3.5)<1e-6
  assert before==[tuple(p.co) for p in ps.points(obj)]
  print('THROUGH_CASE_PASS',separate,traffic_side,len(obj['roadlab_core_mesh'].data.vertices),flush=True)
print('THROUGH_LANE_PASS')
# Exercise the registered operator, selection resolver, and paired removal.
scene.roadlab_map_settings.traffic_side='RIGHT';obj['roadlab_lane_pockets']='[]';road_core.rebuild(obj,True)
for other in bpy.context.view_layer.objects:other.select_set(False)
obj.select_set(True);bpy.context.view_layer.objects.active=obj
for p in ps.points(obj):p.select=abs(p.co.x)<1e-5 and abs(p.co.y)<1e-5
bpy.ops.object.mode_set(mode='EDIT')
_,options=lane_add.choices(bpy.context)
assert len(options)==4 and any('West' in c['label'] for c in options)
result=bpy.ops.roadlab.add_lane('EXEC_DEFAULT',road_name=obj.name,choices_json=json.dumps(options),approach='0',side='RIGHT',movement='THROUGH',width=3.5,length=24.,taper=15.,merge_taper=71.46)
assert result=={'FINISHED'},result
saved=json.loads(obj['roadlab_lane_pockets']);assert len(saved)==2
assert bpy.ops.roadlab.remove_lane_pocket(pocket_id=saved[0]['id'])=={'FINISHED'}
assert json.loads(obj['roadlab_lane_pockets'])==[]
bpy.ops.object.mode_set(mode='OBJECT')
print('THROUGH_OPERATOR_AND_REMOVE_PASS',flush=True)
