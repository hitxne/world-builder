"""Independent junction ports keep medians aligned and permit manual arm shifts."""
import json,math,copy
from mathutils import Vector

def settings(road):return json.loads(road.get('roadlab_approach_offsets','[]'))
def traffic_side(road):
    import bpy
    scene=road.users_scene[0] if road.users_scene else bpy.context.scene
    return scene.roadlab_map_settings.traffic_side

def signature(road):
    profiles=[]
    for row in json.loads(road.get('roadlab_lanes','[]')):
        ni=sum(l['width'] for l in row['incoming']);no=sum(l['width'] for l in row['outgoing'])
        if row['incoming'] and row['outgoing'] and abs(ni-no)>1e-6:profiles.append((row['endpoints'],ni,no,row.get('median',0.),row.get('lane_transition',30.)))
    return [profiles,settings(road),traffic_side(road) if profiles else None]

class PortOffsets(dict):
    def __init__(self):super().__init__();self.gates={}

def ports(road,nodes,positions=None,edges=None):
    from .point_settings import records
    positions=positions or {};lookup={r['id']:tuple(r['co']) for r in records(road)};result=PortOffsets()
    side=1 if traffic_side(road)=='RIGHT' else -1
    for row in json.loads(road.get('roadlab_lanes','[]')):
        if not row['incoming'] or not row['outgoing']:continue
        if not all(i in lookup for i in row['endpoints']):continue
        a,b=(Vector(positions.get(lookup[i],lookup[i])) for i in row['endpoints'])
        delta=b-a;delta.z=0;length=delta.length
        if length<1e-6:continue
        u=delta/length;ni=sum(l['width'] for l in row['incoming']);no=sum(l['width'] for l in row['outgoing'])
        if abs(ni-no)<1e-6:continue
        left=(no if side>0 else ni)+row.get('median',0.)/2+.5
        right=(ni if side>0 else no)+row.get('median',0.)/2+.5
        xmin,xmax=sorted((a.x,b.x));ymin,ymax=sorted((a.y,b.y))
        for p,neighbors in nodes.items():
            if not xmin-1e-4<=p[0]<=xmax+1e-4 or not ymin-1e-4<=p[1]<=ymax+1e-4:continue
            v=Vector(p)-a;s=v.dot(u)
            if not -1e-4<=s<=length+1e-4 or abs(v.x*u.y-v.y*u.x)>1e-4:continue
            for q in neighbors:
                d=Vector(q)-Vector(p);d.z=0
                qs=(Vector(q)-a).dot(u)
                overlap=min(max(s,qs),length)-max(min(s,qs),0.)
                if overlap>1e-5 and d.length>1e-6 and abs(d.normalized().dot(u))>.9999:
                    if edges is not None:
                        from .surface_network import edge_width
                        half=edge_width(edges,p,q)/2
                        center=max(left-half,min(0.,half-right))
                    else:center=side*(no-ni)/2
                    if abs(center)>1e-6:result.setdefault(p,{})[q]=center*(1 if d.dot(u)>0 else -1)
    for row in settings(road):
        if not all(i in lookup for i in row['endpoints']):continue
        other,anchor=(positions.get(lookup[i],lookup[i]) for i in row['endpoints'])
        center=min(nodes,key=lambda p:math.dist(p,anchor),default=None)
        if center is None or math.dist(center,anchor)>1e-4 or len(nodes[center])<3:continue
        u=Vector(other)-Vector(anchor);u.z=0
        if u.length<1e-6:continue
        u.normalize();neighbor=max(nodes[center],key=lambda p:(Vector(p)-Vector(center)).normalized().dot(u))
        if (Vector(neighbor)-Vector(center)).normalized().dot(u)<.8:continue
        result.setdefault(center,{})[neighbor]=result.get(center,{}).get(neighbor,0.)+row['offset']
    for p,neighbors in nodes.items():
        if len(neighbors)!=2:continue
        a,b=neighbors;ua=Vector(a)-Vector(p);ub=Vector(b)-Vector(p);ua.z=ub.z=0
        if ua.normalized().dot(ub.normalized())>-.9999:continue
        if abs(sum(result.get(p,{}).get(q,0.) for q in neighbors))<1e-6:continue
        runs=[c.get('lane_transition',30.) for c in json.loads(road.get('roadlab_lanes','[]')) if any(i in lookup and (Vector(positions.get(tuple(round(v,6) for v in lookup[i]),lookup[i]))-Vector(p)).length<1e-4 for i in c['endpoints'])]
        result.gates[p]=min(max(runs,default=30.)/2,min(ua.length,ub.length)*.35)
    return result

