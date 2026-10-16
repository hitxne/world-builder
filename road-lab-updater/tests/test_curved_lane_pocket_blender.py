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
