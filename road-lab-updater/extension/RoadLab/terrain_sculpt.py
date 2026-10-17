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
            if not obj.data.materials:
                from . import material
                obj.data.materials.append(material('grass'))
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
        from . import core_terrain
        from .sculpt_preview import HeightPreview
        self.obj=context.scene.wb_native.terrain;self.settings=context.scene.roadlab_terrain_brush
        self.region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
        if self.region is None or _ACTIVE:return {'CANCELLED'}
        self.original=self.obj.get('roadlab_terrain_field','');self.original_enabled=self.obj.roadlab_core_terrain_enabled
        self.obj.roadlab_core_terrain_enabled=True
        self.mouse=(event.mouse_x,event.mouse_y);self.space=context.space_data;self.area=context.area
        self.center=None;self.stroke_box=None;self.target=None;self.paint=True;self.last=time.monotonic()
        self.values=field.decode(self.original);self.tree=source_tree(self.obj);self.base_cache={}
        self.ray_height=max((v.co.z for v in self.obj.data.vertices),default=0.)+1.
        self.preview=None;self.timer=None;self.handle=None;_ACTIVE=True
        try:
            core_terrain.rebuild(context.scene)
            helper=self.obj.get('roadlab_core_terrain_mesh')
            if helper is None:core_terrain.attach(self.obj);helper=self.obj['roadlab_core_terrain_mesh']
            if not self.obj.get('roadlab_core_terrain_signature'):
                old=helper.data;helper.data=self.obj.data.copy()
                if old.users==0:bpy.data.meshes.remove(old)
            for mod in self.obj.modifiers:
                if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('ROADLAB_TERRAIN_CONTACT'):mod.show_viewport=True
            state=core_terrain._STATE.get(self.obj.as_pointer(),{})
            self.preview=HeightPreview(self.obj,helper,self.values,state.get('sculpt_weights') if self.obj.get('roadlab_core_terrain_signature') else None)
            self.center=self.hit()
            if self.center is not None:
                self.preview.ensure_detail(self.center.xy,self.settings.radius);self.target=self.center.z;self.stamp(.04)
            self.timer=context.window_manager.event_timer_add(.04,window=context.window)
            self.handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_brush,(),'WINDOW','POST_VIEW')
            context.window_manager.modal_handler_add(self);return {'RUNNING_MODAL'}
        except (ValueError,RuntimeError) as exc:
            self.report({'ERROR'},str(exc));return self.finish(context,True)
    def hit(self):
        from bpy_extras import view3d_utils
        xy=(self.mouse[0]-self.region.x,self.mouse[1]-self.region.y)
        if not (0<=xy[0]<self.region.width and 0<=xy[1]<self.region.height):return None
        origin=view3d_utils.region_2d_to_origin_3d(self.region,self.space.region_3d,xy)
        direction=view3d_utils.region_2d_to_vector_3d(self.region,self.space.region_3d,xy)
        inv=self.obj.matrix_world.inverted()
        return self.preview.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())
    def base_height(self,x,y):
        key=(x,y)
        if key not in self.base_cache:
            p=self.tree.ray_cast(Vector((x,y,self.ray_height)),Vector((0,0,-1)))[0]
            if len(self.base_cache)>=65536:self.base_cache.clear()
            self.base_cache[key]=p.z if p is not None else None
        return self.base_cache[key]
    def stamp(self,dt):
        patch=field.stamp_patch(self.values,self.center.xy,self.settings.radius,self.settings.strength,dt,self.tool_mode,self.base_height,self.target)
        if not patch:return False
        self.values.update(patch);self.preview.update(self.center.xy,self.settings.radius)
        r=self.settings.radius+2;b=(self.center.x-r,self.center.y-r,self.center.x+r,self.center.y+r)
        old=self.stroke_box;self.stroke_box=b if old is None else (min(old[0],b[0]),min(old[1],b[1]),max(old[2],b[2]),max(old[3],b[3]))
        return True
    def draw_brush(self):
        if self.center is None:return
        from .brush_cursor import draw_rings
        draw_rings(self.obj,self.center,self.settings.radius,self.preview.height,(.3,1.,.4,1))
    def finish(self,context,cancel=False):
        global _ACTIVE
        from . import core_terrain
        try:
            if self.timer is not None:context.window_manager.event_timer_remove(self.timer)
            if self.handle is not None:bpy.types.SpaceView3D.draw_handler_remove(self.handle,'WINDOW')
            self.area.header_text_set(None)
            if self.preview is not None:self.preview.close()
            if cancel:
                self.obj['roadlab_terrain_field']=self.original
                self.obj.roadlab_core_terrain_enabled=self.original_enabled
            elif self.stroke_box:
                self.obj['roadlab_terrain_field']=field.encode(self.values)
                _DIRTY[self.obj.as_pointer()]={'box':self.stroke_box,'radius':self.settings.radius,'refine':True,'coarsen':True}
                core_terrain.rebuild(context.scene,True)
            else:self.obj.roadlab_core_terrain_enabled=self.original_enabled
            # Restore visibility after cancelling a first stroke on an unsculpted plane.
            core_terrain.rebuild(context.scene)
        finally:
            _ACTIVE=False;self.area.tag_redraw()
        return {'CANCELLED'} if cancel else {'FINISHED'}
    def modal(self,context,event):
        if event.type=='ESC':return self.finish(context,True)
        if event.type in ('RET','NUMPAD_ENTER','RIGHTMOUSE') and event.value=='PRESS':return self.finish(context)
        if context.active_object!=self.obj or context.mode!='OBJECT':return self.finish(context)
        tool=context.workspace.tools.from_space_view3d_mode(context.mode,create=False)
        if tool and tool.idname!='roadlab.terrain_'+self.tool_mode.lower():return self.finish(context)
        if event.type=='MOUSEMOVE':self.mouse=(event.mouse_x,event.mouse_y)
        xy=(event.mouse_x-self.region.x,event.mouse_y-self.region.y)
        inside=0<=xy[0]<self.region.width and 0<=xy[1]<self.region.height
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':self.paint=False;self.target=None
        if event.type=='MIDDLEMOUSE' or event.alt or (not inside and event.type!='TIMER'):
            self.center=None;self.area.tag_redraw();return {'PASS_THROUGH'}
        if event.type in ('WHEELUPMOUSE','WHEELDOWNMOUSE'):
            self.settings.radius=max(1.,min(100.,self.settings.radius*(1.1 if event.type=='WHEELUPMOUSE' else 1/1.1)))
        if event.type=='LEFTMOUSE' and event.value=='PRESS':
            self.mouse=(event.mouse_x,event.mouse_y);self.center=self.hit();self.paint=True;self.last=time.monotonic()
            if self.center is not None:
                self.preview.ensure_detail(self.center.xy,self.settings.radius);self.target=self.center.z;self.stamp(.04)
        if event.type in ('TIMER','MOUSEMOVE','WHEELUPMOUSE','WHEELDOWNMOUSE'):
            self.center=self.hit();now=time.monotonic()
            if event.type=='TIMER' and self.paint and self.center is not None:
                try:
                    self.preview.ensure_detail(self.center.xy,self.settings.radius)
                    self.stamp(min(now-self.last,.1))
                except (ValueError,RuntimeError) as exc:self.report({'ERROR'},str(exc));return self.finish(context,True)
                self.last=now
            self.area.header_text_set(f'Terrain {self.tool_mode.title()} | Preview | LMB strokes | Enter apply detail | Esc cancel strokes')
            self.area.tag_redraw()
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
