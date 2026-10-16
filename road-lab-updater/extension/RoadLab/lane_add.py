"""Selection-based lane pockets with an isolated, cancellable geometry preview."""
import bpy,json,uuid,math
from mathutils import Vector
from bpy.props import FloatProperty,EnumProperty,StringProperty
from . import point_settings as ps,lane_pockets
_ACTIVE=None
_APPROACH_ITEMS={}

def approach_items(self,context):
    # RNA can query items through a temporary, read-only operator wrapper.
    # Keep strings alive globally and never attach Python state in this callback.
    key=self.choices_json or '[]'
    if key not in _APPROACH_ITEMS:_APPROACH_ITEMS[key]=[(str(i),c['label'],'') for i,c in enumerate(json.loads(key))] or [('0','Selected street','')]
    return _APPROACH_ITEMS[key]

def choices(context):
    from .lane_editor import road
    from .road_core import graph,values,key
    obj=road(context);selected=set(ps.selected(context,obj));rows=ps.records(obj)
    if not selected:raise ValueError('Select a road point, or a connected run of road points')
    points=ps.points(obj);paths=[];ids=[];offset=0
    for spline in obj.data.splines:
        coords=[tuple(p.co[:3]) for p in spline.points];ident=[r['id'] for r in rows[offset:offset+len(coords)]];offset+=len(coords)
        paths.append((coords+([coords[0]] if spline.use_cyclic_u else []),[1.]*(len(coords)+int(spline.use_cyclic_u))));ids.append(ident)
    nodes,_,_=graph(paths,values(obj)['road width']);locations={key(points[i].co[:3]) for i in selected};junction=len(locations)==1 and len(nodes.get(next(iter(locations)),()))>=3
    selected_ids={rows[i]['id'] for i in selected};result=[]
    for index,((coords,_),ident) in enumerate(zip(paths,ids)):
        anchors=[v for v in ident if v in selected_ids or junction and key(coords[ident.index(v)]) in locations]
        if not anchors:continue
        positions=[ident.index(v) for v in anchors]
        if not junction:
            if len(selected_ids-set(ident)):continue
            gaps=sum((positions[(i+1)%len(positions)]-positions[i])%len(ident)>1 for i in range(len(positions)))
            if len(positions)>1 and gaps>(1 if obj.data.splines[index].use_cyclic_u else 0):
                if positions!=list(range(min(positions),max(positions)+1)):raise ValueError('Select adjacent points along one street')
            junction_points=[i for i in positions if len(nodes.get(key(coords[i]),()))>=3]
            turn=len(junction_points)==1 and junction_points[0] in (min(positions),max(positions)) and len(positions)>1
            at=junction_points[0] if turn else positions[0]
            result.append(dict(spline=index,anchors=anchors,axis=ident[:2],label='Selected street section',junction=turn,junction_anchor=ident[at] if turn else '',junction_direction=(1 if at==min(positions) else -1) if turn else 0))
        else:
            at=positions[0]
            for neighbor in (at-1,at+1):
                if not 0<=neighbor<len(ident):continue
                d=Vector(coords[neighbor])-Vector(coords[at]);angle=math.atan2(d.y,d.x);names=('East','Northeast','North','Northwest','West','Southwest','South','Southeast');name=names[round(angle/(math.pi/4))%8]
                result.append(dict(spline=index,anchors=[ident[at]],axis=ident[:2],label=f'Toward {name} · {d.length:.0f} m',junction=True,junction_direction=1 if neighbor>at else -1))
    if not result:raise ValueError('Choose one connected street section; select a junction alone to choose its approach')
    return obj,result

