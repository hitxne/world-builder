"""Connect paint through two-arm bends using the road kernel's actual patch sides."""
import math,hashlib,json
from mathutils import Vector
from . import surface_network as surface

def patches(nodes,edges,settings,overrides,port_offsets=None):
    result={};spacing=settings['resolution']
    for p,neighbors in nodes.items():
        if len(neighbors)!=2:continue
        a,b=neighbors
        if (Vector(a)-Vector(p)).normalized().dot((Vector(b)-Vector(p)).normalized())<-.9999:continue
        radii={k:settings['corner '+k] for k in ('NW','NE','SW','SE')};radii.update(overrides.get(p,{}))
        budgets={q:(.44 if len(nodes[q])>1 else .9) for q in neighbors}
        cachekey=('junction',p,tuple(sorted((q,edges[tuple(sorted((p,q)))],budgets[q]) for q in neighbors)),spacing,tuple(sorted(radii.items())))
        offsets=(port_offsets or {}).get(p,{})
        gate=getattr(port_offsets,'gates',{}).get(p,0.)
        if offsets:cachekey+=('ports',tuple(sorted(offsets.items())))
        if gate:cachekey+=('gate',gate)
        patch=surface._CACHE.get(cachekey)
        if patch is None:
            try:patch=surface.junction(p,neighbors,edges,spacing,radii,budgets,offsets,gate)
            except surface.NeedsFootprintMerge:continue # Retain a paint gap when a clean corridor is unavailable.
        result[p]=patch
    return result

def gate(patch,center,neighbor):
    u=(Vector(neighbor)-Vector(center));u.z=0;u.normalize()
    return sum((Vector(p)-Vector(center)).dot(u) for p in patch[2][neighbor])/len(patch[2][neighbor])

def resample(path,t):
    lengths=[(b-a).length for a,b in zip(path,path[1:])];distance=sum(lengths)*t
    for a,b,length in zip(path,path[1:],lengths):
        if distance<=length:return a+(b-a)*(distance/max(length,1e-9))
        distance-=length
    return path[-1].copy()

def side_paths(patch,a,b):
    verts,faces,seams=patch[:3];loop=max(surface.perimeter(verts,faces),key=len);points=[Vector(verts[i]) for i in loop]
    closest=lambda p:min(range(len(points)),key=lambda i:(points[i]-Vector(p)).length)
    ar,al=closest(seams[a][0]),closest(seams[a][-1]);br,bl=closest(seams[b][0]),closest(seams[b][-1])
    def walk(start,end,avoid):
        for step in (1,-1):
            indices=[start];i=start
            for _ in points:
                i=(i+step)%len(points);indices.append(i)
                if i==end:break
                if i in avoid:break
            if indices[-1]==end:return [points[j] for j in indices]
        raise ValueError('Bend paint corridor could not be traced')
    return walk(ar,bl,{al,br}),walk(al,br,{ar,bl})

def connect(bends,arms,hidden):
    plans=[];warnings=[]
    for p,patch in bends.items():
        neighbors=sorted(patch[2]);a,b=neighbors
        aa=arms.get((p,a),[]);bb=arms.get((p,b),[])
        if not aa or not bb:continue
        try:left,right=side_paths(patch,a,b)
        except ValueError as error:warnings.append(str(error));continue
        centersA=[r['fraction'] for r in aa if r['family'] in ('center-yellow','median-yellow','center-white')]
        centersB=[r['fraction'] for r in bb if r['family'] in ('center-yellow','median-yellow','center-white')]
        centerA=sum(centersA)/len(centersA) if centersA else .5;centerB=sum(centersB)/len(centersB) if centersB else .5
        for family in ('outer','center-yellow','median-yellow','center-white','divider'):
            rowsA=sorted([row for row in aa if row['family']==family],key=lambda row:row['fraction'])
            rowsB=sorted([row for row in bb if row['family']==family],key=lambda row:row['fraction'],reverse=True)
            pairs=list(zip(rowsA,rowsB))
            if family=='divider':
                pairs=[]
                for flow in (-1,1):
                    left_rows=sorted([r for r in rowsA if r['flow']==flow],key=lambda r:abs(r['fraction']-centerA))
                    right_rows=sorted([r for r in rowsB if r['flow']==-flow],key=lambda r:abs(r['fraction']-centerB))
                    outerA=next((r for r in aa if r['family']=='outer' and r['flow']==flow),None)
                    outerB=next((r for r in bb if r['family']=='outer' and r['flow']==-flow),None)
                    if not outerA or not outerB:
                        if left_rows or right_rows:warnings.append('Opposing one-way layouts need an explicit junction.')
                        continue
                    for i in range(max(len(left_rows),len(right_rows))):
                        ra=left_rows[i] if i<len(left_rows) else dict(outerA,asset=right_rows[i]['asset'],width=right_rows[i]['width'])
                        rb=right_rows[i] if i<len(right_rows) else dict(outerB,asset=left_rows[i]['asset'],width=left_rows[i]['width'])
                        pairs.append((ra,rb))
            elif len(rowsA)!=len(rowsB):
                warnings.append('Median or travel direction changes need an explicit lane transition.');continue
            for index,(ra,rb) in enumerate(pairs):
                if ra['asset']!=rb['asset']:continue
                count=max(4,math.ceil(max(sum((y-x).length for x,y in zip(path,path[1:])) for path in (left,right))/.35))
                path=[];baseline=[]
                wa=(left[0]-right[0]).length;wb=(left[-1]-right[-1]).length
                fa=ra.get('edge_inset',.5)/wa;fb=rb.get('edge_inset',.5)/wb
                fa=fa if ra['fraction']<.5 else 1-fa;fb=fb if 1-rb['fraction']<.5 else 1-fb
                for i in range(count+1):
                    t=i/count;blend=t*t*(3-2*t);fraction=ra['fraction']*(1-blend)+(1-rb['fraction'])*blend
                    l,r=resample(left,t),resample(right,t)
                    path.append(tuple(l.lerp(r,fraction)));baseline.append(tuple(l.lerp(r,fa*(1-blend)+fb*blend)))
                length=sum((Vector(y)-Vector(x)).length for x,y in zip(path,path[1:]));delta=Vector(path[-1])-Vector(path[0]);delta.z=0
                if length<1e-5 or delta.length<1e-5:continue
                delta.normalize();identity=hashlib.sha256(json.dumps(['bend',p,a,b,family,index]).encode()).hexdigest()
                if identity in hidden:continue
                plans.append(dict(unexpanded_path=baseline if family=='outer' else [],asset=ra['asset'],center=list(resample([Vector(x) for x in path],.5)),forward=[delta.x,delta.y],size=[ra['width'],length],path=path,role=['bend',family,index],id=identity,edge_inset=(ra.get('edge_inset',.5)+rb.get('edge_inset',.5))/2))
    return plans,warnings

