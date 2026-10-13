import unittest,sys,types,json,math,copy
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parents[1]
# Blender add-on __init__ cannot load in ordinary Python; import portable modules only.
if 'WB_TrackTools' not in sys.modules:
 pkg=types.ModuleType('WB_TrackTools');pkg.__path__=[str(root)];sys.modules['WB_TrackTools']=pkg
from WB_TrackTools import model,geometry
class ConnectedTests(unittest.TestCase):
 def setUp(self):self.g=model.loads((root/'fixtures/intersection.json').read_text())
 def test_ribbon_top_normals(self):
  spec=geometry.ribbon('test',[(0,0,0),(2,0,0)],[(0,0),(1,0)],'concrete')
  a,b,c=[spec['verts'][k] for k in spec['faces'][0][:3]]
  self.assertGreater(geometry.cross(geometry.sub(b,a),geometry.sub(c,a)),0)
 def test_parking_concave_polygon(self):
  g=model.loads((root/'fixtures/parking.json').read_text());g['parking']['vertices']=[[12,-28],[62,-28],[62,32],[40,32],[40,26],[12,26]];specs,_,_=model.build(g);self.assertTrue(specs)
 def test_planter_outside_rejected(self):
  g=model.loads((root/'fixtures/parking.json').read_text());g['parking']['islands'][0]['vertices'][0]=[500,500];self.assertRaises(ValueError,model.validate,g)
 def test_planter_overlap_rejected(self):
  g=model.loads((root/'fixtures/parking.json').read_text());g['parking']['islands'][1]['vertices']=copy.deepcopy(g['parking']['islands'][0]['vertices']);self.assertRaises(ValueError,model.validate,g)
 def test_island_edit_keeps_parking_outline(self):
  g=model.loads((root/'fixtures/parking.json').read_text());outline=copy.deepcopy(g['parking']['vertices']);g['parking']['islands'][0]['vertices'][0][0]+=1;model.build(g);self.assertEqual(g['parking']['vertices'],outline)
 def test_parking_cuts_have_explicit_target(self):
  g=model.loads((root/'fixtures/parking.json').read_text());specs=model.build(g)[0];cuts=[x for x in specs if x['category']=='cutter'];self.assertEqual(len(cuts),2)
  for cut in cuts:self.assertEqual(cut['metadata']['cut_target'],'parking-lot-parking-1')
 def test_sidewalks_outside_pavement(self):
  for fixture in ('arterial','boulevard'):
   g=model.loads((root/'fixtures'/(fixture+'.json')).read_text());specs=model.build(g)[0]
   road=next(x for x in specs if x['category']=='road')
   outside_y=max(v[1] for v in road['verts'])
   sidewalks=[x for x in specs if x['category']=='sidewalk']
   self.assertGreater(max(v[1] for sw in sidewalks for v in sw['verts']),outside_y)
   self.assertLess(min(v[1] for sw in sidewalks for v in sw['verts']),min(v[1] for v in road['verts']))
 def test_arterial_one_side_edit_preserves_opposite(self):
  g=model.loads((root/'fixtures/arterial.json').read_text());before=model.build(g)[0];g['boulevard']['outer_turns'][0]['width']=4.2;after=model.build(g)[0]
  a=next(x for x in before if x['id']=='curb-arterial-outer--1');b=next(x for x in after if x['id']=='curb-arterial-outer--1');self.assertEqual(a,b)
 def test_driveways_staggered(self):
  g=model.loads((root/'fixtures/arterial.json').read_text());self.assertNotEqual(g['boulevard']['driveways'][0]['station'],g['boulevard']['driveways'][1]['station']);self.assertTrue(model.build(g)[0])
 def test_interchange_decks_have_no_lower_connections(self):
  g=model.loads((root/'fixtures/interchange.json').read_text());specs=model.build(g)[0];decks=[x for x in specs if x['category']=='bridge'];self.assertEqual(len(decks),2)
  for d in decks:self.assertEqual(d['metadata']['connections_to_lower'],[]);self.assertGreater(min(v[2] for v in d['verts']),6)
 def test_median_setback_independent_of_ramp(self):
  g=model.loads((root/'fixtures/interchange.json').read_text());before=model.build(g)[0];g['interchange']['median_setback']=18;after=model.build(g)[0]
  a=next(x for x in before if x['id']=='interchange-off-ramp');b=next(x for x in after if x['id']=='interchange-off-ramp');self.assertEqual(a,b)
  a=next(x for x in before if x['id']=='interchange-far-median');b=next(x for x in after if x['id']=='interchange-far-median');self.assertNotEqual(a,b)
 def test_warning_domes_closed(self):
  e=geometry.resolve_endpoint(self.g['junction'],self.g['crosswalks'][0]['endpoints']['A']);spec=geometry.warning_domes(e);counts=Counter()
  for f in spec['faces']:
   for a,b in zip(f,f[1:]+f[:1]):counts[tuple(sorted((a,b)))]+=1
  self.assertTrue(all(v==2 for v in counts.values()))
 def test_endpoints_face_each_other(self):
  _,_,res=model.build(self.g)
  for ends in res.values():
   a,b=ends['A'],ends['B'];d=geometry.norm2(geometry.sub(b['position'],a['position']))
   fa=(math.sin(a['rotation']),-math.cos(a['rotation']));fb=(math.sin(b['rotation']),-math.cos(b['rotation']))
   self.assertGreater(sum(fa[k]*d[k] for k in range(2)),.999);self.assertLess(sum(fb[k]*d[k] for k in range(2)),-.999)
 def test_solid_geometry_closed(self):
  specs,_,_=model.build(self.g)
  for spec in specs:
   if spec['category'] not in ('road','curb','sidewalk','gutter'):continue
   counts=Counter()
   for f in spec['faces']:
    for a,b in zip(f,f[1:]+f[:1]):counts[tuple(sorted((a,b)))]+=1
   self.assertTrue(all(n==2 for n in counts.values()),spec['id'])
 def test_triangle_areas_match_polygon(self):
  polygon,_=geometry.junction_boundary(self.g['junction']);tri=geometry.triangulate(polygon)
  total=sum(geometry.cross(geometry.sub(polygon[b],polygon[a]),geometry.sub(polygon[c],polygon[a]))/2 for a,b,c in tri)
  self.assertAlmostEqual(total,geometry.area(polygon),places=6)
 def test_corner_edit_local(self):
  _,before=geometry.junction_boundary(self.g['junction']);self.g['junction']['corners']['NW']['radius']=10;_,after=geometry.junction_boundary(self.g['junction'])
  for a,b in zip(before,after):self.assertEqual(a['points']==b['points'],a['label']!='NW')
 def test_endpoint_edit_local(self):
  changed=model.change_endpoint(self.g,'crosswalk-N','A',{'station':28,'run':2.5})
  self.assertEqual(changed['crosswalks'][0]['endpoints']['B'],self.g['crosswalks'][0]['endpoints']['B'])
  _,_,before=model.build(self.g);_,_,after=model.build(changed)
  self.assertEqual(before['crosswalk-N']['B'],after['crosswalk-N']['B'])
 def test_ramp_lowers_curb(self):
  j=self.g['junction'];_,chains=geometry.junction_boundary(j);e=geometry.resolve_endpoint(j,self.g['crosswalks'][0]['endpoints']['A']);chain=next(c for c in chains if geometry.nearest_station(c['points'],e['position'])[0]<.01)
  specs=geometry.curb_sidewalk(chain,[e],self.g['settings']);curb=specs[0]
  near=[v for v in curb['verts'] if math.dist(v[:2],e['position'][:2])<.05]
  self.assertTrue(near);self.assertLess(min(v[2] for v in near),.01)
 def test_boulevard_fixed_opposition(self):
  g=model.loads((root/'fixtures/boulevard.json').read_text());before,_,_=model.build(g);g['boulevard']['pocket_start']=20;after,_,_=model.build(g)
  # sample grid changes with exact taper endpoints; compare physical opposing bounds.
  a=next(x for x in before if x['id']=='boulevard-opposing');b=next(x for x in after if x['id']=='boulevard-opposing')
  self.assertEqual(sorted(set(v[1] for v in a['points'])),sorted(set(v[1] for v in b['points'])))
 def test_median_ends_before_road(self):
  g=model.loads((root/'fixtures/boulevard.json').read_text());specs,_,_=model.build(g);median=next(x for x in specs if x['category']=='median');road=g['boulevard']
  self.assertAlmostEqual(max(v[0] for v in median['verts']),road['median_end']);self.assertLess(road['median_end'],road['length'])
 def test_pocket_station_precision(self):
  g=model.loads((root/'fixtures/boulevard.json').read_text());b=g['boulevard'];rows=geometry.boulevard_sections(b)
  row=next(x for x in rows if x[0]==b['pocket_start']+b['taper_length']);self.assertAlmostEqual(row[2],b['median_width']/2-b['lane_width'])
 def test_skew_and_offset(self):
  g=model.loads((root/'fixtures/skew.json').read_text());specs,diag,_=model.build(g);self.assertTrue(specs);self.assertEqual(diag,[])
 def test_determinism_v2(self):self.assertEqual(model.mesh_digest(model.build(self.g)[0]),model.mesh_digest(model.build(self.g)[0]))
 def test_metadata_roundtrip(self):self.assertEqual(model.loads(model.dumps(self.g)),self.g)
 def test_duplicate_id_rejected(self):
  self.g['crosswalks'][0]['endpoints']['A']['id']=self.g['crosswalks'][0]['id'];self.assertRaises(ValueError,model.validate,self.g)
 def test_invalid_radius_rejected(self):
  self.g['junction']['corners']['NW']['radius']=1000;self.assertRaises(ValueError,model.build,self.g)
 def test_manual_override_preserved(self):
  e=geometry.resolve_endpoint(self.g['junction'],self.g['crosswalks'][0]['endpoints']['A']);e['mode']='manual';self.g['crosswalks'][0]['endpoints']['A']=e;self.g['junction']['corners']['NW']['radius']=12
  _,_,res=model.build(self.g);self.assertEqual(res['crosswalk-N']['A']['position'],e['position'])
 def test_movement_directions(self):
  lanes=self.g['junction']['lanes'];lanes[0]['travel']='outgoing'
  self.assertRaises(ValueError,geometry.lane_paths,self.g['junction'])
if __name__=='__main__':unittest.main(verbosity=2)
