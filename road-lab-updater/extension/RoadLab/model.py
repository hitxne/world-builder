"""Versioned metadata and validation. v2 intentionally rejects unsupported topologies."""
import json,copy,math
from . import geometry
VERSION=2

def migrate(g):
 g=copy.deepcopy(g)
 if g.get('version')==1:
  # Legacy demos are not connected junction definitions. Keep source under migration metadata.
  # Never silently infer road/lane topology from the old four guide arcs.
  raise ValueError('v1 pilot requires explicit replacement with a v2 fixture; keep old scene as backup')
 if g.get('version') not in (VERSION,3):raise ValueError('Unsupported graph version')
 return g

def validate(g):
 from .compatibility import migrate_graph
 migrate_graph(g)
 if g.get('version')==3:
  from . import network
  return network.validate(g)
 if g.get('version')!=VERSION or g.get('units')!='m':raise ValueError('Expected v2 graph in meters')
 ids=[]
 def entity(x):
  if not isinstance(x.get('id'),str) or not x['id']:raise ValueError('Missing persistent ID')
  ids.append(x['id'])
 settings=g['settings']
 if settings['sidewalk_width']<=.5 or settings['curb_height']<=0:raise ValueError('Invalid sidewalk or curb height')
 if settings.get('sample_spacing',.5)<.1:raise ValueError('Sampling below 0.1m is not supported by this pilot')
 if g['fixture'] in ('intersection','skew'):
  j=g['junction'];entity(j)
  for a in j['approaches']:
   entity(a)
   if a['half_width']<=0 or a['length']<5:raise ValueError('Invalid approach dimensions')
  ap={a['id'] for a in j['approaches']}
  for c in j['corners'].values():
   entity(c)
   if c['radius']<=0:raise ValueError('Radius must be positive')
   if any(x not in ap for x in c['approach_pair']):raise ValueError('Corner references missing approach')
  lanes={l['id'] for l in j.get('lanes',[])}
  for lane in j.get('lanes',[]):
   entity(lane)
   if lane['approach_id'] not in ap:raise ValueError('Lane references missing approach')
  for movement in j.get('movements',[]):
   entity(movement)
   if movement['from'] not in lanes or movement['to'] not in lanes:raise ValueError('Movement references missing lane')
  for c in g['crosswalks']:
   entity(c)
   if c['width']<=0:raise ValueError('Positive crosswalk width required')
   for e in c['endpoints'].values():
    entity(e)
    if e['approach_id'] not in ap or e['side'] not in (-1,1):raise ValueError('Invalid endpoint anchor')
    if min(e['run'],e['opening_width'],e['transition_left'],e['transition_right'])<=0:raise ValueError('Positive endpoint dimensions required')
    if e.get('mode','auto') not in ('auto','manual','constrained-linked'):raise ValueError('Invalid ownership mode')
    if e['mode']=='manual' and 'position' not in e:raise ValueError('Manual endpoint needs position')
 elif g['fixture'] in ('boulevard','arterial'):
  b=g['boulevard'];entity(b)
  if b['median_width']<=b['lane_width']+.5:raise ValueError('Median insufficient for the selected pocket')
  if not 0<=b['pocket_start']<b['pocket_start']+b['taper_length']<=b['pocket_end']<b['length']:raise ValueError('Invalid pocket stations')
  if g['fixture']=='arterial':
   for a in b['outer_turns']:
    entity(a)
    if a['side'] not in (-1,1) or a['width']<=0:raise ValueError('Invalid auxiliary lane')
    if not 0<=a['start']<a['start']+a['taper']<a['end']-a['taper_out']<a['end']<=b['length']:raise ValueError('Auxiliary taper stations overlap')
   for d in b['driveways']:
    entity(d)
    if d['side'] not in (-1,1) or not 0<d['station']<b['length'] or d['width']<=0:raise ValueError('Invalid driveway')
 elif g['fixture']=='interchange':
  r=g['interchange'];entity(r)
  if min(r['lane_width'],r['median_width'],r['taper_length'],r['ramp_length'],r['ramp_offset'])<=0:raise ValueError('Positive interchange dimensions required')
  if max(r['split_station'],r['merge_station'])+r['taper_length']>=r['length']:raise ValueError('Interchange taper exceeds road')
  if not r['median_width']<r['turn_station']<r['length']-r['median_setback']-r['median_width']:raise ValueError('Median setback exceeds available road')
  for c in r['connections']:entity(c)
 elif g['fixture']=='parking':
  p=g['parking'];entity(p);entity(p['access_road']);entity(p['connection'])
  if len(p['vertices'])<3:raise ValueError('Parking lot needs at least 3 vertices')
  geometry.polygon_valid(p['vertices']);geometry.triangulate([(*v,0) for v in p['vertices']])
  for island in p['islands']:
   entity(island);geometry.polygon_valid(island['vertices']);geometry.triangulate([(*v,0) for v in island['vertices']])
   if not all(geometry.point_inside(v,p['vertices']) for v in island['vertices']):raise ValueError('Planter island must be inside lot')
  for i,island in enumerate(p['islands']):
   for other in p['islands'][i+1:]:
    if geometry.polygons_overlap(island['vertices'],other['vertices']):raise ValueError('Planter islands overlap')
  for row in p['rows']:entity(row)
 else:raise ValueError('Unsupported fixture')
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate persistent IDs')
 def finite(x):
  if isinstance(x,float) and not math.isfinite(x):raise ValueError('Non-finite parameter')
  if isinstance(x,dict):
   for v in x.values():finite(v)
  if isinstance(x,list):
   for v in x:finite(v)
 finite(g);return g

def loads(text):return validate(json.loads(text))
def dumps(g):return json.dumps(validate(g),sort_keys=True,indent=2,allow_nan=False)
def build(g):
 if g.get('version')==3:
  from . import network
  return network.build(g)
 validate(g)
 return geometry.build_parking(g) if g['fixture']=='parking' else geometry.build_interchange(g) if g['fixture']=='interchange' else geometry.build_arterial(g) if g['fixture']=='arterial' else geometry.build_boulevard(g) if g['fixture']=='boulevard' else geometry.build_junction(g)
def change_endpoint(g,crosswalk_id,key,patch):
 result=copy.deepcopy(g);e=next(c for c in result['crosswalks'] if c['id']==crosswalk_id)['endpoints'][key]
 if 'id' in patch:raise ValueError('Persistent IDs cannot be edited')
 e.update(copy.deepcopy(patch));result['revision']=result.get('revision',0)+1;return validate(result)

def mesh_digest(specs):
 import hashlib
 serial=[{k:s.get(k) for k in ('id','verts','faces','points','metadata')} for s in specs]
 return hashlib.sha256(json.dumps(serial,sort_keys=True).encode()).hexdigest()
