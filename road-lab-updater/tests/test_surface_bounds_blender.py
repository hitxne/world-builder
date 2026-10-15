"""Editable bounds, surface presets, terrain following and road-edge trimming."""
import bpy,sys,math,tempfile
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import surface_bounds as bounds
from RoadLab.native_extension import set_input

def evaluated(obj):
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
 try:
  vertices=[v.co.copy() for v in m.vertices];faces=[tuple(p.vertices) for p in m.polygons];counts={}
  for f in faces:
   for a,b in zip(f,f[1:]+f[:1]):key=tuple(sorted((a,b)));counts[key]=counts.get(key,0)+1
  return vertices,faces,counts
 finally:ev.to_mesh_clear()
def tree(obj):
 v,f,_=evaluated(obj);return BVHTree.FromPolygons(v,f)
def hit(obj,x,y):return tree(obj).ray_cast(Vector((x,y,100)),Vector((0,0,-1)),200)[0]
try:bounds.validate_outline([(0,0,0),(5,5,0),(0,5,0),(5,0,0)]);raise AssertionError('Self-crossing outline accepted')
except ValueError:pass
# The source stays one small editing plane; generation handles rounded concave bounds.
for i,kind in enumerate(('SIDEWALK','ISLAND','MEDIAN','PARKING')):
 x=i*15;obj=bounds.create_surface(bpy.context,[(x,0,0),(x+7,0,0),(x+7,3,0),(x+4,3,0),(x+4,7,0),(x,7,0)],kind)
 v,f,counts=evaluated(obj);assert v and f and all(c==2 for c in counts.values()),(kind,len(v),len(f),sorted(set(counts.values())))
 assert len(obj.data.vertices)==6 and len(obj.data.polygons)==1
 expected=.1524 if kind in ('SIDEWALK','ISLAND','MEDIAN') else .015
 assert abs(max(p.z for p in v)-expected)<.002,(kind,max(p.z for p in v))
 obj.roadlab_surface.radius=0;oldmax=max(p.x for p in evaluated(obj)[0]);obj.data.vertices[1].co.x+=2;obj.data.update();assert max(p.x for p in evaluated(obj)[0])>oldmax+1.5
# A simple sloping terrain demonstrates height conformity and live terrain edits.
mesh=bpy.data.meshes.new('Sloping terrain');mesh.from_pydata([(-100,-100,-15),(100,-100,5),(100,100,15),(-100,100,-5)],[],[(0,1,2,3)]);mesh.update()
terrain=bpy.data.objects.new('Sloping terrain',mesh);bpy.context.scene.collection.objects.link(terrain);bpy.context.scene.wb_native.terrain=terrain
obj=bounds.create_surface(bpy.context,[(0,20,0),(8,20,0),(8,28,0),(0,28,0)],'SIDEWALK');p=hit(obj,4,24);assert p and abs(p.z-(.1*4+.05*24+.1524))<.002,tuple(p) if p else None
for vertex in terrain.data.vertices:vertex.co.z+=1
terrain.data.update();q=hit(obj,4,24);assert q and abs(q.z-p.z-1)<.002
obj.roadlab_surface.follow=False
for vertex in obj.data.vertices:vertex.co.z=5
obj.data.update();assert abs(hit(obj,4,24).z-5)<.002
# A hill inside a flat boundary needs interior geometry, not a bridging ngon.
hill_mesh=bpy.data.meshes.new('Interior hill');hill_mesh.from_pydata([(20,40,0),(40,40,0),(40,60,0),(20,60,0),(30,50,4)],[],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)]);hill_mesh.update()
hill=bpy.data.objects.new('Interior hill',hill_mesh);bpy.context.scene.collection.objects.link(hill);bpy.context.scene.wb_native.terrain=hill
hill_pad=bounds.create_surface(bpy.context,[(20,40,0),(40,40,0),(40,60,0),(20,60,0)],'PARKING');hill_pad.roadlab_surface.radius=0
hill_vertices,_,_=evaluated(hill_pad);assert len(hill_vertices)>50 and len(hill_pad.data.vertices)==4
assert abs(hit(hill_pad,30,50).z-4.015)<.01
# The alternative plane workflow opens the editable source directly.
assert bpy.ops.roadlab.surface_plane()=={'FINISHED'};assert bpy.context.mode=='EDIT_MESH';assert len(bpy.context.edit_object.data.vertices)==4
bpy.ops.object.mode_set(mode='OBJECT')
# Actual RoadLab network: pads trim against asphalt and the existing sidewalk.
bpy.ops.roadlab.load_example();road=bpy.context.scene.wb_native.road
obj=bounds.create_surface(bpy.context,[(2,18,.02),(12,18,.02),(12,28,.02),(2,28,.02)],'SIDEWALK');obj.roadlab_surface.radius=0
assert hit(obj,2.5,23) is None,'Pad left overlapping faces over asphalt'
assert hit(obj,5.,23) is None,'Pad left coplanar overlap with the existing sidewalk'
assert hit(obj,10.,23) is not None,'Pad outside the existing road edge disappeared'
obj.roadlab_surface.trim=False;assert hit(obj,2.5,23) is not None
obj.roadlab_surface.trim=True
# Native editing remains available after save/reopen.
path=str(Path(tempfile.gettempdir())/'roadlab_surface_bounds_test.blend');name=obj.name;identity=obj['roadlab_surface_id']
bpy.ops.wm.save_as_mainfile(filepath=path);bpy.ops.wm.open_mainfile(filepath=path)
obj=bpy.data.objects[name];assert obj['roadlab_surface_id']==identity;assert len(obj.data.vertices)==4 and obj.get('roadlab_surface_bounds');assert hit(obj,10.,23) is not None
assert not bpy.context.scene.wb_native.road.get('roadlab_core_error')
print('SURFACE_BOUNDS_PASS',flush=True)
