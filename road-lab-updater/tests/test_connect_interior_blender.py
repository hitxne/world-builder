"""RoadLab F supports an interior road point without breaking its through street."""
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,point_settings as ps,lane_editor,road_connections
scene=bpy.context.scene;curve=bpy.data.curves.new('F branch','CURVE');curve.dimensions='3D'
for path in [[(-40,0,0),(0,0,0),(40,0,0)],[(0,40,0),(40,40,0)]]:
 spline=curve.splines.new('POLY');spline.points.add(len(path)-1)
 for p,co in zip(spline.points,path):p.co=(*co,1)
road=bpy.data.objects.new('F branch',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road)
road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=[dict(width=2.5,movement='THROUGH')],outgoing=[dict(width=2.5,movement='THROUGH')],median=0,spacing=18) for _,_,a,b in lane_editor.segments(road)])
before=lane_editor.state(road);bpy.ops.object.select_all(action='DESELECT');road.select_set(True);bpy.context.view_layer.objects.active=road;bpy.ops.object.mode_set(mode='EDIT')
for p in ps.points(road):p.select=False
road.data.splines[0].points[1].select=True;road.data.splines[1].points[-1].select=True
assert bpy.ops.roadlab.connect_points()=={'FINISHED'}
assert bpy.context.mode=='EDIT_CURVE' and len(road.data.splines)==3
assert all(c in lane_editor.state(road) for c in before)
assert tuple(road.data.splines[2].points[0].co[:3])==(0.,0.,0.)
assert tuple(road.data.splines[2].points[1].co[:3])==(40.,40.,0.)
assert len(road.data.splines[0].points)==3
assert road_connections._keymaps[0][1].type=='F'
bpy.ops.object.mode_set(mode='OBJECT');assert not road_connections.ROADLAB_OT_connect_points.poll(bpy.context)
print('INTERIOR_CONNECT_PASS',flush=True)
