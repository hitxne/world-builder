"""Engine-neutral pilot. Meters; +N is tangent-left. No bpy dependency."""
import math, json, copy
VERSION=1
CARDINAL_ORDER=('NW','NE','SW','SE')
def meters(value,unit='m'):
    return value*{'m':1,'ft':0.3048,'in':0.0254}[unit]
def validate(graph):
    if graph.get('version')!=VERSION: raise ValueError('Unsupported schema version')
    ids=[]
    for kind in ('roads','lanes','intersections','crosswalks'):
        ids.extend(x['id'] for x in graph.get(kind,[]))
    for x in graph.get('intersections',[]): ids.extend(c['id'] for c in x.get('corners',{}).values())
    for x in graph.get('crosswalks',[]): ids.extend(e['id'] for e in x['endpoints'].values())
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate persistent ID')
    for road in graph.get('roads',[]):
        if len(road['points'])<2: raise ValueError('Road needs two points')
        for key in ('left','right'):
            if any(w[1]<=0 for w in road[key]): raise ValueError('Width must be positive')
    return graph

def loads(text): return validate(json.loads(text))
def dumps(graph): return json.dumps(validate(graph),indent=2,sort_keys=True)
def width_at(keys,s):
    keys=sorted(keys)
    if s<=keys[0][0]: return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if s<=b: return x+(y-x)*(s-a)/(b-a)
    return keys[-1][1]
def stations(points,step=1):
    if step<=0: raise ValueError('Positive sampling step required')
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]
    if any(x<=1e-8 for x in lengths): raise ValueError('Coincident control points')
    total=sum(lengths); n=max(1,math.ceil(total/step)); seg=0; base=0
    for i in range(n+1):
        s=total*i/n
        while seg<len(lengths)-1 and s>base+lengths[seg]: base+=lengths[seg];seg+=1
        a,b=points[seg:seg+2]; t=(s-base)/lengths[seg]
        tangent=tuple((b[j]-a[j])/lengths[seg] for j in range(3))
        xy=math.hypot(tangent[0],tangent[1])
        if xy<1e-8: raise ValueError('Vertical alignment has no lateral frame')
        normal=(-tangent[1]/xy,tangent[0]/xy,0)
        yield s,tuple(a[j]+t*(b[j]-a[j]) for j in range(3)),normal

def road_mesh(road,step=1):
    verts=[];uv=[];faces=[]
    for s,p,n in stations(road['points'],step):
        for sign,key in ((1,'left'),(-1,'right')):
            offset=sign*width_at(road[key],s)
            verts.append(tuple(p[j]+offset*n[j] for j in range(2))+(p[2]-abs(offset)*road.get('crossfall',0),))
            uv.append((offset,s))
    for i in range(len(verts)//2-1): faces.append((2*i,2*i+1,2*i+3,2*i+2))
    # Surface-only mesh: open perimeter intentional. Detect folds/inversion in XY.
    for face in faces:
        a,b,c=[verts[k] for k in face[:3]]
        if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<=1e-9:
            raise ValueError('Folded or degenerate road surface; refine alignment/width')
    return verts,faces,uv

def corner_arc(vertex,ray_a,ray_b,radius,count=24):
    """Circular fillet between rays pointing AWAY from corner; rejects invalid angles."""
    if radius<=0: raise ValueError('Positive corner radius required')
    def norm(v):
        l=math.hypot(*v)
        if l<1e-9: raise ValueError('Zero ray')
        return tuple(x/l for x in v)
    a,b=norm(ray_a),norm(ray_b); theta=math.acos(max(-1,min(1,sum(x*y for x,y in zip(a,b)))))
    if theta<1e-5 or theta>math.pi-1e-5: raise ValueError('Invalid fillet angle')
    d=radius/math.tan(theta/2); bis=norm(tuple(a[i]+b[i] for i in range(2)))
    center=tuple(vertex[i]+bis[i]*radius/math.sin(theta/2) for i in range(2))
    start=tuple(vertex[i]+a[i]*d for i in range(2)); end=tuple(vertex[i]+b[i]*d for i in range(2))
    aa=math.atan2(start[1]-center[1],start[0]-center[0]);bb=math.atan2(end[1]-center[1],end[0]-center[0]);delta=(bb-aa+math.pi)%(2*math.pi)-math.pi
    return [(center[0]+radius*math.cos(aa+delta*i/count),center[1]+radius*math.sin(aa+delta*i/count),vertex[2]) for i in range(count+1)]

def move_endpoint(graph,crosswalk_id,endpoint,position):
    result=copy.deepcopy(graph)
    cross=next(x for x in result['crosswalks'] if x['id']==crosswalk_id)
    cross['endpoints'][endpoint]['position']=list(position);cross['endpoints'][endpoint]['mode']='manual'
    return result

def ramp_mesh(endpoint):
    """Depressed center and independently sloped side shoulders; rectangular pilot."""
    w=endpoint['opening_width']; l=endpoint['transition_left'];r=endpoint['transition_right'];run=endpoint['run'];h=endpoint['height']
    if min(w,l,r,run)<=0: raise ValueError('Positive ramp dimensions required')
    xs=[-w/2-l,-w/2,w/2,w/2+r]; verts=[]
    angle=endpoint.get('rotation',0);ca=math.cos(angle);sa=math.sin(angle);p=endpoint['position']
    for y in (0,run):
        for i,x in enumerate(xs):
            z=h if y==run or i in (0,3) else 0
            verts.append((p[0]+x*ca-y*sa,p[1]+x*sa+y*ca,p[2]+z))
    return verts,[(i,i+1,i+5,i+4) for i in range(3)]
def warnings(graph):
    result=[]
    for cross in graph.get('crosswalks',[]):
        for key,e in cross['endpoints'].items():
            if e['height']/e['run']>1/12: result.append(f"{e['id']}: running slope exceeds selected 1:12 reference")
            if e['height']/min(e['transition_left'],e['transition_right'])>0.1: result.append(f"{e['id']}: shoulder exceeds selected 1:10 reference")
    return result
