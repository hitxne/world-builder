"""Optional profile-curve extrusions on the original TrackTools border curves."""
import bpy
from .native_extension import socket,set_input,road_modifier


def extrusion_group():
    name='WB_EXTENSION_BORDER_EXTRUSION';g=bpy.data.node_groups.get(name)
    if g and g.get('wb_schema',0)>=8 and any(s.name=='Layer prefix' for s in g.interface.items_tree):return g
    if g and g.library:g=g.copy();g.name=name+'_v08'
    if g:g.nodes.clear()
    else:g=bpy.data.node_groups.new(name,'GeometryNodeTree')
    g['wb_schema']=8
    socket(g,'Geometry','INPUT','NodeSocketGeometry')
    for n,k,d in [('Vertex controls','NodeSocketObject',None),('Layer prefix','NodeSocketString',''),('Use vertex controls','NodeSocketBool',False),('Use layer order','NodeSocketBool',False),('Junction cleanup','NodeSocketBool',True),('Road surfaces','NodeSocketCollection',None),('Enabled','NodeSocketBool',True),('Road','NodeSocketObject',None),('Profile curve','NodeSocketObject',None),('Path curve','NodeSocketObject',None),('Use custom path','NodeSocketBool',False),('Profile width scale','NodeSocketFloat',1.),('Profile height scale','NodeSocketFloat',1.),('Setback','NodeSocketFloat',0.),('Height offset','NodeSocketFloat',0.),('Crossing road','NodeSocketObject',None),('Lower at crossing','NodeSocketBool',False),('Transition length','NodeSocketFloat',3.),('Material','NodeSocketMaterial',None)]:
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
    source_normal=N.new('GeometryNodeInputNormal');normal_store=N.new('GeometryNodeStoreNamedAttribute');normal_store.data_type='FLOAT_VECTOR';normal_store.domain='POINT';normal_store.inputs['Name'].default_value='wb_edge_normal';L.new(edge_store.outputs['Geometry'],normal_store.inputs['Geometry']);L.new(source_normal.outputs['Normal'],normal_store.inputs['Value'])
    position_store=N.new('GeometryNodeStoreNamedAttribute');position_store.data_type='FLOAT_VECTOR';position_store.domain='POINT';position_store.inputs['Name'].default_value='wb_edge_position';L.new(normal_store.outputs['Geometry'],position_store.inputs['Geometry']);L.new(edge_position.outputs['Position'],position_store.inputs['Value'])
    profile=N.new('GeometryNodeObjectInfo');profile.transform_space='ORIGINAL';L.new(inp.outputs['Profile curve'],profile.inputs['Object'])
    negate=N.new('ShaderNodeMath');negate.operation='MULTIPLY';negate.inputs[1].default_value=-1;L.new(inp.outputs['Profile height scale'],negate.inputs[0])
    scale=N.new('ShaderNodeCombineXYZ');scale.inputs['Z'].default_value=1;L.new(inp.outputs['Profile width scale'],scale.inputs['X']);L.new(negate.outputs[0],scale.inputs['Y'])
    height_offset=N.new('ShaderNodeMath');height_offset.operation='MULTIPLY';height_offset.inputs[1].default_value=-1;L.new(inp.outputs['Height offset'],height_offset.inputs[0])
    shift=N.new('ShaderNodeCombineXYZ');L.new(inp.outputs['Setback'],shift.inputs['X']);L.new(height_offset.outputs[0],shift.inputs['Y'])
    profile_x=N.new('GeometryNodeInputPosition');profile_xyz=N.new('ShaderNodeSeparateXYZ');L.new(profile_x.outputs['Position'],profile_xyz.inputs['Vector'])
    profile_bounds=N.new('GeometryNodeAttributeStatistic');profile_bounds.data_type='FLOAT';profile_bounds.domain='POINT';L.new(profile.outputs['Geometry'],profile_bounds.inputs['Geometry']);L.new(profile_xyz.outputs['X'],profile_bounds.inputs['Attribute'])
    profile_min=profile_bounds.outputs['Min'];profile_max=profile_bounds.outputs['Max']
    profile_u=N.new('ShaderNodeMapRange');profile_u.clamp=True;L.new(profile_xyz.outputs['X'],profile_u.inputs['Value']);L.new(profile_min,profile_u.inputs['From Min']);L.new(profile_max,profile_u.inputs['From Max'])
    profile_values=N.new('GeometryNodeStoreNamedAttribute');profile_values.data_type='FLOAT';profile_values.domain='POINT';profile_values.inputs['Name'].default_value='wb_profile_x';L.new(profile.outputs['Geometry'],profile_values.inputs['Geometry']);L.new(profile_xyz.outputs['X'],profile_values.inputs['Value'])
    profile_us=N.new('GeometryNodeStoreNamedAttribute');profile_us.data_type='FLOAT';profile_us.domain='POINT';profile_us.inputs['Name'].default_value='wb_profile_u';L.new(profile_values.outputs['Geometry'],profile_us.inputs['Geometry']);L.new(profile_u.outputs['Result'],profile_us.inputs['Value'])
    orient=N.new('GeometryNodeTransform');L.new(scale.outputs['Vector'],orient.inputs['Scale']);L.new(shift.outputs['Vector'],orient.inputs['Translation']);L.new(profile_us.outputs['Geometry'],orient.inputs['Geometry'])
    sweep=N.new('GeometryNodeCurveToMesh');sweep.inputs['Fill Caps'].default_value=True;L.new(position_store.outputs['Geometry'],sweep.inputs['Curve']);L.new(orient.outputs['Geometry'],sweep.inputs['Profile Curve'])
    # Read per-control-point data from the shared raw curve, never from radius/tilt.
    controls=N.new('GeometryNodeObjectInfo');controls.transform_space='RELATIVE';L.new(inp.outputs['Vertex controls'],controls.inputs['Object'])
    edge_pos_attr=N.new('GeometryNodeInputNamedAttribute');edge_pos_attr.data_type='FLOAT_VECTOR';edge_pos_attr.inputs['Name'].default_value='wb_edge_position'
    nearest=N.new('GeometryNodeSampleNearest');nearest.domain='POINT';L.new(controls.outputs['Geometry'],nearest.inputs['Geometry']);L.new(edge_pos_attr.outputs['Attribute'],nearest.inputs['Sample Position'])
    fields={}
    for key in ('enabled','width','offset','zpos','stack'):
        text=N.new('GeometryNodeStringJoin');text.inputs['Delimiter'].default_value='';suffix=N.new('FunctionNodeInputString');suffix.string=key;L.new(suffix.outputs['String'],text.inputs['Strings']);L.new(inp.outputs['Layer prefix'],text.inputs['Strings'])
        attr_field=N.new('GeometryNodeInputNamedAttribute');attr_field.data_type='FLOAT';L.new(text.outputs['String'],attr_field.inputs['Name'])
        value=N.new('GeometryNodeSampleIndex');value.data_type='FLOAT';value.domain='POINT';L.new(controls.outputs['Geometry'],value.inputs['Geometry']);L.new(attr_field.outputs['Attribute'],value.inputs['Value']);L.new(nearest.outputs['Index'],value.inputs['Index']);fields[key]=value.outputs['Value']
    # Disconnected two-point curve segments provide real caps around disabled spans.
    wire=N.new('GeometryNodeCurveToMesh');L.new(position_store.outputs['Geometry'],wire.inputs['Curve'])
    split_edges=N.new('GeometryNodeSplitEdges');L.new(wire.outputs['Mesh'],split_edges.inputs['Mesh'])
    disabled=N.new('ShaderNodeMath');disabled.operation='LESS_THAN';disabled.inputs[1].default_value=.5;L.new(fields['enabled'],disabled.inputs[0])
    delete_edges=N.new('GeometryNodeDeleteGeometry');delete_edges.domain='EDGE';L.new(split_edges.outputs['Mesh'],delete_edges.inputs['Geometry']);L.new(disabled.outputs[0],delete_edges.inputs['Selection'])
    segments=N.new('GeometryNodeMeshToCurve');L.new(delete_edges.outputs['Geometry'],segments.inputs['Mesh'])
    normal_attr=N.new('GeometryNodeInputNamedAttribute');normal_attr.data_type='FLOAT_VECTOR';normal_attr.inputs['Name'].default_value='wb_edge_normal'
    segment_normals=N.new('GeometryNodeSetCurveNormal');segment_normals.inputs['Mode'].default_value='Free';L.new(segments.outputs['Curve'],segment_normals.inputs['Curve']);L.new(normal_attr.outputs['Attribute'],segment_normals.inputs['Normal'])
    masked_sweep=N.new('GeometryNodeCurveToMesh');masked_sweep.inputs['Fill Caps'].default_value=True;L.new(segment_normals.outputs['Curve'],masked_sweep.inputs['Curve']);L.new(orient.outputs['Geometry'],masked_sweep.inputs['Profile Curve'])
    choose_sweep=N.new('GeometryNodeSwitch');choose_sweep.input_type='GEOMETRY';L.new(inp.outputs['Use vertex controls'],choose_sweep.inputs['Switch']);L.new(sweep.outputs['Mesh'],choose_sweep.inputs['False']);L.new(masked_sweep.outputs['Mesh'],choose_sweep.inputs['True'])
    u_attr=N.new('GeometryNodeInputNamedAttribute');u_attr.data_type='FLOAT';u_attr.inputs['Name'].default_value='wb_profile_u'
    x_attr=N.new('GeometryNodeInputNamedAttribute');x_attr.data_type='FLOAT';x_attr.inputs['Name'].default_value='wb_profile_x'
    width_product=N.new('ShaderNodeMath');width_product.operation='MULTIPLY';L.new(fields['width'],width_product.inputs[0]);L.new(inp.outputs['Profile width scale'],width_product.inputs[1])
    desired_x=N.new('ShaderNodeMath');desired_x.operation='MULTIPLY';L.new(u_attr.outputs['Attribute'],desired_x.inputs[0]);L.new(fields['width'],desired_x.inputs[1])
    stack_choice=N.new('GeometryNodeSwitch');stack_choice.input_type='FLOAT';L.new(inp.outputs['Use layer order'],stack_choice.inputs['Switch']);L.new(fields['stack'],stack_choice.inputs['True'])
    wanted_offset=N.new('ShaderNodeMath');wanted_offset.operation='ADD';L.new(stack_choice.outputs['Output'],wanted_offset.inputs[0]);L.new(fields['offset'],wanted_offset.inputs[1])
    wanted=N.new('ShaderNodeMath');wanted.operation='ADD';L.new(desired_x.outputs[0],wanted.inputs[0]);L.new(wanted_offset.outputs[0],wanted.inputs[1])
    old_x=N.new('ShaderNodeMath');old_x.operation='MULTIPLY';L.new(x_attr.outputs['Attribute'],old_x.inputs[0]);L.new(inp.outputs['Profile width scale'],old_x.inputs[1])
    x_delta=N.new('ShaderNodeMath');x_delta.operation='SUBTRACT';L.new(wanted.outputs[0],x_delta.inputs[0]);L.new(old_x.outputs[0],x_delta.inputs[1])
    x_vector=N.new('ShaderNodeVectorMath');x_vector.operation='SCALE';L.new(normal_attr.outputs['Attribute'],x_vector.inputs[0]);L.new(x_delta.outputs[0],x_vector.inputs['Scale'])
    z_vector=N.new('ShaderNodeCombineXYZ');L.new(fields['zpos'],z_vector.inputs['Z'])
    vertex_offset=N.new('ShaderNodeVectorMath');vertex_offset.operation='ADD';L.new(x_vector.outputs['Vector'],vertex_offset.inputs[0]);L.new(z_vector.outputs['Vector'],vertex_offset.inputs[1])
    vertex_switch=N.new('GeometryNodeSwitch');vertex_switch.input_type='VECTOR';L.new(inp.outputs['Use vertex controls'],vertex_switch.inputs['Switch']);L.new(vertex_offset.outputs['Vector'],vertex_switch.inputs['True'])
    vertex_shape=N.new('GeometryNodeSetPosition');L.new(choose_sweep.outputs['Output'],vertex_shape.inputs['Geometry']);L.new(vertex_switch.outputs['Output'],vertex_shape.inputs['Offset'])
    profile_position=N.new('GeometryNodeInputPosition');max_profile=N.new('ShaderNodeSeparateXYZ');L.new(profile_position.outputs['Position'],max_profile.inputs['Vector'])
    heights=N.new('GeometryNodeAttributeStatistic');heights.data_type='FLOAT';heights.domain='POINT';L.new(profile.outputs['Geometry'],heights.inputs['Geometry']);L.new(max_profile.outputs['Y'],heights.inputs['Attribute'])
    top_height=N.new('ShaderNodeMath');top_height.operation='MULTIPLY';L.new(heights.outputs['Max'],top_height.inputs[0]);L.new(inp.outputs['Profile height scale'],top_height.inputs[1])
    top_offset=N.new('ShaderNodeMath');top_offset.operation='ADD';L.new(top_height.outputs[0],top_offset.inputs[0]);L.new(inp.outputs['Height offset'],top_offset.inputs[1])
    edge_attr=N.new('GeometryNodeInputNamedAttribute');edge_attr.data_type='FLOAT';edge_attr.inputs['Name'].default_value='wb_edge_elevation'
    top_reference=N.new('ShaderNodeMath');top_reference.operation='ADD';L.new(edge_attr.outputs['Attribute'],top_reference.inputs[0]);L.new(top_offset.outputs[0],top_reference.inputs[1]);vertex_top=N.new('ShaderNodeMath');vertex_top.operation='ADD';L.new(top_reference.outputs[0],vertex_top.inputs[0]);L.new(fields['zpos'],vertex_top.inputs[1])
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
    difference=N.new('ShaderNodeMath');difference.operation='SUBTRACT';L.new(target.outputs['Output'],difference.inputs[0]);vertex_top_switch=N.new('GeometryNodeSwitch');vertex_top_switch.input_type='FLOAT';L.new(inp.outputs['Use vertex controls'],vertex_top_switch.inputs['Switch']);L.new(top_reference.outputs[0],vertex_top_switch.inputs['False']);L.new(vertex_top.outputs[0],vertex_top_switch.inputs['True']);L.new(vertex_top_switch.outputs['Output'],difference.inputs[1])
    lower=N.new('ShaderNodeMath');lower.operation='MINIMUM';lower.inputs[1].default_value=0;L.new(difference.outputs[0],lower.inputs[0])
    multiply=N.new('ShaderNodeMath');multiply.operation='MULTIPLY';L.new(lower.outputs[0],multiply.inputs[0]);L.new(enabled.outputs['Output'],multiply.inputs[1])
    offset=N.new('ShaderNodeCombineXYZ');L.new(multiply.outputs[0],offset.inputs['Z'])
    deform=N.new('GeometryNodeSetPosition');L.new(vertex_shape.outputs['Geometry'],deform.inputs['Geometry']);L.new(offset.outputs['Vector'],deform.inputs['Offset'])
    # Resolve concave offset folds as one solid; never apply a modifier to a native road.
    union=N.new('GeometryNodeMeshBoolean');union.operation='UNION';union.solver='EXACT';union.inputs['Self Intersection'].default_value=True;L.new(deform.outputs['Geometry'],union.inputs['Mesh 2'])
    network=N.new('GeometryNodeCollectionInfo');network.transform_space='RELATIVE';L.new(inp.outputs['Road surfaces'],network.inputs['Collection'])
    realized=N.new('GeometryNodeRealizeInstances');L.new(network.outputs['Instances'],realized.inputs['Geometry'])
    network_size=N.new('GeometryNodeAttributeDomainSize');network_size.component='MESH';L.new(realized.outputs['Geometry'],network_size.inputs['Geometry']);network_exists=N.new('ShaderNodeMath');network_exists.operation='GREATER_THAN';L.new(network_size.outputs['Face Count'],network_exists.inputs[0])
    mesh_join=N.new('GeometryNodeSwitch');mesh_join.input_type='GEOMETRY';L.new(network_exists.outputs[0],mesh_join.inputs['Switch']);L.new(road.outputs['Geometry'],mesh_join.inputs['False']);L.new(realized.outputs['Geometry'],mesh_join.inputs['True'])
    road_part=N.new('FunctionNodeCompare');road_part.data_type='INT';road_part.operation='EQUAL';road_part.inputs[3].default_value=1;L.new(attr.outputs['Attribute'],road_part.inputs[2])
    paved=N.new('GeometryNodeSeparateGeometry');paved.domain='POINT';L.new(mesh_join.outputs['Output'],paved.inputs['Geometry']);L.new(road_part.outputs['Result'],paved.inputs['Selection'])
    normal=N.new('GeometryNodeInputNormal');normal_z=N.new('ShaderNodeSeparateXYZ');L.new(normal.outputs['Normal'],normal_z.inputs['Vector'])
    up=N.new('ShaderNodeMath');up.operation='GREATER_THAN';up.inputs[1].default_value=.1;L.new(normal_z.outputs['Z'],up.inputs[0])
    # Extruding a plane leaves the base open: explicitly join a reversed base.
    road_down=N.new('ShaderNodeMath');road_down.operation='LESS_THAN';L.new(normal_z.outputs['Z'],road_down.inputs[0])
    road_flip=N.new('GeometryNodeFlipFaces');L.new(paved.outputs['Selection'],road_flip.inputs['Mesh']);L.new(road_down.outputs[0],road_flip.inputs['Selection'])
    road_floor=N.new('GeometryNodeFlipFaces');L.new(road_flip.outputs['Mesh'],road_floor.inputs['Mesh'])
    cutter=N.new('GeometryNodeExtrudeMesh');cutter.mode='FACES';cutter.inputs['Individual'].default_value=False;cutter.inputs['Offset'].default_value=(0,0,10);cutter.inputs['Offset Scale'].default_value=1;L.new(road_flip.outputs['Mesh'],cutter.inputs['Mesh'])
    closed_cutter=N.new('GeometryNodeJoinGeometry');L.new(road_floor.outputs['Mesh'],closed_cutter.inputs['Geometry']);L.new(cutter.outputs['Mesh'],closed_cutter.inputs['Geometry'])
    weld_cutter=N.new('GeometryNodeMergeByDistance');weld_cutter.inputs['Distance'].default_value=.0001;L.new(closed_cutter.outputs['Geometry'],weld_cutter.inputs['Geometry'])
    clip=N.new('GeometryNodeMeshBoolean');clip.operation='DIFFERENCE';clip.solver='EXACT';clip.inputs['Self Intersection'].default_value=True;L.new(union.outputs['Mesh'],clip.inputs['Mesh 1']);L.new(weld_cutter.outputs['Geometry'],clip.inputs['Mesh 2'])
    cleaned=N.new('GeometryNodeSwitch');cleaned.input_type='GEOMETRY';L.new(inp.outputs['Junction cleanup'],cleaned.inputs['Switch']);L.new(deform.outputs['Geometry'],cleaned.inputs['False']);L.new(clip.outputs['Mesh'],cleaned.inputs['True'])
    mat=N.new('GeometryNodeSetMaterial');L.new(inp.outputs['Material'],mat.inputs['Material']);L.new(cleaned.outputs['Output'],mat.inputs['Geometry'])
    # Native terrain receives tagged physical surfaces and their final boundary curves.
    surfaces=N.new('GeometryNodeStoreNamedAttribute');surfaces.data_type='INT';surfaces.domain='POINT';surfaces.inputs['Name'].default_value='parts';surfaces.inputs['Value'].default_value=1;L.new(mat.outputs['Geometry'],surfaces.inputs['Geometry'])
    face_normal=N.new('GeometryNodeInputNormal');face_z=N.new('ShaderNodeSeparateXYZ');L.new(face_normal.outputs['Normal'],face_z.inputs['Vector'])
    face_up=N.new('ShaderNodeMath');face_up.operation='GREATER_THAN';face_up.inputs[1].default_value=.1;L.new(face_z.outputs['Z'],face_up.inputs[0])
    tops=N.new('GeometryNodeSeparateGeometry');tops.domain='FACE';L.new(surfaces.outputs['Geometry'],tops.inputs['Geometry']);L.new(face_up.outputs[0],tops.inputs['Selection'])
    neighbors=N.new('GeometryNodeInputMeshEdgeNeighbors');boundary=N.new('FunctionNodeCompare');boundary.data_type='INT';boundary.operation='EQUAL';boundary.inputs[3].default_value=1;L.new(neighbors.outputs['Face Count'],boundary.inputs[2])
    rim=N.new('GeometryNodeMeshToCurve');L.new(tops.outputs['Selection'],rim.inputs['Mesh']);L.new(boundary.outputs['Result'],rim.inputs['Selection'])
    tagged_rim=N.new('GeometryNodeStoreNamedAttribute');tagged_rim.data_type='INT';tagged_rim.domain='POINT';tagged_rim.inputs['Name'].default_value='parts';tagged_rim.inputs['Value'].default_value=7;L.new(rim.outputs['Curve'],tagged_rim.inputs['Geometry'])
    rim_id=N.new('GeometryNodeStoreNamedAttribute');rim_id.data_type='INT';rim_id.domain='POINT';rim_id.inputs['Name'].default_value='edgeID';rim_id.inputs['Value'].default_value=0;L.new(tagged_rim.outputs['Geometry'],rim_id.inputs['Geometry'])
    final=N.new('GeometryNodeJoinGeometry');L.new(surfaces.outputs['Geometry'],final.inputs['Geometry']);L.new(rim_id.outputs['Geometry'],final.inputs['Geometry'])
    enabled_geometry=N.new('GeometryNodeSwitch');enabled_geometry.input_type='GEOMETRY';source_size=N.new('GeometryNodeAttributeDomainSize');source_size.component='MESH';L.new(deform.outputs['Geometry'],source_size.inputs['Geometry']);has_faces=N.new('ShaderNodeMath');has_faces.operation='GREATER_THAN';L.new(source_size.outputs['Face Count'],has_faces.inputs[0]);live=N.new('FunctionNodeBooleanMath');live.operation='AND';L.new(inp.outputs['Enabled'],live.inputs[0]);L.new(has_faces.outputs[0],live.inputs[1]);L.new(live.outputs['Boolean'],enabled_geometry.inputs['Switch']);L.new(final.outputs['Geometry'],enabled_geometry.inputs['True']);L.new(enabled_geometry.outputs['Output'],out.inputs['Geometry'])
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
    mod=obj.modifiers.new('WB optional '+kind+' extrusion','NODES');mod.node_group=extrusion_group();set_input(mod,'Road',road);set_input(mod,'Profile curve',profile);set_input(mod,'Material',material({'curb':'concrete','sidewalk':'sidewalk','grass':'grass'}[kind]));
    from .native_layers import add_layer
    add_layer(scene,road,obj,kind)
    from .native_contacts import connect_surfaces
    connect_surfaces(scene);return obj,profile
