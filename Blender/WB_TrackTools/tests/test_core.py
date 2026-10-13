import unittest,sys,json,copy,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
class Tests(unittest.TestCase):
 def setUp(self): self.g=core.loads((Path(__file__).resolve().parents[1]/'fixtures/pilot.json').read_text())
 def test_units(self): self.assertAlmostEqual(core.meters(6,'in'),.1524);self.assertAlmostEqual(core.meters(12,'ft'),3.6576)
 def test_roundtrip(self): self.assertEqual(core.loads(core.dumps(self.g)),self.g)
 def test_fixed_right_edge(self):
  r=copy.deepcopy(self.g['roads'][0]);r['left']=[[0,3],[80,3]];v,_,_=core.road_mesh(r);r=copy.deepcopy(r);r['left']=[[0,3],[20,3],[40,6.66],[80,6.66]];v2,_,_=core.road_mesh(r)
  self.assertEqual(v[1::2],v2[1::2]);self.assertNotEqual(v[::2],v2[::2])
 def test_determinism(self): self.assertEqual(core.road_mesh(self.g['roads'][0]),core.road_mesh(self.g['roads'][0]))
 def test_corner_isolation(self):
  c=self.g['intersections'][0]['corners'];before={k:core.corner_arc(x['vertex'],x['a'],x['b'],x['radius']) for k,x in c.items()};c['NW']['radius']=9
  after={k:core.corner_arc(x['vertex'],x['a'],x['b'],x['radius']) for k,x in c.items()}
  self.assertNotEqual(before['NW'],after['NW']);self.assertEqual([before[k] for k in ('NE','SW','SE')],[after[k] for k in ('NE','SW','SE')])
 def test_endpoint_isolation(self):
  g=core.move_endpoint(self.g,'cross-1','A',[1,2,0]);self.assertEqual(g['crosswalks'][0]['endpoints']['B'],self.g['crosswalks'][0]['endpoints']['B'])
 def test_corner_radius(self):
  p=core.corner_arc((0,0,0),(1,0),(0,1),5)
  for x,y,z in p: self.assertAlmostEqual(math.hypot(x-5,y-5),5)
 def test_invalid_ids(self):
  self.g['roads'].append(self.g['roads'][0]);self.assertRaises(ValueError,core.validate,self.g)
 def test_ramp_profile(self):
  v,f=core.ramp_mesh(self.g['crosswalks'][0]['endpoints']['A']);self.assertEqual(v[1][2],0);self.assertEqual(v[2][2],0);self.assertGreater(v[0][2],0)
 def test_order(self): self.assertEqual(core.CARDINAL_ORDER,('NW','NE','SW','SE'))
if __name__=='__main__': unittest.main(verbosity=2)
