"""Independent parking footprints drive symmetric curb and sidewalk crossings.

Guides share the original boundary mesh, not the trimmed parking output. This
keeps edits live without a sidewalk -> parking -> sidewalk dependency cycle.
"""
import bpy
from .native_extension import set_input
_busy=False

def sync_scene(scene):
    global _busy
    if _busy or not hasattr(bpy.types.Object,'roadlab_surface'):return
    _busy=True
    try:
        from .surface_bounds import group
        from .crosswalk_ramps import layers
        sources=[o for o in scene.objects if o.get('roadlab_surface_bounds')]
        eligible={o for o in sources if o.roadlab_surface.kind=='PARKING' and o.roadlab_surface.entrances and o.roadlab_surface.road}
        # Deleted/reassigned/disabled lots must restore the previous sidewalk.
        for guide in list(scene.objects):
            if guide.get('roadlab_parking_guide') and guide.get('roadlab_parking_source') not in eligible:
                bpy.data.objects.remove(guide,do_unlink=True)
        wanted={}
        for obj in eligible:
            settings=obj.roadlab_surface;road=settings.road
            guide=obj.get('roadlab_entrance_guide')
            if guide is None or guide.get('roadlab_parking_source')!=obj:
                guide=bpy.data.objects.new('RoadLab Parking Entrance Footprint',obj.data);scene.collection.objects.link(guide)
                guide['roadlab_parking_guide']=True;guide['roadlab_parking_source']=obj;obj['roadlab_entrance_guide']=guide
                guide.hide_render=True;guide.hide_set(True);guide.hide_select=True
                constraint=guide.constraints.new('COPY_TRANSFORMS');constraint.target=obj
                mod=guide.modifiers.new('Independent entrance footprint','NODES');mod.node_group=group()
            else:
                if guide.data!=obj.data:guide.data=obj.data
                mod=guide.modifiers[0]
                current=group()
                if mod.node_group!=current:mod.node_group=current
            # No existing-surface input: the guide is strictly upstream of edges.
            terrain=settings.terrain;helper=terrain.get('roadlab_core_terrain_mesh') if terrain else None
            for name,value in [('Entrance guide only',True),('Entrance ramp length',settings.entrance_run),('Terrain detail',settings.detail),('Terrain',helper or terrain),('Road',road),('Follow terrain',settings.follow),('Surface height',settings.rise),('Corner radius',settings.radius)]:set_input(mod,name,value)
            wanted.setdefault(road,set()).add(guide)
        roads={o for o in scene.objects if o.type=='CURVE' and o.get('roadlab_new_core')}
        roads.update(wanted)
        for road in roads:
            collection=road.get('roadlab_parking_entrances');objects=wanted.get(road,set())
            if collection is None and objects:
                collection=bpy.data.collections.new('RoadLab Parking Entrances');road['roadlab_parking_entrances']=collection
            if collection:
                for obj in list(collection.objects):
                    if obj not in objects:collection.objects.unlink(obj)
                for obj in objects:
                    if obj.name not in collection.objects:collection.objects.link(obj)
            for layer in layers(road):
                for mod in layer.object.modifiers:
                    if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                        if any(s.name=='Parking entrances' for s in mod.node_group.interface.items_tree):set_input(mod,'Parking entrances',collection)
    finally:_busy=False

@bpy.app.handlers.persistent
def loaded(_):
    from .surface_bounds import group
    group()
    for scene in bpy.data.scenes:
        for obj in list(scene.objects):
            if obj.get('roadlab_surface_bounds'):
                for mod in obj.modifiers:
                    if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('RoadLab Surface Bounds'):mod.node_group=group()
        sync_scene(scene)

@bpy.app.handlers.persistent
def changed(scene,depsgraph):
    sync_scene(scene)

def deferred():
    if not hasattr(bpy.data,'scenes'):return .1
    loaded(None)

def register():
    if loaded not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(loaded)
    if changed not in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.append(changed)
    bpy.app.timers.register(deferred,first_interval=.1)

def unregister():
    if bpy.app.timers.is_registered(deferred):bpy.app.timers.unregister(deferred)
    if loaded in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(loaded)
    if changed in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.remove(changed)
