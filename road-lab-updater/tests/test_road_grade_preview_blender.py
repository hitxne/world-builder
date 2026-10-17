"""Road height brushes grade terrain live; cancellation and final seams agree."""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,core_terrain,road_sculpt
from RoadLab.native_extension import set_input
from RoadLab.road_grade_preview import RoadGradePreview
scene=bpy.context.scene
curve=bpy.data.curves.new('Grade test','CURVE');curve.dimensions='3D'
s=curve.splines.new('POLY');s.points.add(1)
for p,co in zip(s.points,[(-30,0,.02,1),(30,0,.02,1)]):p.co=co
road=bpy.data.objects.new('Grade test',curve);scene.collection.objects.link(road)
scene.wb_native.road=road;road_core.attach(road)
set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
mesh=bpy.data.meshes.new('Terrain source');mesh.from_pydata([(-80,-80,0),(80,-80,0),(80,80,0),(-80,80,0)],[],[(0,1,2,3)])
terrain=bpy.data.objects.new('Terrain',mesh);scene.collection.objects.link(terrain)
scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True
core_terrain.rebuild(scene,True)
helper=terrain['roadlab_core_terrain_mesh'];original=helper.data
baseline=[tuple(v.co) for v in original.vertices]
preview=RoadGradePreview(scene,road)
assert preview.bindings
# The live path must not invoke the full terrain compiler per brush sample.
rebuild=core_terrain.rebuild
def forbidden(*args,**kwargs):raise AssertionError('Full terrain rebuild during height stroke')
core_terrain.rebuild=forbidden
road_sculpt._PAINTING=True
try:
    for _ in range(4):assert road_sculpt.apply_stamp(bpy.context,road,(0,0),'RAISE',24,2,.1,preview=True,grade_preview=preview)
    assert road_core.flush_pending(force=True) is False
finally:
    core_terrain.rebuild=rebuild;road_sculpt._PAINTING=False
raised=[tuple(v.co) for v in helper.data.vertices]
assert max(z-b[2] for (x,y,z),b in zip(raised,baseline) if abs(x)<8 and 4<=abs(y)<8)>.1
assert all(abs(z-b[2])<1e-6 for (x,y,z),b in zip(raised,baseline) if abs(y)>17)
assert tuple(tuple(v.co) for v in terrain.data.vertices)==((-80.,-80.,0.),(80.,-80.,0.),(80.,80.,0.),(-80.,80.,0.))
preview.close();assert helper.data==original
assert [tuple(v.co) for v in original.vertices]==baseline
core_terrain.rebuild(scene,True)
tree=BVHTree.FromPolygons([v.co for v in helper.data.vertices],[list(f.vertices) for f in helper.data.polygons])
errors=[]
for p in raised:
    if abs(p[0])>15 or not 4.1<abs(p[1])<15:continue
    hit=tree.ray_cast(Vector((p[0],p[1],100)),Vector((0,0,-1)))[0]
    if hit is not None:errors.append(abs(hit.z-p[2]))
