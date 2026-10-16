"""Example loading preserves sky nodes, color settings and the source World."""
import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
source=bpy.context.scene;world=source.world or bpy.data.worlds.new('User World');source.world=world;world.use_nodes=True
sky=world.node_tree.nodes.new('ShaderNodeTexSky');sky.sky_type='MULTIPLE_SCATTERING';sky.sun_elevation=.7
background=world.node_tree.nodes.get('Background');world.node_tree.links.new(sky.outputs['Color'],background.inputs['Color'])
background.inputs['Strength'].default_value=.37;world['custom_sky_setting']='preserve'
source.view_settings.exposure=1.3;source.view_settings.use_curve_mapping=True
source.view_settings.curve_mapping.curves[0].points.new(.3,.2);source.view_settings.curve_mapping.update()
viewport=[]
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   shading=area.spaces.active.shading
   viewport.append((shading,shading.type,shading.use_scene_world,shading.studiolight_rotate_z))
bpy.ops.roadlab.load_example();example=bpy.context.scene
assert example!=source and example.world!=world
assert example.world['custom_sky_setting']=='preserve'
assert example.world.node_tree.nodes[sky.name].sun_elevation==sky.sun_elevation
assert abs(example.world.node_tree.nodes.get('Background').inputs['Strength'].default_value-.37)<1e-6
assert example.view_settings.exposure==source.view_settings.exposure
assert len(example.view_settings.curve_mapping.curves[0].points)==len(source.view_settings.curve_mapping.curves[0].points)
assert abs(example.view_settings.curve_mapping.curves[0].points[1].location.y-.2)<1e-6
for shading,kind,use_world,rotation in viewport:
 assert (shading.type,shading.use_scene_world,shading.studiolight_rotate_z)==(kind,use_world,rotation)
example.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=2.
assert abs(background.inputs['Strength'].default_value-.37)<1e-6
assert source.world==world and world.node_tree.nodes.get(sky.name)
print('EXAMPLE_WORLD_PASS')
