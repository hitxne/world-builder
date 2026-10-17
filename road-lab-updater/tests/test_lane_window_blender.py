import bpy,sys,json
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import lane_editor as e,point_settings as ps
scene=bpy.context.scene
curve=bpy.data.curves.new('Selection regression','CURVE');curve.dimensions='3D'
for end in [(30,0,0),(-30,0,0),(0,30,0),(0,-30,0)]:
 s=curve.splines.new('POLY');s.points.add(1);s.points[0].co=(*end,1);s.points[1].co=(0,0,0,1)
road=bpy.data.objects.new('Selection regression',curve);scene.collection.objects.link(road);road['roadlab_new_core']=True
bpy.ops.object.select_all(action='DESELECT');road.select_set(True);bpy.context.view_layer.objects.active=road;scene.wb_native.road=road
from RoadLab import road_core;road_core.attach(road);ps.sync(road);bpy.ops.object.mode_set(mode='EDIT')
checks=[]
def select(indices):
 for i,p in enumerate(ps.points(road)):p.select=i in indices

def context():
 return SimpleNamespace(scene=scene,mode=bpy.context.mode,edit_object=road,active_object=road,window_manager=SimpleNamespace(invoke_props_dialog=lambda op,**kw: checks.append((op.has_selection,kw['confirm_text'])) or {'RUNNING_MODAL'}))
def window():
 op=SimpleNamespace(has_selection=False,selection_hint='',choices_json='[]',is_junction=False,junction_label='',approach='0')
 assert e.ROADLAB_OT_lane_window.invoke(op,context(),None)=={'RUNNING_MODAL'}
 return op
select({1});op=window();assert op.has_selection and op.is_junction and len(json.loads(op.choices_json))==4
select({1,3,5,7});op=window();assert op.has_selection and op.is_junction
select({0,1});op=window();assert op.has_selection and not op.is_junction
select(set());op=window();assert not op.has_selection and checks[-1][1]=='Close'
select({0});op=window();assert op.has_selection and not op.is_junction
select({0,2,4});op=window();assert not op.has_selection
# A selected junction survives toolbar opening: no viewport selection is invoked.
select({1});before=ps.selected(bpy.context,road)
original=bpy.ops.roadlab.lane_window
# Test the actual operator invocation path through a window capture; no headless UI needed.
class Ops:
 def __call__(self,*args,**kwargs):
  assert ps.selected(bpy.context,road)==before
  window();return {'RUNNING_MODAL'}
bpy.ops.roadlab.lane_window=Ops()
try:
 result=e.ROADLAB_OT_lane_pick.invoke(SimpleNamespace(report=lambda *a:None),bpy.context,SimpleNamespace(shift=False,mouse_region_x=0,mouse_region_y=0))
 assert result=={'FINISHED'} and ps.selected(bpy.context,road)==before
