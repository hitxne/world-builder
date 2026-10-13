import bpy,sys,pathlib,json,importlib.util,time
root=pathlib.Path(__file__).parent.resolve();spec=importlib.util.spec_from_file_location('WB_TrackTools',root/'__init__.py',submodule_search_locations=[str(root)]);pkg=importlib.util.module_from_spec(spec);sys.modules['WB_TrackTools']=pkg;spec.loader.exec_module(pkg);pkg.register()
from WB_TrackTools import model,geometry
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;results={}
for fixture in ('intersection','skew','boulevard','arterial','interchange','parking'):
 scene.wb_controls.fixture=fixture;assert bpy.ops.wb.load_pilot()=={'FINISHED'},fixture
 assert model.loads(scene.wb_graph)['fixture']==fixture
 assert bpy.ops.wb.rebuild()=={'FINISHED'},fixture
 results[fixture]='load and regenerate operators passed'
scene.wb_controls.fixture='parking';bpy.ops.wb.load_pilot();g=model.loads(scene.wb_graph);outline=next(o for o in bpy.data.collections['WB_PARKING_OUTLINES'].objects if o['wb_parking_kind']=='island');island_id=outline['wb_parking_id'];outline.data.splines[0].points[0].co.x+=.5
assert bpy.ops.wb.capture_parking()=={'FINISHED'};changed=model.loads(scene.wb_graph);assert changed['parking']['vertices']==g['parking']['vertices'];assert next(i for i in changed['parking']['islands'] if i['id']==island_id)['vertices']!=next(i for i in g['parking']['islands'] if i['id']==island_id)['vertices'];results['parking_outlines']='editable planter applied; lot boundary unchanged'
scene.wb_controls.fixture='intersection';bpy.ops.wb.load_pilot();graph=model.loads(scene.wb_graph);before_b=json.loads(json.dumps(graph['crosswalks'][0]['endpoints']['B']))
handle=next(o for o in bpy.data.collections['WB_GENERATED'].objects if o.get('wb_endpoint_id')=='endpoint-N-A');handle.location.y+=2
bpy.context.view_layer.objects.active=handle;handle.select_set(True)
try:bpy.ops.wb.rebuild();raise AssertionError('Uncaptured handle did not block regeneration')
except RuntimeError as error:assert 'Moved endpoint' in str(error)
assert bpy.ops.wb.capture_endpoint()=={'FINISHED'};assert bpy.ops.wb.rebuild()=={'FINISHED'}
a=model.loads(scene.wb_graph)['crosswalks'][0]['endpoints']['A'];assert a['mode']=='manual';assert abs(a['position'][1]-28)<1e-6
assert model.loads(scene.wb_graph)['crosswalks'][0]['endpoints']['B']==before_b
results['endpoint_handle']='uncaptured move rejected, captured override kept, far endpoint unchanged'
scene.wb_controls.radius_NW+=1;bpy.ops.wb.rebuild();assert model.loads(scene.wb_graph)['crosswalks'][0]['endpoints']['A']['position']==a['position'];results['corner_change']='manual endpoint retained'
curve=bpy.data.curves.new('WB_WORKFLOW_SOURCE','CURVE');curve.dimensions='3D';spline=curve.splines.new('POLY');spline.points.add(1);spline.points[0].co=(0,0,0,1);spline.points[1].co=(0,30,0,1);source=bpy.data.objects.new('WB_SOURCE_TEST',curve);scene.collection.objects.link(source);bpy.context.view_layer.objects.active=source
assert bpy.ops.wb.curve_profile()=={'FINISHED'};copy_obj=bpy.context.active_object;assert copy_obj is not source;assert copy_obj.data is not source.data;copy_obj.data.splines[0].points[0].radius=2;assert source.data.splines[0].points[0].radius==1
old_group=copy_obj.modifiers[0].node_group;bpy.context.view_layer.objects.active=source;assert bpy.ops.wb.curve_profile()=={'FINISHED'};assert copy_obj.modifiers[0].node_group==old_group;results['curve_copy']='independent source preserved; repeat command retains earlier groups'
Path=pathlib.Path;out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.write_text(json.dumps({'runtime':bpy.app.version_string,'results':results},indent=2));print('WB_WORKFLOW_TESTS_PASSED')
