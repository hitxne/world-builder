"""Repeatable native extrusion layers and per-control-vertex settings.
All data lives on WB helper objects; original upstream curve data is only read/shared.
"""
import bpy,uuid
from mathutils import Vector
from bpy.props import StringProperty,EnumProperty,BoolProperty,FloatProperty,PointerProperty,CollectionProperty,IntProperty
from .native_extension import set_input
KINDS={'curb':('Curb',.32),'sidewalk':('Sidewalk',2.2),'grass':('Grass Patch',1.2)}
_suspended=False


def points(road):
    return [p for s in road.data.splines for p in (s.bezier_points if s.type=='BEZIER' else s.points)]


def selected(context,road):
    if context.mode!='EDIT_CURVE' or context.edit_object!=road:return []
    road.update_from_editmode()
    return [i for i,p in enumerate(points(road)) if getattr(p,'select_control_point',getattr(p,'select',False))]


def prefix(layer):return 'wb_'+layer.uid+'_'


def model_for(road):
    return next((o for o in bpy.data.objects if o.get('wb_layer_model') and o.get('wb_road')==road),None)


def read(model,key):return [v.value for v in model.data.attributes[key].data]


def write(model,key,values):
    attr=model.data.attributes.get(key) or model.data.attributes.new(key,'FLOAT','POINT')
    for a,v in zip(attr.data,values):a.value=v


def default(layer,field):
    return {'enabled':1.,'width':KINDS[layer.kind][1],'offset':0.,'zpos':0.,'stack':0.}[field]


def ensure_model(scene,road):
    model=model_for(road)
    if model:return model
    c=next((c for c in scene.collection.children if c.name.split('.')[0]=='WB_VERTEX_CONTROLS'),None)
    if c is None:c=bpy.data.collections.new('WB_VERTEX_CONTROLS');scene.collection.children.link(c)
    mesh=bpy.data.meshes.new('WB_Vertex_Settings_'+road.name);mesh.from_pydata([tuple(p.co[:3]) for p in points(road)],[],[]);mesh.update()
    model=bpy.data.objects.new('WB_Vertex_Settings_'+road.name,mesh);c.objects.link(model);model.hide_render=True;model.hide_set(True);model['wb_layer_model']=True;model['wb_road']=road
    helper=bpy.data.objects.new('WB_Control_Curve_'+road.name,road.data);c.objects.link(helper);helper.hide_render=True;helper.hide_set(True);helper['wb_mask_helper']=True;helper['wb_road']=road;model['wb_helper']=helper
    constraint=helper.constraints.new('COPY_TRANSFORMS');constraint.target=road
    return model


def rebuild_helper(model):
    helper=model['wb_helper'];road=model['wb_road']
    if helper.data!=road.data:helper.data=road.data
    mod=next((m for m in helper.modifiers if m.type=='NODES'),None)
    group=mod.node_group if mod else bpy.data.node_groups.new('WB_Vertex_Fields_'+road.name,'GeometryNodeTree')
    if not mod:mod=helper.modifiers.new('WB live vertex fields','NODES');mod.node_group=group
    group.nodes.clear()
    from .native_extension import socket
    socket(group,'Geometry','INPUT','NodeSocketGeometry');socket(group,'Geometry','OUTPUT','NodeSocketGeometry')
    N=group.nodes;L=group.links;inp=N.new('NodeGroupInput');out=N.new('NodeGroupOutput');info=N.new('GeometryNodeObjectInfo');info.transform_space='ORIGINAL';info.inputs['Object'].default_value=model
    index=N.new('GeometryNodeInputIndex');geometry=inp.outputs['Geometry'];x=250
    for layer in model.wb_layers:
        for field in ('enabled','width','offset','zpos','stack'):
            attr=N.new('GeometryNodeInputNamedAttribute');attr.data_type='FLOAT';attr.inputs['Name'].default_value=prefix(layer)+field
            sample=N.new('GeometryNodeSampleIndex');sample.data_type='FLOAT';sample.domain='POINT';L.new(info.outputs['Geometry'],sample.inputs['Geometry']);L.new(attr.outputs['Attribute'],sample.inputs['Value']);L.new(index.outputs['Index'],sample.inputs['Index'])
            store=N.new('GeometryNodeStoreNamedAttribute');store.data_type='FLOAT';store.domain='POINT';store.inputs['Name'].default_value=prefix(layer)+field;L.new(geometry,store.inputs['Geometry']);L.new(sample.outputs['Value'],store.inputs['Value']);geometry=store.outputs['Geometry']
            store.location=(x,0);sample.location=(x,-250);attr.location=(x,-550);x+=220
    resample=N.new('GeometryNodeResampleCurve');resample.inputs['Mode'].default_value='Length';resample.inputs['Length'].default_value=.1;L.new(geometry,resample.inputs['Curve'])
    cloud=N.new('GeometryNodeCurveToPoints');cloud.mode='EVALUATED';L.new(resample.outputs['Curve'],cloud.inputs['Curve']);L.new(cloud.outputs['Points'],out.inputs['Geometry']);helper.update_tag()


