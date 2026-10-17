"""Locally cached polygon junction patches and shared, graded approach ribbons."""
import math
from collections import OrderedDict
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

_CACHE=OrderedDict()
EPS=1e-6

class NeedsFootprintMerge(ValueError):pass

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def area(p):return sum(cross(a,b) for a,b in zip(p,p[1:]+p[:1]))*.5

def inside(p,poly):
    hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit

def distance(p,a,b):
    d=b-a;t=max(0.,min(1.,(p-a).dot(d)/max(d.length_squared,1e-12)))
    return (p-a-d*t).length

def intersection(a,u,b,v):
    den=cross(u,v)
    # Unit directions below one microradian are numerically parallel at
    # road-mesh precision; intersecting them produces unstable huge miters.
    if abs(den)<1e-6:return None
    return a+u*(cross(b-a,v)/den)

def cached(key,make,stats):
    if key in _CACHE:
        stats['patches_reused']+=1;_CACHE.move_to_end(key);return _CACHE[key]
    value=make();_CACHE[key]=value;stats['patches_rebuilt']+=1
    while len(_CACHE)>256:_CACHE.popitem(last=False)
    return value

def gradient(center,neighbors):
    xx=xy=yy=xz=yz=0.
    for p in neighbors:
        x,y,z=(p[i]-center[i] for i in range(3));length=max(x*x+y*y,1e-9)
        xx+=x*x/length;xy+=x*y/length;yy+=y*y/length;xz+=x*z/length;yz+=y*z/length
    determinant=xx*yy-xy*xy
    # Nearly collinear arms cannot determine crossfall reliably. Regularize
    # that fit instead of amplifying crest slopes into a sideways spike.
    if determinant<.05*(xx+yy)**2:
        xx+=.08;yy+=.08;determinant=xx*yy-xy*xy
    if determinant>1e-8:
        result=Vector(((xz*yy-yz*xy)/determinant,(yz*xx-xz*xy)/determinant))
        maximum=max(abs(p[2]-center[2])/max(math.hypot(p[0]-center[0],p[1]-center[1]),1e-6) for p in neighbors)*1.5
        if result.length>maximum:result=result.normalized()*maximum
        return result
    p=next(iter(neighbors));d=Vector((p[0]-center[0],p[1]-center[1]));return d*((p[2]-center[2])/d.length_squared)

def edge_width(edges,a,b):
    edge=tuple(sorted((a,b)));value=edges[edge]
    return value[0 if a==edge[0] else 1] if isinstance(value,tuple) else value


