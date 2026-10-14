"""Balanced terrain cells, quad patches, and matching generated road seams."""
import math,hashlib,json
from .adaptive_terrain import overlaps
from .surface_network import area


def cells(bounds,height,features,spacing,tolerance,brush=None,previous=None,dirty=None,coarsen=False,budget=60000):
    """Keep large flat leaves; refine affected leaves and balance adjacent sizes."""
    result=[]
    def visit(box):
        active=any(overlaps(box,f) for f in features)
        x0,y0,x1,y1=box;xm=(x0+x1)/2;ym=(y0+y1)/2;size=max(x1-x0,y1-y0)
        local=spacing
        brushed=brush and overlaps(box,brush[:4])
        if brushed:local=max(.25,min(spacing,brush[4]/6))
        error=0.
        if active or brushed:
            z=[height(x0,y0),height(x1,y0),height(x1,y1),height(x0,y1)]
            tests=[(xm,ym,sum(z)/4),(xm,y0,(z[0]+z[1])/2),(x1,ym,(z[1]+z[2])/2),(xm,y1,(z[2]+z[3])/2),(x0,ym,(z[3]+z[0])/2)]
            error=max(abs(height(x,y)-expected) for x,y,expected in tests)
        if (active or brushed) and size>local and (size>2*local or error>tolerance):
            for child in children(box):visit(child)
        else:result.append(box)
        if len(result)>budget:raise ValueError('Terrain quad cell budget exceeded; increase detail spacing')
    if previous and dirty and not coarsen:
        for box in previous:
            if overlaps(box,dirty):visit(box)
            else:result.append(box)
    else:visit(bounds)
    return balance(result,budget)


def children(box):
    x0,y0,x1,y1=box;xm=(x0+x1)/2;ym=(y0+y1)/2
    return [(x0,y0,xm,ym),(xm,y0,x1,ym),(xm,ym,x1,y1),(x0,ym,xm,y1)]


def balance(boxes,budget=60000):
    """2:1 closure stops a coarse cell from forming a long comb of narrow faces."""
    boxes=list(boxes)
    for _ in range(24):
        vertical={};horizontal={};split=set()
        for i,(x0,y0,x1,y1) in enumerate(boxes):
            vertical.setdefault(round(x0,7),[[],[]])[0].append((y0,y1,i))
            vertical.setdefault(round(x1,7),[[],[]])[1].append((y0,y1,i))
            horizontal.setdefault(round(y0,7),[[],[]])[0].append((x0,x1,i))
            horizontal.setdefault(round(y1,7),[[],[]])[1].append((x0,x1,i))
        for groups in (vertical,horizontal):
            for pair in groups.values():
                a,b=sorted(pair[0]),sorted(pair[1]);i=j=0
                while i<len(a) and j<len(b):
                    lo=max(a[i][0],b[j][0]);hi=min(a[i][1],b[j][1])
                    if hi-lo>1e-7:
                        ai,bi=a[i][2],b[j][2];sa=max(boxes[ai][2]-boxes[ai][0],boxes[ai][3]-boxes[ai][1]);sb=max(boxes[bi][2]-boxes[bi][0],boxes[bi][3]-boxes[bi][1])
                        if sa>sb*2+1e-7:split.add(ai)
                        elif sb>sa*2+1e-7:split.add(bi)
                    if a[i][1]<b[j][1]-1e-7:i+=1
                    elif b[j][1]<a[i][1]-1e-7:j+=1
                    else:i+=1;j+=1
        if not split:return sorted(boxes)
        boxes=[c for i,box in enumerate(boxes) for c in (children(box) if i in split else [box])]
        if len(boxes)>budget:raise ValueError('Balanced terrain exceeds cell budget')
    raise ValueError('Terrain balancing did not converge')


def add_cell_edges(points,boxes):
    from mathutils import Vector
    lookup={tuple(round(x,7) for x in p):i for i,p in enumerate(points)};edges=set()
    for x0,y0,x1,y1 in boxes:
        ids=[]
        for xy in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):
            key=tuple(round(x,7) for x in xy)
            if key not in lookup:lookup[key]=len(points);points.append(Vector(xy))
            ids.append(lookup[key])
        for a,b in zip(ids,ids[1:]+ids[:1]):edges.add(tuple(sorted((a,b))))
    return sorted(edges)


