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
    by_coordinate=defaultdict(deque)
    for item in old:by_coordinate[tuple(item['co'])].append(item)
    for i,p in enumerate(current):
        co=[round(v,6) for v in p.co[:3]]
        if len(old)==len(current):item=dict(old[i])
        else:
            matches=by_coordinate[tuple(co)]
            if matches:item=dict(matches.popleft())
            else:item={'id':uuid.uuid4().hex}
        item['co']=co;new.append(item)
    save(road,new);return new

def width(road,index,default):
    items=records(road);p=points(road)[index]
    return items[index].get('width',default*p.radius) if index<len(items) else default*p.radius

def selected(context,road):
    if context.mode!='EDIT_CURVE' or context.edit_object!=road:return []
    road.update_from_editmode()
    return [i for i,p in enumerate(points(road)) if p.select]

def junction_overrides(road):
    result={}
    for item in records(road):
        if item.get('corners'):result.setdefault(tuple(item['co']),{}).update(item['corners'])
    return result

def widths(road,indices,default):
    items=records(road);ps=points(road)
    return [items[i].get('width',default*ps[i].radius) if i<len(items) else default*ps[i].radius for i in indices]

def corner_lifts(road):
    result={}
    for item in records(road):
        if item.get('corner_lifts'):result.setdefault(tuple(item['co']),{}).update(item['corner_lifts'])
    return result
