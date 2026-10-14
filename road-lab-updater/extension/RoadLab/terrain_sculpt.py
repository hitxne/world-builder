"""Current-core terrain brushes with local cavity refinement and source preservation."""
import bpy,time,math
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import PointerProperty,EnumProperty
from . import road_heightfield as field
_DIRTY={}
_ACTIVE=False
def is_active():return _ACTIVE
def pending(obj):return _DIRTY.get(obj.as_pointer())
def clear_pending(obj):_DIRTY.pop(obj.as_pointer(),None)
def mark(obj,center,radius,refine=True,coarsen=False):
    r=radius+2;_DIRTY[obj.as_pointer()]={'box':(center[0]-r,center[1]-r,center[0]+r,center[1]+r),'radius':radius,'refine':refine,'coarsen':coarsen}

def source_tree(obj):
    obj.data.calc_loop_triangles()
    return BVHTree.FromPolygons([v.co for v in obj.data.vertices],[list(t.vertices) for t in obj.data.loop_triangles],all_triangles=True)

def apply_stamp(obj,center,mode,radius,strength,dt,target=None,refine=True,tree=None):
    tree=tree or source_tree(obj)
    def base(x,y):
        hit=tree.ray_cast(Vector((x,y,100000)),Vector((0,0,-1)));return hit[0].z if hit[0] is not None else None
    before=field.decode(obj.get('roadlab_terrain_field',''));after=field.stamp(before,center,radius,strength,dt,mode,base,target)
    if after==before:return False
    obj['roadlab_terrain_field']=field.encode(after);mark(obj,center,radius,refine)
    from . import core_terrain
    core_terrain.rebuild(bpy.context.scene,True);return True

class ROADLAB_OT_use_terrain(bpy.types.Operator):
    bl_idname='roadlab.use_selected_terrain';bl_label='Use selected mesh as terrain';bl_options={'REGISTER','UNDO'}
    bl_description='Designate an editable plane for local quad terrain sculpting; preserve its world shape'
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and context.active_object is not None and context.active_object.type=='MESH'
    def execute(self,context):
        from . import core_terrain
        obj=context.active_object
        try:
            if any(not (m.type=='NODES' and m.node_group and m.node_group.name.startswith('ROADLAB_TERRAIN_CONTACT')) for m in obj.modifiers):raise ValueError('Select a mesh plane without other modifiers')
            base,loops=core_terrain.source_boundary(obj.data)
            if not loops:raise ValueError('Terrain needs an open mesh plane, not a closed solid')
            world=[tuple(obj.matrix_world@Vector(v)) for v in base]
            if not any(core_terrain.area([world[i][:2] for i in f])>1e-8 for f in loops):raise ValueError('The terrain plane must face upward')
            origin=obj.matrix_world.translation.copy();bake=Matrix.Translation(-origin)@obj.matrix_world
            if not obj.get('roadlab_terrain_field') and bake!=Matrix.Identity(4):
                if obj.data.users>1 or obj.data.library is not None:obj.data=obj.data.copy()
                obj.data.transform(bake,shape_keys=True);obj.matrix_world=Matrix.Translation(origin);obj.data.update()
            context.scene.wb_native.terrain=obj;obj.roadlab_core_terrain_enabled=True
            core_terrain._STATE.pop(obj.as_pointer(),None);core_terrain.rebuild(context.scene,True)
        except (ValueError,RuntimeError) as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
        self.report({'INFO'},'Terrain ready: select Raise, Lower, Flatten or Smooth in the toolbar');return {'FINISHED'}


