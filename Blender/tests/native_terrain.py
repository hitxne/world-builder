"""Run with Blender --background --python native_terrain.py.
Set WB_TT_LIBRARY to your original TT_NodeGroups.blend; no commercial data is bundled.
"""
import bpy,sys,os,json,tempfile
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import WB_TrackTools as addon
from WB_TrackTools import terrain_ui as ui,network_blender as nb,terrain_clearance as tc
addon.register();bpy.ops.wm.read_factory_settings(use_empty=True)
g={'version':3,'fixture':'network','units':'m','settings':{'sample_spacing':1,'curb_height':.1524,'sidewalk_width':2.2},'roads':[{'id':'test-road','alignment':{'kind':'polyline','points':[[0,0,1.5],[60,0,1.5]]},'width_left':[[0,3]],'width_right':[[0,3]],'crossfall':0,'lanes':[],'terrain_mode':'grade','curbs':False}],'connections':[],'accesses':[],'parking_lots':[],'terrain':{'enabled':True,'bounds':[-20,80,-30,30],'grid_spacing':1,'blend_distance':18,'base_height':0,'wave_amplitude':0,'tt_library':os.environ['WB_TT_LIBRARY'],'backend':'tracktools'},'validation':{'max_road_grade':.12,'max_terrain_slope':.6}}
ui.rebuild(bpy.context.scene,g)
def check():
    bpy.context.view_layer.update();obj=ui.terrain_object();e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
    try:
        m.calc_loop_triangles();v=[tuple(p.co) for p in m.vertices];t=[tuple(p.vertices) for p in m.loop_triangles];b=BVHTree.FromPolygons(v,t,all_triangles=True)
        hit=b.ray_cast(Vector((30,3.02,20)),Vector((0,0,-1)),100)[0];assert hit is not None and abs(hit.z-1.5)<.001,hit
        assert b.ray_cast(Vector((30,0,20)),Vector((0,0,-1)),100)[0] is None, 'Native cutter must remove ground under the road'
    finally:e.to_mesh_clear()
check();obj=ui.terrain_object();adj=ui.neighbors(obj);s=bpy.context.scene.wb_terrain;s.radius=8;s.strength=2
for mode in ('RAISE','LOWER','SMOOTH','FLATTEN'):
    s.mode=mode;ui.apply_stamp(obj,s,(30,6,0),.1,.3,adj);check()
ui.commit(bpy.context.scene,obj);before=[v.co.z for v in obj.data.vertices];ui.rebuild(bpy.context.scene,json.loads(bpy.context.scene.wb_graph));assert max(abs(z-v.co.z) for z,v in zip(before,ui.terrain_object().data.vertices))<2e-5;check()
with tempfile.TemporaryDirectory(prefix='wb-terrain-test-') as temp:
    path=str(Path(temp)/'checkpoint.blend');bpy.ops.wm.save_as_mainfile(filepath=path);bpy.ops.wm.open_mainfile(filepath=path);check()
print('WB_NATIVE_TERRAIN_PASSED',flush=True)
