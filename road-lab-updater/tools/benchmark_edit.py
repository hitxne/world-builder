"""Measure committed edits in the tactile-crosswalk example, outside the profiler."""
import bpy,sys,time,json,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register()
from RoadLab import selected_points
started=time.perf_counter();bpy.ops.roadlab.load_example();load=time.perf_counter()-started
road=bpy.context.scene.wb_native.road;times=[]
for _ in range(3):
 started=time.perf_counter();road.data.splines[0].points[0].co.y+=.05;selected_points.notify(bpy.context,road);bpy.context.view_layer.update();times.append(time.perf_counter()-started)
print('ROADLAB_EDIT_BENCHMARK',json.dumps(dict(blender=bpy.app.version_string,threads=bpy.context.scene.render.threads,load_seconds=load,edit_seconds=times,median_edit_seconds=statistics.median(times))),flush=True)
