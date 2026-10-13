"""Blender 5.1.2: --background --python build_blender.py -- OUT [SCENE LIBRARY]."""
import bpy,sys,pathlib,shutil,json,importlib.util,time,math,os
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];out=pathlib.Path(args[0]).resolve();out.mkdir(parents=True,exist_ok=True);root=pathlib.Path(__file__).parent.resolve()
spec=importlib.util.spec_from_file_location('WB_TrackTools',root/'__init__.py',submodule_search_locations=[str(root)]);mod=importlib.util.module_from_spec(spec);sys.modules['WB_TrackTools']=mod;spec.loader.exec_module(mod);mod.register()
from WB_TrackTools import model,diagnostics,nodes

def camera_render(scene,path,center,scale,top=False):
 camdata=bpy.data.cameras.new('WB_EvidenceCamera');camera=bpy.data.objects.new('WB_EvidenceCamera',camdata);scene.collection.objects.link(camera)
 camera.location=Vector(center)+Vector((0,0,95) if top else (65,-85,78));direction=Vector(center)-camera.location;camera.rotation_euler=direction.to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=scale;scene.camera=camera
 world=bpy.data.worlds.new('WB_EvidenceWorld');world.use_nodes=True;world.node_tree.nodes.get('Background').inputs[0].default_value=(.24,.27,.31,1);world.node_tree.nodes.get('Background').inputs[1].default_value=.8;scene.world=world
 lightdata=bpy.data.lights.new('WB_Sun','SUN');lightdata.energy=3;light=bpy.data.objects.new('WB_Sun',lightdata);scene.collection.objects.link(light);light.rotation_euler=(.4,-.3,-.5)
 scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False;scene.render.resolution_x=1100;scene.render.resolution_y=850;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(path)
 scene.view_settings.view_transform='AgX';bpy.ops.render.render(write_still=True)
 return camera

selected=os.environ.get('WB_ONLY_FIXTURES','').split(',') if os.environ.get('WB_ONLY_FIXTURES') else None
results=json.loads((out/'blender_validation.json').read_text()) if selected and (out/'blender_validation.json').exists() else {}
for fixture in ('intersection','skew','boulevard','arterial','interchange','parking'):
 if selected and fixture not in selected:continue
 bpy.ops.wm.read_factory_settings(use_empty=True)
 # factory reset removes property registration? Classes remain registered.
 graph=model.loads((root/'fixtures'/(fixture+'.json')).read_text());t=time.perf_counter();mod.regenerate(bpy.context.scene,graph);mod.sync_controls(bpy.context.scene,graph);report=diagnostics.inspect_scene(bpy.context.scene);report['regenerate_seconds']=time.perf_counter()-t
 for obj in report['objects']:
  if obj['category'] not in ('marking','warning'):
   assert obj['boundary_edges']==0,(obj['id'],obj['boundary_edges']);assert obj['signed_volume_m3']>0,(obj['id'],'inverted signed volume')
  assert obj['nonmanifold_edges']==0,(obj['id'],'nonmanifold')
  assert obj['zero_area_faces']==0,(obj['id'],'zero area')
 # Direct output edits must be detected without replacing the graph or mesh.
 first=next(obj for obj in bpy.data.collections['WB_GENERATED'].objects if obj.type=='MESH');original=first.data.vertices[0].co.copy();first.data.vertices[0].co.x+=.02
 rejected=False
 try:mod.regenerate(bpy.context.scene,graph)
 except ValueError as error:rejected='Direct edit detected' in str(error)
 assert rejected,'Direct mesh edits were silently overwritten'
 first.data.vertices[0].co=original;report['direct_edit_protection']='passed'
 # determinism and data cleanup: repeated regeneration leaves no orphan WB meshes.
 digest=bpy.context.scene['wb_mesh_digest'];num_meshes=len(bpy.data.meshes);mod.regenerate(bpy.context.scene,graph);assert bpy.context.scene['wb_mesh_digest']==digest;assert len(bpy.data.meshes)==num_meshes
 groups=nodes.create_groups();bpy.data.libraries.write(str(out/'WB_ExtensionNodes.blend'),set(groups))
 center=(80 if fixture=='arterial' else 60,0,0) if fixture in ('boulevard','arterial') else (28,0,0) if fixture=='parking' else (0,0,0);scale=200 if fixture=='interchange' else 195 if fixture=='arterial' else 145 if fixture=='boulevard' else 108
 camera_render(bpy.context.scene,out/(fixture+'_overview.png'),center,scale)
 if fixture=='intersection':
  camera=bpy.context.scene.camera;camera.location=(0,0,95);camera.rotation_euler=(0,0,0);camera.data.ortho_scale=102;bpy.context.scene.render.filepath=str(out/'intersection_top.png');bpy.ops.render.render(write_still=True)
  camera.location=(-24,41,25);target=Vector((-7.32,26,.0));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=18;bpy.context.scene.render.filepath=str(out/'ramp_detail.png');bpy.ops.render.render(write_still=True)
  # restore opening view to full intersection
  camera.location=(65,-85,78);camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=108
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    area.spaces.active.shading.color_type='MATERIAL';area.spaces.active.region_3d.view_location=center;area.spaces.active.region_3d.view_distance=scale;area.spaces.active.region_3d.view_rotation=bpy.context.scene.camera.rotation_euler.to_quaternion()
 blend=out/('WB_'+fixture.title()+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend));graph_text=bpy.context.scene.wb_graph
 bpy.ops.wm.open_mainfile(filepath=str(blend));assert bpy.context.scene.wb_graph==graph_text
 after=diagnostics.inspect_scene(bpy.context.scene);assert [(o['id'],o['vertices_sha256']) for o in after['objects']]==[(o['id'],o['vertices_sha256']) for o in report['objects']]
 report['save_reopen']='passed';report['regeneration_determinism']='passed';report['orphan_mesh_regression']='passed';results[fixture]=report
 (out/(fixture+'_report.json')).write_text(json.dumps(report,indent=2))
 print('WB_FIXTURE_VALIDATED',fixture,flush=True)

