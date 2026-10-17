"""Blender curve adapters for road-local width brushes and bridge cuts."""
import math,json
from . import point_settings as data,road_paths

def paths(road):
    result=[]
    for spline in road.data.splines:
        points=[tuple(p.co[:3]) for p in spline.points]
        if spline.use_cyclic_u and points:points.append(points[0])
        result.append(points)
    return result

def widen(road,center,radius,strength,dt):
    from .road_core import values
    default=values(road)['road width'];items=data.sync(road);all_points=data.points(road)
    old_widths=[item.get('width',default*p.radius) for item,p in zip(items,all_points)];offset=0;new_offset=0;inserted=[];topology_changed=False
    for spline in road.data.splines:
        if spline.type!='POLY':continue
        original=[(tuple(p.co),p.radius,p.select,old_widths[offset+i]) for i,p in enumerate(spline.points)];offset+=len(original)
        expanded=[];count=len(original);edge_count=count if spline.use_cyclic_u else count-1
        for i,entry in enumerate(original):
            expanded.append(entry)
            if i>=edge_count:continue
            a,b=entry,original[(i+1)%count];dx,dy=b[0][0]-a[0][0],b[0][1]-a[0][1];length=math.hypot(dx,dy)
            if length<=2:continue
            t=max(0.,min(1.,((center[0]-a[0][0])*dx+(center[1]-a[0][1])*dy)/length**2))
            d=math.hypot(a[0][0]+dx*t-center[0],a[0][1]+dy*t-center[1])
            if d>=radius:continue
            span=math.sqrt(max(0,radius**2-d**2))/length;lo=max(0.,t-span);hi=min(1.,t+span)
            samples=max(1,math.ceil((hi-lo)*length/2))
            cuts=sorted(set([lo,hi,t]+[lo+(hi-lo)*j/samples for j in range(samples+1)]))
            for u in cuts:
                if u*length<1 or (1-u)*length<1:continue
                if math.dist(expanded[-1][0][:2],(a[0][0]+dx*u,a[0][1]+dy*u))<1:continue
                co=tuple(a[0][k]+(b[0][k]-a[0][k])*u for k in range(4))
                expanded.append((co,a[1]+(b[1]-a[1])*u,False,a[3]+(b[3]-a[3])*u))
        if len(expanded)>len(original):
            spline.points.add(len(expanded)-len(original))
            for p,entry in zip(spline.points,expanded):p.co=entry[0];p.radius=entry[1];p.select=entry[2]
            original_coords={tuple(round(v,6) for v in entry[0][:3]) for entry in original}
            topology_changed=True
            for i,entry in enumerate(expanded):
                if tuple(round(v,6) for v in entry[0][:3]) not in original_coords:inserted.append((new_offset+i,entry[3]))
        new_offset+=len(spline.points)
    if topology_changed:items=data.sync(road)
    for i,width in inserted:items[i]['width']=width
    points=data.points(road);changed=0
    for i,p in enumerate(points):
        t=math.hypot(p.co.x-center[0],p.co.y-center[1])/radius
        if t>=1:continue
        width=items[i].get('width',default*p.radius);items[i]['width']=width+strength*min(dt,.1)*(1-t*t)**2;changed+=1
    if len(points)>10000:raise ValueError('Width brush exceeded 10,000 authoring points')
    data.save(road,items);return changed

def add_slice(road,start,end):
    source=paths(road);a=road_paths.closest(source,start);b=road_paths.closest(source,end)
    if a is None or b is None or a['spline']!=b['spline']:raise ValueError('Bridge cuts must be on the same road spline')
    if abs(a['along']-b['along'])<1:raise ValueError('Choose bridge cuts at least one metre apart')
    cyclic=road.data.splines[a['spline']].use_cyclic_u
    cuts=json.loads(road.get('roadlab_bridge_cuts','[]'));cuts.append({'spline':a['spline'],'start':list(a['point']),'end':list(b['point']),'wrap':cyclic and abs(a['along']-b['along'])>a['length']/2})
    road['roadlab_bridge_cuts']=json.dumps(cuts,sort_keys=True);return cuts[-1]

def slice_contact(road,point,reattach=False):
    source=paths(road);q=road_paths.closest(source,point)
    if q is None:raise ValueError('Select a road surface')
    cuts=json.loads(road.get('roadlab_bridge_cuts','[]'))
    pending=next((i for i in reversed(range(len(cuts))) if cuts[i].get('pending') and cuts[i]['spline']==q['spline']),None)
    if reattach:
        if pending is None:raise ValueError('Slice a start point on this spline before using Alt + Slice')
        cut=cuts[pending];a=road_paths.closest(source,cut['start'],cut['spline'])
        if abs(a['along']-q['along'])<1:raise ValueError('Bridge span needs at least one metre')
        cut['end']=list(q['point']);cut['pending']=False
        cut['wrap']=road.data.splines[q['spline']].use_cyclic_u and abs(a['along']-q['along'])>q['length']/2
    else:
        if pending is not None:cuts.pop(pending)
        cyclic=road.data.splines[q['spline']].use_cyclic_u
        cuts.append({'spline':q['spline'],'start':list(q['point']),'end':list(source[q['spline']][-1]),'wrap':cyclic,'pending':True})
    road['roadlab_bridge_cuts']=json.dumps(cuts,sort_keys=True)
    return cuts
