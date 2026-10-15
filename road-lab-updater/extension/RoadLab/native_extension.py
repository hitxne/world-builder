"""Additive RoadLab integration. Native objects and node groups remain untouched."""
import bpy
from bpy.props import PointerProperty, StringProperty


def road_modifier(obj):
    return next((m for m in obj.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.split('.')[0] in ('ROAD','ROADLAB_ROAD_CORE')),None) if obj and obj.type=='CURVE' else None


def native_roads(scene):
    return [o for o in scene.objects if road_modifier(o)]


def native_terrain(scene):
    return next((o for o in scene.objects if o.type=='MESH' and any(m.type=='NODES' and m.node_group and m.node_group.name.split('.')[0]=='TERRAIN_SHAPE' for m in o.modifiers) and not o.get('wb_id')),None)


def is_roadlab_scene(scene):
    return bool(native_roads(scene))


def socket(group,name,direction,kind,default=None):
    result=next((s for s in group.interface.items_tree if s.name==name and getattr(s,'in_out',None)==direction),None)
    if result:return result
    result=group.interface.new_socket(name=name,in_out=direction,socket_type=kind)
    if default is not None:result.default_value=default
    return result



def set_input(mod,name,value):
    item=next(s for s in mod.node_group.interface.items_tree if getattr(s,'in_out',None)=='INPUT' and s.name==name)
    if item.identifier in mod and mod[item.identifier]==value and not (isinstance(value,bool) and not isinstance(mod[item.identifier],bool)):return
    mod[item.identifier]=value;mod.id_data.update_tag()


def cleanup_quality(self,context):
    for obj in context.scene.objects:
        if obj.get('wb_native_feature') not in ('curb','sidewalk','grass'):continue
        for mod in obj.modifiers:
            if mod.type=='NODES' and mod.node_group and mod.node_group.get('wb_schema',0)>=9:
                set_input(mod,'Precise viewport cleanup',self.precise_cleanup)


class WBNativeSettings(bpy.types.PropertyGroup):
    edit_preview:bpy.props.BoolProperty(name='Fast curve editing',description='Skip layer junction cleanup while editing the road or profile curve; clean junctions again in Object Mode',default=True)
    precise_cleanup:bpy.props.BoolProperty(name='Exact junction cleanup',description='Use precise layer Boolean cleanup in the viewport; slower on large networks. Rendering always uses precise cleanup',default=False,update=cleanup_quality)
    road:PointerProperty(name='Road curve',type=bpy.types.Object,poll=lambda self,obj:bool(road_modifier(obj)))
    terrain:PointerProperty(name='Terrain plane',type=bpy.types.Object,poll=lambda self,obj:obj.type=='MESH')


class WB_OT_bind_native(bpy.types.Operator):
    bl_idname='wb.bind_roadlab';bl_label='Connect scene';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        roads=native_roads(context.scene);terrain=native_terrain(context.scene)
        if not terrain and any(road.get('roadlab_new_core') for road in roads):terrain=context.scene.wb_native.terrain
        if not roads or not terrain:self.report({'ERROR'},'Open your road scene with its road curves and terrain plane');return {'CANCELLED'}
        settings=context.scene.wb_native;settings.road=context.active_object if context.active_object in roads else roads[0];settings.terrain=terrain
        from .native_layers import migrate_scene
        migrate_scene(context.scene)
        return {'FINISHED'}


