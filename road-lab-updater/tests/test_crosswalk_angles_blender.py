"""Angled crossings reach their curb and pads conform over complete faces."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import road_core,lane_editor,crosswalk_layout,crosswalk_ramps
from RoadLab.road_edges import boundary
scene=bpy.context.scene;road=scene.wb_native.road
for angle in (30.,45.,70.,90.,110.,135.,150.):
 radians=math.radians(angle);road.data.splines[1].points[2].co=(55*math.cos(radians),55*math.sin(radians),.52,1)
 configs=lane_editor.state(road)
 # Exercise independent crossing endpoint setbacks, rather than just square crossings.
 configs[3]['crosswalk_a']=1.5 if angle!=90 else 0.;road['roadlab_lanes']=json.dumps(configs)
 road_core.rebuild(road,True);lane_editor.rebuild(road,scene,True)
 assert not road.get('roadlab_core_error'),road.get('roadlab_core_error')
 catalog=json.loads(road['roadlab_generated_marking_catalog']);crossings=[m for m in catalog if m['role'][0]=='crosswalk'];pads=[m for m in catalog if m['asset']=='tactile_pad'];assert crossings and pads
 def edge_distance(point):
  point=Vector(point);best=1e9
  for a,b in boundary(road):
   a,b=Vector(a),Vector(b);d=b-a;d.z=0;t=max(0.,min(1.,(point-a).dot(d)/max(d.length_squared,1e-12)));best=min(best,(point-a-d*t).xy.length)
  return best
 for mark in crossings:
  assert max(edge_distance(p) for p in mark['crosswalk_ends'])<1e-4
 target=road['roadlab_marking_object'];slots={i for i,m in enumerate(target.data.materials) if 'tactile_pad' in m.name};actual=0.
 for face in target.data.polygons:
  if face.material_index in slots:
   a,b,c=(target.data.vertices[i].co for i in list(face.vertices)[:3]);actual+=abs((b-a).cross(c-a).z)/2
 assert actual>sum(m['size'][0]*m['size'][1] for m in pads)*.93,('Generated pads lost faces',angle,actual)
 triangles,footprint=crosswalk_layout.concrete(road);tree=crosswalk_ramps.surface_tree(road)
 for pad in pads:
  end=Vector(pad['crosswalk_end']);out=Vector(pad['crosswalk_outward']);probe=end+out*.12
  curb=tree.ray_cast(Vector((probe.x,probe.y,100)),Vector((0,0,-1)))[0]
  assert curb is not None and curb.z-end.z<.045,('Curb opening did not reach the crossing',angle,tuple(end),curb)
  assert len(pad.get('pad_path',[]))==17,('Pad did not follow the sidewalk',angle,pad)
  verts,faces,uv=crosswalk_layout.decal(pad,triangles);assert faces
  area=sum((Vector(verts[f[1]])-Vector(verts[f[0]])).cross(Vector(verts[f[2]])-Vector(verts[f[0]])).z/2 for f in faces)
  assert area>pad['size'][0]*pad['size'][1]*.95,('Pad lost part of its footprint',angle,area)
  for face in faces:
   for weights in ((1/3,1/3,1/3),(.6,.2,.2)):
    p=sum((Vector(verts[i])*w for i,w in zip(face,weights)),Vector())
    hit=tree.ray_cast(Vector((p.x,p.y,100)),Vector((0,0,-1)))[0]
    assert hit is not None and .002<p.z-hit.z<.004,('Pad interior clips concrete',angle,tuple(p),hit)
 print('CROSSWALK_ANGLE_PASS',angle,len(crossings),len(pads),flush=True)
print('CROSSWALK_ANGLES_PASS',flush=True)

# A nearly transverse curb segment must not throw an edge line across lanes.
from RoadLab import road_edges,point_settings
config=lane_editor.state(road)[0];rows={r['id']:r for r in point_settings.records(road)}
a,b=(Vector(rows[i]['co']) for i in config['endpoints']);u=b-a;u.z=0;u.normalize();n=Vector((-u.y,u.x,0));center=a.lerp(b,.5)
original=road_edges.boundary
try:
 road_edges.boundary=lambda obj:[(tuple(center-u*.02-n*6),tuple(center+u*.02-n*2))]
 mark=dict(asset='line_white',role=['outer',1],forward=list(u[:2]),center=list(center-n*3.5),size=[.1524,.02])
 fitted=road_edges.fit(road,config,[mark])[0]['path']
 assert all((Vector(p)-center).dot(n)<-1.9 for p in fitted),'Edge line crossed the carriageway at a steep curb angle'
finally:road_edges.boundary=original
print('STEEP_EDGE_NORMAL_OFFSET_PASS',flush=True)

# Exact triangle clipping still selects the intended deck at an overpass.
mark=dict(asset='line_white',role=['crosswalk',1,0],center=[0,0,0],forward=[0,1],size=[1,1])
triangles=[]
for z in (0.,5.):
 triangles.extend([(Vector((-1,-1,z)),Vector((1,-1,z)),Vector((1,1,z))),(Vector((-1,-1,z)),Vector((1,1,z)),Vector((-1,1,z)))])
verts,faces,uv=crosswalk_layout.decal(mark,triangles,lambda x,y,z,on_terrain:(x,y,.003))
assert faces and all(abs(p[2]-.003)<1e-6 for p in verts)
print('CROSSWALK_DECK_SELECTION_PASS',flush=True)
