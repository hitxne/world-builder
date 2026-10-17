"""Collection wiring for native terrain and WB expansions; no native group edits."""
import bpy
from .modifier_inputs import get_value
from .native_extension import native_roads,native_terrain,set_input


def input_value(mod,name):
    s=next((s for s in mod.node_group.interface.items_tree if s.name==name and getattr(s,'in_out',None)=='INPUT'),None)
    return get_value(mod,s.identifier,getattr(s,'default_value',None)) if s else None


def collection(scene,name):
    c=next((c for c in scene.collection.children if c.name.split('.')[0]==name),None)
    if c is None:c=bpy.data.collections.new(name);scene.collection.children.link(c)
    c['wb_owned_contacts']=True;return c


def connect_surfaces(scene):
    roads=native_roads(scene);refs=collection(scene,'WB_NATIVE_ROAD_REFERENCES')
    for obj in list(refs.objects):
        if obj not in roads:refs.objects.unlink(obj)
    for obj in roads:
        if obj.name not in refs.objects:refs.objects.link(obj)
    features=next((c for c in scene.collection.children if c.name.split('.')[0]=='ROADLAB_FEATURES'),None)
    if features is None:return
    from .native_extrusion import extrusion_group
    group=extrusion_group()
    for obj in features.objects:
        if obj.get('wb_native_feature') not in ('curb','sidewalk','grass'):continue
        for mod in obj.modifiers:
            if mod.type=='NODES' and mod.node_group and mod.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):
                if mod.node_group!=group:mod.node_group=group
                set_input(mod,'Road surfaces',refs)
    terrain=native_terrain(scene)
    if terrain is None:return
    for mod in terrain.modifiers:
        if mod.type!='NODES' or not mod.node_group:continue
        name=mod.node_group.name.split('.')[0]
        if name not in ('TERRAIN_GEOMETRY','TERRAIN_SHAPE'):continue
        if getattr(mod.node_group,'is_missing',False):continue
        geom=name=='TERRAIN_GEOMETRY';mode_name='input type' if geom else 'target mode';col_name='road collection' if geom else 'target collection';obj_name='road object' if geom else 'target object'
        required={mode_name,col_name,obj_name}
        available={item.name for item in mod.node_group.interface.items_tree if getattr(item,'in_out',None)=='INPUT'}
        if not required.issubset(available):continue
        target=input_value(mod,col_name)
        if input_value(mod,mode_name)!=1 or target is None:
            target=collection(scene,'WB_NATIVE_TERRAIN_TARGETS');original=input_value(mod,obj_name)
            if original and original.name not in target.objects:target.objects.link(original)
            if refs.name not in target.children:target.children.link(refs)
            set_input(mod,mode_name,1);set_input(mod,col_name,target)
        if target==features:raise ValueError('Choose a separate native terrain target collection')
        if features.name not in target.children:target.children.link(features)
    scene['wb_native_terrain_contacts']='Native terrain targets include WB curb, sidewalk and grass surfaces'
