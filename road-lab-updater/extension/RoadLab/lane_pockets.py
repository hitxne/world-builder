"""Portable, source-preserving local lane widening and taper evaluation."""
import math,bisect

def point_key(p):return tuple(round(float(v),6) for v in p)

def stations(coords):
    out=[0.]
    for a,b in zip(coords,coords[1:]):out.append(out[-1]+math.dist(a[:2],b[:2]))
    return out

def locate(coords,ids,pocket,base_width=8.,corner_radius=4.):
    selected=[i for i,ident in enumerate(ids) if ident in pocket['anchors']]
    if not selected:return None
    ss=stations(coords);total=ss[-1]
    if total<1e-6:return None
    cyclic=len(coords)>2 and math.dist(coords[0],coords[-1])<1e-6
    selected=sorted(set(ss[i] for i in selected))
    if cyclic and len(selected)>1:
        gaps=[((selected[(i+1)%len(selected)]-selected[i])%total,i) for i in range(len(selected))]
        _,i=max(gaps);first=selected[(i+1)%len(selected)];selected=sorted(s if s>=first else s+total for s in selected)
    orientation=1
    axis=pocket.get('axis',[])
    if len(axis)==2 and all(a in ids for a in axis):
        a,b=(ids.index(v) for v in axis)
        if b<a and not (cyclic and a==len(ids)-1 and b==0):orientation=-1
    side=pocket.get('side',-1)*orientation
    junction_direction=pocket.get('junction_direction',0)*orientation
    lo,hi=selected[0],selected[-1]
    if pocket.get('junction'):
        anchor=pocket.get('junction_anchor',pocket['anchors'][0]);center=ss[ids.index(anchor)] if anchor in ids else lo
        if (junction_direction or (1 if center<total*.5 else -1))>0:lo=center;hi=max(hi,center+pocket.get('length',24.))
        else:hi=center;lo=min(lo,center-pocket.get('length',24.))
    else:
        # Retain the entry shoulder when extending a one-point pocket to a run.
        lo-=pocket.get('length',12.)*.5;hi+=pocket.get('length',12.)*.5
    if not pocket.get('junction'):
        # Keep the requested corner radius: a bend needs a longer full-width
        # plateau than a straight bus bay. Do not add short taper gates there.
        for index,ident in enumerate(ids):
            if ident not in pocket['anchors'] or not (cyclic or 0<index<len(ids)-1):continue
            previous=coords[index-1 if index else len(ids)-1];current=coords[index];following=coords[(index+1)%len(ids)]
            a=(current[0]-previous[0],current[1]-previous[1]);b=(following[0]-current[0],following[1]-current[1]);den=math.hypot(*a)*math.hypot(*b)
            if den<1e-8:continue
            cosine=max(-.999,min(1.,(a[0]*b[0]+a[1]*b[1])/den))
            if cosine>.9999:continue
            tangent=math.sqrt((1-cosine)/max(1e-6,1+cosine));buffer=(((base_width+pocket['width'])/2+corner_radius)*tangent+.2)/.44+1.
            station=ss[index]
            if cyclic:
                station=min((station-total,station,station+total),key=lambda s:abs(s-(lo+hi)/2))
            lo=min(lo,station-buffer);hi=max(hi,station+buffer)
    if not cyclic:lo=max(0.,lo);hi=min(total,hi)
    start=lo-pocket.get('taper',15.);end=hi+pocket.get('taper',15.)
    if pocket.get('junction'):
        # A junction pocket belongs to one approach, never the opposite arm.
        if junction_direction>0:start=lo
        else:end=hi
    if not cyclic:start=max(0.,start);end=min(total,end)
    return dict(junction_direction=junction_direction,start=start,lo=lo,hi=hi,end=end,total=total,cyclic=cyclic,side=side,width=pocket['width'],pocket=pocket)

