"""Native Blender assembly and grading from actual evaluated physical surfaces."""
import bpy,json,math,time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from . import network

def top_triangles(objects,include_bridges=False):
 positions=[];triangles=[]
 for obj in objects:
  metadata=json.loads(obj.get('wb_metadata','{}'))
  if obj.type!='MESH' or (not include_bridges and metadata.get('terrain_mode')!='grade'):continue
  mesh=obj.data;mesh.calc_loop_triangles();attr=mesh.attributes.get('wb_station');start=metadata.get('grade_from',-1e30);end=metadata.get('grade_to',1e30)
  for tri in mesh.loop_triangles:
   if tri.normal.z<=.02:continue
   if attr and not include_bridges:
    station=sum(attr.data[i].value for i in tri.vertices)/3
    if not start<=station<=end:continue
   coordinates=[obj.matrix_world @ mesh.vertices[i].co for i in tri.vertices]
   if abs((coordinates[1]-coordinates[0]).cross(coordinates[2]-coordinates[0]).z)<1e-10:continue
   offset=len(positions);positions.extend(coordinates);triangles.append((offset,offset+1,offset+2))
 return positions,triangles

def barycentric_z(p,a,b,c):
 denominator=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y)
 if abs(denominator)<1e-14:return (a.z+b.z+c.z)/3
 u=((b.y-c.y)*(p.x-c.x)+(c.x-b.x)*(p.y-c.y))/denominator;v=((c.y-a.y)*(p.x-c.x)+(a.x-c.x)*(p.y-c.y))/denominator
 return u*a.z+v*b.z+(1-u-v)*c.z

def source_sampler(config):
 source=config.get('source_mesh')
 if not source:
  amplitude=config.get('wave_amplitude',.9);base=config.get('base_height',-.2)
  return lambda x,y:base+amplitude*math.sin(x/24)*math.cos(y/29)+config.get('slope_x',0)*x+config.get('slope_y',0)*y
 vertices=[Vector(p) for p in source['vertices']];bvh=BVHTree.FromPolygons(vertices,source['triangles'],all_triangles=True)
 projected=BVHTree.FromPolygons([Vector((v.x,v.y,0)) for v in vertices],source['triangles'],all_triangles=True)
 def height(x,y):
  nearest,normal,index,distance=projected.find_nearest(Vector((x,y,0)))
  if nearest is not None and distance<1e-4:
   a,b,c=[vertices[k] for k in source['triangles'][index]]
   return barycentric_z(nearest,a,b,c)
  p,n,i,d=bvh.ray_cast(Vector((x,y,max(v.z for v in vertices)+10)),Vector((0,0,-1)),20000)
  if p is None:
   nearest,normal,index,distance=projected.find_nearest(Vector((x,y,0)))
   if nearest is not None and distance<1e-4:
    a,b,c=[vertices[k] for k in source['triangles'][index]]
    return barycentric_z(nearest,a,b,c)
   raise ValueError(f'Terrain baseline has no height at {x:.2f},{y:.2f}; shrink terrain bounds or supply a complete height field')
  return p.z
 return height

