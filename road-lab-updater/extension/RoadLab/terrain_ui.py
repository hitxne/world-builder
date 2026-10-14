"""Interactive circular terrain brushes with persistent editable baseline."""
import json, time, math
from pathlib import Path
import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty, PointerProperty, StringProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras import view3d_utils
from . import terrain_brush

def terrain_object():
    col=bpy.data.collections.get('WB_GENERATED')
    return next((o for o in col.objects if o.get('wb_id')=='network-terrain'),None) if col else None

def neighbors(obj):
    obj.data.calc_loop_triangles()
    return terrain_brush.adjacency(len(obj.data.vertices),[tuple(t.vertices) for t in obj.data.loop_triangles])

def apply_stamp(obj, settings, center, dt, target, adjacent):
    mesh=obj.data; baseline=mesh.attributes['wb_original_height'];native=obj.get('wb_terrain_backend')=='roadlab';weights=mesh.attributes.get('wb_grade_weight');targets=mesh.attributes.get('wb_grade_target')
    original=[v.value for v in baseline.data]
    values=terrain_brush.stamp([v.co for v in mesh.vertices],original,center,settings.radius,settings.strength,dt,settings.mode,target,adjacent)
    for i, height in enumerate(values):
        if height==original[i]:continue
        baseline.data[i].value=height
        if native:
            mesh.vertices[i].co.z=height;continue
        w=weights.data[i].value;z=height*(1-w)+targets.data[i].value*w
        ceiling=mesh.attributes.get('wb_grade_ceiling')
        mesh.vertices[i].co.z=min(z,ceiling.data[i].value) if ceiling else z
    mesh.update()

def commit(scene,obj):
    from . import object_fingerprint
    graph=json.loads(scene.wb_graph);obj.data.calc_loop_triangles()
    baseline=obj.data.attributes['wb_original_height']
    graph['terrain']['source_mesh']={'vertices':[[v.co.x,v.co.y,baseline.data[v.index].value] for v in obj.data.vertices],'triangles':[list(t.vertices) for t in obj.data.loop_triangles]}
    if obj.get('wb_clearance_signature'):
        graph['terrain']['sculpted_surface']={'vertices':[list(v.co) for v in obj.data.vertices],'triangles':[list(t.vertices) for t in obj.data.loop_triangles],'signature':obj['wb_clearance_signature']}
    elif obj.get('wb_terrain_backend')=='roadlab':graph['terrain'].pop('sculpted_surface',None)
    scene.wb_graph=json.dumps(graph);obj['wb_fingerprint']=object_fingerprint(obj)
    from . import bridge_blender
    bridge_blender.refresh(scene,obj)

def rebuild(scene,graph,force=False):
    from . import network,network_blender,create_spec,delete_collection,object_fingerprint
    network.validate(graph)
    from . import bridge_supports
    bridge_supports.validate(graph)
    old=bpy.data.collections.get('WB_GENERATED')
    if old and not force:
        for obj in old.objects:
            if obj.get('wb_fingerprint') and object_fingerprint(obj)!=obj['wb_fingerprint']:
                raise ValueError('Direct geometry edit detected: keep a copy before rebuilding')
    stage=bpy.data.collections.new('WB_STAGING');scene.collection.children.link(stage)
    def delete(obj):
        data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
        if data and data.users==0:bpy.data.meshes.remove(data)
    try: specs,warnings,context,report=network_blender.assemble(stage,graph,create_spec,delete)
    except Exception:
        delete_collection(stage);raise
    if old:delete_collection(old)
    stage.name='WB_GENERATED'
    for obj in stage.objects:obj['wb_fingerprint']=object_fingerprint(obj)
    scene.wb_graph=json.dumps(graph);scene['wb_validation']=json.dumps(warnings);scene['wb_terrain_report']=json.dumps(report)
    return report

