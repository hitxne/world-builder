"""Saved schema-18 graphs upgrade in place without losing layer inputs."""
import bpy,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import RoadLab
RoadLab.register();bpy.ops.roadlab.load_example()
from RoadLab import native_extrusion,native_layers
from RoadLab.native_contacts import input_value
road=bpy.context.scene.wb_native.road
model=native_layers.model_for(road)
sidewalk=next(l.object for l in model.wb_layers if l.kind=='sidewalk')
g=native_extrusion.extrusion_group()
identifiers={s.name:s.identifier for s in g.interface.items_tree if s.item_type=='SOCKET'}
mods=[m for m in sidewalk.modifiers if m.type=='NODES']
settings=[{name:(lambda v:v.name if hasattr(v,'name') else v)(input_value(m,name)) for name in ('Evaluation stage','Slab length','Slab width','Material','Layer prefix')} for m in mods]
# Model a stale saved graph, with a sentinel that only rebuilding can remove.
g['wb_schema']=18;g.nodes.new('ShaderNodeValue').name='OLD_GRAPH_SENTINEL'
with tempfile.TemporaryDirectory() as tmp:
 path=str(Path(tmp)/'saved-sidewalk.blend');bpy.ops.wm.save_as_mainfile(filepath=path)
 bpy.ops.wm.open_mainfile(filepath=path)
 g=bpy.data.node_groups['WB_EXTENSION_BORDER_EXTRUSION']
 assert g.get('wb_schema')==19,'Older graph was incorrectly accepted as current'
 assert 'OLD_GRAPH_SENTINEL' not in g.nodes
 assert {s.name:s.identifier for s in g.interface.items_tree if s.item_type=='SOCKET'}==identifiers
 sidewalk=next(l.object for l in native_layers.model_for(bpy.context.scene.wb_native.road).wb_layers if l.kind=='sidewalk')
 mods=[m for m in sidewalk.modifiers if m.type=='NODES']
 for m,old in zip(mods,settings):
  assert m.node_group==g
  for name,value in old.items():
   now=input_value(m,name)
   assert (now.name if hasattr(now,'name') else now)==value,(name,now,value)
 count=len(g.nodes);assert native_extrusion.extrusion_group()==g and len(g.nodes)==count
print('SIDEWALK_SAVED_UPGRADE_PASS',flush=True)
