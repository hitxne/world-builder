"""Selection-scoped lane controls and surface-conforming marking output."""
import bpy,json,hashlib
from math import hypot
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import IntProperty,FloatProperty,EnumProperty,CollectionProperty,PointerProperty,BoolProperty,StringProperty
from . import point_settings, lane_markings, lane_logic

MOVEMENTS=[('THROUGH','Through',''),('LEFT','Left',''),('RIGHT','Right',''),('LEFT_THROUGH','Left + through',''),('RIGHT_THROUGH','Through + right',''),('LEFT_RIGHT','Left + right',''),('LEFT_RIGHT_THROUGH','Left + through + right',''),('UTURN','U-turn','')]

def road(context):
    active=getattr(context,'edit_object',None) or getattr(context,'active_object',None)
    obj=active if active is not None and getattr(active,'type',None)=='CURVE' and active.get('roadlab_new_core') else context.scene.wb_native.road
    if not obj or not obj.get('roadlab_new_core'):raise ValueError('Assign a RoadLab core road first')
    return obj

def segments(obj):
    items=point_settings.records(obj);offset=0;result=[]
    for spl in obj.data.splines:
        count=len(spl.points)
        for i in range(count if spl.use_cyclic_u else count-1):
            x=offset+i;y=offset+(i+1)%count
            if max(x,y)<len(items):result.append((x,y,items[x]['id'],items[y]['id']))
        offset+=count
    return result

def split_lane_assignments(obj,configs,new_ids,records):
    """Migrate an assigned edge through newly inserted points on its source spline.

    Existing unrelated routes are never used to repair a removed connection.
    Lane orientation and controls at the two original endpoints are preserved.
    """
    valid={frozenset((a,b)) for _,_,a,b in segments(obj)};splines=[];offset=0
    for spline in obj.data.splines:
        ids=[row['id'] for row in records[offset:offset+len(spline.points)]];offset+=len(spline.points)
        splines.append((ids,spline.use_cyclic_u))
    lookup={row['id']:i for i,row in enumerate(records)};result=[]
    for config in configs:
        a,b=config['endpoints']
        if frozenset((a,b)) in valid:result.append(config);continue
        routes=[]
        for ids,cyclic in splines:
            if a not in ids or b not in ids:continue
            first,last=ids.index(a),ids.index(b)
            for step in ((1,-1) if cyclic else ((1,) if first<last else (-1,))):
                path=[a];index=first
                for _ in range(len(ids)-1):
                    index=(index+step)%len(ids);path.append(ids[index])
                    if ids[index]==b:break
                if path[-1]!=b or len(path)<=2:continue
                delta=Vector(records[lookup[b]]['co'])-Vector(records[lookup[a]]['co']);length2=delta.length_squared
                def on_original_edge(ident):
                    point=Vector(records[lookup[ident]]['co'])-Vector(records[lookup[a]]['co'])
                    t=point.dot(delta)/max(length2,1e-12)
                    return 0<t<1 and (point-delta*t).length<1e-5
                if all(i in new_ids for i in path[1:-1]) or all(on_original_edge(i) for i in path[1:-1]):routes.append(path)
        if len(routes)!=1:result.append(config);continue
        path=routes[0];coords=[Vector(records[lookup[i]]['co']) for i in path]
        lengths=[(y-x).length for x,y in zip(coords,coords[1:])];total=sum(lengths);distance=0.
        from .road_core import values
        default=values(obj)['road width'];wa=point_settings.width(obj,lookup[a],default);wb=point_settings.width(obj,lookup[b],default)
        for index,ident in enumerate(path[1:-1],1):
            distance+=lengths[index-1]
            if 'width' not in records[lookup[ident]]:records[lookup[ident]]['width']=wa+(wb-wa)*distance/max(total,1e-9)
        for index,(x,y) in enumerate(zip(path,path[1:])):
            child=json.loads(json.dumps(config));child['endpoints']=[x,y]
            if index>0:child['control_outgoing']='NONE';child['crosswalk_outgoing']=False
            if index<len(path)-2:child['control_incoming']='NONE';child['crosswalk_incoming']=False
            result.append(child)
    return result


def inherit_extensions(obj):
    """Copy a lane profile only onto newly created, unambiguous endpoint extensions."""
    records=point_settings.records(obj);ids={row['id'] for row in records}
    known=set(json.loads(obj.get('roadlab_lane_known_points',json.dumps(sorted(ids)))))
    new=ids-known;obj['roadlab_lane_known_points']=json.dumps(sorted(ids))
    edges={frozenset((a,b)) for _,_,a,b in segments(obj)}
    old_edges={frozenset(edge) for edge in json.loads(obj.get('roadlab_lane_known_edges',json.dumps([sorted(edge) for edge in edges])))}
    added_edges=edges-old_edges;obj['roadlab_lane_known_edges']=json.dumps(sorted(sorted(edge) for edge in edges))
    if 'roadlab_lanes' not in obj:return
    configs=split_lane_assignments(obj,state(obj),new,records)
    if not new and not added_edges:
        if configs!=state(obj):obj['roadlab_lanes']=json.dumps(configs);point_settings.save(obj,records)
        return
    ps=point_settings.points(obj);lookup={row['id']:i for i,row in enumerate(records)}
    position=lambda ident:tuple(round(float(v),6) for v in ps[lookup[ident]].co[:3])
    segs=segments(obj);neighbors={}
    for _,_,a,b in segs:
        pa,pb=position(a),position(b);neighbors.setdefault(pa,set()).add(pb);neighbors.setdefault(pb,set()).add(pa)
    changed=True
    while changed:
        changed=False;assigned={frozenset(c['endpoints']) for c in configs}
        for _,_,a,b in segs:
            if frozenset((a,b)) in assigned or not ({a,b}&new or frozenset((a,b)) in added_edges):continue
            if not ({a,b}&new):
                # Joining two configured ends may fill the gap only if both
                # profiles agree in the new edge's direction of travel.
                proposals=[]
                for shared,other in ((a,b),(b,a)):
                    parents=[c for c in configs if all(i in lookup for i in c['endpoints']) and any(position(i)==position(shared) for i in c['endpoints'])]
                    if len(neighbors[position(shared)])!=2 or len(parents)!=1:break
                    parent=parents[0];forward=([shared,other] if position(parent['endpoints'][1])==position(shared) else [other,shared])==[a,b]
                    proposals.append((parent['incoming'] if forward else parent['outgoing'],parent['outgoing'] if forward else parent['incoming'],parent.get('median',0)))
                if len(proposals)!=2 or proposals[0]!=proposals[1]:continue
            for shared,other in ((a,b),(b,a)):
                p=position(shared)
                if len(neighbors[p])!=2:continue
                candidates=[]
                for config in configs:
                    x,y=config['endpoints']
                    if x not in lookup or y not in lookup:continue
                    if position(x)==p or position(y)==p:candidates.append(config)
                if len(candidates)!=1:continue
                parent=candidates[0];copy=json.loads(json.dumps(parent))
                copy['endpoints']=[shared,other] if position(parent['endpoints'][1])==p else [other,shared]
                copy['control_incoming']=copy['control_outgoing']='NONE';copy['crosswalk_incoming']=copy['crosswalk_outgoing']=False;configs.append(copy)
                if 'width' not in records[lookup[other]] and 'width' in records[lookup[shared]]:records[lookup[other]]['width']=records[lookup[shared]]['width']
                assigned.add(frozenset((a,b)));changed=True;break
    obj['roadlab_lanes']=json.dumps(configs);point_settings.save(obj,records)


def selected_segment(context,sync=False):
    obj=road(context);sel=set(point_settings.selected(context,obj))
    if sync:point_settings.sync(obj)
    matches=[s for s in segments(obj) if s[0] in sel and s[1] in sel]
    if len(sel)!=2 or len(matches)!=1:raise ValueError('Select exactly two adjacent road points in Edit Mode')
    return obj,matches[0]

def state(obj):return json.loads(obj.get('roadlab_lanes','[]'))

def entries(rows,prefix):return [lane_logic.Lane(f'{prefix}{i}',x['width'],frozenset(x['movement'].split('_'))) for i,x in enumerate(rows)]

def rows(collection):return [{'width':x.width,'movement':x.movement,'entry':getattr(x,'entry','CONTINUOUS')} for x in collection]

class ROADLAB_Lane(bpy.types.PropertyGroup):
    entry:EnumProperty(name='Lane entry',items=[('CONTINUOUS','Continuous','Normal lane divider'),('ADDED','Added lane','Short dotted divider in the entry section; does not change road geometry')],default='CONTINUOUS')
    width:FloatProperty(name='Width (m)',min=.5,default=3.5)
    movement:EnumProperty(name='Movement',items=MOVEMENTS,default='THROUGH')