def proposal(obj,choice,side,width,length,taper):
    rows=ps.records(obj);ids=[];offset=0
    for spline in obj.data.splines:
        ids.append([r['id'] for r in rows[offset:offset+len(spline.points)]]);offset+=len(spline.points)
    ident=ids[choice['spline']];anchors=set(choice['anchors']);existing=json.loads(obj.get('roadlab_lane_pockets','[]'));merged=[]
    # Adding a neighboring control point extends the same lane instead of stacking it.
    coords=[tuple(p.co[:3]) for p in obj.data.splines[choice['spline']].points]
    if obj.data.splines[choice['spline']].use_cyclic_u:coords.append(coords[0])
    changed=True
    while changed:
        changed=False
        for pocket in existing:
            resolved=resolved_spec(obj,coords,ident,pocket)
            if pocket in merged or not resolved or resolved['side']!=side:continue
            old={ident.index(a) for a in pocket['anchors'] if a in ident};new={ident.index(a) for a in anchors if a in ident}
            if pocket.get('junction'):
                anchor=pocket.get('junction_anchor',pocket['anchors'][0]);at=ident.index(anchor)
                if any((i-at)*resolved['junction_direction']<0 for i in new):continue
            adjacent=any(abs(a-b)<=1 or obj.data.splines[choice['spline']].use_cyclic_u and abs(a-b)==len(ident)-1 for a in old for b in new)
            if not adjacent:continue
            if merged and abs(pocket['width']-merged[0]['width'])>1e-5:raise ValueError('These lanes use different widths; edit them to match before joining')
            width=pocket['width']
            anchors.update(pocket['anchors']);merged.append(pocket);changed=True
    pocket=dict(id=merged[0]['id'] if merged else uuid.uuid4().hex,anchors=[a for a in ident if a in anchors],axis=choice['axis'],side=side,width=width,length=merged[0].get('length',length) if merged else length,taper=merged[0].get('taper',taper) if merged else taper,junction=choice.get('junction',False),junction_direction=choice.get('junction_direction',0),junction_anchor=choice.get('junction_anchor') or (choice['anchors'][0] if choice.get('junction') else ''))
    if merged:
        for key in ('movement','receiving','link_group'):
            if key in merged[0]:pocket[key]=merged[0][key]
        pocket['junction']=merged[0].get('junction',False)
        pocket['junction_direction']=resolved_spec(obj,coords,ident,merged[0])['junction_direction']
        pocket['junction_anchor']=merged[0].get('junction_anchor',merged[0]['anchors'][0])
        if pocket['junction']:
            at=ident.index(pocket['junction_anchor'])
            if any((ident.index(a)-at)*pocket['junction_direction']<0 for a in pocket['anchors']):raise ValueError('A turning pocket ends at its junction; extend along the same approach')
    candidate=[p for p in existing if p not in merged]+[pocket]
    # A side can carry at most seven travel lanes, including pocket additions.
    base=1
    for config in json.loads(obj.get('roadlab_lanes','[]')):
        if any(a in ident for a in config['endpoints']):base=max(base,len(config.get('incoming',[])),len(config.get('outgoing',[])))
    if base+1>7:raise ValueError('This direction already has seven lanes')
    coords=[tuple(p.co[:3]) for p in obj.data.splines[choice['spline']].points]
    if obj.data.splines[choice['spline']].use_cyclic_u:coords.append(coords[0])
    spec=resolved_spec(obj,coords,ident,pocket)
    for other in candidate[:-1]:
        old=resolved_spec(obj,coords,ident,other)
        if not old or old['side']!=side:continue
        if old and max(old['start'],spec['start'])<min(old['end'],spec['end'])-1e-5:raise ValueError('These lane tapers overlap. Select the points between them to extend one lane.')
    return candidate,pocket,bool(merged)

