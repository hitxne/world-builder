"""Sidewalk width drafts isolate source data, carry the stack, cancel and commit."""
import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,native_layers
from RoadLab.native_extrusion import add_extrusion
from RoadLab.native_extension import set_input
from RoadLab.sidewalk_width import WidthDraft,_SESSIONS
scene=bpy.context.scene;data=bpy.data.curves.new('Width draft road','CURVE');data.dimensions='3D'
s=data.splines.new('POLY');s.points.add(2)
for p,co in zip(s.points,[(-30,0,.02,1),(0,0,.02,1),(0,30,.02,1)]):p.co=co
road=bpy.data.objects.new('Width draft road',data);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road)
add_extrusion(scene,road,'curb');sidewalk,_=add_extrusion(scene,road,'sidewalk');grass,_=add_extrusion(scene,road,'grass')
model=native_layers.model_for(road);layer=next(l for l in model.wb_layers if l.object==sidewalk);following=next(l for l in model.wb_layers if l.object==grass)
base=native_layers.prefix(layer);after=native_layers.prefix(following)
bpy.context.view_layer.update();source_widths=native_layers.read(model,base+'width');source_stack=native_layers.read(model,after+'stack');objects=set(bpy.data.objects);groups=set(bpy.data.node_groups);materials=set(bpy.data.materials)
draft=WidthDraft(bpy.context,layer.uid);draft.update(6);bpy.context.view_layer.update()
assert native_layers.read(model,base+'width')==source_widths
assert native_layers.read(model,after+'stack')==source_stack
assert native_layers.read(draft.draft,base+'width')==[6.]*3
assert all(abs(b-a-(6-source_widths[0]))<1e-5 for a,b in zip(source_stack,native_layers.read(draft.draft,after+'stack')))
assert sidewalk.hide_get() and grass.hide_get()
preview=next(obj for original,obj in draft.copies if original.uid==layer.uid)
e=preview.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=e.to_mesh();assert len(mesh.polygons)>0
assert max(v.co.x for v in mesh.vertices)>7,e.name
e.to_mesh_clear();draft.close();bpy.context.view_layer.update()
assert not sidewalk.hide_get() and not grass.hide_get()
assert native_layers.read(model,base+'width')==source_widths
assert set(bpy.data.objects)==objects and set(bpy.data.node_groups)==groups and set(bpy.data.materials)==materials
assert not _SESSIONS
# Edit-mode draft affects selected points only; acceptance keeps other widths.
for obj in bpy.context.selected_objects:obj.select_set(False)
road.select_set(True);bpy.context.view_layer.objects.active=road
for i,p in enumerate(s.points):p.select=i==1
bpy.ops.object.mode_set(mode='EDIT')
draft=WidthDraft(bpy.context,layer.uid);assert draft.indices==[1]
draft.update(5);assert native_layers.read(model,base+'width')==source_widths
draft.accept();assert native_layers.read(model,base+'width')==[source_widths[0],5.,source_widths[2]]
assert set(bpy.data.objects)==objects and not _SESSIONS
bpy.ops.object.mode_set(mode='OBJECT')
# All-point acceptance builds the real panelled geometry, not the draft band.
draft=WidthDraft(bpy.context,layer.uid);draft.update(6);draft.accept();bpy.context.view_layer.update()
assert native_layers.read(model,base+'width')==[6.]*3
from RoadLab.native_contacts import input_value
mod=next(m for m in sidewalk.modifiers if m.type=='NODES');assert input_value(mod,'Sidewalk panels') is True
print('SIDEWALK_WIDTH_DRAFT_PASS',flush=True)
# Point profiles expose the absolute inner-edge distance from asphalt, while
# preserving the layer stack and all unselected points.
widths=native_layers.read(model,base+'width');gaps=native_layers.read(model,base+'offset');stack=native_layers.read(model,base+'stack');following_stack=native_layers.read(model,after+'stack')
for i,p in enumerate(road.data.splines[0].points):p.select=i==1
bpy.ops.object.mode_set(mode='EDIT')
draft=WidthDraft(bpy.context,layer.uid);assert draft.indices==[1] and draft.selected_only
draft.update(width=4.5,offset=1.4)
assert native_layers.read(model,base+'width')==widths and native_layers.read(model,base+'offset')==gaps
preview_gaps=native_layers.read(draft.draft,base+'offset');preview_stack=native_layers.read(draft.draft,base+'stack')
assert all(abs(preview_stack[i]+preview_gaps[i]-(1.4 if i==1 else stack[i]+gaps[i]))<1e-5 for i in range(3))
assert native_layers.read(draft.draft,base+'width')==[widths[0],4.5,widths[2]]
assert all(abs(a-b)<1e-5 for i,(a,b) in enumerate(zip(following_stack,native_layers.read(draft.draft,after+'stack'))) if i!=1)
draft.close();assert native_layers.read(model,base+'offset')==gaps and not _SESSIONS
assert set(bpy.data.objects)==objects and set(bpy.data.node_groups)==groups and set(bpy.data.materials)==materials
# Accept both fields at one selected point, then move that point.
draft=WidthDraft(bpy.context,layer.uid);draft.update(width=4.5,offset=1.4);draft.accept()
assert native_layers.read(model,base+'width')==[widths[0],4.5,widths[2]]
actual_gaps=native_layers.read(model,base+'offset');actual_stack=native_layers.read(model,base+'stack')
assert abs(actual_stack[1]+actual_gaps[1]-1.4)<1e-5
assert all(abs(actual_gaps[i]-gaps[i])<1e-5 for i in (0,2))
bpy.ops.object.mode_set(mode='OBJECT');road.data.splines[0].points[1].co.x=1.;native_layers.sync_model(model)
assert abs(native_layers.read(model,base+'offset')[1]-actual_gaps[1])<1e-5
assert native_layers.read(model,base+'width')[1]==4.5
# Changing only offset on a mixed-width selection must not unify its widths.
for p in road.data.splines[0].points:p.select=True
bpy.ops.object.mode_set(mode='EDIT');mixed_widths=native_layers.read(model,base+'width')
draft=WidthDraft(bpy.context,layer.uid);draft.update(offset=2.);draft.accept()
assert native_layers.read(model,base+'width')==mixed_widths
assert all(abs(a+b-2.)<1e-5 for a,b in zip(native_layers.read(model,base+'stack'),native_layers.read(model,base+'offset')))
# Changing only width likewise preserves independently edited offsets.
native_layers.write(model,base+'offset',[0.,1.,2.]);native_layers.refresh_stack(model)
before=native_layers.read(model,base+'offset');draft=WidthDraft(bpy.context,layer.uid);draft.update(width=3.1);draft.accept()
assert native_layers.read(model,base+'offset')==before
# Empty Edit-mode selection must never silently become all-point editing.
bpy.ops.curve.select_all(action='DESELECT')
road.update_from_editmode()
try:WidthDraft(bpy.context,layer.uid)
except ValueError:pass
else:raise AssertionError('Empty selection changed all sidewalk points')
bpy.ops.object.mode_set(mode='OBJECT')
# Direct operator execution supports offset-only edits without changing width.
old_widths=native_layers.read(model,base+'width');bpy.ops.roadlab.sidewalk_width(uid=layer.uid,offset=2.5)
assert native_layers.read(model,base+'width')==old_widths
assert all(abs(a+b-2.5)<1e-5 for a,b in zip(native_layers.read(model,base+'stack'),native_layers.read(model,base+'offset')))
assert not _SESSIONS and set(bpy.data.objects)==objects
print('SIDEWALK_POINT_PROFILE_PASS',flush=True)
# Verify the evaluated footprint in an isolated scene, so another test road
# cannot clip it as a real intersecting street.
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
from mathutils import Vector
from mathutils.bvhtree import BVHTree
cv=bpy.data.curves.new('Straight point profile','CURVE');cv.dimensions='3D';line=cv.splines.new('POLY');line.points.add(4)
for p,x in zip(line.points,(-40,-20,0,20,40)):p.co=(x,0,.02,1)
rd=bpy.data.objects.new('Straight point profile',cv);scene.collection.objects.link(rd);scene.wb_native.road=rd;road_core.attach(rd);set_input(road_core.modifier(rd),'road width',8);road_core.rebuild(rd,True)
add_extrusion(scene,rd,'curb');sw,_=add_extrusion(scene,rd,'sidewalk');mdl=native_layers.model_for(rd);ly=next(l for l in mdl.wb_layers if l.object==sw)
for obj in bpy.context.selected_objects:obj.select_set(False)
rd.select_set(True);bpy.context.view_layer.objects.active=rd
for i,p in enumerate(rd.data.splines[0].points):p.select=i==2
bpy.ops.object.mode_set(mode='EDIT');draft=WidthDraft(bpy.context,ly.uid);draft.update(width=5.,offset=1.5)
preview=next(obj for original,obj in draft.copies if original.uid==ly.uid)
def surface(obj):
 bpy.context.view_layer.update();ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
 try:return BVHTree.FromPolygons([v.co for v in m.vertices],[tuple(p.vertices) for p in m.polygons])
 finally:ev.to_mesh_clear()
