"""V3 editable network kernel. Traffic connectivity is explicit; geometry is derived."""
import math,json,copy,bisect,hashlib
from . import geometry as geo,core
EPS=1e-8

def vec(a,b,t):return tuple(a[k]+(b[k]-a[k])*t for k in range(3))
def unit(v):
 length=math.sqrt(sum(x*x for x in v))
 if length<EPS:raise ValueError('Zero alignment tangent')
 return tuple(x/length for x in v)
def smooth(t):return t*t*(3-2*t)
def key(keys,s):return core.width_at(keys,s)
def cubic(points,count):
 a,b,c,d=points
 return [tuple((1-u)**3*a[k]+3*(1-u)**2*u*b[k]+3*(1-u)*u*u*c[k]+u**3*d[k] for k in range(3)) for u in [i/count for i in range(count+1)]]

def sample_points(points,spacing):
 """Arc-distance stationing with exact input breakpoints and smoothed local frames."""
 raw=[];stations=[0.]
 for a,b in zip(points,points[1:]):
  if math.dist(a,b)<EPS:raise ValueError('Coincident alignment points')
  n=max(1,math.ceil(math.dist(a,b)/spacing))
  raw.extend(vec(a,b,i/n) for i in range(n))
 raw.append(tuple(points[-1]))
 for a,b in zip(raw,raw[1:]):stations.append(stations[-1]+math.dist(a,b))
 result=[]
 for i,p in enumerate(raw):
  a=raw[max(0,i-1)];b=raw[min(len(raw)-1,i+1)];t=unit(geo.sub(b,a));xy=math.hypot(t[0],t[1])
  if xy<EPS:raise ValueError('Vertical road alignment has no planar frame')
  result.append((stations[i],p,t,(-t[1]/xy,t[0]/xy,0)))
 return result

def alignment_points(road,spacing):
 a=road['alignment'];points=a['points']
 if a.get('kind','polyline')=='bezier':
  result=[]
  for segment in a['segments']:
   count=max(8,math.ceil(sum(math.dist(x,y) for x,y in zip(segment,segment[1:]))/spacing))
   result.extend(cubic(segment,count)[:-1])
  result.append(tuple(a['segments'][-1][-1]));return result
 return points

def road_samples(road,spacing):return sample_points(alignment_points(road,spacing),spacing)
def frame(samples,s):
 length=samples[-1][0]
 if s<-EPS or s>length+EPS:raise ValueError(f'Station {s:.2f} outside alignment [0,{length:.2f}]')
 s=max(0,min(length,s));i=min(len(samples)-2,max(0,bisect.bisect_right([x[0] for x in samples],s)-1));a,b=samples[i:i+2];u=(s-a[0])/(b[0]-a[0]);t=unit(vec(a[2],b[2],u));xy=math.hypot(t[0],t[1]);n=(-t[1]/xy,t[0]/xy,0)
 return vec(a[1],b[1],u),t,n

def widths(road,s):
 radius=key(road.get('radius',[[0,1]]),s)
 return key(road['width_left'],s)*radius,key(road['width_right'],s)*radius

def surface_point(road,samples,s,offset):
 p,t,n=frame(samples,s);z=p[2]-abs(offset)*road.get('crossfall',0)
 return (p[0]+offset*n[0],p[1]+offset*n[1],z),t,n

def lane_anchor(graph,lane_id,station,cache=None):
 for road in graph['roads']:
  lane=next((x for x in road['lanes'] if x['id']==lane_id),None)
  if lane:
   samples=cache[road['id']] if cache else road_samples(road,graph['settings']['sample_spacing'])
   if station<lane.get('start',0)-EPS or station>lane.get('end',samples[-1][0])+EPS:raise ValueError(f"{lane_id}: attachment outside lane's active stations")
   offset=key(lane['offset'],station);p,t,n=surface_point(road,samples,station,offset)
   return p,tuple(lane['direction']*x for x in t),n,road,lane
 raise ValueError('Unknown lane '+lane_id)

