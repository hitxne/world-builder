"""Planar concrete reduces evaluated geometry while preserving ramps and grade."""
import bpy,sys,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import crosswalk_ramps as ramps,road_core,core_terrain,lane_editor
scene=bpy.context.scene;road=scene.wb_native.road;terrain=scene.wb_native.terrain
sidewalk=next(l.object for l in ramps.layers(road) if l.kind=='sidewalk');finish=sidewalk.modifiers['RoadLab Planar Slabs']
def mesh_info():
 ev=sidewalk.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 try:return len(mesh.vertices),BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons]),all(not p.use_smooth for p in mesh.polygons)
 finally:ev.to_mesh_clear()
finish.show_viewport=False;raw,rawtree,_=mesh_info();finish.show_viewport=True;simple,tree,flat=mesh_info()
# Adaptive cross-sections now avoid generating most of the old dense input.
# Keep an absolute final budget without requiring wasteful raw geometry.
assert simple<10000 and simple<raw*.5,(raw,simple)
assert flat,'Concrete profile edges must not shade as inflated smooth surfaces'
checked=0
for x in (4.2,4.6,5.2,6.2,7.):
 for y in (-30.,-15.,-12.,-10.,-8.,-7.):
  a=rawtree.ray_cast(Vector((x,y,20)),Vector((0,0,-1)),40)[0];b=tree.ray_cast(Vector((x,y,20)),Vector((0,0,-1)),40)[0]
  if a is not None and b is not None:assert abs(a.z-b.z)<.002,(tuple(a),tuple(b));checked+=1
assert checked>10
for height in (.02,2.02):
 for spline in road.data.splines:spline.points[1].co.z=height
 road_core.rebuild(road,True);core_terrain.rebuild(scene,True);lane_editor.rebuild(road,scene,True)
 helper=terrain['roadlab_core_terrain_mesh'];ground=BVHTree.FromPolygons([v.co for v in helper.data.vertices],[tuple(p.vertices) for p in helper.data.polygons]);surfaces=ramps.surface_tree(road)
 # Previously the curb toe was translated below the terrain at the crossing.
 for x in (4.005,4.015,4.035,4.07,4.15,4.3):
  for y in (-11.3,-11.8):
   p=Vector((x,y,20));top=surfaces.ray_cast(p,Vector((0,0,-1)),40)[0];base=ground.ray_cast(p,Vector((0,0,-1)),40)[0]
   assert top is not None
   if base is not None:assert top.z>=base.z-.001,(height,x,y,tuple(top),tuple(base))
print('SIDEWALK_SLABS_PASS',raw,simple,flush=True)