class ROADLAB_LaneDraft(bpy.types.PropertyGroup):
    segment_key:StringProperty(default='',options={'HIDDEN'})
    targets_json:StringProperty(default='[]',options={'HIDDEN'})
    road_width:FloatProperty(name='Road width (m)',min=.25,default=8.)
    show_size:BoolProperty(default=False)
    show_incoming:BoolProperty(default=False)
    show_outgoing:BoolProperty(default=False)
    show_markings:BoolProperty(default=False)
    page:EnumProperty(items=[('LANES','Lanes','Lane counts and allowed movements'),('MARKINGS','Markings','Arrows, dividers and stop lines'),('ROAD','Road size','Width, median and section direction')],default='LANES')
    travel:EnumProperty(items=[('incoming','Arriving','Traffic toward the junction or section end'),('outgoing','Leaving','Traffic away from the junction or section end')],default='incoming')
    show_arrows:BoolProperty(default=False)
    show_dividers:BoolProperty(default=False)
    show_stops:BoolProperty(default=False)
    show_crosswalks:BoolProperty(default=False)
    crosswalk_incoming:BoolProperty(name='Crosswalk at this end',default=False)
    crosswalk_outgoing:BoolProperty(name='Crosswalk at other end',default=False)
    crosswalk_depth:FloatProperty(name='Crosswalk width (m)',default=3.048,min=.5,max=10.)
    crosswalk_gap:FloatProperty(name='Gap from junction (m)',default=1.,min=0.,max=30.)
    crosswalk_ramp:FloatProperty(name='Ramp run (m)',default=1.9,min=.3,max=10.,description='Distance from the street edge to full curb/sidewalk height')
    crosswalk_a:FloatProperty(name='A-end position (m)',default=0.,min=-10.,max=30.,description='Move this sidewalk end away from the junction; opposite end stays fixed')
    crosswalk_b:FloatProperty(name='B-end position (m)',default=0.,min=-10.,max=30.,description='Move the opposite sidewalk end away from the junction; first end stays fixed')
    crosswalk_tactile:BoolProperty(name='Yellow tactile pads',default=False)
    show_lane_details:BoolProperty(default=False)
    show_saved:BoolProperty(default=False)
    incoming_index:IntProperty(default=0,min=0)
    outgoing_index:IntProperty(default=0,min=0)
    incoming:CollectionProperty(type=ROADLAB_Lane)
    outgoing:CollectionProperty(type=ROADLAB_Lane)
    median:FloatProperty(name='Median (m)',min=0.,default=0.)
    spacing:FloatProperty(name='Arrow spacing (m)',min=5.,default=18.)
    arrow_approach:FloatProperty(name='Arrow approach (m)',min=0.,default=35.,description='Distance before a junction that receives automatic arrows; zero disables them')
    solid_approach:FloatProperty(name='Solid approach (m)',min=0.,default=20.)
    lane_transition:FloatProperty(name='Lane transition (m)',min=1.,default=30.,description='Length used to taper a lane-count change on a straight connection')
    transition_length:FloatProperty(name='Entry dots (m)',min=0.,default=30.)
    stop_setback:FloatProperty(name='Stop setback (m)',min=0.,default=1.22)
    control_incoming:EnumProperty(name='Forward-end control',items=[('NONE','Uncontrolled','No stop bar'),('STOP','Stop','Place a stop bar on incoming lanes'),('SIGNAL','Traffic signals','Place a stop bar; traffic simulation remains separate'),('YIELD','Yield','No stop bar')],default='NONE')
    control_outgoing:EnumProperty(name='Reverse-end control',items=[('NONE','Uncontrolled','No stop bar'),('STOP','Stop','Place a stop bar on incoming lanes'),('SIGNAL','Traffic signals','Place a stop bar; traffic simulation remains separate'),('YIELD','Yield','No stop bar')],default='NONE')
    reverse:BoolProperty(name='Reverse section direction',description='Swap which end incoming lanes travel toward; the map driving side stays unchanged')


def paint_material(asset):
    name='RoadLab Marking '+asset;mat=bpy.data.materials.get(name)
    if mat:
        for node in mat.node_tree.nodes if mat.node_tree else []:
            if node.type=='TEX_IMAGE':node.extension='REPEAT' if asset in ('broken_white','dotted_white') else 'CLIP'
        return mat
    if asset=='tactile_pad':
        mat=bpy.data.materials.new(name);mat.use_nodes=True;mat.diffuse_color=(.95,.55,.025,1)
        nodes=mat.node_tree.nodes;links=mat.node_tree.links;shader=nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=mat.diffuse_color;shader.inputs['Roughness'].default_value=.78
        uv=nodes.new('ShaderNodeTexCoord');scale=nodes.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(50.8,10.1667,0);links.new(uv.outputs['UV'],scale.inputs[0])
        fract=nodes.new('ShaderNodeVectorMath');fract.operation='FRACTION';links.new(scale.outputs['Vector'],fract.inputs[0])
        center=nodes.new('ShaderNodeVectorMath');center.operation='SUBTRACT';center.inputs[1].default_value=(.5,.5,0);links.new(fract.outputs['Vector'],center.inputs[0])
        distance=nodes.new('ShaderNodeVectorMath');distance.operation='LENGTH';links.new(center.outputs['Vector'],distance.inputs[0])
        mask=nodes.new('ShaderNodeMath');mask.operation='LESS_THAN';mask.inputs[1].default_value=.2;links.new(distance.outputs['Value'],mask.inputs[0])
        bump=nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.005;links.new(mask.outputs[0],bump.inputs['Height']);links.new(bump.outputs['Normal'],shader.inputs['Normal'])
        return mat
    row=lane_markings.manifest()[asset];mat=bpy.data.materials.new(name);mat.use_nodes=True
    nodes=mat.node_tree.nodes;p=nodes.get('Principled BSDF');tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(lane_markings.ROOT/row['rgba']),check_existing=True);tex.image.alpha_mode='STRAIGHT';tex.extension='REPEAT' if asset in ('broken_white','dotted_white') else 'CLIP'
    mat.node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color']);mat.node_tree.links.new(tex.outputs['Alpha'],p.inputs['Alpha']);p.inputs['Roughness'].default_value=.85
    if hasattr(mat,'surface_render_method'):mat.surface_render_method='DITHERED'
    elif hasattr(mat,'blend_method'):mat.blend_method='HASHED'
    mat.diffuse_color=(.94,.94,.86,1);return mat


def rebuild(obj,scene,force=False):
    from . import road_core
    previous=road_core._busy;road_core._busy=True
    try:return _rebuild(obj,scene,force)
    finally:road_core._busy=previous

