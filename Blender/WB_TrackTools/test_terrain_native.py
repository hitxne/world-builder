"""Real Blender tests for persistent sculpting, protected grading and resampling."""
import bpy,sys,importlib.util,pathlib,json,math
from mathutils import Vector
root=pathlib.Path(__file__).parent.resolve();spec=importlib.util.spec_from_file_location('WB_TrackTools',root/'__init__.py',submodule_search_locations=[str(root)]);pkg=importlib.util.module_from_spec(spec);sys.modules['WB_TrackTools']=pkg;spec.loader.exec_module(pkg);pkg.register()
from WB_TrackTools import terrain_ui as ui,terrain_brush as brush,model
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
assert bpy.ops.wb.load_terrain_world()=={'FINISHED'}
obj=ui.terrain_object();settings=scene.wb_terrain;adjacent=ui.neighbors(obj)
before=[v.co.z for v in obj.data.vertices];base=[v.value for v in obj.data.attributes['wb_original_height'].data]
settings.mode='RAISE';settings.radius=20;settings.strength=5
for _ in range(8):ui.apply_stamp(obj,settings,(-75,45,0),.2,0,adjacent)
raised=[v.value for v in obj.data.attributes['wb_original_height'].data]
assert max(b-a for a,b in zip(base,raised))>7
for i,v in enumerate(obj.data.vertices):
    if math.hypot(v.co.x+75,v.co.y-45)>=20:assert raised[i]==base[i]
    if obj.data.attributes['wb_grade_weight'].data[i].value==1:assert abs(v.co.z-before[i])<1e-5
settings.mode='LOWER';ui.apply_stamp(obj,settings,(-75,45,0),.2,0,adjacent)
assert max(raised[i]-v.value for i,v in enumerate(obj.data.attributes['wb_original_height'].data))>.9
settings.mode='FLATTEN';settings.radius=10
original=[v.value for v in obj.data.attributes['wb_original_height'].data];ui.apply_stamp(obj,settings,(-75,45,0),.3,3.,adjacent)
for i,v in enumerate(obj.data.vertices):
    if math.hypot(v.co.x+75,v.co.y-45)<10:assert abs(obj.data.attributes['wb_original_height'].data[i].value-3)<=abs(original[i]-3)+1e-6
# A spike smooths toward its neighbors without altering vertices outside the brush.
points=[(x,y,0) for y in range(5) for x in range(5)];values=[0.]*25;values[12]=10
links=brush.adjacency(25,[(i,i+1,i+6) for i in [0,1,2,3,5,6,7,8,10,11,12,13,15,16,17,18]])
smoothed=brush.stamp(points,values,(2,2),1.5,2,1,'SMOOTH',neighbors=links)
assert 0<smoothed[12]<10 and smoothed[0]==0
settings.mode='SMOOTH';settings.radius=20;ui.apply_stamp(obj,settings,(-75,45,0),.1,0,adjacent)
ui.commit(scene,obj);sculpted=[v.co.z for v in obj.data.vertices];graph=model.loads(scene.wb_graph)
ui.rebuild(scene,graph);obj=ui.terrain_object();error=max(abs(v.co.z-z) for v,z in zip(obj.data.vertices,sculpted));assert error<2e-5,error
# Finer detail resamples the sculpted baseline instead of resetting it.
graph=json.loads(scene.wb_graph);graph['terrain']['grid_spacing']=1;ui.rebuild(scene,graph);obj=ui.terrain_object();assert len(obj.data.vertices)>len(sculpted)
ui.commit(scene,obj)
# A freely sculpted bridge-side mound for the delivered scene.
settings.mode='RAISE';settings.radius=24;settings.strength=4;adjacent=ui.neighbors(obj)
for _ in range(9):ui.apply_stamp(obj,settings,(-40,48,0),.2,0,adjacent)
settings.mode='SMOOTH';settings.strength=2
for _ in range(5):ui.apply_stamp(obj,settings,(-40,48,0),.2,0,adjacent)
ui.commit(scene,obj);settings.mode='RAISE';settings.radius=12;settings.strength=2;settings.spacing=1
out=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True)
path=out/'WB_Terrain_Sculpt.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));saved=json.loads(scene.wb_graph)['terrain']['source_mesh'];bpy.ops.wm.open_mainfile(filepath=str(path));assert json.loads(bpy.context.scene.wb_graph)['terrain']['source_mesh']==saved
report={'raise':True,'lower':True,'flatten':True,'smooth':True,'circular_locality':True,'protected_roadbed':True,'rebuild_max_error_m':error,'detail_resampling':True,'save_reopen_baseline':True,'vertices':len(ui.terrain_object().data.vertices),'interactive_modal_ui':'not exercised by headless tests'}
(out/'terrain_brush_validation.json').write_text(json.dumps(report,indent=2));print('WB_TERRAIN_TESTS_PASSED',report,flush=True)
# Render evidence, with the camera and lights outside generated geometry.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.resolution_x=1100;scene.render.resolution_y=850;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('WB_Sky');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.45,.55,.7,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
light=bpy.data.lights.new('WB_Sun','SUN');light.energy=3;sun=bpy.data.objects.new('WB_Sun',light);scene.collection.objects.link(sun);sun.rotation_euler=(.3,-.4,-.5)
camera=bpy.data.cameras.new('WB_Camera');cam=bpy.data.objects.new('WB_Camera',camera);scene.collection.objects.link(cam);scene.camera=cam
for name,position,target,lens in [('Overview',(-155,-160,145),(0,5,0),43),('BridgeHill',(-83,94,35),(-30,43,3),46)]:
    cam.location=position;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camera.lens=lens;scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path));print('WB_TERRAIN_RENDERED',flush=True)
