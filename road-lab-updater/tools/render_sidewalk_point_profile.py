"""Actual Cycles comparison: saved profile and a one-point width/offset draft."""
import bpy,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,native_layers
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion
from RoadLab.sidewalk_width import WidthDraft
scene=bpy.context.scene
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
def road_at(y):
 cv=bpy.data.curves.new('Editable point profile','CURVE');cv.dimensions='3D';s=cv.splines.new('POLY');s.points.add(4)
 for p,x in zip(s.points,(-40,-20,0,20,40)):p.co=(x,y,.02,1)
 road=bpy.data.objects.new('Editable point profile',cv);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
 add_extrusion(scene,road,'curb');walk,_=add_extrusion(scene,road,'sidewalk');return road,walk
saved,_=road_at(-12);road,walk=road_at(12)
for obj in bpy.context.selected_objects:obj.select_set(False)
road.select_set(True);bpy.context.view_layer.objects.active=road
for i,p in enumerate(road.data.splines[0].points):p.select=i==2
bpy.ops.object.mode_set(mode='EDIT')
model=native_layers.model_for(road);layer=next(l for l in model.wb_layers if l.object==walk);draft=WidthDraft(bpy.context,layer.uid);draft.update(width=5.,offset=1.5)
# Render the same draft geometry that is normally viewport-only.
for source,_ in draft.hidden:source.hide_render=True
for _,copy in draft.copies:copy.hide_render=False
bpy.ops.object.mode_set(mode='OBJECT')
orange=bpy.data.materials.new('Selected point orange');orange.diffuse_color=(1.,.3,.025,1)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.55,location=(0,12,.6));bpy.context.object.data.materials.append(orange)
text_material=bpy.data.materials.new('Labels');text_material.diffuse_color=(.04,.05,.07,1)
for body,y in [('PREVIEW: selected point | width 5.0 m | road edge offset 1.5 m',26),('SAVED: width 2.2 m | road edge offset 0.323 m',-3)]:
 data=bpy.data.curves.new('Profile label','FONT');data.body=body;data.size=1.25;obj=bpy.data.objects.new('Profile label',data);scene.collection.objects.link(obj);obj.location=(-40,y,.3);data.materials.append(text_material)
mesh=bpy.data.meshes.new('Ground');mesh.from_pydata([(-60,-45,0),(60,-45,0),(60,45,0),(-60,45,0)],[],[(0,1,2,3)]);ground=bpy.data.objects.new('Ground',mesh);scene.collection.objects.link(ground);mesh.materials.append(RoadLab.material('grass'))
light=bpy.data.lights.new('Sun','SUN');light.energy=3;sun=bpy.data.objects.new('Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.15,-.25,-.2);scene.world.color=(.3,.3,.3)
cam=bpy.data.cameras.new('Point profile overview');cam.type='ORTHO';cam.ortho_scale=105
camera=bpy.data.objects.new('Point profile overview',cam);scene.collection.objects.link(camera);camera.location=(0,3,150);scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(root/'docs'/'sidewalk-point-profile-01830.png');bpy.ops.render.render(write_still=True)
draft.close();print('SIDEWALK_POINT_PROFILE_RENDER',scene.render.filepath,flush=True)
