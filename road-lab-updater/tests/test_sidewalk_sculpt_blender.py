"""Edge brushes carry pavement, curb and stable sidewalk joints together."""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,road_sculpt,road_heightfield as field
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion
from RoadLab.road_stroke_preview import RoadStrokePreview
scene=bpy.context.scene
cv=bpy.data.curves.new('Sidewalk edge brush','CURVE');cv.dimensions='3D';sp=cv.splines.new('POLY');sp.points.add(1)
for p,co in zip(sp.points,[(-25,0,.02,1),(25,0,.02,1)]):p.co=co
road=bpy.data.objects.new('Sidewalk edge brush',cv);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road)
set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
curb,_=add_extrusion(scene,road,'curb');walk,_=add_extrusion(scene,road,'sidewalk')
def geometry(obj,raw=False,precise=False):
 for mod in obj.modifiers:
  if mod.type=='NODES':set_input(mod,'Precise viewport cleanup',precise)
 for name in ('RoadLab Planar Slabs','RoadLab Surface Finish'):
  m=obj.modifiers.get(name)
  if m:m.show_viewport=not raw
 bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 try:
  top=[p for p in mesh.polygons if abs(p.normal.z)>.05 and all(abs(mesh.attributes['wb_profile_y'].data[i].value-.1524)<1e-4 for i in p.vertices)]
  assert top and all(p.normal.z>0 for p in top),('Folded sidewalk top',[(p.index,tuple(p.normal)) for p in top if p.normal.z<=0])
  return sorted(tuple(round(v.co[i],5) for i in range(3)) for v in mesh.vertices)
 finally:ev.to_mesh_clear()
def coverage(obj,raw,precise):
 geometry(obj,raw,precise);ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 try:return BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
 finally:ev.to_mesh_clear()
for width,side in ((8.,1),(8.6,-1)):
 road['roadlab_sculpt_field']='';set_input(road_core.modifier(road),'road width',width);road_core.rebuild(road,True)
 before=geometry(walk,True);original=road['roadlab_core_mesh'].data;outline=road['roadlab_core_outline'].data
 session=RoadStrokePreview(scene,road);center=(0,side*(width/2-.3))
 for _ in range(8):assert session.stamp(center,'RAISE',4,5,.1)
 expected=.02+field.sample(session.values,0,side*width/2)
 edge=[v.co.z for v in road['roadlab_core_mesh'].data.vertices if abs(v.co.x)<1e-5 and abs(v.co.y-side*width/2)<1e-5]
 assert edge and min(edge)>2 and max(abs(z-expected) for z in edge)<1e-5,('Live curb edge pinned below brush',edge,expected)
 live=geometry(walk,True)
 assert [p[:2] for p in before]==[p[:2] for p in live],'Sculpting moved slab joints in XY'
 assert max(p[2] for p in live)>2.15
 edge_y=side*width/2
 # Simplifying a cyclic border used to rotate its sampling origin, shifting
 # the sidewalk hill by a metre even though its footprint stayed fixed.
 # Bottom vertices are .2 m below the top; keep the matching top samples.
 for x,y,z in live:
  if not width/2+.32<side*y<width/2+2.53 or abs(x)>=8:continue
  expected=.1724+field.sample(session.values,x,edge_y)
  assert min(abs(z-expected),abs(z-(expected-.2)))<.002,('Sidewalk height shifted along road',x,y,z,expected)
 geometry(walk)
 rawtree=coverage(walk,True,False);render_tree=coverage(walk,False,True);checked=0
 for i in range(-24,25):
  for offset in (.65,1.2,2.):
   p=Vector((i*.37+.071,side*(width/2+offset),30));direction=Vector((0,0,-1))
   a=rawtree.ray_cast(p,direction)[0];b=render_tree.ray_cast(p,direction)[0]
   if a is not None:
    assert b is not None and abs(a.z-b.z)<.002,('Precise cleanup cut the sculpted sidewalk',tuple(p),a,b)
    checked+=1
 assert checked>100
 # The saved compiler and the stroke use the same boundary samples.
 values=dict(session.values);session.close(True);road_core.rebuild(road,True)
 final=geometry(walk,True);assert len(live)==len(final)
 assert max(abs(a-b) for p,q in zip(live,final) for a,b in zip(p,q))<1e-4,'Release changed sidewalk shape'
 geometry(walk)
 # Lower, flatten and smooth retain stable slab footprints as well.
 session=RoadStrokePreview(scene,road)
 for mode in ('LOWER','FLATTEN','SMOOTH'):
  assert session.stamp(center,mode,4,3,.1,1. if mode=='FLATTEN' else None)
  points=geometry(walk,True);assert [p[:2] for p in points]==[p[:2] for p in final]
 session.close(False);assert field.decode(road['roadlab_sculpt_field'])=={k:round(v,7) for k,v in values.items() if abs(v)>1e-7}
 assert road_sculpt.base_height(road,0,side*(width/2+3)) is None,'Brush halo extends too far beyond pavement'
 print('SIDEWALK_EDGE_SCULPT_PASS',width,side,flush=True)