assert errors and max(errors)<.035,max(errors,default=-1)
assert __import__('json').loads(terrain['roadlab_core_terrain_report'])['maximum_seam_error']<1e-4
print('ROAD_GRADE_PREVIEW_PASS',len(preview.bindings),max(errors),flush=True)
# A tight brush near the pavement edge used to extrapolate its slope into a pit.
road['roadlab_sculpt_field']='';road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
preview=RoadGradePreview(scene,road)
for _ in range(12):road_sculpt.apply_stamp(bpy.context,road,(0,3.7),'RAISE',5,5,.1,preview=True,grade_preview=preview)
assert min(v.co.z for v in helper.data.vertices)>-1e-6, 'Live grading excavated terrain'
preview.close();core_terrain.rebuild(scene,True)
assert min(v.co.z for v in helper.data.vertices)>-1e-6, 'Final grading excavated terrain'
# Restoring the road field and rebuilding restores the unedited surface.
road['roadlab_sculpt_field']='';road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
assert max(v.co.z for v in helper.data.vertices)<.021
print('EDGE_BRUSH_NO_PIT_PASS',flush=True)
from RoadLab import road_authoring
road_authoring.slice_contact(road,Vector((-20,0,.02)))
road_authoring.slice_contact(road,Vector((20,0,.02)),True)
road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
preview=RoadGradePreview(scene,road)
assert all(abs(preview.mesh.vertices[b[0]].co.x)>7.9 for b in preview.bindings), 'Bridge received terrain grading bindings'
before=[tuple(v.co) for v in preview.mesh.vertices]
road_sculpt.apply_stamp(bpy.context,road,(0,3.7),'RAISE',5,5,.1,preview=True,grade_preview=preview)
assert [tuple(v.co) for v in preview.mesh.vertices]==before, 'Bridge sculpt moved the ground'
preview.close()
print('BRIDGE_CONTACT_EXCLUSION_PASS',flush=True)
# Height/bank sessions do not compile roads, terrain or markings per sample.
road['roadlab_bridge_cuts']='[]';road['roadlab_sculpt_field']=''
road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
from RoadLab.road_stroke_preview import RoadStrokePreview
import time,statistics
original_road=road['roadlab_core_mesh'].data;original_outline=road['roadlab_core_outline'].data
paint_mesh=bpy.data.meshes.new('Manual preview paint');paint_mesh.from_pydata([(-1,-1,.025),(1,-1,.025),(1,1,.025),(-1,1,.025)],[],[(0,1,2,3)])
paint=bpy.data.objects.new('Manual preview paint',paint_mesh);scene.collection.objects.link(paint);paint.matrix_world=road.matrix_world.copy();road['roadlab_manual_marking_object']=paint
session=RoadStrokePreview(scene,road);timings=[]
old_road=road_core.rebuild;old_terrain=core_terrain.rebuild;old_marks=road_core.refresh_markings
road_core.rebuild=forbidden;core_terrain.rebuild=forbidden;road_core.refresh_markings=forbidden
try:
    for i in range(12):
        start=time.perf_counter();assert session.stamp((i*.1,0),'RAISE',8,2,.04);timings.append(time.perf_counter()-start)
    assert min(v.co.z for v in paint.data.vertices)>.1, 'Manual paint did not follow the live road'
    assert session.stamp((0,0),'LOWER',8,1,.04)
    assert session.stamp((0,0),'FLATTEN',8,1,.04,.1)
    assert session.stamp((0,0),'SMOOTH',8,1,.04)
    altered=road_sculpt.field.bank(dict(session.values),(0,0),(1,0),8,.08,session.base_height)
    session.values.clear();session.values.update(altered);session.update((0,0),8)
    assert road['roadlab_sculpt_field']=='', 'Preview serialized road field per sample'
    assert max(v.co.z for v in road['roadlab_core_mesh'].data.vertices)>.2
    assert max(v.co.z for v in helper.data.vertices)>.05
finally:
    road_core.rebuild=old_road;core_terrain.rebuild=old_terrain;road_core.refresh_markings=old_marks
values=dict(session.values);session.close(False)
assert road['roadlab_core_mesh'].data==original_road and road['roadlab_core_outline'].data==original_outline
assert road['roadlab_sculpt_field']==''
assert paint.data==paint_mesh, 'Cancel did not restore paint mesh'
session=RoadStrokePreview(scene,road);session.values.update(values);session.update((0,0),12);session.close(True)
assert road['roadlab_sculpt_field']
road_core.rebuild(road,True);core_terrain.rebuild(scene,True)
print('ROAD_STROKE_LOCAL_PASS',{'median_ms':round(statistics.median(timings)*1000,3),'max_ms':round(max(timings)*1000,3)},flush=True)
# Every toolbar brush owns a native hover callback before any modal brush starts.
from RoadLab import road_toolbar,brush_cursor
assert all(tool.draw_cursor is brush_cursor.draw_tool_cursor for tool in road_toolbar.tools)
print('NATIVE_HOVER_CALLBACK_PASS',flush=True)
