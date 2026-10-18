"""Actual Cycles render: extended west road with an added right-turn lane."""
import bpy,sys,json,math
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_editor,lane_add,point_settings as ps
from RoadLab.native_extension import set_input
scene=bpy.context.scene
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
curve=bpy.data.curves.new('West extension','CURVE');curve.dimensions='3D'
for path in [[(-110,90,.02),(-110,0,.02),(-65,-1,.02),(0,0,.02),(80,0,.02)],[(0,-65,.02),(0,0,.02),(0,65,.02)]]:
 s=curve.splines.new('POLY');s.points.add(len(path)-1)
 for p,co in zip(s.points,path):p.co=(*co,1)
road=bpy.data.objects.new('RoadLab source curve',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
rows=ps.records(road);lane=[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=lane,outgoing=lane,median=0.,spacing=18.) for _,_,a,b in lane_editor.segments(road)])
choice=dict(spline=0,anchors=[rows[3]['id']],axis=[rows[1]['id'],rows[2]['id']],junction=True,junction_direction=-1)
candidate,pocket,_=lane_add.proposal(road,choice,-1,3.5,64,30);lane_add.ensure_baseline(road,pocket,'RIGHT');road['roadlab_lane_pockets']=json.dumps(candidate);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
from RoadLab.native_extrusion import add_extrusion
add_extrusion(scene,road,'curb');add_extrusion(scene,road,'sidewalk')
mesh=bpy.data.meshes.new('Ground');mesh.from_pydata([(-200,-200,0),(200,-200,0),(200,200,0),(-200,200,0)],[],[(0,1,2,3)]);mesh.update()
ground=bpy.data.objects.new('Ground',mesh);scene.collection.objects.link(ground);ground.data.materials.append(RoadLab.material('grass'))
light=bpy.data.lights.new('Sun','SUN');light.energy=3;sun=bpy.data.objects.new('Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.2,-.3,-.2);scene.world.color=(.3,.3,.3)
corner='--corner' in sys.argv
cam=bpy.data.cameras.new('Overview');cam.type='ORTHO';cam.ortho_scale=22 if corner else 142
camera=bpy.data.objects.new('Overview',cam);scene.collection.objects.link(camera);camera.location=(-110,0,180) if corner else (-43,0,180);scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=900 if corner else 1200;scene.render.resolution_y=900 if corner else 560;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(root/'docs'/('taper-sidewalk-corner.png' if corner else 'bent-turn-lane.png'))
bpy.ops.render.render(write_still=True)
print('POINT_LANE_RENDER',scene.render.filepath,flush=True)