class ROADLAB_OT_terrain_sculpt(bpy.types.Operator):
    bl_idname='roadlab.terrain_sculpt';bl_label='Sculpt terrain';bl_options={'REGISTER','UNDO'}
    tool_mode:EnumProperty(items=[(m,m.title(),m.title()) for m in ('RAISE','LOWER','FLATTEN','SMOOTH')],default='RAISE',options={'HIDDEN'})
    @classmethod
    def poll(cls,context):
        obj=context.scene.wb_native.terrain
        return obj is not None and obj==context.active_object and obj.type=='MESH' and context.mode=='OBJECT' and context.area is not None and context.area.type=='VIEW_3D'
    def invoke(self,context,event):
        global _ACTIVE
        _ACTIVE=True
        self.obj=context.scene.wb_native.terrain;self.obj.roadlab_core_terrain_enabled=True;self.original=self.obj.get('roadlab_terrain_field','');self.settings=context.scene.roadlab_terrain_brush
        self.mouse=(event.mouse_x,event.mouse_y);self.region=next(r for r in context.area.regions if r.type=='WINDOW');self.space=context.space_data;self.area=context.area;self.center=None;self.stroke_box=None;self.target=None;self.refined_at=None;self.last=time.monotonic();self.tree=source_tree(self.obj)
        from . import core_terrain
        core_terrain.rebuild(context.scene,True)
        self.timer=context.window_manager.event_timer_add(.05,window=context.window);self.handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_brush,(),'WINDOW','POST_VIEW');context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def hit(self):
        from bpy_extras import view3d_utils
        xy=(self.mouse[0]-self.region.x,self.mouse[1]-self.region.y)
        if not (0<=xy[0]<self.region.width and 0<=xy[1]<self.region.height):return None
        origin=view3d_utils.region_2d_to_origin_3d(self.region,self.space.region_3d,xy);direction=view3d_utils.region_2d_to_vector_3d(self.region,self.space.region_3d,xy);inv=self.obj.matrix_world.inverted()
        helper=self.obj.get('roadlab_core_terrain_mesh');mesh=helper.data if helper and self.obj.get('roadlab_core_terrain_signature') else self.obj.data
        tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[list(f.vertices) for f in mesh.polygons])
        return tree.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())[0]
    def draw_brush(self):
        if self.center is None:return
        import gpu
        from gpu_extras.batch import batch_for_shader
        p=self.center;r=self.settings.radius;points=[self.obj.matrix_world@Vector((p.x+r*math.cos(i*math.tau/64),p.y+r*math.sin(i*math.tau/64),p.z+.08)) for i in range(65)]
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');shader.bind();shader.uniform_float('color',(.3,1.,.4,1));batch_for_shader(shader,'LINE_STRIP',{'pos':points}).draw(shader)
    def finish(self,context,cancel=False):
        global _ACTIVE
        _ACTIVE=False
        context.window_manager.event_timer_remove(self.timer);bpy.types.SpaceView3D.draw_handler_remove(self.handle,'WINDOW');self.area.header_text_set(None)
        from . import core_terrain
        if cancel:
            self.obj['roadlab_terrain_field']=self.original;core_terrain._STATE.pop(self.obj.as_pointer(),None)
        if self.stroke_box and not cancel:_DIRTY[self.obj.as_pointer()]={'box':self.stroke_box,'radius':self.settings.radius,'refine':True,'coarsen':True}
        core_terrain.rebuild(context.scene,True);self.area.tag_redraw()
        return {'CANCELLED'} if cancel else {'FINISHED'}
    def modal(self,context,event):
        if event.type=='ESC':return self.finish(context,True)
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':return self.finish(context)
        if event.type in ('WHEELUPMOUSE','WHEELDOWNMOUSE'):self.settings.radius=max(1.,min(100.,self.settings.radius*(1.1 if event.type=='WHEELUPMOUSE' else 1/1.1)))
        if event.type=='MOUSEMOVE':self.mouse=(event.mouse_x,event.mouse_y)
        if event.type in ('TIMER','MOUSEMOVE'):
            self.center=self.hit();now=time.monotonic()
            if self.center is not None and now-self.last>=.04:
                if self.target is None:self.target=self.center.z
                refine=self.refined_at is None or math.dist(self.center.xy,self.refined_at)>self.settings.radius*.3
                try:apply_stamp(self.obj,self.center.xy,self.tool_mode,self.settings.radius,self.settings.strength,now-self.last,self.target,refine,self.tree)
                except (ValueError,RuntimeError) as exc:self.report({'ERROR'},str(exc));return self.finish(context,True)
                b=(self.center.x-self.settings.radius-2,self.center.y-self.settings.radius-2,self.center.x+self.settings.radius+2,self.center.y+self.settings.radius+2)
                old=self.stroke_box;self.stroke_box=b if old is None else (min(old[0],b[0]),min(old[1],b[1]),max(old[2],b[2]),max(old[3],b[3]))
                if refine:self.refined_at=tuple(self.center.xy)
                self.last=now
            self.area.header_text_set(f'Terrain {self.tool_mode.title()} | Radius {self.settings.radius:.1f} m | Release to finish | Esc cancel');self.area.tag_redraw()
        return {'RUNNING_MODAL'}

class ROADLAB_OT_reset_terrain_sculpt(bpy.types.Operator):
    bl_idname='roadlab.reset_terrain_sculpt';bl_label='Clear terrain sculpt';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return context.scene.wb_native.terrain is not None
    def execute(self,context):
        obj=context.scene.wb_native.terrain;obj['roadlab_terrain_field']=''
        from . import core_terrain
        core_terrain._STATE.pop(obj.as_pointer(),None);core_terrain.rebuild(context.scene,True);return {'FINISHED'}

class ROADLAB_PT_terrain_tools(bpy.types.Panel):
    bl_label='Terrain tools';bl_idname='ROADLAB_PT_terrain_tools';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_order=3;bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):
        obj=context.scene.wb_native.terrain
        return obj is not None and obj==context.active_object and context.mode=='OBJECT'
    def draw(self,context):
        from . import road_toolbar
        for pair in [('RAISE','LOWER'),('FLATTEN','SMOOTH')]:
            row=self.layout.row(align=True)
            for mode in pair:row.operator('wm.tool_set_by_id',text=mode.title(),icon_value=road_toolbar.icon(mode)).name='roadlab.terrain_'+mode.lower()
        self.layout.prop(context.scene.roadlab_terrain_brush,'radius');self.layout.prop(context.scene.roadlab_terrain_brush,'strength')
        if context.scene.wb_native.terrain.get('roadlab_terrain_field'):self.layout.operator('roadlab.reset_terrain_sculpt',icon='LOOP_BACK')

classes=(ROADLAB_OT_use_terrain,ROADLAB_OT_terrain_sculpt,ROADLAB_OT_reset_terrain_sculpt,ROADLAB_PT_terrain_tools)
def register():
    from .road_sculpt import RoadBrushSettings
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.roadlab_terrain_brush=PointerProperty(type=RoadBrushSettings)
def unregister():
    global _ACTIVE
    _ACTIVE=False;_DIRTY.clear();del bpy.types.Scene.roadlab_terrain_brush
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
