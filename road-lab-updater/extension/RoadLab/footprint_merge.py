"""Local planar footprint unions using Blender CDT; no solid mesh Booleans."""
import math
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from mathutils.kdtree import KDTree
from .surface_network import area,inside,distance,perimeter,cross,cached


def outline(piece):
    vertices,faces,_=piece
    faces=[list(f) if area([vertices[i][:2] for i in f])>0 else list(reversed(f)) for f in faces]
    loops=perimeter(vertices,faces)
    return [[Vector(vertices[i][:2]) for i in loop] for loop in loops]


def coverage(p,loops):
    return sum((1 if area(loop)>0 else -1) for loop in loops if inside(p,loop))


def overlaps(a,b):
    for loop in a:
        for p,q in zip(loop,loop[1:]+loop[:1]):
            for other in b:
                for r,s in zip(other,other[1:]+other[:1]):
                    u=q-p;v=s-r;den=cross(u,v)
                    if abs(den)>1e-9:
                        t=cross(r-p,v)/den;h=cross(r-p,u)/den
                        if 1e-6<t<1-1e-6 and 1e-6<h<1-1e-6:return True
    # Interior probes distinguish real area overlap from a shared gate seam.
    for first,second in ((a,b),(b,a)):
        edges=[(p,q) for loop in second for p,q in zip(loop,loop[1:]+loop[:1])]
        for loop in first:
            for p,q in zip(loop,loop[1:]+loop[:1]):
                d=q-p
                if d.length<1e-8:continue
                probe=(p+q)*.5+Vector((-d.y,d.x)).normalized()*1e-4
                if coverage(probe,first)>0 and coverage(probe,second)>0 and min(distance(probe,r,s) for r,s in edges)>1e-6:return True
    return False