def preview_meshes(obj,pockets):
    """Evaluate cloned road and feature nodes, then remove every preview datablock."""
    from . import road_core,native_layers
    from .native_extension import set_input
    from .native_contacts import input_value
    initial_objects=set(bpy.data.objects);initial_meshes=set(bpy.data.meshes);initial_curves=set(bpy.data.curves)
    created=[];groups=[];collections=[];previous=road_core._busy;road_core._busy=True
    def copy(original,data=False):
        o=original.copy();o.name='RoadLab Pending Lane';o.hide_render=True
        if data:o.data=original.data.copy()
        created.append(o);return o
    def snapshot(o):
        evaluated=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=evaluated.to_mesh();m.calc_loop_triangles()
        try:return ([tuple(o.matrix_world@v.co) for v in m.vertices],[tuple(t.vertices) for t in m.loop_triangles])
        finally:evaluated.to_mesh_clear()
    try:
        proxy=copy(obj,True)
        for key in list(proxy.keys()):
            if any(s in key for s in ('marking','crosswalk','lanes','surface_contacts')):del proxy[key]
        proxy['roadlab_new_core']=False;proxy['roadlab_lane_pockets']=json.dumps(pockets)
        refs={}
        for key in ('roadlab_core_mesh','roadlab_core_outline'):
            original=obj[key];ref=copy(original,True)
            for name in list(ref.keys()):
                if name.startswith('roadlab_seam_'):del ref[name]
            ref['roadlab_core_owner_name']=proxy.name;proxy[key]=ref;refs[original]=ref
        mod=road_core.modifier(proxy);mod.node_group=mod.node_group.copy();groups.append(mod.node_group)
        for node in mod.node_group.nodes:
            if node.bl_idname=='GeometryNodeObjectInfo' and node.inputs['Object'].default_value in refs:node.inputs['Object'].default_value=refs[node.inputs['Object'].default_value]
        road_core.rebuild(proxy,True)
        collection=bpy.data.collections.new('RoadLab Pending Evaluation');collections.append(collection);bpy.context.scene.collection.children.link(collection)
        for o in created:collection.objects.link(o);o.hide_set(True)
        # Rebuild crosswalk guides against the proposed pavement, in isolation.
        proxy['roadlab_lanes']=obj.get('roadlab_lanes','[]')
        before=set(bpy.data.objects)
        for pocket in pockets:ensure_baseline(proxy,pocket,bpy.context.scene.roadlab_map_settings.traffic_side)
        from . import lane_editor
        lane_editor.rebuild(proxy,bpy.context.scene,True)
        for extra in set(bpy.data.objects)-before:
            if extra not in created:created.append(extra);extra.hide_set(True);extra.hide_render=True
        meshes=[(list(tuple(obj.matrix_world@v.co) for v in proxy['roadlab_core_mesh'].data.vertices),[tuple(p.vertices) for p in proxy['roadlab_core_mesh'].data.polygons])]
        # CurveToMesh and ramp deformation run with the same controls as the real layers.
        model=native_layers.model_for(obj);helper=None
        if model:
            model_copy=copy(model,True);model_copy['wb_layer_model']=False;model_copy['wb_road']=proxy
            helper=copy(model['wb_helper']);helper.data=proxy.data
            collection.objects.link(model_copy);collection.objects.link(helper);model_copy.hide_set(True);helper.hide_set(True)
            for m in helper.modifiers:
                if m.type=='NODES' and m.node_group:
                    m.node_group=m.node_group.copy();groups.append(m.node_group)
                    for n in m.node_group.nodes:
                        if n.bl_idname=='GeometryNodeObjectInfo' and n.inputs['Object'].default_value==model:n.inputs['Object'].default_value=model_copy
            network=bpy.data.collections.new('RoadLab Pending Road References');collections.append(network);network.objects.link(proxy)
            for layer in model.wb_layers:
                if not layer.object:continue
                for m in layer.object.modifiers:
                    if m.type=='NODES' and m.node_group and m.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                        refs_collection=input_value(m,'Road surfaces')
                        if refs_collection:
                            for reference in refs_collection.all_objects:
                                if reference!=obj and reference.name not in network.objects:network.objects.link(reference)
            for layer in model.wb_layers:
                if not layer.enabled or not layer.object:continue
                o=copy(layer.object);collection.objects.link(o);o.hide_set(True)
                for m in o.modifiers:
                    if m.type=='NODES' and m.node_group and m.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                        set_input(m,'Road',proxy);set_input(m,'Vertex controls',helper);set_input(m,'Road surfaces',network);set_input(m,'Crosswalk areas',proxy.get('roadlab_crosswalk_guide'))
                bpy.context.view_layer.update();meshes.append(snapshot(o))
        return meshes
    finally:
        for extra in set(bpy.data.objects)-initial_objects:
            if extra not in created:created.append(extra)
        for o in reversed(created):
            data=o.data;bpy.data.objects.remove(o,do_unlink=True)
            if data and data.users==0:
                if isinstance(data,bpy.types.Mesh):bpy.data.meshes.remove(data)
                elif isinstance(data,bpy.types.Curve):bpy.data.curves.remove(data)
        for group in groups:
            if group.users==0:bpy.data.node_groups.remove(group)
        for collection in reversed(collections):bpy.data.collections.remove(collection)
        for mesh in set(bpy.data.meshes)-initial_meshes:
            if mesh.users==0:bpy.data.meshes.remove(mesh)
        for curve in set(bpy.data.curves)-initial_curves:
            if curve.users==0:bpy.data.curves.remove(curve)
        road_core._busy=previous

def cleanup():
    global _ACTIVE
    if _ACTIVE and _ACTIVE.get('handle'):
        bpy.types.SpaceView3D.draw_handler_remove(_ACTIVE['handle'],'WINDOW')
    _ACTIVE=None
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()

