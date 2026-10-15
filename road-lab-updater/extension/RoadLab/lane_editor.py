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
    incoming_index:IntProperty(default=0,min=0)
    outgoing_index:IntProperty(default=0,min=0)
    incoming:CollectionProperty(type=ROADLAB_Lane)
    outgoing:CollectionProperty(type=ROADLAB_Lane)
    median:FloatProperty(name='Median (m)',min=0.,default=0.)
    spacing:FloatProperty(name='Arrow spacing (m)',min=5.,default=18.)
    arrow_approach:FloatProperty(name='Arrow approach (m)',min=0.,default=35.,description='Distance before a junction that receives automatic arrows; zero disables them')
    solid_approach:FloatProperty(name='Solid approach (m)',min=0.,default=20.)
    transition_length:FloatProperty(name='Entry dots (m)',min=0.,default=30.)
    stop_setback:FloatProperty(name='Stop setback (m)',min=0.,default=1.22)
    control_incoming:EnumProperty(name='Forward-end control',items=[('NONE','Uncontrolled','No stop bar'),('STOP','Stop','Place a stop bar on incoming lanes'),('SIGNAL','Traffic signals','Place a stop bar; traffic simulation remains separate'),('YIELD','Yield','No stop bar')],default='NONE')
    control_outgoing:EnumProperty(name='Reverse-end control',items=[('NONE','Uncontrolled','No stop bar'),('STOP','Stop','Place a stop bar on incoming lanes'),('SIGNAL','Traffic signals','Place a stop bar; traffic simulation remains separate'),('YIELD','Yield','No stop bar')],default='NONE')
    reverse:BoolProperty(name='Reverse section direction',description='Swap which end incoming lanes travel toward; the map driving side stays unchanged')


def paint_material(asset):
    name='RoadLab Marking '+asset;mat=bpy.data.materials.get(name)
    if mat:return mat
    row=lane_markings.manifest()[asset];mat=bpy.data.materials.new(name);mat.use_nodes=True
    nodes=mat.node_tree.nodes;p=nodes.get('Principled BSDF');tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(lane_markings.ROOT/row['rgba']),check_existing=True);tex.image.alpha_mode='STRAIGHT';tex.extension='CLIP'
    mat.node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color']);mat.node_tree.links.new(tex.outputs['Alpha'],p.inputs['Alpha']);p.inputs['Roughness'].default_value=.85
    if hasattr(mat,'surface_render_method'):mat.surface_render_method='DITHERED'
    elif hasattr(mat,'blend_method'):mat.blend_method='HASHED'
    mat.diffuse_color=(.94,.94,.86,1);return mat


