"""Blender diagnostics, including topology counts and deterministic vertex hashing."""
import bpy,hashlib,json,time
from collections import Counter

def inspect_scene(scene):
 result={'runtime':bpy.app.version_string,'graph':json.loads(scene.wb_graph) if scene.wb_graph else None,'warnings':json.loads(scene.get('wb_validation','[]')),'objects':[],'mesh_digest':scene.get('wb_mesh_digest','')}
 col=bpy.data.collections.get('WB_GENERATED');start=time.perf_counter()
 if not col:return result
 deps=bpy.context.evaluated_depsgraph_get()
 for obj in col.objects:
  if obj.type!='MESH':continue
  evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();counts=Counter()
  for face in mesh.polygons:
   vs=list(face.vertices)
   for a,b in zip(vs,vs[1:]+vs[:1]):counts[tuple(sorted((a,b)))]+=1
  mesh.calc_loop_triangles();signed_volume=sum(mesh.vertices[t.vertices[0]].co.dot(mesh.vertices[t.vertices[1]].co.cross(mesh.vertices[t.vertices[2]].co))/6 for t in mesh.loop_triangles)
  result['objects'].append({'name':obj.name,'id':obj.get('wb_id'),'category':obj.get('wb_category'),'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'boundary_edges':sum(v==1 for v in counts.values()),'nonmanifold_edges':sum(v>2 for v in counts.values()),'signed_volume_m3':signed_volume,'zero_area_faces':sum(p.area<1e-10 for p in mesh.polygons),'uv_layers':len(mesh.uv_layers),'materials':[m.name for m in mesh.materials if m],'vertices_sha256':hashlib.sha256(json.dumps([list(v.co) for v in mesh.vertices]).encode()).hexdigest()})
  evaluated.to_mesh_clear()
 result['inspection_seconds']=time.perf_counter()-start;return result