finally:bpy.ops.roadlab.lane_window=original
# Active edited road wins over a stale scene assignment.
scene.wb_native.road=None;select({1});op=window();assert op.has_selection and scene.wb_native.road==road
# Direction labels follow actual world-space arms, including rotated roads.
from mathutils import Vector
geometry=e.approach_geometry(road,json.loads(op.choices_json))
assert {name for name,hint in e.approach_labels(geometry)}=={'North road','East road','South road','West road'}
road.rotation_euler.z=0.78539816339;bpy.context.view_layer.update()
labels=e.approach_labels(e.approach_geometry(road,json.loads(op.choices_json)))
assert {name for name,hint in labels}=={'Northeast road','Northwest road','Southeast road','Southwest road'}
# Two arms in the same compass sector remain distinguishable.
labels=e.approach_labels([(Vector((30,1,0)),Vector((0,0,0))),(Vector((30,5,0)),Vector((0,0,0)))])
assert labels[0][0]!=labels[1][0]
# Guides are transient; opening/closing does not alter source selection or geometry.
before=ps.selected(bpy.context,road)
e.show_approach_preview(op,road);assert e._approach_preview is not None
e.clear_approach_preview();assert e._approach_preview is None and ps.selected(bpy.context,road)==before
# Switching arms retains edits without committing until Apply.
road.rotation_euler.z=0;bpy.context.view_layer.update()
select({1});op=window();op.active_approach='0';op.drafts_json='{}'
d=scene.roadlab_lane_draft;d.road_width=11.5;d.incoming[0].movement='LEFT';d.incoming.add().movement='THROUGH'
op.approach='1';e.approach_changed(op,bpy.context);d.road_width=8.5;d.spacing=23
op.approach='0';e.approach_changed(op,bpy.context)
assert len(d.incoming)==2 and d.incoming[0].movement=='LEFT' and d.road_width==11.5
assert not e.state(road)
batch=list(e.save_active_approach(op,bpy.context).values())
assert bpy.ops.roadlab.lane_apply(batch_json=json.dumps(batch),expand=True)=={'FINISHED'}
assert len(e.state(road))==2
assert {c['spacing'] for c in e.state(road)}=={18,23}
# Invalid edits in a later arm must not partly overwrite earlier valid arms.
before=road['roadlab_lanes'];saved_widths=[x.get('width') for x in ps.records(road)]
bad=json.loads(json.dumps(batch));bad[1]['incoming']=[];bad[1]['outgoing']=[]
try:bpy.ops.roadlab.lane_apply(batch_json=json.dumps(bad))
except RuntimeError:pass
assert road['roadlab_lanes']==before and [x.get('width') for x in ps.records(road)]==saved_widths
# Width expansion still requires approval; all draft arms are applied together.
narrow=json.loads(json.dumps(batch));narrow[0]['road_width']=1
try:bpy.ops.roadlab.lane_apply(batch_json=json.dumps(narrow))
except RuntimeError:pass
assert road['roadlab_lanes']==before
assert bpy.ops.roadlab.lane_apply(batch_json=json.dumps(narrow),expand=True)=={'FINISHED'}
# Apply is a property action inside the dialog; it does not run its closing execute.
bpy.ops.roadlab.lane_window('EXEC_DEFAULT')
persistent=bpy.context.window_manager.operator_properties_last('roadlab.lane_window')
persistent.has_selection=True;persistent.is_junction=True;persistent.choices_json=op.choices_json
persistent.active_approach='0';persistent.drafts_json=op.drafts_json
persistent.apply_status='';persistent.expansion_text='[]'
d.page='MARKINGS';d.show_arrows=True;d.spacing=27
e.show_approach_preview(persistent,road)
persistent.apply_action=True
assert persistent.apply_status=='Applied. Further edits need Apply.' and not persistent.apply_action
assert d.page=='MARKINGS' and d.show_arrows and persistent.active_approach=='0' and e._approach_preview is not None
assert any(c['spacing']==27 for c in e.state(road))
# Expansion and its cancellation keep the same editor and pending edits.
d.road_width=1;persistent.apply_action=True
assert json.loads(persistent.expansion_text)
before=road['roadlab_lanes'];persistent.keep_width_action=True
assert road['roadlab_lanes']==before and persistent.expansion_text=='[]' and d.road_width==1
persistent.apply_action=True
# A changed width request must be reviewed again before expansion.
d.road_width=2;persistent.expand_action=True
assert road['roadlab_lanes']==before and json.loads(persistent.expansion_text)
persistent.expand_action=True
assert persistent.apply_status=='Applied. Further edits need Apply.' and d.road_width>=8
# Invalid changes stay editable in place, and do not change saved lanes.
before=road['roadlab_lanes'];d.incoming.clear();d.outgoing.clear();persistent.apply_action=True
assert 'Add at least one lane' in persistent.apply_status and road['roadlab_lanes']==before
# Done only closes: unapplied changes do not get saved implicitly.
assert e.ROADLAB_OT_lane_window.execute(persistent,bpy.context)=={'FINISHED'}
assert road['roadlab_lanes']==before and e._approach_preview is None
restore=e.state(road)[0];e.set_draft(bpy.context,road,[restore['endpoints']])
# Draw each page and its expanded sections using the real RNA draft.
class Layout:
 def __init__(self):self.text=[];self.enabled=True
 def label(self,**kw):self.text.append(kw.get('text',''))
 def prop(self,*args,**kw):pass
 def prop_enum(self,*args,**kw):pass
 def template_list(self,*args,**kw):pass
 def separator(self):pass
 def row(self,**kw):return self
 def box(self):return self
 def operator(self,*args,**kw):return SimpleNamespace()
for page in ('LANES','MARKINGS','ROAD'):
 d.page=page
 for flag in ('show_incoming','show_outgoing','show_arrows','show_dividers','show_stops','show_size','show_lane_details','show_saved'):setattr(d,flag,True)
 for direction in ('incoming','outgoing'):
  d.travel=direction;layout=Layout();e.draw_lanes(layout,bpy.context,True);e.draw_lanes(layout,bpy.context,False)
assert e._approach_preview is None
bpy.ops.object.mode_set(mode='OBJECT')
print('LANE_WINDOW_GUIDANCE_PASS',json.dumps(checks),flush=True)
