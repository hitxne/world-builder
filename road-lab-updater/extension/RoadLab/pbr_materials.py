"""Shared, offline PBR surfaces. Texture coordinates are measured in world meters."""
from pathlib import Path
import bpy
SPECS={'asphalt':('asphalt_03',2.0),'grass':('leafy_grass',2.0),'concrete':('concrete_floor_02',2.0),'sidewalk':('concrete_floor_02',2.0),'gutter':('concrete_floor_02',2.0)}
ROOT=Path(__file__).with_name('textures')

def ensure(mat,kind):
    if kind not in SPECS or not mat.use_nodes or mat.get('roadlab_pbr_version')==1:return mat
    # Preserve user-authored materials; only upgrade RoadLab's original plain shader.
    if any(n.type not in {'BSDF_PRINCIPLED','OUTPUT_MATERIAL'} for n in mat.node_tree.nodes):return mat
    asset,meters=SPECS[kind]
    paths={k:ROOT/f'{asset}_{k}_1k.jpg' for k in ('diff','rough','nor_gl')}
    if not all(p.is_file() for p in paths.values()):return mat
    nodes=mat.node_tree.nodes;links=mat.node_tree.links
    shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    geo=nodes.new('ShaderNodeNewGeometry');geo.location=(-1000,0)
    size=nodes.new('ShaderNodeValue');size.name='RoadLab Texture Size';size.label='Texture repeat (meters)';size.outputs[0].default_value=meters;size.location=(-1000,300)
    divide=nodes.new('ShaderNodeMath');divide.operation='DIVIDE';divide.inputs[0].default_value=1;links.new(size.outputs[0],divide.inputs[1])
    scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';links.new(geo.outputs['Position'],scale.inputs[0]);links.new(divide.outputs[0],scale.inputs[3]);scale.location=(-800,0)
    textures={}
    for i,(kind_map,path) in enumerate(paths.items()):
        image=bpy.data.images.load(str(path),check_existing=True)
        image.colorspace_settings.name='sRGB' if kind_map=='diff' else 'Non-Color'
        # Packed images survive moving a .blend and updating the extension directory.
        if not image.packed_file:image.pack()
        tex=nodes.new('ShaderNodeTexImage');tex.image=image;tex.projection='BOX';tex.projection_blend=.2;tex.extension='REPEAT';tex.location=(-550,400-i*300);links.new(scale.outputs['Vector'],tex.inputs['Vector']);textures[kind_map]=tex
    links.new(textures['diff'].outputs['Color'],shader.inputs['Base Color']);links.new(textures['rough'].outputs['Color'],shader.inputs['Roughness'])
    # Reorient tangent-space normal data into a surface basis; no UV unwrap required.
    def vector(op,a=None,b=None):
        n=nodes.new('ShaderNodeVectorMath');n.operation=op
        for value,index in ((a,0),(b,1)):
            if value is not None:
                if hasattr(value,'node'):links.new(value,n.inputs[index])
                else:n.inputs[index].default_value=value
        return n
    normal=geo.outputs['Normal']
    dot=vector('DOT_PRODUCT',normal,(0,1,0))
    absolute=nodes.new('ShaderNodeMath');absolute.operation='ABSOLUTE';links.new(dot.outputs['Value'],absolute.inputs[0])
    threshold=nodes.new('ShaderNodeMath');threshold.operation='GREATER_THAN';threshold.inputs[1].default_value=.99;links.new(absolute.outputs[0],threshold.inputs[0])
    axis=nodes.new('ShaderNodeMixRGB');axis.inputs[1].default_value=(0,1,0,1);axis.inputs[2].default_value=(1,0,0,1);links.new(threshold.outputs[0],axis.inputs[0])
    tangent=vector('CROSS_PRODUCT',axis.outputs[0],normal)
    tangent=vector('NORMALIZE',tangent.outputs[0]).outputs[0]
    bitangent=vector('CROSS_PRODUCT',normal,tangent).outputs[0]
    decoded=vector('MULTIPLY_ADD',textures['nor_gl'].outputs['Color'],(2,2,2));decoded.inputs[2].default_value=(-1,-1,-1)
    split=nodes.new('ShaderNodeSeparateXYZ');links.new(decoded.outputs[0],split.inputs[0])
    components=[]
    for basis,component in zip((tangent,bitangent,normal),('X','Y','Z')):
        n=vector('SCALE',basis);links.new(split.outputs[component],n.inputs[3]);components.append(n.outputs[0])
    combined=vector('ADD',vector('ADD',components[0],components[1]).outputs[0],components[2]);links.new(combined.outputs[0],shader.inputs['Normal'])
    mat['roadlab_pbr_version']=1;mat['roadlab_texture_source']='https://polyhaven.com/a/'+asset
    return mat

def upgrade_defaults():
    for kind in SPECS:
        mat=bpy.data.materials.get('WB_'+kind)
        if mat and mat.use_nodes:ensure(mat,kind)
    return None

@bpy.app.handlers.persistent
def loaded(_):
    upgrade_defaults()

class ROADLAB_PT_surface_materials(bpy.types.Panel):
    bl_label='Surface materials';bl_idname='ROADLAB_PT_surface_materials'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):
        obj=context.active_object
        return obj is not None and (obj==getattr(getattr(context.scene,'wb_native',None),'terrain',None) or obj.type=='CURVE' and obj.get('roadlab_new_core') or obj.get('roadlab_surface_bounds'))
    def draw(self,context):
        self.layout.label(text='Shared material scale (meters)')
        for kind in ('asphalt','grass','sidewalk','concrete'):
            mat=bpy.data.materials.get('WB_'+kind)
            if mat and mat.use_nodes:
                node=mat.node_tree.nodes.get('RoadLab Texture Size')
                if node:self.layout.prop(node.outputs[0],'default_value',text=kind.title())
        self.layout.label(text='Edit texture maps in Shader Editor')

def register():
    bpy.utils.register_class(ROADLAB_PT_surface_materials)
    if loaded not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(loaded)
    bpy.app.timers.register(upgrade_defaults,first_interval=.2)

def unregister():
    if loaded in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(loaded)
    if bpy.app.timers.is_registered(upgrade_defaults):bpy.app.timers.unregister(upgrade_defaults)
    bpy.utils.unregister_class(ROADLAB_PT_surface_materials)