def quadify(flat,faces,origins):
    """Shared edge midpoints + interior centers produce only four-sided faces.

    Convex cell regions stay grid-like. Concave road-cut regions get local CDT
    support before conversion; no triangulation stretches across coarse cells.
    """
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    supported=[]
    for face in faces:
        f=list(face)
        if len(set(f))<3 or abs(area([flat[i] for i in f]))<1e-10:continue
        if area([flat[i] for i in f])<0:f.reverse()
        turns=[]
        for i in range(len(f)):
            a,b,c=[flat[f[(i+k)%len(f)]] for k in range(3)]
            turns.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
        if min(turns)>=-1e-9:supported.append(f);continue
        tri=delaunay_2d_cdt([Vector(flat[i]) for i in f],[],[list(range(len(f)))],1,1e-7,True)
        local={}
        for i,p in enumerate(tri[0]):
            if tri[3][i]:local[i]=f[tri[3][i][0]]
            else:local[i]=len(flat);flat.append(tuple(p));origins.append([])
        supported.extend([local[i] for i in t] for t,owners in zip(tri[2],tri[5]) if 0 in owners)
    result=[];midpoints={}
    for face in supported:
        center=tuple(sum(flat[i][k] for i in face)/len(face) for k in (0,1));ci=len(flat);flat.append(center);origins.append([])
        mids=[]
        for a,b in zip(face,face[1:]+face[:1]):
            edge=tuple(sorted((a,b)))
            if edge not in midpoints:
                midpoints[edge]=len(flat);flat.append(tuple((flat[a][k]+flat[b][k])/2 for k in (0,1)));origins.append([])
            mids.append(midpoints[edge])
        for i,v in enumerate(face):result.append([v,mids[i],ci,mids[i-1]])
    return flat,result,origins


def consolidate_cells(flat,faces,boxes,bounds):
    """Remove CDT support diagonals inside each adaptive cell before quadifying."""
    from .surface_network import perimeter
    x0,y0,x1,y1=bounds;lookup={};levels=set()
    for i,b in enumerate(boxes):
        level=round(math.log2((x1-x0)/(b[2]-b[0])))
        scale=2**level;key=(level,round((b[0]-x0)/(x1-x0)*scale),round((b[1]-y0)/(y1-y0)*scale))
        lookup[key]=i;levels.add(level)
    groups={};unassigned=[]
    for face in faces:
        x=sum(flat[v][0] for v in face)/len(face);y=sum(flat[v][1] for v in face)/len(face);found=None
        for level in sorted(levels):
            scale=2**level;key=(level,math.floor((x-x0)/(x1-x0)*scale),math.floor((y-y0)/(y1-y0)*scale))
            if key in lookup:found=lookup[key];break
        if found is None:unassigned.append(face)
        else:groups.setdefault(found,[]).append(face)
    result=list(unassigned)
    for group in groups.values():
        loops=perimeter(flat,group)
        # Keep the existing partition if a road makes an enclosed hole.
        if not loops or any(area([flat[i] for i in f])<=0 for f in loops):result.extend(group)
        else:result.extend(loops)
    return result


def weld_road_cuts(flat,faces,origins,road_original,spacing,near,seed_count):
    """Absorb tiny new grid intersections into existing seam vertices.

    Original seam corners stay fixed. This changes cell partitions, not the
    pavement perimeter, and removes tiny wedges next to original seam points.
    """
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    used={i for f in faces for i in f};fixed=[i for i in used if any(j in road_original for j in origins[i])]
    if not fixed:return flat,faces,origins
    tree=KDTree(len(fixed))
    for i in fixed:tree.insert(Vector((*flat[i],0)),i)
    tree.balance();replace={};limit=min(.05*spacing,.1)
    for i in used:
        if i in fixed or any(j<seed_count for j in origins[i]) or near(flat[i])>1e-5:continue
        _,target,d=tree.find(Vector((*flat[i],0)))
        if d<limit:replace[i]=target
    def loops(face):
        f=[]
        for i in face:
            if not f or f[-1]!=i:f.append(i)
        if f and f[0]==f[-1]:f.pop()
        for i,v in enumerate(f):
            if v in f[:i]:
                j=f.index(v);return loops(f[j:i])+loops(f[:j]+f[i:])
        return [f] if len(f)>=3 and abs(area([flat[i] for i in f]))>1e-10 else []
    cleaned=[]
    for f in faces:cleaned.extend(loops([replace.get(i,i) for i in f]))
    return flat,cleaned,origins