def draw_preview():
    if not _ACTIVE or not _ACTIVE.get('meshes'):return
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader=gpu.shader.from_builtin('UNIFORM_COLOR');gpu.state.blend_set('ALPHA');gpu.state.depth_test_set('LESS_EQUAL');gpu.state.depth_mask_set(False)
    try:
        shader.bind();shader.uniform_float('color',(.04,.38,1.,.38))
        if _ACTIVE.get('batches') is None:
            _ACTIVE['batches']=[]
            for vertices,faces in _ACTIVE['meshes']:
                triangles=[(f[0],f[i],f[i+1]) for f in faces for i in range(1,len(f)-1)]
                _ACTIVE['batches'].append(batch_for_shader(shader,'TRIS',{'pos':[(x,y,z+.025) for x,y,z in vertices]},indices=triangles))
        for batch in _ACTIVE['batches']:batch.draw(shader)
    finally:gpu.state.depth_mask_set(True);gpu.state.depth_test_set('NONE');gpu.state.blend_set('NONE')

class ROADLAB_OT_lane_add_flip(bpy.types.Operator):
    bl_idname='roadlab.pending_lane_flip';bl_label='Change side of street';bl_options={'INTERNAL'}
    def execute(self,context):
        if _ACTIVE:
            op=_ACTIVE['operator'];op.side='LEFT' if op.side=='RIGHT' else 'RIGHT';op.refresh(context)
        return {'FINISHED'}