def connection_points(graph,connection,cache=None):
 p,t,n,from_road,from_lane=lane_anchor(graph,connection['from_lane'],connection['from_station'],cache)
 q,u,m,to_road,to_lane=lane_anchor(graph,connection['to_lane'],connection['to_station'],cache)
 distance=math.dist(p,q)
 start=connection.get('handle_from',[distance*.4,0,0]);end=connection.get('handle_to',[-distance*.4,0,0])
 a=tuple(p[k]+t[k]*start[0]+n[k]*start[1]+(start[2] if k==2 else 0) for k in range(3));b=tuple(q[k]+u[k]*end[0]+m[k]*end[1]+(end[2] if k==2 else 0) for k in range(3))
 count=max(16,math.ceil((math.dist(p,a)+math.dist(a,b)+math.dist(b,q))/graph['settings']['sample_spacing']))
 points=cubic([p,a,b,q],count)
 return points,(p,a,b,q)

def closed_strip(id,samples,left,right,crossfall,material='asphalt',category='road',**metadata):
 v=[];station_values=[];uv=[]
 for s,p,t,n in samples:
  for offset in (key(left,s),-key(right,s)):
   v.append((p[0]+offset*n[0],p[1]+offset*n[1],p[2]-abs(offset)*crossfall+offset*key(metadata.get('cross_slope',[[0,0]]),s)));station_values.append(s);uv.append((offset,s))
 f=[]
 for i in range(len(samples)-1):
  a=2*i;face=(a,a+1,a+3,a+2)
  p,q,r=[v[k] for k in face[:3]]
  if geo.cross(geo.sub(q,p),geo.sub(r,p))<=EPS:raise ValueError(f'{id}: folded pavement; adjust curvature/width')
  f.append(face)
 count=len(v);v+= [(x,y,z-metadata.get('thickness',.22)) for x,y,z in v];f+= [tuple(k+count for k in reversed(face)) for face in list(f)]
 boundary=[0,1]+list(range(3,count,2))+[count-2]+list(range(count-4,0,-2))
 for a,b in zip(boundary,boundary[1:]+boundary[:1]):f.append((a,a+count,b+count,b))
 spec=geo.mesh_spec(id,category,v,f,material,**metadata);spec['station']=station_values*2;spec['uv']=uv*2
 return spec

def surface_profile(road,samples):
 left=[[s,widths(road,s)[0]] for s,_,_,_ in samples];right=[[s,widths(road,s)[1]] for s,_,_,_ in samples]
 return closed_strip(road['id'],samples,left,right,road.get('crossfall',0),level=road.get('level',0),terrain_mode=road.get('terrain_mode','grade'),thickness=road.get('structure',{}).get('deck_depth',.22))

def box_polygon(id,polygon,z,category='cutter',**metadata):
 spec=geo.solid_polygon(id,[(p[0],p[1],z+40) for p in polygon],'asphalt',depth=80,category=category);spec['metadata'].update(metadata);return spec

def polygon_from_strip(spec):
 count=len(spec['verts'])//2
 return [spec['verts'][i][:2] for i in range(1,count,2)]+[spec['verts'][i][:2] for i in range(count-2,-1,-2)]

def connection_apron(graph,connection,spec,samples,cache,which):
 road_lane=connection[which+'_lane'];station=connection[which+'_station'];anchor,t,n,road,lane=lane_anchor(graph,road_lane,station,cache)
 if road.get('terrain_mode')!='grade':return None
 side=1 if key(lane['offset'],station)>0 else -1;overlap=.2;inner_offset=key(lane['offset'],station)-side*(connection['width']/2+overlap)
 extent=connection.get('apron_length',40)
 if extent<=0:return None
 indices=[i for i,row in enumerate(samples) if (row[0]<=extent if which=='from' else samples[-1][0]-row[0]<=extent)]
 parent=[];branch=[]
 for i in indices:
  distance,road_station=geo.nearest_station([p for _,p,_,_ in cache[road['id']]],samples[i][1]);q,_,_=surface_point(road,cache[road['id']],road_station,inner_offset)
  edge=spec['verts'][2*i+(1 if side==1 else 0)];normal=samples[i][3];shift=side*overlap;slope=key(spec['metadata']['cross_slope'],samples[i][0]);b=(edge[0]+normal[0]*shift,edge[1]+normal[1]*shift,edge[2]+slope*shift)
  # Use only the outside fork gap, keeping through lanes unchanged.
  if side*((b[0]-q[0])*n[0]+(b[1]-q[1])*n[1])<-.01:return None
  parent.append(q);branch.append(b)
 outline=parent+list(reversed(branch));clean=[]
 for p in outline:
  if not clean or math.dist(p,clean[-1])>1e-6:clean.append(p)
 if len(clean)>2 and math.dist(clean[0],clean[-1])<1e-6:clean.pop()
 if len(clean)<3 or abs(geo.area(clean))<.01:return None
 if geo.area(clean)<0:clean.reverse()
 geo.polygon_valid(clean)
 apron=geo.solid_polygon(connection['id']+'-'+which+'-apron',clean,'asphalt',depth=.22,category='road');apron['metadata'].update(terrain_mode='grade',connection_id=connection['id'],network_component=spec['metadata']['union_group'],transition_apron=True,intentional_overlap_m=overlap)
 return apron

