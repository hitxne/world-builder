"""Terrain-to-deck round piers and tapered transverse support caps."""
import math
from . import network,geometry

def edge_distance(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
 u=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
 return math.hypot(p[0]-a[0]-u*dx,p[1]-a[1]-u*dy)

def fits(p,radius,polygon):
 return geometry.point_inside(p,polygon) and all(edge_distance(p,a,b)>=radius-1e-7 for a,b in zip(polygon,polygon[1:]+polygon[:1]))

def overlaps(p,radius,polygon):
 return geometry.point_inside(p,polygon) or any(edge_distance(p,a,b)<radius for a,b in zip(polygon,polygon[1:]+polygon[:1]))

def check_placement(graph,support,specs=None):
 road=next(r for r in graph['roads'] if r['id']==support['road_id']);samples=network.road_samples(road,graph['settings']['sample_spacing']);p,t,n=network.frame(samples,support['station']);offset=support.get('offset',0);center=(p[0]+offset*n[0],p[1]+offset*n[1]);radius=support.get('diameter',1.3)/2+support.get('clearance',.25)
 if support.get('clearance',.25)<0:raise ValueError('Pillar clearance must be nonnegative')
 medians=[m for m in graph.get('support_medians',[]) if fits(center,radius,m['vertices'])]
 allowed_roads={m['road_id'] for m in medians}
 if specs is None:specs,_,_=network.build(graph)
 for spec in specs:
  if spec['category'] in ('curb','sidewalk') and spec.get('metadata',{}).get('road_id'):
   parent=next(r for r in graph['roads'] if r['id']==spec['metadata']['road_id'])
   if parent.get('terrain_mode')=='bridge':continue
   count=len(network.road_samples(parent,graph['settings']['sample_spacing']));cols=len(spec['verts'])//(2*count)
   if cols>=2:
    polygon=[spec['verts'][i*cols][:2] for i in range(count)]+[spec['verts'][i*cols+cols-1][:2] for i in range(count-1,-1,-1)]
    if overlaps(center,radius,polygon):raise ValueError(f"Pillar {support['id']} overlaps a curb or sidewalk")
   continue
  if spec['category']!='road' or spec.get('metadata',{}).get('terrain_mode')!='grade':continue
  if spec['id'] in allowed_roads:continue
  if 'station' in spec:polygon=network.polygon_from_strip(spec)
  else:
   lot=next((x for x in graph['parking_lots'] if x['id']==spec['id']),None)
   if not lot:continue
   polygon=lot['vertices']
  if overlaps(center,radius,polygon):raise ValueError(f"Pillar {support['id']} overlaps {spec['id']}; choose clear terrain or a median wide enough for diameter plus clearance")
 bounds=graph['terrain']['bounds']
 if not bounds[0]+radius<=center[0]<=bounds[1]-radius or not bounds[2]+radius<=center[1]<=bounds[3]-radius:raise ValueError('Entire pillar footprint must fit within terrain bounds')
 return 'median' if medians else 'terrain'

def build(graph,support,ground_height):
 road=next((r for r in graph['roads'] if r['id']==support['road_id']),None)
 if not road or road.get('terrain_mode')!='bridge':raise ValueError('Support must reference an elevated bridge road')
 samples=network.road_samples(road,graph['settings']['sample_spacing']);station=support['station'];offset=support.get('offset',0)
 diameter=support.get('diameter',1.3);width=support.get('cap_width',6.5);length=support.get('cap_length',2.2);height=support.get('cap_height',1.0);embed=support.get('embed',.35)
 if not all(math.isfinite(x) for x in (station,offset,diameter,width,length,height,embed)) or min(diameter,width,length,height)<=0 or embed<0:raise ValueError('Invalid bridge support dimensions')
 if width<diameter or length<diameter:raise ValueError('Cap width and length must cover the column diameter')
 left,right=network.widths(road,station)
 if offset+diameter/2>left or offset-diameter/2<-right:raise ValueError('Column must remain beneath its bridge deck')
 if station-length/2<0 or station+length/2>samples[-1][0]:raise ValueError('Support cap extends beyond bridge alignment')
 p,t,n=network.frame(samples,station);xy=math.hypot(t[0],t[1]);along=(t[0]/xy,t[1]/xy,0);center=(p[0]+offset*n[0],p[1]+offset*n[1]);depth=road.get('structure',{}).get('deck_depth',.22)
 tops=[]
 for longitudinal in (-length/2,length/2):
  for lateral in (-width/2,0,width/2):
   q,_,_=network.surface_point(road,samples,station+longitudinal,offset+lateral);tops.append((q[0],q[1],q[2]-depth))
 cap_bottom=min(q[2] for q in tops)-height
 ground_samples=[ground_height(*center)]+[ground_height(center[0]+diameter/2*math.cos(i*math.pi/8),center[1]+diameter/2*math.sin(i*math.pi/8)) for i in range(16)]
 base=min(ground_samples)-embed
 if max(ground_samples)>=cap_bottom-.1:raise ValueError('Terrain is too high beneath this bridge support')
 if base>=cap_bottom-.1:raise ValueError('Insufficient space between terrain and bridge cap for column')
 bottom_width=max(diameter,width*.55);bottom_length=max(diameter,length*.8)
 bottoms=[]
 for longitudinal in (-bottom_length/2,bottom_length/2):
  for lateral in (-bottom_width/2,0,bottom_width/2):bottoms.append((center[0]+along[0]*longitudinal+n[0]*lateral,center[1]+along[1]*longitudinal+n[1]*lateral,cap_bottom))
 faces=[(0,3,4,1),(1,4,5,2),(6,7,10,9),(7,8,11,10)]
 boundary=[0,3,4,5,2,1]
 for a,b in zip(boundary,boundary[1:]+boundary[:1]):faces.append((a,a+6,b+6,b))
 metadata={'support_id':support['id'],'road_id':road['id'],'station':station,'column_height':cap_bottom-base,'base_height':base,'cap_bottom':cap_bottom,'terrain_mode':'structure'}
 cap=geometry.mesh_spec(support['id']+'-cap','bridge-cap',tops+bottoms,faces,'concrete',**metadata)
 segments=48;vertices=[]
 for z in (base,cap_bottom):
  vertices.extend((center[0]+diameter/2*math.cos(i*2*math.pi/segments),center[1]+diameter/2*math.sin(i*2*math.pi/segments),z) for i in range(segments))
 faces=[tuple(reversed(range(segments))),tuple(range(segments,segments*2))]
 faces.extend((i,(i+1)%segments,(i+1)%segments+segments,i+segments) for i in range(segments))
 column=geometry.mesh_spec(support['id']+'-column','bridge-column',vertices,faces,'concrete',**metadata)
 return [column,cap]

def validate(graph):
 seen=set()
 specs=network.build(graph)[0] if graph.get('bridge_supports') else []
 for support in graph.get('bridge_supports',[]):
  if not support.get('id') or support['id'] in seen:raise ValueError('Bridge supports require unique IDs')
  seen.add(support['id']);build(graph,support,lambda x,y:-100);check_placement(graph,support,specs)
