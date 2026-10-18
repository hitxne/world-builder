import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import crosswalk_ramps as ramps
road=bpy.context.scene.wb_native.road
import bmesh
sidewalk=next(l.object for l in ramps.layers(road) if l.kind=='sidewalk')
e=sidewalk.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh();bm=bmesh.new();bm.from_mesh(m)
assert all(e.is_manifold for e in bm.edges)
print('PANELS',len(m.vertices),len(m.polygons),'bad edges',sum(not e.is_manifold for e in bm.edges),flush=True)
seen=set();components=[]
for v in bm.verts:
 if v in seen:continue
 seen.add(v);stack=[v];vs=[]
 while stack:
  p=stack.pop();vs.append(p)
  for edge in p.link_edges:
   other=edge.other_vert(p)
   if other not in seen:seen.add(other);stack.append(other)
 lo=[min(p.co[a] for p in vs) for a in range(3)];hi=[max(p.co[a] for p in vs) for a in range(3)]
 components.append((len(vs),lo,hi))
print('COMPONENTS',len(components),'straight',[(n,tuple(round(b-a,4) for a,b in zip(lo,hi))) for n,lo,hi in components if lo[0]>4.32 and hi[0]<7.6 and hi[1]<-15][:15],flush=True)
assert len(components)>200
# Crosswalk landings intentionally lower whole inner blocks. Ordinary
# blocks away from the crossing must retain the stock top and thickness.
flat=[(n,lo,hi) for n,lo,hi in components if lo[0]>18 or hi[0]<-18 or lo[1]>18 or hi[1]<-18]
assert len(flat)>100 and all(abs(hi[2]-.1724)<1e-5 for n,lo,hi in flat),'Flat panels away from crossings changed elevation'
assert all(.0199<=hi[2]<=.1725 for n,lo,hi in components),'Crossing panels rose above the sidewalk or below the street'
assert any(hi[2]<.16 for n,lo,hi in components),'No complete sidewalk block followed the lowered crossing landing'
# End-cap miters extend beyond their source interval; measure ordinary straight
# blocks away from both the junction and the road-end construction joint.
rectangles=[(n,lo,hi) for n,lo,hi in components if n==8 and lo[0]>4.32 and hi[0]<7.6 and lo[1]>-50 and hi[1]<-15]
assert len(rectangles)>10
for n,lo,hi in rectangles:
 assert 1.45<hi[0]-lo[0]<1.75 and 1.2<hi[1]-lo[1]<1.8,(lo,hi)
 assert hi[2]-lo[2]<.201
bm.free();e.to_mesh_clear()
print('SIDEWALK_PANELS_PASS')
