"""Adding a branch must preserve existing lane profiles and usable paint."""
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import road_core,point_settings as ps,lane_editor as lanes
from RoadLab.native_extension import set_input

def make_road(name,paths):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D'
    for path in paths:
        spline=curve.splines.new('POLY');spline.points.add(len(path)-1)
        for point,co in zip(spline.points,path):point.co=(*co,1)
    obj=bpy.data.objects.new(name,curve);bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.wb_native.road=obj;road_core.attach(obj)
    set_input(road_core.modifier(obj),'road width',8);road_core.rebuild(obj,True)
    profile=lambda:[dict(width=3.5,movement='THROUGH',entry='CONTINUOUS')]
    configs=[dict(endpoints=[a,b],incoming=profile(),outgoing=profile(),median=0,spacing=18,control_incoming='NONE',control_outgoing='NONE') for _,_,a,b in lanes.segments(obj)]
    obj['roadlab_lanes']=json.dumps(configs);lanes.rebuild(obj,bpy.context.scene,True)
    return obj,configs

def paint(obj):return json.loads(obj['roadlab_generated_marking_catalog'])
def branch(obj,start,end):
    spline=obj.data.splines.new('POLY');spline.points.add(1)
    spline.points[0].co=(*start,1);spline.points[1].co=(*end,1)
    road_core.rebuild(obj,True)

# A bend becomes a Y junction. Old THROUGH arrows require review, not loss of lines.
obj,configs=make_road('Bend to branch',[[(-65,0,0),(0,0,0),(0,65,0)]])
assert paint(obj)
branch(obj,(0,0,0),(65,-40,0))
assert lanes.state(obj)==configs,'Adding a branch changed existing saved profiles'
assert len([m for m in paint(obj) if m['role'][0]=='center-yellow'])==2,'Branch erased center lines'
assert len([m for m in paint(obj) if m['role'][0]=='outer'])==4,'Branch erased edge lines'
assert not [m for m in paint(obj) if m['asset']=='arrow_through'],'Unavailable THROUGH arrows must not be painted'
assert json.loads(obj['roadlab_marking_warnings']),'Changed turn choices should be flagged'

# Subdivide the original street to create a branch vertex; both child edges inherit.
obj,configs=make_road('Subdivide and branch',[[(-70,150,0),(70,150,0)]])
old_ids=configs[0]['endpoints'];records=ps.records(obj);records[0]['width']=8;records[1]['width']=8;ps.save(obj,records)
# Add a real source point, keeping the two old endpoint identities by coordinate.
spline=obj.data.splines[0];spline.points.add(1)
for point,co in zip(spline.points,[(-70,150,0),(0,150,0),(70,150,0)]):point.co=(*co,1)
branch(obj,(0,150,0),(0,210,0))
configs_after=lanes.state(obj)
assert len(configs_after)==2,'Split lane assignment was not migrated'
valid={frozenset((a,b)) for _,_,a,b in lanes.segments(obj)}
assert all(frozenset(c['endpoints']) in valid for c in configs_after)
assert configs_after[0]['endpoints'][0]==old_ids[0] and configs_after[-1]['endpoints'][1]==old_ids[1]
assert all(c['incoming']==configs[0]['incoming'] and c['outgoing']==configs[0]['outgoing'] for c in configs_after)
assert len([m for m in paint(obj) if m['role'][0]=='center-yellow'])==2
assert not any('reselection' in w for w in json.loads(obj['roadlab_marking_warnings']))
# Repair a scene already affected by 0.18.6, whose new point IDs were consumed.
legacy=json.loads(json.dumps(configs));legacy[0]['control_incoming']='STOP';legacy[0]['control_outgoing']='SIGNAL'
obj['roadlab_lanes']=json.dumps(legacy);lanes.rebuild(obj,bpy.context.scene,True)
recovered=lanes.state(obj);assert len(recovered)==2
assert recovered[0]['control_outgoing']=='SIGNAL' and recovered[0]['control_incoming']=='NONE'
assert recovered[1]['control_incoming']=='STOP' and recovered[1]['control_outgoing']=='NONE'
configs_after=recovered
# Adding another branch does not reassign the new streets or duplicate old profiles.
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
bpy.ops.object.mode_set(mode='EDIT')
for point in ps.points(obj):point.select=False
obj.data.splines[0].points[1].select=True
assert bpy.ops.wb.add_road_branch(length=60,flip=True)=={'FINISHED'}
road_core.rebuild(obj,True);assert lanes.state(obj)==configs_after
bpy.ops.object.mode_set(mode='OBJECT')
assert len([m for m in paint(obj) if m['role'][0]=='center-yellow'])==2
print('BRANCH_PRESERVATION_PASS',flush=True)