class ROADLAB_OT_add_lane(bpy.types.Operator):
    bl_idname='roadlab.add_lane';bl_label='Add lane pocket';bl_options={'REGISTER','UNDO'}
    road_name:StringProperty(options={'HIDDEN'})
    choices_json:StringProperty(default='[]',options={'HIDDEN'})
    approach:EnumProperty(name='Street / approach',items=approach_items)
    side:EnumProperty(name='Road edge',items=[('RIGHT','Right edge','Right of the source street direction'),('LEFT','Left edge','Left of the source street direction')],default='RIGHT')
    movement:EnumProperty(name='Lane purpose',items=[('TURN','Turn lane','A dedicated turn lane using available receiving capacity'),('THROUGH','Through lane','Add a receiving lane across the junction, merging after the junction')],default='TURN')
    width:FloatProperty(name='Lane width (m)',default=3.5,min=2.,max=5.)
    length:FloatProperty(name='Pocket length (m)',default=12.,min=3.,max=100.)
    taper:FloatProperty(name='Taper length (m)',default=15.,min=3.,max=500.)
    merge_taper:FloatProperty(name='Receiving merge taper (m)',description='Default 71.46 m: FDOT merging taper for a 3.5 m lane at 35 mph. Adjust for your road design speed',default=71.46,min=3.,max=500.)
    @classmethod
    def poll(cls,context):return context.mode=='EDIT_CURVE' and context.edit_object is not None and context.edit_object.get('roadlab_new_core',False)
    def invoke(self,context,event):
        global _ACTIVE
        cleanup()
        try:self._road,self._choices=choices(context)
        except ValueError as e:self.report({'INFO'},str(e));return {'CANCELLED'}
        self.road_name=self._road.name;self.choices_json=json.dumps(self._choices);self._enum_cache=None
        self.approach='0';self._signature=None;self._error='';self._extension=False
        direction=self._choices[0].get('junction_direction',-1)
        sign=direction*(1 if context.scene.roadlab_map_settings.traffic_side=='RIGHT' else -1)
        self.side='LEFT' if sign>0 else 'RIGHT'
        if self._choices[0].get('junction'):self.length=24.
        self._last_approach=self.approach
        _ACTIVE={'operator':self,'meshes':[],'handle':None};_ACTIVE['handle']=bpy.types.SpaceView3D.draw_handler_add(draw_preview,(),'WINDOW','POST_VIEW')
        self.refresh(context)
        return context.window_manager.invoke_props_dialog(self,width=360,confirm_text='Add lane')
    def refresh(self,context):
        if not _ACTIVE:return
        if getattr(self,'_last_approach',self.approach)!=self.approach:
            choice=self._choices[int(self.approach)]
            if choice.get('junction'):
                sign=choice['junction_direction']*(1 if context.scene.roadlab_map_settings.traffic_side=='RIGHT' else -1);self.side='LEFT' if sign>0 else 'RIGHT'
            self._last_approach=self.approach
        signature=(self.approach,self.side,self.movement,self.width,self.length,self.taper,self.merge_taper,self._road.get('roadlab_core_signature'))
        if signature==self._signature:return
        self._signature=signature
        try:
            proposal_rows,pocket,self._extension=proposal(self._road,self._choices[int(self.approach)],1 if self.side=='LEFT' else -1,self.width,self.length,self.taper)
            proposal_rows,pocket=with_receiving_lane(self._road,proposal_rows,pocket,self.movement,self.merge_taper,context.scene.roadlab_map_settings.traffic_side)
            if self._extension and pocket.get('movement')=='THROUGH':self.movement='THROUGH'
            if self._extension:self.width=pocket['width'];self.length=pocket['length'];self.taper=pocket['taper']
            validate_turn(self._road,pocket,context.scene.roadlab_map_settings.traffic_side)
            _ACTIVE['batches']=None
            active=[p for p in proposal_rows if p['id']==pocket['id'] or pocket.get('link_group') and p.get('link_group')==pocket['link_group']]
            _ACTIVE['meshes']=crop_previews(self._road,active,preview_meshes(self._road,proposal_rows));self._candidate=proposal_rows;self._primary=pocket;self._error=''
        except (ValueError,RuntimeError,KeyError) as error:self._error=str(error);_ACTIVE['meshes']=[]
        for area in context.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()
    def check(self,context):self.refresh(context);return True
    def draw(self,context):
        l=self.layout
        if len(self._choices)>1:l.prop(self,'approach')
        if self._choices[int(self.approach)].get('junction'):
            purpose=l.row();purpose.enabled=not self._extension;purpose.prop(self,'movement')
        l.label(text='Blue = proposed road, curb and sidewalk')
        l.label(text='Extend existing lane' if self._extension else 'Local widening with entry and exit tapers')
        turn=pocket_turn(self._road,self._primary,context.scene.roadlab_map_settings.traffic_side) if not self._error and getattr(self,'_candidate',None) else None
        if turn:l.label(text='Through lane + receiving merge' if turn[0]=='THROUGH' else turn[0].title()+' turn pocket')
        l.prop(self,'side');l.operator('roadlab.pending_lane_flip',icon='ARROW_LEFTRIGHT')
        settings=l.column();settings.enabled=not self._extension
        for key in ('width','length','taper'):settings.prop(self,key)
        if self.movement=='THROUGH' and self._choices[int(self.approach)].get('junction'):
            l.prop(self,'merge_taper');l.label(text='Receiving lane merges after the junction')
        l.label(text='Original road points stay editable',icon='CURVE_PATH')
        if self._error:l.label(text=self._error,icon='ERROR')
    def execute(self,context):
        self._road=bpy.data.objects.get(self.road_name)
        if self._road is None:self.report({'ERROR'},'The selected road no longer exists');cleanup();return {'CANCELLED'}
        if not hasattr(self,'_choices'):self._choices=json.loads(self.choices_json)
        original={key:self._road.get(key) for key in ('roadlab_lane_pockets','roadlab_lanes')}
        try:
            if getattr(self,'_error',''):raise ValueError(self._error)
            candidate,pocket,extended=proposal(self._road,self._choices[int(self.approach)],1 if self.side=='LEFT' else -1,self.width,self.length,self.taper)
            candidate,pocket=with_receiving_lane(self._road,candidate,pocket,self.movement,self.merge_taper,context.scene.roadlab_map_settings.traffic_side)
            validate_turn(self._road,pocket,context.scene.roadlab_map_settings.traffic_side)
            for part in candidate:ensure_baseline(self._road,part,context.scene.roadlab_map_settings.traffic_side)
            self._road['roadlab_lane_pockets']=json.dumps(candidate)
            from .selected_points import notify
            cleanup();notify(context,self._road)
            self.report({'INFO'},'Lane extended' if extended else 'Lane pocket added')
        except (ValueError,RuntimeError) as e:
            cleanup()
            for key,value in original.items():
                if value is None:
                    if key in self._road:del self._road[key]
                else:self._road[key]=value
            from .selected_points import notify
            notify(context,self._road);self.report({'ERROR'},str(e));return {'CANCELLED'}
        return {'FINISHED'}
    def cancel(self,context):cleanup()

@bpy.app.handlers.persistent
def clear_on_load(_):cleanup()

def register():
    for cls in (ROADLAB_OT_lane_add_flip,ROADLAB_OT_add_lane,ROADLAB_OT_remove_lane_pocket):bpy.utils.register_class(cls)
    bpy.app.handlers.load_pre.append(clear_on_load)
def unregister():
    cleanup()
    if clear_on_load in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.remove(clear_on_load)
    for cls in (ROADLAB_OT_remove_lane_pocket,ROADLAB_OT_add_lane,ROADLAB_OT_lane_add_flip):bpy.utils.unregister_class(cls)

