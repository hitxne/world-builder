"""Blender F spline joins preserve point identities, profiles and existing paint."""
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,point_settings as ps,lane_editor as lanes
from RoadLab.native_extension import set_input
scene=bpy.context.scene
def make(paths):
 data=bpy.data.curves.new('Join regression','CURVE');data.dimensions='3D'
 for path in paths:
  s=data.splines.new('POLY');s.points.add(len(path)-1)
  for p,co in zip(s.points,path):p.co=(*co,1)
 road=bpy.data.objects.new('Join regression',data);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road)
 set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
 lane=lambda:[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
 road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=lane(),outgoing=lane(),median=0,spacing=18) for _,_,a,b in lanes.segments(road)])
 lanes.rebuild(road,scene,True)
 bpy.ops.object.select_all(action='DESELECT');road.select_set(True);bpy.context.view_layer.objects.active=road
 return road
# Same example layout. Extend west with Blender E, then F to north.
road=make([[(-55,0,.02),(0,0,.02),(55,0,.02)],[(0,-55,.02),(0,0,.02),(0,55,.02)]])
bpy.ops.object.mode_set(mode='EDIT')
for p in ps.points(road):p.select=False
road.data.splines[0].points[0].select=True
bpy.ops.curve.extrude();bpy.ops.transform.translate(value=(0,55,0));road_core.rebuild(road,True)
before=lanes.state(road);identities={r['id']:r['co'] for r in ps.records(road)};assert len(before)==5
for p in ps.points(road):p.select=False
for p in ps.points(road):
 if tuple(round(v,2) for v in p.co[:3]) in ((-55.,55.,.02),(0.,55.,.02)):p.select=True
assert bpy.ops.curve.make_segment()=={'FINISHED'}
road_core.rebuild(road,True);lanes.rebuild(road,scene,True)
after={r['id']:r['co'] for r in ps.records(road)}
assert after==identities,'F reordered authoring points and transferred saved IDs to other locations'
valid={frozenset((a,b)) for _,_,a,b in lanes.segments(road)}
assert all(frozenset(c['endpoints']) in valid for c in before),'F orphaned an existing lane assignment'
assert all(c in lanes.state(road) for c in before),'Existing saved lane settings changed'
assert len(lanes.state(road))==6,'Compatible joined section did not inherit lanes'
marks=json.loads(road['roadlab_generated_marking_catalog']);assert len([m for m in marks if m['role'][0]=='center-yellow'])>=5
# Closing an individual spline with F also preserves its existing assignments.
bpy.ops.object.mode_set(mode='OBJECT')
road=make([[(120,0,.02),(175,0,.02),(175,55,.02),(120,55,.02)]])
before=lanes.state(road);identities={r['id']:r['co'] for r in ps.records(road)}
bpy.ops.object.mode_set(mode='EDIT')
for p in ps.points(road):p.select=False
road.data.splines[0].points[0].select=True;road.data.splines[0].points[-1].select=True
assert bpy.ops.curve.make_segment()=={'FINISHED'}
road_core.rebuild(road,True);lanes.rebuild(road,scene,True)
assert {r['id']:r['co'] for r in ps.records(road)}==identities
assert all(c in lanes.state(road) for c in before)
assert len(lanes.state(road))==4,'Closing edge did not inherit matching profiles'
# Ordinary movement still keeps the selected point identity and custom settings.
records=ps.records(road);records[1]['corner_radius']=7;ps.save(road,records);ident=records[1]['id']
road.data.splines[0].points[1].co.x+=3;road_core.rebuild(road,True)
assert ps.records(road)[1]['id']==ident and ps.records(road)[1]['corner_radius']==7
bpy.ops.object.mode_set(mode='OBJECT')
print('LANE_JOIN_PASS',flush=True)
