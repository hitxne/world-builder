"""WB v0.2 portable geometric kernel. No commercial node data or bpy imports."""
import math,copy
from . import core
EPS=1e-8

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def norm2(a):
 l=math.hypot(a[0],a[1])
 if l<EPS:raise ValueError('Zero planar tangent')
 return (a[0]/l,a[1]/l)
def area(points):return sum(cross(a,b) for a,b in zip(points,points[1:]+points[:1]))/2

def triangulate(points):
 """Ear clipping for a simple CCW polygon; reject instead of guessing a failed topology."""
 if area(points)<=EPS:raise ValueError('Polygon must be CCW')
 remaining=list(range(len(points)));tri=[]
 def inside(p,a,b,c):return min(cross(sub(b,a),sub(p,a)),cross(sub(c,b),sub(p,b)),cross(sub(a,c),sub(p,c)))>=-EPS
 while len(remaining)>3:
  found=False
  for i,b in enumerate(remaining):
   a=remaining[i-1];c=remaining[(i+1)%len(remaining)]
   if cross(sub(points[b],points[a]),sub(points[c],points[b]))<=EPS:continue
   if any(inside(points[k],points[a],points[b],points[c]) for k in remaining if k not in (a,b,c)):continue
   tri.append((a,b,c));remaining.pop(i);found=True;break
  if not found:raise ValueError('Cannot triangulate polygon; overlapping edges or degenerate corners')
 tri.append(tuple(remaining));return tri

def mesh_spec(id,category,verts,faces,material,**metadata):
 return dict(id=id,category=category,verts=[tuple(x) for x in verts],faces=[tuple(x) for x in faces],material=material,metadata=metadata)
def solid_polygon(id,points,material,depth=.2,category='road'):
 n=len(points);tri=triangulate(points);v=list(points)+[(x,y,z-depth) for x,y,z in points]
 f=tri+[tuple(k+n for k in reversed(t)) for t in tri]+[(i,i+n,(i+1)%n+n,(i+1)%n) for i in range(n)]
 return mesh_spec(id,category,v,f,material)

def line_intersection(p,a,q,b):
 det=cross(a,b)
 if abs(det)<EPS:raise ValueError('Parallel adjacent approaches')
 t=cross(sub(q,p),b)/det
 return (p[0]+t*a[0],p[1]+t*a[1])
def approach_frame(junction,approach):
 angle=approach['bearing'];t=(math.cos(angle),math.sin(angle));n=(-t[1],t[0]);center=junction.get('center',[0,0,0]);offset=approach.get('offset',0)
 p=(center[0]+offset*n[0],center[1]+offset*n[1],center[2])
 return p,t,n

def junction_boundary(junction,spacing=.5):
 approaches=sorted(junction['approaches'],key=lambda x:x['bearing']%(2*math.pi));chains=[];polygon=[]
 if len(approaches)<3:raise ValueError('Junction requires at least three approaches')
 for i,a in enumerate(approaches):
  b=approaches[(i+1)%len(approaches)];pa,ta,na=approach_frame(junction,a);pb,tb,nb=approach_frame(junction,b)
  ap=(pa[0]+na[0]*a['half_width'],pa[1]+na[1]*a['half_width']);bp=(pb[0]-nb[0]*b['half_width'],pb[1]-nb[1]*b['half_width'])
  corner=next(c for c in junction['corners'].values() if c['approach_pair']==[a['id'],b['id']])
  v=line_intersection(ap,ta,bp,tb);radius=corner['radius'];arc=core.corner_arc((*v,pa[2]),ta,tb,radius,max(12,math.ceil(radius*math.pi/spacing)))
  far_a=(ap[0]+ta[0]*a['length'],ap[1]+ta[1]*a['length'],pa[2]);far_b=(bp[0]+tb[0]*b['length'],bp[1]+tb[1]*b['length'],pb[2])
  if sum((arc[0][k]-ap[k])*ta[k] for k in range(2))>=a['length']-1:raise ValueError(f"{corner['id']}: radius exceeds approach length")
  if sum((arc[-1][k]-bp[k])*tb[k] for k in range(2))>=b['length']-1:raise ValueError(f"{corner['id']}: radius exceeds approach length")
  raw=[far_a]+arc+[far_b];path=[]
  # distance sampling includes original arc points, precise joins
  for start,end in zip(raw,raw[1:]):
   count=max(1,math.ceil(math.dist(start,end)/spacing))
   for k in range(count):path.append(tuple(start[j]+(end[j]-start[j])*k/count for j in range(3)))
  path.append(far_b)
  chains.append(dict(id=corner['id'],label=corner['label'],points=path,approach_pair=corner['approach_pair']))
  # CCW road polygon includes previous approach cap from far-right to far-left.
  polygon.extend(path)
 if area(polygon)<0:raise ValueError('Approaches have invalid winding')
 return polygon,chains

