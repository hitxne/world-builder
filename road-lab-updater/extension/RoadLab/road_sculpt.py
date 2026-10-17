"""Blender brush adapter over the portable RoadLab displacement field."""
import math,time,json,bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import EnumProperty,FloatProperty,PointerProperty,BoolProperty
from . import road_heightfield as field
_BASE={}
_PAINTING=False
def is_painting():return _PAINTING

def remember(road,verts,faces,signature):
    key=road.as_pointer();old=_BASE.get(key)
    if not old or old['signature']!=signature:
        _BASE[key]={'signature':signature,'verts':verts[:],'faces':faces[:],'tree':None}

def base_tree(road):
    item=_BASE.get(road.as_pointer())
    if not item:raise ValueError('Rebuild the road before sculpting')
    if item['tree'] is None:item['tree']=BVHTree.FromPolygons(item['verts'],item['faces'])
    return item['tree']

def apply_stamp(context,road,center,mode,radius,strength,dt,target=None,preview=False):
    tree=base_tree(road)
    def base(x,y):
        hit=tree.ray_cast(Vector((x,y,100000)),Vector((0,0,-1)))
        return hit[0].z if hit[0] is not None else None
    old=road.get('roadlab_sculpt_field','');before=field.decode(old)
    after=field.stamp(before,center,radius,strength,dt,mode,base,target)
    encoded=field.encode(after)
    if encoded==old:return False
    road['roadlab_sculpt_field']=encoded
    if preview:
        from . import road_core
        previous=road_core._busy;road_core._busy=True
        try:road_core.rebuild(road)
        finally:road_core._busy=previous
    else:
        from .selected_points import notify
        notify(context,road)
    return True

class RoadBrushSettings(bpy.types.PropertyGroup):
    mode:EnumProperty(name='Brush',items=[('RAISE','Raise','Lift the road'),('LOWER','Lower','Lower the road'),('FLATTEN','Flatten','Flatten toward the height where the stroke starts'),('SMOOTH','Smooth','Relax local elevation differences'),('WIDEN','Widen','Increase width near the brush; inserts authoring points'),('BANK','Bank','Drag sideways to tilt the road around its centerline')])
    radius:FloatProperty(name='Radius (m)',default=8.,min=1.,max=100.)
    strength:FloatProperty(name='Strength',description='Metres per second for raise/lower; blend rate for flatten/smooth',default=2.,min=.01,max=20.)