def _rebuild(obj,scene,force=False):
    if obj.get('roadlab_new_core'):inherit_extensions(obj)
    configs=state(obj);output=obj.get('roadlab_core_mesh')
    if output is None:return
    side=scene.roadlab_map_settings.traffic_side
    signature=hashlib.sha256(json.dumps(['editable-crossings-v5',getattr(scene.wb_native.terrain,'get',lambda *args:None)('roadlab_core_terrain_signature'),[(row.get('co'),row.get('connection_mode')) for row in point_settings.records(obj) if row.get('connection_mode')],obj.get('roadlab_hidden_lane_markings','[]'),configs,obj.get('roadlab_core_signature'),output.data.as_pointer(),side],sort_keys=True).encode()).hexdigest()
    existing=obj.get('roadlab_marking_object')
    owned=existing is not None and (existing.get('roadlab_markings_owner_object')==obj or existing.get('roadlab_markings_owner')==obj.name)
    if not force and owned and obj.get('roadlab_marking_signature')==signature:
        target=obj.get('roadlab_marking_object')
        if target is not None:target.matrix_world=obj.matrix_world.copy()
        return
    items=point_settings.records(obj);points=point_settings.points(obj);lookup={x['id']:i for i,x in enumerate(items)};valid={frozenset((a,b)) for _,_,a,b in segments(obj)}
    from .road_core import values,key,graph
    default=values(obj)['road width'];paths=[];offset=0
    for spl in obj.data.splines:
        coords=[tuple(p.co[:3]) for p in spl.points];widths=[point_settings.width(obj,offset+i,default)/default for i in range(len(coords))];offset+=len(coords)
        if spl.use_cyclic_u and coords:coords.append(coords[0]);widths.append(widths[0])
        paths.append((coords,widths))
    nodes,edges,_=graph(paths,default)
    from . import lane_bends
    transitions=lane_bends.profile_transitions(nodes,edges,configs,{ident:key(points[index].co[:3]) for ident,index in lookup.items()},values(obj),{key(row['co']) for row in items if row.get('connection_mode')=='STOP'})
    bends=lane_bends.patches(nodes,edges,values(obj),point_settings.junction_overrides(obj));bends.update(transitions);bend_arms={}
    stop_nodes={key(row['co']) for row in items if row.get('connection_mode')=='STOP'}
    def clearance(co,width,other):
        if key(co) in bends:
            neighbors=nodes[key(co)];neighbor=max(neighbors,key=lambda n:(Vector(n)-Vector(co)).normalized().dot((Vector(other)-Vector(co)).normalized()))
            return lane_bends.gate(bends[key(co)],key(co),neighbor)
        if len(nodes.get(key(co),[]))<3:return 0.
        # Keep paint clear of rounded junction footprints; never draw connectors here.
        touching=[max(w) if isinstance(w,(list,tuple)) else w for e,w in edges.items() if key(co) in e]
        overrides=point_settings.junction_overrides(obj).get(key(co),{})
        radius=max(overrides.get(c,values(obj)['corner '+c]) for c in ('NW','NE','SW','SE'))
        return max([width,*touching])/2+radius+1.
    def available(start,finish):
        neighbors=nodes.get(key(finish),set())
        return lane_logic.available_movements(key(start),key(finish),neighbors) if len(neighbors)>=3 else None
    plans=[];crossing_definitions=[];warnings=[];hidden=set(json.loads(obj.get('roadlab_hidden_lane_markings','[]')))
    for config in configs:
        a,b=config['endpoints']
        if a not in lookup or b not in lookup or frozenset((a,b)) not in valid:
            warnings.append('Lane assignment needs reselection after topology edit');continue
        ia,ib=lookup[a],lookup[b];pa,pb=tuple(points[ia].co[:3]),tuple(points[ib].co[:3]);width=min(point_settings.width(obj,ia,default),point_settings.width(obj,ib,default))
        try:validate_approach(obj,config['endpoints'],entries(config['incoming'],'i'),entries(config['outgoing'],'o'))
        except ValueError as error:warnings.append('Lane movements need review: '+str(error))
        try:
            delta=Vector(pb)-Vector(pa);length=hypot(delta.x,delta.y);cuts=[(0.,pa),(length,pb)]
            if length>1e-6:
                for junction,neighbors in nodes.items():
                    if len(neighbors)<3:continue
                    t=((junction[0]-pa[0])*delta.x+(junction[1]-pa[1])*delta.y)/(length*length)
                    candidate=Vector(pa)+delta*t
                    if 1e-6<t<1-1e-6 and (candidate-Vector(junction)).length<1e-5:cuts.append((length*t,junction))
            cuts.sort(key=lambda cut:cut[0])
            for part,((_,start),(_,finish)) in enumerate(zip(cuts,cuts[1:])):
                paint_settings={k:config.get(k,v) for k,v in [('crosswalk_incoming',False),('crosswalk_outgoing',False),('crosswalk_depth',3.048),('crosswalk_gap',1.),('crosswalk_ramp',1.9),('crosswalk_a',0.),('crosswalk_b',0.),('crosswalk_tactile',False),('arrow_approach',35.),('solid_approach',20.),('transition_length',30.),('stop_setback',1.22),('control_incoming','NONE'),('control_outgoing','NONE')]}
                if key(finish)!=key(pb):paint_settings['crosswalk_incoming']=False;paint_settings['control_incoming']='NONE'
                if key(start)!=key(pa):paint_settings['crosswalk_outgoing']=False;paint_settings['control_outgoing']='NONE'
                if key(finish) in stop_nodes:paint_settings['control_incoming']='STOP'
                if key(start) in stop_nodes:paint_settings['control_outgoing']='STOP'
                segment_plans=lane_markings.plan(start,finish,entries(config['incoming'],'i'),entries(config['outgoing'],'o'),width,side,config['median'],clearance(start,width,finish),clearance(finish,width,start),config['spacing'],**paint_settings,allowed_incoming=available(start,finish),allowed_outgoing=available(finish,start),junction_start=len(nodes.get(key(start),[]))>=3 or key(start) in stop_nodes,junction_end=len(nodes.get(key(finish),[]))>=3 or key(finish) in stop_nodes,emerging_incoming=[i for i,row in enumerate(config['incoming']) if row.get('entry')=='ADDED'],emerging_outgoing=[i for i,row in enumerate(config['outgoing']) if row.get('entry')=='ADDED'])
                for co,other in ((start,finish),(finish,start)):
                    if key(co) not in bends or key(co) in stop_nodes:continue
                    neighbor=max(nodes[key(co)],key=lambda n:(Vector(n)-Vector(co)).normalized().dot((Vector(other)-Vector(co)).normalized()))
                    u=Vector(neighbor)-Vector(co);u.z=0;u.normalize();normal=Vector((-u.y,u.x,0));seen=set();arm=[]
                    for mark in segment_plans:
                        role=mark['role'];family=role[0]
                        if family not in ('outer','center-yellow','median-yellow','center-white','divider'):continue
                        semantic=tuple(role[:3] if family=='divider' else role[:2])
                        if semantic in seen:continue
                        seen.add(semantic);lateral=(Vector(mark['center'])-Vector(co)).dot(normal)
                        arm.append(dict(family=family,flow=1 if Vector((*mark['forward'],0)).dot(u)>0 else -1,asset=mark['asset'],fraction=.5+lateral/(Vector(bends[key(co)][2][neighbor][-1])-Vector(bends[key(co)][2][neighbor][0])).length,width=mark['size'][0]))
                    bend_arms[(key(co),neighbor)]=arm
                for mark in segment_plans:
                    if mark['role'][0]=='crosswalk':
                        mark['source_endpoints']=config['endpoints'];crossing_definitions.append(mark)
                    mark['id']=hashlib.sha256(json.dumps([config['endpoints'],part,mark['role']],sort_keys=True).encode()).hexdigest()
                    if mark['id'] not in hidden:plans.append(mark)
        except ValueError as error:warnings.append(str(error))
    connectors,notes=lane_bends.connect(bends,bend_arms,hidden);plans.extend(connectors);warnings.extend(notes)
    obj['roadlab_generated_marking_catalog']=json.dumps(plans)
    from . import crosswalk_ramps
    crosswalk_ramps.rebuild(obj,scene,crossing_definitions)
    mesh=output.data;vs=[v.co.copy() for v in mesh.vertices];polys=[tuple(p.vertices) for p in mesh.polygons]
    bvh=BVHTree.FromPolygons(vs,polys);top=max((v.z for v in vs),default=0)+100;bottom=min((v.z for v in vs),default=0)-100
    terrain=scene.wb_native.terrain;terrain_tree=None
    if terrain is not None and any(m.get('on_terrain') for m in plans):
        helper=terrain.get('roadlab_core_terrain_mesh')
        mesh=helper.data if helper else terrain.data;matrix=obj.matrix_world.inverted()@(helper.matrix_world if helper else terrain.matrix_world)
        if mesh.polygons:
            terrain_vertices=[matrix@v.co for v in mesh.vertices]
            terrain_tree=BVHTree.FromPolygons(terrain_vertices,[tuple(p.vertices) for p in mesh.polygons])
            top=max(top,max(v.z for v in terrain_vertices)+100);bottom=min(bottom,min(v.z for v in terrain_vertices)-100)
    pad_tree=crosswalk_ramps.surface_tree(obj) if any(m.get('on_terrain') for m in plans) else None
    def surface(x,y,expected,on_terrain=False):
        if on_terrain and pad_tree is not None:
            hit,normal,face,distance=pad_tree.ray_cast(Vector((x,y,top)),Vector((0,0,-1)),top-bottom)
            if hit is not None:
                if normal.z<0:normal=-normal
                return (hit.x,hit.y,hit.z+.003)
        # At overpasses choose the nearest road elevation, not the topmost deck.
        hits=[];origin=top
        for _ in range(32):
            hit,normal,face,distance=(terrain_tree if on_terrain and terrain_tree is not None else bvh).ray_cast(Vector((x,y,origin)),Vector((0,0,-1)),origin-bottom)
            if hit is None:break
            hits.append((abs(hit.z-expected),hit,normal));origin=hit.z-.001
        if not hits:return None
        _,hit,normal=min(hits,key=lambda h:h[0])
        if normal.z<0:normal=-normal
        return tuple(hit+normal*.003)
    verts=[];faces=[];uvs=[];materials=[];slots=[]
    for marking in plans:
        if marking['asset'] not in slots:slots.append(marking['asset'])
        index=slots.index(marking['asset']);pv,pf,pu=lane_markings.patch_grid(marking);projected=[]
        for x,y,z in pv:
            projected.append(surface(x,y,z,marking.get('on_terrain',False)))
        for face in pf:
            if any(projected[i] is None for i in face):continue
            center=Vector(tuple(sum(pv[i][j] for i in face)/4 for j in range(3)))
            tree=terrain_tree if marking.get('on_terrain') and terrain_tree is not None else bvh
            if tree.ray_cast(Vector((center.x,center.y,top)),Vector((0,0,-1)),top-bottom)[0] is None:continue
            base=len(verts);verts.extend(projected[i] for i in face);uvs.extend(pu[i] for i in face);faces.append(tuple(range(base,base+4)));materials.append(index)
    data=bpy.data.meshes.new('RoadLab Lane Markings');data.from_pydata(verts,[],faces);data.update();uv=data.uv_layers.new(name='UVMap')
    uv.data.foreach_set('uv',[c for loop in data.loops for c in uvs[loop.vertex_index]])
    for asset in slots:data.materials.append(paint_material(asset))
    for p,index in zip(data.polygons,materials):p.material_index=index
    target=obj.get('roadlab_marking_object')
    if target is None or (target.get('roadlab_markings_owner_object')!=obj and target.get('roadlab_markings_owner')!=obj.name):
        target=bpy.data.objects.new('RoadLab Lane Markings',data);scene.collection.objects.link(target);obj['roadlab_marking_object']=target
    else:
        old=target.data;target.data=data
        if old.users==0:bpy.data.meshes.remove(old)
    target.matrix_world=obj.matrix_world.copy();target.hide_select=True;target['roadlab_markings_owner']=obj.name;target['roadlab_markings_owner_object']=obj
    obj['roadlab_marking_signature']=signature;obj['roadlab_marking_warnings']=json.dumps(warnings)