class WBTerrainSettings(bpy.types.PropertyGroup):
    radius:FloatProperty(name='Brush radius (m)',default=12,min=.1,max=500)
    strength:FloatProperty(name='Strength',description='Raise/lower: meters per second. Smooth/flatten: response per second',default=2,min=.01,max=100)
    mode:EnumProperty(name='Brush',items=[('RAISE','Raise','Build hills'),('LOWER','Lower','Dig depressions'),('SMOOTH','Smooth','Soften neighboring heights'),('FLATTEN','Flatten','Blend toward a level elevation')],default='RAISE')
    sample_flatten:BoolProperty(name='Pick height on first click',default=True)
    flatten_height:FloatProperty(name='Flatten height (m)',default=0)
    spacing:FloatProperty(name='Grid spacing (m)',description='Smaller spacing creates more vertices for finer brush detail',default=2,min=.5,max=20)
    blend:FloatProperty(name='Grade blend distance (m)',default=18,min=.5,max=200)
    contact_min:FloatProperty(name='Full-contact distance (m)',default=1,min=0,max=50)
    contact_max:FloatProperty(name='Blend end distance (m)',default=18,min=.1,max=200)

class WB_OT_use_native_terrain_adapter(bpy.types.Operator):
    bl_idname='wb.use_native_terrain_adapter';bl_label='Link terrain nodes';bl_options={'REGISTER','UNDO'}
    filepath:StringProperty(subtype='FILE_PATH')
    filter_glob:StringProperty(default='*.blend',options={'HIDDEN'})
    def invoke(self,context,event):
        context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        try:
            graph=json.loads(context.scene.wb_graph)
            if graph.get('version')!=3:raise ValueError('Load the connected terrain example first')
            graph['terrain'].update(backend='roadlab',tt_library=bpy.path.abspath(self.filepath),tt_flat_min=context.scene.wb_terrain.contact_min,tt_flat_max=context.scene.wb_terrain.contact_max)
            graph['terrain'].pop('sculpted_surface',None)
            rebuild(context.scene,graph)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}

class WB_OT_load_terrain(bpy.types.Operator):
    bl_idname='wb.load_terrain_world';bl_label='Load terrain example';bl_options={'REGISTER','UNDO'}
    filepath:StringProperty(name='RoadLab node library',subtype='FILE_PATH')
    filter_glob:StringProperty(default='*.blend',options={'HIDDEN'})
    def invoke(self,context,event):
        context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        if terrain_object() or bpy.data.collections.get('WB_GENERATED'):
            self.report({'ERROR'},'Open a new scene to load the example; existing WB geometry is preserved');return {'CANCELLED'}
        try:
            graph=json.loads((Path(__file__).parent/'fixtures/network.json').read_text())
            if not self.filepath:raise ValueError('Choose your original upstream node library to load this example')
            graph['terrain'].update(backend='roadlab',tt_library=bpy.path.abspath(self.filepath))
            rebuild(context.scene,graph)
            context.scene.wb_terrain.spacing=graph['terrain']['grid_spacing'];context.scene.wb_terrain.blend=graph['terrain']['blend_distance']
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}

class WB_OT_grade_terrain(bpy.types.Operator):
    bl_idname='wb.grade_terrain';bl_label='Rebuild terrain';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        try:
            graph=json.loads(context.scene.wb_graph);settings=context.scene.wb_terrain
            graph['terrain']['grid_spacing']=settings.spacing;graph['terrain']['blend_distance']=settings.blend
            if graph['terrain'].get('backend')=='roadlab':
                if settings.contact_max<=settings.contact_min:raise ValueError('Terrain blend must exceed the contact band')
                graph['terrain'].update(tt_flat_min=settings.contact_min,tt_flat_max=settings.contact_max)
            rebuild(context.scene,graph)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}