def resolve_endpoint(junction,endpoint):
 e=copy.deepcopy(endpoint)
 if e.get('mode','auto')=='manual' and 'position' in e:return e
 approach=next(a for a in junction['approaches'] if a['id']==e['approach_id']);p,t,n=approach_frame(junction,approach);side=e['side'];station=e['station'];out=(n[0]*side,n[1]*side)
 e['position']=[p[0]+t[0]*station+out[0]*approach['half_width'],p[1]+t[1]*station+out[1]*approach['half_width'],p[2]]
 # local +Y extends AWAY from roadway, local -Y faces the crosswalk.
 e['rotation']=math.atan2(-out[0],out[1])+e.get('rotation_offset',0)
 return e

def path_stations(points):
 s=[0.]
 for a,b in zip(points,points[1:]):s.append(s[-1]+math.dist(a,b))
 return s

def nearest_station(points,p):
 best=(float('inf'),0);s=0
 for a,b in zip(points,points[1:]):
  d=sub(b,a);l=math.dist(a,b);u=max(0,min(1,sum((p[k]-a[k])*d[k] for k in range(3))/(l*l)))
  q=tuple(a[k]+u*d[k] for k in range(3));candidate=(math.dist(q,p),s+u*l)
  if candidate[0]<best[0]:best=candidate
  s+=l
 return best

def depression(delta,e):
 half=e['opening_width']/2
 if -half<=delta<=half:return 1.
 length=e['transition_left'] if delta<0 else e['transition_right']
 return max(0,1-(abs(delta)-half)/max(EPS,length))

def path_frame(points,i):
 # Outward normal for a CCW road boundary is tangent-right.
 if i==0:t=norm2(sub(points[1],points[0]))
 elif i==len(points)-1:t=norm2(sub(points[-1],points[-2]))
 else:
  a=norm2(sub(points[i],points[i-1]));b=norm2(sub(points[i+1],points[i]));t=norm2((a[0]+b[0],a[1]+b[1]))
 return t,(t[1],-t[0])

def ribbon(id,points,profile,material,height_fn=None,category='curb',thickness=.12):
 v=[];stations=path_stations(points);cols=len(profile)
 for i,p in enumerate(points):
  t,n=path_frame(points,i)
  for offset,z in profile:
   value=height_fn(stations[i],offset,z) if height_fn else z
   v.append((p[0]+n[0]*offset,p[1]+n[1]*offset,p[2]+value))
 f=[]
 for i in range(len(points)-1):
  for k in range(cols-1):
   a=i*cols+k;f.append((a,a+1,a+cols+1,a+cols))
 if thickness:
  # Closed bottom and side walls, even through ramps. Bottom follows top minus thickness.
  count=len(v);v+= [(x,y,z-thickness) for x,y,z in v]
  f+= [tuple(x+count for x in reversed(face)) for face in list(f)]
  boundary=list(range(cols))+[i*cols+cols-1 for i in range(1,len(points))]+list(range((len(points)-1)*cols+cols-2,(len(points)-1)*cols-1,-1))+[i*cols for i in range(len(points)-2,0,-1)]
  for a,b in zip(boundary,boundary[1:]+boundary[:1]):f.append((a,a+count,b+count,b))
 return mesh_spec(id,category,v,f,material)

def curb_sidewalk(chain,endpoints,settings):
 points=chain['points'];h=settings['curb_height'];sw=settings['sidewalk_width'];active=[]
 for e in endpoints:
  dist,s=nearest_station(points,e['position'])
  if dist<.15:active.append((s,e))
 # endpoints are anchors on this chain. Insert section breaks to preserve exact opening widths.
 stations=path_stations(points);extra=[]
 for s,e in active:extra.extend([s-e['opening_width']/2-e['transition_left'],s-e['opening_width']/2,s,s+e['opening_width']/2,s+e['opening_width']/2+e['transition_right']])
 for target in sorted(extra):
  if target<=0 or target>=stations[-1]:continue
  if min(abs(target-x) for x in stations)<1e-6:continue
  for i,(a,b) in enumerate(zip(stations,stations[1:])):
   if a<target<b:
    u=(target-a)/(b-a);p=tuple(points[i][k]+u*(points[i+1][k]-points[i][k]) for k in range(3));points=points[:i+1]+[p]+points[i+1:];stations=path_stations(points);break
 def height(s,offset,z):
  effect=0
  for anchor,e in active:effect=max(effect,depression(s-anchor,e)*max(0,1-max(0,offset)/e['run']))
  return z*(1-effect)
 curb=ribbon('curb-'+chain['id'],points,[(0,0),(.12,h),(.32,h)],'concrete',height)
 # profile subdivided outward so ramps have proper center run and landing break.
 offsets=sorted(set([.32,sw+.32]+[min(sw+.32,max(.32,e['run'])) for _,e in active]))
 sidewalk=ribbon('sidewalk-'+chain['id'],points,[(x,h) for x in offsets],'sidewalk',height,category='sidewalk')
 gutter=ribbon('gutter-'+chain['id'],points,[(-.3,.006),(0,.006)],'gutter',category='gutter',thickness=.04)
 for spec in (curb,sidewalk,gutter):spec['metadata'].update(corner_id=chain['id'],label=chain['label'])
 return [curb,sidewalk,gutter]