def selection_targets(context):
    obj=road(context);selected=set(point_settings.selected(context,obj));point_settings.sync(obj)
    ps=point_settings.points(obj);position=lambda i:tuple(round(float(v),6) for v in ps[i].co[:3])
    locations={position(i) for i in selected}
    # A logical junction can have one coincident control point per source spline.
    sel={i for i in range(len(ps)) if position(i) in locations};segs=segments(obj)
    if len(locations)==1:
        choices=[]
        for x,y,a,b in segs:
            if x in sel:choices.append([b,a])
            elif y in sel:choices.append([a,b])
        if len(choices)<2:raise ValueError('Select a connection point, or two adjacent points for a street section')
        return obj,choices,True
    targets=[(a,b,position(x),position(y)) for x,y,a,b in segs if x in sel and y in sel]
    if not targets:raise ValueError('Select two adjacent road points for a street section')
    connected={targets[0][2]}
    while True:
        new=connected|{v for a,b,x,y in targets if x in connected or y in connected for v in (x,y)}
        if new==connected:break
        connected=new
    if len(connected)!=len({v for a,b,x,y in targets for v in (x,y)}):raise ValueError('Choose one connected street section, or select just its junction')
    degree={v:sum(v in (x,y) for a,b,x,y in targets) for v in connected}
    if max(degree.values())>2:raise ValueError('To edit a branching selection, select its junction point only')
    ends=[v for v,n in degree.items() if n==1];current=targets[0][2] if not ends or targets[0][2] in ends else targets[0][3] if targets[0][3] in ends else ends[0]
    ordered=[];remaining=list(targets)
    while remaining:
        t=next(t for t in remaining if current in t[2:]);remaining.remove(t);a,b,x,y=t
        ordered.append([a,b] if x==current else [b,a]);current=y if x==current else x
    return obj,ordered,False


def set_draft(context,obj,targets,normalize=False):
    d=context.scene.roadlab_lane_draft;d.segment_key=obj.name;d.targets_json=json.dumps(targets);d.reverse=False
    d.incoming.clear();d.outgoing.clear();d.incoming_index=d.outgoing_index=0
    from .road_core import values
    lookup={x['id']:i for i,x in enumerate(point_settings.records(obj))}
    d.road_width=min(point_settings.width(obj,lookup[v],values(obj)['road width']) for t in targets for v in t)
    config=next((c for c in state(obj) if frozenset(c['endpoints'])==frozenset(targets[0])),None)
    if config:d.reverse=config['endpoints'][0]!=targets[0][0];d.median=config['median'];d.spacing=config['spacing']
    else:d.median=0.;d.spacing=18.
    for field,value in [('crosswalk_incoming',False),('crosswalk_outgoing',False),('crosswalk_depth',3.048),('crosswalk_gap',1.),('crosswalk_ramp',1.9),('crosswalk_a',0.),('crosswalk_b',0.),('crosswalk_tactile',False),('arrow_approach',35.),('solid_approach',20.),('lane_transition',30.),('transition_length',30.),('stop_setback',1.22),('control_incoming','NONE'),('control_outgoing','NONE')]:setattr(d,field,config.get(field,value) if config else value)
    for field in ('incoming','outgoing'):
        for row in (config[field] if config else [{'width':3.5,'movement':'THROUGH'}]):
            item=getattr(d,field).add();item.width=row['width'];item.movement=row['movement'];item.entry=row.get('entry','CONTINUOUS')
    if normalize and d.reverse:
        incoming,outgoing=rows(d.incoming),rows(d.outgoing);d.incoming.clear();d.outgoing.clear()
        for field,values in (('incoming',outgoing),('outgoing',incoming)):
            for row in values:
                item=getattr(d,field).add();item.width=row['width'];item.movement=row['movement'];item.entry=row.get('entry','CONTINUOUS')
        d.control_incoming,d.control_outgoing=d.control_outgoing,d.control_incoming
        d.crosswalk_incoming,d.crosswalk_outgoing=d.crosswalk_outgoing,d.crosswalk_incoming
        d.crosswalk_a,d.crosswalk_b=d.crosswalk_b,d.crosswalk_a
        d.reverse=False


def draft_target(context):
    obj=road(context);d=context.scene.roadlab_lane_draft;targets=json.loads(d.targets_json)
    if d.segment_key!=obj.name or not targets:raise ValueError('Open the lane window for your selection first')
    items=point_settings.records(obj);lookup={x['id']:i for i,x in enumerate(items)};valid={frozenset((a,b)) for _,_,a,b in segments(obj)}
    if any(frozenset(t) not in valid for t in targets):raise ValueError('Road topology changed; reopen the lane window')
    indices=sorted({lookup[v] for t in targets for v in t})
    return obj,indices,targets


class ROADLAB_OT_lane_edit(bpy.types.Operator):
    bl_idname='roadlab.lane_edit';bl_label='Open lane window';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        bpy.ops.roadlab.lane_window('INVOKE_DEFAULT');return {'FINISHED'}

class ROADLAB_OT_lane_count(bpy.types.Operator):
    bl_idname='roadlab.lane_count';bl_label='Change lane count';bl_options={'REGISTER','UNDO'}
    direction:EnumProperty(items=[('incoming','Incoming',''),('outgoing','Outgoing','')])
    delta:IntProperty(default=1)
    def execute(self,context):
        items=getattr(context.scene.roadlab_lane_draft,self.direction)
        d=context.scene.roadlab_lane_draft;field=self.direction+'_index'
        if self.delta>0 and len(items)<7:items.add();setattr(d,field,len(items)-1)
        elif self.delta<0 and len(items)>0:
            index=min(getattr(d,field),len(items)-1);items.remove(index);setattr(d,field,max(0,min(index,len(items)-1)))
        return {'FINISHED'}

def validate_approach(obj,endpoints,incoming,outgoing):
    """Reject turns toward missing branches; no simulated right-of-way claims."""
    from .road_core import graph,values,key
    from math import atan2,degrees
    ps=point_settings.points(obj);lookup={x['id']:i for i,x in enumerate(point_settings.records(obj))};paths=[]
    for spl in obj.data.splines:
        coords=[tuple(p.co[:3]) for p in spl.points]
        if spl.use_cyclic_u and coords:coords.append(coords[0])
        paths.append((coords,[1.]*len(coords)))
    nodes,edges,_=graph(paths,values(obj)['road width'])
    errors=[]
    for ids,lanes in ((endpoints,incoming),(endpoints[::-1],outgoing)):
        a,b=(key(tuple(ps[lookup[x]].co[:3])) for x in ids);neighbors=nodes.get(b,set())
        if len(neighbors)<3:continue
        available=lane_logic.available_movements(a,b,neighbors)
        left=sum('LEFT' in lane.movements for lane in lanes);right=sum('RIGHT' in lane.movements for lane in lanes)
        if lanes:errors+=lane_logic.validate_lanes(lanes,available,left,right)
    if errors:raise ValueError('; '.join(errors))


DRAFT_FIELDS=('segment_key','targets_json','reverse','road_width','median','spacing','crosswalk_incoming','crosswalk_outgoing','crosswalk_depth','crosswalk_gap','crosswalk_ramp','crosswalk_a','crosswalk_b','crosswalk_tactile','arrow_approach','solid_approach','lane_transition','transition_length','stop_setback','control_incoming','control_outgoing')

def draft_snapshot(d):
    return dict({k:getattr(d,k) for k in DRAFT_FIELDS},incoming=rows(d.incoming),outgoing=rows(d.outgoing))

