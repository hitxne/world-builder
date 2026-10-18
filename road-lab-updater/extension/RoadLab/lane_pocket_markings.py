"""Keep existing travel lanes aligned while lane pockets widen one road edge."""
import math,copy,json
from . import lane_pockets as pocket_math,lane_markings,point_settings

_CACHE={}

def context(obj):
    from . import point_settings as ps
    from .road_core import graph,values
    signature=(obj.as_pointer(),obj.get('roadlab_core_signature'),obj.get('roadlab_lane_pockets'),obj.get('roadlab_point_settings'))
    if signature in _CACHE:return _CACHE[signature]
    settings=values(obj);default=settings['road width'];radius=max(settings['corner '+k] for k in ('NW','NE','SW','SE'))
    rows=ps.records(obj);offset=0;paths=[];ids_by_path=[];records=[];pockets=json.loads(obj.get('roadlab_lane_pockets','[]'))
    for spline in obj.data.splines:
        ids=[r['id'] for r in rows[offset:offset+len(spline.points)]];offset+=len(spline.points)
        coords=[tuple(p.co[:3]) for p in spline.points]
        if spline.use_cyclic_u:coords.append(coords[0])
        widths=[ps.width(obj,i,default)/default for i in range(offset-len(ids),offset)]
        if spline.use_cyclic_u:widths.append(widths[0])
        specs=[s for p in pockets if (s:=pocket_math.locate(coords,ids,p,max(widths)*default,radius))]
        records.append((coords,ids,specs));paths.append((coords,widths));ids_by_path.append(ids)
    nodes,_,_=graph(paths,values(obj)['road width'])
    shifts=pocket_math.junction_shifts(paths,ids_by_path,pockets,[p for p,n in nodes.items() if len(n)>=3],default,radius)
    result=(records,shifts);_CACHE[signature]=result
    if len(_CACHE)>32:_CACHE.pop(next(iter(_CACHE)))
    return result

def source(obj,config):
    for coords,ids,specs in context(obj)[0]:
        if all(a in ids for a in config['endpoints']):return coords,ids,specs
    return None

def effective_width(obj,config,point,width,toward=None):
    if not obj.get('roadlab_lane_pockets') or obj.get('roadlab_lane_pockets')=='[]':return width
    data=source(obj,config)
    if not data:return width
    coords,ids,specs=data;a,b=(next(r['co'] for r in point_settings.records(obj) if r['id']==v) for v in config['endpoints'])
    other=toward if toward is not None else b if math.dist(point,a)<math.dist(point,b) else a
    near=[point[k]+(other[k]-point[k])*1e-6 for k in range(3)]
    station,_=project(coords,pocket_math.stations(coords),near);left,right=pocket_math.offsets(station,specs)
    return width+left+right

def warp_neighbor(obj,config,plans):
    from . import point_settings as ps
    rows={r['id']:r for r in ps.records(obj)};a,b=(rows[i]['co'] for i in config['endpoints']);shifts=context(obj)[1]
    da=shifts.get(pocket_math.point_key(a),(0.,0.));db=shifts.get(pocket_math.point_key(b),(0.,0.))
    if not any(abs(x)>1e-8 for d in (da,db) for x in d):return plans
    dx,dy=b[0]-a[0],b[1]-a[1];length2=dx*dx+dy*dy
    axis=(dx/math.sqrt(length2),dy/math.sqrt(length2))
    da=tuple(axis[k]*(da[0]*axis[0]+da[1]*axis[1]) for k in range(2));db=tuple(axis[k]*(db[0]*axis[0]+db[1]*axis[1]) for k in range(2))
    def warp(p):
        t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/max(length2,1e-9)))
        return [p[0]+da[0]*(1-t)+db[0]*t,p[1]+da[1]*(1-t)+db[1]*t,p[2]]
    output=[]
    for original in plans:
        mark=copy.deepcopy(original);c=mark['center'];f=mark['forward'];mark['center']=warp(c)
        p,q=warp([c[0]-f[0],c[1]-f[1],c[2]]),warp([c[0]+f[0],c[1]+f[1],c[2]]);d=math.hypot(q[0]-p[0],q[1]-p[1]);mark['forward']=[(q[0]-p[0])/max(d,1e-9),(q[1]-p[1])/max(d,1e-9)]
        if mark.get('path'):mark['path']=[warp(p) for p in mark['path']]
        elif mark['role'][0] in ('outer','divider','center-yellow','median-yellow','center-white'):
            half=mark['size'][1]/2;mark['path']=[warp([c[0]-f[0]*half,c[1]-f[1]*half,c[2]]),warp([c[0]+f[0]*half,c[1]+f[1]*half,c[2]])]
        if mark.get('crosswalk_ends'):mark['crosswalk_ends']=[warp(p) for p in mark['crosswalk_ends']]
        output.append(mark)
    return output