def amount(station,spec):
    if spec['cyclic']:
        station=min((station-spec['total'],station,station+spec['total']),key=lambda s:abs(s-(spec['lo']+spec['hi'])/2))
    a,b,c,d=(spec[k] for k in ('start','lo','hi','end'))
    if station<a-1e-8 or station>d+1e-8:return 0.
    if b<=station<=c:return spec['width']
    t=(station-a)/max(b-a,1e-9) if station<b else (d-station)/max(d-c,1e-9)
    t=max(0.,min(1.,t));return spec['width']*t*t*(3-2*t)

def sample(coords,ss,station):
    station=max(0.,min(ss[-1],station));i=next((i for i in range(len(ss)-1) if station<=ss[i+1]+1e-8),len(ss)-2)
    t=(station-ss[i])/max(ss[i+1]-ss[i],1e-9);a,b=coords[i:i+2]
    p=tuple(a[k]+(b[k]-a[k])*t for k in range(3));dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
    return p,(dx/max(length,1e-9),dy/max(length,1e-9)),i,t

def offsets(station,specs):
    groups={}
    for i,s in enumerate(specs):
        key=(s['pocket'].get('link_group',s['pocket'].get('id',i)),s['side'])
        groups[key]=max(groups.get(key,0.),amount(station,s))
    left=sum(v for (_,side),v in groups.items() if side>0);right=sum(v for (_,side),v in groups.items() if side<0)
    return left,right

def expand(paths,ids_by_path,pockets,default,tilts=None,junctions=(),corner_radius=4.):
    result=[];angles=[];details=[]
    shared=junction_shifts(paths,ids_by_path,pockets,junctions,default,corner_radius)
    for path_index,((coords,radii),ids) in enumerate(zip(paths,ids_by_path)):
        ss=stations(coords)
        specs=[v for p in pockets if (v:=locate(coords,ids,p,max(radii)*default,corner_radius)) is not None]
        if not specs:
            deformed=[(p[0]+shared.get(point_key(p),(0,0))[0],p[1]+shared.get(point_key(p),(0,0))[1],p[2]) for p in coords]
            result.append((deformed,radii));angles.append(tilts[path_index] if tilts else [0.]*len(coords));details.append(dict(specs=[],source_positions=dict(zip(coords,deformed))));continue
        cuts=set(ss)
        for spec in specs:
            for shift in (-spec['total'],0.,spec['total']) if spec['cyclic'] else (0.,):
                for section,(lo,hi) in enumerate(((spec['start']+shift,spec['lo']+shift),(spec['lo']+shift,spec['hi']+shift),(spec['hi']+shift,spec['end']+shift))):
                    lo=max(0.,lo);hi=min(ss[-1],hi)
                    if hi<lo:continue
                    steps=1 if section==1 else max(1,math.ceil((hi-lo)/2.))
                    cuts.update(lo+(hi-lo)*j/steps for j in range(steps+1))
        # Never insert a tiny segment beside an authored point. The junction
        # mesher needs useful gate lengths even for very shallow taper bends.
        minimum=max(.25,min(1.5,min((b-a for a,b in zip(ss,ss[1:]) if b>a),default=6.)*.25))
        retained=sorted(set(ss))
        for station in sorted(cuts-set(ss)):
            at=bisect.bisect_left(retained,station)
            if at and station-retained[at-1]<minimum or at<len(retained) and retained[at]-station<minimum:continue
            retained.insert(at,station)
        cuts=retained
        vs=[];rs=[];ts=[]
        junction_stations=[s for p,s in zip(coords,ss) if any(math.dist(p,q)<1e-5 for q in junctions)]
        for s in sorted(cuts):
            p,u,i,t=sample(coords,ss,s);left,right=offsets(s,specs)
            shift=(left-right)*.5
            # Use a miter at authored bends so a one-sided offset stays continuous.
            if abs(s-ss[i+1])<1e-7 and i+2<len(coords):
                dx=coords[i+2][0]-coords[i+1][0];dy=coords[i+2][1]-coords[i+1][1];norm=math.hypot(dx,dy)
                if norm>1e-8:
                    nx,ny=u[0]+dx/norm,u[1]+dy/norm;size=math.hypot(nx,ny)
                    if size>1e-8:
                        new_u=(nx/size,ny/size);cos=max(.2,u[0]*new_u[0]+u[1]*new_u[1]);shift/=cos;u=new_u
            if math.dist(coords[0],coords[-1])<1e-6 and (s<1e-7 or abs(s-ss[-1])<1e-7):
                before=(coords[-1][0]-coords[-2][0],coords[-1][1]-coords[-2][1]);after=(coords[1][0]-coords[0][0],coords[1][1]-coords[0][1]);na,nb=math.hypot(*before),math.hypot(*after)
                if na>1e-8 and nb>1e-8:
                    a=(before[0]/na,before[1]/na);b=(after[0]/nb,after[1]/nb);length=math.hypot(a[0]+b[0],a[1]+b[1])
                    if length>1e-8:u=((a[0]+b[0])/length,(a[1]+b[1])/length);shift=(left-right)*.5/max(.2,u[0]*b[0]+u[1]*b[1])
            delta=shared.get(point_key(p),(-u[1]*shift,u[0]*shift))
            vs.append((p[0]+delta[0],p[1]+delta[1],p[2]));rs.append((radii[i]*(1-t)+radii[i+1]*t)+(left+right)/default)
            source_tilts=tilts[path_index] if tilts else [0.]*len(coords);ts.append(source_tilts[i]*(1-t)+source_tilts[i+1]*t)
        result.append((vs,rs));angles.append(ts);details.append(dict(specs=specs,source_positions={tuple(p):vs[retained.index(s)] for p,s in zip(coords,ss)}))
    return result,angles,details


