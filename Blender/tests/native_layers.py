import bpy,sys,pathlib,json,os
from mathutils import Matrix,Vector
root=pathlib.Path(__file__).parent;sys.path.insert(0,str(root if (root/'WB_TrackTools').exists() else root.parent));import WB_TrackTools as addon;addon.register()
from WB_TrackTools import native_extension as ext,native_extrusion as feats,native_layers as layers
bpy.ops.wm.open_mainfile(filepath=os.environ.get('WB_TRACKTOOLS_STARTUP',str(root/'tt_originals/TT_startup_scene_01(2).blend')))
for lib in bpy.data.libraries:lib.filepath=os.environ.get('WB_TRACKTOOLS_NODES',str(root/'tt_originals/TT_NodeGroups(3).blend'));lib.reload()
road=ext.native_roads(bpy.context.scene)[0];curve=bpy.data.curves.new('WB_Layer_Test','CURVE');curve.dimensions='3D';s=curve.splines.new('POLY');s.points.add(3)
for p,q in zip(s.points,[(0,0,1.5),(10,0,1.5),(20,0,1.5),(30,0,1.5)]):p.co=(*q,1)
road.data=curve;road.matrix_world=Matrix.Identity(4);m=ext.road_modifier(road)
for name,val in [('road width',6.),('crossfall',0.)]:ext.set_input(m,name,val)
bpy.context.scene.wb_native.road=road
objects=[]
for kind in ['curb','grass','sidewalk','grass','sidewalk']:objects.append(feats.add_extrusion(bpy.context.scene,road,kind)[0])
model=layers.model_for(road)
def bounds(obj):
 bpy.context.view_layer.update();e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh();vs=[obj.matrix_world@v.co for v in mesh.vertices if 4<v.co.x<26];r=[min(abs(v.y) for v in vs),max(abs(v.y) for v in vs),min(v.z for v in vs),max(v.z for v in vs),len(mesh.polygons)] if vs else [];e.to_mesh_clear();return r
report={'stack':[]}
expected=[(3,3.32),(3.32,4.52),(4.52,6.72),(6.72,7.92),(7.92,10.12)]
for layer,want in zip(model.wb_layers,expected):
 b=bounds(layer.object);assert b and max(abs(b[i]-want[i]) for i in (0,1))<.002,(layer.name,b,want)
 bpy.context.view_layer.update();e=layer.object.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh()
 for sign in (-1,1):
  ys=[abs(v.co.y) for v in mesh.vertices if 4<v.co.x<26 and v.co.y*sign>0]
  assert ys and abs(min(ys)-want[0])<.002 and abs(max(ys)-want[1])<.002,(layer.name,sign,ys)
 e.to_mesh_clear()
 report['stack'].append({'name':layer.name,'kind':layer.kind,'uid':layer.uid,'radial_bounds':b[:2]})
assert len({l.uid for l in model.wb_layers})==5
# Same-kind layers retain independent values and identity through reordering.
uids=[l.uid for l in model.wb_layers];model.wb_layers.move(4,1);layers.refresh_stack(model)
assert [l.uid for l in model.wb_layers]==[uids[0],uids[4],uids[1],uids[2],uids[3]]
assert abs(bounds(model.wb_layers[1].object)[0]-3.32)<.002
model.wb_layers.move(1,4);layers.refresh_stack(model)
# Width changes move all following layers, including repeated instances.
model.wb_layers[1].width=2.
assert abs(bounds(model.wb_layers[2].object)[0]-5.32)<.002
assert abs(bounds(model.wb_layers[3].object)[0]-7.52)<.002
model.wb_layers[1].width=1.2
# Per-vertex edits act on selected original control points only.
for o in bpy.context.selected_objects:o.select_set(False)
road.hide_set(False);road.select_set(True);bpy.context.view_layer.objects.active=road
for p in s.points:p.select=False
s.points[2].select=True;s.points[3].select=True
bpy.ops.object.mode_set(mode='EDIT')
layer=model.wb_layers[3];layer.width=1.8;layer.offset=.25;layer.zpos=.3
for field,target in [('width',1.8),('offset',.25),('zpos',.3)]:
 v=layers.read(model,layers.prefix(layer)+field);assert abs(v[2]-target)<1e-5 and abs(v[3]-target)<1e-5 and abs(v[0]-layers.default(layer,field))<1e-5,(field,v)
layer.vertex_enabled=False
bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
e=layer.object.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh();assert not any(v.co.x>24 for v in mesh.vertices);e.to_mesh_clear()
# All disabled must produce no geometry (including no boolean cutter remnants).
layers.apply(layer,'enabled',0,bpy.context);assert bounds(layer.object)==[]
layers.apply(layer,'enabled',1,bpy.context)
for field in ('width','offset','zpos'):layers.apply(layer,field,layers.default(layer,field),bpy.context)
# Source control points still drive all expansions live.
before=[bounds(o)[2] for o in objects]
for p in layers.points(road):p.co.z+=1
road.data.update_tag();road.update_tag();bpy.context.view_layer.update()
for obj,z in zip(objects,before):
 b=bounds(obj);assert abs(b[2]-z-1)<.002,(obj.name,b,z,[tuple(p.co) for p in layers.points(road)])
for p in layers.points(road):p.co.z-=1
road.data.update_tag();road.update_tag();bpy.context.view_layer.update()
report.update(both_road_sides=True,reordering=True,width_propagation=True,selected_vertex_fields=True,selected_disable=True,all_disabled_empty=True,live_source_curve=True)
out=root/'WB_Output_Layers';out.mkdir(exist_ok=True);(out/'native_layer_validation.json').write_text(json.dumps(report,indent=2))
# Export only our group, never the commercial TrackTools node library.
bpy.data.libraries.write(str(out/'WB_Native_Expansion_Nodes.blend'),{feats.extrusion_group()},fake_user=True,compress=True)
# Render a proof view; commercial scene remains a local test copy.
terrain=ext.native_terrain(bpy.context.scene)
if terrain:terrain.hide_render=True
evalroad=road.evaluated_get(bpy.context.evaluated_depsgraph_get());roadmesh=evalroad.to_mesh().copy();evalroad.to_mesh_clear();roadmesh.materials.clear();roadmesh.materials.append(addon.material('asphalt'));proofroad=bpy.data.objects.new('WB_Render_Asphalt',roadmesh);scene_collection=bpy.context.scene.collection;scene_collection.objects.link(proofroad);proofroad.matrix_world=road.matrix_world.copy();road.hide_render=True
camdata=bpy.data.cameras.new('WB_Proof_Camera');cam=bpy.data.objects.new('WB_Proof_Camera',camdata);bpy.context.scene.collection.objects.link(cam);cam.location=(15,0,40);direction=Vector((15,0,1.5))-cam.location;cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=38;bpy.context.scene.camera=cam
lightdata=bpy.data.lights.new('WB_Proof_Light','AREA');lightdata.energy=2200;lightdata.shape='DISK';lightdata.size=30;light=bpy.data.objects.new('WB_Proof_Light',lightdata);bpy.context.scene.collection.objects.link(light);light.location=(15,-5,25)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.render.resolution_x=1100;scene.render.resolution_y=750;scene.render.resolution_percentage=100;scene.world.color=(.25,.25,.25);scene.render.filepath=str(out/'RepeatedLayers.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Layers.blend'));print('NATIVE_LAYER_VALIDATION_PASS',json.dumps(report),flush=True)
