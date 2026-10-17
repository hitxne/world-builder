"""Actual mesh preview, local edits, rollback and sparse-plane refinement."""
import bpy, sys, time, statistics
from pathlib import Path
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extension'))
import RoadLab
RoadLab.register()
from RoadLab import sculpt_preview, road_heightfield as field

def plane(size, divisions):
    mesh=bpy.data.meshes.new('Preview source')
    vertices=[(-size/2+size*x/divisions,-size/2+size*y/divisions,0.) for y in range(divisions+1) for x in range(divisions+1)]
    faces=[]
    for y in range(divisions):
        for x in range(divisions):
            a=y*(divisions+1)+x;faces.append((a,a+1,a+divisions+2,a+divisions+1))
    mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new('Preview terrain',mesh);bpy.context.scene.collection.objects.link(obj)
    return obj

obj=plane(200,100);source=obj.data;original=[tuple(v.co) for v in source.vertices]
values={};preview=sculpt_preview.HeightPreview(obj,obj,values)
times=[]
for i in range(100):
    center=(i%5,0.);start=time.perf_counter()
    values.update(field.stamp_patch(values,center,8.,2.,.04,'RAISE',lambda x,y:0.))
    preview.update(center,8.)
    times.append(time.perf_counter()-start)
assert max(v.co.z for v in obj.data.vertices)>.1
assert tuple(obj.data.vertices[-1].co)==original[-1], 'Distant terrain changed'
assert [tuple(v.co) for v in source.vertices]==original, 'Preview altered original mesh'
assert preview.changed_vertices<200, preview.changed_vertices
hit=preview.ray_cast(Vector((0,0,100)),Vector((0,0,-1)))
assert hit is not None and abs(hit.z-preview.height(0,0))<.001
preview.close();assert obj.data==source
assert [tuple(v.co) for v in obj.data.vertices]==original
print('LOCAL_PREVIEW_PASS',{'vertices':len(source.vertices),'median_ms':round(statistics.median(times)*1000,3),'max_ms':round(max(times)*1000,3)},flush=True)

# A four-vertex plane must show an interior stroke before final compilation.
obj=plane(1000,1);values={};preview=sculpt_preview.HeightPreview(obj,obj,values)
start=time.perf_counter();preview.ensure_detail((0,0),8.)
elapsed=time.perf_counter()-start
values.update(field.stamp_patch(values,(0,0),8.,2.,.1,'RAISE',lambda x,y:0.))
preview.update((0,0),8.)
assert max(v.co.z for v in obj.data.vertices)>.05, 'Sparse plane has no visible interior preview'
assert len(obj.data.vertices)<=sculpt_preview.PREVIEW_VERTEX_BUDGET
print('SPARSE_PREVIEW_PASS',{'vertices':len(obj.data.vertices),'prepare_ms':round(elapsed*1000,3)},flush=True)
preview.close()

# Road-contact pins must remain fixed even under repeated sculpting.
obj=plane(20,20);values={};weights=[0. if abs(v.co.x)<1. else 1. for v in obj.data.vertices]
preview=sculpt_preview.HeightPreview(obj,obj,values,weights)
for _ in range(10):
    values.update(field.stamp_patch(values,(0,0),8.,2.,.1,'RAISE',lambda x,y:0.));preview.update((0,0),8.)
assert all(abs(v.co.z)<1e-7 for v in obj.data.vertices if abs(v.co.x)<1e-7), 'Road-contact seam moved'
assert max(v.co.z for v in obj.data.vertices)>.1
preview.close()
print('PREVIEW_SEAM_PASS',flush=True)