def refresh_stack(model):
    offset=[0.]*len(model.data.vertices)
    for layer in model.wb_layers:
        base=prefix(layer);gaps=read(model,base+'offset');widths=read(model,base+'width');enabled=read(model,base+'enabled')
        write(model,base+'stack',offset)
        if layer.enabled:
            offset=[o+(w+gap)*e for o,w,gap,e in zip(offset,widths,gaps,enabled)]
        obj=layer.object
        if obj:
            for mod in obj.modifiers:
                if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                    set_input(mod,'Enabled',layer.enabled);set_input(mod,'Vertex controls',model['wb_helper']);set_input(mod,'Layer prefix',base);set_input(mod,'Use vertex controls',True);set_input(mod,'Use layer order',True)
    model.data.update();model.update_tag()


def add_layer(scene,road,obj,kind):
    model=ensure_model(scene,road)
    existing=next((l for l in model.wb_layers if l.object==obj),None)
    if existing:return existing
    global _suspended
    _suspended=True
    layer=model.wb_layers.add();layer.uid=uuid.uuid4().hex[:12];layer.kind=kind;layer.name=KINDS[kind][0]+' '+str(sum(l.kind==kind for l in model.wb_layers));layer.object=obj;layer.width=KINDS[kind][1]
    _suspended=False
    for field in ('enabled','width','offset','zpos','stack'):write(model,prefix(layer)+field,[default(layer,field)]*len(model.data.vertices))
    model.wb_layer_index=len(model.wb_layers)-1;rebuild_helper(model);refresh_stack(model);return layer


def apply(layer,field,value,context):
    if _suspended:return
    model=layer.id_data;road=model.get('wb_road')
    if not road:return
    indices=selected(context,road)
    if context.mode.startswith('EDIT') and not indices:return
    if not indices:indices=list(range(len(model.data.vertices)))
    values=read(model,prefix(layer)+field)
    for i in indices:
        if i<len(values):values[i]=float(value)
    write(model,prefix(layer)+field,values);refresh_stack(model)


def layer_enabled(self,context):
    if not _suspended and self.uid:refresh_stack(self.id_data)


