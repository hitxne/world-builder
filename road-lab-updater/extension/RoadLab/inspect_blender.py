import bpy,json,sys,pathlib,time
scene,lib,out=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.open_mainfile(filepath=str(pathlib.Path(scene).resolve()))
for library in list(bpy.data.libraries):
 library.filepath=str(pathlib.Path(lib).resolve());library.reload()
report={'runtime':bpy.app.version_string,'libraries':[{'name':l.name,'filepath':l.filepath} for l in bpy.data.libraries],'groups':{},'objects':[]}
for g in bpy.data.node_groups:
 if g.name in ('ROAD','road_bool','|DJH_border_curve','TERRAIN_GEOMETRY','TERRAIN_SHAPE'):
  report['groups'][g.name]={'nodes':len(g.nodes),'links':len(g.links),'nested':[n.node_tree.name for n in g.nodes if n.type=='GROUP' and n.node_tree]}
for o in bpy.context.scene.objects:
 if o.type not in ('MESH','CURVE'):continue
 start=time.perf_counter();e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
 report['objects'].append({'name':o.name,'type':o.type,'modifiers':[{'name':x.name,'group':getattr(getattr(x,'node_group',None),'name',None)} for x in o.modifiers],'vertices':len(m.vertices) if m else None,'polygons':len(m.polygons) if m else None,'seconds':time.perf_counter()-start})
 e.to_mesh_clear()
report['images']=[{'name':x.name,'path':x.filepath,'packed':bool(x.packed_file)} for x in bpy.data.images]
pathlib.Path(out).write_text(json.dumps(report,indent=2));print('WB_INSPECT_DONE')
