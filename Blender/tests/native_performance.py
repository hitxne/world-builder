import bpy,sys,pathlib,time,json,statistics,os
root=pathlib.Path(__file__).parent;sys.path.insert(0,str(root if (root/'WB_TrackTools').exists() else root.parent));import WB_TrackTools as addon;addon.register()
from WB_TrackTools import native_extension as ext,native_extrusion as feats,native_layers as layers
bpy.ops.wm.open_mainfile(filepath=os.environ.get('WB_TRACKTOOLS_STARTUP',str(root/'tt_originals/TT_startup_scene_01(2).blend')))
for lib in bpy.data.libraries:lib.filepath=os.environ.get('WB_TRACKTOOLS_NODES',str(root/'tt_originals/TT_NodeGroups(3).blend'));lib.reload()
road=ext.native_roads(bpy.context.scene)[0];result={}
def timing(label):
 bpy.context.view_layer.update();times=[]
 for i in range(4):
  p=layers.points(road)[0];p.co.z+=.0001;road.data.update_tag();road.update_tag()
  start=time.perf_counter();bpy.context.view_layer.update();times.append(time.perf_counter()-start)
 result[label]={'median_seconds':statistics.median(times),'samples':times}
 print('BENCHMARK',label,result[label],flush=True)
timing('road_only')
feats.add_extrusion(bpy.context.scene,road,'curb');timing('curb')
feats.add_extrusion(bpy.context.scene,road,'sidewalk');timing('curb_sidewalk')
name=sys.argv[-1] if '--' in sys.argv else 'baseline'
(root/('native_performance_'+name+'.json')).write_text(json.dumps(result,indent=2));print('BENCHMARK_PASS',flush=True)
