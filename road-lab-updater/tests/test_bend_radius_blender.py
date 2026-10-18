"""A selected bend radius links both road edges without changing source points."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,point_settings as ps,selected_points
from RoadLab.native_extension import set_input
scene=bpy.context.scene;data=bpy.data.curves.new('Bend slider','CURVE');data.dimensions='3D';s=data.splines.new('POLY');s.points.add(2)
for p,co in zip(s.points,[(-80,0,.02,1),(0,0,.02,1),(0,80,.02,1)]):p.co=co
road=bpy.data.objects.new('Bend slider',data);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
for obj in bpy.context.selected_objects:obj.select_set(False)
road.select_set(True);bpy.context.view_layer.objects.active=road
for i,p in enumerate(road.data.splines[0].points):p.select=i==1
bpy.ops.object.mode_set(mode='EDIT');assert len(selected_points.bend_points(bpy.context))==1
source=[tuple(p.co) for p in ps.points(road)]
for radius in (8.,16.,10.):
 scene.roadlab_bend_radius=radius;road_core.flush_pending(force=True)
 assert abs(scene.roadlab_bend_radius-radius)<1e-5
 report=json.loads(road['roadlab_core_report']);corners=report['radius_limits']
 inner=next(c for c in corners if c.get('kind')=='interior');outer=next(c for c in corners if c.get('kind')=='exterior')
 assert abs(inner['applied']-(radius-4))<1e-4 and abs(outer['applied']-(radius+4))<1e-4,corners
 assert math.dist(inner['arc_center'],outer['arc_center'])<1e-4,'Bend edges are not concentric'
 assert source==[tuple(p.co) for p in ps.points(road)]
# A request beyond the available segment length remains editable/recoverable.
scene.roadlab_bend_radius=100.;road_core.flush_pending(force=True)
assert selected_points.bend_points(bpy.context)
scene.roadlab_bend_radius=10.;road_core.flush_pending(force=True)
assert 'bend_radius' not in ps.records(road)[0] and 'bend_radius' not in ps.records(road)[2]
# Moving the handle into another quadrant recomputes the corner labels.
bpy.ops.object.mode_set(mode='OBJECT');road.data.splines[0].points[2].co.y=-80;road_core.rebuild(road,True)
corners=json.loads(road['roadlab_core_report'])['radius_limits']
assert all(abs(c['requested']-(6 if c['kind']=='interior' else 14))<1e-4 for c in corners)
# Existing independent corner controls remain available and unlink the bend.
bpy.ops.object.mode_set(mode='EDIT');corner=corners[0]['corner'];bpy.ops.roadlab.point_corner(corner=corner,value=7.)
assert 'bend_radius' not in ps.records(road)[1]
bpy.ops.roadlab.point_reset(field='CORNERS');assert 'corners' not in ps.records(road)[1]
bpy.ops.object.mode_set(mode='OBJECT')
print('SELECTED_BEND_RADIUS_PASS',flush=True)
