"""Benchmark wrappers around installed TrackTools helpers; no commercial groups are copied."""
import bpy,sys,pathlib,time,statistics,json,os
root=pathlib.Path(__file__).parent;sys.path.insert(0,str(root if (root/'WB_TrackTools').exists() else root.parent));from WB_TrackTools import native_extension as ext
startup=os.environ.get('WB_TRACKTOOLS_STARTUP',str(root/'tt_originals/TT_startup_scene_01(2).blend'));nodes=os.environ.get('WB_TRACKTOOLS_NODES',str(root/'tt_originals/TT_NodeGroups(3).blend'));report={}
for method in ('generic','native_even_thickness'):
 bpy.ops.wm.open_mainfile(filepath=startup)
 for lib in bpy.data.libraries:lib.filepath=nodes;lib.reload()
 road=ext.native_roads(bpy.context.scene)[0]
 curve=bpy.data.curves.new('WB_Research_Corner','CURVE');curve.dimensions='3D';s=curve.splines.new('POLY');s.points.add(2)
 for p,co in zip(s.points,[(0,0,1.5),(0,30,1.5),(12,38,1.5)]):p.co=(*co,1)
 road.data=curve
 profiledata=bpy.data.curves.new('WB_Research_Profile','CURVE');profiledata.dimensions='2D';profiledata.fill_mode='NONE';sp=profiledata.splines.new('POLY');sp.points.add(3);sp.use_cyclic_u=True
 for p,co in zip(sp.points,[(0,-.1524),(2.2,-.1524),(2.2,-.0524),(0,-.0524)]):p.co=(*co,0,1)
 profile=bpy.data.objects.new('WB_Research_Profile',profiledata);bpy.context.scene.collection.objects.link(profile);profile.hide_render=True;profile.hide_set(True)
 obj=bpy.data.objects.new('WB_Research_Sidewalk',bpy.data.meshes.new('WB_Research_Sidewalk'));bpy.context.scene.collection.objects.link(obj)
 g=bpy.data.node_groups.new('WB_Research_'+method,'GeometryNodeTree');ext.socket(g,'Geometry','INPUT','NodeSocketGeometry');ext.socket(g,'Geometry','OUTPUT','NodeSocketGeometry');N=g.nodes;L=g.links
 info=N.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=road
 tag=N.new('GeometryNodeInputNamedAttribute');tag.data_type='INT';tag.inputs['Name'].default_value='parts';eq=N.new('FunctionNodeCompare');eq.data_type='INT';eq.operation='EQUAL';eq.inputs[3].default_value=7;L.new(tag.outputs['Attribute'],eq.inputs[2])
 select=N.new('GeometryNodeSeparateGeometry');select.domain='POINT';L.new(info.outputs['Geometry'],select.inputs['Geometry']);L.new(eq.outputs['Result'],select.inputs['Selection'])
 pi=N.new('GeometryNodeObjectInfo');pi.transform_space='ORIGINAL';pi.inputs['Object'].default_value=profile
 if method=='native_even_thickness':
  helper=bpy.data.node_groups.get('Curve-To-Mesh Even-Thickness');assert helper
  sweep=N.new('GeometryNodeGroup');sweep.node_tree=helper;sweep.inputs['Even-Thickness'].default_value=True;sweep.inputs['curve radius'].default_value=1.;output=sweep.outputs['Geometry']
 else:
  sweep=N.new('GeometryNodeCurveToMesh');output=sweep.outputs['Mesh']
 sweep.inputs['Fill Caps'].default_value=True;L.new(select.outputs['Selection'],sweep.inputs['Curve']);L.new(pi.outputs['Geometry'],sweep.inputs['Profile Curve']);out=N.new('NodeGroupOutput');L.new(output,out.inputs['Geometry'])
 mod=obj.modifiers.new('WB research sweep','NODES');mod.node_group=g;bpy.context.view_layer.update();samples=[]
 for i in range(5):
  road.data.splines[0].points[-1].co.x+=.01;road.data.update_tag();road.update_tag();start=time.perf_counter();bpy.context.view_layer.update();samples.append(time.perf_counter()-start)
 e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh();assert len(mesh.polygons)>0;report[method]={'median_update_seconds':statistics.median(samples),'samples':samples,'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'native_terrain_enabled':True,'terrain_observes_research_sidewalk':False,'extra_wb_mesh_booleans':0};e.to_mesh_clear();print('CURVE_HELPER_BENCH',method,report[method],flush=True)
report['scope']='Isolated curve-helper prototype only; per-vertex layer controls, terrain contacts and junction clipping are not integrated. Native terrain remains enabled with its original road-only targets. Not a production replacement or large-network performance claim.'
(root/'native_curve_helper_research.json').write_text(json.dumps(report,indent=2));print('CURVE_HELPER_RESEARCH_PASS',flush=True)