# Compile a real road/terrain fixture, preview without recompilation, then commit.
from RoadLab import road_core, core_terrain, terrain_sculpt
from RoadLab.native_extension import set_input
scene=bpy.context.scene
curve=bpy.data.curves.new('Preview road','CURVE');curve.dimensions='3D'
spline=curve.splines.new('POLY');spline.points.add(1)
for point,co in zip(spline.points,[(-20,0,.02,1),(20,0,.02,1)]):point.co=co
road=bpy.data.objects.new('Preview road',curve);scene.collection.objects.link(road)
scene.wb_native.road=road;road_core.attach(road)
set_input(road_core.modifier(road),'road width',8);road_core.rebuild(road,True)
terrain=plane(80,1);scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True
core_terrain.rebuild(scene,True)
helper=terrain['roadlab_core_terrain_mesh'];original=helper.data
state=core_terrain._STATE[terrain.as_pointer()];values={}
preview=sculpt_preview.HeightPreview(terrain,helper,values,state['sculpt_weights'])
terrain_sculpt._ACTIVE=True
try:
    road_core._pending[scene.as_pointer()]=(scene,{road})
    assert road_core.flush_pending(force=True) is False, 'Scheduler rebuilt during terrain preview'
    preview.ensure_detail((0,16),8)
    for _ in range(10):
        values.update(field.stamp_patch(values,(0,16),8,2,.04,'RAISE',lambda x,y:0))
        preview.update((0,16),8);bpy.context.view_layer.update()
    assert helper.data!=original and original==preview.original
    expected=preview.height(0,16)
    assert expected>.5
    seam=[v for v in helper.data.vertices if abs(abs(v.co.y)-4)<1e-5 and abs(v.co.x)<19]
    assert seam and all(abs(v.co.z-.02)<1e-5 for v in seam), 'Preview moved the road seam'
finally:
    preview.close();terrain_sculpt._ACTIVE=False;road_core._pending.clear()
terrain['roadlab_terrain_field']=field.encode(values)
terrain_sculpt.mark(terrain,(0,16),8)
core_terrain.rebuild(scene,True)
mesh=helper.data;mesh.calc_loop_triangles()
from mathutils.bvhtree import BVHTree
tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
hit=tree.ray_cast(Vector((0,16,100)),Vector((0,0,-1)))[0]
assert hit and abs(hit.z-expected)<.05, ('Commit differs from preview',hit,expected)
assert not terrain.get('roadlab_core_terrain_error')
assert max(abs(v.co.z-.02) for v in mesh.vertices if abs(abs(v.co.y)-4)<1e-5 and abs(v.co.x)<19)<1e-5
print('ROAD_TERRAIN_PREVIEW_COMMIT_PASS',flush=True)

# Exercise the operator's stroke and cancel path, including field restoration.
from types import SimpleNamespace
saved_field=terrain['roadlab_terrain_field'];saved_mesh=helper.data
values=field.decode(saved_field)
preview=sculpt_preview.HeightPreview(terrain,helper,values,core_terrain._STATE[terrain.as_pointer()]['sculpt_weights'])
preview.ensure_detail((0,16),8)
session=SimpleNamespace(obj=terrain,settings=SimpleNamespace(radius=8.,strength=2.),
    values=values,preview=preview,center=Vector((0,16,expected)),tool_mode='RAISE',
    target=expected,base_height=lambda x,y:0.,stroke_box=None,timer=None,handle=None,
    original=saved_field,original_enabled=True,
    area=SimpleNamespace(header_text_set=lambda text:None,tag_redraw=lambda:None))
terrain_sculpt._ACTIVE=True
assert terrain_sculpt.ROADLAB_OT_terrain_sculpt.stamp(session,.04)
assert terrain['roadlab_terrain_field']==saved_field, 'Stroke serialized the whole field before commit'
assert terrain_sculpt.ROADLAB_OT_terrain_sculpt.finish(session,bpy.context,True)=={'CANCELLED'}
assert not terrain_sculpt.is_active() and helper.data==saved_mesh
assert terrain['roadlab_terrain_field']==saved_field
print('SCULPT_SESSION_CANCEL_PASS',flush=True)

# Repeating the same session through apply persists values and frees the preview.
values=field.decode(saved_field)
preview=sculpt_preview.HeightPreview(terrain,helper,values,core_terrain._STATE[terrain.as_pointer()]['sculpt_weights'])
preview.ensure_detail((0,16),8)
session.values=values;session.preview=preview;session.stroke_box=None;preview_name=preview.mesh.name
terrain_sculpt._ACTIVE=True
assert terrain_sculpt.ROADLAB_OT_terrain_sculpt.stamp(session,.04)
assert terrain_sculpt.ROADLAB_OT_terrain_sculpt.finish(session,bpy.context)=={'FINISHED'}
assert terrain['roadlab_terrain_field']!=saved_field and not terrain_sculpt.is_active()
try:
    preview.mesh.name
except ReferenceError:
    pass
else:
    raise AssertionError('Applied session leaked its temporary mesh')
print('SCULPT_SESSION_APPLY_PASS',flush=True)
