import json,bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import bridge_supports

def generate(collection,graph,terrain,create_spec):
 if not graph.get('bridge_supports'):return []
 if terrain:
  evaluated=terrain.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
  try:
   mesh.calc_loop_triangles();points=[terrain.matrix_world@v.co for v in mesh.vertices];triangles=[tuple(t.vertices) for t in mesh.loop_triangles];bvh=BVHTree.FromPolygons(points,triangles,all_triangles=True)
  finally:evaluated.to_mesh_clear()
  # RoadLab cuts ground beneath road furniture. Legal median foundations
  # therefore sample the median surface, which remains a physical solid.
  if terrain.get('wb_terrain_backend')=='roadlab':
   for obj in (terrain.users_collection[0].objects if terrain.users_collection else []):
    if obj.type!='MESH' or obj.get('wb_category')!='median':continue
    obj.data.calc_loop_triangles();offset=len(points);points.extend(obj.matrix_world@v.co for v in obj.data.vertices)
    triangles.extend(tuple(offset+i for i in t.vertices) for t in obj.data.loop_triangles if t.normal.z>.1)
   bvh=BVHTree.FromPolygons(points,triangles,all_triangles=True)
  ceiling=max(v.z for v in points)+100
  def ground(x,y):
   hit=bvh.ray_cast(Vector((x,y,ceiling)),Vector((0,0,-1)),20000)[0]
   if hit is None:raise ValueError('Bridge support is outside terrain coverage')
   return hit.z
 else:
  from .network_blender import source_sampler
  ground=source_sampler(graph['terrain'])
 from . import network
 obstacles=network.build(graph)[0];made=[]
 for support in graph.get('bridge_supports',[]):
  placement=bridge_supports.check_placement(graph,support,obstacles)
  for spec in bridge_supports.build(graph,support,ground):
   spec['metadata']['placement']=placement
   obj=create_spec(collection,spec);made.append(obj)
   if spec['category']=='bridge-column':
    for face in obj.data.polygons:
     if len(face.vertices)==4:face.use_smooth=True
 return made

def refresh(scene,terrain,graph=None):
 from . import create_spec,object_fingerprint,delete_collection
 graph=json.loads(scene.wb_graph) if graph is None else graph;col=bpy.data.collections.get('WB_GENERATED')
 if not col:return
 for obj in col.objects:
  if obj.get('wb_category') in ('bridge-cap','bridge-column') and obj.get('wb_fingerprint') and obj['wb_fingerprint']!=object_fingerprint(obj):raise ValueError('Direct support mesh edit detected; keep a copy before applying controls')
 stage=bpy.data.collections.new('WB_SUPPORT_STAGE');scene.collection.children.link(stage)
 try:made=generate(stage,graph,terrain,create_spec)
 except Exception:delete_collection(stage);raise
 for obj in list(col.objects):
  if obj.get('wb_category') in ('bridge-cap','bridge-column'):
   data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
   if data.users==0:bpy.data.meshes.remove(data)
 for obj in made:
  col.objects.link(obj);stage.objects.unlink(obj);obj['wb_fingerprint']=object_fingerprint(obj)
 bpy.data.collections.remove(stage)
 scene.wb_graph=json.dumps(graph)
