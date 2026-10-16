"""Editable heightfield plane -> constrained road seam + smooth distance grading.
The source mesh is never overwritten. Display uses a derived helper mesh.
"""
import hashlib,json,math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import delaunay_2d_cdt
from .surface_network import area,perimeter

_STATE={}

def source_boundary(mesh):
    verts=[tuple(v.co) for v in mesh.vertices];faces=[list(p.vertices) for p in mesh.polygons]
    return verts,perimeter(verts,faces)

def surface(terrain,roads,blend,spacing,state=None):
    from . import terrain_quads as quad,road_heightfield,adaptive_terrain,terrain_sculpt
    raw=terrain.data;raw.calc_loop_triangles();base=[tuple(v.co) for v in raw.vertices]
    source_tree=BVHTree.FromPolygons(base,[tuple(t.vertices) for t in raw.loop_triangles],all_triangles=True)
    base_verts,outer=source_boundary(raw)
    if not outer:raise ValueError('Terrain needs an open upward-facing mesh plane')
    signs=[1 if area([base[i][:2] for i in loop])>0 else -1 for loop in outer]
    if not any(s>0 for s in signs):raise ValueError('Terrain faces must point upward')
    points=[Vector(p[:2]) for p in base];polygons=[list(loop) for loop in outer];source_count=len(polygons)
    inv=terrain.matrix_world.inverted();road_segments=[];road_refs=[];road_by_original={};helpers={}
    for road in roads:
        helper=road.get('roadlab_core_mesh')
        if helper is None:continue
        mesh=quad.base_mesh(helper);helpers[helper]=road
        verts=[tuple(inv@helper.matrix_world@v.co) for v in mesh.vertices]
        contact=mesh.attributes.get('roadlab_ground_contact')
        faces=[list(p.vertices) for p in mesh.polygons if contact is None or contact.data[p.index].value]
        gradients={}
        for face in faces:
            a,b,c=(Vector(verts[i]) for i in face[:3]);normal=(b-a).cross(c-a)
            g=Vector((-normal.x/normal.z,-normal.y/normal.z)) if abs(normal.z)>1e-8 else Vector((0,0))
            for u,v in zip(face,face[1:]+face[:1]):gradients[tuple(sorted((u,v)))]=g
        for loop in perimeter(verts,faces):
            poly=[]
            for j,i in enumerate(loop):
                other=loop[(j+1)%len(loop)];a,b=Vector(verts[i]),Vector(verts[other]);index=len(points)
                points.append(a.xy);poly.append(index);road_by_original[index]=tuple(a)
                road_segments.append((a,b,gradients[tuple(sorted((i,other)))]));road_refs.append((helper,i,other))
            polygons.append(poly);signs.append(1 if area([verts[i][:2] for i in loop])>0 else -1)
    # Planar source subdivision is intentionally free to simplify into quad cells.
    planar=False
    if raw.loop_triangles:
        first=raw.loop_triangles[0];a,b,c=(Vector(base[i]) for i in first.vertices);normal=(b-a).cross(c-a).normalized()
        planar=all(abs((Vector(p)-a).dot(normal))<1e-6 for p in base)
        if planar:
            keep=sorted({i for f in polygons for i in f});mapping={old:new for new,old in enumerate(keep)}
            points=[points[i] for i in keep];polygons=[[mapping[i] for i in f] for f in polygons];road_by_original={mapping[i]:p for i,p in road_by_original.items()}
    seed_count=len(points)
    tree=KDTree(len(road_segments))
    for i,(a,b,g) in enumerate(road_segments):tree.insert(Vector(((a.x+b.x)/2,(a.y+b.y)/2,0)),i)
    tree.balance()
    def nearest(p):
        if not road_segments:return (float('inf'),None,-1,0.,None)
        best=None
        for _,index,_ in tree.find_n(Vector((p.x,p.y,0)),min(16,len(road_segments))):
            a,b,g=road_segments[index];d=b.xy-a.xy;t=max(0.,min(1.,(p-a.xy).dot(d)/max(d.length_squared,1e-12)));q=a+(b-a)*t;dist=(p-q.xy).length
            if best is None or dist<best[0]:best=(dist,q.z+g.dot(p-q.xy),index,t,q)
        return best
    sculpt=road_heightfield.decode(terrain.get('roadlab_terrain_field',''));height_cache={}
    def height_at(x,y):
        key=(x,y)
        if key in height_cache:return height_cache[key]
        hit=source_tree.ray_cast(Vector((x,y,100000)),Vector((0,0,-1)))
        z=(hit[0].z if hit[0] is not None else 0.)+road_heightfield.sample(sculpt,x,y)
        dist,road_z,index,t,q=nearest(Vector((x,y)))
        if dist<blend:
            t=max(0.,min(1.,dist/max(blend,.1)));smooth=t*t*t*(t*(t*6-15)+10);z=road_z+(z-road_z)*smooth
        height_cache[key]=z;return z
    xmin=min(p[0] for p in base);xmax=max(p[0] for p in base);ymin=min(p[1] for p in base);ymax=max(p[1] for p in base)
    bounds=(xmin,ymin,xmax,ymax)
    features=[(min(a.x,b.x)-blend,min(a.y,b.y)-blend,max(a.x,b.x)+blend,max(a.y,b.y)+blend) for a,b,g in road_segments]+adaptive_terrain.feature_bounds(sculpt)
    if not planar:
        for tri in raw.loop_triangles:
            ps=[base[i] for i in tri.vertices];features.append((min(p[0] for p in ps),min(p[1] for p in ps),max(p[0] for p in ps),max(p[1] for p in ps)))
    topology_key=hashlib.sha256(json.dumps([7,[tuple(p) for p in points],polygons,signs,spacing,blend,terrain.roadlab_core_terrain_tolerance],sort_keys=True).encode()).hexdigest()
    reused=bool(state and state['topology_key']==topology_key);dirty=terrain_sculpt.pending(terrain)
    refine=not reused or bool(dirty and dirty['refine']);local=False;retained=0
    if refine:
        box=dirty['box'] if dirty else None;brush=(*box,dirty['radius']) if dirty and not dirty.get('coarsen') else None
        boxes=quad.cells(bounds,height_at,features,spacing,terrain.roadlab_core_terrain_tolerance,brush,state.get('cells') if reused else None,box,bool(dirty and dirty.get('coarsen')))
        if reused and boxes==state.get('cells'):
            flat=[tuple(p) for p in state['flat']];faces=[list(f) for f in state['faces']];origins=[list(x) for x in state['origins']];refine=False
        else:
            constraints=[f if sign>0 else list(reversed(f)) for f,sign in zip(polygons,signs)]
            edges=quad.add_cell_edges(points,boxes)
            cdt=delaunay_2d_cdt(points,edges,constraints,4,1e-6,True);flat=[tuple(p) for p in cdt[0]];origins=[list(x) for x in cdt[3]];faces=[]
            for f,owners in zip(cdt[2],cdt[5]):
                source=sum(signs[i] for i in owners if i<source_count);road=sum(signs[i] for i in owners if i>=source_count)
                if source>0 and road>1:raise ValueError('Ground-contact footprints overlap')
                if source>0 and road<=0:faces.append(list(f))
            faces=quad.consolidate_cells(flat,faces,boxes,bounds)
            flat,faces,origins=quad.weld_road_cuts(flat,faces,origins,road_by_original,spacing,lambda p:nearest(Vector(p))[0],seed_count)
            flat,faces,origins=quad.quadify(flat,faces,origins);local=reused
    else:
        boxes=state['cells'];flat=[tuple(p) for p in state['flat']];faces=[list(f) for f in state['faces']];origins=[list(x) for x in state['origins']]
    previous={tuple(round(x,7) for x in p[:2]):p for p in state['vertices']} if reused else {}
    vertices=[];pins={helper:{} for helper in helpers};seam=changed=resampled=0;seam_points=[];seam_pins={};candidate_used={i for f in faces for i in f}
    for i,xy in enumerate(flat):
        if i not in candidate_used:vertices.append((*xy,0.));continue
        p=Vector(xy);dist,road_z,index,t,q=nearest(p);authored=[road_by_original[j] for j in origins[i] if j in road_by_original]
        if authored and max(v[2] for v in authored)-min(v[2] for v in authored)>1e-4:raise ValueError('Ground-contact roads overlap at different heights')
        old=previous.get(tuple(round(x,7) for x in xy))
        if dist<1e-5:
            xy=tuple(q.xy);z=q.z;seam+=1;seam_points.append((road_refs[index][0],Vector((xy[0],xy[1],z))))
            helper,a,b=road_refs[index];edge=tuple(sorted((a,b)));factor=t if edge[0]==a else 1-t;seam_pins[i]=(helper,edge,factor)
        elif authored:z=sum(v[2] for v in authored)/len(authored);seam+=1
        elif old and dirty and not (dirty['box'][0]<=xy[0]<=dirty['box'][2] and dirty['box'][1]<=xy[1]<=dirty['box'][3]):z=old[2]
        else:z=height_at(*xy);resampled+=1
        vertices.append((*xy,z))
        if old is None or abs(z-old[2])>1e-7:changed+=1
    # Discard only numerically collapsed pieces. All surviving terrain faces are quads.
    faces=[f for f in faces if len(set(f))==4 and area([vertices[i][:2] for i in f])>1e-10]
    used=sorted({i for f in faces for i in f});mapping={i:j for j,i in enumerate(used)}
    meshverts=[vertices[i] for i in used];meshfaces=[[mapping[i] for i in f] for f in faces];meshorigins=[origins[i] for i in used]
    if reused:
        oldfaces={tuple(sorted(tuple(round(v,7) for v in state['vertices'][i][:2]) for i in f)) for f in state['faces']}
        retained=sum(tuple(sorted(tuple(round(v,7) for v in meshverts[i][:2]) for i in f)) in oldfaces for f in meshfaces)
    for i in used:
        if i in seam_pins:
            owner,edge,factor=seam_pins[i];pins[owner].setdefault(edge,set()).add(factor)
    splits=sum(quad.match_road_seams(helper,values) for helper,values in pins.items())
    if splits:
        from . import road_core
        for road in helpers.values():road_core.refresh_markings(road)
    seam_error=0.
    for helper in helpers:
        locations=[p for owner,p in seam_points if owner==helper]
        if not locations:continue
        seam_tree=KDTree(len(helper.data.vertices))
        for i,v in enumerate(helper.data.vertices):seam_tree.insert(inv@helper.matrix_world@v.co,i)
        seam_tree.balance();seam_error=max(seam_error,max(seam_tree.find(p)[2] for p in locations))
    report=dict(vertices=len(meshverts),faces=len(meshfaces),quads=len(meshfaces),triangles=0,ngons=0,seam_vertices=seam,maximum_seam_error=seam_error,topology_reused=reused and not refine,height_samples_changed=changed,height_samples_resampled=resampled,blend_distance=blend,spacing=spacing,adaptive=True,flat_polygons=0,local_remesh=local,faces_retriangulated=0,faces_retained=retained,quad_cells=len(boxes),shared_road_vertices_added=splits,uniform_grid_estimate=round((xmax-xmin)*(ymax-ymin)/spacing**2))
    terrain_sculpt.clear_pending(terrain)
    return meshverts,meshfaces,report,dict(topology_key=topology_key,flat=[v[:2] for v in meshverts],faces=meshfaces,origins=meshorigins,vertices=meshverts,cells=boxes)

