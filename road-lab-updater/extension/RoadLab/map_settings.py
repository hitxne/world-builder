"""Scene-wide RoadLab map settings. No street/junction/roundabout overrides."""
import bpy
from bpy.props import EnumProperty, IntProperty, PointerProperty


def changed(settings, context):
    settings.traffic_revision += 1
    scene=getattr(context,'scene',None)
    if scene is not None:
        scene['roadlab_traffic_dirty']=True
        from . import lane_editor
        for obj in list(scene.objects):
            if obj.get('roadlab_new_core') and 'roadlab_lanes' in obj:
                try:lane_editor.rebuild(obj,scene)
                except Exception as error:
                    import json
                    obj['roadlab_marking_warnings']=json.dumps([str(error)])
    # Lane/roundabout systems consume this revision on their next regeneration.
    # Do not rewrite ordinary road geometry or pretend traffic adapters are live.


class ROADLAB_MapSettings(bpy.types.PropertyGroup):
    traffic_side: EnumProperty(name='Driving side',description='Map-wide side of the road used by traffic; independent of vehicle steering-wheel position',items=[('RIGHT','Right-side traffic','All roads use right-side traffic'),('LEFT','Left-side traffic','All roads use left-side traffic')],default='RIGHT',update=changed)
    traffic_revision: IntProperty(default=0,options={'HIDDEN'})


def traffic_side(scene):
    """Only application-level source; no object or junction fallback."""
    side=scene.roadlab_map_settings.traffic_side
    if side not in ('RIGHT','LEFT'):raise ValueError('Unknown map driving side')
    return side


def export(scene):
    return {'schema':1,'traffic_side':traffic_side(scene),
            'traffic_revision':scene.roadlab_map_settings.traffic_revision}


class ROADLAB_PT_map_settings(bpy.types.Panel):
    bl_label='Settings'
    bl_idname='ROADLAB_PT_map_settings'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='RoadLab'
    bl_order=-15
    bl_options={'DEFAULT_CLOSED'}

    def draw(self,context):
        layout=self.layout
        layout.prop(context.scene.roadlab_map_settings,'traffic_side')
        layout.label(text='Applies to the entire map',icon='WORLD')


classes=(ROADLAB_MapSettings,ROADLAB_PT_map_settings)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.roadlab_map_settings=PointerProperty(type=ROADLAB_MapSettings)


def unregister():
    del bpy.types.Scene.roadlab_map_settings
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
