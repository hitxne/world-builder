"""Render the real paired through-lane geometry for visual review (Blender 5.1)."""
import bpy,sys,json,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_editor,lane_add,point_settings as ps,core_terrain
from RoadLab.native_extension import set_input
scene=bpy.context.scene
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
data=bpy.data.curves.new('Road alignment','CURVE');data.dimensions='3D'
for coords in [[(-160,0,.02),(0,0,.02),(160,0,.02)],[(0,-160,.02),(0,0,.02),(0,160,.02)]]:
 spline=data.splines.new('POLY');spline.points.add(len(coords)-1)
 for p,co in zip(spline.points,coords):p.co=(*co,1)
road=bpy.data.objects.new('Road — edit this curve',data);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road)
set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
rows=ps.records(road);choice=dict(spline=0,anchors=[rows[1]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=-1)
candidate,pocket,_=lane_add.proposal(road,choice,-1,3.5,24,15)
candidate,pocket=lane_add.with_receiving_lane(road,candidate,pocket,'THROUGH',71.46,'RIGHT')
for part in candidate:lane_add.ensure_baseline(road,part,'RIGHT')
road['roadlab_lane_pockets']=json.dumps(candidate);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
from RoadLab.native_extrusion import add_extrusion
add_extrusion(scene,road,'curb');add_extrusion(scene,road,'sidewalk')
mesh=bpy.data.meshes.new('Terrain');mesh.from_pydata([(-200,-200,0),(200,-200,0),(200,200,0),(-200,200,0)],[],[(0,1,2,3)]);mesh.update()
terrain=bpy.data.objects.new('Terrain',mesh);scene.collection.objects.link(terrain)
terrain.data.materials.append(RoadLab.material('grass'));scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_spacing=4;terrain.roadlab_core_terrain_enabled=True;core_terrain.rebuild(scene,True)
light=bpy.data.lights.new('Daylight','SUN');light.energy=3;sun=bpy.data.objects.new('Daylight',light);scene.collection.objects.link(sun);sun.rotation_euler=(.35,-.3,-.35)
scene.world.color=(.3,.3,.3)
cam=bpy.data.cameras.new('Overview');cam.type='ORTHO';cam.ortho_scale=175
camera=bpy.data.objects.new('Overview',cam);scene.collection.objects.link(camera);camera.location=(25,0,200);camera.rotation_euler=(0,0,0);scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=650;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';output=root/'docs'/'lane-through-merge.png';output.parent.mkdir(exist_ok=True)
scene.render.filepath=str(output)
bpy.ops.render.render(write_still=True)
print('LANE_DEMO_RENDER',output)
