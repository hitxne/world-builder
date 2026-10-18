"""Selection-scoped sidewalk width and road-edge offset drafts."""
import bpy
from bpy.props import StringProperty,FloatProperty
from . import native_layers as layers
from .native_extension import set_input
from .native_contacts import input_value
_SESSIONS=set()

class WidthDraft:
    def __init__(self,context,uid):
        self.scene=context.scene;self.road=context.scene.wb_native.road;self.model=layers.model_for(self.road)
        if self.road is None or self.model is None:raise ValueError('Choose a RoadLab road with a sidewalk')
        if context.mode not in ('OBJECT','EDIT_CURVE') or context.mode=='EDIT_CURVE' and context.edit_object!=self.road:raise ValueError('Select the road and enter Edit Mode to edit its points')
        self.layer=next((l for l in self.model.wb_layers if l.uid==uid and l.kind=='sidewalk'),None)
        if self.layer is None:raise ValueError('Choose a sidewalk layer')
        self.indices=layers.selected(context,self.road)
        if context.mode=='EDIT_CURVE' and not self.indices:raise ValueError('Select road points first')
        self.selected_only=context.mode=='EDIT_CURVE';layers.sync_model(self.model)
        if not self.indices:self.indices=list(range(len(self.model.data.vertices)))
        self.original=layers.read(self.model,layers.prefix(self.layer)+'width');self.values=list(self.original)
        self.original_gaps=layers.read(self.model,layers.prefix(self.layer)+'offset');self.gaps=list(self.original_gaps)
        self.stacks=layers.read(self.model,layers.prefix(self.layer)+'stack')
        self.original_offsets=[s+g for s,g in zip(self.stacks,self.original_gaps)]
        self.objects=[];self.hidden=[];self.group=None;self.material=None;self.changed=False;self.closed=False
        _SESSIONS.add(self)
        try:
            data=self.model.data.copy();self.draft=bpy.data.objects.new('RoadLab Sidewalk Draft Fields',data);self.scene.collection.objects.link(self.draft);self.draft.hide_render=True;self.draft.hide_set(True);self.objects.append(self.draft)
            source=self.model['wb_helper'];helper=bpy.data.objects.new('RoadLab Sidewalk Draft Controls',source.data);self.scene.collection.objects.link(helper);helper.hide_render=True;helper.hide_set(True);self.objects.append(helper)
            helper.matrix_world=source.matrix_world.copy();constraint=helper.constraints.new('COPY_TRANSFORMS');constraint.target=self.road
            modifier=next(m for m in source.modifiers if m.type=='NODES');self.group=modifier.node_group.copy()
            for node in self.group.nodes:
                if node.bl_idname=='GeometryNodeObjectInfo' and node.inputs['Object'].default_value==self.model:node.inputs['Object'].default_value=self.draft
            mod=helper.modifiers.new('RoadLab draft vertex fields','NODES');mod.node_group=self.group
            self.material=bpy.data.materials.new('RoadLab Sidewalk Preview Blue');self.material.diffuse_color=(.07,.35,1.,1);self.material.use_nodes=True
            self.material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.07,.35,1.,1)
            self.copies=[];started=False
            for layer in self.model.wb_layers:
                if layer.uid==uid:started=True
                if not started or layer.object is None:continue
                source=layer.object;obj=source.copy();obj.name='RoadLab Sidewalk Preview — '+layer.name;self.scene.collection.objects.link(obj);self.objects.append(obj);obj.hide_render=True;obj.hide_select=True
                for key in ('wb_native_feature','wb_road'):
                    if key in obj:del obj[key]
                obj.color=(.07,.35,1.,1)
                self.hidden.append((source,source.hide_get()));source.hide_set(True)
                self.copies.append((layer,obj))
                for mod in obj.modifiers:
                    if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                        set_input(mod,'Vertex controls',helper);set_input(mod,'Material',self.material)
                        # A continuous surface is sufficient to review width and
                        # stack offsets. Individual blocks are finalized on Accept.
                        set_input(mod,'Sidewalk panels',False)
            self.refresh()
        except Exception:
            self.close();raise
    def refresh(self):
        self.draft.data.attributes[layers.prefix(self.layer)+'width'].data.foreach_set('value',self.values)
        self.draft.data.attributes[layers.prefix(self.layer)+'offset'].data.foreach_set('value',self.gaps)
        offset=[0.]*len(self.values)
        for layer in self.model.wb_layers:
            prefix=layers.prefix(layer);enabled=layers.read(self.draft,prefix+'enabled')
            if layer.enabled and layer.kind=='sidewalk':offset=[o+.003*e for o,e in zip(offset,enabled)]
            self.draft.data.attributes[prefix+'stack'].data.foreach_set('value',offset)
            if layer.enabled:
                widths=layers.read(self.draft,prefix+'width');gaps=layers.read(self.draft,prefix+'offset')
                offset=[o+(w+g)*e for o,w,g,e in zip(offset,widths,gaps,enabled)]
        self.draft.data.update();self.draft.update_tag()
    def update(self,width=None,offset=None):
        if width is not None:
            self.values=list(self.original)
            for i in self.indices:self.values[i]=width
        if offset is not None:
            self.gaps=list(self.original_gaps)
            for i in self.indices:self.gaps[i]=offset-self.stacks[i]
        self.changed=self.values!=self.original or self.gaps!=self.original_gaps;self.refresh()
    def accept(self):
        if self.changed:
            values=list(self.values);gaps=list(self.gaps);layer=self.layer;model=self.model
            self.close()
            model.data.attributes[layers.prefix(layer)+'width'].data.foreach_set('value',values)
            model.data.attributes[layers.prefix(layer)+'offset'].data.foreach_set('value',gaps)
            old=layers._suspended;layers._suspended=True
            try:layer.width=values[self.indices[0]];layer.offset=gaps[self.indices[0]]
            finally:layers._suspended=old
            layers.refresh_stack(model)
            from . import road_core
            road_core.refresh_markings(self.road)
            bpy.context.view_layer.update()
            terrain=self.scene.wb_native.terrain
            if terrain is not None and terrain.roadlab_core_terrain_enabled:
                from . import core_terrain
                core_terrain.rebuild(self.scene,True)
        else:self.close()
    def close(self):
        if self.closed:return
        self.closed=True
        for obj,hidden in self.hidden:
            try:obj.hide_set(hidden)
            except ReferenceError:pass
        for obj in reversed(self.objects):
            try:
                data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
                if data.users==0 and isinstance(data,bpy.types.Mesh):bpy.data.meshes.remove(data)
            except ReferenceError:pass
        if self.group is not None and self.group.users==0:bpy.data.node_groups.remove(self.group)
        if self.material is not None and self.material.users==0:bpy.data.materials.remove(self.material)
        _SESSIONS.discard(self)

