"""Open grass surfaces use the editable terrain mesh as a cycle-free base."""
import bpy
from .native_extension import native_terrain,set_input


def terrain_base(scene):
    terrain=scene.wb_native.terrain or native_terrain(scene)
    if not terrain:return None
    base=next((o for o in scene.objects if o.get('wb_grass_terrain_base') and o.get('wb_terrain_source')==terrain),None)
    if base is None:
        collection=bpy.data.collections.get('RoadLab Terrain References')
        if collection is None:collection=bpy.data.collections.new('RoadLab Terrain References');scene.collection.children.link(collection)
        elif collection.name not in scene.collection.children:scene.collection.children.link(collection)
        base=bpy.data.objects.new('RoadLab Grass Terrain Base',terrain.data);collection.objects.link(base)
        base['wb_grass_terrain_base']=True;base['wb_terrain_source']=terrain;base.hide_render=True;base.hide_set(True)
    if base.data!=terrain.data:base.data=terrain.data
    if base.matrix_world!=terrain.matrix_world:base.matrix_world=terrain.matrix_world.copy()
    return base


def sync_bases(scene):
    for base in scene.objects:
        if not base.get('wb_grass_terrain_base'):continue
        source=base.get('wb_terrain_source')
        if source:
            if base.data!=source.data:base.data=source.data
            if base.matrix_world!=source.matrix_world:base.matrix_world=source.matrix_world.copy()


def configure(scene,obj,mod):
    from .native_contacts import input_value
    from .native_extrusion import extrusion_group
    mod.node_group=extrusion_group()
    profile=input_value(mod,'Profile curve')
    if profile and profile.type=='CURVE' and profile.get('wb_native_feature')=='profile':
        needs_conversion=any(s.use_cyclic_u for s in profile.data.splines)
        if needs_conversion:
            if profile.users>2:
                copy=profile.copy();copy.data=profile.data.copy();profile.users_collection[0].objects.link(copy);profile=copy;set_input(mod,'Profile curve',profile)
            upper={}
            for spline in profile.data.splines:
                for point in (spline.bezier_points if spline.type=='BEZIER' else spline.points):
                    x,y=point.co[:2];upper[x]=max(upper.get(x,float('-inf')),y)
            if len(upper)>1:
                profile.data.splines.clear();spline=profile.data.splines.new('POLY');spline.points.add(len(upper)-1)
                for point,(x,y) in zip(spline.points,sorted(upper.items())):point.co=(x,y,0,1)
                profile.data.update_tag()
    set_input(mod,'Grass surface',True);set_input(mod,'Terrain base',terrain_base(scene))
