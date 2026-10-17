"""Parking bounds lower curb/sidewalk crossings symmetrically and restore cleanly."""
import bpy,sys,tempfile
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,native_layers,surface_bounds as bounds,parking_entrances
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion
scene=bpy.context.scene
curve=bpy.data.curves.new('Entrance road','CURVE');curve.dimensions='3D';s=curve.splines.new('POLY');s.points.add(1)
for p,co in zip(s.points,[(0,-40,.02,1),(0,40,.02,1)]):p.co=co
road=bpy.data.objects.new('Entrance road',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
add_extrusion(scene,road,'curb');sidewalk,_=add_extrusion(scene,road,'sidewalk')
next(l for l in native_layers.model_for(road).wb_layers if l.object==sidewalk).width=3.2

def tree(obj):
 bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 try:return BVHTree.FromPolygons([ev.matrix_world@v.co for v in mesh.vertices],[tuple(f.vertices) for f in mesh.polygons])
 finally:ev.to_mesh_clear()
def height(t,x,y):
 p=t.ray_cast(Vector((x,y,20)),Vector((0,0,-1)),40)[0];assert p is not None,(x,y);return p.z
lot=bounds.create_surface(bpy.context,[(2,-3,0),(18,-3,0),(18,3,0),(2,3,0)],'PARKING');lot.roadlab_surface.radius=0
parking_entrances.sync_scene(scene);t=tree(sidewalk)
assert height(t,5,0)<.06
for d in (.5,1,1.5,2,2.5,3.5):
 a=height(t,5,-3-d);b=height(t,5,3+d);assert abs(a-b)<.004,(d,a,b)
assert height(t,5,7)>.16
curb=next(l.object for l in native_layers.model_for(road).wb_layers if l.kind=='curb');assert height(tree(curb),4.15,0)<.06
# Shared source mesh + transform constraint makes edits live, without copying it.
guide=lot['roadlab_entrance_guide'];assert guide.data==lot.data
lot.location.y=12;t=tree(sidewalk);assert height(t,5,0)>.16 and height(t,5,12)<.06
for v in lot.data.vertices:v.co.y+=3
lot.data.update();t=tree(sidewalk);assert height(t,5,15)<.06 and height(t,5,7)>.16
lot.roadlab_surface.entrances=False;t=tree(sidewalk);assert height(t,5,15)>.16
lot.roadlab_surface.entrances=True;assert height(tree(sidewalk),5,15)<.06
# Saving/reopening restores bindings and avoids circular evaluated dependencies.
with tempfile.TemporaryDirectory() as tmp:
 name=lot.name;rn=road.name;sn=sidewalk.name
 bpy.ops.wm.save_as_mainfile(filepath=str(Path(tmp)/'driveway.blend'));bpy.ops.wm.open_mainfile(filepath=str(Path(tmp)/'driveway.blend'))
 lot=bpy.data.objects[name];road=bpy.data.objects[rn];sidewalk=bpy.data.objects[sn]
 assert height(tree(sidewalk),5,15)<.06
 bpy.data.objects.remove(lot,do_unlink=True);parking_entrances.sync_scene(bpy.context.scene)
 assert height(tree(sidewalk),5,15)>.16
 assert not any(o.get('roadlab_parking_guide') for o in bpy.context.scene.objects)
print('PARKING_ENTRANCES_PASS',flush=True)
