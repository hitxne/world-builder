"""Actual angled crossing, curb opening and conforming tactile pads."""
import bpy,sys,math,json
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import road_core,core_terrain,lane_editor
scene=bpy.context.scene;road=scene.wb_native.road
road.data.splines[1].points[2].co=(18,40,.02,1)
road_core.rebuild(road,True);core_terrain.rebuild(scene,True);lane_editor.rebuild(road,scene,True)
light=bpy.data.lights.new('Sun','SUN');light.energy=3;sun=bpy.data.objects.new('Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.3,-.35,-.3);scene.world.color=(.3,.3,.3)
cam=bpy.data.cameras.new('Crosswalk overview');cam.type='ORTHO';cam.ortho_scale=23
camera=bpy.data.objects.new('Crosswalk overview',cam);scene.collection.objects.link(camera);camera.location=(20,25,28);camera.rotation_euler=(Vector((4,9,0))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(root/'docs'/'angled-crosswalk-01832.png');bpy.ops.render.render(write_still=True)
