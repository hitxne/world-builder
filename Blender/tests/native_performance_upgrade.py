import bpy,pathlib,sys,zipfile,tempfile,hashlib,os
root=pathlib.Path(__file__).parent;sys.path.insert(0,str(root if (root/'WB_TrackTools').exists() else root.parent))
bpy.ops.wm.open_mainfile(filepath=os.environ.get('WB_TRACKTOOLS_STARTUP',str(root/'tt_originals/TT_startup_scene_01(2).blend')))
for lib in bpy.data.libraries:lib.filepath=os.environ.get('WB_TRACKTOOLS_NODES',str(root/'tt_originals/TT_NodeGroups(3).blend'));lib.reload()
folder=pathlib.Path(tempfile.mkdtemp(prefix='wb_v08_nodes_'))
with zipfile.ZipFile(pathlib.Path(os.environ.get('WB_V08_ADDON_ZIP',str(root.parent/'Dist/WB_TrackTools_Additive_v08.zip')))) as z:z.extract('Nodes/WB_Native_Expansion_Nodes.blend',folder)
with bpy.data.libraries.load(str(folder/'Nodes/WB_Native_Expansion_Nodes.blend'),link=False) as (src,dst):dst.node_groups=['WB_EXTENSION_BORDER_EXTRUSION']
g=dst.node_groups[0];assert g['wb_schema']==8
import WB_TrackTools as addon
from WB_TrackTools import native_extension as ext
road=ext.native_roads(bpy.context.scene)[0];original_data=road.data;original_mods=[(m.name,m.node_group) for m in road.modifiers if m.type=='NODES']
c=bpy.data.collections.new('WB_TRACKTOOLS_FEATURES');bpy.context.scene.collection.children.link(c)
obj=bpy.data.objects.new('WB_existing_curb',bpy.data.meshes.new('WB_existing_mesh'));c.objects.link(obj);obj['wb_native_feature']='curb';mod=obj.modifiers.new('WB existing','NODES');mod.node_group=g
curve=bpy.data.curves.new('WB_existing_profile','CURVE');curve.dimensions='2D';s=curve.splines.new('POLY');s.points.add(3);s.use_cyclic_u=True
for p,co in zip(s.points,[(0,0,0,1),(0,.15,0,1),(.32,.15,0,1),(.32,0,0,1)]):p.co=co
profile=bpy.data.objects.new('WB_existing_profile',curve);bpy.context.scene.collection.objects.link(profile);profile.hide_set(True);profile.hide_render=True
ext.set_input(mod,'Road',road);ext.set_input(mod,'Profile curve',profile);ext.set_input(mod,'Height offset',.04)
identifiers={n:next(s.identifier for s in g.interface.items_tree if s.name==n and getattr(s,'in_out',None)=='INPUT') for n in ('Road','Profile curve','Height offset')}
addon.register()
assert mod.node_group['wb_schema']==9
for n,i in identifiers.items():assert next(s.identifier for s in mod.node_group.interface.items_tree if s.name==n and getattr(s,'in_out',None)=='INPUT')==i
assert mod[identifiers['Road']]==road and mod[identifiers['Profile curve']]==profile and abs(mod[identifiers['Height offset']]-.04)<1e-5
assert road.data==original_data and [(m.name,m.node_group) for m in road.modifiers if m.type=='NODES']==original_mods
bpy.context.view_layer.update();eval_obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=eval_obj.to_mesh();assert len(mesh.polygons)>0;eval_obj.to_mesh_clear()
addon.unregister();print('EXISTING_V08_UPGRADE_PASS',flush=True)