def attach(terrain):
    group=bpy.data.node_groups.new('ROADLAB_TERRAIN_CONTACT','GeometryNodeTree');group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    collection=next((c for c in bpy.context.scene.collection.children if c.name.split('.')[0]=='RoadLab Core References'),None)
    if collection is None:collection=bpy.data.collections.new('RoadLab Core References');bpy.context.scene.collection.children.link(collection)
    helper=bpy.data.objects.new('RoadLab Graded Terrain Reference',bpy.data.meshes.new('RoadLab Graded Terrain'));collection.objects.link(helper);helper.hide_render=True;helper.hide_set(True);terrain['roadlab_core_terrain_mesh']=helper
    info=group.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=helper
    out=group.nodes.new('NodeGroupOutput');group.links.new(info.outputs['Geometry'],out.inputs['Geometry'])
    mod=terrain.modifiers.new('RoadLab Terrain Contact','NODES');mod.node_group=group


def rebuild(scene,force=False):
    terrain=scene.wb_native.terrain
    if not terrain:return
    for mod in terrain.modifiers:
        if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('ROADLAB_TERRAIN_CONTACT'):
            mod.show_viewport=terrain.roadlab_core_terrain_enabled;mod.show_render=terrain.roadlab_core_terrain_enabled
    if not terrain.roadlab_core_terrain_enabled:return
    if terrain.type!='MESH':raise ValueError('Choose an editable terrain mesh plane')
    if terrain.mode=='EDIT':terrain.update_from_editmode()
    roads=[o for o in scene.objects if o.type=='CURVE' and o.get('roadlab_new_core') and o.roadlab_core_ground_contact]
    roads=[r for r in roads if r.get('roadlab_core_mesh') and (r['roadlab_core_mesh'].data.attributes.get('roadlab_ground_contact') is None or any(v.value for v in r['roadlab_core_mesh'].data.attributes.get('roadlab_ground_contact').data))]
    if not roads and not json.loads(terrain.get('roadlab_terrain_field','') or '{}').get('heights') and terrain.data.polygons and all(len(p.vertices)==4 for p in terrain.data.polygons):
        for mod in terrain.modifiers:
            if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('ROADLAB_TERRAIN_CONTACT'):mod.show_viewport=False;mod.show_render=False
        terrain['roadlab_core_terrain_signature']='';terrain['roadlab_core_terrain_error']='';return
    helper=terrain.get('roadlab_core_terrain_mesh')
    others=[m for m in terrain.modifiers if not (m.type=='NODES' and m.node_group and m.node_group.name.startswith('ROADLAB_TERRAIN_CONTACT'))]
    if others:raise ValueError('New-core contact needs an unmodified heightfield plane; original terrain modifiers remain intact')
    from . import terrain_quads
    signature=hashlib.sha256(json.dumps([7,terrain.get('roadlab_terrain_field',''),terrain.roadlab_core_terrain_tolerance,[(tuple(v.co)) for v in terrain.data.vertices],[list(p.vertices) for p in terrain.data.polygons],[list(row) for row in terrain.matrix_world],[(o.name,o.get('roadlab_core_signature'),terrain_quads.base_mesh(o['roadlab_core_mesh']).as_pointer(),[list(row) for row in o.matrix_world]) for o in roads],terrain.roadlab_core_blend,terrain.roadlab_core_terrain_spacing],sort_keys=True).encode()).hexdigest()
    if not force and signature==terrain.get('roadlab_core_terrain_signature') and helper:
        terrain['roadlab_core_terrain_error']='';return
    verts,faces,report,state=surface(terrain,roads,terrain.roadlab_core_blend,terrain.roadlab_core_terrain_spacing,_STATE.get(terrain.as_pointer()))
    if helper is None:attach(terrain);helper=terrain['roadlab_core_terrain_mesh']
    if report['topology_reused'] and len(helper.data.vertices)==len(verts):
        mesh=helper.data
        for point,co in zip(mesh.vertices,verts):
            if (point.co-Vector(co)).length>1e-7:point.co=co
        mesh.update()
    else:
        mesh=bpy.data.meshes.new('RoadLab Graded Terrain');mesh.from_pydata(verts,[],faces);mesh.update()
    mesh.materials.clear()
    for mat in terrain.data.materials:mesh.materials.append(mat)
    mesh.polygons.foreach_set('use_smooth',[True]*len(mesh.polygons))
    uv=mesh.uv_layers.get('UVMap') or mesh.uv_layers.new(name='UVMap')
    # Batch writes avoid repeatedly resolving Blender's legacy UV collection.
    # Height-only updates keep the existing planar UV coordinates.
    if not report['topology_reused']:
        uv.data.foreach_set('uv',[c for loop in mesh.loops for c in verts[loop.vertex_index][:2]])
    old=helper.data;helper.data=mesh;helper.matrix_world=terrain.matrix_world.copy()
    if old!=mesh and old.users==0:bpy.data.meshes.remove(old)
    _STATE[terrain.as_pointer()]=state;terrain['roadlab_core_terrain_signature']=signature;terrain['roadlab_core_terrain_error']='';terrain['roadlab_core_terrain_report']=json.dumps(report);terrain.update_tag()
    from . import lane_editor
    for road in roads:
        if any(c.get('crosswalk_tactile') and (c.get('crosswalk_incoming') or c.get('crosswalk_outgoing')) for c in lane_editor.state(road)):
            from . import road_core
            road_core.refresh_markings(road)


