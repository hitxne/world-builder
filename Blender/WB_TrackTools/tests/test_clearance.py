import unittest,importlib.util,pathlib
p=pathlib.Path(__file__).parents[1]/'terrain_clearance.py';s=importlib.util.spec_from_file_location('clearance',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ClearanceTests(unittest.TestCase):
 def test_road_crosses_face_with_all_vertices_outside(self):
  road=[(.3,.3,0),(.7,.3,0),(.3,.7,0)];terrain=[(0,0,2),(2,0,2),(0,2,2)];index=m.SurfaceIndex(road,[(0,1,2)])
  self.assertGreater(m.measure(terrain,[(0,1,2)],index)['violating_overlaps'],0)
  result,ceilings,report=m.enforce(terrain,[(0,1,2)],index)
  self.assertEqual(m.measure(result,[(0,1,2)],index)['violating_overlaps'],0)
  self.assertTrue(all(p[2]<-.025 for p in result))
 def test_sloping_surface_and_shared_faces(self):
  road=[(0,0,0),(2,0,1),(0,2,0),(2,2,1)];terrain=[(0,0,2),(2,0,-1),(0,2,2),(2,2,3)];faces=[(0,1,2),(1,3,2)];index=m.SurfaceIndex(road,faces)
  result,ceilings,report=m.enforce(terrain,faces,index)
  self.assertEqual(m.measure(result,faces,index)['violating_overlaps'],0)
  for a,b in zip(terrain,result):self.assertLessEqual(b[2],a[2])
 def test_outside_terrain_preserved(self):
  index=m.SurfaceIndex([(0,0,0),(1,0,0),(0,1,0)],[(0,1,2)])
  terrain=[(5,5,10),(6,5,10),(5,6,10)];result,ceilings,report=m.enforce(terrain,[(0,1,2)],index)
  self.assertEqual(result,[list(p) for p in terrain]);self.assertEqual(report['protected_vertices'],0)
 def test_overlap_area_and_affine_maximum(self):
  polygon=m.clip([(0,0),(2,0),(0,2)],[(.5,.5),(1.5,.5),(.5,1.5)])
  self.assertAlmostEqual(m.area(polygon),.5)