def rebuild(obj,scene,force=False):
    configs=state(obj);output=obj.get('roadlab_core_mesh')
    if output is None:return
    side=scene.roadlab_map_settings.traffic_side
    signature=hashlib.sha256(json.dumps(['approach-arrows-erase-v2',obj.get('roadlab_hidden_lane_markings','[]'),configs,obj.get('roadlab_core_signature'),output.data.as_pointer(),side],sort_keys=True).encode()).hexdigest()
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
    def clearance(co,width):
        if len(nodes.get(key(co),[]))<3:return 0.
        # Keep paint clear of rounded junction footprints; never draw connectors here.
        touching=[max(w) if isinstance(w,(list,tuple)) else w for e,w in edges.items() if key(co) in e]
        overrides=point_settings.junction_overrides(obj).get(key(co),{})
        radius=max(overrides.get(c,values(obj)['corner '+c]) for c in ('NW','NE','SW','SE'))
        return max([width,*touching])/2+radius+1.
    plans=[];warnings=[];hidden=set(json.loads(obj.get('roadlab_hidden_lane_markings','[]')))
    for config in configs:
        a,b=config['endpoints']
        if a not in lookup or b not in lookup or frozenset((a,b)) not in valid:
            warnings.append('Lane assignment needs reselection after topology edit');continue
        ia,ib=lookup[a],lookup[b];pa,pb=tuple(points[ia].co[:3]),tuple(points[ib].co[:3]);width=min(point_settings.width(obj,ia,default),point_settings.width(obj,ib,default))
        try:
            validate_approach(obj,config['endpoints'],entries(config['incoming'],'i'),entries(config['outgoing'],'o'))
            delta=Vector(pb)-Vector(pa);length=hypot(delta.x,delta.y);cuts=[(0.,pa),(length,pb)]
            if length>1e-6:
                for junction,neighbors in nodes.items():
                    if len(neighbors)<3:continue
                    t=((junction[0]-pa[0])*delta.x+(junction[1]-pa[1])*delta.y)/(length*length)
                    candidate=Vector(pa)+delta*t
                    if 1e-6<t<1-1e-6 and (candidate-Vector(junction)).length<1e-5:cuts.append((length*t,junction))
            cuts.sort(key=lambda cut:cut[0])
            for part,((_,start),(_,finish)) in enumerate(zip(cuts,cuts[1:])):
                segment_plans=lane_markings.plan(start,finish,entries(config['incoming'],'i'),entries(config['outgoing'],'o'),width,side,config['median'],clearance(start,width),clearance(finish,width),config['spacing'],**{k:config.get(k,v) for k,v in [('arrow_approach',35.),('solid_approach',20.),('transition_length',30.),('stop_setback',1.22),('control_incoming','NONE'),('control_outgoing','NONE')]},emerging_incoming=[i for i,row in enumerate(config['incoming']) if row.get('entry')=='ADDED'],emerging_outgoing=[i for i,row in enumerate(config['outgoing']) if row.get('entry')=='ADDED'])
                for mark in segment_plans:
                    mark['id']=hashlib.sha256(json.dumps([config['endpoints'],part,mark['role']],sort_keys=True).encode()).hexdigest()
                    if mark['id'] not in hidden:plans.append(mark)
        except ValueError as error:warnings.append(str(error))
    obj['roadlab_generated_marking_catalog']=json.dumps(plans)
    mesh=output.data;vs=[v.co.copy() for v in mesh.vertices];polys=[tuple(p.vertices) for p in mesh.polygons]
    bvh=BVHTree.FromPolygons(vs,polys);top=max((v.z for v in vs),default=0)+100;bottom=min((v.z for v in vs),default=0)-100
    def surface(x,y,expected):
        # At overpasses choose the nearest road elevation, not the topmost deck.
        hits=[];origin=top
        for _ in range(32):
            hit,normal,face,distance=bvh.ray_cast(Vector((x,y,origin)),Vector((0,0,-1)),origin-bottom)
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
            projected.append(surface(x,y,z))
        for face in pf:
            if any(projected[i] is None for i in face):continue
            center=Vector(tuple(sum(pv[i][j] for i in face)/4 for j in range(3)))
            if bvh.ray_cast(Vector((center.x,center.y,top)),Vector((0,0,-1)),top-bottom)[0] is None:continue
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
        if len(choices)<3:raise ValueError('Select a junction, or two adjacent points for a street section')
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
    for field,value in [('arrow_approach',35.),('solid_approach',20.),('transition_length',30.),('stop_setback',1.22),('control_incoming','NONE'),('control_outgoing','NONE')]:setattr(d,field,config.get(field,value) if config else value)
    for field in ('incoming','outgoing'):
        for row in (config[field] if config else [{'width':3.5,'movement':'THROUGH'}]):
            item=getattr(d,field).add();item.width=row['width'];item.movement=row['movement'];item.entry=row.get('entry','CONTINUOUS')
    if normalize and d.reverse:
        incoming,outgoing=rows(d.incoming),rows(d.outgoing);d.incoming.clear();d.outgoing.clear()
        for field,values in (('incoming',outgoing),('outgoing',incoming)):
            for row in values:
                item=getattr(d,field).add();item.width=row['width'];item.movement=row['movement'];item.entry=row.get('entry','CONTINUOUS')
        d.control_incoming,d.control_outgoing=d.control_outgoing,d.control_incoming
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


