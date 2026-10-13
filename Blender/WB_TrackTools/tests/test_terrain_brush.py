import unittest,importlib.util,pathlib
path=pathlib.Path(__file__).parents[1]/'terrain_brush.py'
spec=importlib.util.spec_from_file_location('terrain_brush_test',path);brush=importlib.util.module_from_spec(spec);spec.loader.exec_module(brush)

class TerrainBrushTests(unittest.TestCase):
 def test_raise_lower_and_circle(self):
  points=[(0,0),(1,0),(2,0),(1.5,1.5)];values=[0]*4
  raised=brush.stamp(points,values,(0,0),2,4,.5,'RAISE')
  self.assertEqual(raised,[2,1,0,0]);self.assertEqual(brush.stamp(points,raised,(0,0),2,4,.5,'LOWER'),values)
 def test_flatten_converges_without_overshoot(self):
  out=brush.stamp([(0,0),(1,0)],[10,-10],(0,0),5,100,1,'FLATTEN',target=3)
  self.assertTrue(all(abs(h-3)<1e-8 for h in out))
 def test_smooth_uses_snapshot(self):
  out=brush.stamp([(0,0),(1,0),(2,0)],[0,10,0],(1,0),3,1,1,'SMOOTH',neighbors=[[1],[0,2],[1]])
  self.assertGreater(out[0],0);self.assertLess(out[1],10);self.assertAlmostEqual(out[0],out[2])
 def test_strength_zero_and_invalid_mode(self):
  self.assertEqual(brush.stamp([(0,0)],[4],(0,0),1,0,1,'RAISE'),[4])
  with self.assertRaises(ValueError):brush.stamp([(0,0)],[4],(0,0),1,1,1,'INVALID')
