import bpy,sys,importlib.util,pathlib,json
root=pathlib.Path(__file__).parent.resolve();spec=importlib.util.spec_from_file_location('WB_TrackTools',root/'__init__.py',submodule_search_locations=[str(root)]);pkg=importlib.util.module_from_spec(spec);sys.modules['WB_TrackTools']=pkg;spec.loader.exec_module(pkg)
from WB_TrackTools import nodes
bpy.ops.wm.read_factory_settings(use_empty=True);groups=nodes.create_groups();g=groups[0]
curve=bpy.data.curves.new('WB_EDITABLE_ALIGNMENT','CURVE');curve.dimensions='3D';spline=curve.splines.new('POLY');spline.points.add(1);spline.points[0].co=(0,0,0,1);spline.points[1].co=(0,30,0,1)
obj=bpy.data.objects.new('WB_Profile_Proof',curve);bpy.context.scene.collection.objects.link(obj);modifier=obj.modifiers.new('WB asymmetric profile','NODES');modifier.node_group=g
sockets={s.name:s.identifier for s in g.interface.items_tree if s.item_type=='SOCKET' and s.in_out=='INPUT'}
modifier[sockets['Left width']]=3.;modifier[sockets['Right width']]=3.;modifier[sockets['Material']]=pkg.material('asphalt')
def coords():
 obj.update_tag();bpy.context.view_layer.update();mesh=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh();result=[tuple(v.co) for v in mesh.vertices];obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear();return result
before=coords();modifier[sockets['Left width']]=6.;after=coords();print('WB_GN_BOUNDS',[(min(v[k] for v in before),max(v[k] for v in before)) for k in range(3)],[(min(v[k] for v in after),max(v[k] for v in after)) for k in range(3)],flush=True)
assert len(before)>0 and len(before)==len(after)
unchanged=[a for a,b in zip(before,after) if a==b];assert len(unchanged)==len(before)//2,(len(before),len(unchanged))
assert all(abs(v[2])<1e-5 for v in after),'Road sweep not planar'
spline.points[1].radius=1.5;radius_coords=coords();assert radius_coords!=after
# Curved source proof with four independently editable radii.
curved=bpy.data.curves.new('WB_CURVED_ALIGNMENT','CURVE');curved.dimensions='3D';poly=curved.splines.new('POLY');poly.points.add(3)
for p,co,rad in zip(poly.points,[(25,0,0,1),(35,15,0,1),(25,30,0,1),(35,45,0,1)],[.8,1.3,1.3,.8]):p.co=co;p.radius=rad
curve_obj=bpy.data.objects.new('WB_Curved_Profile',curved);bpy.context.scene.collection.objects.link(curve_obj);cm=curve_obj.modifiers.new('WB curved profile','NODES');cm.node_group=g;cm[sockets['Left width']]=3.;cm[sockets['Right width']]=3.;cm[sockets['Material']]=pkg.material('asphalt');bpy.context.view_layer.update();evaluated=curve_obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();assert len(mesh.vertices)>100;assert all(p.normal.z>=-1e-5 for p in mesh.polygons);evaluated.to_mesh_clear()
out=pathlib.Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(out/'WB_Profile_Proof.blend'));bpy.data.libraries.write(str(out/'WB_ExtensionNodes.blend'),set(groups))
(out/'node_profile_test.json').write_text(json.dumps({'runtime':bpy.app.version_string,'evaluated_vertices':len(after),'fixed_side_vertices':len(unchanged),'left_width_isolation':'passed','curve_radius_update':'passed','planar_surface':'passed','curved_varying_radius_surface':'passed','groups':[{'name':x.name,'nodes':len(x.nodes),'links':len(x.links)} for x in groups]},indent=2))
print('WB_NODE_TEST_PASSED')
