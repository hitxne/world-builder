"""Adapter into the user's original TrackTools terrain node groups."""
import bpy,math,json,os
from mathutils import Vector
from . import network

def load_groups(path):
    path=bpy.path.abspath(path)
    if not os.path.isfile(path):raise ValueError('TrackTools node library is missing; reconnect your TT_NodeGroups.blend file')
    required=['TERRAIN_GEOMETRY','TERRAIN_SHAPE']
    existing={name:next((g for g in bpy.data.node_groups if g.name==name and g.library and os.path.realpath(bpy.path.abspath(g.library.filepath))==os.path.realpath(path)),None) for name in required}
    if all(existing.values()):return existing
    with bpy.data.libraries.load(path,link=True) as (source,target):
        if any(name not in source.node_groups for name in required):raise ValueError('Select the TrackTools node library containing TERRAIN_GEOMETRY and TERRAIN_SHAPE')
        target.node_groups=list(required)
    groups=dict(zip(required,target.node_groups))
    if any(group is None for group in groups.values()):raise ValueError('TrackTools terrain groups could not be linked')
    return groups

def border_wrapper():
    name='WB_TT_BORDER_ADAPTER';group=bpy.data.node_groups.get(name)
    if group:return group
    group=bpy.data.node_groups.new(name,'GeometryNodeTree');group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes=group.nodes;links=group.links;input=nodes.new('NodeGroupInput');output=nodes.new('NodeGroupOutput');neighbors=nodes.new('GeometryNodeInputMeshEdgeNeighbors');compare=nodes.new('FunctionNodeCompare');compare.data_type='INT';compare.operation='EQUAL';links.new(neighbors.outputs['Face Count'],compare.inputs[2]);compare.inputs[3].default_value=1
    curve=nodes.new('GeometryNodeMeshToCurve');links.new(input.outputs['Geometry'],curve.inputs['Mesh']);links.new(compare.outputs['Result'],curve.inputs['Selection'])
    parts=nodes.new('GeometryNodeStoreNamedAttribute');parts.data_type='INT';parts.domain='POINT';parts.inputs['Name'].default_value='parts';parts.inputs['Value'].default_value=7;links.new(curve.outputs['Curve'],parts.inputs['Geometry'])
    ids=nodes.new('GeometryNodeStoreNamedAttribute');ids.data_type='INT';ids.domain='POINT';ids.inputs['Name'].default_value='edgeID';ids.inputs['Value'].default_value=0;links.new(parts.outputs['Geometry'],ids.inputs['Geometry'])
    join=nodes.new('GeometryNodeJoinGeometry');links.new(input.outputs['Geometry'],join.inputs['Geometry']);links.new(ids.outputs['Geometry'],join.inputs['Geometry']);links.new(join.outputs['Geometry'],output.inputs['Geometry'])
    return group

def set_input(mod,name,value):
    socket=next((s for s in mod.node_group.interface.items_tree if getattr(s,'in_out',None)=='INPUT' and s.name==name),None)
    if not socket:raise ValueError('TrackTools interface does not expose '+name)
    mod[socket.identifier]=value

def native_stack(obj,target_collection,groups,config):
    geometry=obj.modifiers.new('TT adaptive terrain geometry','NODES');geometry.node_group=groups['TERRAIN_GEOMETRY']
    for name,value in [('input type',1),('road collection',target_collection),('number of ranges',config.get('tt_refinement',1)),('range 1',config.get('tt_refine_distance',5.)),('delete far',0.)]:set_input(geometry,name,value)
    shape=obj.modifiers.new('TT terrain road contact','NODES');shape.node_group=groups['TERRAIN_SHAPE']
    for name,value in [('target mode',1),('target collection',target_collection),('flatten min',config.get('tt_flat_min',1.)),('flatten max',config.get('tt_flat_max',config['blend_distance'])),('cut terrain',config.get('tt_cut',True)),('extrude cutter',True),('EDGE index',0),('Z offset',0.)]:set_input(shape,name,value)
    obj['wb_terrain_backend']='tracktools';return geometry,shape

def proxy_mesh(collection,points,faces,bridge_flags=None):
    mesh=bpy.data.meshes.new('WB_TT_ROAD_SURFACES');mesh.from_pydata(points,[],faces);mesh.update()
    for name,kind,values in [('parts','INT',[1]*len(points)),('br_tun','INT',bridge_flags or [0]*len(points)),('road_width','FLOAT',[6.]*len(points))]:
        attr=mesh.attributes.new(name,kind,'POINT')
        for item,value in zip(attr.data,values):item.value=value
    obj=bpy.data.objects.new('WB_TT_ROAD_SURFACES',mesh);collection.objects.link(obj);obj.hide_render=True;obj.hide_set(True);modifier=obj.modifiers.new('WB road edges for TrackTools','NODES');modifier.node_group=border_wrapper();return obj

