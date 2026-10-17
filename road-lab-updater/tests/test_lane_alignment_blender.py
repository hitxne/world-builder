"""Through lanes stay on their carriageway; independent ports align median paint."""
import bpy,sys,json,tempfile,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import lane_add,road_core,point_settings as ps,lane_editor,lane_pockets,approach_alignment as align
from RoadLab.native_extension import set_input
scene=bpy.context.scene;data=bpy.data.curves.new('Alignment test','CURVE');data.dimensions='3D'
for path in [[(-160,0,.02),(0,0,.02),(160,0,.02)],[(0,-160,.02),(0,0,.02),(0,160,.02)]]:
 s=data.splines.new('POLY');s.points.add(2)
 for p,co in zip(s.points,path):p.co=(*co,1)
road=bpy.data.objects.new('Alignment test',data);scene.collection.objects.link(road);scene.wb_native.road=road
road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
rows=ps.records(road);before=[tuple(p.co) for p in ps.points(road)]
for traffic in ('RIGHT','LEFT'):
 scene.roadlab_map_settings.traffic_side=traffic
 for direction in (-1,1):
  for side in (-1,1):
   road['roadlab_lane_pockets']='[]';road['roadlab_lanes']='[]';road_core.rebuild(road,True)
   choice=dict(spline=0,anchors=[rows[1]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=direction)
   candidate,primary,_=lane_add.proposal(road,choice,side,3.5,24,15)
   candidate,primary=lane_add.with_receiving_lane(road,candidate,primary,'THROUGH',50,traffic)
   partner=next(p for p in candidate if p.get('paired'))
   assert primary['receiving']==((-side*(1 if traffic=='RIGHT' else -1))==direction)
   assert partner['receiving']!=primary['receiving']
   for p in candidate:lane_add.ensure_baseline(road,p,traffic)
   road['roadlab_lane_pockets']=json.dumps(candidate);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
   plans=json.loads(road['roadlab_generated_marking_catalog'])
   medians=[p for p in plans if p['role'][0]=='center-yellow' and abs(p['center'][0])>15]
   assert len(medians)>=2 and all(abs(p['center'][1])<1e-4 for p in medians),(traffic,direction,side,medians)
   # The unaffected opposite carriageway edge stays on its old alignment.
   edge=-side*3.5
   unchanged=[p for p in plans if p['role'][0]=='outer' and abs(p['center'][0])>15 and abs(p['center'][1]-edge)<1e-4]
   assert len(unchanged)>=2,(traffic,direction,side,[(p['center'],p['role']) for p in plans if p['role'][0]=='outer'])
   print('THROUGH_ALIGNMENT_CASE_PASS',traffic,direction,side,flush=True)
# Lane-editor counts can differ without moving either median off the source axis.
scene.roadlab_map_settings.traffic_side='RIGHT';road['roadlab_lane_pockets']='[]';road['roadlab_lanes']='[]'
road_core.rebuild(road,True)
configs=[]
for i,j,a,b in lane_editor.segments(road):
 lane=lambda:dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')
 configs.append(dict(endpoints=[a,b],incoming=[lane()],outgoing=[lane()],median=0.,spacing=18.))
east=next(c for c in configs if c['endpoints']==[rows[1]['id'],rows[2]['id']]);east['incoming'].append(dict(width=3.5,movement='THROUGH',entry='CONTINUOUS'))
road['roadlab_lanes']=json.dumps(configs)
for row in rows:
 if row['id'] in east['endpoints']:row['width']=11.5
ps.save(road,rows);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
plans=json.loads(road['roadlab_generated_marking_catalog'])
assert all(abs(m['center'][1])<1e-4 for m in plans if m['role'][0]=='center-yellow' and abs(m['center'][0])>15)
ports=json.loads(road['roadlab_core_report'])['approach_ports']
assert not any(p['junction'][0]==0 and p['neighbor'][0]<0 for p in ports),'East profile displaced the west road'
mesh=road['roadlab_core_mesh'].data;tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(f.vertices) for f in mesh.polygons])
assert tree.ray_cast(Vector((100,-7.4,20)),Vector((0,0,-1)),40)[0] is not None
assert tree.ray_cast(Vector((100,5,20)),Vector((0,0,-1)),40)[0] is None
# Global traffic-side changes update both geometry and paint together.
scene.roadlab_map_settings.traffic_side='LEFT'
assert align.traffic_side(road)=='LEFT'
ports=json.loads(road['roadlab_core_report'])['approach_ports']
assert next(p['offset'] for p in ports if p['junction'][0]==0 and p['neighbor'][0]>0)>0
plans=json.loads(road['roadlab_generated_marking_catalog']);assert all(abs(m['center'][1])<1e-4 for m in plans if m['role'][0]=='center-yellow' and abs(m['center'][0])>15)
scene.roadlab_map_settings.traffic_side='RIGHT'
# A deliberate east offset changes only that port and its paint, not curve data.
pair=[rows[2]['id'],rows[1]['id']];draft=align.edited(road,pair,2)
original=road.get('roadlab_approach_offsets','[]');objects=set(bpy.data.objects);meshes=set(bpy.data.meshes)
preview=lane_add.preview_meshes(road,[],{'roadlab_approach_offsets':json.dumps(draft)})
assert preview and road.get('roadlab_approach_offsets','[]')==original
assert set(bpy.data.objects)==objects and set(bpy.data.meshes)==meshes,'Offset draft leaked helper data'
road['roadlab_approach_offsets']=json.dumps(draft);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
plans=json.loads(road['roadlab_generated_marking_catalog'])
west=[m for m in plans if m['role'][0]=='center-yellow' and m['center'][0]<-15];assert west and all(abs(m['center'][1])<1e-4 for m in west)
eastpaint=next(m for m in plans if m['role'][0]=='center-yellow' and m['center'][0]>15)
assert eastpaint.get('path') and 1.5<eastpaint['path'][0][1]<2.1 and abs(eastpaint['path'][-1][1])<.01,eastpaint
assert before==[tuple(p.co) for p in ps.points(road)]
with tempfile.TemporaryDirectory() as tmp:
 name=road.name;bpy.ops.wm.save_as_mainfile(filepath=str(Path(tmp)/'aligned.blend'));bpy.ops.wm.open_mainfile(filepath=str(Path(tmp)/'aligned.blend'));road=bpy.data.objects[name]
 assert align.settings(road)==draft and not road.get('roadlab_core_error')