class ROADLAB_OT_lane_apply(bpy.types.Operator):
    bl_idname='roadlab.lane_apply';bl_label='Apply lanes and markings';bl_options={'REGISTER','UNDO'}
    expand:BoolProperty(name='Expand road to fit',default=False)
    def required(self,context):
        d=context.scene.roadlab_lane_draft
        return lane_logic.road_width(entries(rows(d.incoming),'i'),entries(rows(d.outgoing),'o'),d.median)[1]
    def invoke(self,context,event):
        self.expand=False
        try:
            obj,indices,targets=draft_target(context)
            from .road_core import values
            available=context.scene.roadlab_lane_draft.road_width;needed=self.required(context)
            if needed>available+1e-6:
                self.expand=True
                return context.window_manager.invoke_props_dialog(self,width=350,confirm_text='Expand road & apply')
        except ValueError as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return self.execute(context)
    def draw(self,context):
        self.layout.label(text=f'Lanes require {self.required(context):.2f} m')
        self.layout.label(text=f'Requested road width: {context.scene.roadlab_lane_draft.road_width:.2f} m')
        self.layout.label(text='Keep current road: cancel this change.')
        self.layout.label(text='Expand road & apply, or Cancel to keep it.')
    def execute(self,context):
        try:
            obj,indices,targets=draft_target(context);draft=context.scene.roadlab_lane_draft
            if not len(draft.incoming)+len(draft.outgoing):raise ValueError('Add at least one lane')
            from .road_core import values
            needed=self.required(context);available=draft.road_width
            if needed>available+1e-6 and not self.expand:raise ValueError('Road too narrow. Enable expansion to apply these lanes.')
            for row in [*rows(draft.incoming),*rows(draft.outgoing)]:lane_markings.arrow_id(row['movement'].split('_'))
            for t in targets:validate_approach(obj,t[::-1] if draft.reverse else t,entries(rows(draft.incoming),'i'),entries(rows(draft.outgoing),'o'))
            from math import isfinite
            if not isfinite(available):raise ValueError('Road width must be finite')
            desired=max(available,needed) if self.expand else available
            items=point_settings.sync(obj)
            for i in indices:items[i]['width']=desired
            point_settings.save(obj,items);draft.road_width=desired
            configs=[c for c in state(obj) if all(frozenset(c['endpoints'])!=frozenset(t) for t in targets)]
            for t in targets:
                endpoints=t[::-1] if draft.reverse else t
                configs.append({'endpoints':endpoints,'incoming':rows(draft.incoming),'outgoing':rows(draft.outgoing),'median':draft.median,'spacing':draft.spacing,**{k:getattr(draft,k) for k in ('arrow_approach','solid_approach','transition_length','stop_setback','control_incoming','control_outgoing')}})
            obj['roadlab_lanes']=json.dumps(configs)
            from .selected_points import notify
            notify(context,obj);rebuild(obj,context.scene)
        except ValueError as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        return {'FINISHED'}

class ROADLAB_OT_lane_remove(bpy.types.Operator):
    bl_idname='roadlab.lane_remove';bl_label='Remove selected segment markings';bl_options={'REGISTER','UNDO'}
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


def draw_lanes(l,context,junction=False):
    d=context.scene.roadlab_lane_draft
    required=lane_logic.road_width(entries(rows(d.incoming),'i'),entries(rows(d.outgoing),'o'),d.median)[1]
    box=section(l,d,'show_size','Road size',f'{d.road_width:.1f} m')
    if box:
        box.prop(d,'road_width');box.prop(d,'median')
        box.label(text=f'Width needed by lanes: {required:.2f} m')
        box.label(text='Extra width remains shoulder space')
        if not junction:box.prop(d,'reverse')
    if required>d.road_width+1e-6:l.label(text=f'Needs {required:.2f} m — expansion approval on Apply',icon='INFO')
    for field in ('incoming','outgoing'):
        items=getattr(d,field);box=section(l,d,'show_'+field,field.title()+' lanes',f'{len(items)} / 7')
        if box:
            box.label(text=('Toward this junction' if field=='incoming' else 'Away from this junction') if junction else ('Along selected direction' if field=='incoming' else 'Against selected direction'))
            row=box.row(align=True);row.label(text='Driver’s left → right')
            for delta,icon in [(-1,'REMOVE'),(1,'ADD')]:
                button=row.row();button.enabled=len(items)<7 if delta>0 else len(items)>0
                op=button.operator('roadlab.lane_count',text='Remove lane' if delta<0 else 'Add lane',icon=icon);op.direction=field;op.delta=delta
            header=box.row();header.label(text='Lane');header.label(text='Allowed movement');header.label(text='Width (m)')
            box.template_list('ROADLAB_UL_lanes',field,d,field,d,field+'_index',rows=3,maxrows=3)
            if items and getattr(d,field+'_index')<len(items):box.prop(items[getattr(d,field+'_index')],'entry')
    box=section(l,d,'show_markings','Markings')
    if box:
        box.prop(d,'spacing');box.prop(d,'arrow_approach');box.prop(d,'solid_approach');box.prop(d,'transition_length')
        box.prop(d,'control_incoming');box.prop(d,'control_outgoing');box.prop(d,'stop_setback')
        box.label(text='Stop bars apply at junctions on controlled arrivals')
        box.label(text='Added-lane dots mark entry; geometry is unchanged')



_approach_enum_cache={}

def approach_items(self,context):
    choices=json.loads(self.choices_json)
    if not choices:return [('0','Section','')]
    obj=road(context);items=point_settings.records(obj);lookup={x['id']:i for i,x in enumerate(items)};ps=point_settings.points(obj)
    result=[]
    from math import atan2,degrees
    for i,(a,b) in enumerate(choices):
        pa,pb=ps[lookup[a]].co,ps[lookup[b]].co
        if hasattr(obj,'matrix_world'):pa,pb=obj.matrix_world@pa,obj.matrix_world@pb
        angle=degrees(atan2(pa.y-pb.y,pa.x-pb.x))%360
        result.append((str(i),f'Approach {i+1} · {angle:.0f}°','Actual connected road heading'))
    cache_key=self.choices_json
    _approach_enum_cache[cache_key]=result or [('0','Section','')]
    return _approach_enum_cache[cache_key]