def restore_draft(d,data):
    for k in DRAFT_FIELDS:setattr(d,k,data[k])
    for field in ('incoming','outgoing'):
        getattr(d,field).clear()
        for row in data[field]:
            item=getattr(d,field).add();item.width=row['width'];item.movement=row['movement'];item.entry=row.get('entry','CONTINUOUS')
        setattr(d,field+'_index',0)

def checked_drafts(context,drafts):
    from math import isfinite
    obj=road(context);lookup={x['id']:i for i,x in enumerate(point_settings.records(obj))}
    valid={frozenset((a,b)) for _,_,a,b in segments(obj)};result=[]
    for data in drafts:
        targets=json.loads(data['targets_json'])
        if data['segment_key']!=obj.name or not targets or any(frozenset(t) not in valid for t in targets):raise ValueError('Road topology changed; reopen the lane editor')
        if not len(data['incoming'])+len(data['outgoing']):raise ValueError('Add at least one lane')
        needed=lane_logic.road_width(entries(data['incoming'],'i'),entries(data['outgoing'],'o'),data['median'])[1]
        if not isfinite(data['road_width']):raise ValueError('Road width must be finite')
        for row in data['incoming']+data['outgoing']:lane_markings.arrow_id(row['movement'].split('_'))
        for t in targets:validate_approach(obj,t[::-1] if data['reverse'] else t,entries(data['incoming'],'i'),entries(data['outgoing'],'o'))
        result.append((data,targets,sorted({lookup[v] for t in targets for v in t}),needed))
    return obj,result

class ROADLAB_OT_lane_apply(bpy.types.Operator):
    bl_idname='roadlab.lane_apply';bl_label='Apply lanes and markings';bl_options={'REGISTER','UNDO'}
    expand:BoolProperty(name='Expand road to fit',default=False)
    batch_json:StringProperty(default='',options={'HIDDEN'})
    def drafts(self,context):return json.loads(self.batch_json) if self.batch_json else [draft_snapshot(context.scene.roadlab_lane_draft)]
    def required(self,context):
        d=context.scene.roadlab_lane_draft
        return lane_logic.road_width(entries(rows(d.incoming),'i'),entries(rows(d.outgoing),'o'),d.median)[1]
    def invoke(self,context,event):
        self.expand=False
        try:
            obj,checked=checked_drafts(context,self.drafts(context))
            if any(needed>data['road_width']+1e-6 for data,_,_,needed in checked):
                self.expand=True
                return context.window_manager.invoke_props_dialog(self,width=390,confirm_text='Expand roads & apply')
        except ValueError as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return self.execute(context)
    def draw(self,context):
        self.layout.label(text='More space is needed for these lanes',icon='INFO')
        for data,_,_,needed in checked_drafts(context,self.drafts(context))[1]:
            if needed>data['road_width']+1e-6:self.layout.label(text=f"{data.get('label','Selected road')}: {data['road_width']:.1f} m → {needed:.1f} m")
        self.layout.label(text='Cancel keeps the roads unchanged.')
    def execute(self,context):
        try:
            obj,checked=checked_drafts(context,self.drafts(context))
            if any(needed>data['road_width']+1e-6 for data,_,_,needed in checked) and not self.expand:raise ValueError('Road too narrow. Enable expansion to apply these lanes.')
            # Validate every edited arm before changing any road data.
            items=point_settings.sync(obj);configs=state(obj);widths={}
            for data,targets,indices,needed in checked:
                desired=max(data['road_width'],needed) if self.expand else data['road_width']
                for i in indices:widths[i]=max(widths.get(i,0),desired)
                configs=[c for c in configs if all(frozenset(c['endpoints'])!=frozenset(t) for t in targets)]
                for t in targets:
                    configs.append(dict(endpoints=t[::-1] if data['reverse'] else t,incoming=data['incoming'],outgoing=data['outgoing'],**{k:data[k] for k in ('median','spacing','crosswalk_incoming','crosswalk_outgoing','crosswalk_depth','crosswalk_gap','crosswalk_ramp','crosswalk_a','crosswalk_b','crosswalk_tactile','arrow_approach','solid_approach','lane_transition','transition_length','stop_setback','control_incoming','control_outgoing')}))
            for data,_,_,_ in checked:
                if data.get('_connection_node') is not None:
                    for row in items:
                        if all(abs(a-b)<1e-5 for a,b in zip(row['co'],data['_connection_node'])):row['connection_mode']=data['_connection_mode']
            for i,width in widths.items():items[i]['width']=width
            point_settings.save(obj,items);obj['roadlab_lanes']=json.dumps(configs)
            context.scene.roadlab_lane_draft.road_width=max(context.scene.roadlab_lane_draft.road_width,self.required(context)) if self.expand else context.scene.roadlab_lane_draft.road_width
            from .selected_points import notify
            notify(context,obj);rebuild(obj,context.scene)
        except ValueError as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return {'FINISHED'}

class ROADLAB_OT_lane_remove(bpy.types.Operator):
    bl_idname='roadlab.lane_remove';bl_label='Clear saved lane setup';bl_options={'REGISTER','UNDO'}
    def invoke(self,context,event):return context.window_manager.invoke_confirm(self,event)
    def execute(self,context):
        try:
            obj,indices,targets=draft_target(context);obj['roadlab_lanes']=json.dumps([c for c in state(obj) if all(frozenset(c['endpoints'])!=frozenset(t) for t in targets)]);rebuild(obj,context.scene,True)
        except ValueError as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return {'FINISHED'}

