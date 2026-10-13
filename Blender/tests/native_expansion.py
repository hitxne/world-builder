import bpy,pathlib,sys,hashlib,json,os,tempfile
from mathutils import Vector
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));import WB_TrackTools as addon;addon.register()
from WB_TrackTools import native_extension as ext,native_extrusion as features
bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(os.environ['WB_TT_STARTUP'])))
for lib in bpy.data.libraries:lib.filepath=str(pathlib.Path(os.environ['WB_TT_LIBRARY']));lib.reload()
scene=bpy.context.scene;road=ext.native_roads(scene)[0];terrain=ext.native_terrain(scene)
def source_state():
 return {'road':str(road.data.as_pointer()),'terrain':str(terrain.data.as_pointer()),'road_modifiers':[(m.name,m.type,m.node_group.name if m.type=='NODES' else '') for m in road.modifiers],'terrain_modifiers':[(m.name,m.type,m.node_group.name if m.type=='NODES' else '') for m in terrain.modifiers]}
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [pathlib.Path(os.environ['WB_TT_STARTUP']),pathlib.Path(os.environ['WB_TT_LIBRARY'])]};original=source_state();assert bpy.ops.wb.bind_tracktools()=={'FINISHED'};assert not scene.wb_graph

def evaluated(obj):
 bpy.context.view_layer.update();e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();v=[tuple(obj.matrix_world@p.co) for p in m.vertices];faces=[tuple(p.vertices) for p in m.polygons];e.to_mesh_clear();return v,faces
made={}
for kind in ('curb','sidewalk','grass'):
 obj,profile=features.add_extrusion(scene,road,kind);v,f=evaluated(obj);assert len(v)>0 and len(f)>0,(kind,len(v),len(f));made[kind]=(obj,profile);print('NATIVE_EXTRUSION',kind,len(v),len(f),min(p[2] for p in v),max(p[2] for p in v),flush=True)
assert source_state()==original
# The native curve remains authoritative; edits propagate through the original ROAD group.
points=[p for spl in road.data.splines for p in (spl.bezier_points if spl.type=='BEZIER' else spl.points)]
before,_=evaluated(made['sidewalk'][0])
for p in points:
 p.co.z+=1
 if hasattr(p,'handle_left'):p.handle_left.z+=1;p.handle_right.z+=1
road.data.update_tag();road.update_tag();after,_=evaluated(made['sidewalk'][0]);delta=min(p[2] for p in after)-min(p[2] for p in before);assert abs(delta-1)<.001,delta
for p in points:
 p.co.z-=1
 if hasattr(p,'handle_left'):p.handle_left.z-=1;p.handle_right.z-=1
road.data.update_tag();road.update_tag()
# A second native road crosses the sidewalk; surface heights come from its native ROAD output.
rv,_=evaluated(road);center=Vector(tuple((min(p[i] for p in rv)+max(p[i] for p in rv))/2 for i in range(3)))
curve=bpy.data.curves.new('WB_Test_Crossing','CURVE');curve.dimensions='3D';s=curve.splines.new('POLY');s.points.add(1)
s.points[0].co=(center.x-15,center.y,center.z-.025,1);s.points[1].co=(center.x+15,center.y,center.z-.025,1)
cross=bpy.data.objects.new('WB_Test_Crossing',curve);scene.collection.objects.link(cross);m=cross.modifiers.new('Native TrackTools ROAD','NODES');m.node_group=ext.road_modifier(road).node_group
for item in m.node_group.interface.items_tree:
 if getattr(item,'in_out',None)=='INPUT' and item.identifier in ext.road_modifier(road):
  value=ext.road_modifier(road)[item.identifier];m[item.identifier]=bool(value) if getattr(item,'socket_type',None)=='NodeSocketBool' else value