def union_mesh(pieces,spacing):
    points=[];polygons=[];signs=[];height=pieces[0][0][0][2]
    for piece in pieces:
        for loop in outline(piece):
            polygon=list(range(len(points),len(points)+len(loop)));points.extend(loop);polygons.append(polygon);signs.append(1 if area(loop)>0 else -1)
    if len(points)>150000:raise ValueError('Merged region exceeds its sampling budget')
    first=delaunay_2d_cdt(points,[],[f if s>0 else list(reversed(f)) for f,s in zip(polygons,signs)],1,1e-6,True)
    owned=[list(f) for f,owners in zip(first[2],first[5]) if sum(signs[i] for i in owners)>0]
    first_vertices=[(p.x,p.y,height) for p in first[0]]
    loops=perimeter(first_vertices,owned)
    boundary=[];contours=[];contour_signs=[]
    for loop in loops:
        contour=list(range(len(boundary),len(boundary)+len(loop)));contours.append(contour)
        poly=[]
        for i in loop:
            p=Vector(first_vertices[i][:2])
            if not poly or (p-poly[-1]).length>1e-4:poly.append(p)
        if len(poly)>1 and (poly[0]-poly[-1]).length<=1e-4:poly.pop()
        # Near-coincident input edges can leave an out-and-back numerical
        # whisker. Collapse it before triangulating the exposed contour.
        changed=True
        while changed and len(poly)>3:
            changed=False
            for j,b in enumerate(poly):
                a=poly[j-1];c=poly[(j+1)%len(poly)];u=b-a;v=c-b
                if u.dot(v)<0 and abs(cross(u,v))/max(u.length,v.length,1e-12)<1e-4:
                    poly.pop(j);changed=True;break
        if len(poly)<3 or abs(area(poly))<1e-5:
            contours.pop();continue
        contours[-1]=list(range(len(boundary),len(boundary)+len(poly)))
        boundary.extend(poly);contour_signs.append(1 if area(poly)>0 else -1)
    segments=[(boundary[a],boundary[b]) for f in contours for a,b in zip(f,f[1:]+f[:1])]
    vertices=boundary[:];seen={tuple(round(x,6) for x in p) for p in vertices}
    # Discard internal constraints and overlapping sample grids. A single
    # uniformly spaced interior grid avoids clusters of near-duplicate points
    # and the needle triangles they would otherwise create after a union.
    xmin=min(p.x for p in boundary);xmax=max(p.x for p in boundary);ymin=min(p.y for p in boundary);ymax=max(p.y for p in boundary)
    if (xmax-xmin)*(ymax-ymin)/spacing**2>150000:raise ValueError('Merged region exceeds its sampling budget')
    nearest=KDTree(len(segments))
    for i,(a,b) in enumerate(segments):nearest.insert(Vector(((a.x+b.x)*.5,(a.y+b.y)*.5,0)),i)
    nearest.balance()
    for x in range(math.floor(xmin/spacing),math.ceil(xmax/spacing)+1):
        for y in range(math.floor(ymin/spacing),math.ceil(ymax/spacing)+1):
            p=Vector((x*spacing,y*spacing));k=tuple(round(v,6) for v in p)
            if k in seen:continue
            if sum(sign for f,sign in zip(contours,contour_signs) if inside(p,[boundary[i] for i in f]))<=0:continue
            indices=[i for _,i,_ in nearest.find_n(Vector((p.x,p.y,0)),min(12,len(segments)))]
            if min(distance(p,*segments[i]) for i in indices)<spacing*.28:continue
            seen.add(k);vertices.append(p)
    tri=delaunay_2d_cdt(vertices,[],[f if s>0 else list(reversed(f)) for f,s in zip(contours,contour_signs)],1,1e-6,True)
    faces=[list(f) for f,owners in zip(tri[2],tri[5]) if sum(contour_signs[i] for i in owners)>0]
    expected=sum(area([boundary[i] for i in f]) for f in contours);actual=sum(abs(area([tri[0][i] for i in f])) for f in faces)
    if abs(expected-actual)>max(1e-4,expected*1e-6):raise ValueError('Merged region could not be triangulated safely')
    used=sorted({i for f in faces for i in f});ids={old:new for new,old in enumerate(used)}
    result=[(tri[0][i].x,tri[0][i].y,height) for i in used]
    faces=[[ids[i] for i in f] for f in faces]
    perimeter(result,faces)
    return result,faces,0


def merge_overlaps(pieces,spacing,stats):
    # Broad phase by patch bounds; only overlapping planar patches are grouped.
    flat=[i for i,p in enumerate(pieces) if max(v[2] for v in p[0])-min(v[2] for v in p[0])<1e-5]
    bounds={i:(min(v[0] for v in pieces[i][0]),max(v[0] for v in pieces[i][0]),min(v[1] for v in pieces[i][0]),max(v[1] for v in pieces[i][0])) for i in flat}
    parent=list(range(len(pieces)));outlines={};pairs=0
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for position,i in enumerate(flat):
        a=bounds[i]
        for j in flat[:position]:
            b=bounds[j]
            if min(a[1],b[1])-max(a[0],b[0])<1e-6 or min(a[3],b[3])-max(a[2],b[2])<1e-6:continue
            if abs(pieces[i][0][0][2]-pieces[j][0][0][2])>1e-5:continue
            if i not in outlines:outlines[i]=outline(pieces[i])
            if j not in outlines:outlines[j]=outline(pieces[j])
            if overlaps(outlines[i],outlines[j]):parent[find(i)]=find(j);pairs+=1
    groups={}
    for i,piece in enumerate(pieces):groups.setdefault(find(i),[]).append(i)
    output=[];merged=0
    for indices in groups.values():
        if len(indices)==1:output.append(pieces[indices[0]]);continue
        selected=[pieces[i] for i in indices]
        key=('merged footprint',spacing,tuple((tuple(vs),tuple(tuple(f) for f in fs)) for vs,fs,_ in selected))
        output.append(cached(key,lambda selected=selected:union_mesh(selected,spacing),stats));merged+=1
    return output,dict(merged_regions=merged,overlap_pairs_resolved=pairs)