def pocket_turn(obj,pocket,traffic_side):
    if not pocket.get('junction'):return None
    from .lane_pocket_markings import source
    data=source(obj,{'endpoints':pocket['axis']})
    if not data:return None
    coords,ids,specs=data;spec=resolved_spec(obj,coords,ids,pocket);flow=-spec['junction_direction'];curb=-flow*(1 if traffic_side=='RIGHT' else -1)
    median=spec['side']!=curb
    movement=('LEFT' if traffic_side=='RIGHT' else 'RIGHT') if median else ('RIGHT' if traffic_side=='RIGHT' else 'LEFT')
    if pocket.get('movement')=='THROUGH':movement='THROUGH'
    at=ids.index(pocket['anchors'][0] if len(pocket['anchors'])==1 else next(a for a in pocket['anchors'] if a==pocket.get('junction_anchor',pocket['anchors'][0])))
    # Locate the selected junction rather than assuming a curve endpoint.
    from .road_core import graph,values,key
    from . import point_settings as ps
    paths=[]
    for spl in obj.data.splines:
        cs=[tuple(p.co[:3]) for p in spl.points]
        if spl.use_cyclic_u:cs.append(cs[0])
        paths.append((cs,[1.]*len(cs)))
    nodes,_,_=graph(paths,values(obj)['road width'])
    candidates=[i for i,a in enumerate(ids) if a in pocket['anchors'] and len(nodes.get(key(coords[i]),()))>=3]
    if not candidates:return None
    at=candidates[0];neighbor=at+spec['junction_direction']
    if not 0<=neighbor<len(ids):raise ValueError('This junction approach changed; select it again')
    return movement,coords[neighbor],coords[at],nodes,ids[neighbor],ids[at]

def validate_turn(obj,pocket,traffic_side):
    info=pocket_turn(obj,pocket,traffic_side)
    if not info:return
    from . import lane_logic
    from .road_core import key
    movement,a,b,nodes,_,_=info
    if movement not in lane_logic.available_movements(key(a),key(b),nodes[key(b)]):raise ValueError(f'There is no {movement.lower()}-turn destination on this approach. Change side or choose another approach.')
    from . import lane_editor
    turn_count=1
    for config in lane_editor.state(obj):
        if frozenset(config['endpoints'])!=frozenset(info[4:]):continue
        direction='incoming' if config['endpoints']==list(info[4:]) else 'outgoing'
        turn_count+=sum(row['movement']==movement for row in config[direction])
    for other in json.loads(obj.get('roadlab_lane_pockets','[]')):
        if other['id']==pocket['id']:continue
        other_turn=pocket_turn(obj,other,traffic_side)
        if other_turn and other_turn[0]==movement and other_turn[4:]==info[4:]:turn_count+=1
    if pocket.get('movement')=='THROUGH':return
    capacity=receiving_capacity(obj,info)
    if turn_count>capacity:raise ValueError(f'This turn needs {turn_count} receiving lanes; the destination has {capacity}. Configure the destination first.')

def ensure_baseline(obj,pocket,traffic_side):
    from . import lane_editor as editor
    from .road_core import values
    rows=ps.records(obj);offset=0;configs=editor.state(obj);default=values(obj)['road width'];turn=pocket_turn(obj,pocket,traffic_side)
    from .road_core import graph,key
    from . import lane_logic
    paths=[]
    for spl in obj.data.splines:
        cs=[tuple(p.co[:3]) for p in spl.points]
        if spl.use_cyclic_u:cs.append(cs[0])
        paths.append((cs,[1.]*len(cs)))
    nodes,_,_=graph(paths,default)
    def movement(a,b):
        if len(nodes.get(key(b),()))<3:return 'THROUGH'
        available=lane_logic.available_movements(key(a),key(b),nodes[key(b)])
        if 'THROUGH' in available:return 'THROUGH'
        return '_'.join(m for m in ('LEFT','RIGHT') if m in available) or 'THROUGH'
    for spline in obj.data.splines:
        ids=[r['id'] for r in rows[offset:offset+len(spline.points)]];indices=list(range(offset,offset+len(ids)));offset+=len(ids)
        if not any(a in ids for a in pocket['anchors']) and not (turn and any(key(p.co[:3])==key(turn[2]) for p in spline.points)):continue
        for i in range(len(ids) if spline.use_cyclic_u else len(ids)-1):
            j=(i+1)%len(ids);pair=[ids[i],ids[j]]
            if any(frozenset(c['endpoints'])==frozenset(pair) for c in configs):continue
            width=min(ps.width(obj,indices[i],default),ps.width(obj,indices[j],default));lane_width=min(3.5,max(.5,(width-1.)/2))
            configs.append(dict(endpoints=pair,incoming=[dict(width=lane_width,movement=movement(spline.points[i].co[:3],spline.points[j].co[:3]),entry='CONTINUOUS')],outgoing=[dict(width=lane_width,movement=movement(spline.points[j].co[:3],spline.points[i].co[:3]),entry='CONTINUOUS')],median=0.,spacing=18.,solid_approach=20.,transition_length=30.,stop_setback=1.22,control_incoming='NONE',control_outgoing='NONE'))
    obj['roadlab_lanes']=json.dumps(configs)

