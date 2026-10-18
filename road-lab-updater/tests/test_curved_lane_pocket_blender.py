import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_add,point_settings as ps,lane_editor
from RoadLab.native_extension import set_input
scene=bpy.context.scene;data=bpy.data.curves.new('Curved pocket','CURVE');data.dimensions='3D';s=data.splines.new('POLY');s.points.add(3)
for p,co in zip(s.points,[(0,0,.02),(60,0,.02),(90,30,.02),(90,90,.02)]):p.co=(*co,1)
obj=bpy.data.objects.new('Curved pocket',data);scene.collection.objects.link(obj);scene.wb_native.road=obj;road_core.attach(obj);set_input(road_core.modifier(obj),'road width',8);road_core.rebuild(obj,True);rows=ps.records(obj)
choice=dict(spline=0,anchors=[rows[1]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=False)
candidate,pocket,_=lane_add.proposal(obj,choice,-1,3.5,12,15);lane_add.ensure_baseline(obj,pocket,'RIGHT');obj['roadlab_lane_pockets']=json.dumps(candidate);road_core.rebuild(obj,True);lane_editor.rebuild(obj,scene,True)
plans=json.loads(obj['roadlab_generated_marking_catalog']);print('CURVED',len(plans),obj.get('roadlab_marking_warnings'),[m['role'] for m in plans if m['role'][0]=='pocket-bend-divider'],flush=True)
assert any(m['role'][0]=='pocket-bend-divider' for m in plans)
print('CURVED_POCKET_PASS')

from mathutils import Vector
from mathutils.bvhtree import BVHTree
mesh=obj['roadlab_core_mesh'].data;tree=BVHTree.FromPolygons([p.co for p in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
for mark in plans:
 if mark['role'][0]=='outer' and mark.get('path'):
  for p in mark['path']:
   assert tree.ray_cast(Vector((p[0],p[1],20)),Vector((0,0,-1)))[0] is not None,p
assert any(tuple(c['junction'])==tuple(round(v,6) for v in s.points[1].co[:3]) for c in json.loads(obj['roadlab_core_report'])['radius_limits'])

# A gentle handle inside a long turn pocket must not push its divider to the
# expanded curb. Its bend connector joins the two existing divider endpoints.
import math
cv=bpy.data.curves.new('Gentle turn pocket','CURVE');cv.dimensions='3D'
for coords in [[(-110,90,.02),(-110,0,.02),(-65,-1,.02),(0,0,.02),(120,0,.02)],[(0,-120,.02),(0,0,.02),(0,120,.02)]]:
 sp=cv.splines.new('POLY');sp.points.add(len(coords)-1)
 for p,co in zip(sp.points,coords):p.co=(*co,1)
rd=bpy.data.objects.new('Gentle turn pocket',cv);scene.collection.objects.link(rd);scene.wb_native.road=rd;road_core.attach(rd);set_input(road_core.modifier(rd),'road width',8);road_core.rebuild(rd,True)
rr=ps.records(rd);choice=dict(spline=0,anchors=[rr[3]['id']],axis=[rr[1]['id'],rr[2]['id']],junction=True,junction_direction=-1)
candidate,pocket,_=lane_add.proposal(rd,choice,-1,3.5,64,30);lane_add.ensure_baseline(rd,pocket,'RIGHT')
road_core.rebuild(rd,True);lane_editor.rebuild(rd,scene,True)
from RoadLab.surface_network import perimeter
original_points=[tuple(p.co) for p in ps.points(rd)]
def boundaries():
 mesh=rd['roadlab_core_mesh'].data;v=[p.co.copy() for p in mesh.vertices]
 return [(v[a],v[b]) for loop in perimeter(v,[tuple(f.vertices) for f in mesh.polygons]) for a,b in zip(loop,loop[1:]+loop[:1])]
def north(edges,x):
 hits=[a.y+(b.y-a.y)*(x-a.x)/(b.x-a.x) for a,b in edges if abs(b.x-a.x)>1e-6 and min(a.x,b.x)<=x<=max(a.x,b.x)]
 assert hits;return max(hits)
before=boundaries();before_marks=json.loads(rd['roadlab_generated_marking_catalog'])
rd['roadlab_lane_pockets']=json.dumps(candidate);road_core.rebuild(rd,True);lane_editor.rebuild(rd,scene,True)
marks=json.loads(rd['roadlab_generated_marking_catalog']);joins=[p for m in marks if m['role'][0]=='pocket-divider' for p in (m['path'][0],m['path'][-1])]
curves=[m for m in marks if m['role'][0]=='pocket-bend-divider'];assert len(curves)==1
for mark in curves:
 for p in mark['path']:assert -4.6<p[1]<-4.3,('Divider jumped outwards at a road handle',p)
 for p in (mark['path'][0],mark['path'][-1]):assert min(math.dist(p,q) for q in joins)<1e-5,('Divider seam disconnected',p)
assert not json.loads(rd['roadlab_marking_warnings'])
assert original_points==[tuple(p.co) for p in ps.points(rd)]
report=json.loads(rd['roadlab_core_report']);assert report['perimeter_loops']==1,report['perimeter_loops']
after=boundaries()
for x in (-99.,-90.,-80.,-70.,-65.,-60.,-50.,-40.,-30.,-20.):assert abs(north(before,x)-north(after,x))<.002,('Westbound curb moved',x,north(before,x),north(after,x))
def paint_y(catalog,x,family):
 hits=[]
 for mark in catalog:
  role=mark['role']
  if role[0]!=family and not (role[0]=='bend' and role[1]==family):continue
  path=mark.get('path')
  if not path:
   c=mark['center'];f=mark['forward'];h=mark['size'][1]/2;path=[[c[0]+f[0]*t,c[1]+f[1]*t,c[2]] for t in (-h,h)]
  for a,b in zip(path,path[1:]):
   if abs(b[0]-a[0])>1e-6 and min(a[0],b[0])-1e-5<=x<=max(a[0],b[0])+1e-5:hits.append(a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]))
 assert hits,(family,x)
 return max(hits)
for x in (-90.,-80.,-70.,-65.,-60.,-50.,-40.,-30.,-20.):
 for family in ('outer','center-yellow'):
  assert abs(paint_y(before_marks,x,family)-paint_y(marks,x,family))<.002,('Opposing paint moved',family,x,paint_y(before_marks,x,family),paint_y(marks,x,family))
print('GENTLE_TURN_DIVIDER_PASS',flush=True)