def crosswalk_mesh(crosswalk,endpoints):
 a,b=(endpoints[x]['position'] for x in ('A','B'));d=sub(b,a);length=math.hypot(d[0],d[1]);t=norm2(d);n=(-t[1],t[0]);w=crosswalk['width'];stripe=crosswalk.get('stripe_width',.45);gap=crosswalk.get('stripe_gap',.45)
 if length<.5:raise ValueError('Crosswalk endpoints too close')
 verts=[];faces=[]
 # white bars extend along pedestrian travel, distributed transversely across width.
 count=max(1,math.floor((length+gap)/(stripe+gap)));used=count*stripe+(count-1)*gap
 for i in range(count):
  station=(length-used)/2+i*(stripe+gap);corners=[(station,-w/2),(station+stripe,-w/2),(station+stripe,w/2),(station,w/2)];start=len(verts)
  verts.extend((a[0]+t[0]*x+n[0]*y,a[1]+t[1]*x+n[1]*y,a[2]+(b[2]-a[2])*x/length+.012) for x,y in corners);faces.append(tuple(range(start,start+4)))
 return mesh_spec('marking-'+crosswalk['id'],'marking',verts,faces,'white',crosswalk_id=crosswalk['id'])

def warning_panel(e):
 w=min(e['opening_width'],e.get('warning_width',e['opening_width']));depth=e.get('warning_depth',.61);ca=math.cos(e['rotation']);sa=math.sin(e['rotation']);p=e['position']
 verts=[]
 for x,y in [(-w/2,.08),(w/2,.08),(w/2,.08+depth),(-w/2,.08+depth)]:
  verts.append((p[0]+ca*x-sa*y,p[1]+sa*x+ca*y,p[2]+e['height']*min(1,y/e['run'])+.006))
 return mesh_spec('warning-'+e['id'],'warning',verts,[(0,1,2,3)],'warning',endpoint_id=e['id'],rotation=e['rotation'])

def bezier_path(p0,p1,t0,t1,samples=40):
 distance=math.dist(p0,p1);scale=distance*.45
 a=tuple(p0[k]+t0[k]*scale for k in range(3));b=tuple(p1[k]-t1[k]*scale for k in range(3))
 return [tuple((1-u)**3*p0[k]+3*(1-u)**2*u*a[k]+3*(1-u)*u*u*b[k]+u**3*p1[k] for k in range(3)) for u in [i/samples for i in range(samples+1)]]

def lane_paths(junction):
 specs=[];lanes={x['id']:x for x in junction.get('lanes',[])}
 def endpoint(lane):
  ap=next(x for x in junction['approaches'] if x['id']==lane['approach_id']);p,t,n=approach_frame(junction,ap);s=lane.get('connection_station',22);offset=lane['offset'];pos=(p[0]+t[0]*s+n[0]*offset,p[1]+t[1]*s+n[1]*offset,p[2]+.035)
  direction=-1 if lane['travel']=='incoming' else 1
  return pos,(*[direction*v for v in t],0)
 for movement in junction.get('movements',[]):
  incoming=lanes[movement['from']];outgoing=lanes[movement['to']]
  if incoming['travel']!='incoming' or outgoing['travel']!='outgoing':raise ValueError('Movement must connect incoming to outgoing')
  p,t=endpoint(incoming);q,u=endpoint(outgoing);points=bezier_path(p,q,t,u)
  specs.append(dict(id=movement['id'],category='guide',points=points,material='guide',metadata={'from_lane':incoming['id'],'to_lane':outgoing['id'],'movement':movement['type']}))
 return specs

def build_junction(graph):
 j=graph['junction'];settings=graph['settings'];polygon,chains=junction_boundary(j,settings.get('sample_spacing',.5));specs=[solid_polygon('junction-'+j['id'],polygon,'asphalt')];endpoints=[];resolved={};diagnostics=[]
 for crosswalk in graph['crosswalks']:
  ends={key:resolve_endpoint(j,e) for key,e in crosswalk['endpoints'].items()};resolved[crosswalk['id']]=ends;endpoints.extend(ends.values());specs.append(crosswalk_mesh(crosswalk,ends))
  for e in ends.values():
   e['height']=settings['curb_height'];specs.append(warning_panel(e));specs.append(warning_domes(e))
   dist=min(nearest_station(c['points'],e['position'])[0] for c in chains)
   if dist>.15:diagnostics.append(f"{e['id']}: manual endpoint is {dist:.2f}m from curb; opening cannot be attached")
   if e['run']>settings['sidewalk_width']+.32:diagnostics.append(f"{e['id']}: ramp run exceeds sidewalk strip; landing incomplete")
   if e['height']/e['run']>1/12:diagnostics.append(f"{e['id']}: slope exceeds selected 1:12 reference")
 for c in chains:specs.extend(curb_sidewalk(c,endpoints,settings))
 specs.extend(lane_paths(j))
 return specs,diagnostics,resolved