road['roadlab_approach_offsets']='[]';road_core.rebuild(road,True)
# A lane addition plus a manual shift must not move its curb line twice.
scene=bpy.context.scene;scene.roadlab_map_settings.traffic_side='RIGHT';road['roadlab_lane_pockets']='[]';road['roadlab_lanes']='[]'
rr=ps.records(road)
for r in rr:r['width']=8
ps.save(road,rr);road_core.rebuild(road,True)
choice=dict(spline=0,anchors=[rr[1]['id']],axis=[rr[0]['id'],rr[1]['id']],junction=True,junction_direction=1)
candidate,primary,_=lane_add.proposal(road,choice,-1,3.5,24,15);candidate,primary=lane_add.with_receiving_lane(road,candidate,primary,'THROUGH',50,'RIGHT')
for part in candidate:lane_add.ensure_baseline(road,part,'RIGHT')
road['roadlab_lane_pockets']=json.dumps(candidate);road['roadlab_approach_offsets']=json.dumps(align.edited(road,[rr[2]['id'],rr[1]['id']],2))
road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
from RoadLab.surface_network import perimeter
mesh=road['roadlab_core_mesh'].data;vv=[v.co.copy() for v in mesh.vertices];segments=[]
for loop in perimeter(vv,[tuple(f.vertices) for f in mesh.polygons]):
 for a,b in zip(loop,loop[1:]+loop[:1]):segments.append((vv[a],vv[b]))
def distance(p,a,b):
 d=b-a;d.z=0;q=Vector(p);q.z=0;a=Vector((a.x,a.y,0));t=max(0.,min(1.,(q-a).dot(d)/max(d.length_squared,1e-9)));return (q-a-d*t).length
checked=0
for mark in json.loads(road['roadlab_generated_marking_catalog']):
 if mark['role'][0]!='outer' or not mark.get('path'):continue
 for p in mark['path']:
  if not 25<p[0]<90:continue
  gap=min(distance(p,a,b) for a,b in segments);assert .4<gap<.6,(p,gap);checked+=1
assert checked>0
# A minimum-width straight lane transition also needs a matching pavement taper.
cv=bpy.data.curves.new('Minimum lane transition','CURVE');cv.dimensions='3D';sp=cv.splines.new('POLY');sp.points.add(2)
for p,co in zip(sp.points,[(220,0,0,1),(260,0,0,1),(300,0,0,1)]):p.co=co
rd=bpy.data.objects.new('Minimum lane transition',cv);scene.collection.objects.link(rd);scene.wb_native.road=rd;road_core.attach(rd);set_input(road_core.modifier(rd),'road width',11.5);road_core.rebuild(rd,True)
rs=ps.records(rd);lane=lambda:dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')
rd['roadlab_lanes']=json.dumps([dict(endpoints=[rs[0]['id'],rs[1]['id']],incoming=[lane(),lane()],outgoing=[lane()],median=0.,spacing=18.),dict(endpoints=[rs[1]['id'],rs[2]['id']],incoming=[lane()],outgoing=[lane()],median=0.,spacing=18.)])
lane_editor.rebuild(rd,scene,True);mm=rd['roadlab_core_mesh'].data;tree=BVHTree.FromPolygons([v.co for v in mm.vertices],[tuple(f.vertices) for f in mm.polygons])
for mark in json.loads(rd['roadlab_generated_marking_catalog']):
 if not mark.get('path'):continue
 for p in mark['path']:
  assert tree.ray_cast(Vector((p[0],p[1],20)),Vector((0,0,-1)),40)[0] is not None,('Paint escaped transition pavement',mark['role'],p)

# Offset gates are shared exactly with ribbons at multi-road junctions too.
for count in (3,4,5,6):
 paths=[([(0,0,0),(60*math.cos(i*math.tau/count),60*math.sin(i*math.tau/count),0)],[1.,1.]) for i in range(count)]
 c=(0.,0.,0.);end=(60.,0.,0.)
 v,f,_,loops,report=road_core.build(paths,8,1,dict.fromkeys(('NW','NE','SW','SE'),4),port_offsets={c:{end:2.}})
 assert v and f and loops and report['junction_area_error_m2']<1e-4
print('LANE_ALIGNMENT_PASS',flush=True)
