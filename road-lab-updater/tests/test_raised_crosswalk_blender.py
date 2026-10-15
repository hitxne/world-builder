"""Raised junctions keep crossing ramps and tactile pads above graded terrain."""
import bpy,sys,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import road_core,core_terrain,lane_editor
scene=bpy.context.scene;road=scene.wb_native.road;terrain=scene.wb_native.terrain
configs=lane_editor.state(road);configs[2]['crosswalk_a']=3;road['roadlab_lanes']=json.dumps(configs)
for height in (.52,2.02,-.98):
 for spline in road.data.splines:spline.points[1].co.z=height
 road_core.rebuild(road,True);core_terrain.rebuild(scene,True);lane_editor.rebuild(road,scene,True)
 helper=terrain['roadlab_core_terrain_mesh'];tree=BVHTree.FromPolygons([v.co for v in helper.data.vertices],[tuple(p.vertices) for p in helper.data.polygons])
 target=road['roadlab_marking_object'];pad_slots={i for i,m in enumerate(target.data.materials) if 'tactile_pad' in m.name};checked=0
 for face in target.data.polygons:
  if face.material_index not in pad_slots:continue
  for i in face.vertices:
   v=target.data.vertices[i].co;hit=tree.ray_cast(Vector((v.x,v.y,100)),Vector((0,0,-1)),200)[0]
   if hit is not None:
    assert v.z>hit.z+.0001,(height,tuple(v),tuple(hit));checked+=1
 assert checked>0
 assert not road_core._busy,'Update guard was not restored'
 assert not road.get('roadlab_core_error')
print('RAISED_CROSSWALK_PASS',flush=True)