def grade_terrain(collection,graph,positions,triangles,create_spec,clearance_positions=None,clearance_triangles=None):
 config=graph['terrain']
 if not config['enabled']:return None,{'enabled':False}
 start=time.perf_counter();world=BVHTree.FromPolygons(positions,triangles,all_triangles=True)
 projected=BVHTree.FromPolygons([Vector((v.x,v.y,0)) for v in positions],triangles,all_triangles=True)
 xmin,xmax,ymin,ymax=config['bounds'];spacing=config['grid_spacing'];nx=math.ceil((xmax-xmin)/spacing);ny=math.ceil((ymax-ymin)/spacing);dx=(xmax-xmin)/nx;dy=(ymax-ymin)/ny;source=source_sampler(config);clearance=config.get('clearance',.025);blend=config['blend_distance'];verts=[];base_values=[];weights=[];inside_flags=[];targets=[];max_error=0;covered=0
 for iy in range(ny+1):
  y=ymin+dy*iy
  for ix in range(nx+1):
   x=xmin+dx*ix;base=source(x,y);p,n,index,distance=projected.find_nearest(Vector((x,y,0)))
   weight=0;target=base;inside=False
   if p is not None and distance<=blend:
    if distance<1e-6:
     hit,normal,i,dist=world.ray_cast(Vector((x,y,-10000)),Vector((0,0,1)),20000)
     if hit is not None:target=hit.z-clearance;weight=1;inside=True;covered+=1
    if not inside:
     a,b,c=[positions[k] for k in triangles[index]];target=barycentric_z(p,a,b,c)-clearance*max(0,1-distance/.3);weight=1-network.smooth(min(1,distance/blend))
     # A grid triangle can cross a pavement edge even when its vertex lies
     # outside. Keep a cell-diagonal collar below the surface to prevent
     # interpolated grass triangles protruding through asphalt.
     if distance<math.hypot(dx,dy):target=barycentric_z(p,a,b,c)-clearance;weight=1
   height=base+(target-base)*weight;verts.append((x,y,height));base_values.append(base);weights.append(weight);inside_flags.append(inside);targets.append(target)
   if inside:max_error=max(max_error,abs(height-target))
 # Relax competing nearest-surface targets outside the hard road footprints.
 # This removes Voronoi seams where a high ramp and a low road both influence
 # the landscape. Smooth only the grading target, so baseline brush edits remain
 # independent and regenerate deterministically.
 active=[]
 for iy in range(ny+1):
  for ix in range(nx+1):
   i=iy*(nx+1)+ix
   if weights[i]<=0 or weights[i]>=1:continue
   adjacent=[]
   for ox,oy in ((-1,0),(1,0),(0,-1),(0,1)):
    x,y=ix+ox,iy+oy
    if 0<=x<=nx and 0<=y<=ny:
     j=y*(nx+1)+x
     if weights[j]>0:adjacent.append(j)
   if adjacent:active.append((i,adjacent))
 for iteration in range(max(12,math.ceil(8/spacing)**2)):
  previous=list(targets)
  for i,adjacent in active:targets[i]=.35*previous[i]+.65*sum(previous[j] for j in adjacent)/len(adjacent)
 verts=[(p[0],p[1],base_values[i]+(targets[i]-base_values[i])*weights[i]) for i,p in enumerate(verts)]
 faces=[]
 for y in range(ny):
  for x in range(nx):
   a=y*(nx+1)+x;faces.extend([(a,a+1,a+nx+2),(a,a+nx+2,a+nx+1)])
 spec={'id':'network-terrain','category':'terrain','verts':verts,'faces':faces,'material':'grass','metadata':{'graded_from':'evaluated physical surfaces','source_mode':'mesh' if config.get('source_mesh') else 'procedural','intentional_open_surface':True}}
 from . import terrain_clearance
 safety_positions=clearance_positions if clearance_positions is not None else positions;safety_triangles=clearance_triangles if clearance_triangles is not None else triangles
 pavement_depth=max((r.get('structure',{}).get('deck_depth',.22) for r in graph['roads'] if r.get('terrain_mode')=='grade'),default=.22)
 required_clearance=pavement_depth+clearance
 signature=terrain_clearance.signature(safety_positions,safety_triangles,{**config,'clearance':required_clearance})
 snapshot=config.get('sculpted_surface')
 if snapshot and snapshot.get('signature')==signature:
  sample=source_sampler({'source_mesh':snapshot})
  verts=[(p[0],p[1],sample(p[0],p[1])) for p in verts]
 index=terrain_clearance.SurfaceIndex(safety_positions,safety_triangles)
 verts,ceilings,clearance_report=terrain_clearance.enforce(verts,faces,index,required_clearance)
 clearance_report['required_face_clearance_m']=required_clearance
 spec['verts']=verts
 obj=create_spec(collection,spec)
 obj['wb_clearance_signature']=signature
 for name,values,type in [('wb_original_height',base_values,'FLOAT'),('wb_grade_weight',weights,'FLOAT'),('wb_grade_target',targets,'FLOAT'),('wb_grade_ceiling',ceilings,'FLOAT'),('wb_covered_by_pavement',inside_flags,'BOOLEAN')]:
  attribute=obj.data.attributes.new(name,type,'POINT')
  for item,value in zip(attribute.data,values):item.value=value
 changed=sum(abs(p[2]-b)>1e-5 for p,b in zip(verts,base_values));cut=sum(max(0,b-p[2])*dx*dy for p,b in zip(verts,base_values));fill=sum(max(0,p[2]-b)*dx*dy for p,b in zip(verts,base_values));max_slope=0
 for y in range(ny+1):
  for x in range(nx+1):
   i=y*(nx+1)+x
   if x<nx and not inside_flags[i] and not inside_flags[i+1]:max_slope=max(max_slope,abs(verts[i][2]-verts[i+1][2])/dx)
   if y<ny and not inside_flags[i] and not inside_flags[i+nx+1]:max_slope=max(max_slope,abs(verts[i][2]-verts[i+nx+1][2])/dy)
 max_error=max((abs(p[2]-targets[i]) for i,p in enumerate(verts) if inside_flags[i]),default=0)
 report={'enabled':True,'vertices':len(verts),'modified_vertices':changed,'vertices_under_surfaces':covered,'max_under_surface_target_error_m':max_error,'approx_cut_m3':cut,'approx_fill_m3':fill,'max_exposed_grid_slope':max_slope,'grid_spacing_m':[dx,dy],'elapsed_seconds':time.perf_counter()-start,'grade_target_triangles':len(triangles),'face_clearance':clearance_report}
 return obj,report

