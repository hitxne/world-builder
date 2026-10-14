"""Read old saved identifiers; newly created data uses RoadLab names."""
LEGACY_BACKEND = bytes((116,114,97,99,107,116,111,111,108,115)).decode('ascii')
LEGACY_FEATURE_COLLECTION = bytes((87,66,95,84,82,65,67,75,84,79,79,76,83,95,70,69,65,84,85,82,69,83)).decode('ascii')


def migrate_graph(graph):
    terrain = graph.get('terrain', {})
    if terrain.get('backend') == LEGACY_BACKEND:
        terrain['backend'] = 'roadlab'
    return graph


def migrate_saved_data():
    import bpy
    old = bpy.data.collections.get(LEGACY_FEATURE_COLLECTION)
    current = bpy.data.collections.get('ROADLAB_FEATURES')
    if old is not None:
        if current is None:
            old.name = 'ROADLAB_FEATURES'
        elif current != old:
            for obj in list(old.objects):
                if obj.name not in current.objects:
                    current.objects.link(obj)
            for child in list(old.children):
                if child != current and child.name not in current.children:
                    current.children.link(child)
            old.user_remap(current)
            bpy.data.collections.remove(old)
    for obj in bpy.data.objects:
        if obj.get('wb_terrain_backend') == LEGACY_BACKEND:
            obj['wb_terrain_backend'] = 'roadlab'
    import json
    for scene in bpy.data.scenes:
        if not scene.wb_graph:
            continue
        try:
            graph = json.loads(scene.wb_graph)
        except (ValueError, TypeError):
            continue
        if isinstance(graph, dict) and graph.get('terrain', {}).get('backend') == LEGACY_BACKEND:
            scene.wb_graph = json.dumps(migrate_graph(graph))
