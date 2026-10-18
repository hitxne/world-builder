"""Persistent settings for authoring points; UI readers never change selection."""
import json,uuid
from collections import defaultdict,deque

def points(road):return [p for spline in road.data.splines for p in spline.points]

def records(road):return json.loads(road.get('roadlab_point_settings','[]'))

def save(road,items):
    encoded=json.dumps(items,sort_keys=True)
    if road.get('roadlab_point_settings')!=encoded:road['roadlab_point_settings']=encoded

def sync(road):
    current=points(road);old=records(road);new=[]
    coordinates=[tuple(round(v,6) for v in p.co[:3]) for p in current]
    by_coordinate=defaultdict(list)
    for i,item in enumerate(old):by_coordinate[tuple(item['co'])].append(i)
    topology=json.loads(road.get('roadlab_point_topology','[]'))
    old_lookup={item['id']:tuple(item['co']) for item in old};old_neighbors=defaultdict(set)
    for ids,cyclic in topology:
        for i in range(len(ids) if cyclic else len(ids)-1):
            a,b=ids[i],ids[(i+1)%len(ids)]
            if a in old_lookup and b in old_lookup:
                old_neighbors[a].add(old_lookup[b]);old_neighbors[b].add(old_lookup[a])
    neighbors=defaultdict(set);offset=0;shape=[]
    for spline in road.data.splines:
        count=len(spline.points);shape.append((offset,count,spline.use_cyclic_u))
        for i in range(count if spline.use_cyclic_u else count-1):
            a,b=offset+i,offset+(i+1)%count
            neighbors[a].add(coordinates[b]);neighbors[b].add(coordinates[a])
        offset+=count
    # F may reverse and concatenate splines without changing the point count.
    # Index identity is safe for point movement, but not for that permutation.
    from collections import Counter
    remap=len(old)!=len(current) or Counter(coordinates)==Counter(tuple(item['co']) for item in old)
    used=set()
    for i,co in enumerate(coordinates):
        if not remap:item=dict(old[i])
        else:
            matches=[j for j in by_coordinate[co] if j not in used]
            if matches:
                j=max(matches,key=lambda j:(len(neighbors[i]&old_neighbors[old[j]['id']]),j==i))
                used.add(j);item=dict(old[j])
            else:item={'id':uuid.uuid4().hex}
        item['co']=list(co);new.append(item)
    save(road,new)
    topology_json=json.dumps([([item['id'] for item in new[start:start+count]],cyclic) for start,count,cyclic in shape])
    if road.get('roadlab_point_topology')!=topology_json:road['roadlab_point_topology']=topology_json
    return new

def width(road,index,default):
    items=records(road);p=points(road)[index]
    return items[index].get('width',default*p.radius) if index<len(items) else default*p.radius

def selected(context,road):
    if context.mode!='EDIT_CURVE' or context.edit_object!=road:return []
    road.update_from_editmode()
    return [i for i,p in enumerate(points(road)) if p.select]

def junction_overrides(road):
    result={}
    items=records(road)
    for item in items:
        if item.get('corners'):result.setdefault(tuple(item['co']),{}).update(item['corners'])
    if not any('bend_radius' in item for item in items):return result
    import math
    from .road_core import values
    from mathutils import Vector
    lookup={item['id']:item for item in items};neighbors=defaultdict(set)
    for ids,cyclic in json.loads(road.get('roadlab_point_topology','[]')):
        for i in range(len(ids) if cyclic else len(ids)-1):
            a,b=ids[i],ids[(i+1)%len(ids)]
            if a in lookup and b in lookup:
                neighbors[tuple(lookup[a]['co'])].add(tuple(lookup[b]['co']))
                neighbors[tuple(lookup[b]['co'])].add(tuple(lookup[a]['co']))
    default=values(road)['road width'];curve_points=points(road)
    for index,item in enumerate(items):
        if 'bend_radius' not in item:continue
        co=tuple(item['co']);arms=neighbors[co]
        if len(arms)!=2:continue
        arms=sorted((Vector((p[0]-co[0],p[1]-co[1])).normalized() for p in arms),key=lambda v:math.atan2(v.y,v.x))
        half=item.get('width',default*curve_points[index].radius)/2;radius=max(half+.02,item['bend_radius']);corners={}
        for a,b in (arms,arms[::-1]):
            theta=math.atan2(a.x*b.y-a.y*b.x,a.dot(b))%(2*math.pi)
            if abs(theta-math.pi)<1e-5:continue
            bisector=a+b
            if theta>math.pi:bisector=-bisector
            label=('N' if bisector.y>=0 else 'S')+('E' if bisector.x>=0 else 'W')
            corners[label]=radius-half if theta<math.pi else radius+half
        result.setdefault(co,{}).update(corners)
    return result

def widths(road,indices,default):
    items=records(road);ps=points(road)
    return [items[i].get('width',default*ps[i].radius) if i<len(items) else default*ps[i].radius for i in indices]

def corner_lifts(road):
    result={}
    for item in records(road):
        if item.get('corner_lifts'):result.setdefault(tuple(item['co']),{}).update(item['corner_lifts'])
    return result
