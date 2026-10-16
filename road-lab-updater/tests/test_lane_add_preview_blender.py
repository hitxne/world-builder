import sys,bpy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import lane_add,point_settings as ps,road_core
obj=bpy.context.scene.wb_native.road;rows=ps.records(obj)
pocket=dict(id='test',anchors=[rows[0]['id']],axis=[rows[0]['id'],rows[1]['id']],side=-1,width=3.5,length=12.,taper=15.,junction=False)
before=(obj.get('roadlab_point_settings'),obj.get('roadlab_lane_pockets'),len(bpy.data.objects),len(bpy.data.meshes),len(bpy.data.curves),len(bpy.data.node_groups),len(bpy.data.collections))
meshes=lane_add.preview_meshes(obj,[pocket])
after=(obj.get('roadlab_point_settings'),obj.get('roadlab_lane_pockets'),len(bpy.data.objects),len(bpy.data.meshes),len(bpy.data.curves),len(bpy.data.node_groups),len(bpy.data.collections))
print('PREVIEW',[(len(v),len(f)) for v,f in meshes],before==after,before,after,flush=True)
assert before==after
assert len(meshes)==3 and all(len(v)>100 for v,f in meshes)
lane_add.ensure_baseline(obj,pocket,'RIGHT');obj['roadlab_lane_pockets']=json.dumps([pocket]);road_core.rebuild(obj,True)
print('COMMITTED',len(obj['roadlab_core_mesh'].data.vertices),flush=True)

bpy.context.view_layer.update()
# Evaluated preview is the same geometry that will be committed.
from RoadLab import crosswalk_ramps
for (vertices,faces),layer in zip(meshes[1:],crosswalk_ramps.layers(obj)):
 ev=layer.object.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
 try:
  actual=sorted(tuple(round(v,5) for v in layer.object.matrix_world@p.co) for p in m.vertices)
  expected=sorted(tuple(round(v,5) for v in p) for p in vertices)
  from mathutils.bvhtree import BVHTree
  from mathutils import Vector
  preview_tree=BVHTree.FromPolygons([Vector(p) for p in vertices],faces)
  actual_tree=BVHTree.FromPolygons([layer.object.matrix_world@p.co for p in m.vertices],[tuple(p.vertices) for p in m.polygons])
  error=max([preview_tree.find_nearest(Vector(p))[3] for p in actual]+[actual_tree.find_nearest(Vector(p))[3] for p in expected])
  print('PREVIEW_SURFACE_ERROR',layer.kind,error,flush=True)
  # Contact seam splitting changes Boolean tessellation; the surfaces must
  # still agree within one millimeter at road scale.
  assert error<.001,(layer.kind,error)
 finally:ev.to_mesh_clear()
# Exceptions must not leave temporary objects/groups in the scene.
before=(len(bpy.data.objects),len(bpy.data.meshes),len(bpy.data.curves),len(bpy.data.node_groups),len(bpy.data.collections))
original_build=road_core.build
try:
 def fail(*args,**kwargs):raise ValueError('Deliberate preview failure')
 road_core.build=fail
 try:lane_add.preview_meshes(obj,[pocket])
 except ValueError:pass
 else:raise AssertionError('Expected failure')
finally:road_core.build=original_build
assert before==(len(bpy.data.objects),len(bpy.data.meshes),len(bpy.data.curves),len(bpy.data.node_groups),len(bpy.data.collections))
print('LANE_PREVIEW_ISOLATION_PASS')
