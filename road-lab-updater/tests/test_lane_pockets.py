"""Portable tests for local taper widths, source invariance, cyclic and reversed paths."""
import importlib.util, pathlib,unittest,copy
path=pathlib.Path(__file__).resolve().parents[1]/'extension'/'RoadLab'/'lane_pockets.py'
spec=importlib.util.spec_from_file_location('pockets',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Pockets(unittest.TestCase):
 def setUp(self):
  self.coords=[(i*30.,0.,0.) for i in range(5)];self.ids=list('abcde');self.p=dict(anchors=['c'],axis=['a','b'],side=-1,width=3.5,length=12.,taper=15.)
 def test_local(self):
  s=m.locate(self.coords,self.ids,self.p)
  self.assertEqual([s[k] for k in ('start','lo','hi','end')],[39.,54.,66.,81.]);self.assertEqual(m.amount(0,s),0);self.assertEqual(m.amount(60,s),3.5);self.assertAlmostEqual(m.amount(46.5,s),1.75)
 def test_extend_keeps_entry(self):
  a=m.locate(self.coords,self.ids,self.p);p=dict(self.p,anchors=['c','d']);b=m.locate(self.coords,self.ids,p)
  self.assertEqual(a['start'],b['start']);self.assertEqual(a['lo'],b['lo']);self.assertGreater(b['end'],a['end'])
 def test_one_sided_source(self):
  original=copy.deepcopy(self.coords);paths,angles,_=m.expand([(self.coords,[1.]*5)],[self.ids],[self.p],8.)
  self.assertEqual(original,self.coords)
  for co,radius in zip(*paths[0]):
   self.assertAlmostEqual(co[1]+radius*4,4.,places=6)
 def test_flip(self):
  a,_,_=m.expand([(self.coords,[1.]*5)],[self.ids],[self.p],8.)
  b,_,_=m.expand([(self.coords,[1.]*5)],[self.ids],[dict(self.p,side=1)],8.)
  for p,q in zip(a[0][0],b[0][0]):self.assertEqual(p[0],q[0]);self.assertEqual(p[1],-q[1])
 def test_reversal(self):
  a=m.locate(self.coords,self.ids,self.p);b=m.locate(self.coords[::-1],self.ids[::-1],self.p)
  self.assertEqual(a['side'],-b['side']);self.assertEqual(a['start'],b['start'])
 def test_junction(self):
  p=dict(self.p,anchors=['a'],junction=True,junction_anchor='a',junction_direction=1,length=24.)
  s=m.locate(self.coords,self.ids,p);self.assertEqual(s['lo'],0);self.assertEqual(s['hi'],24)
  b=m.locate(self.coords[::-1],self.ids[::-1],p);self.assertEqual(b['lo'],96);self.assertEqual(b['hi'],120)
 def test_cyclic_wrap(self):
  coords=[(0,0,0),(30,0,0),(30,30,0),(0,30,0),(0,0,0)];p=dict(self.p,anchors=['a']);s=m.locate(coords,list('abcd'),p)
  self.assertGreater(m.amount(118,s),3.4);self.assertGreater(m.amount(2,s),3.4);self.assertEqual(m.amount(60,s),0)
 def test_junction_does_not_spill_across(self):
  p=dict(self.p,anchors=['c'],junction=True,junction_anchor='c',junction_direction=1,length=24.)
  s=m.locate(self.coords,self.ids,p)
  self.assertEqual(m.amount(59,s),0);self.assertEqual(m.amount(60,s),3.5)
 def test_linked_halves_share_one_lane(self):
  a=dict(self.p,anchors=['c'],junction=True,junction_anchor='c',junction_direction=-1,length=24.,link_group='through')
  b=dict(a,junction_direction=1,receiving=True)
  specs=[m.locate(self.coords,self.ids,p) for p in (a,b)]
  self.assertEqual(m.offsets(60,specs),(0.,3.5))
  shifted=m.junction_shifts([(self.coords,[1.]*5)],[self.ids],[a,b],[self.coords[2]])
  self.assertEqual(shifted[self.coords[2]],(0.,-1.75))
 def test_cyclic_geometry_closes(self):
  coords=[(0,0,0),(30,0,0),(30,30,0),(0,30,0),(0,0,0)]
  p=dict(self.p,anchors=['a']);paths,_,_=m.expand([(coords,[1.]*5)],[list('abcd')],[p],8.)
  self.assertEqual(paths[0][0][0],paths[0][0][-1])
if __name__=='__main__':unittest.main()
