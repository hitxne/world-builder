"""Panel frame continuity, bounded end caps, persistent point data and one paint pass."""
import bpy,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,native_layers,point_settings as ps,selected_points
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion
scene=bpy.context.scene;data=bpy.data.curves.new('Straight frame test','CURVE');data.dimensions='3D';s=data.splines.new('POLY');s.points.add(1)
for p,co in zip(s.points,[(0,0,.02),(30,0,.02)]):p.co=(*co,1)
road=bpy.data.objects.new('Straight frame test',data);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
add_extrusion(scene,road,'curb');sidewalk,_=add_extrusion(scene,road,'sidewalk');bpy.context.view_layer.update()
ev=sidewalk.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
try:
 assert len(mesh.vertices)>0
 outer=.32+.003+2.2
 assert all(-outer-.002<=v.co.x<=30+outer+.002 and abs(v.co.y)<=4+outer+.002 for v in mesh.vertices),'A road-end panel protrudes beyond its analytical offset bounds'
 assert all(abs(v.co.z-.1724)<1e-5 or abs(v.co.z+.0276)<1e-5 for v in mesh.vertices),'A panel frame has inverted its profile height'
 tops=[p for p in mesh.polygons if all(abs(mesh.vertices[i].co.z-.1724)<1e-5 for i in p.vertices)]
 assert tops and all(p.normal.z>.99 for p in tops),'A panel top has flipped normals'
 print('ROAD_END_BOUNDS_PASS',tuple(min(v.co[i] for v in mesh.vertices) for i in range(3)),tuple(max(v.co[i] for v in mesh.vertices) for i in range(3)),flush=True)
finally:ev.to_mesh_clear()
road.data.splines[0].points[1].co=(30,30,.02,1);road_core.rebuild(road,True);bpy.context.view_layer.update()
ev=sidewalk.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
try:
 length=math.sqrt(1800);outer=.32+.003+2.2
 for v in mesh.vertices:
  along=(v.co.x+v.co.y)/math.sqrt(2);across=(-v.co.x+v.co.y)/math.sqrt(2)
  assert -outer-.002<=along<=length+outer+.002 and abs(across)<=4+outer+.002,'Rotated road-end panel has a spike'
finally:ev.to_mesh_clear()
model=native_layers.model_for(road);layer=next(l for l in model.wb_layers if l.kind=='sidewalk');name=native_layers.prefix(layer)+'width';native_layers.write(model,name,[3.1,2.2]);native_layers.refresh_stack(model)
road.data.splines[0].points[0].co.y=.5;native_layers.sync_model(model)
assert all(abs(a-b)<1e-5 for a,b in zip(native_layers.read(model,name),[3.1,2.2])),'Moving a control point reset its layer width'
print('POINT_FIELDS_PRESERVED_PASS',flush=True)
bpy.ops.roadlab.load_example();road=bpy.context.scene.wb_native.road;calls=[];original=road_core._refresh_markings_now
try:
 def counted(obj):calls.append(obj);return original(obj)
 road_core._refresh_markings_now=counted
 road.data.splines[0].points[0].co.y+=.1
 selected_points.notify(bpy.context,road)
finally:road_core._refresh_markings_now=original
assert calls.count(road)==1,('Markings rebuilt repeatedly in one edit',len(calls))
assert not road.get('roadlab_core_error')
print('SINGLE_EDIT_MARKING_PASS',flush=True)