print('SIDEWALK_SCULPT_PASS',flush=True)
# A completed edge stroke grades the ground beneath the sidewalk as well.
from RoadLab import core_terrain,terrain_sculpt
road['roadlab_sculpt_field']='';set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
mesh=bpy.data.meshes.new('Grading source');mesh.from_pydata([(-40,-30,0),(40,-30,0),(40,30,0),(-40,30,0)],[],[(0,1,2,3)])
terrain=bpy.data.objects.new('Grading source',mesh);scene.collection.objects.link(terrain);scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True;core_terrain.rebuild(scene,True)
session=RoadStrokePreview(scene,road)
for _ in range(10):assert session.stamp((0,3.7),'RAISE',8,3,.1)
live_ground=[tuple(v.co) for v in terrain['roadlab_core_terrain_mesh'].data.vertices]
session.close(True);assert terrain_sculpt.pending(terrain)['refine']
road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
walktree=coverage(walk,False,True);mesh=terrain['roadlab_core_terrain_mesh'].data
ground=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
checked=0
for i in range(-18,19):
 for y in (4.6,5.2,6.):
  p=Vector((i*.37+.071,y,30));a=walktree.ray_cast(p,Vector((0,0,-1)))[0];b=ground.ray_cast(p,Vector((0,0,-1)))[0]
  if a is not None:
   assert b is not None and b.z<=a.z+.002,('Terrain pierced sculpted sidewalk',a,b)
   checked+=1
assert checked>70
assert ground.ray_cast(Vector((.1,5.2,30)),Vector((0,0,-1)))[0].z>2.5,'Terrain stayed flat beneath raised sidewalk'
# Check underside support rather than merely avoiding top-surface penetration.
errors=[];live_errors=[]
for x,y,z in live_ground:
 if abs(x)>6 or not 4.6<y<6.4:continue
 expected=.02+field.sample(field.decode(road['roadlab_sculpt_field']),x,4)-.0476-.005
 live_errors.append(abs(z-expected))
 hit=ground.ray_cast(Vector((x,y,30)),Vector((0,0,-1)))[0]
 if hit is not None:errors.append(abs(hit.z-expected))
assert errors and max(errors)<.06,('Unsupported final sidewalk',max(errors,default=-1))
assert live_errors and max(live_errors)<.06,('Unsupported preview sidewalk',max(live_errors,default=-1))
assert all(len(p.vertices)==4 for p in mesh.polygons)
print('SIDEWALK_SCULPT_TERRAIN_PASS',{'final_support_error':max(errors),'live_support_error':max(live_errors)},flush=True)

# Raising authored curve points supports the full sidewalk, including its end.
# A wide setback also exercises contacts beyond the asphalt's blend radius.
from RoadLab import native_layers
from RoadLab.sidewalk_width import WidthDraft
road['roadlab_sculpt_field']=''
for p in road.data.splines[0].points:p.co.z=5.02
road_core.rebuild(road,True)
model=native_layers.model_for(road);layer=next(l for l in model.wb_layers if l.object==walk)
for obj in bpy.context.selected_objects:obj.select_set(False)
road.select_set(True);bpy.context.view_layer.objects.active=road
profile=WidthDraft(bpy.context,layer.uid);profile.update(width=5.,offset=10.);profile.accept()
core_terrain.rebuild(scene,True)
from RoadLab.terrain_contacts import ContactMask
contacts=ContactMask(scene,terrain,terrain.roadlab_core_blend)
mesh=terrain['roadlab_core_terrain_mesh'].data
ground=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons])
checks=0
for x,y in ((0.071,15.),(0.071,-15.),(24.,16.),(36.,.071)):
 weight,roof,support=contacts.contact(x,y)
 if weight>1e-8:continue
 hit=ground.ray_cast(Vector((x,y,30)),Vector((0,0,-1)))[0]
 assert hit is not None and abs(hit.z-(support-.005))<.06,('Raised curve sidewalk unsupported',x,y,hit,support)
 checks+=1
assert checks==4
print('RAISED_CURVE_SIDEWALK_SUPPORT_PASS',checks,flush=True)