# Divided-road fixture uses fixed outer edges and a pocket that consumes median space.
def boulevard_sections(road):
 length=road['length'];step=road.get('sample_spacing',1);samples=sorted(set([i*length/math.ceil(length/step) for i in range(math.ceil(length/step)+1)]+[road['pocket_start'],road['pocket_start']+road['taper_length'],road['pocket_end']]))
 result=[]
 for s in samples:
  factor=max(0,min(1,(s-road['pocket_start'])/road['taper_length'])) if s<=road['pocket_end'] else max(0,1-(s-road['pocket_end'])/road['taper_length'])
  pocket=road['lane_width']*factor;result.append((s,-road['median_width']/2,road['median_width']/2-pocket))
 return result

def build_boulevard(graph):
 road=graph['boulevard'];sections=boulevard_sections(road);offset=road.get('origin',[0,0,0]);angle=road.get('bearing',0);t=(math.cos(angle),math.sin(angle));n=(-t[1],t[0]);lane=road['lane_width'];outer=road['median_width']/2+2*lane;specs=[]
 def convert(s,y,z=0):return (offset[0]+t[0]*s+n[0]*y,offset[1]+t[1]*s+n[1]*y,offset[2]+z)
 # Continuous pavement continues through the median termination and turn-lane opening.
 specs.append(solid_polygon('boulevard-pavement',[convert(0,-outer),convert(road['length'],-outer),convert(road['length'],outer),convert(0,outer)],'asphalt'))
 end=road.get('median_end',road['length']-12);nose_length=road.get('nose_length',4);nose_start=end-nose_length
 if not 0<nose_start<end<=road['length']:raise ValueError('Invalid median end or nose length')
 rows=[row for row in sections if row[0]<nose_start]
 # sample exact nose start from independently variable median boundaries
 a=-road['median_width']/2;b=core.width_at([[row[0],row[2]] for row in sections],nose_start);rows.append((nose_start,a,b));mid=(a+b)/2;half=(b-a)/2
 if half<.2:raise ValueError('Median nose is too narrow')
 nose=[]
 shape=road.get('nose_shape','rounded')
 if shape=='rounded':
  for i in range(33):
   theta=math.pi*i/32;nose.append(convert(nose_start+nose_length*math.sin(theta),mid-half*math.cos(theta),.08))
 else:nose=[convert(nose_start,a,.08),convert(end,mid,.08),convert(nose_start,b,.08)]
 median=[convert(s,a,.08) for s,a,b in rows]+nose[1:]+[convert(s,b,.08) for s,a,b in reversed(rows[:-1])]
 specs.append(solid_polygon('median-'+road['id'],median,road.get('median_material','grass'),depth=.16,category='median'))
 curb_path=[(x,y,z-.08) for x,y,z in median]+[(median[0][0],median[0][1],0)]
 specs.append(ribbon('median-curb-'+road['id'],curb_path,[(0,.08),(.12,.1524),(.24,.1524)],'concrete'))
 # Boundary metadata is separate from unified pavement; used for future lane export.
 for name,index,bound in [('opposing',1,-outer),('pocket-side',2,outer)]:
  points=[convert(sec[0],sec[index],.04) for sec in sections]
  specs.append(dict(id='boulevard-'+name,category='guide',points=points,material='guide',metadata={'fixed_outer_edge':bound,'carriageway':name}))
 # Yellow inner-edge lines stop before the nose and retain the selected pocket taper.
 for sign,index in [(-1,1),(1,2)]:
  points=[convert(sec[0],sec[index]+sign*.38,.012) for sec in rows]
  if sign==-1:points.reverse()
  specs.append(ribbon('median-edge-stripe-'+str(sign),points,[(-.06,0),(.06,0)],'yellow',category='marking',thickness=0))
 # fixed outside sidewalk/curbs
 for sign in (-1,1):
  points=[convert(sec[0],sign*outer,0) for sec in sections]
  if sign==1:points.reverse()
  specs.append(ribbon('outer-curb-'+str(sign),points,[(0,0),(.12,.1524),(.32,.1524)],'concrete'))
  specs.append(ribbon('outer-sidewalk-'+str(sign),points,[(.32,.1524),(2.72,.1524)],'sidewalk',category='sidewalk'))
 # longitudinal lane stripes, derived from current lane width. Context dimensions configurable.
 for sign in (-1,1):
  for s in range(0,int(road['length'])-3,9):
   points=[convert(s,sign*(road['median_width']/2+lane),.012),convert(s+3,sign*(road['median_width']/2+lane),.012)]
   specs.append(ribbon('lane-stripe-'+str(sign)+'-'+str(s),points,[(-.06,0),(.06,0)],'white',category='marking',thickness=0))
 return specs,[],{}