class WB_OT_sculpt_terrain(bpy.types.Operator):
    bl_idname='wb.sculpt_terrain';bl_label='Sculpt terrain';bl_options={'REGISTER','UNDO','BLOCKING'}
    def refresh_bvh(self):
        if self.obj.get('wb_terrain_backend')=='roadlab':
            evaluated=self.obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles();self.bvh=BVHTree.FromPolygons([v.co.copy() for v in mesh.vertices],[tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
            finally:evaluated.to_mesh_clear()
            return
        self.obj.data.calc_loop_triangles()
        self.bvh=BVHTree.FromPolygons([v.co.copy() for v in self.obj.data.vertices],[tuple(t.vertices) for t in self.obj.data.loop_triangles],all_triangles=True)
    def locate(self,event):
        coordinate=(event.mouse_x-self.region.x,event.mouse_y-self.region.y)
        origin=view3d_utils.region_2d_to_origin_3d(self.region,self.rv3d,coordinate)
        direction=view3d_utils.region_2d_to_vector_3d(self.region,self.rv3d,coordinate)
        return self.bvh.ray_cast(origin,direction,100000)[0]
    def draw_cursor(self):
        if self.hit is None:return
        import gpu
        from gpu_extras.batch import batch_for_shader
        radius=self.settings.radius;points=[]
        for i in range(97):
            angle=2*math.pi*i/96;x=self.hit.x+radius*math.cos(angle);y=self.hit.y+radius*math.sin(angle)
            p=self.bvh.ray_cast(Vector((x,y,10000)),Vector((0,0,-1)),20000)[0]
            points.append((x,y,(p.z if p is not None else self.hit.z)+.05))
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');batch=batch_for_shader(shader,'LINE_STRIP',{'pos':points})
        shader.bind();shader.uniform_float('color',(1.,.65,.08,1.));batch.draw(shader)
    def finish(self,context,cancel=False):
        if not cancel:
            try:commit(context.scene,self.obj)
            except Exception as exc:
                cancel=True;context.scene.wb_graph=self.original_graph;self.report({'ERROR'},str(exc))
        if cancel:
            for i,v in enumerate(self.obj.data.vertices):
                v.co.z=self.original_z[i];self.obj.data.attributes['wb_original_height'].data[i].value=self.original_base[i]
            self.obj.data.update()
            from . import object_fingerprint
            self.obj['wb_fingerprint']=object_fingerprint(self.obj)
        bpy.types.SpaceView3D.draw_handler_remove(self.handler,'WINDOW');context.window_manager.event_timer_remove(self.timer)
        context.workspace.status_text_set(None);context.area.tag_redraw()
        return {'CANCELLED'} if cancel else {'FINISHED'}
    def invoke(self,context,event):
        self.obj=terrain_object()
        if context.area.type!='VIEW_3D' or not self.obj or not (self.obj.data.attributes.get('wb_grade_target') or self.obj.get('wb_terrain_backend')=='roadlab'):
            self.report({'ERROR'},'Load the connected terrain example in a 3D viewport first');return {'CANCELLED'}
        if self.obj.get('wb_terrain_backend')!='roadlab' and not self.obj.data.attributes.get('wb_grade_ceiling'):
            self.report({'ERROR'},'Rebuild terrain once to enable face clearance protection');return {'CANCELLED'}
        if context.mode!='OBJECT':self.report({'ERROR'},'Switch to Object Mode first');return {'CANCELLED'}
        if self.obj.matrix_world!=__import__('mathutils').Matrix.Identity(4):
            self.report({'ERROR'},'Terrain transform changed; restore the generated terrain transform before sculpting');return {'CANCELLED'}
        self.settings=context.scene.wb_terrain;self.adjacent=neighbors(self.obj)
        self.original_graph=context.scene.wb_graph
        self.region=next(r for r in context.area.regions if r.type=='WINDOW');self.rv3d=context.space_data.region_3d
        self.original_z=[v.co.z for v in self.obj.data.vertices];self.original_base=[v.value for v in self.obj.data.attributes['wb_original_height'].data]
        self.hit=None;self.painting=False;self.last=time.monotonic();self.target=self.settings.flatten_height;self.refresh_bvh()
        self.handler=bpy.types.SpaceView3D.draw_handler_add(self.draw_cursor,(),'WINDOW','POST_VIEW')
        self.timer=context.window_manager.event_timer_add(.05,window=context.window);context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set('Left drag: sculpt | Shift+wheel: radius | Ctrl+wheel: strength | Enter/right click: finish | Esc: cancel')
        return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if event.type=='ESC':return self.finish(context,True)
        if event.type in ('RET','NUMPAD_ENTER','RIGHTMOUSE') and event.value=='PRESS':return self.finish(context)
        if event.type in ('WHEELUPMOUSE','WHEELDOWNMOUSE') and (event.shift or event.ctrl):
            factor=1.1 if event.type=='WHEELUPMOUSE' else 1/1.1
            if event.shift:self.settings.radius*=factor
            else:self.settings.strength*=factor
            context.area.tag_redraw();return {'RUNNING_MODAL'}
        if event.type=='MOUSEMOVE':self.hit=self.locate(event);context.area.tag_redraw()
        if event.type=='LEFTMOUSE':
            self.painting=event.value=='PRESS';self.hit=self.locate(event);self.last=time.monotonic()
            if self.painting and self.hit is not None and self.settings.sample_flatten:self.target=self.hit.z
            return {'RUNNING_MODAL'}
        if event.type=='TIMER':
            now=time.monotonic();dt=min(.1,now-self.last);self.last=now
            if self.painting and self.hit is not None:
                apply_stamp(self.obj,self.settings,self.hit,dt,self.target,self.adjacent);self.refresh_bvh();context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type in ('MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE','NDOF_MOTION'):return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

class WB_OT_capture_terrain(bpy.types.Operator):
    bl_idname='wb.capture_terrain_source';bl_label='Use selected mesh';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!='MESH' or obj==terrain_object():
            self.report({'ERROR'},'Select a separate terrain mesh; its original geometry will be preserved');return {'CANCELLED'}
        try:
            graph=json.loads(context.scene.wb_graph)
            if graph.get('version')!=3:raise ValueError('Load the connected terrain world first')
            evaluated=obj.evaluated_get(context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles();vertices=[list(obj.matrix_world@v.co) for v in mesh.vertices];triangles=[list(t.vertices) for t in mesh.loop_triangles]
                if not triangles:raise ValueError('Selected terrain has no faces')
                graph['terrain']['source_mesh']={'vertices':vertices,'triangles':triangles}
            finally:evaluated.to_mesh_clear()
            rebuild(context.scene,graph)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}

class WB_PT_terrain(bpy.types.Panel):
    bl_label='Terrain sculpting';bl_idname='WB_PT_terrain';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):
        from .native_extension import is_roadlab_scene
        return not is_roadlab_scene(context.scene)
    def draw(self,context):
        l=self.layout;s=context.scene.wb_terrain
        if not terrain_object():l.operator('wb.load_terrain_world');return
        box=l.box();box.label(text='Brush')
        box.prop(s,'mode',expand=True);box.prop(s,'radius');box.prop(s,'strength')
        if s.mode=='FLATTEN':
            box.prop(s,'sample_flatten')
            if not s.sample_flatten:box.prop(s,'flatten_height')
        box.operator('wb.sculpt_terrain',icon='BRUSH_DATA')
        box.label(text='Enter: apply   Esc: cancel')
        native=terrain_object().get('wb_terrain_backend')=='roadlab'
        box=l.box();box.label(text='Road contact')
        if native:box.prop(s,'contact_min');box.prop(s,'contact_max')
        else:box.prop(s,'blend')
        box=l.box();box.label(text='Terrain mesh')
        box.prop(s,'spacing');box.operator('wb.grade_terrain')
        box=l.box();box.label(text='Source')
        box.operator('wb.use_native_terrain_adapter',icon='FILE_FOLDER')
        box.operator('wb.capture_terrain_source')

classes=(WBTerrainSettings,WB_OT_use_native_terrain_adapter,WB_OT_load_terrain,WB_OT_grade_terrain,WB_OT_sculpt_terrain,WB_OT_capture_terrain,WB_PT_terrain)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.wb_terrain=PointerProperty(type=WBTerrainSettings)
def unregister():
    del bpy.types.Scene.wb_terrain
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