def profile_transitions(nodes,edges,configs,positions,settings,stop_nodes=(),port_offsets=None):
    """Add paint-only corridors at straight two-road profile changes."""
    incident={}
    for config in configs:
        a,b=config['endpoints']
        if a not in positions or b not in positions:continue
        for ident,other,start in ((a,b,True),(b,a,False)):
            p=positions[ident];out=config['incoming' if start else 'outgoing'];inc=config['outgoing' if start else 'incoming']
            profile=([row['width'] for row in inc],[row['width'] for row in out],config['median'])
            incident.setdefault(p,[]).append((profile,config.get('lane_transition',30.)))
    candidates={p:rows for p,rows in incident.items() if len(rows)==2 and (p in stop_nodes or (rows[0][0][0],rows[0][0][1],rows[0][0][2])!=(rows[1][0][1],rows[1][0][0],rows[1][0][2]))}
    # The surface graph removes collinear authoring handles; restore only the
    # handles that actually need a lane transition, without changing the mesh.
    for p in candidates:
        if p in nodes:continue
        point=Vector(p)
        for (a,b),width in list(edges.items()):
            delta=Vector(b)-Vector(a);t=(point-Vector(a)).dot(delta)/max(delta.length_squared,1e-9)
            if not 1e-6<t<1-1e-6 or (Vector(a)+delta*t-point).length>1e-5:continue
            wa,wb=width if isinstance(width,(tuple,list)) else (width,width);wp=wa+(wb-wa)*t
            del edges[(a,b)];nodes[a].remove(b);nodes[b].remove(a);nodes[a].add(p);nodes[b].add(p);nodes[p]={a,b}
            for x,y,wx,wy in ((a,p,wa,wp),(p,b,wp,wb)):
                key=tuple(sorted((x,y)));pair=(wx,wy) if key[0]==x else (wy,wx);edges[key]=pair[0] if abs(wx-wy)<1e-6 else pair
            break
    result={}
    for p,rows in candidates.items():
        neighbors=nodes.get(p,set())
        if len(neighbors)!=2:continue
        a,b=sorted(neighbors);ua=(Vector(a)-Vector(p)).normalized();ub=(Vector(b)-Vector(p)).normalized()
        if ua.dot(ub)>-.9999:continue
        seams={}
        for q,u in ((a,ua),(b,ub)):
            distance=getattr(port_offsets,'gates',{}).get(p,min(max(row[1] for row in rows)/2,(Vector(q)-Vector(p)).length*.4))
            center=Vector(p)+u*distance;normal=Vector((-u.y,u.x,0));center+=normal*(port_offsets or {}).get(p,{}).get(q,0.);width=surface.edge_width(edges,p,q)
            seams[q]=[tuple(center-normal*width/2),tuple(center+normal*width/2)]
        verts=[seams[a][0],seams[a][1],seams[b][0],seams[b][1]]
        result[p]=(verts,[[0,1,2,3]],seams,None,[],0)
    return result
