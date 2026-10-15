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
 def test_no_receiving_arrows(self):
  for side in ('RIGHT','LEFT'):
   ms=plan((0,0,0),(0,100,0),[Lane('i')],[Lane('o')],8.,side,trim_end=12)
   arrows=[m for m in ms if m['asset'].startswith('arrow_')]
   self.assertTrue(arrows);self.assertEqual({tuple(m['forward']) for m in arrows},{(0.,1.)})
   self.assertTrue(all(m['center'][1]-m['size'][1]/2>=53 for m in arrows))
 def test_two_junctions_approach_both_ends(self):
  ms=plan((0,0,0),(0,100,0),[Lane('i')],[Lane('o')],8.,trim_start=12,trim_end=12)
  arrows=[m for m in ms if m['asset'].startswith('arrow_')];self.assertEqual({tuple(m['forward']) for m in arrows},{(0.,1.),(0.,-1.)})
  for m in arrows:
   if m['forward'][1]>0:self.assertGreaterEqual(m['center'][1]-m['size'][1]/2,50)
   else:self.assertLessEqual(m['center'][1]+m['size'][1]/2,50)
 def test_no_junction_or_disabled_arrows(self):
  for kwargs in ({},{'trim_end':12,'arrow_approach':0}):
   ms=plan((0,0,0),(0,100,0),[Lane('i')],[Lane('o')],8.,**kwargs)
   self.assertFalse(any(m['asset'].startswith('arrow_') for m in ms))
 def test_rotation_and_z(self):
  ms=plan((0,0,0),(100,0,10),[Lane('i')],[Lane('o')],8.,trim_end=10,control_incoming='STOP');bar=next(m for m in ms if m['asset']=='stop_bar');self.assertEqual(bar['forward'],[1.,0.]);self.assertAlmostEqual(bar['center'][2],bar['center'][0]/10)

 def test_changed_junction_keeps_lines_but_filters_unavailable_arrows(self):
  for side in ('RIGHT','LEFT'):
   ms=plan((0,0,0),(0,100,0),[Lane('i0',3.5,frozenset({'THROUGH'})),Lane('i1',3.5,frozenset({'RIGHT'}))],[Lane('o')],11.5,side,trim_end=12,allowed_incoming={'RIGHT'})
   self.assertTrue(any(m['role'][0]=='center-yellow' for m in ms))
   self.assertEqual(len([m for m in ms if m['role'][0]=='outer']),2)
   self.assertFalse(any(m['asset']=='arrow_through' for m in ms))
   self.assertTrue(any(m['asset']=='arrow_right' and m['role'][2]==1 for m in ms))

 def test_crosswalk_endpoints_move_independently_and_stop_line_stays_behind(self):
  def crossing(**kw):return plan((0,0,0),(0,100,0),[Lane('i')],[Lane('o')],8.,trim_end=10,crosswalk_incoming=True,crosswalk_tactile=True,control_incoming='STOP',**kw)
  original=crossing();moved=crossing(crosswalk_a=4)
  first=next(m for m in original if m['role'][0]=='crosswalk');second=next(m for m in moved if m['role'][0]=='crosswalk')
  self.assertEqual(first['crosswalk_ends'][1],second['crosswalk_ends'][1])
  self.assertAlmostEqual(first['crosswalk_ends'][0][1]-second['crosswalk_ends'][0][1],4.)
  self.assertNotEqual(first['forward'],second['forward'])
  self.assertEqual(len([m for m in moved if m['asset']=='tactile_pad']),2)
  bar=next(m for m in moved if m['asset']=='stop_bar')
  self.assertLess(bar['center'][1]+bar['size'][1]/2,min(p[1] for p in second['crosswalk_ends']))
 def test_midblock_crosswalk_needs_no_junction(self):
  ms=plan((0,0,0),(0,100,0),[Lane('i')],[Lane('o')],8.,crosswalk_incoming=True)
  self.assertTrue(any(m['role'][0]=='crosswalk' for m in ms))
  self.assertFalse(any(m['asset'].startswith('arrow_') for m in ms))

if __name__=='__main__':unittest.main()
