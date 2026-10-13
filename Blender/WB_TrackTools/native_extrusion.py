"""Optional profile-curve extrusions on the original TrackTools border curves."""
import bpy
from .native_extension import socket,set_input,road_modifier


def extrusion_group():
    name='WB_EXTENSION_BORDER_EXTRUSION';g=bpy.data.node_groups.get(name)
    if g:return g
    g=bpy.data.node_groups.new(name,'GeometryNodeTree')
    socket(g,'Geometry','INPUT','NodeSocketGeometry')
    for n,k,d in [('Enabled','NodeSocketBool',True),('Road','NodeSocketObject',None),('Profile curve','NodeSocketObject',None),('Path curve','NodeSocketObject',None),('Use custom path','NodeSocketBool',False),('Profile width scale','NodeSocketFloat',1.),('Profile height scale','NodeSocketFloat',1.),('Setback','NodeSocketFloat',0.),('Height offset','NodeSocketFloat',0.),('Crossing road','NodeSocketObject',None),('Lower at crossing','NodeSocketBool',False),('Transition length','NodeSocketFloat',3.),('Material','NodeSocketMaterial',None)]:
        item=socket(g,n,'INPUT',k,d)
        if n in ('Profile width scale','Profile height scale','Transition length'):item.min_value=.01
    socket(g,'Geometry','OUTPUT','NodeSocketGeometry')
    N=g.nodes;L=g.links;inp=N.new('NodeGroupInput');out=N.new('NodeGroupOutput')
    road=N.new('GeometryNodeObjectInfo');road.transform_space='RELATIVE';L.new(inp.outputs['Road'],road.inputs['Object'])
    attr=N.new('GeometryNodeInputNamedAttribute');attr.data_type='INT';attr.inputs['Name'].default_value='parts'
    test=N.new('FunctionNodeCompare');test.data_type='INT';test.operation='EQUAL';test.inputs[3].default_value=7;L.new(attr.outputs['Attribute'],test.inputs[2])
    border=N.new('GeometryNodeSeparateGeometry');border.domain='POINT';L.new(road.outputs['Geometry'],border.inputs['Geometry']);L.new(test.outputs['Result'],border.inputs['Selection'])
    path=N.new('GeometryNodeObjectInfo');path.transform_space='RELATIVE';L.new(inp.outputs['Path curve'],path.inputs['Object'])
    choose_path=N.new('GeometryNodeSwitch');choose_path.input_type='GEOMETRY';L.new(inp.outputs['Use custom path'],choose_path.inputs['Switch']);L.new(border.outputs['Selection'],choose_path.inputs['False']);L.new(path.outputs['Geometry'],choose_path.inputs['True'])
    resample=N.new('GeometryNodeResampleCurve');resample.inputs['Mode'].default_value='Length';resample.inputs['Length'].default_value=.25;L.new(choose_path.outputs['Output'],resample.inputs['Curve'])
    edge_position=N.new('GeometryNodeInputPosition');edge_z=N.new('ShaderNodeSeparateXYZ');L.new(edge_position.outputs['Position'],edge_z.inputs['Vector'])
    edge_store=N.new('GeometryNodeStoreNamedAttribute');edge_store.data_type='FLOAT';edge_store.domain='POINT';edge_store.inputs['Name'].default_value='wb_edge_elevation';L.new(edge_z.outputs['Z'],edge_store.inputs['Value']);L.new(resample.outputs['Curve'],edge_store.inputs['Geometry'])
    profile=N.new('GeometryNodeObjectInfo');profile.transform_space='ORIGINAL';L.new(inp.outputs['Profile curve'],profile.inputs['Object'])
    negate=N.new('ShaderNodeMath');negate.operation='MULTIPLY';negate.inputs[1].default_value=-1;L.new(inp.outputs['Profile height scale'],negate.inputs[0])
    scale=N.new('ShaderNodeCombineXYZ');scale.inputs['Z'].default_value=1;L.new(inp.outputs['Profile width scale'],scale.inputs['X']);L.new(negate.outputs[0],scale.inputs['Y'])
    height_offset=N.new('ShaderNodeMath');height_offset.operation='MULTIPLY';height_offset.inputs[1].default_value=-1;L.new(inp.outputs['Height offset'],height_offset.inputs[0])
    shift=N.new('ShaderNodeCombineXYZ');L.new(inp.outputs['Setback'],shift.inputs['X']);L.new(height_offset.outputs[0],shift.inputs['Y'])
    orient=N.new('GeometryNodeTransform');L.new(scale.outputs['Vector'],orient.inputs['Scale']);L.new(shift.outputs['Vector'],orient.inputs['Translation']);L.new(profile.outputs['Geometry'],orient.inputs['Geometry'])
    sweep=N.new('GeometryNodeCurveToMesh');sweep.inputs['Fill Caps'].default_value=True;L.new(edge_store.outputs['Geometry'],sweep.inputs['Curve']);L.new(orient.outputs['Geometry'],sweep.inputs['Profile Curve'])
    profile_position=N.new('GeometryNodeInputPosition');max_profile=N.new('ShaderNodeSeparateXYZ');L.new(profile_position.outputs['Position'],max_profile.inputs['Vector'])
    heights=N.new('GeometryNodeAttributeStatistic');heights.data_type='FLOAT';heights.domain='POINT';L.new(profile.outputs['Geometry'],heights.inputs['Geometry']);L.new(max_profile.outputs['Y'],heights.inputs['Attribute'])
    top_height=N.new('ShaderNodeMath');top_height.operation='MULTIPLY';L.new(heights.outputs['Max'],top_height.inputs[0]);L.new(inp.outputs['Profile height scale'],top_height.inputs[1])
    top_offset=N.new('ShaderNodeMath');top_offset.operation='ADD';L.new(top_height.outputs[0],top_offset.inputs[0]);L.new(inp.outputs['Height offset'],top_offset.inputs[1])
    edge_attr=N.new('GeometryNodeInputNamedAttribute');edge_attr.data_type='FLOAT';edge_attr.inputs['Name'].default_value='wb_edge_elevation'
    top_reference=N.new('ShaderNodeMath');top_reference.operation='ADD';L.new(edge_attr.outputs['Attribute'],top_reference.inputs[0]);L.new(top_offset.outputs[0],top_reference.inputs[1])
    cross=N.new('GeometryNodeObjectInfo');cross.transform_space='RELATIVE';L.new(inp.outputs['Crossing road'],cross.inputs['Object'])
    position=N.new('GeometryNodeInputPosition');split=N.new('ShaderNodeSeparateXYZ');L.new(position.outputs['Position'],split.inputs['Vector'])
    proximity=N.new('GeometryNodeProximity');proximity.target_element='FACES';L.new(cross.outputs['Geometry'],proximity.inputs['Geometry'])
    closest=N.new('ShaderNodeSeparateXYZ');L.new(proximity.outputs['Position'],closest.inputs['Vector'])
    ramp=N.new('ShaderNodeMapRange');ramp.interpolation_type='SMOOTHERSTEP';ramp.clamp=True;ramp.inputs['From Min'].default_value=0;ramp.inputs['To Min'].default_value=1;ramp.inputs['To Max'].default_value=0;L.new(inp.outputs['Transition length'],ramp.inputs['From Max']);L.new(proximity.outputs['Distance'],ramp.inputs['Value'])
    origin=N.new('ShaderNodeVectorMath');origin.operation='ADD';origin.inputs[1].default_value=(0,0,1000);L.new(position.outputs['Position'],origin.inputs[0])
    ray=N.new('GeometryNodeRaycast');ray.data_type='FLOAT';ray.inputs['Ray Direction'].default_value=(0,0,-1);ray.inputs['Ray Length'].default_value=2000;L.new(cross.outputs['Geometry'],ray.inputs['Target Geometry']);L.new(origin.outputs['Vector'],ray.inputs['Source Position'])
    hit_z=N.new('ShaderNodeSeparateXYZ');L.new(ray.outputs['Hit Position'],hit_z.inputs['Vector'])
    target=N.new('GeometryNodeSwitch');target.input_type='FLOAT';L.new(ray.outputs['Is Hit'],target.inputs['Switch']);L.new(closest.outputs['Z'],target.inputs['False']);L.new(hit_z.outputs['Z'],target.inputs['True'])
    weight=N.new('GeometryNodeSwitch');weight.input_type='FLOAT';weight.inputs['True'].default_value=1;L.new(ray.outputs['Is Hit'],weight.inputs['Switch']);L.new(ramp.outputs['Result'],weight.inputs['False'])
    enabled=N.new('GeometryNodeSwitch');enabled.input_type='FLOAT';enabled.inputs['False'].default_value=0;L.new(inp.outputs['Lower at crossing'],enabled.inputs['Switch']);L.new(weight.outputs['Output'],enabled.inputs['True'])
    difference=N.new('ShaderNodeMath');difference.operation='SUBTRACT';L.new(target.outputs['Output'],difference.inputs[0]);L.new(top_reference.outputs[0],difference.inputs[1])
    lower=N.new('ShaderNodeMath');lower.operation='MINIMUM';lower.inputs[1].default_value=0;L.new(difference.outputs[0],lower.inputs[0])
    multiply=N.new('ShaderNodeMath');multiply.operation='MULTIPLY';L.new(lower.outputs[0],multiply.inputs[0]);L.new(enabled.outputs['Output'],multiply.inputs[1])
    offset=N.new('ShaderNodeCombineXYZ');L.new(multiply.outputs[0],offset.inputs['Z'])
    deform=N.new('GeometryNodeSetPosition');L.new(sweep.outputs['Mesh'],deform.inputs['Geometry']);L.new(offset.outputs['Vector'],deform.inputs['Offset'])
    mat=N.new('GeometryNodeSetMaterial');L.new(inp.outputs['Material'],mat.inputs['Material']);L.new(deform.outputs['Geometry'],mat.inputs['Geometry'])
    enabled_geometry=N.new('GeometryNodeSwitch');enabled_geometry.input_type='GEOMETRY';L.new(inp.outputs['Enabled'],enabled_geometry.inputs['Switch']);L.new(mat.outputs['Geometry'],enabled_geometry.inputs['True']);L.new(enabled_geometry.outputs['Output'],out.inputs['Geometry'])
    layout=[(inp,(0,400)),(road,(280,400)),(attr,(280,0)),(test,(520,0)),(border,(760,400)),(path,(760,800)),(choose_path,(1000,400)),(resample,(1240,400)),(edge_store,(1480,400)),(edge_position,(1000,0)),(edge_z,(1240,0)),(profile,(760,-500)),(negate,(760,-900)),(scale,(1000,-700)),(height_offset,(760,-1200)),(shift,(1000,-1100)),(orient,(1240,-500)),(sweep,(1720,400)),(profile_position,(1000,-1450)),(max_profile,(1240,-1450)),(heights,(1480,-800)),(top_height,(1720,-800)),(top_offset,(1960,-800)),(edge_attr,(1960,-1150)),(top_reference,(2200,-800)),(cross,(1960,1000)),(position,(1720,1450)),(split,(1960,1450)),(proximity,(2200,1000)),(closest,(2440,1000)),(ramp,(2440,600)),(origin,(1960,1800)),(ray,(2200,1800)),(hit_z,(2440,1800)),(target,(2680,1300)),(weight,(2680,600)),(enabled,(2920,600)),(difference,(2920,1300)),(lower,(3160,1300)),(multiply,(3400,1000)),(offset,(3640,1000)),(deform,(3880,400)),(mat,(4120,400)),(enabled_geometry,(4360,400)),(out,(4600,400))]
    for node,location in layout:node.location=location
    edge_store.label='Remember native road edge height';top_reference.label='Profile top elevation';lower.label='Lower only; leave elevated crossings clear';enabled_geometry.label='Optional extrusion'
    return g