def warning_domes(e):
 """Configurable truncated domes, illustrative geometry rather than certification."""
 w=min(e['opening_width'],e.get('warning_width',e['opening_width']));depth=e.get('warning_depth',.61);pitch=e.get('dome_pitch',.06);base=e.get('dome_base_diameter',.023)/2;top=e.get('dome_top_diameter',.012)/2;height=e.get('dome_height',.0051)
 ca=math.cos(e['rotation']);sa=math.sin(e['rotation']);p=e['position'];verts=[];faces=[]
 nx=max(1,int((w-.04)/pitch));ny=max(1,int((depth-.04)/pitch))
 if nx*ny>4000:raise ValueError('Warning panel exceeds 4000 dome budget')
 for ix in range(nx):
  for iy in range(ny):
   x=(ix-(nx-1)/2)*pitch;y=.08+depth/2+(iy-(ny-1)/2)*pitch;start=len(verts)
   for radius,zz in ((base,0),(top,height)):
    for k in range(8):
     xx=x+radius*math.cos(k*math.pi/4);yy=y+radius*math.sin(k*math.pi/4);z=e['height']*min(1,yy/e['run'])+.0063+zz
     verts.append((p[0]+ca*xx-sa*yy,p[1]+sa*xx+ca*yy,p[2]+z))
   faces.append(tuple(start+k for k in reversed(range(8))));faces.append(tuple(start+8+k for k in range(8)))
   faces.extend((start+k,start+(k+1)%8,start+8+(k+1)%8,start+8+k) for k in range(8))
 return mesh_spec('domes-'+e['id'],'warning-domes',verts,faces,'warning',endpoint_id=e['id'])

def auxiliary_width(road,s,side):
 total=0
 for lane in road.get('outer_turns',[]):
  if lane['side']!=side:continue
  keys=[[lane['start'],0],[lane['start']+lane['taper'],lane['width']],[lane['end']-lane['taper_out'],lane['width']],[lane['end'],0]]
  total+=core.width_at(keys,s)
 return total

def build_arterial(graph):
 """Independent outside pockets, a continuous median, bike bands and staggered driveways."""
 r=graph['boulevard'];settings=graph['settings'];length=r['length'];lane=r['lane_width'];median=r['median_width'];bike=r.get('bike_width',1.5);base=median/2+r.get('through_lanes',3)*lane+bike
 keys=set([float(x) for x in range(int(length)+1)])
 for a in r['outer_turns']:keys.update([a['start'],a['start']+a['taper'],a['end']-a['taper_out'],a['end']])
 samples=sorted(keys);offset=r.get('origin',[0,0,0]);angle=r.get('bearing',0);t=(math.cos(angle),math.sin(angle));n=(-t[1],t[0])
 def co(s,y,z=0):return (offset[0]+t[0]*s+n[0]*y,offset[1]+t[1]*s+n[1]*y,offset[2]+z)
 left=[co(s,base+auxiliary_width(r,s,1)) for s in samples];right=[co(s,-base-auxiliary_width(r,s,-1)) for s in samples]
 specs=[solid_polygon('arterial-'+r['id'],right+list(reversed(left)),'asphalt')]
 # Straight median is separate from outside lane transitions.
 median_poly=[co(0,-median/2,.08),co(length,-median/2,.08),co(length,median/2,.08),co(0,median/2,.08)]
 specs.append(solid_polygon('arterial-median',median_poly,'grass',depth=.16,category='median'))
 for side in (-1,1):
  median_points=[co(s,side*median/2,0) for s in samples]
  if side==1:median_points.reverse()
  specs.append(ribbon('arterial-median-curb-'+str(side),median_points,[(0,.08),(.12,.1524),(.24,.1524)],'concrete'))
  outside=list(reversed(left)) if side==1 else right;endpoints=[]
  for driveway in r['driveways']:
   if driveway['side']!=side:continue
   station=driveway['station'];edge=side*(base+auxiliary_width(r,station,side));p=co(station,edge)
   endpoint={'id':driveway['id'],'position':p,'opening_width':driveway['width'],'transition_left':1.5,'transition_right':1.5,'height':settings['curb_height'],'run':settings['sidewalk_width']+.32}
   endpoints.append(endpoint)
   # road-aligned mouth to setback driveway; extra depth begins beyond sidewalk.
   w=driveway['width'];back=edge+side*(settings['sidewalk_width']+.32);outer=back+side*driveway.get('depth',10)
   poly=[co(station-w/2,back,settings['curb_height']),co(station+w/2,back,settings['curb_height']),co(station+w/2,outer,settings['curb_height']),co(station-w/2,outer,settings['curb_height'])]
   if area(poly)<0:poly.reverse()
   specs.append(solid_polygon('driveway-'+driveway['id'],poly,'asphalt',category='driveway'))
  chain={'id':'arterial-outer-'+str(side),'label':str(side),'points':outside}
  specs.extend(curb_sidewalk(chain,endpoints,settings))
  # independent, direction-aware lane lines and bike corridor
  through=r.get('through_lanes',3)
  for index in range(1,through):
   y=side*(median/2+index*lane)
   for s in range(0,int(length)-3,9):
    points=[co(s,y,.012),co(s+3,y,.012)]
    specs.append(ribbon('arterial-line-'+str(side)+'-'+str(index)+'-'+str(s),points,[(-.06,0),(.06,0)],'white',category='marking',thickness=0))
  bike_center=side*(median/2+through*lane+bike/2)
  for driveway in r['driveways']:
   if driveway['side']==side:
    station=driveway['station'];poly=[co(station-5,bike_center-bike/2,.009),co(station+5,bike_center-bike/2,.009),co(station+5,bike_center+bike/2,.009),co(station-5,bike_center+bike/2,.009)]
    specs.append(solid_polygon('bike-green-'+driveway['id'],poly,'bike-green',depth=.004,category='marking'))
  for off in (-bike/2,bike/2):
   points=[co(s,bike_center+off,.014) for s in samples]
   specs.append(ribbon('bike-edge-'+str(side)+'-'+str(off),points,[(-.045,0),(.045,0)],'white',category='marking',thickness=0))
 return specs,[],{}

