"""Terrain strokes pin concrete footprints in live and final terrain meshes."""
import bpy,sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import core_terrain,road_heightfield as field
from RoadLab.sculpt_preview import HeightPreview
scene=bpy.context.scene;terrain=scene.wb_native.terrain;road=scene.wb_native.road
core_terrain.rebuild(scene,True);helper=terrain['roadlab_core_terrain_mesh'];state=core_terrain._STATE[terrain.as_pointer()]
road_before=[tuple(v.co) for v in road['roadlab_core_mesh'].data.vertices]
# Use a straight section away from crosswalks and junctions, right sidewalk x=4.32..7.52.
center=(7.,32.);values={}
for _ in range(12):values=field.stamp(values,center,10,5,.1,'RAISE',lambda x,y:0.)
preview=HeightPreview(terrain,helper,values={},weights=state['sculpt_weights'],contact_mask=state['contact_mask'])
preview.ensure_detail(center,10);preview.values.update(values);preview.update(center,10,all_vertices=True)
protected=[v.co.z for v in preview.mesh.vertices if 4.5<v.co.x<7.3 and 28<v.co.y<36]
assert protected and max(protected)<.17,(len(protected),max(protected,default=-1))
assert max(v.co.z for v in preview.mesh.vertices if 9<v.co.x<13 and 29<v.co.y<35)>.1
preview.close()
terrain['roadlab_terrain_field']=field.encode(values);core_terrain.rebuild(scene,True)
protected=[v.co.z for v in helper.data.vertices if 4.5<v.co.x<7.3 and 28<v.co.y<36]
assert protected and max(protected)<.17,max(protected,default=-1)
# Inspect interpolated terrain faces too: safe vertices alone can hide bleed.
tree=BVHTree.FromPolygons([v.co for v in helper.data.vertices],[tuple(f.vertices) for f in helper.data.polygons])
for x in (4.5,5.,6.,7.,7.3):
 for y in (29.,30.,31.,32.,33.,34.,35.):
  hit=tree.ray_cast(Vector((x,y,20)),Vector((0,0,-1)),40)[0]
  assert hit is not None and hit.z<.17,(x,y,hit)

assert road_before==[tuple(v.co) for v in road['roadlab_core_mesh'].data.vertices], 'Terrain brush changed the road'
assert all(len(p.vertices)==4 for p in helper.data.polygons)
# Lowering near a sidewalk must not excavate its supporting terrain either.
terrain['roadlab_terrain_field']=field.encode({k:-v for k,v in values.items()});core_terrain.rebuild(scene,True)
protected=[v.co.z for v in helper.data.vertices if 4.5<v.co.x<7.3 and 28<v.co.y<36]
assert min(protected)>-.01
print('TERRAIN_SIDEWALK_MASK_PASS',flush=True)