class WB_OT_link_node_library(bpy.types.Operator):
    bl_idname='wb.link_roadlab_nodes';bl_label='Link node library';bl_options={'REGISTER','UNDO'}
    filepath:StringProperty(subtype='FILE_PATH')
    filter_glob:StringProperty(default='*.blend',options={'HIDDEN'})
    def invoke(self,context,event):
        context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        import os
        path=bpy.path.abspath(self.filepath)
        if not os.path.isfile(path):self.report({'ERROR'},'Choose your existing node-library .blend file');return {'CANCELLED'}
        try:
            with bpy.data.libraries.load(path,link=True) as (source,target):
                if not {'ROAD','TERRAIN_GEOMETRY','TERRAIN_SHAPE'}.issubset(source.node_groups):
                    self.report({'ERROR'},'This file needs ROAD, TERRAIN_GEOMETRY and TERRAIN_SHAPE node groups');return {'CANCELLED'}
            libraries={group.library for group in bpy.data.node_groups if group.library and group.name.split('.')[0] in ('ROAD','TERRAIN_GEOMETRY','TERRAIN_SHAPE')}
            if not libraries:self.report({'ERROR'},'Open the sample scene first');return {'CANCELLED'}
            for library in libraries:
                library.filepath=path;library.reload()
            for obj in context.scene.objects:
                for modifier in obj.modifiers:
                    if modifier.type!='NODES' or not modifier.node_group or modifier.node_group.library not in libraries:continue
                    for item in modifier.node_group.interface.items_tree:
                        if getattr(item,'in_out',None)=='INPUT' and getattr(item,'socket_type',None)=='NodeSocketBool':
                            set_input(modifier,item.name,bool(modifier.get(item.identifier,item.default_value)))
            bpy.ops.wb.bind_roadlab()
            context.view_layer.update()
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'Road and terrain nodes connected');return {'FINISHED'}


class WB_OT_add_road_branch(bpy.types.Operator):
    bl_idname='wb.add_road_branch';bl_label='Add branch';bl_description='Create a separate road spline at one selected control point; preserve the through road';bl_options={'REGISTER','UNDO'}
    length:bpy.props.FloatProperty(name='Branch length (m)',default=12.,min=.1)
    flip:bpy.props.BoolProperty(name='Opposite side',default=False)
    @classmethod
    def poll(cls,context):return context.mode=='EDIT_CURVE' and context.edit_object==context.scene.wb_native.road
    def invoke(self,context,event):return context.window_manager.invoke_props_dialog(self)
    def execute(self,context):
        from mathutils import Vector
        from . import native_layers as layers
        road=context.edit_object;road.update_from_editmode()
        indices=layers.selected(context,road)
        if len(indices)!=1:self.report({'ERROR'},'Select one road point for the branch');return {'CANCELLED'}
        index=indices[0];controls=layers.points(road);origin=Vector(controls[index].co[:3]);offset=0;tangent=None
        for spline in road.data.splines:
            points=list(spline.bezier_points if spline.type=='BEZIER' else spline.points)
            if offset<=index<offset+len(points):
                local=index-offset
                if len(points)>1:tangent=Vector(points[min(local+1,len(points)-1)].co[:3])-Vector(points[max(local-1,0)].co[:3])
                break
            offset+=len(points)
        if tangent is None or tangent.length<1e-6:self.report({'ERROR'},'This point needs a distinct neighboring point');return {'CANCELLED'}
        world_tangent=road.matrix_world.to_3x3()@tangent
        direction=Vector((-world_tangent.y,world_tangent.x,0))
        if direction.length<1e-6:self.report({'ERROR'},'The road needs a horizontal direction');return {'CANCELLED'}
        direction.normalize();delta=road.matrix_world.inverted().to_3x3()@(direction*self.length*(-1 if self.flip else 1))
        model=layers.model_for(road)
        inherited={a.name:layers.read(model,a.name)[index] for a in model.data.attributes if a.data_type=='FLOAT' and a.domain=='POINT'} if model else {}
        bpy.ops.object.mode_set(mode='OBJECT')
        branch=road.data.splines.new('POLY');branch.points.add(1)
        for point,co in zip(branch.points,(origin,origin+delta)):point.co=(*co,1)
        if model:
            layers.sync_model(model)
            for name,value in inherited.items():
                values=layers.read(model,name);values[-2:]=[value,value];layers.write(model,name,values)
            layers.refresh_stack(model)
        for point in layers.points(road):
            if hasattr(point,'select_control_point'):point.select_control_point=False;point.select_left_handle=False;point.select_right_handle=False
            else:point.select=False
        branch.points[-1].select=True;road.update_tag();bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class WB_OT_import_materials(bpy.types.Operator):
    bl_idname='wb.import_roadlab_materials';bl_label='Import materials';bl_description='Import existing materials from a Blender file, then assign them in RoadLab';bl_options={'REGISTER','UNDO'}
    filepath:StringProperty(subtype='FILE_PATH')
    filter_glob:StringProperty(default='*.blend',options={'HIDDEN'})
    def invoke(self,context,event):context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        import os
        path=bpy.path.abspath(self.filepath);images_before=set(bpy.data.images)
        if not os.path.isfile(path):self.report({'ERROR'},'Choose a Blender file containing your materials');return {'CANCELLED'}
        try:
            with bpy.data.libraries.load(path,link=False) as (source,target):
                target.materials=[name for name in source.materials if name not in bpy.data.materials]
            imported=[material for material in target.materials if material]
            for image in set(bpy.data.images)-images_before:
                if image.filepath.startswith('//'):
                    candidate=bpy.path.abspath(image.filepath,start=os.path.dirname(path))
                    if os.path.isfile(candidate):image.filepath=candidate
            self.report({'INFO'},f'Imported {len(imported)} materials; choose them in RoadLab')
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return {'FINISHED'}


