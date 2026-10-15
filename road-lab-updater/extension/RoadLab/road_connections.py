"""Connect selected RoadLab curve points, including points inside a through street."""
import bpy
from . import point_settings,road_core
_keymaps=[]
class ROADLAB_OT_connect_points(bpy.types.Operator):
    bl_idname='roadlab.connect_points';bl_label='Connect road points';bl_options={'REGISTER','UNDO'}
    bl_description='Connect two road points; interior points create a branch without breaking the through street'
    @classmethod
    def poll(cls,context):
        obj=context.edit_object
        return context.mode=='EDIT_CURVE' and obj is not None and obj.get('roadlab_new_core',False)
    def execute(self,context):
        road=context.edit_object;road.update_from_editmode();selected=[i for i,p in enumerate(point_settings.points(road)) if p.select]
        if len(selected)!=2:self.report({'ERROR'},'Select two road points to connect');return {'CANCELLED'}
        points=point_settings.points(road);a,b=(points[i] for i in selected);coords=[tuple(p.co) for p in (a,b)]
        if (a.co.xyz-b.co.xyz).length<1e-5:self.report({'INFO'},'These points already share a junction');return {'CANCELLED'}
        from .lane_editor import segments
        point_settings.sync(road)
        if any({x,y}==set(selected) for x,y,_,_ in segments(road)):
            self.report({'INFO'},'These points are already connected');return {'CANCELLED'}
        endpoint=[];offset=0
        for spline in road.data.splines:
            for i in selected:
                if offset<=i<offset+len(spline.points):endpoint.append(not spline.use_cyclic_u and i-offset in (0,len(spline.points)-1))
            offset+=len(spline.points)
        if all(endpoint):
            result=bpy.ops.curve.make_segment()
            if result=={'FINISHED'}:road_core.rebuild(road,True)
            return result
        radii=[a.radius,b.radius];tilts=[a.tilt,b.tilt]
        bpy.ops.object.mode_set(mode='OBJECT')
        spline=road.data.splines.new('POLY');spline.points.add(1)
        for i,p in enumerate(spline.points):p.co=coords[i];p.radius=radii[i];p.tilt=tilts[i]
        for p in point_settings.points(road):p.select=False
        for p in spline.points:p.select=True
        road.update_tag();road_core.rebuild(road,True)
        bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'},'Road connected; through streets preserved')
        return {'FINISHED'}
def register():
    bpy.utils.register_class(ROADLAB_OT_connect_points)
    config=bpy.context.window_manager.keyconfigs.addon
    if config:
        km=config.keymaps.new(name='Curve',space_type='EMPTY');item=km.keymap_items.new('roadlab.connect_points','F','PRESS');_keymaps.append((km,item))
def unregister():
    for km,item in _keymaps:km.keymap_items.remove(item)
    _keymaps.clear();bpy.utils.unregister_class(ROADLAB_OT_connect_points)