def edited(road,endpoints,value):
    result=[r for r in settings(road) if r['endpoints']!=list(endpoints)]
    if abs(value)>1e-6:result.append(dict(endpoints=list(endpoints),offset=value))
    return result

def warp(road,config,plans,side):
    """Use the same cross-section shifts for paint, arrows and crossing endpoints."""
    from .point_settings import records
    lookup={r['id']:Vector(r['co']) for r in records(road)}
    if not all(i in lookup for i in config['endpoints']):return plans
    a,b=(lookup[i] for i in config['endpoints']);u=b-a;u.z=0;length=u.length
    if length<1e-6:return plans
    u/=length;normal=Vector((-u.y,u.x,0));sign=1 if side=='RIGHT' else -1
    center=sign*(sum(l['width'] for l in config['outgoing'])-sum(l['width'] for l in config['incoming']))/2 if config['incoming'] and config['outgoing'] else 0.
    offsets=[];report=json.loads(road.get('roadlab_core_report','{}'))
    for row in settings(road):
        if frozenset(row['endpoints'])!=frozenset(config['endpoints']):continue
        other,anchor=(lookup[i] for i in row['endpoints']);out=other-anchor;out.z=0
        if out.length<1e-6:continue
        out.normalize();n=Vector((-out.y,out.x,0));gate=0.;render_anchor=anchor
        for corner in report.get('radius_limits',[]):
            if corner.get('geometry_junction') is not None and (Vector(corner['junction'])-anchor).length<.01:render_anchor=Vector(corner['geometry_junction']);break
        for placement in report.get('approach_ports',[]):
            c=Vector(placement['junction']);q=Vector(placement['neighbor'])
            if (c-render_anchor).length<.01 and (q-c).normalized().dot(out)>.8:
                gate=max(gate,(Vector(placement.get('gate_center',c))-anchor).dot(out))
                actual=q-c;actual.z=0;actual.normalize();n=Vector((-actual.y,actual.x,0))
        offsets.append((anchor,out,n*row['offset'],gate))
    if abs(center)<1e-6 and not offsets:return plans
    def point(p):
        p=Vector(p);delta=normal*center
        for anchor,out,shift,gate in offsets:
            s=(p-anchor).dot(out);weight=max(0.,min(1.,(length-s)/max(.1,length-gate)));delta+=shift*weight
        return list(p+delta)
    output=[]
    for original in plans:
        mark=copy.deepcopy(original)
        if mark.get('pavement_anchored'):
            if mark.get('path'):mark['center']=list(mark['path'][len(mark['path'])//2])
            output.append(mark);continue
        c=mark['center'];f=mark['forward'];mark['center']=point(c)
        p,q=(Vector(point([c[0]+f[0]*t,c[1]+f[1]*t,c[2]])) for t in (-1,1));d=q-p;d.z=0
        if d.length>1e-8:mark['forward']=list(d.normalized()[:2])
        if mark.get('path'):mark['path']=[point(p) for p in mark['path']]
        elif mark['role'][0] in ('outer','divider','center-yellow','median-yellow','center-white'):
            h=mark['size'][1]/2;mark['path']=[point([c[0]+f[0]*t,c[1]+f[1]*t,c[2]]) for t in (-h,h)]
        if mark.get('crosswalk_ends'):mark['crosswalk_ends']=[point(p) for p in mark['crosswalk_ends']]
        output.append(mark)
    return output

# A compact isolated draft keeps geometry previews out of the saved scene.
import bpy
from bpy.props import StringProperty,EnumProperty,FloatProperty
_SESSION=None
_ENUMS={}

def enum_items(self,context):
    key=(self.road_name,self.choices_json)
    if key not in _ENUMS:
        from .lane_editor import approach_geometry,approach_labels
        obj=bpy.data.objects.get(self.road_name)
        labels=approach_labels(approach_geometry(obj,json.loads(self.choices_json))) if obj else []
        _ENUMS[key]=[(str(i),label[0],label[1]) for i,label in enumerate(labels)]
    return _ENUMS[key]

@bpy.app.handlers.persistent
def clear_preview(_unused=None):
    global _SESSION
    session=_SESSION;_SESSION=None
    if session and session.get('handler') is not None:bpy.types.SpaceView3D.draw_handler_remove(session['handler'],'WINDOW')

def update_preview(operator,context):
    session=_SESSION
    if not session or session.get('busy'):return
    from .lane_add import preview_meshes
    row=json.loads(operator.choices_json)[int(operator.arm)]
    session['offsets']=[r for r in session['offsets'] if r['endpoints']!=row]
    if abs(operator.offset)>1e-6:session['offsets'].append(dict(endpoints=row,offset=operator.offset))
    signature=json.dumps(session['offsets'],sort_keys=True)
    if signature==session.get('signature'):return
    session['signature']=signature;session['batches']=None
    obj=bpy.data.objects.get(operator.road_name)
    try:
        session['meshes']=preview_meshes(obj,json.loads(obj.get('roadlab_lane_pockets','[]')),{'roadlab_approach_offsets':signature});session['error']=''
    except (ValueError,RuntimeError) as error:session['meshes']=[];session['error']=str(error)
    for area in context.screen.areas if context.screen else []:
        if area.type=='VIEW_3D':area.tag_redraw()

def arm_changed(self,context):
    session=_SESSION
    if not session or session.get('busy'):return
    session['busy']=True
    try:
        row=json.loads(self.choices_json)[int(self.arm)]
        self.offset=next((r['offset'] for r in session['offsets'] if r['endpoints']==row),0.)
    finally:session['busy']=False
    update_preview(self,context)

def draw_session(session):
    if not session or not session.get('meshes'):return
    import gpu
    from gpu_extras.batch import batch_for_shader
    if session.get('batches') is None:
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');batches=[]
        for vertices,faces in session['meshes']:
            triangles=[(f[0],f[i],f[i+1]) for f in faces for i in range(1,len(f)-1)]
            batches.append(batch_for_shader(shader,'TRIS',{'pos':[(x,y,z+.015) for x,y,z in vertices]},indices=triangles))
        session['batches']=(shader,batches)
    shader,batches=session['batches'];gpu.state.blend_set('ALPHA');gpu.state.depth_test_set('LESS_EQUAL')
    try:
        shader.bind();shader.uniform_float('color',(.08,.45,1.,.5))
        for batch in batches:batch.draw(shader)
    finally:gpu.state.blend_set('NONE');gpu.state.depth_test_set('NONE')

def draw_preview():draw_session(_SESSION)

class ROADLAB_OT_approach_alignment(bpy.types.Operator):
    bl_idname='roadlab.approach_alignment';bl_label='Approach alignment';bl_options={'REGISTER','UNDO'}
    bl_description='Offset one junction arm sideways, with a blue draft before applying'
    road_name:StringProperty(options={'HIDDEN'})
    choices_json:StringProperty(default='[]',options={'HIDDEN'})
    arm:EnumProperty(name='Road',items=enum_items,update=arm_changed)
    offset:FloatProperty(name='Sideways offset (m)',default=0.,min=-10,max=10,precision=2,update=update_preview)
    @classmethod
    def poll(cls,context):
        from .lane_editor import road
        return context.mode=='EDIT_CURVE' and road(context) is not None
    def invoke(self,context,event):
        global _SESSION
        from .lane_editor import selection_targets
        try:
            obj,choices,junction=selection_targets(context)
            if not junction or len(choices)<3:raise ValueError('Select one junction point with three or more streets')
        except ValueError as error:self.report({'WARNING'},str(error));return {'CANCELLED'}
        clear_preview();self.road_name=obj.name;self.choices_json=json.dumps(choices)
        _SESSION={'offsets':settings(obj),'busy':True,'handler':None,'meshes':[],'error':''}
        self.arm='0';self.offset=next((r['offset'] for r in _SESSION['offsets'] if r['endpoints']==choices[0]),0.)
        _SESSION['busy']=False;update_preview(self,context)
        _SESSION['handler']=bpy.types.SpaceView3D.draw_handler_add(draw_preview,(),'WINDOW','POST_VIEW')
        return context.window_manager.invoke_props_dialog(self,width=400,confirm_text='Apply alignment')
    def draw(self,context):
        self.layout.prop(self,'arm');self.layout.prop(self,'offset')
        self.layout.label(text='Positive: right while facing the junction.')
        self.layout.label(text='0 m restores automatic median alignment.')
        if _SESSION and _SESSION.get('error'):self.layout.label(text=_SESSION['error'],icon='ERROR')
        else:self.layout.label(text='Blue is a draft. Apply saves; Cancel discards.')
    def execute(self,context):
        obj=bpy.data.objects.get(self.road_name)
        if obj is None:clear_preview();return {'CANCELLED'}
        if _SESSION:
            update_preview(self,context)
            if _SESSION.get('error'):
                self.report({'ERROR'},_SESSION['error']);clear_preview();return {'CANCELLED'}
            offsets=list(_SESSION['offsets'])
        else:offsets=edited(obj,json.loads(self.choices_json)[int(self.arm)],self.offset)
        obj['roadlab_approach_offsets']=json.dumps(offsets);clear_preview()
        from .selected_points import notify
        notify(context,obj)
        return {'FINISHED'}
    def cancel(self,context):clear_preview()

def register():
    bpy.utils.register_class(ROADLAB_OT_approach_alignment)
    if clear_preview not in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.append(clear_preview)

def unregister():
    clear_preview()
    if clear_preview in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.remove(clear_preview)
    bpy.utils.unregister_class(ROADLAB_OT_approach_alignment);_ENUMS.clear()


class GeometryDraft:
    """Owned preview footprint for lane-count changes; the source stays intact."""
    def __init__(self,source,proxy,scene):
        self.source=source;self.proxy=proxy;self.scene=scene;self.signature=None
        self.helper=bpy.data.objects.new('RoadLab Alignment Draft',bpy.data.meshes.new('RoadLab Alignment Draft'))
        scene.collection.objects.link(self.helper);self.helper.hide_set(True);self.helper.hide_render=True;self.helper['roadlab_temporary_preview']=True
        self.drawing={'meshes':[],'batches':None};self.handler=bpy.types.SpaceView3D.draw_handler_add(draw_session,(self.drawing,),'WINDOW','POST_VIEW')
    def update(self,configs):
        from .lane_add import preview_meshes
        key=json.dumps([configs,self.proxy.get('roadlab_point_settings'),self.source.get('roadlab_core_signature')],sort_keys=True)
        if key==self.signature:return
        metadata={};meshes=preview_meshes(self.source,json.loads(self.source.get('roadlab_lane_pockets','[]')),{'roadlab_lanes':json.dumps(configs),'roadlab_point_settings':self.proxy.get('roadlab_point_settings',self.source.get('roadlab_point_settings','[]'))},metadata)
        inv=self.source.matrix_world.inverted();vertices,faces=meshes[0]
        mesh=bpy.data.meshes.new('RoadLab Alignment Draft');mesh.from_pydata([inv@Vector(v) for v in vertices],[],faces);mesh.update()
        old=self.helper.data;self.helper.data=mesh;self.helper.matrix_world=self.source.matrix_world.copy()
        if old.users==0:bpy.data.meshes.remove(old)
        self.proxy['roadlab_core_mesh']=self.helper;self.proxy['roadlab_core_report']=metadata['report'];self.proxy['roadlab_core_signature']=metadata['signature']
        self.drawing.update(meshes=meshes,batches=None);self.signature=key
    def close(self):
        if self.handler is not None:bpy.types.SpaceView3D.draw_handler_remove(self.handler,'WINDOW');self.handler=None
        if self.helper is not None:
            mesh=self.helper.data;bpy.data.objects.remove(self.helper,do_unlink=True);self.helper=None
            if mesh.users==0:bpy.data.meshes.remove(mesh)
        self.drawing.clear()

def protected(road,positions=None):
    """Keep straight handles only where a saved cross-section actually changes."""
    from .point_settings import records
    positions=positions or {};lookup={r['id']:tuple(r['co']) for r in records(road)};incident={}
    from .road_core import key
    for c in json.loads(road.get('roadlab_lanes','[]')):
        a,b=c['endpoints']
        if a not in lookup or b not in lookup:continue
        for ident,start in ((a,True),(b,False)):
            p=key(positions.get(key(lookup[ident]),lookup[ident]))
            profile=tuple(r['width'] for r in c['incoming' if start else 'outgoing']),tuple(r['width'] for r in c['outgoing' if start else 'incoming']),c.get('median',0.)
            incident.setdefault(p,[]).append(profile)
    return {p for p,rows in incident.items() if len(rows)==2 and rows[0]!=(rows[1][1],rows[1][0],rows[1][2])}