class WB_OT_find_textures(bpy.types.Operator):
    bl_idname='wb.find_roadlab_textures';bl_label='Locate textures';bl_description='Find missing image files inside your chosen texture folder';bl_options={'REGISTER','UNDO'}
    directory:StringProperty(subtype='DIR_PATH')
    def invoke(self,context,event):context.window_manager.fileselect_add(self);return {'RUNNING_MODAL'}
    def execute(self,context):
        import os
        directory=bpy.path.abspath(self.directory)
        if not os.path.isdir(directory):self.report({'ERROR'},'Choose the folder containing your textures');return {'CANCELLED'}
        return bpy.ops.file.find_missing_files(directory=directory)


class WB_OT_native_curbs(bpy.types.Operator):
    bl_idname='wb.add_native_curbs';bl_label='Add edge layer';bl_options={'REGISTER','UNDO'}
    kind:bpy.props.EnumProperty(items=[('curb','Curb','Editable curb profile'),('sidewalk','Sidewalk','Editable sidewalk profile'),('grass','Grass strip','Editable grass profile')],default='curb')
    def execute(self,context):
        road=context.scene.wb_native.road
        if not road_modifier(road):self.report({'ERROR'},'Select an existing RoadLab road curve');return {'CANCELLED'}
        from .native_extrusion import add_extrusion
        obj,profile=add_extrusion(context.scene,road,self.kind)
        if context.mode=='OBJECT':context.view_layer.objects.active=obj;obj.select_set(True)
        return {'FINISHED'}



class WB_OT_edit_native_profile(bpy.types.Operator):
    bl_idname='wb.edit_native_profile';bl_label='Edit cross-section';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        mod=active_layer_modifier(context)
        if not mod:return {'CANCELLED'}
        item=next(s for s in mod.node_group.interface.items_tree if s.name=='Profile curve' and getattr(s,'in_out',None)=='INPUT');profile=mod.get(item.identifier)
        if not profile or profile.type!='CURVE':self.report({'ERROR'},'Choose a curve profile first');return {'CANCELLED'}
        if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        for selected in context.selected_objects:selected.select_set(False)
        profile.hide_set(False);profile.select_set(True);context.view_layer.objects.active=profile
        if context.area and context.area.type=='VIEW_3D':
            region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
            if region:
                with context.temp_override(region=region):bpy.ops.view3d.view_selected(use_all_regions=False)
        bpy.ops.object.mode_set(mode='EDIT');return {'FINISHED'}


def draw_input(layout,modifier,name,label):
    item=next((p for p in modifier.node_group.interface.items_tree if p.name==name and getattr(p,'in_out',None)=='INPUT'),None)
    layout.use_property_split=True;layout.use_property_decorate=False
    if item:layout.prop(modifier,'["'+item.identifier+'"]',text=label)


