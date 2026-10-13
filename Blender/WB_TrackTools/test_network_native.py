import bpy,sys,importlib.util,pathlib,json,time
root=pathlib.Path(__file__).parent.resolve();spec=importlib.util.spec_from_file_location('WB_TrackTools',root/'__init__.py',submodule_search_locations=[str(root)]);pkg=importlib.util.module_from_spec(spec);sys.modules['WB_TrackTools']=pkg;spec.loader.exec_module(pkg);pkg.register()
from WB_TrackTools import network,network_blender,diagnostics
bpy.ops.wm.read_factory_settings(use_empty=True);graph=json.loads((root/'fixtures/network.json').read_text());collection=bpy.data.collections.new('WB_GENERATED');bpy.context.scene.collection.children.link(collection)
def delete_object(obj):
 data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
 if data and data.users==0:bpy.data.meshes.remove(data)
t=time.perf_counter();specs,warnings,context,report=network_blender.assemble(collection,graph,pkg.create_spec,delete_object);print('WB_NATIVE_ASSEMBLED',time.perf_counter()-t,warnings,report,flush=True)
bpy.context.scene.wb_graph=json.dumps(graph);bpy.context.scene['wb_validation']=json.dumps(warnings);bpy.context.scene['wb_mesh_digest']='native-network';r=diagnostics.inspect_scene(bpy.context.scene);r['terrain']=report
for o in r['objects']:
 if o['category']!='terrain':assert o['boundary_edges']==0 and o['nonmanifold_edges']==0 and o['zero_area_faces']==0,(o['id'],o)
road=next(o for o in collection.objects if 'wb_union_sources' in o);print('WB_NETWORK_COMPONENT',road['wb_union_sources'],flush=True)
out=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(out/'WB_Network_Prototype.blend'));(out/'native_report.json').write_text(json.dumps(r,indent=2));print('WB_NATIVE_PASSED')