def hit(tree,x,y):return tree.ray_cast(Vector((x,y,20)),Vector((0,0,-1)))[0]
tree=surface(preview)
assert hit(tree,.071,9.8) is not None,'Selected point sidewalk did not widen'
assert hit(tree,.071,5.) is None,'Sidewalk inner edge ignored road-edge offset'
assert hit(tree,-30.071,9.8) is None and hit(tree,-30.071,5.) is not None,'Distant unselected sidewalk changed'
draft.accept();tree=surface(sw)
assert hit(tree,.071,9.8) is not None and hit(tree,.071,5.) is None,'Accepted sidewalk differs from preview'
bpy.ops.object.mode_set(mode='OBJECT');assert not _SESSIONS
print('SIDEWALK_POINT_FOOTPRINT_PASS',flush=True)
# Terrain contacts force-refresh on Apply, not while previewing the fields.
from RoadLab import core_terrain
mesh=bpy.data.meshes.new('Point profile terrain');mesh.from_pydata([(-60,-30,0),(60,-30,0),(60,30,0),(-60,30,0)],[],[(0,1,2,3)])
terrain=bpy.data.objects.new('Point profile terrain',mesh);scene.collection.objects.link(terrain);scene.wb_native.terrain=terrain;terrain.roadlab_core_terrain_enabled=True;core_terrain.rebuild(scene,True)
original_source=[tuple(p.co) for p in terrain.data.vertices];calls=[];real_rebuild=core_terrain.rebuild
bpy.ops.object.mode_set(mode='EDIT')
try:
 def counted(*args,**kwargs):calls.append(kwargs.get('force',args[1] if len(args)>1 else False));return real_rebuild(*args,**kwargs)
 core_terrain.rebuild=counted;draft=WidthDraft(bpy.context,ly.uid);draft.update(width=3.5);draft.update(offset=1.)
 assert not calls,'Draft edits recompiled terrain'
 draft.accept();assert sum(calls)==1,('Apply did not force-refresh terrain contacts exactly once',calls)
finally:core_terrain.rebuild=real_rebuild
assert [tuple(p.co) for p in terrain.data.vertices]==original_source
assert not _SESSIONS
bpy.ops.object.mode_set(mode='OBJECT')
print('SIDEWALK_PROFILE_TERRAIN_PASS',flush=True)