def approach_changed(self,context):
    choices=json.loads(self.choices_json)
    if choices and self.is_junction:set_draft(context,road(context),[choices[int(self.approach)]],normalize=True)


class ROADLAB_OT_lane_window(bpy.types.Operator):
    bl_idname='roadlab.lane_window';bl_label='Lane editor';bl_options={'REGISTER','UNDO'}
    choices_json:StringProperty(default='[]',options={'HIDDEN'})
    has_selection:BoolProperty(default=False,options={'HIDDEN'})
    selection_hint:StringProperty(default='',options={'HIDDEN'})
    is_junction:BoolProperty(default=False,options={'HIDDEN'})
    junction_label:StringProperty(default='Junction',options={'HIDDEN'})
    approach:EnumProperty(name='Approach',items=approach_items,update=approach_changed)
    def invoke(self,context,event):
        try:
            obj,targets,junction=selection_targets(context);context.scene.wb_native.road=obj;self.has_selection=True;self.choices_json=json.dumps(targets);self.is_junction=junction
            set_draft(context,obj,[targets[0]] if junction else targets,normalize=junction)
            if junction:
                from .junction_layout import from_selection
                self.junction_label=from_selection(context)['kind'].replace('_',' ').title();self.approach='0'
        except (ValueError,AttributeError) as e:
            self.has_selection=False;self.selection_hint=str(e);self.choices_json='[]';self.is_junction=False
        return context.window_manager.invoke_props_dialog(self,width=520,confirm_text='Apply lanes' if self.has_selection else 'Close')
    def check(self,context):return True
    def draw(self,context):
        l=self.layout
        if not self.has_selection:
            l.label(text='Choose what to edit',icon='INFO')
            l.label(text=self.selection_hint)
            box=l.box();box.label(text='1. Select a RoadLab road and enter Edit Mode (Tab).')
            box.label(text='2. Junction: select its shared center point.')
            box.label(text='   Street: select two or more adjacent curve points.')
            box.label(text='3. Open the lane window to edit the selection.')
            l.label(text='Shift-click adds points. Existing selections are kept.')
            return
        if self.is_junction:
            l.label(text=f'{self.junction_label} · {len(json.loads(self.choices_json))} approaches');l.prop(self,'approach')
        else:
            l.label(text=f'{len(json.loads(self.choices_json))} selected street segment(s)')
            obj,indices,targets=draft_target(context);lookup={x['id']:i for i,x in enumerate(point_settings.records(obj))};ps=point_settings.points(obj);endpoint=targets[0][0] if context.scene.roadlab_lane_draft.reverse else targets[-1][1];co=obj.matrix_world@Vector(ps[lookup[endpoint]].co[:3]);l.label(text=f'Incoming toward ({co.x:.1f}, {co.y:.1f})')
        l.label(text='Driving side: '+context.scene.roadlab_map_settings.traffic_side.title())
        draw_lanes(l,context,self.is_junction);l.label(text='Apply saves this section / approach')
        l.operator('roadlab.lane_remove')
    def execute(self,context):
        if self.has_selection:bpy.ops.roadlab.lane_apply('INVOKE_DEFAULT')
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
                try:rebuild(obj,scene)
                except Exception as error:obj['roadlab_marking_warnings']=json.dumps([str(error)])
    return None


classes=(ROADLAB_Lane,ROADLAB_LaneDraft,ROADLAB_UL_lanes,ROADLAB_OT_lane_edit,ROADLAB_OT_lane_count,ROADLAB_OT_lane_apply,ROADLAB_OT_lane_remove,ROADLAB_OT_lane_window,ROADLAB_OT_lane_pick,ROADLAB_PT_lanes)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.roadlab_lane_draft=PointerProperty(type=ROADLAB_LaneDraft)
    bpy.utils.register_tool(ROADLAB_WST_lanes,separator=True)
    bpy.app.timers.register(refresh_loaded_markings,first_interval=.1)
def unregister():
    if bpy.app.timers.is_registered(refresh_loaded_markings):bpy.app.timers.unregister(refresh_loaded_markings)
    bpy.utils.unregister_tool(ROADLAB_WST_lanes)
    del bpy.types.Scene.roadlab_lane_draft
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
