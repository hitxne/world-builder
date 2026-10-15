import sys,types,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'extension'/'RoadLab'
pkg=types.ModuleType('RoadLab');pkg.__path__=[str(root)];sys.modules['RoadLab']=pkg
from RoadLab.lane_markings import plan
from RoadLab.lane_logic import Lane

class ApproachTests(unittest.TestCase):
 def markings(self,**kwargs):
  return plan((0,0,0),(0,100,0),[Lane('left',movements=frozenset({'LEFT'})),Lane('through')],[Lane('receiver')],11.5,trim_end=12,**kwargs)
 def test_controlled_stop_spans_incoming_only(self):
  ms=self.markings(control_incoming='STOP');bar=next(m for m in ms if m['asset']=='stop_bar');self.assertEqual(bar['size'],[7.,.6096]);self.assertAlmostEqual(bar['center'][0],1.75);self.assertAlmostEqual(bar['center'][1]+bar['size'][1]/2,86.78)
  for m in ms:
   if m['asset'].startswith('arrow_') and m['forward']==[0,1]:self.assertLess(m['center'][1]+m['size'][1]/2,bar['center'][1]-bar['size'][1]/2)
 def test_no_stop_on_yield_uncontrolled_or_dead_end(self):
  for control in ('NONE','YIELD'):self.assertFalse(any(m['asset']=='stop_bar' for m in self.markings(control_incoming=control)))
  self.assertFalse(any(m['asset']=='stop_bar' for m in plan((0,0,0),(0,100,0),[Lane('i')],[],4.5,control_incoming='STOP')))
 def test_solid_approach_and_dotted_added_lane(self):
  ms=self.markings(control_incoming='SIGNAL',emerging_incoming=[0]);self.assertTrue(any(m['asset']=='dotted_white' for m in ms));self.assertTrue(any(m['asset']=='broken_white' for m in ms))
  dividers=[m for m in ms if abs(m['center'][0]-1.75)<1e-6 and m['asset']=='line_white'];self.assertEqual(len(dividers),1);self.assertAlmostEqual(dividers[0]['size'][1],20.)
 def test_short_block_and_left_side(self):
  for side in ('RIGHT','LEFT'):
   for length in (2,15,25,100):
    ms=plan((0,0,0),(0,length,0),[Lane('i0'),Lane('i1')],[Lane('o0'),Lane('o1')],15.,side,trim_start=2,trim_end=2,control_incoming='STOP',control_outgoing='SIGNAL',emerging_incoming=[0],emerging_outgoing=[1])
    for m in ms:self.assertGreater(min(m['size']),0);self.assertGreaterEqual(m['center'][1]-m['size'][1]/2,2-1e-6);self.assertLessEqual(m['center'][1]+m['size'][1]/2,length-2+1e-6)
 def test_rotation_and_z(self):
  ms=plan((0,0,0),(100,0,10),[Lane('i')],[Lane('o')],8.,trim_end=10,control_incoming='STOP');bar=next(m for m in ms if m['asset']=='stop_bar');self.assertEqual(bar['forward'],[1.,0.]);self.assertAlmostEqual(bar['center'][2],bar['center'][0]/10)

if __name__=='__main__':unittest.main()