def closed_curb(id,points,profile):
 count=len(points);cols=len(profile);vertices=[];faces=[]
 for i,p in enumerate(points):
  before=points[(i-1)%count];after=points[(i+1)%count];t=geo.norm2(geo.sub(after,before));n=(t[1],-t[0])
  for offset,z in profile:vertices.append((p[0]+n[0]*offset,p[1]+n[1]*offset,p[2]+z))
 top=len(vertices);vertices.extend((x,y,z-.12) for x,y,z in list(vertices))
 for i in range(count):
  a=i*cols;b=((i+1)%count)*cols
  for j in range(cols-1):
   face=(a+j,a+j+1,b+j+1,b+j);faces.append(face);faces.append(tuple(v+top for v in reversed(face)))
  faces.append((a,b,b+top,a+top));faces.append((a+cols-1,a+cols-1+top,b+cols-1+top,b+cols-1))
 return geo.mesh_spec(id,'curb',vertices,faces,'concrete')

def edge_strip(road,samples,side,settings,**metadata):
 points=[]
 for s,p,t,n in samples:
  offset=side*widths(road,s)[0 if side==1 else 1];q,_,_=surface_point(road,samples,s,offset);points.append(q)
 if side==1:points.reverse()
 h=settings['curb_height'];curb=geo.ribbon('curb-'+road['id']+'-'+str(side),points,[(0,0),(.035,h-.02),(.065,h),(.32,h)],'concrete')
 sidewalk=geo.ribbon('sidewalk-'+road['id']+'-'+str(side),points,[(.32+road.get('sidewalk_setback',0),h),(.32+road.get('sidewalk_setback',0)+road.get('sidewalk_width',settings['sidewalk_width']),h)],'sidewalk',category='sidewalk')
 for s in (curb,sidewalk):s['metadata'].update(road_id=road['id'],terrain_mode=road.get('terrain_mode','grade'),level=road.get('level',0),**metadata)
 return [curb,sidewalk]

def access_points(graph,access,cache):
 road=next(x for x in graph['roads'] if x['id']==access['road_id']);lot=next(x for x in graph['parking_lots'] if x['id']==access['lot_id']);s=access['station'];side=access['side'];samples=cache[road['id']];l,r=widths(road,s);offset=side*(l if side==1 else r)
 p,t,n=surface_point(road,samples,s,offset);out=tuple(side*x for x in n)
 edge=access['lot_edge'];vertices=lot['vertices'];a,b=vertices[edge],vertices[(edge+1)%len(vertices)];fraction=access['fraction'];xy=[a[k]+(b[k]-a[k])*fraction for k in range(2)];q=(xy[0],xy[1],lot_height(lot,*xy))
 tangent=geo.norm2(geo.sub(b,a));inward=(-tangent[1],tangent[0],0);length=math.dist(p,q);start=access.get('handle_length',length*.35)
 # Overlap both pavement solids so the physical connection is continuous after union.
 p,_,_=surface_point(road,samples,s,offset-side*.45);q=tuple(q[k]+inward[k]*.45 for k in range(3));q=(q[0],q[1],lot_height(lot,q[0],q[1]));c=tuple(p[k]+out[k]*start for k in range(3));d=tuple(q[k]-inward[k]*start for k in range(3))
 points=cubic([p,c,d,q],max(12,math.ceil((math.dist(p,c)+math.dist(c,d)+math.dist(d,q))/graph['settings']['sample_spacing'])))
 return points,(p,c,d,q)