def junction_shifts(paths,ids_by_path,pockets,junctions,default=8.,corner_radius=4.):
    result={point_key(p):(0.,0.) for p in junctions}
    contributions={}
    for (coords,radii),ids in zip(paths,ids_by_path):
        ss=stations(coords);specs=[s for p in pockets if (s:=locate(coords,ids,p,max(radii)*default,corner_radius))]
        seen=set()
        for i,p in enumerate(coords):
            key=point_key(p)
            if key not in result or key in seen:continue
            seen.add(key)
            _,u,_,_=sample(coords,ss,ss[i])
            for j,spec in enumerate(specs):
                value=amount(ss[i],spec)*spec['side']*.5
                group=spec['pocket'].get('link_group',spec['pocket'].get('id',(id(coords),j)))
                ident=(key,group);delta=(-u[1]*value,u[0]*value)
                if ident not in contributions or math.hypot(*delta)>math.hypot(*contributions[ident]):contributions[ident]=delta
    for (key,_),delta in contributions.items():
        old=result[key];result[key]=(old[0]+delta[0],old[1]+delta[1])
    return result


def travel(spec,traffic_side):
    """Return physical travel direction and whether widening uses the median.

    A through lane added at a curb belongs to that curb's carriageway. It may
    be arriving OR departing at the selected arm; the selection does not decide
    its direction. This also repairs the interpretation of older saved pairs.
    """
    sign=1 if traffic_side=='RIGHT' else -1
    pocket=spec['pocket']
    if pocket.get('movement')=='THROUGH':return -spec['side']*sign,False
    flow=spec.get('junction_direction',0)*(1 if pocket.get('receiving') else -1) if pocket.get('junction') else -spec['side']*sign
    return flow,bool(pocket.get('junction') and spec['side']!=-flow*sign)

def receiving(spec,traffic_side):
    if spec['pocket'].get('movement')=='THROUGH':return travel(spec,traffic_side)[0]==spec.get('junction_direction',0)
    return bool(spec['pocket'].get('receiving'))