def base_mesh(helper):
    base=helper.get('roadlab_seam_base_mesh');result=helper.get('roadlab_seam_result_mesh')
    return base if base is not None and result==helper.data else helper.data


def release_seam(helper):
    import bpy
    base=helper.get('roadlab_seam_base_mesh')
    for key in ('roadlab_seam_base_mesh','roadlab_seam_result_mesh','roadlab_seam_signature'):
        if key in helper:del helper[key]
    if base is not None and base!=helper.data and base.users==0:bpy.data.meshes.remove(base)


def match_road_seams(helper,pins):
    """Split only affected generated road faces; authoring curves stay untouched."""
    import bpy,bmesh
    from mathutils import Vector
    original=base_mesh(helper)
    signature=hashlib.sha256(json.dumps([(list(e),sorted(round(t,9) for t in ts)) for e,ts in sorted(pins.items())]).encode()).hexdigest()
    if helper.get('roadlab_seam_signature')==signature and helper.get('roadlab_seam_result_mesh')==helper.data:return 0
    verts=[tuple(v.co) for v in original.vertices];insertions={};weights={}
    for edge,ts in pins.items():
        a,b=edge;entries=[]
        for t in sorted(set(round(t,9) for t in ts)):
            if t<=1e-7 or t>=1-1e-7:continue
            co=tuple(verts[a][k]+(verts[b][k]-verts[a][k])*t for k in range(3));index=len(verts);verts.append(co);weights[index]=(a,b,t);entries.append((t,index))
        if entries:insertions[edge]=entries
    if not insertions:
        previous=helper.data
        if previous!=original:
            helper.data=original
            release_seam(helper)
            if previous.users==0:bpy.data.meshes.remove(previous)
        return 0
    faces=[];parents=[];changed=[]
    for polygon in original.polygons:
        f=list(polygon.vertices);new=[]
        for a,b in zip(f,f[1:]+f[:1]):
            new.append(a);edge=tuple(sorted((a,b)));entries=insertions.get(edge,[])
            new.extend(i for t,i in (entries if edge[0]==a else list(reversed(entries))))
        faces.append(new);parents.append(polygon.index);changed.append(len(new)!=len(f))
    mesh=bpy.data.meshes.new('RoadLab Shared Seam Road');mesh.from_pydata(verts,[],faces);mesh.update()
    for material in original.materials:mesh.materials.append(material)
    for p,parent in zip(mesh.polygons,parents):p.material_index=original.polygons[parent].material_index;p.use_smooth=original.polygons[parent].use_smooth
    for attr in original.attributes:
        if not attr.name.startswith('roadlab_') or attr.domain not in ('POINT','FACE'):continue
        new=mesh.attributes.new(attr.name,attr.data_type,attr.domain)
        for i,value in enumerate(new.data):
            if attr.domain=='FACE':value.value=attr.data[parents[i]].value;continue
            if i<len(original.vertices):value.value=attr.data[i].value;continue
            a,b,t=weights[i]
            if attr.data_type=='FLOAT':value.value=attr.data[a].value*(1-t)+attr.data[b].value*t
            else:value.value=attr.data[a if t<.5 else b].value
    layer=mesh.attributes.new('roadlab_seam_changed','BOOLEAN','FACE')
    for x,v in zip(layer.data,changed):x.value=v
    bm=bmesh.new();bm.from_mesh(mesh);bm.faces.ensure_lookup_table();flag=bm.faces.layers.int.get('roadlab_seam_changed')
    # BOOLEAN face layers are exposed as integers by BMesh.
    targets=[f for f in bm.faces if flag is not None and f[flag]]
    if not targets:targets=[bm.faces[i] for i,v in enumerate(changed) if v]
    bmesh.ops.triangulate(bm,faces=targets,quad_method='BEAUTY',ngon_method='BEAUTY');bm.to_mesh(mesh);bm.free()
    if mesh.attributes.get('roadlab_seam_changed'):mesh.attributes.remove(mesh.attributes['roadlab_seam_changed'])
    uv=mesh.uv_layers.new(name='UVMap')
    uv.data.foreach_set('uv',[c for loop in mesh.loops for c in mesh.vertices[loop.vertex_index].co[:2]])
    previous=helper.data;helper['roadlab_seam_base_mesh']=original;helper.data=mesh;helper['roadlab_seam_result_mesh']=mesh;helper['roadlab_seam_signature']=signature
    if previous!=original and previous.users==0:bpy.data.meshes.remove(previous)
    return len(weights)
