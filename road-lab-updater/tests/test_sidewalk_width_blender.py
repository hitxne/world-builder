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
