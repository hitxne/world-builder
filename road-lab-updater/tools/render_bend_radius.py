"""Actual linked bend-radius geometry with both road ends visible."""
import bpy,sys,json
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,core_terrain,lane_editor
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion
scene=bpy.context.scene
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
data=bpy.data.curves.new('Editable right-angle road','CURVE');data.dimensions='3D';s=data.splines.new('POLY');s.points.add(2)
for p,co in zip(s.points,[(-40,0,.02,1),(0,0,.02,1),(0,40,.02,1)]):p.co=co
road=bpy.data.objects.new('Editable right-angle road',data);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
road.select_set(True);bpy.context.view_layer.objects.active=road
for i,p in enumerate(road.data.splines[0].points):p.select=i==1
bpy.ops.object.mode_set(mode='EDIT');scene.roadlab_bend_radius=18.;road_core.flush_pending(force=True);bpy.ops.object.mode_set(mode='OBJECT')
lane=lambda:[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=lane(),outgoing=lane(),median=0,spacing=18) for _,_,a,b in lane_editor.segments(road)])
add_extrusion(scene,road,'curb');add_extrusion(scene,road,'sidewalk');lane_editor.rebuild(road,scene,True)
mesh=bpy.data.meshes.new('Terrain plane');mesh.from_pydata([(-65,-25,0),(25,-25,0),(25,65,0),(-65,65,0)],[],[(0,1,2,3)]);mesh.update()
terrain=bpy.data.objects.new('Terrain plane',mesh);scene.collection.objects.link(terrain);terrain.data.materials.append(RoadLab.material('grass'));scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True;core_terrain.rebuild(scene,True)
light=bpy.data.lights.new('Sun','SUN');light.energy=3;sun=bpy.data.objects.new('Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.3,-.35,-.3);scene.world.color=(.3,.3,.3)
cam=bpy.data.cameras.new('Bend overview');cam.type='ORTHO';cam.ortho_scale=78
camera=bpy.data.objects.new('Bend overview',cam);scene.collection.objects.link(camera);camera.location=(30,-35,65);camera.rotation_euler=(Vector((-12,12,0))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(root/'docs'/'bend-radius-01832.png');bpy.ops.render.render(write_still=True)
