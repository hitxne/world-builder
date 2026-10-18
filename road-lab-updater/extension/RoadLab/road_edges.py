"""Station-based white edge lines, measured from the actual pavement boundary.

Point gaps are in source-spline left/right coordinates and interpolate between
handles. A transverse intersection avoids nearest-edge hopping at lane tapers.
"""
import copy,math
from collections import OrderedDict
from mathutils import Vector
from . import point_settings as ps
_CACHE=OrderedDict()

def boundary(obj):
    helper=obj.get('roadlab_core_mesh')
    if helper is None:return []
    key=(helper.as_pointer(),helper.data.as_pointer(),obj.get('roadlab_core_signature'))
    if key not in _CACHE:
        from .surface_network import perimeter
        verts=[tuple(v.co) for v in helper.data.vertices]
        _CACHE[key]=[(verts[a],verts[b]) for loop in perimeter(verts,[tuple(p.vertices) for p in helper.data.polygons]) for a,b in zip(loop,loop[1:]+loop[:1])]
        while len(_CACHE)>16:_CACHE.popitem(last=False)
    return _CACHE[key]

def fit(obj,config,plans):
    rows=ps.records(obj);lookup={r['id']:r for r in rows}
    if not all(v in lookup for v in config['endpoints']):return plans
    a,b=(Vector(lookup[v]['co']) for v in config['endpoints']);u=b-a;u.z=0;length=u.length
    if length<1e-6:return plans
    u/=length;n=Vector((-u.y,u.x,0));bins={};cell=4.
    # Project the perimeter once for this section, then query only its station bin.
    for p,q in boundary(obj):
        p=Vector(p)-a;q=Vector(q)-a;s,t=p.dot(u),q.dot(u)
        if abs(t-s)<1e-8:continue
        lo,hi=sorted((s,t))
        if hi<0 or lo>length:continue
        row=(s,t,p.dot(n),q.dot(n))
        for i in range(math.floor(max(-cell,lo)/cell),math.floor(min(length+cell,hi)/cell)+1):bins.setdefault(i,[]).append(row)
    if not bins:return plans
    # Spline left/right stays stable even when the lane editor reverses its view.
    ids=[r['id'] for r in rows];forward=True;offset=0
    for spline in obj.data.splines:
        seq=ids[offset:offset+len(spline.points)];offset+=len(spline.points)
        if all(v in seq for v in config['endpoints']):
            ia,ib=(seq.index(v) for v in config['endpoints']);forward=(ib-ia==1 or spline.use_cyclic_u and ia==len(seq)-1 and ib==0);break
    output=[]
    for original in plans:
        if original['role'][0]!='outer':output.append(original);continue
        mark=copy.deepcopy(original);f=Vector((*mark['forward'],0));c=Vector(mark['center']);h=mark['size'][1]/2
        source=[Vector(p) for p in mark.get('path',[c-f*h,c+f*h])];path=[];last_gap=.5
        for p,q in zip(source,source[1:]):
            count=max(1,math.ceil((q-p).length/1.))
            path.extend(p.lerp(q,i/count) for i in range(count))
        path.append(source[-1]);result=[]
        for point in path:
            s=(point-a).dot(u)
            safe=max(.0001,min(length-.0001,s))
            if abs(s-safe)<.001:point=point+u*(safe-s);s=safe
            old=(point-a).dot(n);positive=old>=0
            hits=[v+(w-v)*(s-x)/(y-x) for x,y,v,w in bins.get(math.floor(s/cell),[]) if min(x,y)-1e-5<=s<=max(x,y)+1e-5]
            candidates=[v for v in hits if (v>=0)==positive]
            if not candidates:result.append(list(point));continue
            edge=min(candidates,key=lambda v:abs(v-old))
            field='edge_left' if positive==forward else 'edge_right'
            t=max(0.,min(1.,s/length));ra,rb=(lookup[v] for v in config['endpoints']);gap=ra.get(field,.5)*(1-t)+rb.get(field,.5)*t
            # Measure perpendicular to the boundary, including a widening taper.
            slopes=[(w-v)/(y-x) for x,y,v,w in bins.get(math.floor(s/cell),[]) if min(x,y)-1e-5<=s<=max(x,y)+1e-5 and abs(v+(w-v)*(s-x)/(y-x)-edge)<1e-5]
            slope=min(slopes,key=abs) if slopes else 0.
            # Offset along the boundary normal. Converting a normal gap to
            # a transverse gap explodes near a perpendicular junction edge
            # and can send a white line diagonally across the carriageway.
            inward=(-1 if positive else 1)*(n-u*slope)/math.sqrt(1+slope*slope)
            result.append(list(point+n*(edge-old)+inward*gap));last_gap=gap
        mark['path']=result;mark['center']=result[len(result)//2];mark['size'][1]=sum(math.dist(p,q) for p,q in zip(result,result[1:]));mark['edge_inset']=last_gap;mark['pavement_anchored']=True
        output.append(mark)
    return output
