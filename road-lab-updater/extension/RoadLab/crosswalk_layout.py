"""Crossings fitted to the finished pavement and tactile decals on concrete."""
import copy,bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def fit(road,plans):
    from .road_edges import boundary
    edges=boundary(road);output=list(plans)
    for direction in {m['role'][1] for m in plans if m['role'][0]=='crosswalk'}:
        stripes=[m for m in plans if m['role'][0]=='crosswalk' and m['role'][1]==direction]
        template=stripes[0];a,b=map(Vector,template['crosswalk_ends']);u=b-a;u.z=0;length=u.length
        if length<1e-6:continue
        u/=length;center=(a+b)*.5;hits=[]
        for p,q in edges:
            p,q=Vector(p),Vector(q);v=q-p
            cross=u.x*v.y-u.y*v.x
            if abs(cross)<1e-9:continue
            d=p-center;t=(d.x*v.y-d.y*v.x)/cross;s=(d.x*u.y-d.y*u.x)/cross
            if -1e-6<=s<=1+1e-6:hits.append((t,p+v*max(0.,min(1.,s)),v))
        lo=[h for h in hits if h[0]<-1e-5];hi=[h for h in hits if h[0]>1e-5]
        if not lo or not hi:continue
        left=max(lo,key=lambda h:h[0]);right=min(hi,key=lambda h:h[0]);a,b=left[1],right[1]
        # Preserve each endpoint's authored longitudinal setback; only extend
        # the crossing along its existing axis to the actual pavement edge.
        delta=b-a;length=delta.xy.length;u=Vector((delta.x/length,delta.y/length,0))
        width=.6096;period=1.2192;inset=.15;count=max(1,int((length-2*inset+period-width)/period));used=count*width+(count-1)*(period-width)
        output=[m for m in output if m not in stripes]
        for i in range(count):
            t=((length-used)/2+width/2+i*period)/length;mark=copy.deepcopy(template)
            mark.update(center=list(a.lerp(b,t)),forward=[u.y,-u.x],crosswalk_ends=[list(a),list(b)],role=['crosswalk',direction,i]);output.append(mark)
        for mark in output:
            if mark['role'][0]!='tactile' or mark['role'][1]!=direction:continue
            end,edge=(left if mark['role'][2]<0 else right)[1:];out=Vector((edge.y,-edge.x,0)).normalized()
            if out.dot(end-center)<0:out=-out
            mark['crosswalk_end']=list(end);mark['crosswalk_outward']=list(out)
            mark['forward']=list(out[:2]);mark['center']=list(end+out*.705)
    return output


def concrete(road):
    """Top triangles only: never project a pad onto a curb wall or slab bottom."""
    from .crosswalk_ramps import layers
    inverse=road.matrix_world.inverted();depsgraph=bpy.context.evaluated_depsgraph_get();triangles=[]
    for layer in layers(road):
        if layer.kind!='sidewalk':continue
        evaluated=layer.object.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles();matrix=inverse@evaluated.matrix_world;normal=matrix.to_3x3().inverted().transposed()
            points=[matrix@v.co for v in mesh.vertices]
            triangles.extend(tuple(points[i] for i in t.vertices) for t in mesh.loop_triangles if (normal@mesh.polygons[t.polygon_index].normal).z>.05)
        finally:evaluated.to_mesh_clear()
    points=[p for tri in triangles for p in tri]
    tree=BVHTree.FromPolygons([(p.x,p.y,0) for p in points],[(i,i+1,i+2) for i in range(0,len(points),3)],all_triangles=True) if points else None
    return triangles,tree


def place_pads(plans,tree,triangles):
    if tree is None:return
    for mark in plans:
        if mark['asset']!='tactile_pad' or 'crosswalk_end' not in mark:continue
        end=Vector(mark['crosswalk_end']);point=tree.find_nearest(Vector((end.x,end.y,0)))[0]
        if point is None:continue
        out=Vector(mark['crosswalk_outward']);right=Vector((out.y,-out.x,0));w,h=mark['size'];path=[]
        local=[[(p-end).dot(right) for p in tri] for tri in triangles]
        for i in range(17):
            station=w*(i/16-.5);intervals=[]
            for tri,stations in zip(triangles,local):
                if station<min(stations)-1e-7 or station>max(stations)+1e-7:continue
                hits=[]
                for a,b,sa,sb in zip(tri,tri[1:]+tri[:1],stations,stations[1:]+stations[:1]):
                    if abs(sb-sa)<1e-8:continue
                    if min(sa,sb)-1e-7<=station<=max(sa,sb)+1e-7:hits.append((a.lerp(b,(station-sa)/(sb-sa))-end).dot(out))
                if len(hits)>1 and max(hits)>=0:intervals.append(max(0.,min(hits)))
            if not intervals:break
            path.append(list(end+right*station+out*(min(intervals)+.08)))
        if len(path)==17:
            mark['pad_path']=path;mark['center']=list(Vector(path[8])+out*h/2)
        else:mark['center']=list(Vector((point.x,point.y,end.z))+out*(.08+h/2))


def decal(mark,triangles,project=None):
    """Clip each pad band to exact concrete planes; retain UVs across the curve."""
    center=Vector(mark['center']);f=Vector((*mark['forward'],0));r=Vector((f.y,-f.x,0));w,h=mark['size'];verts=[];faces=[];uv=[]
    path=[Vector(p) for p in mark.get('pad_path',[])]
    if not path:path=[center-r*w/2-f*h/2,center+r*w/2-f*h/2]
    for row,(a,b) in enumerate(zip(path,path[1:])):
        quad=[a,b,b+f*h,a+f*h];bounds=(min(p.x for p in quad),min(p.y for p in quad),max(p.x for p in quad),max(p.y for p in quad))
        sign=1 if (b-a).cross(f).z>=0 else -1
        for tri in triangles:
            if max(p.x for p in tri)<bounds[0] or min(p.x for p in tri)>bounds[2] or max(p.y for p in tri)<bounds[1] or min(p.y for p in tri)>bounds[3]:continue
            polygon=list(tri)
            for q,v in zip(quad,quad[1:]+quad[:1]):
                edge=v-q;axis=Vector((edge.y,-edge.x,0))*sign;clipped=[]
                for p,t in zip(polygon,polygon[1:]+polygon[:1]):
                    da=(p-q).dot(axis);db=(t-q).dot(axis)
                    if da<=1e-8:clipped.append(p)
                    if (da<0)!=(db<0):clipped.append(p.lerp(t,da/(da-db)))
                polygon=clipped
                if len(polygon)<3:break
            for i in range(1,len(polygon)-1):
                patch=(polygon[0],polygon[i],polygon[i+1])
                if abs((patch[1]-patch[0]).cross(patch[2]-patch[0]).z)<1e-10:continue
                if project is not None:
                    q=sum(patch,Vector())/3;hit=project(q.x,q.y,center.z,mark.get('on_terrain',False))
                    if hit is None or abs(hit[2]-q.z-.003)>.005:continue
                start=len(verts)
                for p in patch:
                    t=max(0.,min(1.,(p-a).dot(r)/max((b-a).dot(r),1e-9)));base=a.lerp(b,t)
                    verts.append((p.x,p.y,p.z+.003));uv.append(((row+t)/(len(path)-1),(p-base).dot(f)/h))
                faces.append((start,start+1,start+2))
    return verts,faces,uv
