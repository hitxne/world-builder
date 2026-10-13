"""Additive TrackTools integration. Native objects and node groups remain untouched."""
import bpy
from bpy.props import PointerProperty


def road_modifier(obj):
    return next((m for m in obj.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.split('.')[0]=='ROAD'),None) if obj and obj.type=='CURVE' else None


def native_roads(scene):
    return [o for o in scene.objects if road_modifier(o)]


def native_terrain(scene):
    return next((o for o in scene.objects if o.type=='MESH' and any(m.type=='NODES' and m.node_group and m.node_group.name.split('.')[0]=='TERRAIN_SHAPE' for m in o.modifiers) and not o.get('wb_id')),None)


def is_tracktools_scene(scene):
    return bool(native_roads(scene))


def socket(group,name,direction,kind,default=None):
    result=next((s for s in group.interface.items_tree if s.name==name and getattr(s,'in_out',None)==direction),None)
    if result:return result
    result=group.interface.new_socket(name=name,in_out=direction,socket_type=kind)
    if default is not None:result.default_value=default
    return result



def set_input(mod,name,value):
    item=next(s for s in mod.node_group.interface.items_tree if getattr(s,'in_out',None)=='INPUT' and s.name==name)
    if item.identifier in mod and mod[item.identifier]==value:return
    mod[item.identifier]=value;mod.id_data.update_tag()


def cleanup_quality(self,context):
    for obj in context.scene.objects:
        if obj.get('wb_native_feature') not in ('curb','sidewalk','grass'):continue
        for mod in obj.modifiers:
            if mod.type=='NODES' and mod.node_group and mod.node_group.get('wb_schema',0)>=9:
                set_input(mod,'Precise viewport cleanup',self.precise_cleanup)


class WBNativeSettings(bpy.types.PropertyGroup):
    precise_cleanup:bpy.props.BoolProperty(name='Precise viewport cleanup',default=False,update=cleanup_quality)
    road:PointerProperty(name='TrackTools road curve',type=bpy.types.Object,poll=lambda self,obj:bool(road_modifier(obj)))
    terrain:PointerProperty(name='TrackTools terrain plane',type=bpy.types.Object,poll=lambda self,obj:obj.type=='MESH')


class WB_OT_bind_native(bpy.types.Operator):
    bl_idname='wb.bind_tracktools';bl_label='Use existing TrackTools scene';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        roads=native_roads(context.scene);terrain=native_terrain(context.scene)
        if not roads or not terrain:self.report({'ERROR'},'Open your original TrackTools scene with its road curves and terrain plane');return {'CANCELLED'}
        settings=context.scene.wb_native;settings.road=context.active_object if context.active_object in roads else roads[0];settings.terrain=terrain
        from .native_layers import migrate_scene
        migrate_scene(context.scene)
        return {'FINISHED'}


class WB_OT_native_curbs(bpy.types.Operator):
    bl_idname='wb.add_native_curbs';bl_label='Add optional extrusion';bl_options={'REGISTER','UNDO'}
    kind:bpy.props.EnumProperty(items=[('curb','Curb','Editable curb profile'),('sidewalk','Sidewalk','Editable sidewalk profile'),('grass','Grass strip','Editable grass profile')],default='curb')
    def execute(self,context):
        road=context.scene.wb_native.road
        if not road_modifier(road):self.report({'ERROR'},'Select an existing TrackTools road curve');return {'CANCELLED'}
        from .native_extrusion import add_extrusion
        obj,profile=add_extrusion(context.scene,road,self.kind)
        if context.mode=='OBJECT':context.view_layer.objects.active=obj;obj.select_set(True)
        return {'FINISHED'}