class ROADLAB_OT_sculpt(bpy.types.Operator):
    bl_idname='roadlab.sculpt';bl_label='Sculpt road';bl_options={'REGISTER','UNDO'}
    tool_mode:EnumProperty(items=[(m,m.title(),m.title()) for m in ('CURRENT','RAISE','LOWER','FLATTEN','SMOOTH','WIDEN','BANK')],default='CURRENT',options={'HIDDEN'})
    bl_description='Paint road elevation with a circular brush; LMB paints, wheel adjusts radius, Esc restores the session'
    @classmethod
    def poll(cls,context):
        obj=context.scene.wb_native.road
        return obj is not None and bool(obj.get('roadlab_new_core')) and context.active_object==obj and context.mode=='OBJECT' and context.area is not None and context.area.type=='VIEW_3D'
    def invoke(self,context,event):
        global _PAINTING
        self.road=context.scene.wb_native.road;self.original_curve=self.road.data.copy();self.original_points=self.road.get('roadlab_point_settings','[]');self.original=self.road.get('roadlab_sculpt_field','');self.center=None;self.paint=False;self.target=None;self.last=time.monotonic();self.mouse=(event.mouse_x,event.mouse_y)
        self.region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
        if self.region is None:return {'CANCELLED'}
        self.space=context.space_data;self.area=context.area;self.settings=context.scene.roadlab_road_brush
        if self.tool_mode!='CURRENT':self.settings.mode=self.tool_mode
        self.mode=self.settings.mode;self.bank_snapshot=None;self.bank_anchor=None;self.bank_start=event.mouse_x
        xy=(event.mouse_x-self.region.x,event.mouse_y-self.region.y)
        self.one_stroke=self.tool_mode!='CURRENT'
        self.paint=event.type=='LEFTMOUSE' and event.value=='PRESS' and 0<=xy[0]<self.region.width and 0<=xy[1]<self.region.height
        from . import road_core
        road_core.rebuild(self.road,True)
        _PAINTING=self.paint
        self.timer=context.window_manager.event_timer_add(.05,window=context.window)
        self.draw_handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_brush,(), 'WINDOW','POST_VIEW')
        context.window_manager.modal_handler_add(self);self.area.tag_redraw()
        return {'RUNNING_MODAL'}
    def hit(self,context):
        from bpy_extras import view3d_utils
        xy=(self.mouse[0]-self.region.x,self.mouse[1]-self.region.y)
        if not (0<=xy[0]<self.region.width and 0<=xy[1]<self.region.height):return None
        rv=self.space.region_3d;origin=view3d_utils.region_2d_to_origin_3d(self.region,rv,xy);direction=view3d_utils.region_2d_to_vector_3d(self.region,rv,xy)
        inverse=self.road.matrix_world.inverted();local=inverse@origin;ray=(inverse.to_3x3()@direction).normalized()
        helper=self.road['roadlab_core_mesh']
        key=(helper.data.as_pointer(),self.road.get('roadlab_core_signature'))
        if getattr(self,'_hit_key',None)!=key:
            self._hit_tree=BVHTree.FromPolygons([v.co for v in helper.data.vertices],[list(f.vertices) for f in helper.data.polygons])
            self._hit_key=key
        found=self._hit_tree.ray_cast(local,ray)
        return found[0]
    def draw_brush(self):
        if self.center is None:return
        import gpu
        from gpu_extras.batch import batch_for_shader
        p=self.center;r=self.settings.radius;matrix=self.road.matrix_world
        points=[matrix@Vector((p.x+r*math.cos(i*2*math.pi/64),p.y+r*math.sin(i*2*math.pi/64),p.z+.06)) for i in range(65)]
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');batch=batch_for_shader(shader,'LINE_STRIP',{'pos':points})
        gpu.state.blend_set('ALPHA');shader.bind();shader.uniform_float('color',(1.,.45,.08,.95));batch.draw(shader);gpu.state.blend_set('NONE')
    def finish(self,context,cancel=False):
        global _PAINTING
        _PAINTING=False
        context.window_manager.event_timer_remove(self.timer);bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle,'WINDOW');self.area.header_text_set(None)
        if cancel:
            old=self.road.data;self.road.data=self.original_curve
            if old.users==0:bpy.data.curves.remove(old)
            self.road['roadlab_point_settings']=self.original_points
            self.road['roadlab_sculpt_field']=self.original
            from .selected_points import notify
            notify(context,self.road)
        from . import road_core,core_terrain
        road_core.rebuild(self.road,True);core_terrain.rebuild(context.scene);road_core.flush_pending(force=True)
        if not cancel and self.original_curve.users==0:bpy.data.curves.remove(self.original_curve)
        self.area.tag_redraw()
        return {'CANCELLED'} if cancel else {'FINISHED'}
    def modal(self,context,event):
        global _PAINTING
        if event.type=='ESC':return self.finish(context,True)
        if event.type in ('RET','NUMPAD_ENTER','RIGHTMOUSE') and event.value=='PRESS':return self.finish(context)
        if event.type in ('MIDDLEMOUSE',) or event.alt:return {'PASS_THROUGH'}
        if event.type in ('WHEELUPMOUSE','WHEELDOWNMOUSE'):
            self.settings.radius=max(1.,min(100.,self.settings.radius*(1.1 if event.type=='WHEELUPMOUSE' else 1/1.1)))
        if event.type=='MOUSEMOVE':self.mouse=(event.mouse_x,event.mouse_y)
        if event.type=='LEFTMOUSE':
            self.mouse=(event.mouse_x,event.mouse_y);self.paint=event.value=='PRESS';self.target=None;self.last=time.monotonic();_PAINTING=self.paint
            if self.paint:self.bank_snapshot=None;self.bank_anchor=None;self.bank_start=event.mouse_x
            if not self.paint:
                if self.one_stroke:return self.finish(context)
                from . import road_core,core_terrain
                core_terrain.rebuild(context.scene);road_core.flush_pending(force=True)
        if event.type in ('MOUSEMOVE','TIMER','LEFTMOUSE'):
            self.center=self.hit(context);now=time.monotonic()
            if self.paint and self.center is not None and now-self.last>=.04:
                if self.target is None:self.target=self.center.z
                try:
                    if self.mode=='WIDEN':
                        from . import road_authoring,road_core
                        previous=road_core._busy;road_core._busy=True
                        try:
                            road_authoring.widen(self.road,self.center.xy,self.settings.radius,self.settings.strength,now-self.last);road_core.rebuild(self.road)
                        finally:road_core._busy=previous
                    elif self.mode=='BANK':
                        from . import road_authoring,road_paths,road_core
                        if self.bank_snapshot is None:
                            self.bank_snapshot=field.decode(self.road.get('roadlab_sculpt_field',''));self.bank_anchor=road_paths.closest(road_authoring.paths(self.road),self.center)
                        tree=base_tree(self.road)
                        def base(x,y):
                            hit=tree.ray_cast(Vector((x,y,100000)),Vector((0,0,-1)))
                            return hit[0].z if hit[0] is not None else None
                        angle=(self.mouse[0]-self.bank_start)*.003*self.settings.strength
                        altered=field.bank(self.bank_snapshot,self.bank_anchor['point'],self.bank_anchor['tangent'],self.settings.radius,angle,base)
                        self.road['roadlab_sculpt_field']=field.encode(altered)
                        previous=road_core._busy;road_core._busy=True
                        try:road_core.rebuild(self.road)
                        finally:road_core._busy=previous
                    else:apply_stamp(context,self.road,self.center.xy,self.mode,self.settings.radius,self.settings.strength,now-self.last,self.target,preview=True)
                except (ValueError,RuntimeError) as exc:self.report({'ERROR'},str(exc));return self.finish(context,True)
                self.last=now
            self.area.header_text_set(f'Road sculpt: {self.mode.title()} | Radius {self.settings.radius:.1f} m | LMB paint | Wheel size | Enter finish | Esc cancel')
            self.area.tag_redraw()
        return {'RUNNING_MODAL'}

