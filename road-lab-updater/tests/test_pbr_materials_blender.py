import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extension'))
import bpy,RoadLab
from RoadLab import pbr_materials
for name in pbr_materials.SPECS:
 m=RoadLab.material(name);m.use_fake_user=True
 assert m.get('roadlab_pbr_version')==1,name
 assert len([n for n in m.node_tree.nodes if n.type=='TEX_IMAGE'])==3
 assert all(n.image.packed_file for n in m.node_tree.nodes if n.type=='TEX_IMAGE')
 assert all(m.node_tree.nodes.get('Principled BSDF').inputs[k].is_linked for k in ['Base Color','Normal','Roughness'])
 assert RoadLab.material(name)==m
m=RoadLab.material('white');assert not m.get('roadlab_pbr_version')
print('PBR tests passed')
# Preserve artist edits and share one image datablock between concrete variants.
custom=bpy.data.materials.new('WB_custom_pbr_test');custom.use_nodes=True
custom.node_tree.nodes.new('ShaderNodeTexNoise')
assert pbr_materials.ensure(custom,'grass')==custom
assert not custom.get('roadlab_pbr_version')
images=[n.image for n in RoadLab.material('sidewalk').node_tree.nodes if n.type=='TEX_IMAGE']
assert images==[n.image for n in RoadLab.material('concrete').node_tree.nodes if n.type=='TEX_IMAGE']
# Default migration and clean register/unregister must also work.
RoadLab.register();pbr_materials.upgrade_defaults();RoadLab.unregister()
bpy.ops.wm.save_as_mainfile(filepath='/tmp/roadlab-pbr-test.blend')
bpy.ops.wm.open_mainfile(filepath='/tmp/roadlab-pbr-test.blend')
for kind in pbr_materials.SPECS:
 assert all(n.image.packed_file for n in bpy.data.materials['WB_'+kind].node_tree.nodes if n.type=='TEX_IMAGE')
print('PBR migration, sharing and file round-trip passed')