class WB_OT_edit_native_profile(bpy.types.Operator):
    bl_idname='wb.edit_native_profile';bl_label='Edit extrusion profile vertices';bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.get('wb_native_feature') not in ('curb','sidewalk','grass'):return {'CANCELLED'}
        mod=obj.modifiers[0];item=next(s for s in mod.node_group.interface.items_tree if s.name=='Profile curve' and getattr(s,'in_out',None)=='INPUT');profile=mod.get(item.identifier)
        if not profile or profile.type!='CURVE':self.report({'ERROR'},'Choose a curve profile first');return {'CANCELLED'}
        if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        for selected in context.selected_objects:selected.select_set(False)
        profile.hide_set(False);profile.select_set(True);context.view_layer.objects.active=profile
        if context.area and context.area.type=='VIEW_3D':
            region=next((r for r in context.area.regions if r.type=='WINDOW'),None)
            if region:
                with context.temp_override(region=region):bpy.ops.view3d.view_selected(use_all_regions=False)
        bpy.ops.object.mode_set(mode='EDIT');return {'FINISHED'}


class WB_PT_native(bpy.types.Panel):
    bl_label='TrackTools + WB';bl_idname='WB_PT_native';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='WB Roads';bl_order=-10
    def draw(self,context):
        layout=self.layout;s=context.scene.wb_native
        layout.operator('wb.bind_tracktools',icon='LINKED');layout.prop(s,'road');layout.prop(s,'terrain')
        road=s.road;mod=road_modifier(road)
        if mod:
            layout.label(text='Edit the original road curve in Edit Mode')
            layout.prop(s,'precise_cleanup',text='Precise viewport cleanup (slower)')
            layout.label(text='Renders use precise cleanup automatically')
            for name in ('road width','resolution','crossfall','Shrinkwrap'):
                item=next((p for p in mod.node_group.interface.items_tree if p.name==name and getattr(p,'in_out',None)=='INPUT'),None)
                if item:layout.prop(mod,'["'+item.identifier+'"]',text=name)
            from .native_layers import model_for
            model=model_for(road)
            if model:
                layout.label(text='Layers: road edge outward')
                row=layout.row();row.template_list('WB_UL_layers','',model,'wb_layers',model,'wb_layer_index',rows=5)
                col=row.column(align=True)
                col.operator('wb.move_native_layer',text='',icon='TRIA_UP').direction=-1
                col.operator('wb.move_native_layer',text='',icon='TRIA_DOWN').direction=1
            for kind,label in [('curb','Add curb layer'),('sidewalk','Add sidewalk layer'),('grass','Add grass patch layer')]:
                layout.operator('wb.add_native_curbs',text=label).kind=kind
        if s.terrain:
            for terrain_modifier in s.terrain.modifiers:
                if terrain_modifier.type!='NODES' or not terrain_modifier.node_group:continue
                base=terrain_modifier.node_group.name.split('.')[0]
                names=('flatten min','flatten max') if base=='TERRAIN_SHAPE' else ('number of ranges','range 1') if base=='TERRAIN_GEOMETRY' else ()
                for name in names:
                    item=next((p for p in terrain_modifier.node_group.interface.items_tree if p.name==name and getattr(p,'in_out',None)=='INPUT'),None)
                    if item:layout.prop(terrain_modifier,'["'+item.identifier+'"]',text='Terrain '+name)
        active=context.active_object
        if active and active.get('wb_native_feature') in ('curb','sidewalk','grass'):
            m=active.modifiers[0]
            for name in ('Enabled','Profile curve','Path curve','Use custom path','Profile width scale','Profile height scale','Setback','Height offset','Crossing road','Lower at crossing','Transition length'):
                item=next(p for p in m.node_group.interface.items_tree if p.name==name and getattr(p,'in_out',None)=='INPUT');layout.prop(m,'["'+item.identifier+'"]',text=name)
            layout.label(text='Edit profile curve vertices for cross section')
            layout.operator('wb.edit_native_profile')
            layout.label(text='Enabled toggles the extrusion')
        layout.label(text='Native plane, curves and nodes stay in place')


classes=(WBNativeSettings,WB_OT_bind_native,WB_OT_native_curbs,WB_OT_edit_native_profile,WB_PT_native)
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
