"""Width insertion preserves point settings and shared height sampling stays exact."""
import bpy,sys,math,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_authoring,road_core,point_settings,road_heightfield as field
scene=bpy.context.scene
curve=bpy.data.curves.new('Width test','CURVE');curve.dimensions='3D'
for y in (0,100):
 s=curve.splines.new('POLY');s.points.add(1)
 for p,co in zip(s.points,[(-30,y,.02,1),(30,y,.02,1)]):p.co=co
road=bpy.data.objects.new('Width test',curve);scene.collection.objects.link(road)
scene.wb_native.road=road;road_core.attach(road)
items=point_settings.sync(road)
for item,width in zip(items,[6,10,8,12]):item['width']=width
point_settings.save(road,items);saved={item['id']:dict(item) for item in items}
road_authoring.widen(road,(0,0),10,2,.1)
items=point_settings.records(road);ps=point_settings.points(road)
assert len(ps)>4
for item,p in zip(items,ps):
 if item['id'] in saved:assert item['width']==saved[item['id']]['width']
 if abs(p.co.y)<1e-5 and abs(p.co.x)<10:
  initial=6+(p.co.x+30)/60*4;t=abs(p.co.x)/10
  assert abs(item['width']-(initial+.2*(1-t*t)**2))<1e-5,(p.co[:],item['width'],initial)
count=len(ps);road_authoring.widen(road,(0,0),10,2,.1)
assert len(point_settings.points(road))==count, 'Repeated width stamp kept inserting points'
road_core.rebuild(road,True)
random.seed(7);values={(x,y):random.uniform(-4,4) for x in range(-4,5) for y in range(-4,5)}
for _ in range(300):
 x,y=random.uniform(-5,5),random.uniform(-5,5);a,b=math.floor(x),math.floor(y);u,v=x-a,y-b
 expected=sum(values.get((a+i,b+j),0.)*(u if i else 1-u)*(v if j else 1-v) for i in (0,1) for j in (0,1))
 assert abs(field.sample(values,x,y)-expected)<1e-12
print('SCULPT_TOOLS_PASS',flush=True)

from RoadLab import road_draw_preview
road_draw_preview.remember(road,6.)
assert road_draw_preview.ribbons(road)==[]
spline=road.data.splines[0];spline.points.add(1);spline.points[-1].co=(45,0,.02,1)
preview=road_draw_preview.ribbons(road)
assert len(preview)==1, len(preview)
assert abs(max(p[1] for p in preview[0])-min(p[1] for p in preview[0])-10)<1e-5
assert all(p[0]>=29.99 for p in preview[0]), 'Extension preview rebuilt untouched streets'
spline.points[-1].co=(45,20,3,1)
assert len(road_draw_preview.ribbons(road))==1
road_core.rebuild(road,True)
assert road_draw_preview.ribbons(road)==[]
print('ROAD_EXTENSION_PREVIEW_PASS',flush=True)
