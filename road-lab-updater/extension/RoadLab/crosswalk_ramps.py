"""Crosswalk endpoints drive the existing native curb/sidewalk ramp field."""
import bpy,json,hashlib
from mathutils import Vector
from .native_extension import set_input

def source(road):return road.get('roadlab_preview_source') or road

def layers(road):
    from .native_layers import model_for
    model=model_for(source(road))
    return [layer for layer in model.wb_layers if layer.kind in ('curb','sidewalk') and layer.enabled and layer.object] if model else []

def bind(road,guide):
    for layer in layers(road):
        for mod in layer.object.modifiers:
            if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                if mod.node_group.get('wb_schema',0)<15:
                    from .native_extrusion import extrusion_group
                    mod.node_group=extrusion_group()
                set_input(mod,'Crosswalk areas',guide)
                set_input(mod,'Flatten curb at crossing',layer.kind=='curb')

def rebuild(road,scene,plans):
    verts=[];faces=[];weights=[];seen=set()
    # Junction surfaces need not follow the source segment's linear Z profile.
    # Use the finished road edge as the ramp datum, including each stripe end.
    helper=road.get('roadlab_core_mesh');boundary=[];tree=None
    if helper is not None:
        from mathutils.bvhtree import BVHTree
        from .surface_network import perimeter
        matrix=road.matrix_world.inverted()@helper.matrix_world
        points=[matrix@v.co for v in helper.data.vertices];polygons=[list(p.vertices) for p in helper.data.polygons]
        tree=BVHTree.FromPolygons(points,polygons)
        for loop in perimeter(points,polygons):
            boundary.extend((points[i],points[j]) for i,j in zip(loop,loop[1:]+loop[:1]))
    def road_height(co):
        if tree is not None:
            hits=[];origin=co.z+100
            for _ in range(32):
                hit=tree.ray_cast(Vector((co.x,co.y,origin)),Vector((0,0,-1)),200)[0]
                if hit is None:break
                hits.append(hit.z);origin=hit.z-.001
            if hits:return (co.x,co.y,min(hits,key=lambda z:abs(z-co.z)))
        nearest=None
        for a,b in boundary:
            delta=b.xy-a.xy;t=max(0.,min(1.,(co.xy-a.xy).dot(delta)/max(delta.length_squared,1e-12)))
            q=a+(b-a)*t;distance=(co.xy-q.xy).length_squared
            if nearest is None or distance<nearest[0]:nearest=(distance,q.z)
        return (co.x,co.y,nearest[1] if nearest else co.z)
    for mark in plans:
        if 'crosswalk_ends' not in mark:continue
        identity=(tuple(mark.get('source_endpoints',[])),mark['role'][1])
        if identity in seen:continue
        seen.add(identity);a,b=map(Vector,mark['crosswalk_ends']);tangent=(b-a).normalized();normal=Vector((tangent.y,-tangent.x,0))
        half=mark['size'][1]/2;run=mark.get('ramp_run',1.8);start=len(verts)
        for center,weight in ((a-tangent*run,0),(a,1),(b,1),(b+tangent*run,0)):
            for sign in (-1,1):verts.append(road_height(center+normal*(sign*half)));weights.append(weight)
        faces.extend((start+2*i,start+2*i+1,start+2*i+3,start+2*i+2) for i in range(3))
    guide=road.get('roadlab_crosswalk_guide')
    if guide is None and not faces:return
    signature=hashlib.sha256(json.dumps([verts,faces,weights,[list(row) for row in road.matrix_world]]).encode()).hexdigest()
    if guide is not None and guide.get('roadlab_crosswalk_signature')==signature:bind(road,guide);return
    mesh=bpy.data.meshes.new('RoadLab Crosswalk Ramp Areas');mesh.from_pydata(verts,[],faces);mesh.update()
    attr=mesh.attributes.new('roadlab_crossing_weight','FLOAT','POINT')
    attr.data.foreach_set('value',weights)
    if guide is None:
        guide=bpy.data.objects.new('RoadLab Crosswalk Ramp Areas',mesh);scene.collection.objects.link(guide);guide.hide_set(True);guide.hide_render=True;guide.hide_select=True;road['roadlab_crosswalk_guide']=guide
    else:
        old=guide.data;guide.data=mesh
        if old.users==0:bpy.data.meshes.remove(old)
    guide['roadlab_crosswalk_signature']=signature;guide.matrix_world=road.matrix_world.copy();bind(road,guide)

def cleanup(road):
    actual=source(road);bind(actual,actual.get('roadlab_crosswalk_guide'))
    guide=road.get('roadlab_crosswalk_guide')
    if guide is not None:
        mesh=guide.data;bpy.data.objects.remove(guide,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)

def surface_tree(road):
    from mathutils.bvhtree import BVHTree
    verts=[];faces=[];inverse=road.matrix_world.inverted()
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for layer in layers(road):
        evaluated=layer.object.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
        try:
            offset=len(verts);matrix=inverse@evaluated.matrix_world
            verts.extend(matrix@v.co for v in mesh.vertices);faces.extend(tuple(offset+i for i in p.vertices) for p in mesh.polygons)
        finally:evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts,faces) if faces else None