def junction(center,neighbors,edges,spacing,radii,budgets,offsets=None,minimum_gate=0.,directions=None):
    c=Vector(center[:2]);g=gradient(center,neighbors)
    arms=[]
    for p in sorted(neighbors,key=lambda p:math.atan2(p[1]-center[1],p[0]-center[0])):
        delta=Vector((p[0]-center[0],p[1]-center[1]));u=Vector((directions or {}).get((center,p),delta.normalized()));n=Vector((-u.y,u.x))
        arms.append(dict(p=p,u=u,n=n,shift=(offsets or {}).get(p,0.),w=edge_width(edges,center,p),cols=max(2,math.ceil(max(edge_width(edges,center,p),edge_width(edges,p,center))/spacing)),budget=delta.length*budgets[p],gate=0.))
    corners=[];limits=[]
    for i,a in enumerate(arms):
        b=arms[(i+1)%len(arms)];u,v=a['u'],b['u'];theta=math.atan2(cross(u,v),u.dot(v))%(2*math.pi)
        bisector=u+v
        if theta>math.pi:bisector=-bisector
        label=('N' if bisector.y>=0 else 'S')+('E' if bisector.x>=0 else 'W')
        requested=radii[label];origin=intersection(a['n']*(a['shift']+a['w']/2),u,b['n']*(b['shift']-b['w']/2),v)
        if origin is None:
            corners.append(None);continue
        direction=1 if theta<math.pi else -1
        unit_center=intersection(a['n']*(a['shift']+a['w']/2+1),u,b['n']*(b['shift']-b['w']/2-1),v)
        da=direction*(unit_center-a['n']-origin).dot(u);db=direction*(unit_center+b['n']-origin).dot(v)
        ta=origin.dot(u);tb=origin.dot(v)
        maximum=min((a['budget']-spacing*.2-ta)/max(da,1e-9),(b['budget']-spacing*.2-tb)/max(db,1e-9))
        exterior=direction<0
        if exterior and len(arms)==2:
            other_label=('N' if -bisector.y>=0 else 'S')+('E' if -bisector.x>=0 else 'W')
            # Exterior rounding must not consume the opposite pavement edge.
            maximum=min(maximum,min(a['w'],b['w'])+radii[other_label]-.02)
        if maximum<requested and not exterior:raise NeedsFootprintMerge('Corner cannot fit between the existing patch gates')
        if maximum<.02:raise NeedsFootprintMerge('Exterior corner cannot fit safely between patch gates')
        applied=min(requested,maximum);cc=origin+(unit_center-origin)*(direction*applied);pa=cc-a['n']*(direction*applied);pb=cc+b['n']*(direction*applied)
        start=math.atan2((pa-cc).y,(pa-cc).x);sweep=theta-math.pi
        count=max(3,math.ceil(applied*abs(sweep)/spacing));curve=[cc+Vector((math.cos(start+sweep*j/count),math.sin(start+sweep*j/count)))*applied for j in range(count+1)]
        # A sub-micron arc collapses to a line at the output's coordinate
        # precision. Keep its miter instead of emitting collinear arc triangles.
        if applied*(1-math.cos(sweep/2))<EPS:curve=[origin]
        a['gate']=max(a['gate'],pa.dot(u)+spacing*.2);b['gate']=max(b['gate'],pb.dot(v)+spacing*.2)
        limits.append(dict(corner=label,kind='exterior' if exterior else 'interior',angle_degrees=math.degrees(theta),requested=requested,applied=applied,minimum=.02,maximum=maximum,arc_center=[cc.x+c.x,cc.y+c.y],height_anchor=[curve[len(curve)//2].x+c.x,curve[len(curve)//2].y+c.y],height_falloff=max(a['w'],b['w'],applied)*1.5))
        corners.append(curve)
    straight_frame=len(arms)==2 and directions and all((center,a['p']) in directions for a in arms) and arms[0]['u'].dot(arms[1]['u'])<-.99999
    for a in arms:a['gate']=max(a['gate'],min(.005 if straight_frame else max(spacing,minimum_gate),a['budget']*(.8 if minimum_gate else .5)))
    boundary=[];gates={}
    def line(a,b,count=None):
        count=count or max(1,math.ceil((b-a).length/spacing))
        for i in range(count):boundary.append(a+(b-a)*(i/count))
    for i,a in enumerate(arms):
        b=arms[(i+1)%len(arms)];right=a['u']*a['gate']+a['n']*(a['shift']-a['w']/2);left=a['u']*a['gate']+a['n']*(a['shift']+a['w']/2)
        cols=a['cols'];gates[a['p']]=list(range(len(boundary),len(boundary)+cols+1));line(right,left,cols)
        next_right=b['u']*b['gate']+b['n']*(b['shift']-b['w']/2);corner=corners[i]
        if corner:
            line(left,corner[0]);boundary.extend(corner[:-1]);line(corner[-1],next_right)
        else:line(left,next_right)
    # All gates share their exact original coordinates with the ribbon mesh.
    points=[Vector(p) for p in boundary];xmin=min(p.x for p in boundary);xmax=max(p.x for p in boundary);ymin=min(p.y for p in boundary);ymax=max(p.y for p in boundary)
    if (xmax-xmin)*(ymax-ymin)/spacing**2>120000:raise ValueError('Junction sampling budget exceeded')
    for x in range(math.floor(xmin/spacing),math.ceil(xmax/spacing)+1):
        for y in range(math.floor(ymin/spacing),math.ceil(ymax/spacing)+1):
            p=Vector((x*spacing,y*spacing))
            if inside(p,boundary) and min(distance(p,a,b) for a,b in zip(boundary,boundary[1:]+boundary[:1]))>spacing*.28:points.append(p)
    tri=delaunay_2d_cdt(points,[],[list(range(len(boundary)))],1,1e-7,True)
    faces=[list(f) for f,owners in zip(tri[2],tri[5]) if 0 in owners]
    expected=abs(area(boundary));actual=sum(abs(area([tri[0][j] for j in f])) for f in faces)
    if abs(expected-actual)>max(1e-4,expected*1e-6):raise ValueError('Junction footprint could not be triangulated safely')
    verts=[(c.x+p.x,c.y+p.y,center[2]+g.dot(p)) for p in tri[0]]
    original={old:new for new,items in enumerate(tri[3]) for old in items}
    seams={p:[verts[original[j]] for j in ids] for p,ids in gates.items()}
    return verts,faces,seams,g,limits,abs(expected-actual)

def ribbon(a,b,w,spacing,start,end,g0,g1,offset_a=0.,offset_b=0.,direction=None):
    wa,wb=w if isinstance(w,tuple) else (w,w)
    d=Vector((b[0]-a[0],b[1]-a[1]));length=d.length;u=Vector(direction) if direction else d.normalized();n=Vector((-u.y,u.x));cols=max(2,math.ceil(max(wa,wb)/spacing))
    if start is None:start=[(a[0]+n.x*(offset_a-wa/2+wa*j/cols),a[1]+n.y*(offset_a-wa/2+wa*j/cols),a[2]) for j in range(cols+1)]
    if end is None:end=[(b[0]+n.x*(-offset_b-wb/2+wb*j/cols),b[1]+n.y*(-offset_b-wb/2+wb*j/cols),b[2]) for j in range(cols+1)]
    start=sorted(start,key=lambda p:Vector(p[:2]).dot(n));end=sorted(end,key=lambda p:Vector(p[:2]).dot(n))
    length=(Vector(end[cols//2][:2])-Vector(start[cols//2][:2])).length;rows=max(1,math.ceil(length/spacing))
    if rows*cols>150000:raise ValueError('Road sampling budget exceeded')
    verts=[];faces=[]
    c0=tuple((start[0][k]+start[-1][k])*.5 for k in range(2));c1=tuple((end[0][k]+end[-1][k])*.5 for k in range(2))
    for i in range(rows+1):
        t=i/rows;h00=2*t**3-3*t*t+1;h10=t**3-2*t*t+t;h01=-2*t**3+3*t*t;h11=t**3-t*t
        blend=t if direction else h01
        for p,q in zip(start,end):
            z=h00*p[2]+h10*length*g0.dot(u)+h01*q[2]+h11*length*g1.dot(u)
            if i==0:xy=p[:2]
            elif i==rows:xy=q[:2]
            elif abs(wa-wb)<1e-9:xy=tuple(p[k]+(q[k]-p[k])*t for k in range(2))
            else:xy=tuple(c0[k]+(c1[k]-c0[k])*t+n[k]*((c1[0]-c0[0])*n.x+(c1[1]-c0[1])*n.y)*(blend-t)+(p[k]-c0[k])*(1-blend)+(q[k]-c1[k])*blend for k in range(2))
            verts.append((*xy,z))
    for i in range(rows):
        for j in range(cols):
            k=i*(cols+1)+j;faces.append([k,k+1,k+cols+2,k+cols+1])
    return verts,faces

def perimeter(verts,faces):
    counts={}
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):
            e=tuple(sorted((a,b)));counts[e]=counts.get(e,0)+1
    if max(counts.values(),default=0)>2:raise ValueError('Non-manifold interior edge')
    directed={}
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):
            if counts[tuple(sorted((a,b)))]==1:
                if a in directed:raise ValueError('Intersecting footprints need a merged junction; last valid mesh retained')
                directed[a]=b
    loops=[]
    while directed:
        start=next(iter(directed));p=start;loop=[]
        while p in directed:loop.append(p);p=directed.pop(p)
        if p!=start:raise ValueError('Open surface perimeter')
        loops.append(loop)
    return loops

def check_exposed_edges(verts,loops,spacing):
    # A spatial index catches same-height self-intersections without comparing
    # every generated face. Separate-height crossing surfaces remain allowed.
    bins={};segments=[];cell=max(spacing*2,1.)
    for loop in loops:
        for a,b in zip(loop,loop[1:]+loop[:1]):
            p,q=Vector(verts[a]),Vector(verts[b]);ids=set()
            keys=[(x,y) for x in range(math.floor(min(p.x,q.x)/cell),math.floor(max(p.x,q.x)/cell)+1) for y in range(math.floor(min(p.y,q.y)/cell),math.floor(max(p.y,q.y)/cell)+1)]
            for k in keys:ids.update(bins.get(k,[]))
            for old in ids:
                c,d,r,s=segments[old]
                if a in (c,d) or b in (c,d):continue
                u=q.xy-p.xy;v=s.xy-r.xy;den=cross(u,v)
                if abs(den)<max(1e-8,1e-6*u.length*v.length):continue
                t=cross(r.xy-p.xy,v)/den;h=cross(r.xy-p.xy,u)/den
                if 1e-6<t<1-1e-6 and 1e-6<h<1-1e-6 and abs((p.z+(q.z-p.z)*t)-(r.z+(s.z-r.z)*h))<1e-3:
                    raise ValueError('Road footprints overlap outside their junction; separate the points or reduce the width')
            index=len(segments);segments.append((a,b,p,q))
            for k in keys:bins.setdefault(k,[]).append(index)


def build_network(paths,width,spacing,radii,graph,junction_radii=None,port_offsets=None):
    if width<=0 or spacing<.1:raise ValueError('Width must be positive; spacing must be at least 0.1 m')
    radii=radii or dict.fromkeys(('NW','NE','SW','SE'),4.)
    if any(r<=0 for r in radii.values()):raise ValueError('Corner radii must be positive')
    from .footprint_merge import merge_overlaps,merged_junction
    def make_junction(p,neighbors,budgets,local_radii):
        offsets=(port_offsets or {}).get(p,{})
        try:return junction(p,neighbors,edges,spacing,local_radii,budgets,offsets,getattr(port_offsets,'gates',{}).get(p,0.),getattr(port_offsets,'directions',{}))
        except NeedsFootprintMerge:
            if any(abs(v)>1e-6 for v in offsets.values()):raise ValueError('This approach offset cannot fit; reduce it or extend the adjoining roads')
            return merged_junction(p,neighbors,edges,spacing,local_radii)
    nodes,edges,duplicates=graph(paths,width)
    if callable(port_offsets):port_offsets=port_offsets(nodes,edges)
    patches={};stats={'patches_reused':0,'patches_rebuilt':0};limits=[];error=0.
    for p,neighbors in nodes.items():
        if len(neighbors)<2:continue
        if len(neighbors)>6:raise ValueError('More than six streets at one junction are not supported')
        budgets={q:(.44 if len(nodes[q])>1 else .9) for q in neighbors}
        local_radii=dict(radii);local_radii.update((junction_radii or {}).get(p,{}))
        key=('junction',p,tuple(sorted((q,edges[tuple(sorted((p,q)))],budgets[q]) for q in neighbors)),spacing,tuple(sorted(local_radii.items())))
        if (port_offsets or {}).get(p):key+=('ports',tuple(sorted(port_offsets[p].items())))
        if getattr(port_offsets,'gates',{}).get(p):key+=('gate',port_offsets.gates[p])
        key+=('frames',tuple((q,getattr(port_offsets,'directions',{}).get((p,q))) for q in sorted(neighbors)))
        patches[p]=cached(key,lambda p=p,neighbors=neighbors:make_junction(p,neighbors,budgets,local_radii),stats)
        limits.extend(dict(item,junction=list(p)) for item in patches[p][4]);error=max(error,patches[p][5])
    verts=[];faces=[];regions=[];lookup={}
    def add(vs,fs,region):
        ids=[]
        for p in vs:
            k=tuple(round(float(v),6) for v in p)
            if k not in lookup:lookup[k]=len(verts);verts.append(k)
            ids.append(lookup[k])
        for f in fs:
            f=[ids[i] for i in f]
            if len(set(f))!=len(f):raise ValueError('Degenerate generated surface')
            signed=area([verts[i][:2] for i in f])
            if abs(signed)<1e-9:raise ValueError('Zero-area generated face')
            if signed<0:f.reverse()
            faces.append(f);regions.append(region)
    pieces=[(patch[0],patch[1],0) for patch in patches.values()]
    for region,((a,b),w) in enumerate(edges.items(),1):
        start=patches[a][2][b] if a in patches else None;end=patches[b][2][a] if b in patches else None
        g0=patches[a][3] if a in patches else gradient(a,[b]);g1=patches[b][3] if b in patches else gradient(b,[a])
        oa=(port_offsets or {}).get(a,{}).get(b,0.);ob=(port_offsets or {}).get(b,{}).get(a,0.)
        key=('ribbon',a,b,w,spacing,tuple(start or []),tuple(end or []),tuple(g0),tuple(g1),oa,ob)
        direction=getattr(port_offsets,'directions',{}).get((a,b));key+=('frame',direction)
        vs,fs=cached(key,lambda a=a,b=b,w=w,start=start,end=end,g0=g0,g1=g1:ribbon(a,b,w,spacing,start,end,g0,g1,oa,ob,direction),stats);pieces.append((vs,fs,region))
    pieces,merge_report=merge_overlaps(pieces,spacing,stats)
    for vs,fs,region in pieces:add(vs,fs,region)
    loops=perimeter(verts,faces)
    check_exposed_edges(verts,loops,spacing)
    if merge_report['merged_regions']:
        boundary=[verts[i] for loop in loops for i in loop]
        for item in limits:
            center=item.get('arc_center')
            if center and item['applied']>0:
                exposed=sum(abs(math.hypot(p[0]-center[0],p[1]-center[1])-item['applied'])<2e-5 for p in boundary)>=2
                if not exposed:item.update(applied=0.,mode='merged',exposed=False,maximum=0.)
    placements=[]
    for p,offsets in (port_offsets or {}).items():
        for q,value in offsets.items():
            if p in patches:
                gate=patches[p][2][q];c=Vector(tuple((gate[0][k]+gate[-1][k])/2 for k in range(3)));u=Vector(q)-Vector(p);u.z=0;u.normalize();distance=(c-Vector(p)).dot(u)
            else:distance=0.;c=Vector(p)
            placements.append(dict(junction=list(p),neighbor=list(q),offset=value,gate_distance=distance,gate_center=list(c)))
    return verts,faces,regions,loops,dict(approach_ports=placements,junctions=sum(len(v)>=3 for v in nodes.values()),junction_nodes=[list(p) for p,v in nodes.items() if len(v)>=3],unique_edges=len(edges),duplicate_segments_removed=duplicates,vertices=len(verts),faces=len(faces),perimeter_loops=len(loops),quad_faces=sum(len(f)==4 for f in faces),triangle_faces=sum(len(f)==3 for f in faces),active_corners=sorted(set(x['corner'] for x in limits)),radius_limits=limits,junction_area_error_m2=error,hidden_corners=sum(not x.get('exposed',True) for x in limits),**merge_report,**stats)
