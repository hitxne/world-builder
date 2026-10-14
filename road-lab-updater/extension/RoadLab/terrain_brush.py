"""Deterministic circular height-field brushes; independent of Blender."""
import math

def stamp(vertices, heights, center, radius, strength, dt, mode, target=0., neighbors=None):
    if radius <= 0 or strength < 0 or dt < 0:
        raise ValueError('Positive radius and nonnegative strength/time required')
    if mode not in ('RAISE','LOWER','SMOOTH','FLATTEN'):
        raise ValueError('Unknown terrain brush')
    before=list(heights); result=list(before)
    for i, p in enumerate(vertices):
        distance=math.hypot(p[0]-center[0],p[1]-center[1])
        if distance >= radius: continue
        t=distance/radius; falloff=1-t*t*(3-2*t)
        amount=strength*dt*falloff
        if mode in ('RAISE','LOWER'):
            result[i]+=amount*(1 if mode=='RAISE' else -1)
        else:
            if mode=='SMOOTH':
                adjacent=neighbors[i] if neighbors else []
                desired=sum(before[j] for j in adjacent)/len(adjacent) if adjacent else before[i]
            else: desired=target
            result[i]+=(desired-before[i])*(1-math.exp(-amount))
    return result

def adjacency(count, triangles):
    neighbors=[set() for _ in range(count)]
    for face in triangles:
        for i in face: neighbors[i].update(j for j in face if j!=i)
    return [sorted(row) for row in neighbors]
