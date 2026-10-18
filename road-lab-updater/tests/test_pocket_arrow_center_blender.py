"""The full pocket arrow is centered between lane boundaries."""
import sys,bpy,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_editor,lane_add,lane_markings,point_settings as ps,lane_pockets
from RoadLab.native_extension import set_input
from mathutils import Vector
scene=bpy.context.scene;curve=bpy.data.curves.new('Arrow placement','CURVE');curve.dimensions='3D'
for coords in [[(-120,0,.02),(0,0,.02),(120,0,.02)],[(0,-120,.02),(0,0,.02),(0,120,.02)]]:
 s=curve.splines.new('POLY');s.points.add(2)
 for p,co in zip(s.points,coords):p.co=(*co,1)
road=bpy.data.objects.new('Arrow placement',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
rows=ps.records(road)
for traffic_side in ('RIGHT','LEFT'):
 scene.roadlab_map_settings.traffic_side=traffic_side
 for arm in (-1,1):
  for side in (-1,1):
   road['roadlab_lane_pockets']='[]';road['roadlab_lanes']='[]'
   choice=dict(spline=0,anchors=[rows[1]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=arm)
   pockets,pocket,_=lane_add.proposal(road,choice,side,3.5,24,15)
   lane_add.ensure_baseline(road,pocket,traffic_side);road['roadlab_lane_pockets']=json.dumps(pockets);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
   plans=json.loads(road['roadlab_generated_marking_catalog']);arrows=[m for m in plans if m['role'][0]=='pocket-arrow'];assert len(arrows)==1
   mark=arrows[0]
   forward=Vector((*mark['forward'],0));right=Vector((forward.y,-forward.x,0));center=Vector(mark['center'])
   dividers=[m for m in plans if m['role'][0]=='pocket-divider' and m['role'][2]==1];assert len(dividers)==1
   divider=dividers[0];lateral=divider['path'][0][1];expected=lateral+side*pocket['width']/2
   assert abs(center.y-expected)<1e-5,(traffic_side,arm,side,center.y,expected)
   # Both lateral edges of the full decal stay within this lane's paint margin.
   limits=sorted((lateral,lateral+side*pocket['width']))
   for edge in (-.5,.5):
    p=center+right*edge*mark['size'][0];assert limits[0]+.149<=p.y<=limits[1]-.149,(limits,p)
   # A turn-only addition must leave the opposite street at its original width.
   vertices=[v.co for v in road['roadlab_core_mesh'].data.vertices if 25<(-arm)*v.co.x<100]
   assert vertices and abs(max(v.y for v in vertices)-4)<1e-5 and abs(min(v.y for v in vertices)+4)<1e-5,(traffic_side,arm,side,'opposite widened')
   print('CENTERED_ARROW',traffic_side,arm,side,mark['asset'],flush=True)
# Both through purposes create a genuine receiving lane; right-only does not.
scene.roadlab_map_settings.traffic_side='RIGHT'
for movement,count in [('TURN',1),('THROUGH',2),('RIGHT_THROUGH',2)]:
 road['roadlab_lane_pockets']='[]';road['roadlab_lanes']='[]'
 choice=dict(spline=0,anchors=[rows[1]['id']],axis=[rows[0]['id'],rows[1]['id']],junction=True,junction_direction=-1)
 pockets,pocket,_=lane_add.proposal(road,choice,-1,3.5,24,15)
 pockets,pocket=lane_add.with_receiving_lane(road,pockets,pocket,movement,45,'RIGHT');assert len(pockets)==count
 lane_add.validate_turn(road,pocket,'RIGHT')
 for part in pockets:lane_add.ensure_baseline(road,part,'RIGHT')
 road['roadlab_lane_pockets']=json.dumps(pockets);road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
 vertices=[v.co for v in road['roadlab_core_mesh'].data.vertices if 18<v.co.x<24]
 assert vertices
 if movement=='TURN':assert min(v.y for v in vertices)>-4.001
 else:assert min(v.y for v in vertices)<-7.49
 if movement=='RIGHT_THROUGH':
  marks=json.loads(road['roadlab_generated_marking_catalog']);assert any(m['role'][0]=='pocket-arrow' and m['asset']=='arrow_right_through' for m in marks)
print('POCKET_ARROW_CENTER_PASS',flush=True)