class ROADLAB_OT_remove_lane_pocket(bpy.types.Operator):
    bl_idname='roadlab.remove_lane_pocket';bl_label='Remove lane pocket';bl_options={'REGISTER','UNDO'}
    pocket_id:StringProperty(options={'HIDDEN'})
    def execute(self,context):
        from .lane_editor import road
        from .selected_points import notify
        obj=road(context);pockets=json.loads(obj.get('roadlab_lane_pockets','[]'));target=next((p for p in pockets if p['id']==self.pocket_id),{});group=target.get('link_group')
        obj['roadlab_lane_pockets']=json.dumps([p for p in pockets if p['id']!=self.pocket_id and not (group and p.get('link_group')==group)]);cleanup();notify(context,obj);return {'FINISHED'}

def receiving_capacity(obj,turn):
    """Reject adding parallel turn lanes into fewer configured destination lanes."""
    from . import lane_editor,point_settings as ps
    from .road_core import key
    movement,start,junction,nodes,_,_=turn;u=Vector(junction)-Vector(start);u.z=0;u.normalize();target=[]
    for neighbor in nodes[key(junction)]:
        v=Vector(neighbor)-Vector(junction);v.z=0;v.normalize();angle=math.atan2(u.x*v.y-u.y*v.x,u.dot(v))
        if movement=='LEFT' and angle>.3 or movement=='RIGHT' and angle<-.3:target.append((abs(abs(angle)-math.pi/2),neighbor))
    if not target:return 0
    dest=min(target)[1];rows=ps.records(obj);co={r['id']:key(r['co']) for r in rows}
    for config in lane_editor.state(obj):
        a,b=config['endpoints']
        if a not in co or b not in co:continue
        if co[a]==key(junction) and co[b]==key(dest):return len(config['incoming'])
        if co[b]==key(junction) and co[a]==key(dest):return len(config['outgoing'])
    return 1

def crop_preview(obj,pocket,meshes):
    from .lane_pocket_markings import source,project
    data=source_for_pocket(obj,pocket)
    if not data:return meshes
    coords,ids=data;ss=lane_pockets.stations(coords);spec=resolved_spec(obj,coords,ids,pocket);result=[]
    from .road_core import values
    maxdist=max(ps.width(obj,i,values(obj)['road width']) for i in range(len(ps.points(obj))))/2+pocket['width']+12.
    inverse=obj.matrix_world.inverted()
    for vertices,faces in meshes:
        selected=[]
        for face in faces:
            center=tuple(sum(vertices[i][axis] for i in face)/len(face) for axis in range(3));local=inverse@Vector(center);station,u=project(coords,ss,local);nearest,_,_,_=lane_pockets.sample(coords,ss,station)
            if math.dist(local[:2],nearest[:2])>maxdist:continue
            if spec['cyclic'] or spec['start']-1<=station<=spec['end']+1:selected.append(face)
        used=sorted({i for f in selected for i in f});mapping={old:new for new,old in enumerate(used)}
        result.append(([vertices[i] for i in used],[tuple(mapping[i] for i in f) for f in selected]))
    return result

def source_for_pocket(obj,pocket):
    rows=ps.records(obj);offset=0
    for spline in obj.data.splines:
        ids=[r['id'] for r in rows[offset:offset+len(spline.points)]];offset+=len(ids)
        if not all(a in ids for a in pocket['anchors']):continue
        coords=[tuple(p.co[:3]) for p in spline.points]
        if spline.use_cyclic_u:coords.append(coords[0])
        return coords,ids


def resolved_spec(obj,coords,ids,pocket):
    from .road_core import values
    settings=values(obj);default=settings['road width'];lookup={r['id']:i for i,r in enumerate(ps.records(obj))};width=max(ps.width(obj,lookup[i],default) for i in ids)
    return lane_pockets.locate(coords,ids,pocket,width,max(settings['corner '+k] for k in ('NW','NE','SW','SE')))


