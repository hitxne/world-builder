"""Geometry Nodes input access for Blender 5.1 and the 5.2 RNA interface."""

def input_property(modifier, identifier):
    properties = getattr(modifier, 'properties', None)
    return getattr(properties.inputs, identifier, None) if properties is not None else None


def get_value(modifier, identifier, default=None):
    prop = input_property(modifier, identifier)
    if prop is not None:
        return getattr(prop, 'value', default)
    if getattr(modifier, 'properties', None) is not None:
        return default
    return modifier.get(identifier, default)


def set_value(modifier, identifier, value):
    prop = input_property(modifier, identifier)
    if prop is not None:
        prop.value = value
    elif getattr(modifier, 'properties', None) is not None:
        raise ValueError('Geometry Nodes input is unavailable: ' + identifier)
    else:
        modifier[identifier] = value


def draw_value(layout, modifier, identifier, label):
    prop = input_property(modifier, identifier)
    if prop is not None:
        layout.prop(prop, 'value', text=label)
    elif getattr(modifier, 'properties', None) is None:
        layout.prop(modifier, '["' + identifier + '"]', text=label)


def integer_operand(node, name):
    """5.1 keeps inactive typed sockets; 5.2 exposes only the active pair."""
    return next(s for s in node.inputs if s.name == name and s.type == 'INT')