def solid_strip(id,points,width):
 road={'points':points,'left':[[0,width/2]],'right':[[0,width/2]],'crossfall':0};v,f,uv=core.road_mesh(road,.7);count=len(v);faces=list(f)+[tuple(x+count for x in reversed(face)) for face in f];verts=v+[(x,y,z-.2) for x,y,z in v]
 boundary=[0,1]+list(range(3,count,2))+[count-2]+list(range(count-4,0,-2))
 for a,b in zip(boundary,boundary[1:]+boundary[:1]):faces.append((a,a+count,b+count,b))
 return mesh_spec(id,'road',verts,faces,'asphalt',union_group='interchange')

def build_interchange(graph):
 r=graph['interchange'];lw=r['lane_width'];median=r['median_width'];length=r['length'];split=r['split_station'];merge=r['merge_station'];taper=r['taper_length'];base=median/2+2*lw
 main={'points':[[-length/2,0,0],[length/2,0,0]],'left':[[0,base+lw],[merge,base+lw],[merge+taper,base],[length,base]],'right':[[0,base+lw],[split,base+lw],[split+taper,base],[length,base]],'crossfall':0}
 v,f,u=core.road_mesh(main,.7);count=len(v);verts=v+[(x,y,z-.2) for x,y,z in v];faces=f+[tuple(x+count for x in reversed(face)) for face in f];boundary=[0,1]+list(range(3,count,2))+[count-2]+list(range(count-4,0,-2))
 for a,b in zip(boundary,boundary[1:]+boundary[:1]):faces.append((a,a+count,b+count,b))
 specs=[mesh_spec('interchange-main','road',verts,faces,'asphalt',union_group='interchange')]
 split_x=-length/2+split;merge_x=-length/2+merge;lane_offset=median/2+2.5*lw
 off=bezier_path((split_x,-lane_offset,0),(split_x+r['ramp_length'],-lane_offset-r['ramp_offset'],0),(1,0,0),(1,-.6,0),80)
 on=bezier_path((merge_x+r['ramp_length'],lane_offset+r['ramp_offset'],0),(merge_x,lane_offset,0),(-1,-.6,0),(-1,0,0),80)
 specs.append(solid_strip('interchange-off-ramp',off,lw));specs.append(solid_strip('interchange-on-ramp',on,lw))
 turn_x=-length/2+r.get('turn_station',merge);setback=r.get('median_setback',12)
 # Separate islands: the far nose is pulled back independently of ramp attachment.
 def island(id,start,end,rounded_end):
  radius=median/2;points=[(start,-radius,.08)]
  for i in range(33):
   a=-math.pi/2+math.pi*i/32;points.append((end-radius+radius*math.cos(a),radius*math.sin(a),.08))
  points.append((start,radius,.08))
  return solid_polygon(id,points,'grass',category='median',depth=.16)
 lower_end=turn_x-2;far_start=turn_x+setback
 specs.append(island('interchange-near-median',-length/2,lower_end,True))
 upper=island('interchange-far-median',-length/2,-far_start,True)
 upper['verts']=[(-x,-y,z) for x,y,z in upper['verts']];specs.append(upper)
 # Opposing turn lane feeds the same ramp, with its own editable lane connection.
 connector=bezier_path((turn_x+18,median/2+lw/2,0),(split_x+28,-lane_offset-12,0),(-1,0,0),(.85,-.4,0),64)
 specs.append(solid_strip('interchange-opposing-turn-connector',connector,lw))
 # A U-turn movement guide is permitted through the withdrawn median gap.
 uturn=bezier_path((turn_x+8,median/2+lw/2,.04),(turn_x+8,-median/2-lw/2,.04),(-1,0,0),(1,0,0),50)
 specs.append(dict(id='interchange-uturn',category='guide',points=uturn,material='guide',metadata={'movement':'uturn','median_setback':setback}))
 specs.append(dict(id='opposing-turn-to-ramp',category='guide',points=[(x,y,z+.04) for x,y,z in connector],material='guide',metadata={'movement':'left','to':'ramp-exit'}))
 # Explicit directed paths: lane -> ramp and ramp -> lane; mainline loses/gains the outside lane.
 for id,points in [('exit-lane-continuation',[(-length/2,-lane_offset,.035),(split_x,-lane_offset,.035)]+[(x,y,z+.035) for x,y,z in off[1:]]),('entry-lane-continuation',[(x,y,z+.035) for x,y,z in on]+[(-length/2,lane_offset,.035)])]:
  specs.append(dict(id=id,category='guide',points=points,material='guide',metadata={'lane_connection':'continuation','junction_type':'split' if id.startswith('exit') else 'merge'}))
 # continuous dashed lane lines stop where that lane leaves mainline.
 for sign,station in [(-1,split),(1,merge)]:
  for s in range(0,int(length)-3,9):
   for index in (1,2):
    if index==2 and s>station:continue
    y=sign*(median/2+index*lw);points=[(-length/2+s,y,.012),(-length/2+s+3,y,.012)];specs.append(ribbon('interchange-line-'+str(sign)+'-'+str(index)+'-'+str(s),points,[(-.06,0),(.06,0)],'white',category='marking',thickness=0))
 specs.extend(grade_separated_decks(graph))
 return specs,[],{}

