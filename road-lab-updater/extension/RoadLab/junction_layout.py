"""Read actual junction branches from RoadLab's topology; portable detection core."""
from math import atan2, degrees, hypot


def describe(nodes, edges, position, tolerance=15.0):
    """Topology determines branches; labels never rotate or snap their coordinates.

    T/Y/skewed labels are descriptive, not permissions. Movement connections must
    use actual headings and destinations. Existing graph excludes grade-separated
    crossings before this reader runs.
    """
    if position not in nodes:
        raise ValueError('Selected point is not a road-network node')
    approaches=[]
    for neighbor in nodes[position]:
        dx,dy=neighbor[0]-position[0],neighbor[1]-position[1]
        if hypot(dx,dy)<=1e-8:continue
        edge=tuple(sorted((position,neighbor)))
        widths=edges[edge]
        width=widths[edge.index(position)] if isinstance(widths,(tuple,list)) else widths
        approaches.append({'position':neighbor,'heading_deg':degrees(atan2(dy,dx))%360,
                           'width':float(width),'centerline':[position,neighbor]})
    approaches.sort(key=lambda a:a['heading_deg'])
    count=len(approaches)
    def angle(a,b):
        value=abs(a['heading_deg']-b['heading_deg'])%360
        return min(value,360-value)
    pairs=[(i,j) for i in range(count) for j in range(i+1,count)
           if abs(angle(approaches[i],approaches[j])-180)<=tolerance]
    if count==1:kind='ENDPOINT'
    elif count==2:kind='CONTINUATION' if pairs else 'BEND'
    elif count==3:kind='T_JUNCTION' if pairs else 'Y_JUNCTION'
    elif count==4:
        opposing=any(len({i,j,k,l})==4 for i,j in pairs for k,l in pairs)
        right_angles=all(abs(angle(approaches[i],approaches[(i+1)%4])-90)<=tolerance for i in range(4))
        kind='CROSSROADS' if opposing and right_angles else 'SKEWED_FOUR_WAY'
    else:kind='MULTI_WAY' if count>4 else 'ISOLATED'
    return {'position':position,'kind':kind,'approach_count':count,
            'is_junction':count>=3,'approaches':approaches}


def from_selection(context):
    """Blender adapter: read the actual selected POLY junction in world coordinates.

    No geometry or stored settings are changed. Coincident selected handles at
    the same logical junction are accepted; distinct selected points are rejected.
    """
    from mathutils import Vector
    from . import point_settings, road_core
    road=context.scene.wb_native.road
    if road is None:raise ValueError('Assign a scene road first')
    indices=point_settings.selected(context,road)
    points=point_settings.points(road)
    positions={road_core.key(tuple(points[i].co[:3])) for i in indices}
    if len(positions)!=1:raise ValueError('Select one junction location in Edit Mode')
    selected=positions.pop();default=road_core.values(road)['road width']
    paths=[];offset=0
    for spline in road.data.splines:
        if spline.type!='POLY':raise ValueError('Junction reader currently supports POLY road splines')
        coords=[tuple(p.co[:3]) for p in spline.points]
        widths=[point_settings.width(road,offset+i,default)/default for i in range(len(coords))]
        offset+=len(coords)
        if spline.use_cyclic_u and coords:coords.append(coords[0]);widths.append(widths[0])
        paths.append((coords,widths))
    nodes,edges,_=road_core.graph(paths,default)
    world=lambda p:road_core.key(tuple(road.matrix_world@Vector(p)))
    mapping={p:world(p) for p in nodes}
    world_nodes={mapping[p]:{mapping[n] for n in neighbors} for p,neighbors in nodes.items()}
    world_edges={}
    for edge,widths in edges.items():
        a,b=edge;dx,dy=b[0]-a[0],b[1]-a[1];length=hypot(dx,dy)
        factor=(road.matrix_world.to_3x3()@Vector((-dy/length,dx/length,0))).length
        pair=[float(w)*factor for w in widths] if isinstance(widths,(tuple,list)) else [float(widths)*factor]*2
        key=tuple(sorted((mapping[a],mapping[b])))
        if key[0]!=mapping[a]:pair.reverse()
        world_edges[key]=tuple(pair)
    result=describe(world_nodes,world_edges,world(selected))
    if not result['is_junction']:raise ValueError('Selected point is not a connected junction')
    return result