class ROADLAB_OT_reset_sculpt(bpy.types.Operator):
    bl_idname='roadlab.reset_sculpt';bl_label='Clear road sculpt';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):
        obj=context.scene.wb_native.road
        return obj is not None and bool(field.decode(obj.get('roadlab_sculpt_field','')))
    def execute(self,context):
        obj=context.scene.wb_native.road;obj['roadlab_sculpt_field']=''
        from .selected_points import notify
        notify(context,obj);return {'FINISHED'}

class ROADLAB_OT_slice(bpy.types.Operator):
    bl_idname='roadlab.slice';bl_label='Slice terrain contact';bl_options={'REGISTER','UNDO'}
    bl_description='Click to stop terrain contact; Alt-click to restore it farther along the same road spline'
    reattach:BoolProperty(default=False,options={'HIDDEN'})
    poll=ROADLAB_OT_sculpt.poll
    hit=ROADLAB_OT_sculpt.hit
    def invoke(self,context,event):
        self.road=context.scene.wb_native.road;self.mouse=(event.mouse_x,event.mouse_y);self.space=context.space_data
        self.region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
        if self.region is None:return {'CANCELLED'}
        hit=self.hit(context)
        if hit is None:self.report({'WARNING'},'Click on the road');return {'CANCELLED'}
        from . import road_authoring
        try:road_authoring.slice_contact(self.road,hit,self.reattach or event.alt)
        except ValueError as exc:self.report({'WARNING'},str(exc));return {'CANCELLED'}
        from .selected_points import notify
        notify(context,self.road)
        self.report({'INFO'},'Terrain contact restored' if self.reattach or event.alt else 'Terrain contact stopped; Alt-click to reconnect')
        return {'FINISHED'}

class ROADLAB_OT_reset_slices(bpy.types.Operator):
    bl_idname='roadlab.reset_slices';bl_label='Clear bridge cuts';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        obj=context.scene.wb_native.road;obj['roadlab_bridge_cuts']='[]'
        from .selected_points import notify
        notify(context,obj);return {'FINISHED'}

class ROADLAB_PT_sculpt(bpy.types.Panel):
    bl_label='Road tools';bl_idname='ROADLAB_PT_sculpt';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_order=2;bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):
        obj=context.scene.wb_native.road
        return obj is not None and bool(obj.get('roadlab_new_core')) and context.active_object==obj and context.mode=='OBJECT'
    def draw(self,context):
        layout=self.layout;obj=context.scene.wb_native.road
        from . import road_toolbar
        for pair in [('RAISE','LOWER'),('FLATTEN','SMOOTH'),('WIDEN','BANK'),('SLICE',)]:
            row=layout.row(align=True)
            for mode in pair:row.operator('wm.tool_set_by_id',text=mode.title(),icon_value=road_toolbar.icon(mode)).name='roadlab.'+mode.lower()
        layout.label(text='Brush settings appear in the tool header')
        if ROADLAB_OT_reset_sculpt.poll(context):layout.operator('roadlab.reset_sculpt',icon='LOOP_BACK')
        cuts=json.loads(obj.get('roadlab_bridge_cuts','[]'))
        if cuts:
            layout.label(text=f'{len(cuts)} bridge cut span(s)')
            if any(x.get('pending') for x in cuts):layout.label(text='Alt + Slice to reconnect',icon='INFO')
            layout.operator('roadlab.reset_slices',icon='LOOP_BACK')

classes=(RoadBrushSettings,ROADLAB_OT_sculpt,ROADLAB_OT_reset_sculpt,ROADLAB_OT_slice,ROADLAB_OT_reset_slices,ROADLAB_PT_sculpt)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.roadlab_road_brush=PointerProperty(type=RoadBrushSettings)
    from . import terrain_sculpt,road_toolbar
    terrain_sculpt.register();road_toolbar.register()
def unregister():
    global _PAINTING
    from . import road_toolbar
    road_toolbar.unregister()
    from . import terrain_sculpt
    terrain_sculpt.unregister()
    _PAINTING=False;_BASE.clear();del bpy.types.Scene.roadlab_road_brush
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