def with_receiving_lane(obj,candidate,pocket,movement,merge_taper,traffic_side):
    """Pair a through lane with a real downstream widening, atomically."""
    if not pocket.get('junction'):return candidate,pocket
    # Extending a saved lane retains its purpose and its paired receiving arm.
    movement=pocket.get('movement',movement)
    if movement!='THROUGH':return candidate,pocket
    pocket=dict(pocket,movement='THROUGH')
    info=pocket_turn(obj,pocket,traffic_side)
    if not info:raise ValueError('Select a junction approach for a through lane')
    _,start,junction,nodes,_,_=info
    from .road_core import key
    incoming=Vector(junction)-Vector(start);incoming.z=0;incoming.normalize()
    targets=[]
    for neighbor in nodes[key(junction)]:
        delta=Vector(neighbor)-Vector(junction);delta.z=0
        if delta.length<1e-6:continue
        delta.normalize();dot=incoming.dot(delta)
        if dot>math.cos(math.radians(30)):targets.append((dot,neighbor))
    targets.sort(reverse=True)
    if not targets:raise ValueError('This approach has no through street across the junction')
    if len(targets)>1 and targets[0][0]-targets[1][0]<.05:raise ValueError('The through destination is ambiguous; adjust the junction approaches')
    destination=targets[0][1];group=pocket.get('link_group',pocket['id']);pocket['link_group']=group
    previous=next((p for p in candidate if p.get('link_group')==group and p.get('receiving')),None)
    if pocket.get('receiving'):
        return [pocket if p['id']==pocket['id'] else p for p in candidate],pocket
    offset=0;rows=ps.records(obj);receiver=None
    for spline in obj.data.splines:
        ids=[r['id'] for r in rows[offset:offset+len(spline.points)]];offset+=len(ids)
        for i,p in enumerate(spline.points):
            if key(p.co[:3])!=key(junction):continue
            for j in (i-1,i+1):
                if not 0<=j<len(ids) or key(spline.points[j].co[:3])!=key(destination):continue
                source_coords,source_ids=source_for_pocket(obj,pocket);spec=resolved_spec(obj,source_coords,source_ids,pocket)
                # Physical left/right follows flow even when source splines reverse.
                relative_side=spec['side']*(-spec['junction_direction'])
                direction=1 if j>i else -1
                receiver=dict(id=previous['id'] if previous else uuid.uuid4().hex,anchors=[ids[i]],axis=ids[:2],side=relative_side*direction,width=pocket['width'],length=pocket['length'],taper=previous['taper'] if previous else merge_taper,junction=True,junction_anchor=ids[i],junction_direction=direction,movement='THROUGH',receiving=True,link_group=group)
                if previous:
                    receiver['anchors']=previous['anchors'];receiver['length']=previous['length']
                ss=lane_pockets.stations([tuple(p.co[:3]) for p in spline.points]);available=ss[-1]-ss[i] if direction>0 else ss[i]
                if available<receiver['length']+receiver['taper']:
                    raise ValueError(f'Receiving street needs {receiver["length"]+receiver["taper"]:.1f} m for the full lane and merge; available {available:.1f} m. Extend it or shorten the lengths.')
                from . import lane_editor
                for config in lane_editor.state(obj):
                    if frozenset(config['endpoints'])!=frozenset((ids[i],ids[j])):continue
                    field='incoming' if config['endpoints']==[ids[i],ids[j]] else 'outgoing'
                    if len(config[field])>=7:raise ValueError('The receiving direction already has seven lanes')
    if receiver is None:raise ValueError('The receiving street must have editable control points')
    candidate=[p for p in candidate if p['id']!=pocket['id'] and not (p.get('link_group')==group and p.get('receiving'))]+[pocket]
    receiver_coords,receiver_ids=source_for_pocket(obj,receiver);span=resolved_spec(obj,receiver_coords,receiver_ids,receiver)
    for other in candidate:
        if other.get('link_group')==group:continue
        old=resolved_spec(obj,receiver_coords,receiver_ids,other)
        if old and old['side']==span['side'] and max(old['start'],span['start'])<min(old['end'],span['end'])-1e-5:raise ValueError('The receiving merge overlaps another added lane')
    candidate.append(receiver)
    return candidate,pocket


def crop_previews(obj,pockets,meshes):
    # The two arms are cropped separately so a distant road stays unhighlighted.
    result=[]
    for pocket in pockets:result.extend(crop_preview(obj,pocket,meshes))
    return result