class WBLayer(bpy.types.PropertyGroup):
    expanded:BoolProperty(name='Show settings',default=False)
    uid:StringProperty();kind:EnumProperty(items=[(k,v[0],v[0]) for k,v in KINDS.items()]);name:StringProperty()
    object:PointerProperty(type=bpy.types.Object)
    enabled:BoolProperty(name='Enabled',default=True,update=layer_enabled)
    vertex_enabled:BoolProperty(name='Include at points',description='Include this layer at selected curve points in Edit Mode, or all points in Object Mode',default=True,update=lambda s,c:apply(s,'enabled',s.vertex_enabled,c))
    width:FloatProperty(name='Width (m)',default=.32,min=.001,update=lambda s,c:apply(s,'width',s.width,c))
    offset:FloatProperty(name='Gap before layer (m)',description='Distance between the preceding layer and this layer; negative values overlap them',default=0,update=lambda s,c:apply(s,'offset',s.offset,c))
    zpos:FloatProperty(name='Height offset (m)',description='Vertical offset from the road edge; added to the profile height',default=0,update=lambda s,c:apply(s,'zpos',s.zpos,c))


class WB_UL_layers(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        layout.prop(item,'enabled',text='');layout.prop(item,'name',text='',emboss=False)


class WB_OT_layer_move(bpy.types.Operator):
    bl_idname='wb.move_native_layer';bl_label='Move extrusion layer';bl_options={'REGISTER','UNDO'}
    direction:IntProperty(default=1)
    def execute(self,context):
        model=model_for(context.scene.wb_native.road)
        if not model:return {'CANCELLED'}
        i=model.wb_layer_index;j=i+self.direction
        if 0<=j<len(model.wb_layers):model.wb_layers.move(i,j);model.wb_layer_index=j;refresh_stack(model)
        return {'FINISHED'}


class WB_OT_layer_remove(bpy.types.Operator):
    bl_idname='wb.remove_native_layer';bl_label='Remove layer';bl_description='Delete this layer and close its space in the edge-layer stack';bl_options={'REGISTER','UNDO'}
    uid:StringProperty()
    @classmethod
    def poll(cls,context):
        road=context.scene.wb_native.road
        model=model_for(road) if road else None
        return bool(model and model.wb_layers) and context.mode in ('OBJECT','EDIT_CURVE')
    def execute(self,context):
        model=model_for(context.scene.wb_native.road)
        index=next((i for i,l in enumerate(model.wb_layers) if l.uid==self.uid),-1) if self.uid else model.wb_layer_index
        if index<0 or index>=len(model.wb_layers):return {'CANCELLED'}
        layer=model.wb_layers[index];key=prefix(layer);obj=layer.object;profile=None;mesh=None;base=None
        if obj:
            from .native_contacts import input_value
            for mod in obj.modifiers:
                if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                    profile=input_value(mod,'Profile curve');base=input_value(mod,'Terrain base');break
            mesh=obj.data
        model.wb_layers.remove(index)
        for attr in list(model.data.attributes):
            if attr.name.startswith(key):model.data.attributes.remove(attr)
        model.wb_layer_index=max(0,min(model.wb_layer_index,len(model.wb_layers)-1))
        rebuild_helper(model);refresh_stack(model)
        if obj:
            if context.view_layer.objects.active==obj:context.view_layer.objects.active=context.scene.wb_native.road
            bpy.data.objects.remove(obj,do_unlink=True)
            if mesh and mesh.users==0 and mesh.library is None:bpy.data.meshes.remove(mesh)
        if profile and profile.get('wb_native_feature')=='profile' and profile.users==1 and profile.library is None:
            curve=profile.data;bpy.data.objects.remove(profile,do_unlink=True)
            if curve.users==0 and curve.library is None:bpy.data.curves.remove(curve)
        if base and base.get('wb_grass_terrain_base') and base.users==1 and base.library is None:bpy.data.objects.remove(base,do_unlink=True)
        return {'FINISHED'}


class WB_OT_vertices(bpy.types.Operator):
    bl_idname='wb.native_vertex_settings';bl_label='Vertex layer settings';bl_options={'REGISTER','UNDO'}
    action:EnumProperty(items=[('READ','Read selected','Read first selected vertex'),('DISABLE','Disable selected','Disable at selected vertices'),('RESTORE','Restore selected','Enable at selected vertices')]);uid:StringProperty()
    def execute(self,context):
        global _suspended
        road=context.scene.wb_native.road;model=model_for(road);layer=next((l for l in model.wb_layers if l.uid==self.uid),None) if model else None;indices=selected(context,road) if road else []
        if not layer or not indices:self.report({'ERROR'},'Select the original road control vertices in Edit Mode');return {'CANCELLED'}
        if self.action=='READ':
            _suspended=True
            try:
                layer.vertex_enabled=read(model,prefix(layer)+'enabled')[indices[0]]>.5
                for field in ('width','offset','zpos'):setattr(layer,field,read(model,prefix(layer)+field)[indices[0]])
            finally:_suspended=False
        else:apply(layer,'enabled',self.action=='RESTORE',context)
        return {'FINISHED'}


def sync_model(model):
    """Remap values when control topology changes; movement is handled by shared data."""
    road=model.get('wb_road')
    if not road:return
    current=[tuple(p.co[:3]) for p in points(road)];old=[tuple(v.co) for v in model.data.vertices]
    if current==old:return
    if len(current)==len(old):
        for v,co in zip(model.data.vertices,current):v.co=co
        model.data.update();model.update_tag()
        return
    else:
        arrays={a.name:read(model,a.name) for a in model.data.attributes if a.data_type=='FLOAT' and a.domain=='POINT'}
        result={key:[] for key in arrays}
        for co in current:
            distance,index=min(((Vector(co)-Vector(p)).length,i) for i,p in enumerate(old)) if old else (1e9,0)
            for key,values in arrays.items():result[key].append(values[index] if distance<1e-4 else next((default(l,key[len(prefix(l)):]) for l in model.wb_layers if key.startswith(prefix(l))),0))
        model.data.clear_geometry();model.data.from_pydata(current,[],[])
        for key,values in result.items():write(model,key,values)
    model.data.update();refresh_stack(model)


classes=(WBLayer,WB_UL_layers,WB_OT_layer_move,WB_OT_layer_remove,WB_OT_vertices)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Object.wb_layers=CollectionProperty(type=WBLayer);bpy.types.Object.wb_layer_index=IntProperty(default=0)
def unregister():
    del bpy.types.Object.wb_layer_index;del bpy.types.Object.wb_layers
    for cls in reversed(classes):bpy.utils.unregister_class(cls)


def migrate_scene(scene):
    """Adopt older WB extrusions without editing native node groups or curves."""
    from .native_contacts import connect_surfaces,input_value
    for obj in list(scene.objects):
        kind=obj.get('wb_native_feature')
        if kind not in KINDS:continue
        mod=next((m for m in obj.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION')),None)
        if mod:
            road=input_value(mod,'Road')
            if kind=='grass':
                from .grass_surface import configure
                configure(scene,obj,mod)
            if road:add_layer(scene,road,obj,kind)
    if any(o.get('wb_layer_model') for o in scene.objects):connect_surfaces(scene)


class WB_PT_layer_controls(bpy.types.Panel):
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_parent_id='WB_PT_layer_stack';bl_options={'DEFAULT_CLOSED'}
    kind='curb'
    @classmethod
    def poll(cls,context):
        model=model_for(context.scene.wb_native.road) if context.scene.wb_native.road else None
        return bool(model and any(layer.kind==cls.kind for layer in model.wb_layers))
    def draw(self,context):
        layout=self.layout;model=model_for(context.scene.wb_native.road);road=model['wb_road'];indices=selected(context,road)
        road_edit=context.mode=='EDIT_CURVE' and context.edit_object==road
        layout.label(text=f'Apply to: {len(indices)} selected points' if road_edit else 'Apply to: all road points' if context.mode=='OBJECT' else 'Edit the road to change point settings')
        if context.mode!='OBJECT' and not road_edit:layout.operator('wb.edit_road_curve',text='Edit road points')
        for layer in model.wb_layers:
            if layer.kind!=self.kind:continue
            box=layout.box();row=box.row(align=True);row.prop(layer,'expanded',text='',icon='TRIA_DOWN' if layer.expanded else 'TRIA_RIGHT',emboss=False);row.label(text=layer.name);row.prop(layer,'enabled',text='Enabled');row.operator('wb.remove_native_layer',text='',icon='TRASH').uid=layer.uid
            if not layer.expanded:continue
            if context.mode=='EDIT_CURVE':
                row=box.row(align=True)
                for action,label in [('READ','Read first'),('DISABLE','Exclude'),('RESTORE','Include')]:
                    op=row.operator('wb.native_vertex_settings',text=label);op.action=action;op.uid=layer.uid
            col=box.column();col.enabled=context.mode=='OBJECT' or bool(indices)
            col.prop(layer,'vertex_enabled');col.prop(layer,'width');col.prop(layer,'offset');col.prop(layer,'zpos',text='Inner height offset (m)' if layer.kind=='grass' else 'Height offset (m)')

class WB_PT_curbs(WB_PT_layer_controls):bl_idname='WB_PT_curbs';bl_label='Curbs';bl_order=0;kind='curb'
class WB_PT_grass(WB_PT_layer_controls):bl_idname='WB_PT_grass';bl_label='Grass strips';bl_order=1;kind='grass'
class WB_PT_sidewalks(WB_PT_layer_controls):bl_idname='WB_PT_sidewalks';bl_label='Sidewalks';bl_order=2;kind='sidewalk'

_busy=False
@bpy.app.handlers.persistent
def sync_controls(scene,depsgraph):
    global _busy
    if _busy:return
    _busy=True
    try:
        from .grass_surface import sync_bases
        sync_bases(scene)
        for model in list(scene.objects):
            if model.get('wb_layer_model'):sync_model(model)
    finally:_busy=False

# Panels register after their native parent panel.
@bpy.app.handlers.persistent
def upgrade_layers(_unused):
    from .compatibility import migrate_saved_data
    migrate_saved_data()
    for scene in bpy.data.scenes:
        if any(o.get('wb_native_feature') in KINDS for o in scene.objects):migrate_scene(scene)

def deferred_upgrade():
    """Addon registration runs under Blender's restricted data context."""
    if not hasattr(bpy.data,'scenes'):return .1
    upgrade_layers(None)
    return None

def update_edit_preview():
    if not hasattr(bpy.data,'scenes'):return .1
    from .native_contacts import input_value
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if obj.get('wb_native_feature') not in KINDS:continue
            for mod in obj.modifiers:
                if mod.type!='NODES' or not mod.node_group or mod.node_group.get('wb_schema',0)<11:continue
                sources=[input_value(mod,k) for k in ('Road','Profile curve','Path curve')]
                editing=scene.wb_native.edit_preview and any(source and source.mode=='EDIT' for source in sources)
                set_input(mod,'Editing preview',editing)
    return .1

def register_panels():
    for cls in (WB_PT_curbs,WB_PT_grass,WB_PT_sidewalks):bpy.utils.register_class(cls)
    if sync_controls not in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.append(sync_controls)
    if upgrade_layers not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(upgrade_layers)
    if not bpy.app.timers.is_registered(deferred_upgrade):
        bpy.app.timers.register(deferred_upgrade,first_interval=.1)
    if not bpy.app.timers.is_registered(update_edit_preview):
        bpy.app.timers.register(update_edit_preview,first_interval=.1,persistent=True)
def unregister_panels():
    if bpy.app.timers.is_registered(update_edit_preview):bpy.app.timers.unregister(update_edit_preview)
    if bpy.app.timers.is_registered(deferred_upgrade):bpy.app.timers.unregister(deferred_upgrade)
    if upgrade_layers in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(upgrade_layers)
    if sync_controls in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.remove(sync_controls)
    for cls in (WB_PT_sidewalks,WB_PT_grass,WB_PT_curbs):bpy.utils.unregister_class(cls)
