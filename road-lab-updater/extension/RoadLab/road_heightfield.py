"""Engine-independent sparse road displacement field and circular brush math.
Coordinates are road-local XY metres; displacement is road-local Z metres.
The curve, topology compiler and base elevation remain authoritative.
"""
import math,json

MODES=('RAISE','LOWER','FLATTEN','SMOOTH')
def decode(encoded):
    payload=json.loads(encoded or '{}')
    return {tuple(item[:2]):item[2] for item in payload.get('heights',[])}
def encode(field):
    return json.dumps({'version':1,'cell':1.,'heights':[[*key,round(value,7)] for key,value in sorted(field.items()) if abs(value)>1e-7]},separators=(',',':'))
def sample(field,x,y):
    a,b=math.floor(x),math.floor(y);u,v=x-a,y-b
    return sum(field.get((a+i,b+j),0.)*(u if i else 1-u)*(v if j else 1-v) for i in (0,1) for j in (0,1))
def stamp(field,center,radius,strength,dt,mode,base_height,target=None):
    if mode not in MODES or radius<=0 or strength<0 or dt<0:raise ValueError('Invalid road brush settings')
    if mode=='FLATTEN' and target is None:raise ValueError('Flatten needs a target height')
    before=dict(field);result=dict(before);cache={}
    def base(key):
        if key not in cache:cache[key]=base_height(*key)
        return cache[key]
    if radius>100:raise ValueError('Road brush radius cannot exceed 100 m')
    for x in range(math.floor(center[0]-radius),math.ceil(center[0]+radius)+1):
        for y in range(math.floor(center[1]-radius),math.ceil(center[1]+radius)+1):
            distance=math.hypot(x-center[0],y-center[1])
            if distance>=radius:continue
            key=(x,y);z=base(key)
            if z is None:continue
            t=distance/radius;weight=(1-t*t)**2;amount=strength*min(dt,.1)*weight
            current=before.get(key,0.)
            if mode in ('RAISE','LOWER'):value=current+amount*(1 if mode=='RAISE' else -1)
            else:
                if mode=='SMOOTH':
                    neighbors=[(x-1,y),(x+1,y),(x,y-1),(x,y+1)]
                    valid=[base(k)+before.get(k,0.) for k in neighbors if base(k) is not None]
                    desired=sum(valid)/len(valid) if valid else z+current
                else:desired=target
                value=current+(desired-z-current)*(1-math.exp(-amount))
            if abs(value-current)>1e-8:result[key]=value
    if len(result)>150000:raise ValueError('Road sculpt field exceeds 150,000 samples')
    return result

def corner_displacement(x,y,limits,lifts):
    height=0.
    for item in limits:
        amount=lifts.get(tuple(item.get('junction',())),{}).get(item['corner'],0.)
        anchor=item.get('height_anchor')
        if not amount or not anchor or not item.get('exposed',True):continue
        r=item['height_falloff'];t=math.hypot(x-anchor[0],y-anchor[1])/r
        if t<1:height+=amount*(1-t*t)**2
    return height

def bank(field,center,tangent,radius,angle,base_height):
    """Add a lateral tilt under a smooth circular falloff to a stroke snapshot."""
    result=dict(field);angle=max(-.6,min(.6,angle));nx,ny=-tangent[1],tangent[0]
    for x in range(math.floor(center[0]-radius),math.ceil(center[0]+radius)+1):
        for y in range(math.floor(center[1]-radius),math.ceil(center[1]+radius)+1):
            dx,dy=x-center[0],y-center[1];t=math.hypot(dx,dy)/radius
            if t>=1 or base_height(x,y) is None:continue
            result[x,y]=field.get((x,y),0.)+math.tan(angle)*(dx*nx+dy*ny)*(1-t*t)**2
    return result
