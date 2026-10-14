"""Blender authoring-state adapter for an engine-independent edit schema."""
import json
from . import point_settings as points

def authoring_state(road):
    from .road_core import values
    settings=values(road);items=points.sync(road);offset=0;paths=[]
    for spline in road.data.splines:
        path=[]
        for p in spline.points:
            item=items[offset];path.append({'id':item['id'],'position':list(p.co[:3]),'tilt':float(p.tilt),'width':item.get('width',settings['road width']*p.radius),'radii':item.get('corners',{}),'corner_lifts':item.get('corner_lifts',{})});offset+=1
        paths.append({'closed':bool(spline.use_cyclic_u),'points':path})
    return {'schema':'roadlab.edits','version':1,'units':'metres','basis':'road-local right-handed Z-up','transform':[list(row) for row in road.matrix_world],'defaults':settings,'paths':paths,'height_field':json.loads(road.get('roadlab_sculpt_field','') or '{}'),'terrain_contact_cuts':json.loads(road.get('roadlab_bridge_cuts','[]'))}
