"""Portable single-lane roundabout prototype: annulus and directed traffic paths.

No Blender dependency. Approach paths are preview centerlines, not joined road
surfaces. Swept vehicle envelopes, entry deflection and design-speed validation
must precede production use. Two-lane circulation needs a separate lane solver.
"""
from math import atan2, ceil, cos, sin, pi, hypot, isfinite


def build(approaches, center=(0.,0.,0.), island_radius=12., apron_width=1.5,
          lane_width=4.5, traffic_side='RIGHT', spacing=1.):
    if traffic_side not in ('RIGHT','LEFT'):raise ValueError('Unknown traffic side')
    if len(approaches)<3:raise ValueError('A junction roundabout needs at least three approaches')
    if len({a['id'] for a in approaches})!=len(approaches):raise ValueError('Duplicate approach IDs')
    if any(not isfinite(v) or v<=0 for v in (island_radius,lane_width,spacing)) or apron_width<0:
        raise ValueError('Invalid roundabout dimensions')
    if any(a.get('incoming_lanes',1)!=1 or a.get('outgoing_lanes',1)!=1 for a in approaches):
        raise ValueError('Prototype requires single-lane entries/exits; provide upstream transitions')
    sign=1 if traffic_side=='RIGHT' else -1
    inner=island_radius+apron_width;outer=inner+lane_width;radius=(inner+outer)/2
    port_delta=atan2(lane_width*.6,radius)
    bearings=[]
    for a in approaches:
        dx,dy=a['position'][0]-center[0],a['position'][1]-center[1]
        if hypot(dx,dy)<=outer+lane_width:
            raise ValueError('Approach handle too close: move it beyond the circulating roadway')
        bearings.append(atan2(dy,dx)%(2*pi))
    ordered=sorted(bearings)
    if min((ordered[(i+1)%len(ordered)]-ordered[i])%(2*pi) for i in range(len(ordered)))<=2*port_delta+.02:
        raise ValueError('Approaches too close: increase island radius or separate approaches')
    def point(r,t):return (center[0]+r*cos(t),center[1]+r*sin(t),center[2])
    ports=[];paths=[];yields=[]
    for a,bearing in zip(approaches,bearings):
        distance=hypot(a['position'][0]-center[0],a['position'][1]-center[1])
        for kind,angle in [('entry',bearing+sign*port_delta),('exit',bearing-sign*port_delta)]:
            id=f"{a['id']}:{kind}";angle%=2*pi;ports.append({'id':id,'angle':angle,'position':point(radius,angle)})
            tangent=(-sign*sin(angle),sign*cos(angle),0)
            unit=(cos(bearing),sin(bearing),0);lateral=(-sin(bearing),cos(bearing),0)
            offset=sign*lane_width*.6*(1 if kind=='entry' else -1)
            far=(center[0]+distance*unit[0]+offset*lateral[0],center[1]+distance*unit[1]+offset*lateral[1],center[2])
            gate=point(radius,angle);reach=min((distance-radius)*.4,lane_width*2)
            if kind=='entry':
                controls=[far,tuple(far[i]-unit[i]*reach for i in range(3)),tuple(gate[i]-tangent[i]*reach for i in range(3)),gate]
                yields.append({'approach':a['id'],'gate':id,'position':gate,'priority':'CIRCULATING_TRAFFIC'})
            else:controls=[gate,tuple(gate[i]+tangent[i]*reach for i in range(3)),tuple(far[i]-unit[i]*reach for i in range(3)),far]
            paths.append({'id':id,'kind':kind,'controls':controls,'from':f"{a['id']}:incoming" if kind=='entry' else id,'to':id if kind=='entry' else f"{a['id']}:outgoing"})
    ports.sort(key=lambda p:sign*p['angle'])
    ring=[]
    for i,p in enumerate(ports):
        q=ports[(i+1)%len(ports)];sweep=(sign*(q['angle']-p['angle']))%(2*pi);steps=max(2,ceil(radius*sweep/spacing))
        ring.append({'id':f"ring:{p['id']}",'from':p['id'],'to':q['id'],'points':[point(radius,p['angle']+sign*sweep*j/steps) for j in range(steps+1)],'sweep':sign*sweep})
    for y in yields:y['yield_to']=next(e['id'] for e in ring if e['to']==y['gate'])
    # Surface mesh is an annulus. Central island and apron are separate assets.
    steps=max(32,ceil(2*pi*outer/spacing));verts=[];faces=[]
    for i in range(steps):verts.extend((point(inner,2*pi*i/steps),point(outer,2*pi*i/steps)))
    for i in range(steps):j=(i+1)%steps;faces.append((2*i,2*i+1,2*j+1,2*j))
    return {'schema':1,'circulation':'CCW' if sign==1 else 'CW','center':center,
            'island_radius':island_radius,'apron_width':apron_width,'lane_width':lane_width,
            'ports':ports,'ring_edges':ring,'approach_paths':paths,'yield_rules':yields,
            'surface':{'vertices':verts,'faces':faces},'status':'SINGLE_LANE_PROTOTYPE'}


def build_for_map(scene, approaches, **geometry):
    """Scene adapter rejects per-junction traffic-side overrides."""
    from .map_settings import traffic_side
    if 'traffic_side' in geometry:
        raise ValueError('Driving side is a global RoadLab map setting')
    return build(approaches,traffic_side=traffic_side(scene),**geometry)
