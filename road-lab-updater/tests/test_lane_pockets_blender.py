import bpy,sys,json,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_add,point_settings as ps,lane_editor,lane_pockets
scene=bpy.context.scene;data=bpy.data.curves.new('Pocket test','CURVE');data.dimensions='3D'
for coords in [[(x,0,.02) for x in (0,30,60,90,120)],[(120,-60,.02),(120,0,.02),(120,60,.02)]]:
 s=data.splines.new('POLY');s.points.add(len(coords)-1)
 for p,co in zip(s.points,coords):p.co=(*co,1)
obj=bpy.data.objects.new('Pocket test',data);scene.collection.objects.link(obj);scene.wb_native.road=obj;road_core.attach(obj)
from RoadLab.native_extension import set_input
set_input(road_core.modifier(obj),'road width',8);road_core.rebuild(obj,True)
rows=ps.records(obj);original=[tuple(p.co) for p in ps.points(obj)]
choice=dict(spline=0,anchors=[rows[2]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=False)
result,pocket,extended=lane_add.proposal(obj,choice,-1,3.5,12,15);lane_add.ensure_baseline(obj,pocket,'RIGHT');obj['roadlab_lane_pockets']=json.dumps(result);road_core.rebuild(obj,True);lane_editor.rebuild(obj,scene,True)
plans=json.loads(obj['roadlab_generated_marking_catalog']);print('PLANS',len(plans),obj.get('roadlab_marking_warnings'),flush=True)
assert any(m['role'][0]=='pocket-divider' for m in plans)
assert any(m.get('path') and min(p[1] for p in m['path'])<-6.9 for m in plans if m['role'][0]=='outer')
choice['anchors']=[rows[3]['id']];result,pocket,extended=lane_add.proposal(obj,choice,-1,4.,12,15)
assert extended and len(result)==1 and len(pocket['anchors'])==2 and pocket['width']==3.5
old_spec=lane_pockets.locate([tuple(p.co[:3]) for p in obj.data.splines[0].points],[r['id'] for r in rows[:5]],json.loads(obj['roadlab_lane_pockets'])[0])
new_spec=lane_pockets.locate([tuple(p.co[:3]) for p in obj.data.splines[0].points],[r['id'] for r in rows[:5]],pocket)
assert old_spec['start']==new_spec['start']
# Median-side left turn at the end of the same source street.
choice=dict(spline=0,anchors=[rows[4]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=-1)
result,pocket,extended=lane_add.proposal(obj,choice,1,3.5,24,15);lane_add.validate_turn(obj,pocket,'RIGHT');lane_add.ensure_baseline(obj,pocket,'RIGHT');obj['roadlab_lane_pockets']=json.dumps(result);road_core.rebuild(obj,True);lane_editor.rebuild(obj,scene,True)
plans=json.loads(obj['roadlab_generated_marking_catalog']);print('TURN',len(plans),obj.get('roadlab_marking_warnings'),flush=True)
assert any(m['role'][0]=='pocket-arrow' and m['asset']=='arrow_left' for m in plans)
assert any(m.get('path') and max(p[1] for p in m['path'])>3.4 for m in plans if m['role'][0]=='center-yellow')
assert [tuple(p.co) for p in ps.points(obj)]==original
print('POCKET_MARKINGS_PASS')

# RHD/LHD turn sides come from the map setting, never per-street handedness.
for handedness,side,movement in [('RIGHT',-1,'RIGHT'),('LEFT',1,'LEFT'),('LEFT',-1,'RIGHT')]:
 scene.roadlab_map_settings.traffic_side=handedness
 obj['roadlab_lane_pockets']='[]'
 choice=dict(spline=0,anchors=[rows[4]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=-1)
 result,pocket,_=lane_add.proposal(obj,choice,side,3.5,24,15)
 lane_add.validate_turn(obj,pocket,handedness);lane_add.ensure_baseline(obj,pocket,handedness)
 obj['roadlab_lane_pockets']=json.dumps(result);road_core.rebuild(obj,True);lane_editor.rebuild(obj,scene,True)
 plans=json.loads(obj['roadlab_generated_marking_catalog'])
 assert any(m['role'][0]=='pocket-arrow' and m['asset']=='arrow_'+movement.lower() for m in plans),(handedness,side)
# A second dedicated turn must not collapse into one receiving lane.
config=next(c for c in lane_editor.state(obj) if frozenset(c['endpoints'])==frozenset((rows[3]['id'],rows[4]['id'])))
configs=lane_editor.state(obj)
for c in configs:
 if c['endpoints']==config['endpoints']:c['incoming'][0]['movement']='RIGHT'
obj['roadlab_lanes']=json.dumps(configs);scene.roadlab_map_settings.traffic_side='RIGHT';obj['roadlab_lane_pockets']='[]'
result,pocket,_=lane_add.proposal(obj,choice,-1,3.5,24,15)
try:lane_add.validate_turn(obj,pocket,'RIGHT')
except ValueError as error:assert 'receiving' in str(error)
else:raise AssertionError('Two turn lanes must require two receiving lanes')
print('POCKET_DRIVING_SIDE_AND_CAPACITY_PASS')
