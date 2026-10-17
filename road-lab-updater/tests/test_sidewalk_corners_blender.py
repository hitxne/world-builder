"""Tight sidewalks must not reverse winding, self-cross or overlap at corners."""
import bpy,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,native_layers
from RoadLab.native_extension import set_input
from RoadLab.native_extrusion import add_extrusion

def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def area(poly):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))*.5

def overlap(a,b):
    poly=list(a)
    if cross(*b)<0:b=list(reversed(b))
    for p,q in zip(b,b[1:]+b[:1]):
        out=[]
        for u,v in zip(poly,poly[1:]+poly[:1]):
            cu,cv=cross(p,q,u),cross(p,q,v)
            if cu>=0:out.append(u)
            if (cu>0 and cv<0) or (cu<0 and cv>0):
                t=cu/(cu-cv);out.append((u[0]+t*(v[0]-u[0]),u[1]+t*(v[1]-u[1])))
        poly=out
        if not poly:return 0.
    return area(poly)

def check(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    try:
        top={f.index for f in mesh.polygons if all(abs(mesh.vertices[i].co.z-.1724)<1e-4 for i in f.vertices)}
        assert top
        for i in top:
            f=mesh.polygons[i];assert f.normal.z>.99, ('Inverted concrete top',i,tuple(f.center))
            ps=[tuple(mesh.vertices[j].co[:2]) for j in f.vertices]
            for a in range(len(ps)):
                for b in range(a+2,len(ps)):
                    if a==0 and b==len(ps)-1:continue
                    p,q=ps[a],ps[(a+1)%len(ps)];u,v=ps[b],ps[(b+1)%len(ps)]
                    assert not (cross(p,q,u)*cross(p,q,v)<-1e-12 and cross(u,v,p)*cross(u,v,q)<-1e-12), ('Self-crossing slab',i,ps,p,q,u,v)
        mesh.calc_loop_triangles();triangles=[];grid={};pairs=set()
        for tri in mesh.loop_triangles:
            if tri.polygon_index not in top:continue
            ps=[tuple(mesh.vertices[i].co[:2]) for i in tri.vertices]
            if area(ps)<1e-9:continue
            index=len(triangles);triangles.append(ps)
            lo=[math.floor(min(p[k] for p in ps)/4) for k in (0,1)];hi=[math.floor(max(p[k] for p in ps)/4) for k in (0,1)]
            for x in range(lo[0],hi[0]+1):
                for y in range(lo[1],hi[1]+1):
                    bucket=grid.setdefault((x,y),[])
                    for other in bucket:
                        key=(other,index)
                        if key in pairs:continue
                        pairs.add(key);shared=overlap(triangles[other],ps)
                        assert shared<1e-6, ('Overlapping slabs',other,index,shared)
                    bucket.append(index)
    finally:evaluated.to_mesh_clear()

scene=bpy.context.scene;data=bpy.data.curves.new('Corner test','CURVE');data.dimensions='3D'
s=data.splines.new('POLY');s.points.add(2)
for p,co in zip(s.points,[(-40,0,.02,1),(0,0,.02,1),(0,40,.02,1)]):p.co=co
road=bpy.data.objects.new('Corner test',data);scene.collection.objects.link(road);scene.wb_native.road=road
road_core.attach(road);set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
add_extrusion(scene,road,'curb');sidewalk,_=add_extrusion(scene,road,'sidewalk')
layer=next(l for l in native_layers.model_for(road).wb_layers if l.object==sidewalk)
for angle,spacing,width in [(45,1,3.2),(90,1,3.2),(135,1,3.2),(90,.5,3.2),(90,2,3.2),(90,1,2.2),(90,1,4),(90,1,6),(90,1,10)]:
    t=math.radians(angle);s.points[2].co=(40*math.cos(t),40*math.sin(t),.02,1)
    set_input(road_core.modifier(road),'resolution',spacing);road_core.rebuild(road,True);layer.width=width
    bpy.context.view_layer.update()
    for stage in ('raw','full'):
        for name in ('RoadLab Planar Slabs','RoadLab Surface Finish'):sidewalk.modifiers[name].show_viewport=stage=='full'
        bpy.context.view_layer.update();check(sidewalk)
    print('SIDEWALK_CORNER_CASE_PASS',angle,spacing,width,flush=True)
# The four-way example has separate splines, crosswalk ramps and dense profiles.
# Exercise all cleanup paths; manifold edges alone do not detect folded tops.
bpy.ops.roadlab.load_example()
road=bpy.context.scene.wb_native.road
sidewalk=next(l.object for l in native_layers.model_for(road).wb_layers if l.kind=='sidewalk')
for stage in ('raw','fast','precise'):
    for name in ('RoadLab Planar Slabs','RoadLab Surface Finish'):sidewalk.modifiers[name].show_viewport=stage!='raw'
    set_input(sidewalk.modifiers[0],'Precise viewport cleanup',stage=='precise')
    bpy.context.view_layer.update();check(sidewalk)
    print('SIDEWALK_JUNCTION_CASE_PASS',stage,flush=True)
print('SIDEWALK_CORNERS_PASS',flush=True)
