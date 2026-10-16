"""Editable POLY street network with cached angled junctions and graded roads.
No surface Booleans. Quads on approaches; constrained triangulation in junctions.
"""
import math,json,hashlib,time
import bpy
from mathutils import Vector
from .native_extension import socket,set_input
EPS=1e-6
SCHEMA=8
_busy=False
_pending={}
_last_edit=0.
_edit_costs={}
_live_refresh={}
LIVE_BUDGET=.016


def key(p):return tuple(round(float(v),6) for v in p)
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def lerp(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
def area(poly):return sum(cross(poly[i],poly[(i+1)%len(poly)]) for i in range(len(poly)))/2

def inside(p,poly):
    hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit


def graph(paths,width):
    segments=[]
    for points,radius in paths:
        values=[radius]*len(points) if isinstance(radius,(float,int)) else radius
        for i,(a,b) in enumerate(zip(points,points[1:])):
            if math.dist(a,b)>EPS:
                if math.hypot(b[0]-a[0],b[1]-a[1])<EPS:raise ValueError('Vertical road segments are not supported')
                segments.append((a,b,width*values[i],width*values[i+1]))
    cuts=[{0.,1.} for _ in segments]
    for i,(a,b,wa,wb) in enumerate(segments):
        ab=sub(b,a)
        for j in range(i):
            c,d,_,_=segments[j];cd=sub(d,c);ca=sub(c,a);den=cross(ab,cd)
            if abs(den)>EPS:
                t=cross(ca,cd)/den;u=cross(ca,ab)/den
                if -EPS<=t<=1+EPS and -EPS<=u<=1+EPS and abs(lerp(a,b,t)[2]-lerp(c,d,u)[2])<EPS:
                    cuts[i].add(max(0.,min(1.,t)));cuts[j].add(max(0.,min(1.,u)))
            elif abs(cross(ca,ab))<EPS:
                for point in (c,d):
                    t=sum((point[k]-a[k])*ab[k] for k in (0,1))/sum(ab[k]**2 for k in (0,1))
                    if EPS<t<1-EPS and math.dist(point,lerp(a,b,t))<EPS:cuts[i].add(t)
                for point in (a,b):
                    u=sum((point[k]-c[k])*cd[k] for k in (0,1))/sum(cd[k]**2 for k in (0,1))
                    if EPS<u<1-EPS and math.dist(point,lerp(c,d,u))<EPS:cuts[j].add(u)
    nodes={};edges={};duplicates=0
    for (a,b,wa,wb),split in zip(segments,cuts):
        split=sorted(split)
        for t,u in zip(split,split[1:]):
            p=key(lerp(a,b,t));q=key(lerp(a,b,u))
            if p==q:continue
            edge=tuple(sorted((p,q)))
            pw=wa+(wb-wa)*t;qw=wa+(wb-wa)*u
            pair=(pw,qw) if p==edge[0] else (qw,pw)
            if edge in edges:
                duplicates+=1;previous=edges[edge] if isinstance(edges[edge],tuple) else (edges[edge],edges[edge]);pair=tuple(max(x,y) for x,y in zip(previous,pair))
            edges[edge]=pair[0] if abs(pair[0]-pair[1])<EPS else pair
            nodes.setdefault(p,set()).add(q);nodes.setdefault(q,set()).add(p)
    # Collinear control points are authoring handles, not separate mesh regions.
    changed=True
    while changed:
        changed=False
        for p,neighbors in list(nodes.items()):
            if len(neighbors)!=2:continue
            a,b=list(neighbors);va=Vector(sub(a,p));vb=Vector(sub(b,p))
            if va.normalized().dot(vb.normalized())<-.99999:
                ea,eb=tuple(sorted((a,p))),tuple(sorted((b,p)))
                if isinstance(edges[ea],tuple) or isinstance(edges[eb],tuple) or abs(edges[ea]-edges[eb])>EPS:continue
                w=edges.pop(ea);edges.pop(eb);edges[tuple(sorted((a,b)))]=w
                nodes[a].remove(p);nodes[a].add(b);nodes[b].remove(p);nodes[b].add(a);nodes.pop(p)
                changed=True;break
    return nodes,edges,duplicates


def build(paths,width=6.,spacing=1.,radii=None,junction_radii=None):
    from .surface_network import build_network
    return build_network(paths,width,spacing,radii,graph,junction_radii)


def modifier(road):return next((m for m in road.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.split('.')[0]=='ROADLAB_ROAD_CORE'),None)
def values(road):
    from .native_contacts import input_value
    mod=modifier(road)
    return {name:input_value(mod,name) for name in ('road width','resolution','corner NW','corner NE','corner SW','corner SE')}

def rebuild(road,force=False):
    # Evaluating curb/sidewalk surfaces for decals can dispatch depsgraph handlers.
    # A direct rebuild needs the same guard as the queued update path.
    global _busy
    previous=_busy;_busy=True
    try:return _rebuild(road,force)
    finally:_busy=previous

def _rebuild(road,force=False):
    mod=modifier(road)
    if not mod:return
    if road.mode=='EDIT':road.update_from_editmode()
    from . import point_settings
    items=point_settings.sync(road)
    from .lane_editor import inherit_extensions
    inherit_extensions(road);items=point_settings.records(road)
    settings=values(road);paths=[];tilts=[];ids_by_path=[];offset=0
    for spline in road.data.splines:
        if spline.type!='POLY':raise ValueError('Prototype accepts POLY splines only')
        ids_by_path.append([items[offset+i]['id'] for i in range(len(spline.points))])
        radii=[items[offset+i].get('width',settings['road width']*p.radius)/settings['road width'] for i,p in enumerate(spline.points)]
        offset+=len(spline.points)
        angles=[float(p.tilt) for p in spline.points]
        coords=[tuple(p.co[:3]) for p in spline.points]
        if spline.use_cyclic_u and coords:coords.append(coords[0]);radii.append(radii[0]);angles.append(angles[0])
        paths.append((coords,radii));tilts.append(angles)
    shape_signature=hashlib.sha256(json.dumps([SCHEMA,paths,tilts,settings,road.get('roadlab_lane_pockets','[]'),[(list(k),v) for k,v in point_settings.junction_overrides(road).items()],[(list(k),v) for k,v in point_settings.corner_lifts(road).items()]],sort_keys=True).encode()).hexdigest()
    signature=hashlib.sha256((shape_signature+road.get('roadlab_sculpt_field','')+road.get('roadlab_bridge_cuts','')).encode()).hexdigest()
    output=road.get('roadlab_core_mesh');outline=road.get('roadlab_core_outline')
    if output is None or outline is None:raise ValueError('Generated references are missing; reopen the prototype scene')
    owner=output.get('roadlab_core_owner_name')
    if owner and owner!=road.name and mod.node_group.users>1:
        attach(road);return
    for helper in (output,outline):helper['roadlab_core_owner_name']=road.name
    for helper in (output,outline):
        if helper.matrix_world!=road.matrix_world:helper.matrix_world=road.matrix_world.copy()
    if not force and road.get('roadlab_core_signature')==signature:
        if road.get('roadlab_core_error'):road['roadlab_core_error']=''
        refresh_markings(road)
        return
    derived_overrides=point_settings.junction_overrides(road);junction_shifts={};source_positions={}
    pockets=json.loads(road.get('roadlab_lane_pockets','[]'))
    if pockets:
        from . import lane_pockets
        nodes,_,_=graph(paths,settings['road width'])
        junction_shifts=lane_pockets.junction_shifts(paths,ids_by_path,pockets,[p for p,n in nodes.items() if len(n)>=3],settings['road width'],max(settings['corner '+k] for k in ('NW','NE','SW','SE')))
        derived_overrides={(co[0]+junction_shifts.get(co,(0,0))[0],co[1]+junction_shifts.get(co,(0,0))[1],co[2]):v for co,v in derived_overrides.items()}
        paths,tilts,pocket_details=lane_pockets.expand(paths,ids_by_path,pockets,settings['road width'],tilts,[p for p,n in nodes.items() if len(n)>=3],max(settings['corner '+k] for k in ('NW','NE','SW','SE')))
        source_positions={key(co):key(p) for detail in pocket_details for co,p in detail['source_positions'].items()}
        derived_overrides={source_positions.get(co,co):v for co,v in point_settings.junction_overrides(road).items()}
    verts,faces,regions,loops,report=build(paths,settings['road width'],settings['resolution'],{k:settings['corner '+k] for k in ('NW','NE','SW','SE')},derived_overrides)
    from . import road_heightfield,road_sculpt
    from . import curve_bank
    if any(abs(a)>1e-8 for row in tilts for a in row):verts=[(x,y,z+curve_bank.displacement([p[0] for p in paths],tilts,settings['road width'],x,y)) for x,y,z in verts]
    lifts={source_positions.get(co,co):v for co,v in point_settings.corner_lifts(road).items()}
    verts=[(x,y,z+road_heightfield.corner_displacement(x,y,report['radius_limits'],lifts)) for x,y,z in verts]
    road_sculpt.remember(road,verts,faces,shape_signature)
    sculpt=road_heightfield.decode(road.get('roadlab_sculpt_field',''))
    if sculpt:verts=[(x,y,z+road_heightfield.sample(sculpt,x,y)) for x,y,z in verts]
    if source_positions:
        source_junctions={p:co for co,p in source_positions.items()}
        for corner in report['radius_limits']:
            current=key(corner.get('junction',(0,0,0)))
            if current in source_junctions:corner['geometry_junction']=corner['junction'];corner['junction']=list(source_junctions[current])
    report['lane_pockets']=len(pockets)
    report['sculpt_samples']=len(sculpt);report['lifted_corners']=sum(bool(v) for values in lifts.values() for v in values.values())
    mesh=bpy.data.meshes.new('RoadLab Core Mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    for polygon in mesh.polygons:polygon.use_smooth=True
    from . import sidewalk_guard
    limit=mesh.attributes.new('roadlab_offset_limit','FLOAT','POINT')
    for value,height in zip(limit.data,sidewalk_guard.limits(verts,loops,report)):value.value=height
    sidewalk_guard.border_fields(mod.node_group,output)
    region=mesh.attributes.new('roadlab_region','INT','FACE')
    for x,v in zip(region.data,regions):x.value=v
    from . import road_paths
    cuts=json.loads(road.get('roadlab_bridge_cuts','[]'))
    mask=road_paths.contact_mask([path[0] for path in paths],cuts,verts,faces) if cuts else [True]*len(faces)
    contact=mesh.attributes.new('roadlab_ground_contact','BOOLEAN','FACE')
    for x,v in zip(contact.data,mask):x.value=v
    report['bridge_spans']=len(cuts);report['bridge_faces']=sum(not v for v in mask)
    uv=mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:uv.data[loop.index].uv=mesh.vertices[loop.vertex_index].co.xy
    from . import terrain_quads
    terrain_quads.release_seam(output)
    previous=output.data;output.data=mesh
    if previous.users==0:bpy.data.meshes.remove(previous)
    outline.data.splines.clear()
    for loop in loops:
        spline=outline.data.splines.new('POLY');spline.points.add(len(loop)-1);spline.use_cyclic_u=True
        for point,index in zip(spline.points,loop):point.co=(*verts[index],1)
    outline.data.update_tag();road['roadlab_core_signature']=signature;road['roadlab_core_report']=json.dumps(report);road['roadlab_core_error']='';road.update_tag()
    refresh_markings(road)


def refresh_markings(road):
    from . import marking_stamp
    try:
        marking_stamp.rebuild(road);road['roadlab_manual_marking_error']=''
    except Exception as error:road['roadlab_manual_marking_error']=str(error)
    if 'roadlab_lanes' not in road:return
    from . import lane_editor
    for scene in road.users_scene:
        try:lane_editor.rebuild(road,scene)
        except Exception as error:road['roadlab_marking_warnings']=json.dumps([str(error)])


def attach(road):
    from . import material
    previous=modifier(road);saved=values(road) if previous else {}
    from .native_contacts import input_value
    saved_material=input_value(previous,'material') if previous else None
    c=next((c for c in bpy.context.scene.collection.children if c.name.split('.')[0]=='RoadLab Core References'),None)
    if c is None:c=bpy.data.collections.new('RoadLab Core References');bpy.context.scene.collection.children.link(c)
    output=bpy.data.objects.new('RoadLab Core Pavement Reference',bpy.data.meshes.new('RoadLab Core Mesh'));c.objects.link(output);output.hide_set(True);output.hide_render=True
    data=bpy.data.curves.new('RoadLab Finished Perimeter','CURVE');data.dimensions='3D';outline=bpy.data.objects.new('RoadLab Finished Perimeter',data);c.objects.link(outline);outline.hide_set(True);outline.hide_render=True
    road['roadlab_core_mesh']=output;road['roadlab_core_outline']=outline
    for helper in (output,outline):helper['roadlab_core_owner_name']=road.name
    g=bpy.data.node_groups.new('ROADLAB_ROAD_CORE','GeometryNodeTree')
    socket(g,'Geometry','INPUT','NodeSocketGeometry');socket(g,'Geometry','OUTPUT','NodeSocketGeometry')
    for name,value in [('road width',6.),('resolution',1.),('corner NW',4.),('corner NE',4.),('corner SW',4.),('corner SE',4.)]:
        item=socket(g,name,'INPUT','NodeSocketFloat',value);item.min_value=.25
    socket(g,'material','INPUT','NodeSocketMaterial')
    n=g.nodes;l=g.links;inp=n.new('NodeGroupInput');out=n.new('NodeGroupOutput')
    mesh=n.new('GeometryNodeObjectInfo');mesh.transform_space='RELATIVE';mesh.inputs['Object'].default_value=output
    tagged=n.new('GeometryNodeStoreNamedAttribute');tagged.data_type='INT';tagged.domain='POINT';tagged.inputs['Name'].default_value='parts';tagged.inputs['Value'].default_value=1;l.new(mesh.outputs['Geometry'],tagged.inputs['Geometry'])
    mat=n.new('GeometryNodeSetMaterial');l.new(tagged.outputs['Geometry'],mat.inputs['Geometry']);l.new(inp.outputs['material'],mat.inputs['Material'])
    border=n.new('GeometryNodeObjectInfo');border.transform_space='RELATIVE';border.inputs['Object'].default_value=outline
    tangent=n.new('GeometryNodeInputTangent');normal=n.new('ShaderNodeVectorMath');normal.operation='CROSS_PRODUCT';normal.inputs[1].default_value=(0,0,1);l.new(tangent.outputs['Tangent'],normal.inputs[0])
    frame=n.new('GeometryNodeSetCurveNormal');frame.inputs['Mode'].default_value='Free';l.new(border.outputs['Geometry'],frame.inputs['Curve']);l.new(normal.outputs['Vector'],frame.inputs['Normal'])
    tagged_border=n.new('GeometryNodeStoreNamedAttribute');tagged_border.data_type='INT';tagged_border.domain='POINT';tagged_border.inputs['Name'].default_value='parts';tagged_border.inputs['Value'].default_value=7;l.new(frame.outputs['Curve'],tagged_border.inputs['Geometry'])
    joined=n.new('GeometryNodeJoinGeometry');l.new(mat.outputs['Geometry'],joined.inputs['Geometry']);l.new(tagged_border.outputs['Geometry'],joined.inputs['Geometry']);l.new(joined.outputs['Geometry'],out.inputs['Geometry'])
    m=previous or road.modifiers.new('RoadLab New Core','NODES');m.node_group=g;
    for name,value in saved.items():set_input(m,name,value)
    m.show_in_editmode=True;set_input(m,'material',saved_material or material('asphalt'));road['roadlab_new_core']=True;rebuild(road,True)
    return m


def interaction_active():
    # Blender exposes the operators currently running modally on each window.
    prefixes=('TRANSFORM_OT_','CURVE_OT_extrude','MESH_OT_','SCULPT_OT_','PAINT_OT_','GIZMOGROUP_OT_','WM_OT_context_modal','ROADLAB_OT_sculpt','ROADLAB_OT_slice','ROADLAB_OT_terrain_sculpt')
    for window in bpy.context.window_manager.windows:
        for op in window.modal_operators:
            name=op.bl_rna.identifier
            if name.startswith(prefixes):return True
    return False


def live_allowed(scene,roads):
    mode=scene.roadlab_core_update_mode
    if mode=='PLACEMENT':return False
    if mode=='LIVE':return True
    # Auto only evaluates live after observing a fast completed edit. Cold
    # startup cost is conservative; subsequent placements refine the estimate.
    if _edit_costs.get(scene.as_pointer(),float('inf'))>LIVE_BUDGET:return False
    for road in roads:
        report=json.loads(road.get('roadlab_core_report','{}'))
        if report.get('merged_regions',0) or report.get('faces',0)>1500:return False
    return True


def last_edit_ms(scene):return _edit_costs.get(scene.as_pointer(),0.)*1000


def is_pending(scene):return scene.as_pointer() in _pending


def flush_pending(force=False,live=False):
    global _busy
    if _busy or (not force and not live and interaction_active()):return False
    items=list(_pending.values());_pending.clear();_busy=True
    try:
        from . import core_terrain
        for scene,roads in items:
            started=time.perf_counter()
            try:
                if scene.name not in bpy.data.scenes:continue
                old_signatures={road.as_pointer():road.get('roadlab_core_signature') for road in roads}
                terrain=scene.wb_native.terrain;old_terrain=terrain.get('roadlab_core_terrain_signature') if terrain else None
                for road in roads:
                    if road.name not in scene.objects:continue
                    try:rebuild(road)
                    except (ValueError,RuntimeError) as exc:road['roadlab_core_error']=str(exc)
                try:core_terrain.rebuild(scene)
                except (ValueError,RuntimeError) as exc:
                    terrain=scene.wb_native.terrain
                    if terrain:terrain['roadlab_core_terrain_error']=str(exc)
            except ReferenceError:continue
            changed=any(road.get('roadlab_core_signature')!=old_signatures.get(road.as_pointer()) for road in roads) or (terrain and terrain.get('roadlab_core_terrain_signature')!=old_terrain)
            if changed:_edit_costs[scene.as_pointer()]=time.perf_counter()-started
            if live:_live_refresh[scene.as_pointer()]=time.monotonic()
    finally:_busy=False
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()
    return True


def finish_edits():
    if not _pending:return None
    if interaction_active():
        if _pending and all(live_allowed(scene,roads) for scene,roads in _pending.values()):
            delay=max(1/30-(time.monotonic()-_live_refresh.get(scene.as_pointer(),0.)) for scene,roads in _pending.values())
            if delay>0:return max(.01,delay)
            flush_pending(live=True)
        return .08 if _pending else None
    remaining=.16-(time.monotonic()-_last_edit)
    if remaining>0:return max(.02,remaining)
    flush_pending()
    return .08 if _pending else None


@bpy.app.handlers.persistent
def synchronize(scene,depsgraph):
    global _last_edit
    if _busy:return
    changed={update.id.original for update in depsgraph.updates}
    roads={road for road in scene.objects if road.type=='CURVE' and road.get('roadlab_new_core') and
           (road in changed or road.data in changed or (modifier(road) and modifier(road).node_group in changed) or not road.get('roadlab_core_signature'))}
    terrain=scene.wb_native.terrain
    from . import terrain_sculpt
    if terrain_sculpt.is_active() and not roads:return
    if not roads and not (terrain and (terrain in changed or terrain.data in changed)):return
    previous=_pending.get(scene.as_pointer())
    if previous:roads.update(previous[1])
    _pending[scene.as_pointer()]=(scene,roads);_last_edit=time.monotonic()
    # Batch scripts have no interactive transform. Keep deterministic evaluation
    # there; actual modal transforms always defer, including in scheduler tests.
    active=interaction_active()
    if bpy.app.background and not active:flush_pending();return
    from . import road_sculpt
    live=active and not road_sculpt.is_painting() and live_allowed(scene,roads)
    if live and time.monotonic()-_live_refresh.get(scene.as_pointer(),0.)>=1/30:
        flush_pending(live=True);_live_refresh[scene.as_pointer()]=time.monotonic()
        return
    if not bpy.app.timers.is_registered(finish_edits):bpy.app.timers.register(finish_edits,first_interval=.02 if live else .08)


@bpy.app.handlers.persistent
def initialize_loaded_scene(_):
    global _busy
    if _busy:return
    _pending.clear();_busy=True
    try:
        from . import core_terrain,road_sculpt,terrain_sculpt
        core_terrain._STATE.clear();road_sculpt._BASE.clear();terrain_sculpt._DIRTY.clear()
        from .native_extrusion import extrusion_group
        extrusion_group()
        for obj in bpy.data.objects:
            if obj.get('wb_native_feature')=='sidewalk':
                for m in obj.modifiers:
                    if m.type=='NODES' and m.node_group and m.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):set_input(m,'Safe sidewalk offset',True)
        for scene in bpy.data.scenes:
            started=time.perf_counter()
            for road in scene.objects:
                if road.type=='CURVE' and road.get('roadlab_new_core'):
                    try:rebuild(road,True)
                    except (ValueError,RuntimeError) as exc:road['roadlab_core_error']=str(exc)
            try:core_terrain.rebuild(scene,True)
            except (ValueError,RuntimeError) as exc:
                terrain=scene.wb_native.terrain
                if terrain:terrain['roadlab_core_terrain_error']=str(exc)
            _edit_costs[scene.as_pointer()]=time.perf_counter()-started
    finally:_busy=False


@bpy.app.handlers.persistent
def prepare_output(_):
    flush_pending()


def register():
    from .core_terrain import register_properties
    register_properties()
    from . import selected_points
    selected_points.register()
    from . import road_sculpt
    road_sculpt.register()
    if synchronize not in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.append(synchronize)
    if initialize_loaded_scene not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(initialize_loaded_scene)
    for handlers in (bpy.app.handlers.save_pre,bpy.app.handlers.render_pre):
        if prepare_output not in handlers:handlers.append(prepare_output)
def unregister():
    _pending.clear();_edit_costs.clear();_live_refresh.clear()
    if bpy.app.timers.is_registered(finish_edits):bpy.app.timers.unregister(finish_edits)
    from . import selected_points
    from . import road_sculpt
    road_sculpt.unregister()
    selected_points.unregister()
    from .core_terrain import unregister_properties
    unregister_properties()
    if synchronize in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.remove(synchronize)
    if initialize_loaded_scene in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(initialize_loaded_scene)
    for handlers in (bpy.app.handlers.save_pre,bpy.app.handlers.render_pre):
        if prepare_output in handlers:handlers.remove(prepare_output)
