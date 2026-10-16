"""Editable road-on-terrain examples, isolated from the user's current scene."""
import bpy,json
from . import road_core,core_terrain,lane_editor


def load_editable_example(context):
    lane_editor.stop_lane_preview();lane_editor.clear_approach_preview()
    if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    source=context.scene
    scene=bpy.data.scenes.new('RoadLab Example')
    # Keep the environment, but give the example its own editable World.
    scene.world=source.world.copy() if source.world else None
    scene.render.engine=source.render.engine
    scene.display_settings.display_device=source.display_settings.display_device
    for name in ('view_transform','look','exposure','gamma','use_curve_mapping'):
        try:setattr(scene.view_settings,name,getattr(source.view_settings,name))
        except (AttributeError,TypeError):pass
    if source.view_settings.use_curve_mapping:
        old=source.view_settings.curve_mapping;new=scene.view_settings.curve_mapping
        for name in ('black_level','white_level','use_clip','clip_min_x','clip_min_y','clip_max_x','clip_max_y'):
            setattr(new,name,getattr(old,name))
        for original,target in zip(old.curves,new.curves):
            for point in list(target.points)[1:-1]:target.points.remove(point)
            target.points[0].location=original.points[0].location;target.points[-1].location=original.points[-1].location
            for point in list(original.points)[1:-1]:target.points.new(*point.location)
            for a,b in zip(original.points,target.points):b.handle_type=a.handle_type
        new.update()
    scene['roadlab_example_parent_scene']=source.name
    context.window.scene=scene
    # Keep the authoring terrain as one ordinary editable quad.
    mesh=bpy.data.meshes.new('RoadLab Terrain Plane')
    mesh.from_pydata([(-100,-100,0),(100,-100,0),(100,100,0),(-100,100,0)],[],[(0,1,2,3)]);mesh.update()
    terrain=bpy.data.objects.new('Terrain',mesh);scene.collection.objects.link(terrain)
    from . import material
    terrain.data.materials.append(material('grass'))
    terrain.roadlab_core_terrain_spacing=2
    data=bpy.data.curves.new('Road Alignment','CURVE');data.dimensions='3D'
    for path in [[(-55,0,.02),(0,0,.02),(55,0,.02)],[(0,-55,.02),(0,0,.02),(0,55,.02)]]:
        spline=data.splines.new('POLY');spline.points.add(2)
        for point,co in zip(spline.points,path):point.co=(*co,1)
    road=bpy.data.objects.new('Road — edit this curve',data);scene.collection.objects.link(road)
    context.view_layer.update();scene.wb_native.road=road;road_core.attach(road)
    from .native_extension import set_input
    set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
    lane=lambda:[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
    road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=lane(),outgoing=lane(),median=0,spacing=18) for _,_,a,b in lane_editor.segments(road)])
    configs=lane_editor.state(road)
    for config in configs[2:]:
        incoming=config['endpoints'][1]==lane_editor.segments(road)[2][3]
        config['crosswalk_incoming']=incoming;config['crosswalk_outgoing']=not incoming;config['crosswalk_tactile']=True
    road['roadlab_lanes']=json.dumps(configs)
    lane_editor.rebuild(road,scene,True)
    from .native_extrusion import add_extrusion
    add_extrusion(scene,road,'curb');sidewalk,_=add_extrusion(scene,road,'sidewalk')
    from .native_layers import model_for
    next(layer for layer in model_for(road).wb_layers if layer.object==sidewalk).width=3.2
    lane_editor.rebuild(road,scene,True)
    scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True;core_terrain.rebuild(scene,True)
    # Source curve is the active object; hidden meshes remain implementation details.
    for obj in context.view_layer.objects:obj.select_set(False)
    road.select_set(True);context.view_layer.objects.active=road
    for screen in [context.screen] if context.screen else []:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                from mathutils import Quaternion
                space=area.spaces.active
                space.region_3d.view_rotation=Quaternion((1,0,0,0));space.region_3d.view_perspective='ORTHO'
                space.region_3d.view_location=(0,0,0);space.region_3d.view_distance=145
    scene['roadlab_editable_example']=True
    return road,terrain