def merged_junction(center,neighbors,edges,spacing,radii):
    """A short/acute junction expands into a union of its adjoining footprints.
    Circles that fit remain true-radius geometry; fully covered corners retain
    their setting but explicitly have no exposed arc.
    """
    from .surface_network import intersection,edge_width
    if any(isinstance(edges[tuple(sorted((center,p)))],tuple) for p in neighbors):raise ValueError('This acute junction cannot yet merge tapered approaches; reduce width or increase the angle')
    if max(abs(p[2]-center[2]) for p in neighbors)>1e-6:raise ValueError('Acute footprint merging currently requires a flat junction')
    vertices=[];faces=[];limits=[];c=Vector(center[:2]);arms=[]
    def polygon(poly):
        if area(poly)<0:poly=list(reversed(poly))
        if abs(area(poly))<1e-8:return
        ids=list(range(len(vertices),len(vertices)+len(poly)));vertices.extend((p.x+c.x,p.y+c.y,center[2]) for p in poly);faces.append(ids)
    for p in sorted(neighbors,key=lambda p:math.atan2(p[1]-center[1],p[0]-center[0])):
        d=Vector((p[0]-center[0],p[1]-center[1]));u=d.normalized();n=Vector((-u.y,u.x));w=edge_width(edges,center,p);end_w=edge_width(edges,p,center)
        arms.append(dict(u=u,n=n,w=w,length=d.length))
        polygon([-n*w/2,d-n*end_w/2,d+n*end_w/2,n*w/2])
    for a,b in zip(arms,arms[1:]+arms[:1]):
        u,v=a['u'],b['u'];theta=math.atan2(cross(u,v),u.dot(v))%(math.pi*2)
        if theta>=math.pi-1e-5:continue
        direction=u+v;label=('N' if direction.y>=0 else 'S')+('E' if direction.x>=0 else 'W');requested=radii[label]
        origin=intersection(a['n']*a['w']/2,u,-b['n']*b['w']/2,v)
        if origin is None:continue
        unit=intersection(a['n']*(a['w']/2+1),u,-b['n']*(b['w']/2+1),v)
        da=(unit-a['n']-origin).dot(u);db=(unit+b['n']-origin).dot(v)
        maximum=max(0.,min((a['length']*.98-origin.dot(u))/max(da,1e-9),(b['length']*.98-origin.dot(v))/max(db,1e-9)))
        applied=min(requested,maximum)
        if applied<=.02:
            limits.append(dict(corner=label,angle_degrees=math.degrees(theta),requested=requested,applied=0.,minimum=0.,maximum=maximum,mode='merged',exposed=False))
            continue
        cc=origin+(unit-origin)*applied;pa=cc-a['n']*applied;pb=cc+b['n']*applied;start=math.atan2((pa-cc).y,(pa-cc).x);sweep=-(math.pi-theta)
        steps=max(3,math.ceil(abs(sweep)*applied/spacing));arc=[cc+Vector((math.cos(start+sweep*i/steps),math.sin(start+sweep*i/steps)))*applied for i in range(steps+1)]
        polygon([origin]+arc)
        limits.append(dict(corner=label,angle_degrees=math.degrees(theta),requested=requested,applied=applied,minimum=.02,maximum=maximum,mode='fillet',exposed=True,arc_center=[cc.x+c.x,cc.y+c.y]))
    # Merge the raw overlapping rectangles before passing the patch upstream.
    # Each polygon must have its own compact vertex array, or unrelated vertices
    # would influence its bounds and flat-height tests.
    pieces=[([vertices[i] for i in f],[list(range(len(f)))],0) for f in faces]
    vs,fs,_=union_mesh(pieces,spacing)
    return vs,fs,{p:None for p in neighbors},Vector((0,0)),limits,0.