def settings_changed(obj,context):
    obj.update_tag()


def register_properties():
    from bpy.props import BoolProperty,FloatProperty,EnumProperty
    bpy.types.Scene.roadlab_core_update_mode=EnumProperty(name='Mesh updates',items=[('AUTO','Auto','Live when measured edits are fast; defer heavier work until placement'),('PLACEMENT','After placement','Keep the current surface while positioning the curve'),('LIVE','Live','Rebuild during interactive edits; useful for small scenes')],default='AUTO')
    bpy.types.Object.roadlab_core_terrain_enabled=BoolProperty(name='Follow road surface',default=False,update=settings_changed)
    bpy.types.Object.roadlab_core_blend=FloatProperty(name='Blend distance (m)',default=12.,min=.5,max=200.,update=settings_changed)
    bpy.types.Object.roadlab_core_terrain_tolerance=FloatProperty(name='Height tolerance (m)',default=.02,min=.001,max=1.,update=settings_changed)
    bpy.types.Object.roadlab_core_terrain_spacing=FloatProperty(name='Detail spacing (m)',default=1.,min=.25,max=20.,update=settings_changed)
    bpy.types.Object.roadlab_core_ground_contact=BoolProperty(name='Grade terrain to this road',default=True,update=settings_changed)


def unregister_properties():
    _STATE.clear()
    if hasattr(bpy.types.Scene,'roadlab_core_update_mode'):del bpy.types.Scene.roadlab_core_update_mode
    for name in ('roadlab_core_terrain_enabled','roadlab_core_blend','roadlab_core_terrain_spacing','roadlab_core_ground_contact','roadlab_core_terrain_tolerance'):
        if hasattr(bpy.types.Object,name):delattr(bpy.types.Object,name)
