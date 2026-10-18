"""Actual Cycles view of a curb-side height stroke and its attached sidewalk."""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,core_terrain
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion
from RoadLab.road_stroke_preview import RoadStrokePreview
scene=bpy.context.scene
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
cv=bpy.data.curves.new('Editable sculpt road','CURVE');cv.dimensions='3D';s=cv.splines.new('POLY');s.points.add(1)
for p,co in zip(s.points,[(-25,0,.02,1),(25,0,.02,1)]):p.co=co
road=bpy.data.objects.new('Editable sculpt road',cv);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
add_extrusion(scene,road,'curb');add_extrusion(scene,road,'sidewalk')
mesh=bpy.data.meshes.new('Terrain plane');mesh.from_pydata([(-45,-35,0),(45,-35,0),(45,35,0),(-45,35,0)],[],[(0,1,2,3)]);mesh.update()
terrain=bpy.data.objects.new('Terrain plane',mesh);scene.collection.objects.link(terrain);terrain.data.materials.append(RoadLab.material('grass'));scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True;core_terrain.rebuild(scene,True)
session=RoadStrokePreview(scene,road)
for _ in range(10):session.stamp((0,3.7),'RAISE',8,3,.1)
session.close(True);road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
light=bpy.data.lights.new('Sun','SUN');light.energy=3;sun=bpy.data.objects.new('Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.3,-.35,-.3);scene.world.color=(.3,.3,.3)
cam=bpy.data.cameras.new('Sidewalk sculpt overview');cam.type='ORTHO';cam.ortho_scale=35
camera=bpy.data.objects.new('Sidewalk sculpt overview',cam);scene.collection.objects.link(camera);camera.location=(17,25,18);camera.rotation_euler=(Vector((0,1,1))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=850;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(root/'docs'/'sidewalk-sculpt-01829.png');bpy.ops.render.render(write_still=True)
print('SIDEWALK_SCULPT_RENDER',scene.render.filepath,flush=True)