sidewalk=made['sidewalk'][0];mod=sidewalk.modifiers[0];plain,_=evaluated(sidewalk);ext.set_input(mod,'Crossing road',cross);ext.set_input(mod,'Lower at crossing',True);graded,_=evaluated(sidewalk)
ev=sidewalk.evaluated_get(bpy.context.evaluated_depsgraph_get());mm=ev.to_mesh();aa=mm.attributes.get('wb_edge_elevation');print('EDGE_ATTR', min(d.value for d in aa.data),max(d.value for d in aa.data),flush=True);ev.to_mesh_clear();cv,_=evaluated(cross);print('CROSS_BOUNDS',min(p[2] for p in cv),max(p[2] for p in cv),flush=True)
print('CROSS_DEBUG',center, min(p[2] for p in plain),max(p[2] for p in plain),min(p[2] for p in graded),max(p[2] for p in graded),flush=True)
changes=[a[2]-b[2] for a,b in zip(plain,graded) if abs(a[1]-center.y)<1.5];assert changes and max(changes)>.09,(min(changes),max(changes))
# Road and terrain node stacks are unchanged; neither original node group is modified.
assert source_state()==original
assert hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [pathlib.Path(os.environ['WB_TT_STARTUP']),pathlib.Path(os.environ['WB_TT_LIBRARY'])]}
# Optional geometry and editable profile vertices are native node controls.
curb,profile=made['curb'];m=curb.modifiers[0];ext.set_input(m,'Enabled',False);assert not evaluated(curb)[0];ext.set_input(m,'Enabled',True)
baseline,_=evaluated(curb);profile.data.splines[0].points[2].co.y+=.05;profile.data.update_tag();profile.update_tag();updated,_=evaluated(curb);assert max(p[2] for p in updated)>max(p[2] for p in baseline)+.049
profile.data.splines[0].points[2].co.y-=.05;profile.data.update_tag();profile.update_tag()
# An independent path curve supplies editable path vertices as an optional override.
path_data=bpy.data.curves.new('WB_Test_Path','CURVE');path_data.dimensions='3D';sp=path_data.splines.new('POLY');sp.points.add(1);sp.points[0].co=(0,0,0,1);sp.points[1].co=(0,10,0,1);path=bpy.data.objects.new('WB_Test_Path',path_data);scene.collection.objects.link(path)
ext.set_input(m,'Path curve',path);ext.set_input(m,'Use custom path',True);custom,_=evaluated(curb);assert custom and max(p[2] for p in custom)>.15,(min(p[2] for p in custom),max(p[2] for p in custom));sp.points[1].co.y=15;path_data.update_tag();path.update_tag();longer,_=evaluated(curb);assert max(p[1] for p in longer)>max(p[1] for p in custom)+4.9
ext.set_input(m,'Use custom path',False)
# Measure the sidewalk top against the native crossing road surface.
from mathutils.bvhtree import BVHTree
sv,sf=evaluated(sidewalk);cv,cf=evaluated(cross);sb=BVHTree.FromPolygons(sv,sf);cb=BVHTree.FromPolygons(cv,cf);contacts=[]
for x in (center.x-4.2,center.x+4.2):
 a=sb.ray_cast(Vector((x,center.y,100)),Vector((0,0,-1)),200)[0];b=cb.ray_cast(Vector((x,center.y,100)),Vector((0,0,-1)),200)[0]
 if a is not None and b is not None:contacts.append(abs(a.z-b.z))
assert contacts and max(contacts)<.001,contacts
out=pathlib.Path(os.environ.get('WB_NATIVE_OUT',tempfile.mkdtemp(prefix='wb-native-extension-')));out.mkdir(exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(out/'WB_TrackTools_Additive_Proof.blend'))
(out/'validation.json').write_text(json.dumps({'native_sources_preserved':True,'native_modifier_stacks_preserved':True,'road_curve_edit_delta_m':delta,'extrusions':['curb','sidewalk','grass'],'sidewalk_crossing_lowering_m':max(changes),'json_world_not_required':True,'editable_custom_path_vertices_live':True,'optional_enable_toggle':True,'editable_profile_vertices_live':True,'original_files_unchanged':True,'sidewalk_crossing_contact_error_m':max(contacts)},indent=2));bpy.data.libraries.write(str(out/'WB_Native_Expansion_Nodes.blend'),{features.extrusion_group()});print('WB_NATIVE_EXTENSION_PASSED',flush=True)
