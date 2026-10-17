"""Lane-window drafts preview their real pavement alignment without committing."""
import bpy,sys,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,lane_editor as e,point_settings as ps
from RoadLab.native_extension import set_input
scene=bpy.context.scene;curve=bpy.data.curves.new('Alignment preview','CURVE');curve.dimensions='3D'
for path in [[(-80,0,.02),(0,0,.02),(80,0,.02)],[(0,-80,.02),(0,0,.02),(0,80,.02)]]:
 s=curve.splines.new('POLY');s.points.add(2)
 for p,co in zip(s.points,path):p.co=(*co,1)
road=bpy.data.objects.new('Alignment preview',curve);scene.collection.objects.link(road);scene.wb_native.road=road;road_core.attach(road);set_input(road_core.modifier(road),'road width',11.5);road_core.rebuild(road,True)
lane=lambda:[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
road['roadlab_lanes']=json.dumps([dict(endpoints=[a,b],incoming=lane(),outgoing=lane(),median=0,spacing=18) for _,_,a,b in e.segments(road)]);e.rebuild(road,scene,True)
for o in bpy.context.selected_objects:o.select_set(False)
road.select_set(True);bpy.context.view_layer.objects.active=road
for p in ps.points(road):p.select=abs(p.co.x)<1e-5 and abs(p.co.y)<1e-5
bpy.ops.object.mode_set(mode='EDIT')
original=road['roadlab_lanes'];mesh=road['roadlab_core_mesh'].data;objects=set(bpy.data.objects)
context=SimpleNamespace(scene=scene,mode=bpy.context.mode,edit_object=road,active_object=road,window_manager=SimpleNamespace(invoke_props_dialog=lambda *a,**k:{'RUNNING_MODAL'}),screen=None)
op=SimpleNamespace(approach='0',preview_status='');e.ROADLAB_OT_lane_window.invoke(op,context,None)
choices=json.loads(op.choices_json);lookup={r['id']:r['co'] for r in ps.records(road)}
op.approach=str(next(i for i,(a,b) in enumerate(choices) if lookup[a][0]>0));e.approach_changed(op,context)
item=scene.roadlab_lane_draft.incoming.add();item.width=3.5;item.movement='THROUGH'
e.tick_lane_preview();assert e._lane_preview and e._lane_preview.get('geometry_draft'),op.preview_status
draft=e._lane_preview['geometry_draft']
assert e._lane_preview['proxy']['roadlab_core_mesh']==draft.helper
assert max(v.co.y for v in draft.helper.data.vertices if v.co.x>40)>7.4
assert max(v.co.y for v in mesh.vertices if v.co.x>40)<5.8
assert road['roadlab_lanes']==original and road['roadlab_core_mesh'].data==mesh
assert 'Live preview' in op.preview_status,op.preview_status
e.ROADLAB_OT_lane_window.cancel(op,context)
assert set(bpy.data.objects)==objects and not any(o.get('roadlab_temporary_preview') for o in bpy.data.objects)
assert road['roadlab_lanes']==original and road['roadlab_core_mesh'].data==mesh
bpy.ops.object.mode_set(mode='OBJECT')
print('LANE_ALIGNMENT_PREVIEW_PASS',flush=True)