def changed(self,context):
    draft=getattr(self,'draft',None)
    if draft is not None:draft.update(self.width)

def offset_changed(self,context):
    draft=getattr(self,'draft',None)
    if draft is not None:draft.update(offset=self.offset)

class ROADLAB_OT_sidewalk_width(bpy.types.Operator):
    bl_idname='roadlab.sidewalk_width';bl_label='Adjust sidewalk';bl_options={'REGISTER','UNDO'}
    bl_description='Preview sidewalk width and distance from the road edge at selected points; Apply saves, Cancel restores'
    uid:StringProperty(options={'HIDDEN'})
    width:FloatProperty(name='Width (m)',min=.05,max=100.,soft_max=15.,default=2.2,update=changed)
    offset:FloatProperty(name='Road edge offset (m)',description='Distance from the asphalt edge to the inner edge of this sidewalk, including preceding curb or grass layers',min=0.,max=100.,soft_max=15.,default=.323,update=offset_changed)
    def invoke(self,context,event):
        self.draft=None
        try:
            draft=WidthDraft(context,self.uid)
            self.width=sum(draft.original[i] for i in draft.indices)/len(draft.indices)
            self.offset=sum(draft.original_offsets[i] for i in draft.indices)/len(draft.indices)
            self.draft=draft
        except (ValueError,RuntimeError) as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self,width=380,confirm_text='Apply sidewalk')
    def draw(self,context):
        self.layout.label(text=f'{len(self.draft.indices)} selected points' if self.draft.selected_only else 'All road points')
        self.layout.prop(self,'width');self.layout.prop(self,'offset')
        if self.draft.values==self.draft.original and len({round(self.draft.original[i],5) for i in self.draft.indices})>1:self.layout.label(text='Mixed widths: change Width to set them together')
        if self.draft.gaps==self.draft.original_gaps and len({round(self.draft.original_offsets[i],5) for i in self.draft.indices})>1:self.layout.label(text='Mixed offsets: change Offset to set them together')
        if any(self.draft.gaps[i]<-.0001 for i in self.draft.indices):self.layout.label(text='Offset overlaps a preceding layer',icon='INFO')
        self.layout.label(text='Blue: draft sidewalk and following layers')
        self.layout.label(text='Tight inside corners taper to avoid overlap')
        self.layout.label(text='Apply saves and builds the concrete panels')
    def execute(self,context):
        draft=getattr(self,'draft',None)
        if draft is None:
            draft=WidthDraft(context,self.uid)
            draft.update(width=self.width if self.properties.is_property_set('width') else None,offset=self.offset if self.properties.is_property_set('offset') else None)
        draft.accept();self.draft=None
        return {'FINISHED'}
    def cancel(self,context):
        if getattr(self,'draft',None) is not None:self.draft.close();self.draft=None

@bpy.app.handlers.persistent
def clear(_):
    for draft in list(_SESSIONS):draft.close()

def register():
    bpy.utils.register_class(ROADLAB_OT_sidewalk_width);bpy.app.handlers.load_pre.append(clear)
def unregister():
    clear(None)
    if clear in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.remove(clear)
    bpy.utils.unregister_class(ROADLAB_OT_sidewalk_width)