def lot_height(lot,x,y):
 grade=lot.get('grade',{});origin=grade.get('origin',[0,0]);return grade.get('elevation',0)+grade.get('slope_x',0)*(x-origin[0])+grade.get('slope_y',0)*(y-origin[1])

def connected_components(graph):
 parents={x['id']:x['id'] for x in graph['roads']+graph['parking_lots']}
 def find(x):
  while parents[x]!=x:parents[x]=parents[parents[x]];x=parents[x]
  return x
 def join(a,b):
  a,b=find(a),find(b)
  if a!=b:parents[max(a,b)]=min(a,b)
 lane_roads={lane['id']:road['id'] for road in graph['roads'] for lane in road['lanes']}
 for c in graph['connections']:join(lane_roads[c['from_lane']],lane_roads[c['to_lane']])
 for a in graph['accesses']:join(a['road_id'],a['lot_id'])
 return {x:find(x) for x in parents},lane_roads

def build(graph):
 validate(graph);settings=graph['settings'];cache={r['id']:road_samples(r,settings['sample_spacing']) for r in graph['roads']};specs=[];warnings=[];components,lane_roads=connected_components(graph);cuts=[]
 for road in graph['roads']:
  samples=cache[road['id']];spec=surface_profile(road,samples);spec['metadata']['union_group']='network-'+components[road['id']];specs.append(spec)
  if road.get('curbs',True):
   for side in (-1,1):specs.extend(edge_strip(road,samples,side,settings))
  for lane in road['lanes']:
   pts=[]
   for station,p,t,n in samples:
    if lane.get('start',0)-EPS<=station<=lane.get('end',samples[-1][0])+EPS:
     q,_,_=surface_point(road,samples,station,key(lane['offset'],station));pts.append((q[0],q[1],q[2]+.025))
   if len(pts)>1:specs.append(dict(id='lane-guide-'+lane['id'],category='guide',points=pts,material='guide',metadata={'lane_id':lane['id'],'direction':lane['direction']}))
 for c in graph['connections']:
  points,controls=connection_points(graph,c,cache);samples=sample_points(points,settings['sample_spacing']);width=c['width']/2
  _,_,_,fr,fl=lane_anchor(graph,c['from_lane'],c['from_station'],cache);_,_,_,tr,tl=lane_anchor(graph,c['to_lane'],c['to_station'],cache)
  cf_from=-math.copysign(fr.get('crossfall',0),key(fl['offset'],c['from_station']))*fl['direction'];cf_to=-math.copysign(tr.get('crossfall',0),key(tl['offset'],c['to_station']))*tl['direction']
  spec=closed_strip(c['id'],samples,[[0,width]],[[0,width]],0,terrain_mode=c.get('terrain_mode','grade'),grade_from=c.get('grade_from',0),grade_to=c.get('grade_to',samples[-1][0]),level=c.get('level',0),cross_slope=[[0,cf_from],[samples[-1][0],cf_to]],union_group='network-'+components[lane_roads[c['from_lane']]],from_lane=c['from_lane'],to_lane=c['to_lane']);specs.append(spec)
  aprons=[]
  for which in ('from','to'):
   apron=connection_apron(graph,c,spec,samples,cache,which)
   if apron:specs.append(apron);aprons.append(apron)
  # Cut only road edge furniture; the connection slab carries the actual traversable grade.
  polygon=polygon_from_strip(spec)
  targets=['curb-'+r+'-'+str(side) for r in {lane_roads[c['from_lane']],lane_roads[c['to_lane']]} for side in (-1,1)]+['sidewalk-'+r+'-'+str(side) for r in {lane_roads[c['from_lane']],lane_roads[c['to_lane']]} for side in (-1,1)]
  cuts.append(box_polygon('opening-'+c['id'],polygon,0,cut_targets=targets))
  for apron in aprons:cuts.append(box_polygon('opening-'+apron['id'],[p[:2] for p in apron['verts'][:len(apron['verts'])//2]],0,cut_targets=targets))
  if samples[-1][0]>0:
   maximum=max(abs((b[1][2]-a[1][2])/(b[0]-a[0])) for a,b in zip(samples,samples[1:]))
   if maximum>graph['validation']['max_road_grade']:warnings.append(f"{c['id']}: maximum grade {maximum:.1%} exceeds selected {graph['validation']['max_road_grade']:.1%}")
 for lot in graph['parking_lots']:
  points=[(x,y,lot_height(lot,x,y)) for x,y in lot['vertices']];spec=geo.solid_polygon(lot['id'],points,'asphalt',category='road');spec['metadata'].update(terrain_mode='grade',level=0,union_group='network-'+components[lot['id']]);specs.append(spec)
  curb=closed_curb('lot-curb-'+lot['id'],points,[(0,0),(.035,.13),(.065,.1524),(.32,.1524)]);curb['metadata'].update(terrain_mode='grade',level=0);specs.append(curb)
  for island in lot.get('islands',[]):
   polygon=island['vertices'];cuts.append(box_polygon('island-cut-'+island['id'],polygon,0,cut_targets=[lot['id']]))
   grass=geo.solid_polygon('planter-'+island['id'],[(x,y,lot_height(lot,x,y)+.08) for x,y in polygon],'grass',depth=.18,category='planter');grass['metadata'].update(terrain_mode='grade',level=0);specs.append(grass)
   path=[(x,y,lot_height(lot,x,y)) for x,y in polygon];curb=closed_curb('planter-curb-'+island['id'],path,[(0,.08),(.08,.1524),(.26,.1524)]);curb['metadata'].update(terrain_mode='grade',level=0);specs.append(curb)
 for median in graph.get('support_medians',[]):
  road=next(r for r in graph['roads'] if r['id']==median['road_id']);samples=cache[road['id']];points=[]
  for x,y in median['vertices']:
   distance,station=geo.nearest_station([p for _,p,_,_ in samples],(x,y,0));p,t,n=frame(samples,station);offset=(x-p[0])*n[0]+(y-p[1])*n[1];q,_,_=surface_point(road,samples,station,offset);points.append((x,y,q[2]+.08))
  soil=geo.solid_polygon(median['id'],points,'grass',depth=.12,category='median');soil['metadata'].update(terrain_mode='grade',road_id=road['id']);specs.append(soil)
  curb=closed_curb('median-curb-'+median['id'],[(x,y,z-.08) for x,y,z in points],[(0,.08),(.08,.1524),(.26,.1524)]);curb['metadata'].update(terrain_mode='grade',road_id=road['id']);specs.append(curb)
  cuts.append(box_polygon('median-cut-'+median['id'],median['vertices'],0,cut_targets=[road['id']]))
 for a in graph['accesses']:
  points,controls=access_points(graph,a,cache);samples=sample_points(points,settings['sample_spacing']);road=next(x for x in graph['roads'] if x['id']==a['road_id']);lot=next(x for x in graph['parking_lots'] if x['id']==a['lot_id']);_,rt,rn=frame(cache[road['id']],a['station']);xy=math.hypot(rt[0],rt[1]);slope=rt[2]/xy;ng=samples[0][3];coef=slope*(rt[0]/xy*ng[0]+rt[1]/xy*ng[1])-a['side']*road.get('crossfall',0)*(rn[0]*ng[0]+rn[1]*ng[1]);end_n=samples[-1][3];grade=lot.get('grade',{});end_coef=grade.get('slope_x',0)*end_n[0]+grade.get('slope_y',0)*end_n[1];spec=closed_strip(a['id'],samples,[[0,a['width']/2]],[[0,a['width']/2]],0,terrain_mode='grade',level=0,union_group='network-'+components[a['road_id']],road_id=a['road_id'],lot_id=a['lot_id'],cross_slope=[[0,coef],[samples[-1][0],end_coef]]);specs.append(spec)
  targets=['curb-'+a['road_id']+'-'+str(a['side']),'sidewalk-'+a['road_id']+'-'+str(a['side']),'lot-curb-'+a['lot_id']];cuts.append(box_polygon('opening-'+a['id'],polygon_from_strip(spec),0,cut_targets=targets))
 specs.extend(cuts)
 return specs,warnings,{'cache':cache,'components':components}

def validate(g):
 from .compatibility import migrate_graph
 migrate_graph(g)
 if g.get('version')!=3 or g.get('units')!='m':raise ValueError('Expected v3 network in meters')
 ids=[];roads={r['id']:r for r in g['roads']};lots={x['id']:x for x in g['parking_lots']};lanes={}
 def entity(x):
  if not isinstance(x.get('id'),str) or not x['id']:raise ValueError('Entity needs a durable ID')
  ids.append(x['id'])
 if not g['roads']:raise ValueError('Add at least one road')
 if not .25<=g['settings']['sample_spacing']<=5:raise ValueError('Sample spacing must be 0.25–5 m')
 for road in g['roads']:
  entity(road);samples=road_samples(road,g['settings']['sample_spacing']);length=samples[-1][0]
  for side in ('width_left','width_right'):
   keys=road[side]
   if not keys or any(x[1]<=0 for x in keys) or any(a[0]>=b[0] for a,b in zip(keys,keys[1:])):raise ValueError('Invalid width profile')
  for lane in road['lanes']:
   entity(lane);lanes[lane['id']]=road['id']
   if lane['direction'] not in (-1,1):raise ValueError('Lane direction must be +1 or −1')
   if lane['width']<=0 or lane.get('start',0)<0 or lane.get('end',length)>length+EPS:raise ValueError('Invalid lane station/width')
 for lot in g['parking_lots']:
  entity(lot);geo.polygon_valid(lot['vertices'])
  for island in lot.get('islands',[]):
   entity(island);geo.polygon_valid(island['vertices'])
   if not all(geo.point_inside(v,lot['vertices']) for v in island['vertices']):raise ValueError('Island lies outside its lot')
  for i,a in enumerate(lot.get('islands',[])):
   if any(geo.polygons_overlap(a['vertices'],b['vertices']) for b in lot['islands'][i+1:]):raise ValueError('Planter islands overlap')
 for c in g['connections']:
  entity(c)
  if c['from_lane'] not in lanes or c['to_lane'] not in lanes:raise ValueError('Connection references missing lane')
  if c['width']<=0:raise ValueError('Connection needs positive width')
  connection_points(g,c)
 for a in g['accesses']:
  entity(a)
  if a['road_id'] not in roads or a['lot_id'] not in lots:raise ValueError('Parking access references missing entity')
  if a['side'] not in (-1,1) or not 0<=a['fraction']<=1 or not 0<=a['lot_edge']<len(lots[a['lot_id']]['vertices']):raise ValueError('Invalid access anchor')
  if a['width']<=0:raise ValueError('Access width must be positive')
  frame(road_samples(roads[a['road_id']],g['settings']['sample_spacing']),a['station'])
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate entity IDs')
 for median in g.get('support_medians',[]):
  entity(median)
  if median['road_id'] not in roads or roads[median['road_id']].get('terrain_mode')=='bridge':raise ValueError('Median must belong to a ground road')
  geo.polygon_valid(median['vertices'])
  road=roads[median['road_id']];samples=road_samples(road,g['settings']['sample_spacing'])
  for x,y in median['vertices']:
   distance,station=geo.nearest_station([p for _,p,_,_ in samples],(x,y,0));p,t,n=frame(samples,station);offset=(x-p[0])*n[0]+(y-p[1])*n[1];left,right=widths(road,station)
   if not -right<offset<left:raise ValueError('Median must fit within its parent road')
 for support in g.get('bridge_supports',[]):
  entity(support)
  if support['road_id'] not in roads or roads[support['road_id']].get('terrain_mode')!='bridge':raise ValueError('Support references a missing or non-bridge road')
  frame(road_samples(roads[support['road_id']],g['settings']['sample_spacing']),support['station'])
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate entity IDs')
 terrain=g['terrain']
 if terrain.get('backend')=='roadlab':
  if not terrain.get('tt_library'):raise ValueError('Choose the original upstream node library')
  if terrain.get('tt_flat_max',terrain['blend_distance'])<=terrain.get('tt_flat_min',1):raise ValueError('Terrain blend must exceed the contact band')
 if terrain['grid_spacing']<.5 or terrain['blend_distance']<=0:raise ValueError('Invalid terrain resolution/blend')
 xmin,xmax,ymin,ymax=terrain['bounds']
 if xmin>=xmax or ymin>=ymax:raise ValueError('Invalid terrain bounds')
 if (math.ceil((xmax-xmin)/terrain['grid_spacing'])+1)*(math.ceil((ymax-ymin)/terrain['grid_spacing'])+1)>250000:raise ValueError('Terrain exceeds 250,000 vertex budget')
 return g
