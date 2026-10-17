"""Native Blender toolbar tools with packaged geometry icons."""
from pathlib import Path
import bpy

def draw_brush_settings(context,layout,tool):
    if not hasattr(context.scene,'roadlab_road_brush'):return
    if context.active_object!=context.scene.wb_native.road:
        layout.label(text='Select the scene road to use this tool');return
    settings=context.scene.roadlab_road_brush
    layout.prop(settings,'radius');layout.prop(settings,'strength')
    if tool.idname=='roadlab.bank':layout.label(text='Drag sideways to bank')
    elif tool.idname=='roadlab.flatten':layout.label(text='Target: stroke-start height')

def draw_slice_settings(context,layout,tool):
    if context.active_object!=context.scene.wb_native.road:
        layout.label(text='Select the scene road to slice');return
    layout.label(text='Slice: detach | Alt + Slice: reconnect')
    if context.scene.wb_native.road:layout.operator('roadlab.reset_slices',text='Clear bridge cuts')

tools=[]
for mode,label,description in [
 ('RAISE','Raise road','Paint upward road elevation'),('LOWER','Lower road','Paint downward road elevation'),
 ('FLATTEN','Flatten road','Flatten toward the stroke-start height'),('SMOOTH','Smooth road','Smooth local road elevation'),
 ('WIDEN','Widen road','Paint increased width; add editable curve handles where needed'),
 ('BANK','Bank road','Grab and drag sideways to twist the road around its centerline'),
 ('SLICE','Slice terrain contact','Click to detach terrain; Alt-click to reconnect')]:
    attributes=dict(bl_space_type='VIEW_3D',bl_context_mode='OBJECT',bl_idname='roadlab.'+mode.lower(),bl_label=label,bl_description=description,bl_icon=str(Path(__file__).parent/'icons'/mode.lower()),bl_widget=None)
    if mode=='SLICE':
        attributes['bl_keymap']=(('roadlab.slice',{'type':'LEFTMOUSE','value':'PRESS','alt':True},{'properties':[('reattach',True)]}),('roadlab.slice',{'type':'LEFTMOUSE','value':'PRESS'},{'properties':[('reattach',False)]}))
        attributes['draw_settings']=staticmethod(draw_slice_settings)
    else:
        attributes['bl_keymap']=(('roadlab.sculpt',{'type':'LEFTMOUSE','value':'PRESS'},{'properties':[('tool_mode',mode)]}),)
        attributes['draw_settings']=staticmethod(draw_brush_settings)
    tools.append(type('ROADLAB_WST_'+mode,(bpy.types.WorkSpaceTool,),attributes))

def draw_terrain_settings(context,layout,tool):
    if context.active_object!=context.scene.wb_native.terrain:
        layout.label(text='Select the scene terrain');return
    settings=context.scene.roadlab_terrain_brush
    layout.prop(settings,'radius');layout.prop(settings,'strength')

for mode in ('RAISE','LOWER','FLATTEN','SMOOTH'):
    attributes=dict(bl_space_type='VIEW_3D',bl_context_mode='OBJECT',bl_idname='roadlab.terrain_'+mode.lower(),bl_label=mode.title()+' terrain',bl_description=mode.title()+' terrain; refine only the brushed mesh region',bl_icon=str(Path(__file__).parent/'icons'/mode.lower()),bl_widget=None,bl_keymap=(('roadlab.terrain_sculpt',{'type':'LEFTMOUSE','value':'PRESS'},{'properties':[('tool_mode',mode)]}),),draw_settings=staticmethod(draw_terrain_settings))
    tools.append(type('ROADLAB_WST_TERRAIN_'+mode,(bpy.types.WorkSpaceTool,),attributes))

def register():
    from . import brush_cursor
    brush_cursor.register()
    previous=None
    for tool in tools:
        bpy.utils.register_tool(tool,after=None,separator=previous is None or tool.bl_idname=='roadlab.terrain_raise')
        previous=tool.bl_idname

def unregister():
    from . import brush_cursor
    brush_cursor.unregister()
    for tool in reversed(tools):bpy.utils.unregister_tool(tool)
    for value in _icon_values.values():bpy.app.icons.release(value)
    _icon_values.clear()

_icon_values={}
def icon(mode):
    if mode not in _icon_values:_icon_values[mode]=bpy.app.icons.new_triangles_from_file(str(Path(__file__).parent/'icons'/(mode.lower()+'.dat')))
    return _icon_values[mode]