def grade_separated_decks(graph):
 r=graph['interchange'];bridge=r.get('overpass')
 if not bridge:return []
 x=bridge['station']-r['length']/2;gap=bridge['deck_gap'];w=bridge['deck_width'];z=bridge['elevation'];length=bridge['length'];specs=[]
 for side in (-1,1):
  center=x+side*(gap/2+w/2);points=[(center,-length/2,z),(center,length/2,z)]
  spec=solid_strip('highway-deck-'+str(side),points,w);spec['category']='bridge';spec['metadata']={'level':1,'traffic_direction':side,'grade_separated':True,'connections_to_lower':[]};specs.append(spec)
  for edge in (-1,1):
   xx=center+edge*w/2;poly=[(xx-.16,-length/2,z),(xx+.16,-length/2,z),(xx+.16,length/2,z),(xx-.16,length/2,z)]
   specs.append(solid_polygon('bridge-barrier-'+str(side)+'-'+str(edge),[(px,py,pz+.8) for px,py,pz in poly],'concrete',depth=.8,category='bridge-barrier'))
  for y in (-25,25):
   poly=[(center-1,y-1,z-.2),(center+1,y-1,z-.2),(center+1,y+1,z-.2),(center-1,y+1,z-.2)]
   specs.append(solid_polygon('bridge-pier-'+str(side)+'-'+str(y),poly,'concrete',depth=z-.2,category='bridge-pier'))
 return specs

def point_inside(point,polygon):
 x,y=point[:2];inside=False
 for a,b in zip(polygon,polygon[1:]+polygon[:1]):
  if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
 return inside