def active_layer_modifier(context):
    from .native_layers import model_for
    road=context.scene.wb_native.road
    model=model_for(road) if road else None
    if model and model.wb_layers:
        index=max(0,min(model.wb_layer_index,len(model.wb_layers)-1))
        obj=model.wb_layers[index].object
    else:obj=context.active_object
    if not obj or obj.get('wb_native_feature') not in ('curb','sidewalk','grass'):return None
    return next((m for m in obj.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION')),None)


class WB_OT_edit_road_curve(bpy.types.Operator):
    bl_idname='wb.edit_road_curve';bl_label='Edit road curve';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return bool(road_modifier(context.scene.wb_native.road))
    def execute(self,context):
        road=context.scene.wb_native.road
        if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        for obj in context.selected_objects:obj.select_set(False)
        road.hide_set(False);road.select_set(True);context.view_layer.objects.active=road
        bpy.ops.object.mode_set(mode='EDIT');return {'FINISHED'}


class WB_PT_core_status(bpy.types.Panel):
    bl_label='Road status';bl_idname='WB_PT_core_status';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_order=-20;bl_options={'HIDE_HEADER'}
    @classmethod
    def poll(cls,context):
        road=context.scene.wb_native.road;terrain=context.scene.wb_native.terrain
        import json
        from .road_core import is_pending
        if is_pending(context.scene):return True
        limited=road and any(x['applied']<x['requested']-1e-5 for x in json.loads(road.get('roadlab_core_report','{}')).get('radius_limits',[]))
        return bool(limited or (road and road.get('roadlab_core_error')) or (terrain and terrain.get('roadlab_core_terrain_error')))
    def draw(self,context):
        road=context.scene.wb_native.road;terrain=context.scene.wb_native.terrain
        from .road_core import is_pending
        if is_pending(context.scene):self.layout.label(text='Place the road to update the mesh',icon='TIME')
        for obj,field in [(road,'roadlab_core_error'),(terrain,'roadlab_core_terrain_error')]:
            if obj and obj.get(field):
                box=self.layout.box();box.label(text='Edit cannot be built; previous surface shown',icon='ERROR')
                import textwrap
                for line in textwrap.wrap(obj[field],width=42):box.label(text=line)
        if road:
            import json
            limited=[x for x in json.loads(road.get('roadlab_core_report','{}')).get('radius_limits',[]) if x.get('mode')=='merged' or x['applied']<x['requested']-1e-5]
            if limited:
                box=self.layout.box();box.label(text='Corner radius constrained by available space',icon='INFO')
                for x in limited:
                    if x.get('mode')=='merged':box.label(text=f"{x['corner']}: hidden by merge; stored {x['requested']:.2f} m")
                    else:box.label(text=f"{x['corner']}: requested {x['requested']:.2f}, applied {x['applied']:.2f} m")


class ROADLAB_OT_load_example(bpy.types.Operator):
    bl_idname='roadlab.load_example';bl_label='Load example';bl_options={'REGISTER','UNDO'}
    bl_description='Open an editable road curve and connected terrain plane in a separate scene'
    def execute(self,context):
        from .examples import load_editable_example
        load_editable_example(context)
        self.report({'INFO'},'Editable road curve selected. Tab to edit; G to move; terrain follows. Your previous scene is preserved.')
        return {'FINISHED'}


class ROADLAB_OT_new_road(bpy.types.Operator):
    bl_idname='roadlab.new_road';bl_label='Create Road';bl_options={'REGISTER','UNDO'}
    bl_description='Create an editable road at the 3D cursor and connect it to the assigned terrain'
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT'
    def execute(self,context):
        from . import road_core,core_terrain
        from mathutils import Vector
        center=context.scene.cursor.location
        data=bpy.data.curves.new('RoadLab Alignment','CURVE');data.dimensions='3D'
        spline=data.splines.new('POLY');spline.points.add(1)
        for point,x in zip(spline.points,(-15.,15.)):point.co=(x,0.,0.,1.)
        obj=bpy.data.objects.new('RoadLab Road',data);context.collection.objects.link(obj);obj.location=center+Vector((0,0,.02))
        context.view_layer.update()
        context.scene.wb_native.road=obj;road_core.attach(obj)
        if context.scene.wb_native.terrain:core_terrain.rebuild(context.scene,True)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);context.view_layer.objects.active=obj
        self.report({'INFO'},'Road created. Tab to edit; E to extend; G then Z to change elevation.')
        return {'FINISHED'}


class WB_PT_native(bpy.types.Panel):
    bl_label='Scene';bl_idname='WB_PT_native';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_order=-10;bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout;s=context.scene.wb_native
        layout.operator('roadlab.load_example',icon='FILE_NEW')
        layout.operator('roadlab.new_road',icon='CURVE_PATH')
        layout.operator('wb.bind_roadlab',icon='LINKED')
        if context.scene.get('roadlab_sample'):layout.operator('wb.link_roadlab_nodes',icon='FILE_FOLDER')
        layout.prop(s,'road');layout.prop(s,'terrain')
        if context.mode=='OBJECT' and context.active_object and context.active_object.type=='MESH':layout.operator('roadlab.use_selected_terrain',icon='MESH_PLANE')
        if s.road and s.road.get('roadlab_new_core'):
            layout.label(text='Road core: editable XYZ network',icon='INFO')
            error=s.road.get('roadlab_core_error')
            if error:layout.label(text='Last valid mesh retained',icon='ERROR');layout.label(text=error)
        mod=road_modifier(s.road)
        if mod and getattr(mod.node_group,'is_missing',False):layout.label(text='Link the node library to load the road',icon='INFO')


class NativeSection:
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return bool(road_modifier(context.scene.wb_native.road))


class WB_PT_road_shape(NativeSection,bpy.types.Panel):
    bl_label='Road defaults';bl_idname='WB_PT_road_shape';bl_order=0
    def draw(self,context):
        layout=self.layout;mod=road_modifier(context.scene.wb_native.road)
        for name,label in [('road width','Road width (m)'),('resolution','Sample spacing (m)'),('crossfall','Crown rise (m)')]:
            draw_input(layout,mod,name,label)
        layout.operator('wb.edit_road_curve',icon='EDITMODE_HLT')
        if context.mode=='EDIT_CURVE' and context.edit_object==context.scene.wb_native.road:
            layout.operator('wb.add_road_branch',icon='CURVE_PATH')


class WB_PT_road_junctions(NativeSection,bpy.types.Panel):
    bl_label='Corner defaults';bl_idname='WB_PT_road_junctions';bl_order=1
    def draw(self,context):
        mod=road_modifier(context.scene.wb_native.road)
        if mod.node_group.name.split('.')[0]=='ROADLAB_ROAD_CORE':
            self.layout.label(text='Default corner radii for this network')
            for pair in [('NW','NE'),('SW','SE')]:
                row=self.layout.row(align=True)
                for corner in pair:
                    import json
                    col=row.column();col.enabled=corner in json.loads(context.scene.wb_native.road.get('roadlab_core_report','{}')).get('active_corners',[])
                    draw_input(col,mod,'corner '+corner,corner+' radius (m)')
        else:draw_input(self.layout,mod,'smooth intersections','Junction smoothing (m)')


class WB_PT_junction_limits(NativeSection,bpy.types.Panel):
    bl_label='Radius limits';bl_idname='WB_PT_junction_limits';bl_parent_id='WB_PT_road_junctions'
    @classmethod
    def poll(cls,context):
        road=context.scene.wb_native.road
        return road is not None and bool(road.get('roadlab_new_core'))
    def draw(self,context):
        import json
        report=json.loads(context.scene.wb_native.road.get('roadlab_core_report','{}'))
        limits=report.get('radius_limits',[])
        if not limits:self.layout.label(text='No junction corners in this network')
        for item in limits:
            if item.get('mode')=='merged':
                self.layout.label(text=f"{item['corner']}: internal corner merged")
                continue
            self.layout.label(text=f"{item['corner']}: {item['minimum']:.2f}–{item['maximum']:.2f} m")
            if item['applied']<item['requested']-1e-5:
                self.layout.label(text=f"Applied {item['applied']:.2f}; requested {item['requested']:.2f} m",icon='INFO')


class WB_PT_road_elevation(NativeSection,bpy.types.Panel):
    bl_label='Road elevation';bl_idname='WB_PT_road_elevation';bl_order=2
    def draw(self,context):
        layout=self.layout;mod=road_modifier(context.scene.wb_native.road)
        road=context.scene.wb_native.road
        if road.get('roadlab_new_core'):
            layout.label(text='Edit curve points with G, then Z')
            layout.prop(road,'roadlab_core_ground_contact')
        for name,label in [('Z offset','Height offset (m)'),('Shrinkwrap','Follow terrain'),('reference terrain','Terrain reference'),('bridge treshold','Bridge height threshold (m)'),('tunnel treshold','Tunnel depth threshold (m)')]:draw_input(layout,mod,name,label)


class WB_PT_road_curve_detail(NativeSection,bpy.types.Panel):
    bl_label='Curve processing';bl_idname='WB_PT_road_curve_detail';bl_order=6
    def draw(self,context):
        layout=self.layout;mod=road_modifier(context.scene.wb_native.road)
        for name,label in [('subdivide input','Input subdivisions'),('offset','Alignment offset (m)'),('Z-smooth curve','Height smoothing passes'),('smooth radius','Point-width smoothing passes')]:draw_input(layout,mod,name,label)


class WB_PT_road_appearance(NativeSection,bpy.types.Panel):
    bl_label='Materials';bl_idname='WB_PT_road_appearance';bl_order=7
    def draw(self,context):
        layout=self.layout;mod=road_modifier(context.scene.wb_native.road)
        draw_input(layout,mod,'material','Asphalt material')
        terrain=context.scene.wb_native.terrain
        if terrain:layout.prop(terrain,'active_material',text='Terrain material')
        layer=active_layer_modifier(context)
        if layer:draw_input(layout,layer,'Material','Selected layer material')
        row=layout.row(align=True);row.operator('wb.import_roadlab_materials',icon='APPEND_BLEND');row.operator('wb.find_roadlab_textures',icon='FILE_FOLDER')


class WB_PT_road_uv(NativeSection,bpy.types.Panel):
    bl_label='Texture mapping';bl_idname='WB_PT_road_uv';bl_parent_id='WB_PT_road_appearance'
    def draw(self,context):
        mod=road_modifier(context.scene.wb_native.road)
        for name,label in [('UVs','Generate UVs'),('stretch UVs','Stretch along road'),('scale UVs','Texture scale'),('offset UVs','Texture offset'),('rotate UVs','Texture rotation')]:draw_input(self.layout,mod,name,label)


class WB_PT_layer_stack(NativeSection,bpy.types.Panel):
    bl_label='Edge layers';bl_idname='WB_PT_layer_stack';bl_order=3
    def draw(self,context):
        layout=self.layout
        from .native_layers import model_for
        model=model_for(context.scene.wb_native.road)
        if model:
            layout.label(text='Order: road edge outward')
            row=layout.row();row.template_list('WB_UL_layers','',model,'wb_layers',model,'wb_layer_index',rows=4)
            col=row.column(align=True)
            col.operator('wb.move_native_layer',text='',icon='TRIA_UP').direction=-1
            col.operator('wb.move_native_layer',text='',icon='TRIA_DOWN').direction=1
            col.operator('wb.remove_native_layer',text='',icon='TRASH')
        row=layout.row(align=True)
        for kind,label in [('curb','Curb'),('grass','Grass'),('sidewalk','Sidewalk')]:
            row.operator('wb.add_native_curbs',text=label,icon='ADD').kind=kind


class WB_PT_native_terrain(NativeSection,bpy.types.Panel):
    bl_label='Terrain contact';bl_idname='WB_PT_native_terrain';bl_order=4
    @classmethod
    def poll(cls,context):return context.scene.wb_native.terrain is not None
    def draw(self,context):
        layout=self.layout
        terrain=context.scene.wb_native.terrain
        road=context.scene.wb_native.road
        if terrain.roadlab_core_terrain_enabled or (road and road.get('roadlab_new_core')):
            layout.prop(terrain,'roadlab_core_terrain_enabled')
            layout.prop(terrain,'roadlab_core_blend')
            layout.prop(terrain,'roadlab_core_terrain_spacing')
            layout.prop(terrain,'roadlab_core_terrain_tolerance')
            if terrain.get('roadlab_terrain_field'):layout.operator('roadlab.reset_terrain_sculpt',icon='LOOP_BACK')
            error=terrain.get('roadlab_core_terrain_error')
            if error:layout.label(text=error,icon='ERROR')
        for mod in context.scene.wb_native.terrain.modifiers:
            if mod.type!='NODES' or not mod.node_group:continue
            base=mod.node_group.name.split('.')[0]
            if base=='TERRAIN_SHAPE':
                box=layout.box();box.label(text='Road blending')
                for name,label in [('flatten min','Full-contact distance (m)'),('flatten max','Blend end distance (m)'),('Z offset','Terrain height offset (m)')]:draw_input(box,mod,name,label)
                box=layout.box();box.label(text='Road cutouts')
                for name,label in [('cut terrain','Cut beneath roads'),('extrude cutter','Extrude cutout tool')]:draw_input(box,mod,name,label)
            elif base=='TERRAIN_GEOMETRY':
                box=layout.box();box.label(text='Mesh refinement')
                for name,label in [('number of ranges','Refinement bands')]+[(f'range {i}',f'Band {i} radius (m)') for i in range(1,7)]:draw_input(box,mod,name,label)


class WB_PT_layer_profile(NativeSection,bpy.types.Panel):
    bl_label='Selected layer: cross-section';bl_idname='WB_PT_layer_profile';bl_parent_id='WB_PT_layer_stack';bl_order=3;bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return active_layer_modifier(context) is not None
    def draw(self,context):
        layout=self.layout;m=active_layer_modifier(context)
        from .native_layers import model_for
        model=model_for(context.scene.wb_native.road)
        name=next((layer.name for layer in model.wb_layers if layer.object==m.id_data),m.id_data.name) if model else m.id_data.name
        layout.label(text='Layer: '+name)
        draw_input(layout,m,'Material','Layer material')
        box=layout.box();box.label(text='Cross-section')
        for name,label in [('Profile curve','Cross-section curve'),('Profile width scale','Width multiplier'),('Profile height scale','Height multiplier'),('Setback','Extra outward offset (m)'),('Height offset','Extra height offset (m)')]:draw_input(box,m,name,label)
        box.operator('wb.edit_native_profile',icon='EDITMODE_HLT')
        box=layout.box();box.label(text='Path override')
        draw_input(box,m,'Use custom path','Use custom path');draw_input(box,m,'Path curve','Path curve')


class WB_PT_layer_crossing(NativeSection,bpy.types.Panel):
    bl_label='Selected layer: crossing ramp';bl_idname='WB_PT_layer_crossing';bl_parent_id='WB_PT_layer_stack';bl_order=4;bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return active_layer_modifier(context) is not None
    def draw(self,context):
        layout=self.layout;m=active_layer_modifier(context)
        from .native_layers import model_for
        model=model_for(context.scene.wb_native.road)
        name=next((layer.name for layer in model.wb_layers if layer.object==m.id_data),m.id_data.name) if model else m.id_data.name
        layout.label(text='Layer: '+name)
        for name,label in [('Crossing road','Crossing road'),('Lower at crossing','Lower to crossing road'),('Transition length','Ramp transition (m)')]:draw_input(layout,m,name,label)


class WB_PT_viewport(NativeSection,bpy.types.Panel):
    bl_label='Viewport quality';bl_idname='WB_PT_viewport';bl_order=8;bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout;s=context.scene.wb_native
        road=s.road
        if road and road.get('roadlab_new_core'):
            from .road_core import last_edit_ms
            layout.prop(context.scene,'roadlab_core_update_mode')
            layout.label(text=f'Last rebuild: {last_edit_ms(context.scene):.1f} ms')
        layout.prop(s,'edit_preview');layout.prop(s,'precise_cleanup')


classes=(WBNativeSettings,ROADLAB_OT_load_example,ROADLAB_OT_new_road,WB_OT_edit_road_curve,WB_OT_bind_native,WB_OT_link_node_library,WB_OT_add_road_branch,WB_OT_import_materials,WB_OT_find_textures,WB_OT_native_curbs,WB_OT_edit_native_profile,WB_PT_core_status,WB_PT_native,WB_PT_road_shape,WB_PT_road_junctions,WB_PT_junction_limits,WB_PT_road_elevation,WB_PT_road_curve_detail,WB_PT_road_appearance,WB_PT_road_uv,WB_PT_layer_stack,WB_PT_native_terrain,WB_PT_layer_profile,WB_PT_layer_crossing,WB_PT_viewport)

def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.wb_native=PointerProperty(type=WBNativeSettings)
    from .native_layers import register_panels
    register_panels()
def unregister():
    from .native_layers import unregister_panels
    unregister_panels()
    del bpy.types.Scene.wb_native
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