class ROADLAB_UL_lanes(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        row=layout.row(align=True);row.label(text=str(index+1));row.prop(item,'movement',text='',emboss=True);row.prop(item,'width',text='',emboss=True)


def section(l,d,flag,label,summary=''):
    box=l.box();row=box.row(align=True);opened=getattr(d,flag)
    row.prop(d,flag,text=label,icon='TRIA_DOWN' if opened else 'TRIA_RIGHT',emboss=False)
    if summary:row.label(text=summary)
    return box if opened else None


def draw_lanes(l,context,junction=False,connection_mode=None):
    d=context.scene.roadlab_lane_draft
    required=lane_logic.road_width(entries(rows(d.incoming),'i'),entries(rows(d.outgoing),'o'),d.median)[1]
    l.prop(d,'page',expand=True)
    if d.page=='LANES':
        row=l.row(align=True)
        row.prop_enum(d,'travel','incoming',text='Arriving' if junction else 'Toward end')
        row.prop_enum(d,'travel','outgoing',text='Leaving' if junction else 'Toward start')
        field=d.travel;items=getattr(d,field)
        label=('Arriving at junction' if field=='incoming' else 'Leaving junction') if junction else ('Toward section end' if field=='incoming' else 'Toward section start')
        box=section(l,d,'show_'+field,label,f'{len(items)} lanes')
        if box:
            row=box.row(align=True);row.label(text='Lane count')
            for delta,icon in [(-1,'REMOVE'),(1,'ADD')]:
                button=row.row();button.enabled=len(items)<7 if delta>0 else len(items)>0
                op=button.operator('roadlab.lane_count',text='',icon=icon);op.direction=field;op.delta=delta
            if items:
                box.label(text='Lane order: driver’s left → right')
                header=box.row();header.label(text='Lane');header.label(text='Movement');header.label(text='Width (m)')
                box.template_list('ROADLAB_UL_lanes',field,d,field,d,field+'_index',rows=min(7,max(1,len(items))),maxrows=7)
                if getattr(d,field+'_index')<len(items):
                    detail=section(box,d,'show_lane_details','Selected lane details')
                    if detail:
                        detail.prop(items[getattr(d,field+'_index')],'entry',text='Entry')
                        detail.label(text='Added lane paints entry dots.')
                        detail.label(text='Edit the road shape separately.')
            else:box.label(text='No lanes in this direction. Use + to add one.')
        l.label(text=f"Road total: {len(d.incoming)} arriving · {len(d.outgoing)} leaving" if junction else f"Road total: {len(d.incoming)} toward end · {len(d.outgoing)} toward start")
    elif d.page=='MARKINGS':
        box=section(l,d,'show_arrows','Direction arrows')
        if box:box.prop(d,'arrow_approach',text='Before junction (m)');box.prop(d,'spacing',text='Repeat spacing (m)');box.label(text='Set distance to 0 to turn off automatic arrows.')
        box=section(l,d,'show_dividers','Lane lines')
        if box:
            box.prop(d,'solid_approach',text='Solid before junction (m)')
            box.prop(d,'lane_transition',text='Lane merge length (m)')
            box.prop(d,'transition_length',text='Added-lane dots (m)')
        box=section(l,d,'show_crosswalks','Crosswalk')
        if box:
            box.prop(d,'crosswalk_incoming',text='Crosswalk here' if junction else 'At section end')
            if not junction:box.prop(d,'crosswalk_outgoing',text='At section start')
            if d.crosswalk_incoming or (not junction and d.crosswalk_outgoing):
                box.prop(d,'crosswalk_depth',text='Crossing width (m)');box.prop(d,'crosswalk_gap',text='Gap from junction (m)')
                box.prop(d,'crosswalk_a',text='A-end position (m)');box.prop(d,'crosswalk_b',text='B-end position (m)');box.prop(d,'crosswalk_tactile')
                box.label(text='Positive moves away from the junction.')
                box.prop(d,'crosswalk_ramp',text='Ramp run (m)')
                box.label(text='Ramps adapt existing curb and sidewalk layers.')
                box.label(text='Pads follow the sidewalk or assigned terrain.')
        box=section(l,d,'show_stops','Stop line')
        if box:
            if connection_mode is not None:
                box.label(text='Controlled by the Connection setting above.')
                if connection_mode=='STOP':box.prop(d,'stop_setback',text='Setback (m)')
            else:
                box.prop(d,'control_incoming',text='Arrivals here' if junction else 'At section end')
                if not junction:box.prop(d,'control_outgoing',text='At section start')
                if d.control_incoming in {'STOP','SIGNAL'} or (not junction and d.control_outgoing in {'STOP','SIGNAL'}):box.prop(d,'stop_setback',text='Setback (m)')
                box.label(text='Stop and signal controls paint an arrival stop line.')
    else:
        box=section(l,d,'show_size','Width and median',f'{d.road_width:.1f} m')
        if box:
            box.prop(d,'road_width',text='Total width (m)');box.prop(d,'median',text='Median width (m)')
            box.label(text=f'Lanes need {required:.1f} m including shoulders.')
            box.label(text='Extra width becomes shoulder space.')
            if not junction:box.prop(d,'reverse',text='Swap travel directions')
        box=section(l,d,'show_saved','Saved setup')
        if box:box.operator('roadlab.lane_remove',text='Clear saved lane setup',icon='TRASH')
    if required>d.road_width+1e-6:l.label(text=f'Apply will ask to widen this road to {required:.1f} m.',icon='INFO')



_approach_enum_cache={}
_approach_preview=None
_crosswalk_labels=None

def approach_geometry(obj,choices):
    lookup={x['id']:i for i,x in enumerate(point_settings.records(obj))};ps=point_settings.points(obj)
    return [(obj.matrix_world@Vector(ps[lookup[a]].co[:3]),obj.matrix_world@Vector(ps[lookup[b]].co[:3])) for a,b in choices]

def approach_labels(geometry):
    from math import atan2,degrees
    names=['East','Northeast','North','Northwest','West','Southwest','South','Southeast']
    directions=[names[int((degrees(atan2(a.y-b.y,a.x-b.x))%360+22.5)//45)%8] for a,b in geometry]
    return [(direction+' road'+(f' ({a.x-b.x:+.0f} X, {a.y-b.y:+.0f} Y)' if directions.count(direction)>1 else ''),
             f'Traffic arriving from {direction.lower()} toward this junction') for direction,(a,b) in zip(directions,geometry)]

def approach_items(self,context):
    choices=json.loads(self.choices_json)
    if not choices:return [('0','Section','')]
    geometry=approach_geometry(road(context),choices)
    result=[(str(i),name,hint) for i,(name,hint) in enumerate(approach_labels(geometry))]
    # Blender keeps pointers to enum strings, so retain them for the popup lifetime.
    key=(road(context).as_pointer(),self.choices_json,tuple(name for _,name,_ in result))
    _approach_enum_cache[key]=result
    return _approach_enum_cache[key]

def clear_approach_preview():
    global _approach_preview,_crosswalk_labels
    if _crosswalk_labels is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_crosswalk_labels,'WINDOW');_crosswalk_labels=None
    if _approach_preview is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_approach_preview,'WINDOW');_approach_preview=None
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()

def show_approach_preview(operator,obj):
    global _approach_preview,_crosswalk_labels
    clear_approach_preview()
    def draw():
        import gpu
        from gpu_extras.batch import batch_for_shader
        try:geometry=approach_geometry(obj,json.loads(operator.choices_json));selected=int(operator.approach)
        except (ReferenceError,ValueError,KeyError):return
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');gpu.state.depth_test_set('NONE');gpu.state.line_width_set(4)
        try:
            for i,(a,b) in enumerate(geometry):
                # A short centerline guide distinguishes the selected arm without altering the road.
                end=b+(a-b)*.65
                batch=batch_for_shader(shader,'LINES',{'pos':[tuple(b),tuple(end)]})
                shader.bind();shader.uniform_float('color',(1.,.55,.05,1.) if i==selected else (.15,.65,.85,.5));batch.draw(shader)
        finally:gpu.state.line_width_set(1);gpu.state.depth_test_set('NONE')
    _approach_preview=bpy.types.SpaceView3D.draw_handler_add(draw,(),'WINDOW','POST_VIEW')
    def labels():
        import blf
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        session=_lane_preview
        if session is None or session.get('proxy') is None:return
        try:
            choices=json.loads(operator.choices_json);target=choices[int(operator.approach)] if operator.is_junction else None
            seen=set()
            for mark in json.loads(session['proxy'].get('roadlab_generated_marking_catalog','[]')):
                if 'crosswalk_ends' not in mark:continue
                if target is not None and frozenset(mark.get('source_endpoints',[]))!=frozenset(target):continue
                ident=(tuple(mark.get('source_endpoints',[])),mark['role'][1])
                if ident in seen:continue
                seen.add(ident)
                for text,co in zip(('A','B'),mark['crosswalk_ends']):
                    pixel=location_3d_to_region_2d(bpy.context.region,bpy.context.space_data.region_3d,obj.matrix_world@Vector(co))
                    if pixel is None:continue
                    blf.size(0,18);blf.color(0,1.,.6,.1,1.);blf.position(0,pixel.x+8,pixel.y+8,0);blf.draw(0,text)
        except (ReferenceError,AttributeError,ValueError):return
    _crosswalk_labels=bpy.types.SpaceView3D.draw_handler_add(labels,(),'WINDOW','POST_PIXEL')


def save_active_approach(self,context):
    drafts=json.loads(getattr(self,'drafts_json','{}'));key=getattr(self,'active_approach','')
    if key:
        data=draft_snapshot(context.scene.roadlab_lane_draft)
        choices=json.loads(self.choices_json);data['label']=approach_labels(approach_geometry(road(context),choices))[int(key)][0]
        drafts[key]=data;self.drafts_json=json.dumps(drafts)
    return drafts

def approach_changed(self,context):
    choices=json.loads(self.choices_json)
    if choices and self.is_junction:
        drafts=save_active_approach(self,context);key=self.approach
        if key in drafts:restore_draft(context.scene.roadlab_lane_draft,drafts[key])
        else:set_draft(context,road(context),[choices[int(key)]],normalize=True)
        self.active_approach=key
        for area in context.screen.areas if context.screen else []:
            if area.type=='VIEW_3D':area.tag_redraw()


# Preview uses an unlinked source copy and its own marking mesh. Committed lane
# settings, pavement, terrain and manual stamps are never changed by the timer.
_lane_preview=None

def stop_lane_preview():
    global _lane_preview
    session=_lane_preview;_lane_preview=None
    if bpy.app.timers.is_registered(tick_lane_preview):bpy.app.timers.unregister(tick_lane_preview)
    if not session:return
    for target,hidden in session['hidden']:
        try:target.hide_set(hidden)
        except ReferenceError:pass
    proxy=session.get('proxy')
    if proxy is not None:
        try:
            from . import crosswalk_ramps
            crosswalk_ramps.cleanup(proxy)
            marking=proxy.get('roadlab_marking_object')
            if marking is not None:
                mesh=marking.data;bpy.data.objects.remove(marking,do_unlink=True)
                if mesh.users==0:bpy.data.meshes.remove(mesh)
            bpy.data.objects.remove(proxy,do_unlink=True)
        except ReferenceError:pass

def start_lane_preview(operator,context):
    global _lane_preview
    stop_lane_preview()
    _lane_preview={'operator':operator,'scene':context.scene,'road':road(context),'signature':None,'proxy':None,'hidden':[]}
    bpy.app.timers.register(tick_lane_preview,first_interval=.1)

def preview_batch(operator,scene):
    drafts=json.loads(operator.drafts_json) if operator.is_junction else {}
    current=draft_snapshot(scene.roadlab_lane_draft)
    if drafts or operator.is_junction:drafts[operator.active_approach]=current
    batch=list(drafts.values()) if drafts else [current]
    node=getattr(operator,'connection_node','')
    if node:
        # A two-arm connection is one operation. Preserve an existing opposite
        # profile, or continue the current street profile when it has none yet.
        obj=scene.wb_native.road
        for index,target in enumerate(json.loads(operator.choices_json)):
            if any(frozenset(json.loads(data['targets_json'])[0])==frozenset(target) for data in batch):continue
            data=json.loads(json.dumps(current));data['targets_json']=json.dumps([target]);data['reverse']=False
            saved=next((c for c in state(obj) if frozenset(c['endpoints'])==frozenset(target)),None)
            if saved:
                for field in ('median','spacing','crosswalk_incoming','crosswalk_outgoing','crosswalk_depth','crosswalk_gap','crosswalk_ramp','crosswalk_a','crosswalk_b','crosswalk_tactile','arrow_approach','solid_approach','lane_transition','transition_length','stop_setback','control_incoming','control_outgoing'):data[field]=saved.get(field,data[field])
                reverse=saved['endpoints']!=target
                data['incoming']=saved['outgoing' if reverse else 'incoming'];data['outgoing']=saved['incoming' if reverse else 'outgoing']
                if reverse:
                    data['control_incoming'],data['control_outgoing']=data['control_outgoing'],data['control_incoming']
                    data['crosswalk_incoming'],data['crosswalk_outgoing']=saved.get('crosswalk_outgoing',False),saved.get('crosswalk_incoming',False)
                    data['crosswalk_a'],data['crosswalk_b']=saved.get('crosswalk_b',0.),saved.get('crosswalk_a',0.)
            else:data['incoming'],data['outgoing']=data['outgoing'],data['incoming']
            batch.append(data)
        for data in batch:data['_connection_node']=json.loads(node);data['_connection_mode']=operator.connection_mode
    return batch

def tick_lane_preview():
    session=_lane_preview
    if session is None:return None
    try:
        operator=session['operator'];obj=session['road'];scene=session['scene']
        batch=preview_batch(operator,scene)
        signature=json.dumps([batch,obj.get('roadlab_core_signature'),getattr(scene.wb_native.terrain,'get',lambda *args:None)('roadlab_core_terrain_signature'),scene.roadlab_map_settings.traffic_side],sort_keys=True)
        if signature==session['signature']:return .12
        session['signature']=signature
        context=type('PreviewContext',(),{'scene':scene,'edit_object':obj,'active_object':obj})()
        _,checked=checked_drafts(context,batch)
        from .road_core import values
        default=values(obj)['road width']
        if any(needed>min(point_settings.width(obj,i,default) for i in indices)+1e-6 for data,targets,indices,needed in checked):
            operator.preview_status='Preview needs a wider road. Apply to review expansion.';return .12
        configs=state(obj)
        for data,targets,indices,needed in checked:
            configs=[c for c in configs if all(frozenset(c['endpoints'])!=frozenset(t) for t in targets)]
            for t in targets:configs.append(dict(endpoints=t[::-1] if data['reverse'] else t,incoming=data['incoming'],outgoing=data['outgoing'],**{k:data[k] for k in ('median','spacing','crosswalk_incoming','crosswalk_outgoing','crosswalk_depth','crosswalk_gap','crosswalk_ramp','crosswalk_a','crosswalk_b','crosswalk_tactile','arrow_approach','solid_approach','lane_transition','transition_length','stop_setback','control_incoming','control_outgoing')}))
        proxy=session['proxy']
        if proxy is None:
            proxy=obj.copy();proxy.name='RoadLab Preview Source';session['proxy']=proxy
            if 'roadlab_marking_object' in proxy:del proxy['roadlab_marking_object']
            if 'roadlab_crosswalk_guide' in proxy:del proxy['roadlab_crosswalk_guide']
            proxy['roadlab_preview_source']=obj
            proxy['roadlab_new_core']=False
        proxy['roadlab_lanes']=json.dumps(configs)
        preview_records=point_settings.records(obj)
        for data in batch:
            if data.get('_connection_node') is not None:
                for row in preview_records:
                    if all(abs(a-b)<1e-5 for a,b in zip(row['co'],data['_connection_node'])):row['connection_mode']=data['_connection_mode']
        proxy['roadlab_point_settings']=json.dumps(preview_records)
        proxy['roadlab_core_mesh']=obj['roadlab_core_mesh'];proxy['roadlab_core_signature']=obj.get('roadlab_core_signature','')
        proxy.matrix_world=obj.matrix_world.copy();rebuild(proxy,scene,True)
        target=proxy.get('roadlab_marking_object')
        if target is not None:
            target.name='RoadLab Marking Preview';target.hide_render=True;target['roadlab_temporary_preview']=True
            original=obj.get('roadlab_marking_object')
            if original is not None and all(item[0]!=original for item in session['hidden']):
                session['hidden'].append((original,original.hide_get()));original.hide_set(True)
        operator.preview_status='Live preview · Apply saves changes'
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':area.tag_redraw()
    except (ReferenceError,AttributeError):
        stop_lane_preview();return None
    except (ValueError,KeyError,RuntimeError) as error:
        try:session['operator'].preview_status='Preview unavailable: '+str(error)
        except ReferenceError:stop_lane_preview();return None
    return .12

@bpy.app.handlers.persistent
def preview_before_save(*args):
    # Never serialize temporary preview meshes or viewport hiding into a .blend.
    if _lane_preview is not None:
        session=_lane_preview.copy();stop_lane_preview()
        global _preview_resume
        _preview_resume=session

_preview_resume=None

@bpy.app.handlers.persistent
def preview_after_save(*args):
    global _lane_preview,_preview_resume
    if _preview_resume is not None:
        session=_preview_resume;_preview_resume=None
        session.update(signature=None,proxy=None,hidden=[]);_lane_preview=session
        bpy.app.timers.register(tick_lane_preview,first_interval=.1)

@bpy.app.handlers.persistent
def preview_before_load(*args):
    global _preview_resume
    _preview_resume=None;stop_lane_preview();clear_approach_preview()

def apply_window_edits(self,context,expand=False):
    try:
        drafts=save_active_approach(self,context) if self.is_junction else {}
        batch=preview_batch(self,context.scene)
        obj,checked=checked_drafts(context,batch)
        needs=[(data,needed) for data,_,_,needed in checked if needed>data['road_width']+1e-6]
        if expand and json.dumps(batch)!=self.expansion_batch:expand=False
        if needs and not expand:
            self.expansion_text=json.dumps([(data.get('label','Selected road'),data['road_width'],needed) for data,needed in needs])
            self.expansion_batch=json.dumps(batch);self.apply_status='Review road expansion below.';return
        result=bpy.ops.roadlab.lane_apply('EXEC_DEFAULT',batch_json=json.dumps(batch),expand=expand)
        if result!={'FINISHED'}:self.apply_status='Changes were not applied. Review the lane setup.';return
        if expand:
            for data,_,_,needed in checked:data['road_width']=max(data['road_width'],needed)
            if drafts:
                for data in drafts.values():
                    match=next(row for row,_,_,_ in checked if row['targets_json']==data['targets_json'])
                    data['road_width']=match['road_width']
                self.drafts_json=json.dumps(drafts)
        self.expansion_text='[]';self.apply_status='Applied. Further edits need Apply.'
        if _lane_preview is not None:_lane_preview['signature']=None
    except (ValueError,RuntimeError) as error:self.apply_status=str(error).removeprefix('Error: ').strip()

def apply_clicked(self,context):
    if self.apply_action:
        self.apply_action=False;apply_window_edits(self,context)

def expansion_clicked(self,context):
    if self.expand_action:
        self.expand_action=False;apply_window_edits(self,context,expand=True)

def expansion_cancelled(self,context):
    if self.keep_width_action:
        self.keep_width_action=False;self.expansion_text='[]';self.apply_status='Road widths kept. Adjust your lanes, then Apply.'


class ROADLAB_OT_lane_window(bpy.types.Operator):
    bl_idname='roadlab.lane_window';bl_label='Lane editor';bl_options={'REGISTER','UNDO'}
    choices_json:StringProperty(default='[]',options={'HIDDEN'})
    drafts_json:StringProperty(default='{}',options={'HIDDEN'})
    active_approach:StringProperty(default='',options={'HIDDEN'})
    has_selection:BoolProperty(default=False,options={'HIDDEN'})
    selection_hint:StringProperty(default='',options={'HIDDEN'})
    is_junction:BoolProperty(default=False,options={'HIDDEN'})
    junction_label:StringProperty(default='Junction',options={'HIDDEN'})
    connection_node:StringProperty(default='',options={'HIDDEN'})
    connection_mode:EnumProperty(name='Connection',items=[('CONTINUOUS','Continuous street','Lane lines continue through this vertex'),('STOP','Stop-controlled','Terminate lines at both road ends and add arrival stop lines')],default='CONTINUOUS')
    approach:EnumProperty(name='Approach',items=approach_items,update=approach_changed)
    apply_action:BoolProperty(default=False,update=apply_clicked,options={'SKIP_SAVE'})
    expand_action:BoolProperty(default=False,update=expansion_clicked,options={'SKIP_SAVE'})
    keep_width_action:BoolProperty(default=False,update=expansion_cancelled,options={'SKIP_SAVE'})
    expansion_text:StringProperty(default='[]',options={'HIDDEN'})
    expansion_batch:StringProperty(default='[]',options={'HIDDEN'})
    apply_status:StringProperty(default='',options={'HIDDEN'})
    preview_status:StringProperty(default='',options={'HIDDEN'})
    def invoke(self,context,event):
        stop_lane_preview();clear_approach_preview();self.drafts_json='{}';self.active_approach='';self.expansion_text='[]';self.apply_status='';self.connection_node=''
        d=context.scene.roadlab_lane_draft;d.page='LANES';d.travel='incoming'
        for flag in ('show_size','show_incoming','show_outgoing','show_markings','show_arrows','show_dividers','show_stops','show_crosswalks','show_lane_details','show_saved'):setattr(d,flag,False)
        try:
            obj,targets,junction=selection_targets(context);context.scene.wb_native.road=obj;self.has_selection=True;self.choices_json=json.dumps(targets);self.is_junction=junction
            set_draft(context,obj,[targets[0]] if junction else targets,normalize=junction)
            if junction:
                from .junction_layout import from_selection
                if len(targets)==2:
                    self.junction_label='Street connection'
                    indices=point_settings.selected(context,obj);co=tuple(round(v,6) for v in point_settings.points(obj)[indices[0]].co[:3]);self.connection_node=json.dumps(co)
                    self.connection_mode=next((row.get('connection_mode','CONTINUOUS') for row in point_settings.records(obj) if tuple(row['co'])==co),'CONTINUOUS')
                else:self.junction_label=from_selection(context)['kind'].replace('_',' ').title()
                self.approach='0';self.active_approach='0'
        except (ValueError,AttributeError) as e:
            self.has_selection=False;self.selection_hint=str(e);self.choices_json='[]';self.is_junction=False
        if self.has_selection:
            start_lane_preview(self,context)
            if getattr(context,'area',None) and context.area.type=='VIEW_3D':show_approach_preview(self,obj)
        return context.window_manager.invoke_props_dialog(self,width=520,confirm_text='Done' if self.has_selection else 'Close')
    def check(self,context):return True
    def draw(self,context):
        l=self.layout
        if not self.has_selection:
            l.label(text='Choose what to edit',icon='INFO')
            l.label(text=self.selection_hint)
            box=l.box();box.label(text='1. Select a RoadLab road and enter Edit Mode (Tab).')
            box.label(text='2. Connection or junction: select its shared point.')
            box.label(text='   Street: select two or more adjacent curve points.')
            box.label(text='3. Open the lane window to edit the selection.')
            l.label(text='Shift-click adds points. Existing selections are kept.')
            return
        if self.is_junction:
            l.label(text=f'{self.junction_label} · {len(json.loads(self.choices_json))} roads')
            if self.connection_node:l.prop(self,'connection_mode')
            l.prop(self,'approach',text='Edit road from')
            l.label(text='Selected road is orange in the viewport',icon='INFO')
            l.label(text='Switch roads freely. Apply saves your edited roads together.')
        else:
            l.label(text=f'{len(json.loads(self.choices_json))} selected street segment(s)')
            obj,indices,targets=draft_target(context);lookup={x['id']:i for i,x in enumerate(point_settings.records(obj))};ps=point_settings.points(obj);endpoint=targets[0][0] if context.scene.roadlab_lane_draft.reverse else targets[-1][1];co=obj.matrix_world@Vector(ps[lookup[endpoint]].co[:3]);l.label(text=f'Incoming toward ({co.x:.1f}, {co.y:.1f})')
        draw_lanes(l,context,self.is_junction,self.connection_mode if self.connection_node else None)
        l.separator();l.label(text='Traffic keeps '+context.scene.roadlab_map_settings.traffic_side.lower()+' · map setting')
        l.label(text=self.preview_status or 'Preparing live preview…',icon='SHADING_RENDERED')
        l.prop(self,'apply_action',text='Apply lanes',icon='CHECKMARK',toggle=True)
        expansion=json.loads(self.expansion_text)
        if expansion:
            box=l.box();box.label(text='Expand roads to fit these lanes?',icon='QUESTION')
            for name,current,needed in expansion:box.label(text=f'{name}: {current:.1f} m → {needed:.1f} m')
            row=box.row(align=True);row.prop(self,'keep_width_action',text='Keep current widths',toggle=True);row.prop(self,'expand_action',text='Expand & apply',toggle=True)
        if self.apply_status:
            from textwrap import wrap
            for line in wrap(self.apply_status,64):l.label(text=line,icon='INFO')
        l.label(text='Apply saves without closing.')
        l.label(text='Done closes; unapplied changes are discarded.')
    def cancel(self,context):stop_lane_preview();clear_approach_preview()
    def execute(self,context):
        stop_lane_preview();clear_approach_preview()
        return {'FINISHED'}



class ROADLAB_OT_lane_pick(bpy.types.Operator):
    bl_idname='roadlab.lane_pick';bl_label='Select lanes';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):
        try:return context.mode=='EDIT_CURVE' and context.edit_object==road(context)
        except (ValueError,AttributeError):return False
    def invoke(self,context,event):
        obj=road(context);selected=point_settings.selected(context,obj)
        if event.shift or not selected:
            bpy.ops.view3d.select('EXEC_DEFAULT',location=(event.mouse_region_x,event.mouse_region_y),extend=event.shift)
        if event.shift:return {'FINISHED'}
        try:bpy.ops.roadlab.lane_window('INVOKE_DEFAULT')
        except RuntimeError as error:self.report({'INFO'},str(error));return {'CANCELLED'}
        return {'FINISHED'}


class ROADLAB_WST_lanes(bpy.types.WorkSpaceTool):
    bl_space_type='VIEW_3D';bl_context_mode='EDIT_CURVE';bl_idname='roadlab.lanes'
    bl_label='Lanes';bl_description='Click a junction, or Shift-select a street section then click to open its lane editor'
    bl_icon=str(lane_markings.ROOT.parent.parent/'icons'/'lanes');bl_widget=None
    bl_keymap=(('roadlab.lane_pick',{'type':'LEFTMOUSE','value':'PRESS','shift':True},{}),('roadlab.lane_pick',{'type':'LEFTMOUSE','value':'PRESS'},{}))
    @staticmethod
    def draw_settings(context,layout,tool):
        layout.label(text='Shift-click: select section | Click: lane window')
        layout.operator('roadlab.lane_window',text='Open lanes')


class ROADLAB_PT_lanes(bpy.types.Panel):
    bl_label='Lanes';bl_idname='ROADLAB_PT_lanes';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return ROADLAB_OT_lane_pick.poll(context)
    def draw(self,context):
        self.layout.operator('wm.tool_set_by_id',text='Lane toolbar tool').name='roadlab.lanes'
        self.layout.operator('roadlab.lane_window',text='Open lane window')
        for warning in json.loads(road(context).get('roadlab_marking_warnings','[]')):self.layout.label(text=warning,icon='ERROR')

def refresh_loaded_markings():
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if obj.type=='CURVE' and obj.get('roadlab_new_core') and 'roadlab_lanes' in obj:
                if 'roadlab_lane_known_points' not in obj:obj['roadlab_lane_known_points']=json.dumps(sorted(row['id'] for row in point_settings.records(obj)))
                try:rebuild(obj,scene)
                except Exception as error:obj['roadlab_marking_warnings']=json.dumps([str(error)])
    return None


classes=(ROADLAB_Lane,ROADLAB_LaneDraft,ROADLAB_UL_lanes,ROADLAB_OT_lane_edit,ROADLAB_OT_lane_count,ROADLAB_OT_lane_apply,ROADLAB_OT_lane_remove,ROADLAB_OT_lane_window,ROADLAB_OT_lane_pick,ROADLAB_PT_lanes)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.roadlab_lane_draft=PointerProperty(type=ROADLAB_LaneDraft)
    bpy.utils.register_tool(ROADLAB_WST_lanes,separator=True)
    bpy.app.timers.register(refresh_loaded_markings,first_interval=.1)
    bpy.app.handlers.save_pre.append(preview_before_save)
    bpy.app.handlers.save_post.append(preview_after_save)
    bpy.app.handlers.load_pre.append(preview_before_load)
def unregister():
    preview_before_load()
    for handlers,callback in ((bpy.app.handlers.save_pre,preview_before_save),(bpy.app.handlers.save_post,preview_after_save),(bpy.app.handlers.load_pre,preview_before_load)):
        if callback in handlers:handlers.remove(callback)
    clear_approach_preview()
    if bpy.app.timers.is_registered(refresh_loaded_markings):bpy.app.timers.unregister(refresh_loaded_markings)
    bpy.utils.unregister_tool(ROADLAB_WST_lanes)
    del bpy.types.Scene.roadlab_lane_draft
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