def build_parking(graph):
 lot=graph['parking'];specs=[];diag=[];road=lot['access_road'];hw=road['half_width'];length=road['length'];station=lot['connection']['station'];mouth=lot['connection']['width'];join_x=lot['connection']['lot_edge_x']
 asphalt=solid_polygon('parking-access-road',[(-hw,-length/2,0),(hw,-length/2,0),(hw,length/2,0),(-hw,length/2,0)],'asphalt');asphalt['metadata']['union_group']='parking';specs.append(asphalt)
 polygon=[(*p,0) for p in lot['vertices']];parking=solid_polygon('parking-lot-'+lot['id'],polygon,'asphalt');parking['metadata']['union_group']='parking';specs.append(parking)
 connector=solid_polygon('parking-road-connection',[(hw-.1,station-mouth/2,0),(join_x+.1,station-mouth/2,0),(join_x+.1,station+mouth/2,0),(hw-.1,station+mouth/2,0)],'asphalt');connector['metadata']['union_group']='parking';specs.append(connector)
 # Separate exact-solid Boolean cutters subtract actual island holes before pavement union.
 for island in lot['islands']:
  pts=[(*p,.35) for p in island['vertices']]
  cutter=solid_polygon('cut-'+island['id'],pts,'grass',depth=.7,category='cutter');cutter['metadata']['cut_target']=parking['id'];specs.append(cutter)
  grass=solid_polygon('planter-'+island['id'],[(*p,.08) for p in island['vertices']],'grass',depth=.2,category='planter');grass['metadata']['island_id']=island['id'];specs.append(grass)
  path=[(*p,0) for p in island['vertices']];path.append(path[0]);curb=ribbon('planter-curb-'+island['id'],path,[(0,.08),(.08,.1524),(.26,.1524)],'concrete');specs.append(curb)
 # Lot perimeter curb has an actual depressed entrance where it meets the connector.
 path=[(*p,0) for p in lot['vertices']];path.append(path[0]);opening={'id':'parking-opening','position':[join_x,station,0],'opening_width':mouth,'transition_left':1,'transition_right':1,'height':.1524,'run':2}
 specs.extend(curb_sidewalk({'id':'parking-perimeter','label':'lot','points':path},[opening],graph['settings']))
 # Road-side curb cut on the same access station, independent of lot boundary vertices.
 edge=[(hw,-length/2,0),(hw,length/2,0)];opening2=dict(opening,position=[hw,station,0]);specs.extend(curb_sidewalk({'id':'parking-road-edge','label':'access','points':edge},[opening2],graph['settings']))
 # Stall lines stay out of islands; invalid stalls produce explicit diagnostics.
 for row in lot['rows']:
  ca=math.cos(row.get('bearing',0));sa=math.sin(row.get('bearing',0));p=row['origin'];w=row['stall_width'];d=row['stall_depth'];seen_edges=set()
  def co(x,y):return (p[0]+ca*x-sa*y,p[1]+sa*x+ca*y,.012)
  for i in range(row['count']):
   corners=[co(i*w,0),co((i+1)*w,0),co((i+1)*w,d),co(i*w,d)]
   fits=all(point_inside(polygon_point,lot['vertices']) and not any(point_inside(polygon_point,island['vertices']) for island in lot['islands']) for polygon_point in corners)
   fits=fits and not any(polygons_overlap([v[:2] for v in corners],island['vertices']) for island in lot['islands'])
   if not fits:diag.append(f"{row['id']}-stall-{i}: outside lot or intersects island; not generated");continue
   for segment,(a,b) in enumerate([(corners[0],corners[3]),(corners[1],corners[2]),(corners[2],corners[3])]):
    edge_key=tuple(sorted((tuple(round(value,6) for value in a),tuple(round(value,6) for value in b))))
    if edge_key in seen_edges:continue
    seen_edges.add(edge_key)
    direction=norm2(sub(b,a));normal=(direction[1],-direction[0]);verts=[(a[0]-.05*normal[0],a[1]-.05*normal[1],a[2]),(b[0]-.05*normal[0],b[1]-.05*normal[1],b[2]),(b[0]+.05*normal[0],b[1]+.05*normal[1],b[2]),(a[0]+.05*normal[0],a[1]+.05*normal[1],a[2])]
    if area(verts)<0:verts.reverse()
    specs.append(mesh_spec(row['id']+'-stall-'+str(i)+'-'+str(segment),'marking',verts,[(0,1,2,3)],'white',stall_id=row['id']+'-stall-'+str(i)))
 return specs,diag,{}

def segments_cross(a,b,c,d):
 def orient(x,y,z):return cross(sub(y,x),sub(z,x))
 u,v,w,z=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
 return ((u>EPS and v<-EPS) or (u<-EPS and v>EPS)) and ((w>EPS and z<-EPS) or (w<-EPS and z>EPS))
def polygons_overlap(a,b):
 if any(point_inside(p,b) for p in a) or any(point_inside(p,a) for p in b):return True
 return any(segments_cross(x,y,u,v) for x,y in zip(a,a[1:]+a[:1]) for u,v in zip(b,b[1:]+b[:1]))
def polygon_valid(points):
 if len(points)<3 or area(points)<=EPS:raise ValueError('Polygon must have at least 3 CCW vertices')
 edges=list(zip(points,points[1:]+points[:1]))
 for i,(a,b) in enumerate(edges):
  if math.dist(a,b)<EPS:raise ValueError('Duplicate consecutive polygon points')
  for j,(c,d) in enumerate(edges):
   if abs(i-j) in (0,1) or {i,j}=={0,len(edges)-1}:continue
   if segments_cross(a,b,c,d):raise ValueError('Self-intersecting polygon')
 return True
