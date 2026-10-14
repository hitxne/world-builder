"""Exact affine clearance over XY triangle overlaps, with spatial broad phase."""
import math
import hashlib,json

def signature(vertices,triangles,config):
    surfaces=sorted(tuple(sorted(tuple(round(float(v),5) for v in vertices[i]) for i in t)) for t in triangles)
    return hashlib.sha256(json.dumps([surfaces,config['bounds'],config['blend_distance'],config.get('clearance',.025)],separators=(',',':')).encode()).hexdigest()

def plane(a,b,c):
    dx,dy=b[0]-a[0],b[1]-a[1];ex,ey=c[0]-a[0],c[1]-a[1];den=dx*ey-dy*ex
    if abs(den)<1e-12:return None
    x=((b[2]-a[2])*ey-(c[2]-a[2])*dy)/den
    y=(dx*(c[2]-a[2])-ex*(b[2]-a[2]))/den
    return x,y,a[2]-x*a[0]-y*a[1]

def clip(subject,triangle):
    result=list(subject)
    for a,b in zip(triangle,triangle[1:]+triangle[:1]):
        if not result:break
        previous=result[-1];out=[]
        def side(p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        old=side(previous)
        for p in result:
            value=side(p)
            if (value>=0)!=(old>=0):
                u=old/(old-value);out.append((previous[0]+u*(p[0]-previous[0]),previous[1]+u*(p[1]-previous[1])))
            if value>=0:out.append(p)
            previous=p;old=value
        result=out
    return result

def area(points):return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2

class SurfaceIndex:
    def __init__(self,vertices,triangles,cell=4.):
        self.cell=cell;self.cells={};self.surfaces=[]
        for indices in triangles:
            points=[tuple(vertices[i]) for i in indices];eq=plane(*points)
            if eq is None:continue
            xy=[p[:2] for p in points]
            if (xy[1][0]-xy[0][0])*(xy[2][1]-xy[0][1])-(xy[1][1]-xy[0][1])*(xy[2][0]-xy[0][0])<0:xy.reverse()
            bounds=(min(p[0] for p in xy),max(p[0] for p in xy),min(p[1] for p in xy),max(p[1] for p in xy));index=len(self.surfaces);self.surfaces.append((xy,eq,bounds))
            for key in self.keys(bounds):self.cells.setdefault(key,[]).append(index)
    def keys(self,bounds):
        xmin,xmax,ymin,ymax=bounds
        for x in range(math.floor(xmin/self.cell),math.floor(xmax/self.cell)+1):
            for y in range(math.floor(ymin/self.cell),math.floor(ymax/self.cell)+1):yield x,y
    def overlaps(self,points):
        xy=[tuple(p[:2]) for p in points];bounds=(min(p[0] for p in xy),max(p[0] for p in xy),min(p[1] for p in xy),max(p[1] for p in xy));candidates=set()
        for key in self.keys(bounds):candidates.update(self.cells.get(key,()))
        for i in sorted(candidates):
            triangle,eq,b=self.surfaces[i]
            if b[0]>bounds[1] or b[1]<bounds[0] or b[2]>bounds[3] or b[3]<bounds[2]:continue
            polygon=clip(xy,triangle)
            if len(polygon)>=3 and area(polygon)>1e-10:yield polygon,eq

def enforce(vertices,faces,index,clearance=.025):
    result=[list(p) for p in vertices];protected=set();corrected=set();worst=0.;checks=0
    for face in faces:
        points=[result[i] for i in face]
        for overlap,road in index.overlaps(points):
            protected.update(face);checks+=1;terrain=plane(*(result[i] for i in face))
            delta=tuple(terrain[i]-road[i] for i in range(3))
            excess=max(delta[0]*x+delta[1]*y+delta[2]+clearance+2e-5 for x,y in overlap)
            if excess>0:
                worst=max(worst,excess);corrected.update(face)
                for i in face:result[i][2]-=excess
    ceilings=[p[2] if i in protected else 1e20 for i,p in enumerate(result)]
    return result,ceilings,{'face_overlap_checks':checks,'protected_vertices':len(protected),'lowered_vertices':len(corrected),'maximum_local_correction_m':worst}

def measure(vertices,faces,index,clearance=.025):
    worst=-float('inf');violations=0;checks=0
    for face in faces:
        points=[vertices[i] for i in face];terrain=plane(*points)
        for overlap,road in index.overlaps(points):
            checks+=1;delta=tuple(terrain[i]-road[i] for i in range(3));excess=max(delta[0]*x+delta[1]*y+delta[2]+clearance for x,y in overlap)
            worst=max(worst,excess)
            if excess>1e-6:violations+=1
    return {'overlap_checks':checks,'violating_overlaps':violations,'maximum_clearance_excess_m':worst if checks else 0}