def add_extrusion(scene,road,kind):
    if not road_modifier(road):raise ValueError('Choose an existing TrackTools road curve')
    from . import material
    collection=bpy.data.collections.get('WB_TRACKTOOLS_FEATURES')
    if collection is None:collection=bpy.data.collections.new('WB_TRACKTOOLS_FEATURES');scene.collection.children.link(collection)
    profiles=bpy.data.collections.get('WB_EDITABLE_PROFILES')
    if profiles is None:profiles=bpy.data.collections.new('WB_EDITABLE_PROFILES');scene.collection.children.link(profiles)
    coords={'curb':[(0,0),(.035,.1324),(.065,.1524),(.32,.1524),(.32,0)],'sidewalk':[(.32,.1524),(2.52,.1524),(2.52,.0524),(.32,.0524)],'grass':[(2.52,.08),(3.72,.08),(3.72,-.08),(2.52,-.08)]}[kind]
    curve=bpy.data.curves.new('WB_Profile_'+kind,'CURVE');curve.dimensions='2D';curve.fill_mode='NONE';spline=curve.splines.new('POLY');spline.points.add(len(coords)-1);spline.use_cyclic_u=True
    for p,(x,y) in zip(spline.points,coords):p.co=(x,y,0,1)
    profile=bpy.data.objects.new('WB_Profile_'+kind,curve);profiles.objects.link(profile);profile.hide_render=True;profile.hide_set(True);profile['wb_native_feature']='profile'
    obj=bpy.data.objects.new('WB_'+kind+'_'+road.name,bpy.data.meshes.new('WB_'+kind));collection.objects.link(obj);obj['wb_native_feature']=kind
    mod=obj.modifiers.new('WB optional '+kind+' extrusion','NODES');mod.node_group=extrusion_group();set_input(mod,'Road',road);set_input(mod,'Profile curve',profile);set_input(mod,'Material',material({'curb':'concrete','sidewalk':'sidewalk','grass':'grass'}[kind]));return obj,profile
