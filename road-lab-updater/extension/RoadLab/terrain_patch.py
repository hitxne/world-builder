"""Local constrained cavity remeshing; untouched faces retain their vertices."""
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from .surface_network import area,perimeter,inside
from .adaptive_terrain import overlaps

def remesh(flat,faces,origins,box,samples,protected,near_border,spacing):
    selected=[];untouched=[]
    for face in faces:
        bounds=(min(flat[i][0] for i in face),min(flat[i][1] for i in face),max(flat[i][0] for i in face),max(flat[i][1] for i in face))
        (selected if overlaps(bounds,box) else untouched).append(face)
    if not selected:return flat,faces,origins,0,len(untouched)
    loops=perimeter([(x,y,0) for x,y in flat],selected)
    signs=[1 if area([flat[i] for i in loop])>0 else -1 for loop in loops]
    boundary={i for loop in loops for i in loop};ids=sorted(boundary|{i for f in selected for i in f if any(j in protected for j in origins[i]) or not (box[0]<=flat[i][0]<=box[2] and box[1]<=flat[i][1]<=box[3])})
    local=[Vector(flat[i]) for i in ids];metadata=[origins[i] for i in ids];mapping={old:new for new,old in enumerate(ids)}
    constraints=[[mapping[i] for i in loop] for loop in loops]
    seen={tuple(round(v,6) for v in p) for p in local}
    for p in samples:
        key=tuple(round(v,6) for v in p)
        if key in seen or near_border(Vector(p))<=spacing*.1:continue
        if sum(s for loop,s in zip(loops,signs) if inside(p,[flat[i] for i in loop]))<=0:continue
        local.append(Vector(p));metadata.append([]);seen.add(key)
    tri=delaunay_2d_cdt(local,[],[f if s>0 else list(reversed(f)) for f,s in zip(constraints,signs)],1,1e-6,True)
    result=list(flat);result_origins=[list(v) for v in origins];lookup={tuple(round(x,6) for x in p):i for i,p in enumerate(flat)};index={}
    for i,p in enumerate(tri[0]):
        key=tuple(round(x,6) for x in p)
        if key in lookup:index[i]=lookup[key]
        else:index[i]=len(result);lookup[key]=index[i];result.append(tuple(p));result_origins.append([])
        for source in tri[3][i]:
            for old in metadata[source]:
                if old not in result_origins[index[i]]:result_origins[index[i]].append(old)
    new_faces=list(untouched)
    for face,owners in zip(tri[2],tri[5]):
        if sum(signs[i] for i in owners)<=0:continue
        f=[index[i] for i in face]
        if area([result[i] for i in f])<0:f.reverse()
        new_faces.append(f)
    return result,new_faces,result_origins,len(selected),len(untouched)

def merge_flat_faces(verts,faces):
    """Merge horizontal coplanar regions into simple polygons, retaining borders.
    Regions with holes are split along existing edges; no seam vertex is removed.
    """
    groups={};kept=[]
    for i,f in enumerate(faces):
        z=[verts[j][2] for j in f]
        if max(z)-min(z)<1e-8:groups.setdefault(round(z[0],8),[]).append(i)
        else:kept.append(f)
    edge_faces={}
    for ids in groups.values():
        for i in ids:
            f=faces[i]
            for a,b in zip(f,f[1:]+f[:1]):edge_faces.setdefault(tuple(sorted((a,b))),[]).append(i)
    neighbors={i:set() for ids in groups.values() for i in ids}
    for ids in edge_faces.values():
        if len(ids)==2:neighbors[ids[0]].add(ids[1]);neighbors[ids[1]].add(ids[0])
    def components(ids):
        todo=set(ids)
        while todo:
            first=todo.pop();found={first};stack=[first]
            while stack:
                for n in neighbors[stack.pop()] & todo:todo.remove(n);found.add(n);stack.append(n)
            yield found
    def merge(ids,depth=0):
        if len(ids)==1:kept.append(faces[next(iter(ids))]);return
        try:loops=perimeter(verts,[faces[i] for i in ids])
        except ValueError:loops=[]
        if len(loops)==1 and len(loops[0])<=2048:kept.append(loops[0]);return
        if depth>=16:kept.extend(faces[i] for i in ids);return
        centers={i:tuple(sum(verts[j][k] for j in faces[i])/len(faces[i]) for k in (0,1)) for i in ids}
        axis=max((0,1),key=lambda k:max(p[k] for p in centers.values())-min(p[k] for p in centers.values()))
        ordered=sorted(ids,key=lambda i:centers[i][axis]);mid=len(ordered)//2
        for subset in (ordered[:mid],ordered[mid:]):
            for part in components(subset):merge(part,depth+1)
    for ids in groups.values():
        for part in components(ids):merge(part)
    return kept