def project(coords,ss,p):
    best=None
    for i,(a,b) in enumerate(zip(coords,coords[1:])):
        dx,dy=b[0]-a[0],b[1]-a[1];length=ss[i+1]-ss[i]
        if length<1e-8:continue
        t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length**2));q=(a[0]+dx*t,a[1]+dy*t)
        distance=math.dist(q,p[:2])
        if best is None or distance<best[0]:best=(distance,ss[i]+length*t,(dx/length,dy/length))
    return best[1:]

def adapt(obj,config,plans,side):
    if not obj.get('roadlab_lane_pockets') or obj.get('roadlab_lane_pockets')=='[]':return plans
    data=source(obj,config)
    if not data:return plans
    if not data[2]:return warp_neighbor(obj,config,plans)
    coords,ids,specs=data;ss=pocket_math.stations(coords);output=[]
    from . import point_settings as ps
    from .road_core import values
    rows=ps.records(obj);lookup={r['id']:i for i,r in enumerate(rows)};points=ps.points(obj)
    a,b=(tuple(points[lookup[v]].co[:3]) for v in config['endpoints']);delta=(b[0]-a[0],b[1]-a[1]);align=1 if ids.index(config['endpoints'][1])>ids.index(config['endpoints'][0]) else -1
    flow_sign=1 if side=='RIGHT' else -1
    def mode(spec):
        return pocket_math.travel(spec,side)
    def shift(mark,point):
        station,u=project(coords,ss,point);left=(-u[1],u[0]);offset=0.;role=mark['role'];family=role[0]
        flow=role[1]*align if len(role)>1 and isinstance(role[1],(int,float)) else 0
        for spec in specs:
            amount=pocket_math.amount(station,spec)
            incoming,median=mode(spec)
            if median and (family in ('center-yellow','median-yellow','center-white') or flow==-incoming and family not in ('crosswalk','tactile')):offset+=spec['side']*amount
            elif not median and family=='outer' and flow==incoming:offset+=spec['side']*amount
        return [point[0]+left[0]*offset,point[1]+left[1]*offset,point[2]]
    for original in plans:
        mark=copy.deepcopy(original);family=mark['role'][0]
        if family in ('crosswalk','tactile'):output.append(mark);continue
        if family in ('outer','center-yellow','median-yellow','center-white','divider'):
            f=mark['forward'];span=mark['size'][1];count=max(1,math.ceil(span/1.5));c=mark['center']
            path=[shift(mark,[c[0]+f[0]*span*(i/count-.5),c[1]+f[1]*span*(i/count-.5),c[2]]) for i in range(count+1)]
            if any(math.dist(p,q)>1e-6 for p,q in zip(path,[[c[0]+f[0]*span*(i/count-.5),c[1]+f[1]*span*(i/count-.5),c[2]] for i in range(count+1)])):
                if family=='outer':
                    total=sum(r['width'] for field in ('incoming','outgoing') for r in config[field])+config.get('median',0.)
                    baseline=min(ps.width(obj,lookup[v],values(obj)['road width']) for v in config['endpoints']);inset=max(.05,(baseline-total)/2)
                    path=[snap_outer(obj,p,inset) for p in path];mark['pavement_anchored']=True
                mark['path']=path
        else:mark['center']=shift(mark,mark['center'])
        if family=='arrow':
            station,_=project(coords,ss,original['center']);flow=mark['role'][1]*align
            for spec in specs:
                incoming,median=mode(spec)
                if not spec['pocket'].get('junction') or pocket_math.has_through(spec['pocket']) or incoming!=flow or pocket_math.amount(station,spec)<spec['width']*.9:continue
                direction='incoming' if mark['role'][1]>0 else 'outgoing';index=mark['role'][2]
                allowed=config[direction][index]['movement'].split('_')
                movement=('LEFT' if side=='RIGHT' else 'RIGHT') if median else ('RIGHT' if side=='RIGHT' else 'LEFT')
                if movement in allowed and len(allowed)>1:mark['asset']=lane_markings.arrow_id([v for v in allowed if v!=movement],side)
        if family=='stop':
            station,u=project(coords,ss,original['center']);flow=mark['role'][1]*align
            for spec in specs:
                incoming,median=mode(spec);amount=pocket_math.amount(station,spec)
                if incoming!=flow or amount<1e-6:continue
                mark['size'][0]+=amount;mark['center'][0]-=u[1]*spec['side']*amount/2;mark['center'][1]+=u[0]*spec['side']*amount/2
        output.append(mark)
    # Extend crosswalk ends and reconstruct stripes, rather than stretching stripes.
    for direction in set(m['role'][1] for m in output if m['role'][0]=='crosswalk'):
        crossing=[m for m in output if m['role'][0]=='crosswalk' and m['role'][1]==direction]
        template=crossing[0];ends=copy.deepcopy(template['crosswalk_ends']);center=[sum(p[i] for p in ends)/2 for i in range(3)];station,u=project(coords,ss,center);left=(-u[1],u[0]);changed=False
        for spec in specs:
            amount=pocket_math.amount(station,spec)
            if amount<1e-6:continue
            target=max(range(2),key=lambda i:spec['side']*((ends[i][0]-center[0])*left[0]+(ends[i][1]-center[1])*left[1]))
            ends[target][0]+=left[0]*spec['side']*amount;ends[target][1]+=left[1]*spec['side']*amount;changed=True
            for mark in output:
                if mark['role'][0]!='tactile' or mark['role'][1]!=direction:continue
                original_center=mark['center']
                if spec['side']*((original_center[0]-center[0])*left[0]+(original_center[1]-center[1])*left[1])>0:
                    mark['center'][0]+=left[0]*spec['side']*amount;mark['center'][1]+=left[1]*spec['side']*amount
        if not changed:continue
        output=[m for m in output if m not in crossing]
        dx,dy=ends[1][0]-ends[0][0],ends[1][1]-ends[0][1];length=math.hypot(dx,dy);tx,ty=dx/length,dy/length
        period=1.2192;width=.6096;count=max(1,int((length-.3+period-width)/period));used=count*width+(count-1)*(period-width)
        for i in range(count):
            t=((length-used)/2+width/2+i*period)/length;mark=copy.deepcopy(template);mark['role']=['crosswalk',direction,i];mark['center']=[ends[0][j]+(ends[1][j]-ends[0][j])*t for j in range(3)];mark['forward']=[ty,-tx];mark['crosswalk_ends']=copy.deepcopy(ends);output.append(mark)
    for spec in specs:
        incoming,median=mode(spec);pocket=spec['pocket']
        # A config must touch this pocket's source span, including its end tapers.
        sa,_=project(coords,ss,a);sb,_=project(coords,ss,b);lo=max(min(sa,sb),spec['start']);hi=min(max(sa,sb),spec['end'])
        outer=[m for m in plans if m['role'][0]=='outer' and m['role'][1]*align==incoming]
        if not outer or hi-lo<.25:continue
        base=outer[0]
        # Lane divider follows the old curb line, or the old incoming median edge.
        base_station,u=project(coords,ss,base['center']);base_point,_,_,_=pocket_math.sample(coords,ss,base_station);left=(-u[1],u[0])
        lateral=(base['center'][0]-base_point[0])*left[0]+(base['center'][1]-base_point[1])*left[1]
        if median:
            center_mark=next((m for m in plans if m['role'][0] in ('center-yellow','median-yellow','center-white')),None)
            if center_mark:
                lateral=(center_mark['center'][0]-base_point[0])*left[0]+(center_mark['center'][1]-base_point[1])*left[1]
                lateral+=(-incoming*flow_sign)*config.get('median',0.)/2
        # Respect existing junction/crosswalk clearances.
        c=base['center'];f=base['forward'];half=base['size'][1]/2
        s1,_=project(coords,ss,(c[0]-f[0]*half,c[1]-f[1]*half,c[2]));s2,_=project(coords,ss,(c[0]+f[0]*half,c[1]+f[1]*half,c[2]));lo=max(lo,min(s1,s2));hi=min(hi,max(s1,s2))
        for section,(x,y) in enumerate(((lo,min(hi,spec['lo'])),(max(lo,spec['lo']),min(hi,spec['hi'])),(max(lo,spec['hi']),hi))):
            if y-x<.1:continue
            asset='line_white' if pocket.get('junction') and not pocket_math.receiving(spec,side) and section==1 else 'broken_white' if section==1 else 'dotted_white'
            path=[]
            for i in range(max(1,math.ceil((y-x)/1.5))+1):
                s=x+(y-x)*i/max(1,math.ceil((y-x)/1.5));co,tangent,_,_=pocket_math.sample(coords,ss,s);path.append([co[0]-tangent[1]*lateral,co[1]+tangent[0]*lateral,co[2]])
            mark=dict(asset=asset,center=path[len(path)//2],forward=[u[0]*incoming,u[1]*incoming],size=[.1524,y-x],path=path if incoming>0 else path[::-1],role=['pocket-divider',pocket['id'],section]);output.append(mark)
        if pocket.get('junction') and not pocket_math.receiving(spec,side):
            s=min(hi-4.,spec['hi']-4.) if incoming>0 else max(lo+4.,spec['lo']+4.)
            if max(lo,spec['lo'])+2.<s<min(hi,spec['hi'])-2.:
                co,u,_,_=pocket_math.sample(coords,ss,s);offset=lateral+spec['side']*pocket['width']/2
                movement=('LEFT' if side=='RIGHT' else 'RIGHT') if median else ('RIGHT' if side=='RIGHT' else 'LEFT')
                if pocket_math.has_through(pocket):movement=pocket['movement']
                asset=lane_markings.arrow_id(movement.split('_'),side);definition=lane_markings.manifest()[asset];canvas=definition['physical_canvas_m'];scale=min(1.,(pocket['width']-.3)/canvas[0]);canvas=[v*scale for v in canvas]
                output.append(dict(asset=asset,center=[co[0]-u[1]*offset,co[1]+u[0]*offset,co[2]],forward=[u[0]*incoming,u[1]*incoming],size=list(canvas),role=['pocket-arrow',pocket['id'],movement]))
    return output

_BOUNDARIES={}
def snap_outer(obj,point,inset=.5):
    """Project an edge line inside the finished pavement boundary, including bends."""
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    from .surface_network import perimeter
    helper=obj.get('roadlab_core_mesh')
    if not helper:return list(point)
    key=(helper.as_pointer(),helper.data.as_pointer())
    if key not in _BOUNDARIES:
        verts=[v.co.copy() for v in helper.data.vertices];faces=[tuple(p.vertices) for p in helper.data.polygons];segments=[]
        for loop in perimeter(verts,faces):
            for a,b in zip(loop,loop[1:]+loop[:1]):segments.append((verts[a],verts[b]))
        tree=KDTree(len(segments))
        for i,(a,b) in enumerate(segments):tree.insert(Vector(((a.x+b.x)/2,(a.y+b.y)/2,0)),i)
        tree.balance();_BOUNDARIES[key]=(segments,tree)
        if len(_BOUNDARIES)>32:_BOUNDARIES.pop(next(iter(_BOUNDARIES)))
    segments,tree=_BOUNDARIES[key];p=Vector(point);best=None
    for _,i,_ in tree.find_n(Vector((p.x,p.y,0)),min(16,len(segments))):
        a,b=segments[i];d=b-a;length=d.xy.length
        if length<1e-8:continue
        t=max(0.,min(1.,(p.xy-a.xy).dot(d.xy)/length**2));q=a+d*t;distance=(q.xy-p.xy).length_squared
        if best is None or distance<best[0]:best=(distance,q,Vector((-d.y/length,d.x/length,0)))
    if best is None:return list(point)
    q=best[1]+best[2]*inset;return [q.x,q.y,point[2]]

def adapt_connectors(obj,plans,side,segments=()):
    if not obj.get('roadlab_lane_pockets') or obj.get('roadlab_lane_pockets')=='[]':return plans
    from mathutils import Vector
    records,_=context(obj);result=[];sign=1 if side=='RIGHT' else -1
    for original in plans:
        if not original.get('path'):result.append(original);continue
        mark=copy.deepcopy(original);family=mark['role'][1];path=original['path'];changed=False;dividers={}
        for i,p in enumerate(path):
            tangent=Vector(path[min(len(path)-1,i+1)])-Vector(path[max(0,i-1)]);tangent.z=0
            if tangent.length<1e-7:continue
            tangent.normalize();nearest=None
            for coords,ids,specs in records:
                if not specs:continue
                ss=pocket_math.stations(coords);station,u=project(coords,ss,p);co,_,_,_=pocket_math.sample(coords,ss,station);distance=math.dist(co[:2],p[:2])
                if nearest is None or distance<nearest[0]:nearest=(distance,station,u,co,specs)
            if nearest is None:continue
            _,station,u,co,specs=nearest
            if tangent.x*u[0]+tangent.y*u[1]<0:tangent=-tangent
            normal=Vector((-tangent.y,tangent.x,0));lateral=(p[0]-co[0])*-u[1]+(p[1]-co[1])*u[0];active=False
            for spec in specs:
                amount=pocket_math.amount(station,spec)
                if amount<1e-7:continue
                pocket=spec['pocket'];flow,median=pocket_math.travel(spec,side)
                moving=family in ('center-yellow','median-yellow','center-white') and median or family=='outer' and lateral*spec['side']>0
                if moving:active=True;changed=True
                if family=='outer' and not median and lateral*spec['side']>0:dividers[pocket['id']]=(pocket,min(amount,dividers.get(pocket['id'],(None,amount))[1]))
            if active and family=='outer':mark['path'][i]=snap_outer(obj,p,mark.get('edge_inset',.5))
        if changed:
            mark['center']=list(mark['path'][len(mark['path'])//2]);mark['size'][1]=sum(math.dist(a,b) for a,b in zip(mark['path'],mark['path'][1:]))
        result.append(mark)
        for ident,(pocket,minimum) in dividers.items():
            divider=copy.deepcopy(original)
            divider['path']=copy.deepcopy(original.get('unexpanded_path') or original['path'])
            joins=[p for m in segments if m['role'][0]=='pocket-divider' and m['role'][1]==ident for p in (m['path'][0],m['path'][-1])]
            if joins:
                path=divider['path'];deltas=[]
                for p in (path[0],path[-1]):
                    q=min(joins,key=lambda q:math.dist(p,q));deltas.append([q[k]-p[k] for k in range(3)] if math.dist(p,q)<.5 else [0.,0.,0.])
                divider['path']=[[p[k]+deltas[0][k]*(1-i/(len(path)-1))+deltas[1][k]*i/(len(path)-1) for k in range(3)] for i,p in enumerate(path)]
            divider['center']=divider['path'][len(divider['path'])//2];divider['size'][1]=sum(math.dist(a,b) for a,b in zip(divider['path'],divider['path'][1:]));divider['asset']='line_white' if pocket.get('junction') and minimum>pocket['width']*.95 else 'broken_white' if minimum>pocket['width']*.95 else 'dotted_white';divider['role']=['pocket-bend-divider',ident,*original['role'][1:]];divider['id']=original['id']+'-'+ident;result.append(divider)
    return result