if len(args)==3:
 scene_path=pathlib.Path(args[1]).resolve();lib_path=pathlib.Path(args[2]).resolve()
 if out in (scene_path.parent,lib_path.parent):raise ValueError('Separate output directory required')
 local_lib=out/'WB_TrackTools_Dependency.blend';shutil.copy2(lib_path,local_lib)
 bpy.ops.wm.open_mainfile(filepath=str(scene_path))
 for lib in list(bpy.data.libraries):lib.filepath=str(local_lib);lib.reload()
 def baseline():
  bpy.context.view_layer.update();data={};deps=bpy.context.evaluated_depsgraph_get();deps.update()
  for name in ('road_01','terrain_01'):
   obj=bpy.data.objects.get(name)
   if obj:
    e=obj.evaluated_get(deps);m=e.to_mesh();data[name]={'vertices':len(m.vertices),'faces':len(m.polygons),'surface_area':sum(p.area for p in m.polygons),'bounds':[[min(v.co[k] for v in m.vertices),max(v.co[k] for v in m.vertices)] for k in range(3)]};e.to_mesh_clear()
  return data
 baseline();before=baseline();graph=model.loads((root/'fixtures/intersection.json').read_text());graph['junction']['center']=[200,0,0];mod.regenerate(bpy.context.scene,graph);mod.sync_controls(bpy.context.scene,graph);after=baseline();print('WB_BASELINE_COMPARE',before,after,flush=True);assert before['road_01']==after['road_01'];assert before['terrain_01']['vertices']==after['terrain_01']['vertices'];assert all(abs(before['terrain_01']['bounds'][k][i]-after['terrain_01']['bounds'][k][i])<1e-4 for k in range(3) for i in range(2))
 nodes.create_groups()
 target=out/'WB_Startup_Extension.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target))
 for lib in bpy.data.libraries:lib.filepath='//'+local_lib.name
 bpy.ops.wm.save_mainfile();bpy.ops.wm.open_mainfile(filepath=str(target));reopened=baseline();assert reopened['road_01']==before['road_01']
 results['source_copy']={'baseline':before,'after_extension':after,'terrain_note':'Original terrain Boolean face count varies across evaluations; vertex count and bounds checked; strict topology invariance not established','save_reopen':'passed','original_library':'unchanged','extension_location':[200,0,0]}
(out/'blender_validation.json').write_text(json.dumps(results,indent=2))
print('WB_BUILD_COMPLETE',out,flush=True)