def assemble(collection,graph,create_spec,delete_object):
 specs,warnings,context=network.build(graph);made={}
 for spec in specs:
  obj=create_spec(collection,spec);made[spec['id']]=obj
  if 'station' in spec:
   attr=obj.data.attributes.new('wb_station','FLOAT','POINT')
   for item,value in zip(attr.data,spec['station']):item.value=value
  if 'uv' in spec and obj.type=='MESH':
   layer=obj.data.uv_layers.active
   for loop in obj.data.loops:layer.data[loop.index].uv=spec['uv'][loop.vertex_index]
  if spec['category']=='guide':obj.hide_viewport=not graph['settings'].get('show_guides',False)
 bpy.context.view_layer.update()
 for spec in specs:
  if spec['category']!='cutter':continue
  cutter=made[spec['id']]
  for target_id in spec['metadata']['cut_targets']:
   target=made.get(target_id)
   if not target:continue
   modifier=target.modifiers.new('WB controlled opening','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter;bpy.context.view_layer.objects.active=target;target.select_set(True);bpy.ops.object.modifier_apply(modifier=modifier.name);target.select_set(False)
  delete_object(cutter);made.pop(spec['id'])
 bpy.context.view_layer.update()
 # Record grading targets AFTER physical openings/planter cuts, BEFORE bridge/road union.
 positions,triangles=top_triangles(list(made.values()))
 groups={}
 for obj in made.values():
  group=json.loads(obj.get('wb_metadata','{}')).get('union_group')
  if group:groups.setdefault(group,[]).append(obj)
 for group,objects in groups.items():
  main=objects[0];source_ids=[obj['wb_id'] for obj in objects]
  for branch in objects[1:]:
   modifier=main.modifiers.new('WB explicit network union','BOOLEAN');modifier.operation='UNION';modifier.solver='EXACT';modifier.object=branch;bpy.context.view_layer.objects.active=main;main.select_set(True);bpy.ops.object.modifier_apply(modifier=modifier.name);main.select_set(False);delete_object(branch)
  main['wb_union_sources']=json.dumps(source_ids);main['wb_network_component']=group
 terrain=None
 if graph['terrain'].get('backend')=='roadlab':
  from . import native_terrain_adapter
  terrain,report=native_terrain_adapter.assemble(collection,graph,list(collection.objects),create_spec)
 elif triangles:
  safety_positions,safety_triangles=top_triangles(list(collection.objects),include_bridges=True)
  terrain,report=grade_terrain(collection,graph,positions,triangles,create_spec,safety_positions,safety_triangles)
 else:report={'enabled':False,'reason':'No ground-grade target surfaces'}
 if report.get('max_exposed_grid_slope',0)>graph['validation']['max_terrain_slope']:warnings.append(f"Terrain: maximum exposed grid slope {report['max_exposed_grid_slope']:.1%} exceeds selected {graph['validation']['max_terrain_slope']:.1%}; increase grading blend distance")
 from . import bridge_blender
 bridge_blender.generate(collection,graph,terrain,create_spec)
 return specs,warnings,context,report
