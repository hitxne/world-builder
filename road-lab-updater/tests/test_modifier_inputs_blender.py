"""Real modifier values and UI bindings on both sides of the 5.2 API change."""
import bpy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extension'))
import RoadLab
RoadLab.register()
from RoadLab.modifier_inputs import get_value, set_value, draw_value, integer_operand
from RoadLab.native_extension import set_input, draw_input
from RoadLab.native_contacts import input_value

obj = bpy.context.active_object
group = bpy.data.node_groups.new('Input compatibility test', 'GeometryNodeTree')
mod = obj.modifiers.new('Input compatibility test', 'NODES')
mod.node_group = group
material = bpy.data.materials.new('Input material')
for name, kind, value in [('Width', 'NodeSocketFloat', 3.25),
                          ('Enabled', 'NodeSocketBool', True),
                          ('Count', 'NodeSocketInt', 4),
                          ('Object', 'NodeSocketObject', obj),
                          ('Material', 'NodeSocketMaterial', material)]:
    socket = group.interface.new_socket(name=name, in_out='INPUT', socket_type=kind)
    set_input(mod, name, value)
    assert input_value(mod, name) == value, (name, input_value(mod, name))
    assert get_value(mod, socket.identifier) == value
    class Layout:
        def prop(self, owner, path, **kwargs):
            resolved = owner.path_resolve(path)
            assert resolved == value, (name, path, resolved)
    draw_input(Layout(), mod, name, name)
    if kind == 'NodeSocketBool':
        set_input(mod, name, False)
        assert input_value(mod, name) is False
    if kind in ('NodeSocketObject', 'NodeSocketMaterial'):
        set_input(mod, name, None)
        assert input_value(mod, name) is None
node = group.nodes.new('FunctionNodeCompare')
node.data_type = 'INT'
integer_operand(node, 'A').default_value = 3
integer_operand(node, 'B').default_value = 4
assert integer_operand(node, 'B').default_value == 4
print('MODIFIER_INPUTS_PASS', bpy.app.version_string, flush=True)