def assemble(collection,graph,physical_objects,create_spec):
    from .network_blender import source_sampler
    config=graph['terrain']
    if not config.get('enabled',True):return None,{'enabled':False}
    groups=load_groups(config['tt_library']);targets=bpy.data.collections.new('WB_TT_TARGETS');targets['wb_owned']=True;collection.children.link(targets)
    # Preserve topology and separate point classifications across road/bridge regions.
    positions=[];faces=[];flags=[];excluded=0
    bridge_roads=[(r,network.road_samples(r,graph['settings']['sample_spacing'])) for r in graph['roads'] if r.get('terrain_mode')=='bridge']
    cache={r['id']:network.road_samples(r,graph['settings']['sample_spacing']) for r in graph['roads']}
    elevated_connections=[]
    for connection in graph.get('connections',[]):
        points,_=network.connection_points(graph,connection,cache);samples=network.sample_points(points,graph['settings']['sample_spacing'])
        elevated_connections.append((connection,samples))
    def classification(p):
        for road,samples in bridge_roads:
            distance,station=__import__(__package__+'.geometry',fromlist=['nearest_station']).nearest_station([q for _,q,_,_ in samples],p)
            q,t,n=network.frame(samples,station);offset=(p[0]-q[0])*n[0]+(p[1]-q[1])*n[1];left,right=network.widths(road,station)
            if -right-.01<=offset<=left+.01 and abs(p[2]-(q[2]-abs(offset)*road.get('crossfall',0)))<.15:return 2
        for connection,samples in elevated_connections:
            distance,station=__import__(__package__+'.geometry',fromlist=['nearest_station']).nearest_station([q for _,q,_,_ in samples],p)
            q,_,_=network.frame(samples,station)
            if distance<=connection['width']/2+.02 and abs(p[2]-q[2])<.15 and not connection.get('grade_from',0)<=station<=connection.get('grade_to',samples[-1][0]):return 2
        return 0
    for obj in physical_objects:
        if obj.type!='MESH' or obj.get('wb_category') not in ('road','curb','sidewalk','median','planter'):continue
        mesh=obj.data;mesh.calc_loop_triangles();remap={}
        for tri in mesh.loop_triangles:
            if tri.normal.z<.1:continue
            centre=sum((obj.matrix_world@mesh.vertices[i].co for i in tri.vertices),Vector())/3;flag=classification(centre);face=[]
            # Elevated spans are deliberately absent from the ground cutter.
            # The native cut branch cuts every supplied road face, including bridge faces.
            if flag==2:excluded+=1;continue
            for i in tri.vertices:
                key=(i,flag)
                if key not in remap:remap[key]=len(positions);positions.append(tuple(obj.matrix_world@mesh.vertices[i].co));flags.append(flag)
                face.append(remap[key])
            faces.append(face)
    proxy_mesh(targets,positions,faces,flags)
    xmin,xmax,ymin,ymax=config['bounds'];spacing=config['grid_spacing'];nx=math.ceil((xmax-xmin)/spacing);ny=math.ceil((ymax-ymin)/spacing);sample=source_sampler(config);verts=[(xmin+(xmax-xmin)*x/nx,ymin+(ymax-ymin)*y/ny,sample(xmin+(xmax-xmin)*x/nx,ymin+(ymax-ymin)*y/ny)) for y in range(ny+1) for x in range(nx+1)];cells=[]
    for y in range(ny):
        for x in range(nx):
            a=y*(nx+1)+x;cells.append((a,a+1,a+nx+2,a+nx+1))
    obj=create_spec(collection,{'id':'network-terrain','category':'terrain','verts':verts,'faces':cells,'material':'grass','metadata':{'terrain_backend':'TrackTools native groups','intentional_open_surface':True}})
    attr=obj.data.attributes.new('wb_original_height','FLOAT','POINT')
    for item,co in zip(attr.data,verts):item.value=co[2]
    native_stack(obj,targets,groups,config);bpy.context.view_layer.update()
    return obj,{'enabled':True,'backend':'tracktools','base_vertices':len(verts),'native_groups':['TERRAIN_GEOMETRY','TERRAIN_SHAPE'],'proxy_faces':len(faces),'excluded_bridge_faces':excluded,'cut_terrain':config.get('tt_cut',True)}
