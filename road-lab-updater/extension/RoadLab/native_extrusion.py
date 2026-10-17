"""Optional profile-curve extrusions on the original upstream border curves."""
from .modifier_inputs import integer_operand
import bpy
from .modifier_inputs import get_value, set_value
from .native_extension import socket,set_input,road_modifier


def extrusion_group():
    name='WB_EXTENSION_BORDER_EXTRUSION';g=bpy.data.node_groups.get(name)
    if g and g.get('wb_schema',0)>=18 and any(s.name=='Layer prefix' for s in g.interface.items_tree):return g
    if g and g.library:g=g.copy();g.name=name+'_v08'
    if g:g.nodes.clear()
    else:g=bpy.data.node_groups.new(name,'GeometryNodeTree')
    g['wb_schema']=18
    socket(g,'Geometry','INPUT','NodeSocketGeometry')
    stage_socket=socket(g,'Evaluation stage','INPUT','NodeSocketInt',0)
    if hasattr(stage_socket,'hide_in_modifier'):stage_socket.hide_in_modifier=True
    for n,k,d in [('Sidewalk panels','NodeSocketBool',False),('Slab length','NodeSocketFloat',1.5),('Slab width','NodeSocketFloat',1.5),('Joint gap','NodeSocketFloat',.003),('Flatten curb at crossing','NodeSocketBool',False),('Safe sidewalk offset','NodeSocketBool',False),('Grass surface','NodeSocketBool',False),('Terrain base','NodeSocketObject',None),('Vertex controls','NodeSocketObject',None),('Layer prefix','NodeSocketString',''),('Use vertex controls','NodeSocketBool',False),('Use layer order','NodeSocketBool',False),('Junction cleanup','NodeSocketBool',True),('Precise viewport cleanup','NodeSocketBool',False),('Editing preview','NodeSocketBool',False),('Road surfaces','NodeSocketCollection',None),('Enabled','NodeSocketBool',True),('Road','NodeSocketObject',None),('Profile curve','NodeSocketObject',None),('Path curve','NodeSocketObject',None),('Use custom path','NodeSocketBool',False),('Profile width scale','NodeSocketFloat',1.),('Profile height scale','NodeSocketFloat',1.),('Setback','NodeSocketFloat',0.),('Height offset','NodeSocketFloat',0.),('Crosswalk areas','NodeSocketObject',None),('Crossing road','NodeSocketObject',None),('Lower at crossing','NodeSocketBool',False),('Transition length','NodeSocketFloat',3.),('Material','NodeSocketMaterial',None)]:
        item=socket(g,n,'INPUT',k,d)
        if n in ('Slab length','Slab width'):item.min_value=.5;item.max_value=6
        if n=='Joint gap':item.min_value=.001;item.max_value=.02
        if n in ('Profile width scale','Profile height scale','Transition length'):item.min_value=.01
    socket(g,'Geometry','OUTPUT','NodeSocketGeometry')
    N=g.nodes;L=g.links;inp=N.new('NodeGroupInput');out=N.new('NodeGroupOutput')
    road=N.new('GeometryNodeObjectInfo');road.transform_space='RELATIVE';L.new(inp.outputs['Road'],road.inputs['Object'])
    attr=N.new('GeometryNodeInputNamedAttribute');attr.data_type='INT';attr.inputs['Name'].default_value='parts'
    test=N.new('FunctionNodeCompare');test.data_type='INT';test.operation='EQUAL';integer_operand(test,'B').default_value=7;L.new(attr.outputs['Attribute'],integer_operand(test,'A'))
    border=N.new('GeometryNodeSeparateGeometry');border.domain='POINT';L.new(road.outputs['Geometry'],border.inputs['Geometry']);L.new(test.outputs['Result'],border.inputs['Selection'])
    path=N.new('GeometryNodeObjectInfo');path.transform_space='RELATIVE';L.new(inp.outputs['Path curve'],path.inputs['Object'])
    choose_path=N.new('GeometryNodeSwitch');choose_path.input_type='GEOMETRY';L.new(inp.outputs['Use custom path'],choose_path.inputs['Switch']);L.new(border.outputs['Selection'],choose_path.inputs['False']);L.new(path.outputs['Geometry'],choose_path.inputs['True'])
    # Keep pavement polygon corners when spacing the sweep. Uniform resampling
    # cuts across them and produces alternating inward offsets on tight arcs.
    path_position=N.new('GeometryNodeInputPosition');path_index=N.new('GeometryNodeInputIndex')
    next_index=N.new('GeometryNodeOffsetPointInCurve');next_index.inputs['Offset'].default_value=1;L.new(path_index.outputs['Index'],next_index.inputs['Point Index'])
    path_next=N.new('GeometryNodeSampleIndex');path_next.data_type='FLOAT_VECTOR';path_next.domain='POINT';L.new(choose_path.outputs['Output'],path_next.inputs['Geometry']);L.new(path_position.outputs['Position'],path_next.inputs['Value']);L.new(next_index.outputs['Point Index'],path_next.inputs['Index'])
    path_length=N.new('ShaderNodeVectorMath');path_length.operation='DISTANCE';L.new(path_position.outputs['Position'],path_length.inputs[0]);L.new(path_next.outputs['Value'],path_length.inputs[1])
    path_cuts=N.new('ShaderNodeMath');path_cuts.operation='DIVIDE';path_cuts.inputs[1].default_value=.25;L.new(path_length.outputs['Value'],path_cuts.inputs[0])
    cut_count=N.new('ShaderNodeMath');cut_count.operation='FLOOR';L.new(path_cuts.outputs[0],cut_count.inputs[0])
    subdivided=N.new('GeometryNodeSubdivideCurve');L.new(choose_path.outputs['Output'],subdivided.inputs['Curve']);L.new(cut_count.outputs[0],subdivided.inputs['Cuts'])
    # A polyline offset uses the angle bisector and its miter length. A unit
    # normal alone pulls every original arc knot inward by a different amount.
    directions=[]
    for step in (-1,1):
        neighbor=N.new('GeometryNodeOffsetPointInCurve');neighbor.inputs['Offset'].default_value=step;L.new(path_index.outputs['Index'],neighbor.inputs['Point Index'])
        sample=N.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';L.new(subdivided.outputs['Curve'],sample.inputs['Geometry']);L.new(path_position.outputs['Position'],sample.inputs['Value']);L.new(neighbor.outputs['Point Index'],sample.inputs['Index'])
        delta=N.new('ShaderNodeVectorMath');delta.operation='SUBTRACT';L.new(path_position.outputs['Position'] if step<0 else sample.outputs['Value'],delta.inputs[0]);L.new(sample.outputs['Value'] if step<0 else path_position.outputs['Position'],delta.inputs[1])
        flat=N.new('ShaderNodeVectorMath');flat.operation='MULTIPLY';flat.inputs[1].default_value=(1,1,0);L.new(delta.outputs['Vector'],flat.inputs[0])
        unit=N.new('ShaderNodeVectorMath');unit.operation='NORMALIZE';L.new(flat.outputs['Vector'],unit.inputs[0]);directions.append(unit.outputs['Vector'])
    dot=N.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';L.new(directions[0],dot.inputs[0]);L.new(directions[1],dot.inputs[1])
    half=N.new('ShaderNodeMath');half.operation='MULTIPLY_ADD';half.inputs[1].default_value=.5;half.inputs[2].default_value=.5;L.new(dot.outputs['Value'],half.inputs[0])
    safe_cos=N.new('ShaderNodeMath');safe_cos.operation='MAXIMUM';safe_cos.inputs[1].default_value=.04;L.new(half.outputs[0],safe_cos.inputs[0])
    cosine=N.new('ShaderNodeMath');cosine.operation='SQRT';L.new(safe_cos.outputs[0],cosine.inputs[0])
    reciprocal=N.new('ShaderNodeMath');reciprocal.operation='DIVIDE';reciprocal.inputs[0].default_value=1;L.new(cosine.outputs[0],reciprocal.inputs[1])
    miter_store=N.new('GeometryNodeStoreNamedAttribute');miter_store.data_type='FLOAT';miter_store.domain='POINT';miter_store.inputs['Name'].default_value='roadlab_offset_miter';L.new(subdivided.outputs['Curve'],miter_store.inputs['Geometry']);L.new(reciprocal.outputs[0],miter_store.inputs['Value'])
    edge_position=N.new('GeometryNodeInputPosition');edge_z=N.new('ShaderNodeSeparateXYZ');L.new(edge_position.outputs['Position'],edge_z.inputs['Vector'])
    edge_store=N.new('GeometryNodeStoreNamedAttribute');edge_store.data_type='FLOAT';edge_store.domain='POINT';edge_store.inputs['Name'].default_value='wb_edge_elevation';L.new(edge_z.outputs['Z'],edge_store.inputs['Value']);L.new(miter_store.outputs['Geometry'],edge_store.inputs['Geometry'])
    # Subdivision interpolates a Free normal across sharp polygon corners.
    # Recompute the frame from actual neighboring edge directions instead.
    tangent_sum=N.new('ShaderNodeVectorMath');tangent_sum.operation='ADD';L.new(directions[0],tangent_sum.inputs[0]);L.new(directions[1],tangent_sum.inputs[1])
    unit_tangent=N.new('ShaderNodeVectorMath');unit_tangent.operation='NORMALIZE';L.new(tangent_sum.outputs['Vector'],unit_tangent.inputs[0])
    source_normal=N.new('ShaderNodeVectorMath');source_normal.operation='CROSS_PRODUCT';source_normal.inputs[1].default_value=(0,0,1);L.new(unit_tangent.outputs['Vector'],source_normal.inputs[0])
    normal_store=N.new('GeometryNodeStoreNamedAttribute');normal_store.data_type='FLOAT_VECTOR';normal_store.domain='POINT';normal_store.inputs['Name'].default_value='wb_edge_normal';L.new(edge_store.outputs['Geometry'],normal_store.inputs['Geometry']);L.new(source_normal.outputs['Vector'],normal_store.inputs['Value'])
    position_store=N.new('GeometryNodeStoreNamedAttribute');position_store.data_type='FLOAT_VECTOR';position_store.domain='POINT';position_store.inputs['Name'].default_value='wb_edge_position';L.new(normal_store.outputs['Geometry'],position_store.inputs['Geometry']);L.new(edge_position.outputs['Position'],position_store.inputs['Value'])
    source_tangent=N.new('GeometryNodeInputTangent');tangent_store=N.new('GeometryNodeStoreNamedAttribute');tangent_store.data_type='FLOAT_VECTOR';tangent_store.domain='POINT';tangent_store.inputs['Name'].default_value='wb_edge_tangent';L.new(position_store.outputs['Geometry'],tangent_store.inputs['Geometry']);L.new(source_tangent.outputs['Tangent'],tangent_store.inputs['Value'])
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
    profile_heights=N.new('GeometryNodeStoreNamedAttribute');profile_heights.data_type='FLOAT';profile_heights.domain='POINT';profile_heights.inputs['Name'].default_value='wb_profile_y';L.new(profile_values.outputs['Geometry'],profile_heights.inputs['Geometry']);L.new(profile_xyz.outputs['Y'],profile_heights.inputs['Value'])
    profile_depth=N.new('GeometryNodeStoreNamedAttribute');profile_depth.data_type='FLOAT';profile_depth.domain='POINT';profile_depth.inputs['Name'].default_value='wb_profile_z';L.new(profile_heights.outputs['Geometry'],profile_depth.inputs['Geometry']);L.new(profile_xyz.outputs['Z'],profile_depth.inputs['Value'])
    profile_us=N.new('GeometryNodeStoreNamedAttribute');profile_us.data_type='FLOAT';profile_us.domain='POINT';profile_us.inputs['Name'].default_value='wb_profile_u';L.new(profile_depth.outputs['Geometry'],profile_us.inputs['Geometry']);L.new(profile_u.outputs['Result'],profile_us.inputs['Value'])
    orient=N.new('GeometryNodeTransform');L.new(scale.outputs['Vector'],orient.inputs['Scale']);L.new(shift.outputs['Vector'],orient.inputs['Translation']);L.new(profile_us.outputs['Geometry'],orient.inputs['Geometry'])
    # Add width samples only when a crossing needs a ramp/landing break. Original
    # profile corners are retained; the rest of the road keeps its usual cost.
    profile_index=N.new('GeometryNodeInputIndex');next_profile=N.new('GeometryNodeOffsetPointInCurve');next_profile.inputs['Offset'].default_value=1;L.new(profile_index.outputs['Index'],next_profile.inputs['Point Index'])
    next_position=N.new('GeometryNodeSampleIndex');next_position.data_type='FLOAT_VECTOR';next_position.domain='POINT';L.new(orient.outputs['Geometry'],next_position.inputs['Geometry']);L.new(profile_x.outputs['Position'],next_position.inputs['Value']);L.new(next_profile.outputs['Point Index'],next_position.inputs['Index'])
    profile_distance=N.new('ShaderNodeVectorMath');profile_distance.operation='DISTANCE';L.new(profile_x.outputs['Position'],profile_distance.inputs[0]);L.new(next_position.outputs['Value'],profile_distance.inputs[1])
    profile_cuts=N.new('ShaderNodeMath');profile_cuts.operation='DIVIDE';profile_cuts.inputs[1].default_value=.2;L.new(profile_distance.outputs['Value'],profile_cuts.inputs[0])
    rounded_cuts=N.new('ShaderNodeMath');rounded_cuts.operation='FLOOR';L.new(profile_cuts.outputs[0],rounded_cuts.inputs[0])
    divided_profile=N.new('GeometryNodeSubdivideCurve');L.new(orient.outputs['Geometry'],divided_profile.inputs['Curve']);L.new(rounded_cuts.outputs[0],divided_profile.inputs['Cuts'])
    use_divided_profile=N.new('GeometryNodeSwitch');use_divided_profile.input_type='GEOMETRY';L.new(orient.outputs['Geometry'],use_divided_profile.inputs['False']);L.new(divided_profile.outputs['Curve'],use_divided_profile.inputs['True'])
    sweep=N.new('GeometryNodeCurveToMesh');sweep.inputs['Fill Caps'].default_value=True;L.new(position_store.outputs['Geometry'],sweep.inputs['Curve']);L.new(use_divided_profile.outputs['Output'],sweep.inputs['Profile Curve'])
    # Read per-control-point data from the shared raw curve, never from radius/tilt.
    controls=N.new('GeometryNodeObjectInfo');controls.transform_space='RELATIVE';L.new(inp.outputs['Vertex controls'],controls.inputs['Object'])
    edge_pos_attr=N.new('GeometryNodeInputNamedAttribute');edge_pos_attr.data_type='FLOAT_VECTOR';edge_pos_attr.inputs['Name'].default_value='wb_edge_position'
    nearest=N.new('GeometryNodeSampleNearest');nearest.domain='POINT';L.new(controls.outputs['Geometry'],nearest.inputs['Geometry']);L.new(edge_pos_attr.outputs['Attribute'],nearest.inputs['Sample Position'])
    fields={};control_fields={}
    for key in ('enabled','width','offset','zpos','stack'):
        text=N.new('GeometryNodeStringJoin');text.inputs['Delimiter'].default_value='';suffix=N.new('FunctionNodeInputString');suffix.string=key;L.new(suffix.outputs['String'],text.inputs['Strings']);L.new(inp.outputs['Layer prefix'],text.inputs['Strings'])
        attr_field=N.new('GeometryNodeInputNamedAttribute');attr_field.data_type='FLOAT';L.new(text.outputs['String'],attr_field.inputs['Name'])
        control_fields[key]=attr_field.outputs['Attribute']
        value=N.new('GeometryNodeSampleIndex');value.data_type='FLOAT';value.domain='POINT';L.new(controls.outputs['Geometry'],value.inputs['Geometry']);L.new(attr_field.outputs['Attribute'],value.inputs['Value']);L.new(nearest.outputs['Index'],value.inputs['Index']);fields[key]=value.outputs['Value']
    # Delete mesh edges to create connected enabled runs, capped only at real gaps.
    from . import sidewalk_panels
    columns_enabled=N.new('FunctionNodeBooleanMath');columns_enabled.operation='AND';L.new(inp.outputs['Sidewalk panels'],columns_enabled.inputs[0]);L.new(inp.outputs['Use vertex controls'],columns_enabled.inputs[1])
    column_profile=sidewalk_panels.columns(g,profile_us.outputs['Geometry'],controls.outputs['Geometry'],control_fields['width'],columns_enabled.outputs[0],inp.outputs['Slab width'],inp.outputs['Joint gap'])
    L.new(column_profile,orient.inputs['Geometry'])
    panel_path=sidewalk_panels.prepare(g,tangent_store.outputs['Geometry'])
    wire=N.new('GeometryNodeCurveToMesh');L.new(panel_path,wire.inputs['Curve'])
    disabled=N.new('ShaderNodeMath');disabled.operation='LESS_THAN';disabled.inputs[1].default_value=.5;L.new(fields['enabled'],disabled.inputs[0])
    delete_edges=N.new('GeometryNodeDeleteGeometry');delete_edges.domain='EDGE';L.new(wire.outputs['Mesh'],delete_edges.inputs['Geometry']);active_disabled=N.new('FunctionNodeBooleanMath');active_disabled.operation='AND';L.new(disabled.outputs[0],active_disabled.inputs[0]);L.new(inp.outputs['Use vertex controls'],active_disabled.inputs[1]);L.new(active_disabled.outputs[0],delete_edges.inputs['Selection'])
    panel_curves=sidewalk_panels.curves(g,delete_edges.outputs['Geometry'],inp.outputs['Sidewalk panels'],inp.outputs['Slab length'],inp.outputs['Joint gap'])
    normal_attr=N.new('GeometryNodeInputNamedAttribute');normal_attr.data_type='FLOAT_VECTOR';normal_attr.inputs['Name'].default_value='wb_edge_normal'
    segment_normals=N.new('GeometryNodeSetCurveNormal');segment_normals.inputs['Mode'].default_value='Free';L.new(panel_curves,segment_normals.inputs['Curve']);L.new(normal_attr.outputs['Attribute'],segment_normals.inputs['Normal'])
    masked_sweep=N.new('GeometryNodeCurveToMesh');masked_sweep.inputs['Fill Caps'].default_value=True;L.new(segment_normals.outputs['Curve'],masked_sweep.inputs['Curve']);L.new(use_divided_profile.outputs['Output'],masked_sweep.inputs['Profile Curve'])
    choose_sweep=N.new('GeometryNodeSwitch');choose_sweep.input_type='GEOMETRY';use_segment_sweep=N.new('FunctionNodeBooleanMath');use_segment_sweep.operation='OR';L.new(inp.outputs['Use vertex controls'],use_segment_sweep.inputs[0]);L.new(inp.outputs['Sidewalk panels'],use_segment_sweep.inputs[1]);L.new(use_segment_sweep.outputs[0],choose_sweep.inputs['Switch']);L.new(sweep.outputs['Mesh'],choose_sweep.inputs['False']);L.new(masked_sweep.outputs['Mesh'],choose_sweep.inputs['True'])
    u_attr=N.new('GeometryNodeInputNamedAttribute');u_attr.data_type='FLOAT';u_attr.inputs['Name'].default_value='wb_profile_u'
    x_attr=N.new('GeometryNodeInputNamedAttribute');x_attr.data_type='FLOAT';x_attr.inputs['Name'].default_value='wb_profile_x'
    width_product=N.new('ShaderNodeMath');width_product.operation='MULTIPLY';L.new(fields['width'],width_product.inputs[0]);L.new(inp.outputs['Profile width scale'],width_product.inputs[1])
    desired_x=N.new('ShaderNodeMath');desired_x.operation='MULTIPLY';L.new(u_attr.outputs['Attribute'],desired_x.inputs[0]);L.new(fields['width'],desired_x.inputs[1])
    stack_choice=N.new('GeometryNodeSwitch');stack_choice.input_type='FLOAT';L.new(inp.outputs['Use layer order'],stack_choice.inputs['Switch']);L.new(fields['stack'],stack_choice.inputs['True'])
    wanted_offset=N.new('ShaderNodeMath');wanted_offset.operation='ADD';L.new(stack_choice.outputs['Output'],wanted_offset.inputs[0]);L.new(fields['offset'],wanted_offset.inputs[1])
    wanted=N.new('ShaderNodeMath');wanted.operation='ADD';L.new(desired_x.outputs[0],wanted.inputs[0]);L.new(wanted_offset.outputs[0],wanted.inputs[1])
    old_x=N.new('ShaderNodeMath');old_x.operation='MULTIPLY';L.new(x_attr.outputs['Attribute'],old_x.inputs[0]);L.new(inp.outputs['Profile width scale'],old_x.inputs[1])
    offset_limit=N.new('GeometryNodeInputNamedAttribute');offset_limit.data_type='FLOAT';offset_limit.inputs['Name'].default_value='roadlab_offset_limit'
    active_guard=N.new('FunctionNodeBooleanMath');active_guard.operation='AND';L.new(inp.outputs['Safe sidewalk offset'],active_guard.inputs[0]);L.new(offset_limit.outputs['Exists'],active_guard.inputs[1])
    maximum=N.new('GeometryNodeSwitch');maximum.input_type='FLOAT';maximum.inputs['False'].default_value=1e6;L.new(active_guard.outputs[0],maximum.inputs['Switch']);L.new(offset_limit.outputs['Attribute'],maximum.inputs['True'])
    safe_x=N.new('ShaderNodeMath');safe_x.operation='MINIMUM';L.new(wanted.outputs[0],safe_x.inputs[0]);L.new(maximum.outputs[0],safe_x.inputs[1]);safe_x.label='Taper sidewalk before an inward offset folds'
    miter_attr=N.new('GeometryNodeInputNamedAttribute');miter_attr.data_type='FLOAT';miter_attr.inputs['Name'].default_value='roadlab_offset_miter'
    miter_x=N.new('ShaderNodeMath');miter_x.operation='MULTIPLY';L.new(safe_x.outputs[0],miter_x.inputs[0]);L.new(miter_attr.outputs['Attribute'],miter_x.inputs[1])
    x_delta=N.new('ShaderNodeMath');x_delta.operation='SUBTRACT';L.new(miter_x.outputs[0],x_delta.inputs[0]);L.new(old_x.outputs[0],x_delta.inputs[1])
    # Construct from the original border frame, not the frame of a split panel.
    # MeshToCurve can reverse a run, and its endpoint tangent can change a miter.
    x_vector=N.new('ShaderNodeVectorMath');x_vector.operation='SCALE';L.new(normal_attr.outputs['Attribute'],x_vector.inputs[0]);L.new(miter_x.outputs[0],x_vector.inputs['Scale'])
    y_attr=N.new('GeometryNodeInputNamedAttribute');y_attr.data_type='FLOAT';y_attr.inputs['Name'].default_value='wb_profile_y'
    profile_height=N.new('ShaderNodeMath');profile_height.operation='MULTIPLY_ADD';L.new(y_attr.outputs['Attribute'],profile_height.inputs[0]);L.new(inp.outputs['Profile height scale'],profile_height.inputs[1]);L.new(inp.outputs['Height offset'],profile_height.inputs[2])
    final_height=N.new('ShaderNodeMath');final_height.operation='ADD';L.new(profile_height.outputs[0],final_height.inputs[0]);L.new(fields['zpos'],final_height.inputs[1])
    z_vector=N.new('ShaderNodeCombineXYZ');L.new(final_height.outputs[0],z_vector.inputs['Z'])
    edge_tangent=N.new('GeometryNodeInputNamedAttribute');edge_tangent.data_type='FLOAT_VECTOR';edge_tangent.inputs['Name'].default_value='wb_edge_tangent'
    z_attr=N.new('GeometryNodeInputNamedAttribute');z_attr.data_type='FLOAT';z_attr.inputs['Name'].default_value='wb_profile_z'
    depth_vector=N.new('ShaderNodeVectorMath');depth_vector.operation='SCALE';L.new(edge_tangent.outputs['Attribute'],depth_vector.inputs[0]);L.new(z_attr.outputs['Attribute'],depth_vector.inputs['Scale'])
    base_position=N.new('ShaderNodeVectorMath');base_position.operation='ADD';L.new(edge_pos_attr.outputs['Attribute'],base_position.inputs[0]);L.new(x_vector.outputs['Vector'],base_position.inputs[1])
    height_position=N.new('ShaderNodeVectorMath');height_position.operation='ADD';L.new(base_position.outputs['Vector'],height_position.inputs[0]);L.new(z_vector.outputs['Vector'],height_position.inputs[1])
    final_position=N.new('ShaderNodeVectorMath');final_position.operation='ADD';L.new(height_position.outputs['Vector'],final_position.inputs[0]);L.new(depth_vector.outputs['Vector'],final_position.inputs[1])
    current_position=N.new('GeometryNodeInputPosition');vertex_offset=N.new('ShaderNodeVectorMath');vertex_offset.operation='SUBTRACT';L.new(final_position.outputs['Vector'],vertex_offset.inputs[0]);L.new(current_position.outputs['Position'],vertex_offset.inputs[1])
    vertex_switch=N.new('GeometryNodeSwitch');vertex_switch.input_type='VECTOR';L.new(inp.outputs['Use vertex controls'],vertex_switch.inputs['Switch']);L.new(vertex_offset.outputs['Vector'],vertex_switch.inputs['True'])
    vertex_shape=N.new('GeometryNodeSetPosition');L.new(choose_sweep.outputs['Output'],vertex_shape.inputs['Geometry']);L.new(vertex_switch.outputs['Output'],vertex_shape.inputs['Offset'])
    no_room=N.new('ShaderNodeMath');no_room.operation='GREATER_THAN';L.new(wanted_offset.outputs[0],no_room.inputs[0]);L.new(maximum.outputs[0],no_room.inputs[1])
    cannot_fit=N.new('FunctionNodeBooleanMath');cannot_fit.operation='OR';L.new(disabled.outputs[0],cannot_fit.inputs[0]);L.new(no_room.outputs[0],cannot_fit.inputs[1]);L.new(cannot_fit.outputs[0],delete_edges.inputs['Selection'])
    profile_position=N.new('GeometryNodeInputPosition');max_profile=N.new('ShaderNodeSeparateXYZ');L.new(profile_position.outputs['Position'],max_profile.inputs['Vector'])
    heights=N.new('GeometryNodeAttributeStatistic');heights.data_type='FLOAT';heights.domain='POINT';L.new(profile.outputs['Geometry'],heights.inputs['Geometry']);L.new(max_profile.outputs['Y'],heights.inputs['Attribute'])
    top_height=N.new('ShaderNodeMath');top_height.operation='MULTIPLY';L.new(heights.outputs['Max'],top_height.inputs[0]);L.new(inp.outputs['Profile height scale'],top_height.inputs[1])
    top_offset=N.new('ShaderNodeMath');top_offset.operation='ADD';L.new(top_height.outputs[0],top_offset.inputs[0]);L.new(inp.outputs['Height offset'],top_offset.inputs[1])
    edge_attr=N.new('GeometryNodeInputNamedAttribute');edge_attr.data_type='FLOAT';edge_attr.inputs['Name'].default_value='wb_edge_elevation'
    top_reference=N.new('ShaderNodeMath');top_reference.operation='ADD';L.new(edge_attr.outputs['Attribute'],top_reference.inputs[0]);L.new(top_offset.outputs[0],top_reference.inputs[1]);vertex_top=N.new('ShaderNodeMath');vertex_top.operation='ADD';L.new(top_reference.outputs[0],vertex_top.inputs[0]);L.new(fields['zpos'],vertex_top.inputs[1])
    cross=N.new('GeometryNodeObjectInfo');cross.transform_space='RELATIVE';L.new(inp.outputs['Crossing road'],cross.inputs['Object'])
    position=N.new('GeometryNodeInputPosition');split=N.new('ShaderNodeSeparateXYZ');L.new(position.outputs['Position'],split.inputs['Vector'])
    # Crosswalk weight is 1 at the curb and 0 at the back of its ramp.
    # Existing road-crossing lowering remains independently controlled.
    cross_weight=N.new('GeometryNodeStoreNamedAttribute');cross_weight.data_type='FLOAT';cross_weight.domain='POINT';cross_weight.inputs['Name'].default_value='roadlab_crossing_weight';cross_weight.inputs['Value'].default_value=1;L.new(cross.outputs['Geometry'],cross_weight.inputs['Geometry'])
    use_cross=N.new('GeometryNodeSwitch');use_cross.input_type='GEOMETRY';L.new(inp.outputs['Lower at crossing'],use_cross.inputs['Switch']);L.new(cross_weight.outputs['Geometry'],use_cross.inputs['True'])
    crosswalk=N.new('GeometryNodeObjectInfo');crosswalk.transform_space='RELATIVE';L.new(inp.outputs['Crosswalk areas'],crosswalk.inputs['Object'])
    crossing_geometry=N.new('GeometryNodeJoinGeometry');L.new(use_cross.outputs['Output'],crossing_geometry.inputs['Geometry']);L.new(crosswalk.outputs['Geometry'],crossing_geometry.inputs['Geometry'])
    cross_size=N.new('GeometryNodeAttributeDomainSize');cross_size.component='MESH';L.new(crosswalk.outputs['Geometry'],cross_size.inputs['Geometry'])
    has_crosswalk=N.new('ShaderNodeMath');has_crosswalk.operation='GREATER_THAN';L.new(cross_size.outputs['Face Count'],has_crosswalk.inputs[0]);L.new(has_crosswalk.outputs[0],use_divided_profile.inputs['Switch'])
    # Most concrete blocks do not need width samples for a distant ramp.
    # Retain the dense cross-section only on panels that can reach a crossing.
    panel_proximity=N.new('GeometryNodeProximity');panel_proximity.target_element='FACES';L.new(crosswalk.outputs['Geometry'],panel_proximity.inputs['Geometry'])
    absolute_offset=N.new('ShaderNodeMath');absolute_offset.operation='ABSOLUTE';L.new(wanted_offset.outputs[0],absolute_offset.inputs[0])
    panel_reach=N.new('ShaderNodeMath');panel_reach.operation='ADD';L.new(width_product.outputs[0],panel_reach.inputs[0]);L.new(absolute_offset.outputs[0],panel_reach.inputs[1])
    panel_buffer=N.new('ShaderNodeMath');panel_buffer.operation='ADD';L.new(panel_reach.outputs[0],panel_buffer.inputs[0]);L.new(inp.outputs['Transition length'],panel_buffer.inputs[1])
    near_crossing=N.new('ShaderNodeMath');near_crossing.operation='LESS_THAN';L.new(panel_proximity.outputs['Distance'],near_crossing.inputs[0]);L.new(panel_buffer.outputs[0],near_crossing.inputs[1])
    panel_near=N.new('GeometryNodeFieldOnDomain');panel_near.data_type='FLOAT';panel_near.domain='CURVE';L.new(near_crossing.outputs[0],panel_near.inputs['Value'])
    any_near=N.new('ShaderNodeMath');any_near.operation='GREATER_THAN';L.new(panel_near.outputs['Value'],any_near.inputs[0]);any_near.inputs[1].default_value=0
    ramp_panels=N.new('FunctionNodeBooleanMath');ramp_panels.operation='AND';L.new(any_near.outputs[0],ramp_panels.inputs[0]);L.new(has_crosswalk.outputs[0],ramp_panels.inputs[1])
    separate_panels=N.new('GeometryNodeSeparateGeometry');separate_panels.domain='CURVE';L.new(segment_normals.outputs['Curve'],separate_panels.inputs['Geometry']);L.new(ramp_panels.outputs['Boolean'],separate_panels.inputs['Selection'])
    legacy_crossing=N.new('FunctionNodeBooleanMath');legacy_crossing.operation='OR';L.new(ramp_panels.outputs['Boolean'],legacy_crossing.inputs[0]);L.new(inp.outputs['Lower at crossing'],legacy_crossing.inputs[1]);L.new(legacy_crossing.outputs['Boolean'],separate_panels.inputs['Selection'])
    L.new(separate_panels.outputs['Inverted'],masked_sweep.inputs['Curve']);L.new(orient.outputs['Geometry'],masked_sweep.inputs['Profile Curve'])
    ramp_sweep=N.new('GeometryNodeCurveToMesh');ramp_sweep.inputs['Fill Caps'].default_value=True;L.new(separate_panels.outputs['Selection'],ramp_sweep.inputs['Curve']);L.new(divided_profile.outputs['Curve'],ramp_sweep.inputs['Profile Curve'])
    panel_sweeps=N.new('GeometryNodeJoinGeometry');L.new(masked_sweep.outputs['Mesh'],panel_sweeps.inputs['Geometry']);L.new(ramp_sweep.outputs['Mesh'],panel_sweeps.inputs['Geometry']);L.new(panel_sweeps.outputs['Geometry'],choose_sweep.inputs['True'])
    ramp_enabled=N.new('FunctionNodeBooleanMath');ramp_enabled.operation='OR';L.new(inp.outputs['Lower at crossing'],ramp_enabled.inputs[0]);L.new(has_crosswalk.outputs[0],ramp_enabled.inputs[1])
    crossing_attribute=N.new('GeometryNodeInputNamedAttribute');crossing_attribute.data_type='FLOAT';crossing_attribute.inputs['Name'].default_value='roadlab_crossing_weight'
    proximity=N.new('GeometryNodeProximity');proximity.target_element='FACES';L.new(crossing_geometry.outputs['Geometry'],proximity.inputs['Geometry'])
    closest=N.new('ShaderNodeSeparateXYZ');L.new(proximity.outputs['Position'],closest.inputs['Vector'])
    ramp=N.new('ShaderNodeMapRange');ramp.interpolation_type='SMOOTHERSTEP';ramp.clamp=True;ramp.inputs['From Min'].default_value=0;ramp.inputs['To Min'].default_value=1;ramp.inputs['To Max'].default_value=0;L.new(inp.outputs['Transition length'],ramp.inputs['From Max']);L.new(proximity.outputs['Distance'],ramp.inputs['Value'])
    origin=N.new('ShaderNodeVectorMath');origin.operation='ADD';origin.inputs[1].default_value=(0,0,1000);L.new(position.outputs['Position'],origin.inputs[0])
    ray=N.new('GeometryNodeRaycast');ray.data_type='FLOAT';ray.inputs['Ray Direction'].default_value=(0,0,-1);ray.inputs['Ray Length'].default_value=2000;L.new(crossing_geometry.outputs['Geometry'],ray.inputs['Target Geometry']);L.new(crossing_attribute.outputs['Attribute'],ray.inputs['Attribute']);L.new(origin.outputs['Vector'],ray.inputs['Source Position'])
    hit_z=N.new('ShaderNodeSeparateXYZ');L.new(ray.outputs['Hit Position'],hit_z.inputs['Vector'])
    target=N.new('GeometryNodeSwitch');target.input_type='FLOAT';L.new(ray.outputs['Is Hit'],target.inputs['Switch']);L.new(closest.outputs['Z'],target.inputs['False']);L.new(hit_z.outputs['Z'],target.inputs['True'])
    weight=N.new('GeometryNodeSwitch');weight.input_type='FLOAT';weight.inputs['True'].default_value=1;L.new(ray.outputs['Is Hit'],weight.inputs['Switch']);L.new(ramp.outputs['Result'],weight.inputs['False'])
    nearest_weight=N.new('GeometryNodeSampleNearestSurface');nearest_weight.data_type='FLOAT';L.new(crossing_geometry.outputs['Geometry'],nearest_weight.inputs['Mesh']);L.new(crossing_attribute.outputs['Attribute'],nearest_weight.inputs['Value']);L.new(position.outputs['Position'],nearest_weight.inputs['Sample Position'])
    sampled_weight=N.new('GeometryNodeSwitch');sampled_weight.input_type='FLOAT';L.new(ray.outputs['Is Hit'],sampled_weight.inputs['Switch']);L.new(ray.outputs['Attribute'],sampled_weight.inputs['True']);L.new(nearest_weight.outputs['Value'],sampled_weight.inputs['False'])
    full_weight=N.new('ShaderNodeMath');full_weight.operation='MULTIPLY';L.new(weight.outputs['Output'],full_weight.inputs[0]);L.new(sampled_weight.outputs['Output'],full_weight.inputs[1])
    enabled=N.new('GeometryNodeSwitch');enabled.input_type='FLOAT';enabled.inputs['False'].default_value=0;L.new(ramp_enabled.outputs['Boolean'],enabled.inputs['Switch']);L.new(full_weight.outputs[0],enabled.inputs['True'])
    difference=N.new('ShaderNodeMath');difference.operation='SUBTRACT';L.new(target.outputs['Output'],difference.inputs[0]);vertex_top_switch=N.new('GeometryNodeSwitch');vertex_top_switch.input_type='FLOAT';L.new(inp.outputs['Use vertex controls'],vertex_top_switch.inputs['Switch']);L.new(top_reference.outputs[0],vertex_top_switch.inputs['False']);L.new(vertex_top.outputs[0],vertex_top_switch.inputs['True']);L.new(vertex_top_switch.outputs['Output'],difference.inputs[1])
    lower=N.new('ShaderNodeMath');lower.operation='MINIMUM';lower.inputs[1].default_value=0;L.new(difference.outputs[0],lower.inputs[0])
    multiply=N.new('ShaderNodeMath');multiply.operation='MULTIPLY';L.new(lower.outputs[0],multiply.inputs[0]);L.new(enabled.outputs['Output'],multiply.inputs[1])
    curb_floor=N.new('ShaderNodeMath');curb_floor.operation='SUBTRACT';L.new(edge_attr.outputs['Attribute'],curb_floor.inputs[0]);L.new(split.outputs['Z'],curb_floor.inputs[1])
    below_base=N.new('ShaderNodeMath');below_base.operation='MINIMUM';below_base.inputs[1].default_value=0;L.new(curb_floor.outputs[0],below_base.inputs[0])
    curb_drop=N.new('ShaderNodeMath');curb_drop.operation='MAXIMUM';L.new(multiply.outputs[0],curb_drop.inputs[0]);L.new(below_base.outputs[0],curb_drop.inputs[1])
    curb_choice=N.new('GeometryNodeSwitch');curb_choice.input_type='FLOAT';L.new(inp.outputs['Flatten curb at crossing'],curb_choice.inputs['Switch']);L.new(multiply.outputs[0],curb_choice.inputs['False']);L.new(curb_drop.outputs[0],curb_choice.inputs['True'])
    offset=N.new('ShaderNodeCombineXYZ');L.new(curb_choice.outputs['Output'],offset.inputs['Z'])
    deform=N.new('GeometryNodeSetPosition');L.new(vertex_shape.outputs['Geometry'],deform.inputs['Geometry']);L.new(offset.outputs['Vector'],deform.inputs['Offset'])
    finishing=N.new('FunctionNodeCompare');finishing.data_type='INT';finishing.operation='EQUAL';L.new(inp.outputs['Evaluation stage'],integer_operand(finishing,'A'));integer_operand(finishing,'B').default_value=2
    staged=N.new('GeometryNodeSwitch');staged.input_type='GEOMETRY';L.new(finishing.outputs['Result'],staged.inputs['Switch']);L.new(deform.outputs['Geometry'],staged.inputs['False']);L.new(inp.outputs['Geometry'],staged.inputs['True'])
    # Resolve concave offset folds as one solid; never apply a modifier to a native road.
    union=N.new('GeometryNodeMeshBoolean');union.operation='UNION';union.solver='EXACT';union.inputs['Self Intersection'].default_value=True;L.new(staged.outputs['Output'],union.inputs['Mesh 2'])
    network=N.new('GeometryNodeCollectionInfo');network.transform_space='RELATIVE';L.new(inp.outputs['Road surfaces'],network.inputs['Collection'])
    realized=N.new('GeometryNodeRealizeInstances');L.new(network.outputs['Instances'],realized.inputs['Geometry'])
    network_size=N.new('GeometryNodeAttributeDomainSize');network_size.component='MESH';L.new(realized.outputs['Geometry'],network_size.inputs['Geometry']);network_exists=N.new('ShaderNodeMath');network_exists.operation='GREATER_THAN';L.new(network_size.outputs['Face Count'],network_exists.inputs[0])
    mesh_join=N.new('GeometryNodeSwitch');mesh_join.input_type='GEOMETRY';L.new(network_exists.outputs[0],mesh_join.inputs['Switch']);L.new(road.outputs['Geometry'],mesh_join.inputs['False']);L.new(realized.outputs['Geometry'],mesh_join.inputs['True'])
    road_part=N.new('FunctionNodeCompare');road_part.data_type='INT';road_part.operation='EQUAL';integer_operand(road_part,'B').default_value=1;L.new(attr.outputs['Attribute'],integer_operand(road_part,'A'))
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
    # Fast interactive solver; precise cleanup remains lazy until requested/rendered.
    fast_union=N.new('GeometryNodeMeshBoolean');fast_union.operation='UNION';fast_union.solver='MANIFOLD';L.new(staged.outputs['Output'],fast_union.inputs['Mesh 2'])
    fast_clip=N.new('GeometryNodeMeshBoolean');fast_clip.operation='DIFFERENCE';fast_clip.solver='MANIFOLD';L.new(fast_union.outputs['Mesh'],fast_clip.inputs['Mesh 1']);L.new(weld_cutter.outputs['Geometry'],fast_clip.inputs['Mesh 2'])
    # Manifold cleanup is valid only for closed input topology.
    input_neighbors=N.new('GeometryNodeInputMeshEdgeNeighbors');invalid_edge=N.new('FunctionNodeCompare');invalid_edge.data_type='INT';invalid_edge.operation='NOT_EQUAL';integer_operand(invalid_edge,'B').default_value=2;L.new(input_neighbors.outputs['Face Count'],integer_operand(invalid_edge,'A'))
    bad_counts=[]
    for mesh_source in (staged.outputs['Output'],weld_cutter.outputs['Geometry']):
        stats=N.new('GeometryNodeAttributeStatistic');stats.data_type='FLOAT';stats.domain='EDGE';L.new(mesh_source,stats.inputs['Geometry']);L.new(invalid_edge.outputs['Result'],stats.inputs['Attribute']);bad_counts.append(stats.outputs['Sum'])
    bad_sum=N.new('ShaderNodeMath');bad_sum.operation='ADD';L.new(bad_counts[0],bad_sum.inputs[0]);L.new(bad_counts[1],bad_sum.inputs[1]);bad_topology=N.new('ShaderNodeMath');bad_topology.operation='GREATER_THAN';L.new(bad_sum.outputs[0],bad_topology.inputs[0])
    viewport=N.new('GeometryNodeIsViewport');rendering=N.new('FunctionNodeBooleanMath');rendering.operation='NOT';L.new(viewport.outputs['Is Viewport'],rendering.inputs[0])
    precise=N.new('FunctionNodeBooleanMath');precise.operation='OR';L.new(rendering.outputs['Boolean'],precise.inputs[0]);L.new(inp.outputs['Precise viewport cleanup'],precise.inputs[1])
    fast_size=N.new('GeometryNodeAttributeDomainSize');fast_size.component='MESH';L.new(fast_clip.outputs['Mesh'],fast_size.inputs['Geometry']);fast_empty=N.new('ShaderNodeMath');fast_empty.operation='LESS_THAN';fast_empty.inputs[1].default_value=1;L.new(fast_size.outputs['Face Count'],fast_empty.inputs[0])
    fallback=N.new('GeometryNodeSwitch');fallback.input_type='GEOMETRY';L.new(fast_empty.outputs[0],fallback.inputs['Switch']);L.new(fast_clip.outputs['Mesh'],fallback.inputs['False']);L.new(clip.outputs['Mesh'],fallback.inputs['True'])
    quality=N.new('GeometryNodeSwitch');quality.input_type='GEOMETRY';guarded_precise=N.new('FunctionNodeBooleanMath');guarded_precise.operation='OR';L.new(precise.outputs['Boolean'],guarded_precise.inputs[0]);L.new(bad_topology.outputs[0],guarded_precise.inputs[1]);L.new(guarded_precise.outputs['Boolean'],quality.inputs['Switch']);L.new(fallback.outputs['Output'],quality.inputs['False']);L.new(clip.outputs['Mesh'],quality.inputs['True'])
    cleaned=N.new('GeometryNodeSwitch');cleaned.input_type='GEOMETRY';preview_only=N.new('FunctionNodeBooleanMath');preview_only.operation='AND';L.new(viewport.outputs['Is Viewport'],preview_only.inputs[0]);L.new(inp.outputs['Editing preview'],preview_only.inputs[1]);allow_cleanup=N.new('FunctionNodeBooleanMath');allow_cleanup.operation='NOT';L.new(preview_only.outputs['Boolean'],allow_cleanup.inputs[0]);explicit_review=N.new('FunctionNodeBooleanMath');explicit_review.operation='OR';L.new(allow_cleanup.outputs['Boolean'],explicit_review.inputs[0]);L.new(inp.outputs['Precise viewport cleanup'],explicit_review.inputs[1]);cleanup_requested=N.new('FunctionNodeBooleanMath');cleanup_requested.operation='AND';L.new(inp.outputs['Junction cleanup'],cleanup_requested.inputs[0]);L.new(explicit_review.outputs['Boolean'],cleanup_requested.inputs[1]);L.new(cleanup_requested.outputs['Boolean'],cleaned.inputs['Switch']);L.new(staged.outputs['Output'],cleaned.inputs['False']);L.new(quality.outputs['Output'],cleaned.inputs['True'])
    # Only the grass outer edge reaches the base terrain; profile-u blends its interior.
    terrain_info=N.new('GeometryNodeObjectInfo');terrain_info.transform_space='RELATIVE';L.new(inp.outputs['Terrain base'],terrain_info.inputs['Object'])
    terrain_ray=N.new('GeometryNodeRaycast');terrain_ray.data_type='FLOAT';terrain_ray.inputs['Ray Direction'].default_value=(0,0,-1);terrain_ray.inputs['Ray Length'].default_value=2000;L.new(terrain_info.outputs['Geometry'],terrain_ray.inputs['Target Geometry']);L.new(origin.outputs['Vector'],terrain_ray.inputs['Source Position'])
    terrain_height=N.new('ShaderNodeSeparateXYZ');L.new(terrain_ray.outputs['Hit Position'],terrain_height.inputs['Vector'])
    clearance=N.new('ShaderNodeMath');clearance.operation='ADD';clearance.inputs[1].default_value=.005;L.new(terrain_height.outputs['Z'],clearance.inputs[0])
    terrain_delta=N.new('ShaderNodeMath');terrain_delta.operation='SUBTRACT';L.new(clearance.outputs[0],terrain_delta.inputs[0]);L.new(split.outputs['Z'],terrain_delta.inputs[1])
    grass_u=N.new('GeometryNodeInputNamedAttribute');grass_u.data_type='FLOAT';grass_u.inputs['Name'].default_value='wb_profile_u'
    grass_blend=N.new('ShaderNodeMath');grass_blend.operation='MULTIPLY';L.new(terrain_delta.outputs[0],grass_blend.inputs[0]);L.new(grass_u.outputs['Attribute'],grass_blend.inputs[1])
    grass_hit=N.new('GeometryNodeSwitch');grass_hit.input_type='FLOAT';grass_hit.inputs['False'].default_value=0;L.new(terrain_ray.outputs['Is Hit'],grass_hit.inputs['Switch']);L.new(grass_blend.outputs[0],grass_hit.inputs['True'])
    grass_offset=N.new('ShaderNodeCombineXYZ');L.new(grass_hit.outputs['Output'],grass_offset.inputs['Z'])
    grass_deform=N.new('GeometryNodeSetPosition');L.new(staged.outputs['Output'],grass_deform.inputs['Geometry']);L.new(grass_offset.outputs['Vector'],grass_deform.inputs['Offset'])
    grass_road_ray=N.new('GeometryNodeRaycast');grass_road_ray.data_type='FLOAT';grass_road_ray.inputs['Ray Direction'].default_value=(0,0,-1);grass_road_ray.inputs['Ray Length'].default_value=2000;L.new(paved.outputs['Selection'],grass_road_ray.inputs['Target Geometry']);L.new(origin.outputs['Vector'],grass_road_ray.inputs['Source Position'])
    grass_clip=N.new('GeometryNodeDeleteGeometry');grass_clip.domain='FACE';L.new(grass_deform.outputs['Geometry'],grass_clip.inputs['Geometry']);L.new(grass_road_ray.outputs['Is Hit'],grass_clip.inputs['Selection'])
    surface_choice=N.new('GeometryNodeSwitch');surface_choice.input_type='GEOMETRY';L.new(inp.outputs['Grass surface'],surface_choice.inputs['Switch']);L.new(cleaned.outputs['Output'],surface_choice.inputs['False']);L.new(grass_clip.outputs['Geometry'],surface_choice.inputs['True'])
    mat=N.new('GeometryNodeSetMaterial');L.new(inp.outputs['Material'],mat.inputs['Material']);L.new(surface_choice.outputs['Output'],mat.inputs['Geometry'])
    flat_shading=N.new('GeometryNodeSetShadeSmooth');flat_shading.domain='FACE';flat_shading.inputs['Shade Smooth'].default_value=False;L.new(mat.outputs['Geometry'],flat_shading.inputs['Geometry'])
    # Native terrain receives tagged physical surfaces and their final boundary curves.
    surfaces=N.new('GeometryNodeStoreNamedAttribute');surfaces.data_type='INT';surfaces.domain='POINT';surfaces.inputs['Name'].default_value='parts';surfaces.inputs['Value'].default_value=1;L.new(flat_shading.outputs['Geometry'],surfaces.inputs['Geometry'])
    face_normal=N.new('GeometryNodeInputNormal');face_z=N.new('ShaderNodeSeparateXYZ');L.new(face_normal.outputs['Normal'],face_z.inputs['Vector'])
    face_up=N.new('ShaderNodeMath');face_up.operation='GREATER_THAN';face_up.inputs[1].default_value=.1;L.new(face_z.outputs['Z'],face_up.inputs[0])
    tops=N.new('GeometryNodeSeparateGeometry');tops.domain='FACE';L.new(surfaces.outputs['Geometry'],tops.inputs['Geometry']);L.new(face_up.outputs[0],tops.inputs['Selection'])
    neighbors=N.new('GeometryNodeInputMeshEdgeNeighbors');boundary=N.new('FunctionNodeCompare');boundary.data_type='INT';boundary.operation='EQUAL';integer_operand(boundary,'B').default_value=1;L.new(neighbors.outputs['Face Count'],integer_operand(boundary,'A'))
    rim=N.new('GeometryNodeMeshToCurve');L.new(tops.outputs['Selection'],rim.inputs['Mesh']);L.new(boundary.outputs['Result'],rim.inputs['Selection'])
    tagged_rim=N.new('GeometryNodeStoreNamedAttribute');tagged_rim.data_type='INT';tagged_rim.domain='POINT';tagged_rim.inputs['Name'].default_value='parts';tagged_rim.inputs['Value'].default_value=7;L.new(rim.outputs['Curve'],tagged_rim.inputs['Geometry'])
    rim_id=N.new('GeometryNodeStoreNamedAttribute');rim_id.data_type='INT';rim_id.domain='POINT';rim_id.inputs['Name'].default_value='edgeID';rim_id.inputs['Value'].default_value=0;L.new(tagged_rim.outputs['Geometry'],rim_id.inputs['Geometry'])
    final=N.new('GeometryNodeJoinGeometry');L.new(surfaces.outputs['Geometry'],final.inputs['Geometry']);L.new(rim_id.outputs['Geometry'],final.inputs['Geometry'])
    enabled_geometry=N.new('GeometryNodeSwitch');enabled_geometry.input_type='GEOMETRY';source_size=N.new('GeometryNodeAttributeDomainSize');source_size.component='MESH';L.new(staged.outputs['Output'],source_size.inputs['Geometry']);has_faces=N.new('ShaderNodeMath');has_faces.operation='GREATER_THAN';L.new(source_size.outputs['Face Count'],has_faces.inputs[0]);live=N.new('FunctionNodeBooleanMath');live.operation='AND';L.new(inp.outputs['Enabled'],live.inputs[0]);L.new(has_faces.outputs[0],live.inputs[1]);L.new(live.outputs['Boolean'],enabled_geometry.inputs['Switch']);L.new(final.outputs['Geometry'],enabled_geometry.inputs['True']);raw_only=N.new('FunctionNodeCompare');raw_only.data_type='INT';raw_only.operation='EQUAL';L.new(inp.outputs['Evaluation stage'],integer_operand(raw_only,'A'));integer_operand(raw_only,'B').default_value=1
    raw_enabled=N.new('GeometryNodeSwitch');raw_enabled.input_type='GEOMETRY';L.new(inp.outputs['Enabled'],raw_enabled.inputs['Switch']);L.new(deform.outputs['Geometry'],raw_enabled.inputs['True'])
    result_stage=N.new('GeometryNodeSwitch');result_stage.input_type='GEOMETRY';L.new(raw_only.outputs['Result'],result_stage.inputs['Switch']);L.new(enabled_geometry.outputs['Output'],result_stage.inputs['False']);L.new(raw_enabled.outputs['Output'],result_stage.inputs['True']);L.new(result_stage.outputs['Output'],out.inputs['Geometry'])
    layout=[(inp,(0,400)),(road,(280,400)),(attr,(280,0)),(test,(520,0)),(border,(760,400)),(path,(760,800)),(choose_path,(1000,400)),(edge_store,(1480,400)),(edge_position,(1000,0)),(edge_z,(1240,0)),(profile,(760,-500)),(negate,(760,-900)),(scale,(1000,-700)),(height_offset,(760,-1200)),(shift,(1000,-1100)),(orient,(1240,-500)),(sweep,(1720,400)),(profile_position,(1000,-1450)),(max_profile,(1240,-1450)),(heights,(1480,-800)),(top_height,(1720,-800)),(top_offset,(1960,-800)),(edge_attr,(1960,-1150)),(top_reference,(2200,-800)),(cross,(1960,1000)),(position,(1720,1450)),(split,(1960,1450)),(proximity,(2200,1000)),(closest,(2440,1000)),(ramp,(2440,600)),(origin,(1960,1800)),(ray,(2200,1800)),(hit_z,(2440,1800)),(target,(2680,1300)),(weight,(2680,600)),(enabled,(2920,600)),(difference,(2920,1300)),(lower,(3160,1300)),(multiply,(3400,1000)),(offset,(3640,1000)),(deform,(3880,400)),(mat,(4120,400)),(enabled_geometry,(4360,400)),(out,(4600,400))]
    for node,location in layout:node.location=location
    edge_store.label='Remember native road edge height';top_reference.label='Profile top elevation';lower.label='Lower only; leave elevated crossings clear';enabled_geometry.label='Optional extrusion'
    return g


def add_extrusion(scene,road,kind):
    if not road_modifier(road):raise ValueError('Choose an existing RoadLab road curve')
    from . import material
    collection=next((c for c in scene.collection.children if c.name.split('.')[0]=='ROADLAB_FEATURES'),None)
    if collection is None:collection=bpy.data.collections.new('ROADLAB_FEATURES');scene.collection.children.link(collection)
    profiles=next((c for c in scene.collection.children if c.name.split('.')[0]=='WB_EDITABLE_PROFILES'),None)
    if profiles is None:profiles=bpy.data.collections.new('WB_EDITABLE_PROFILES');scene.collection.children.link(profiles)
    coords={'curb':[(0,0),(.035,.1324),(.065,.1524),(.32,.1524),(.32,0)],'sidewalk':[(.32,.1524),(2.52,.1524),(2.52,-.0476),(.32,-.0476)],'grass':[(0,0),(1.2,0)]}[kind]
    curve=bpy.data.curves.new('WB_Profile_'+kind,'CURVE');curve.dimensions='2D';curve.fill_mode='NONE';spline=curve.splines.new('POLY');spline.points.add(len(coords)-1);spline.use_cyclic_u=kind!='grass'
    for p,(x,y) in zip(spline.points,coords):p.co=(x,y,0,1)
    profile=bpy.data.objects.new('WB_Profile_'+kind,curve);profiles.objects.link(profile);profile.hide_render=True;profile.hide_set(True);profile['wb_native_feature']='profile'
    if kind=='sidewalk':profile['roadlab_slab_foundation_upgraded']=True
    obj=bpy.data.objects.new('WB_'+kind+'_'+road.name,bpy.data.meshes.new('WB_'+kind));collection.objects.link(obj);obj['wb_native_feature']=kind
    mod=obj.modifiers.new('WB optional '+kind+' extrusion','NODES');mod.node_group=extrusion_group();set_input(mod,'Road',road);set_input(mod,'Profile curve',profile);set_input(mod,'Precise viewport cleanup',scene.wb_native.precise_cleanup);set_input(mod,'Material',material({'curb':'concrete','sidewalk':'sidewalk','grass':'grass'}[kind]));
    if kind=='curb':set_input(mod,'Flatten curb at crossing',True)
    if kind=='sidewalk':set_input(mod,'Safe sidewalk offset',True);set_input(mod,'Sidewalk panels',True);obj['roadlab_panels_upgraded']=True
    if kind=='grass':
        from .grass_surface import configure
        configure(scene,obj,mod)
    from .native_layers import add_layer
    add_layer(scene,road,obj,kind)
    from .native_contacts import connect_surfaces
    connect_surfaces(scene)
    if kind=='sidewalk':simplify_sidewalk(obj)
    return obj,profile


def simplify_sidewalk(obj):
    """Dissolve redundant coplanar panels; preserve real bends and ramp creases."""
    modifier=obj.modifiers.get('RoadLab Planar Slabs')
    if modifier is None:modifier=obj.modifiers.new('RoadLab Planar Slabs','DECIMATE')
    modifier.decimate_type='DISSOLVE';modifier.angle_limit=.00174533
    modifier.use_dissolve_boundaries=True;modifier.delimit={'MATERIAL','SEAM'}
    # Reduce straight panels before the expensive intersection cleanup.
    sweep=next((m for m in obj.modifiers if m.type=='NODES' and m.node_group and m.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION')),None)
    if sweep is None:return
    finish=obj.modifiers.get('RoadLab Surface Finish')
    if finish is None:
        finish=obj.modifiers.new('RoadLab Surface Finish','NODES');finish.node_group=sweep.node_group
        for item in sweep.node_group.interface.items_tree:
            if getattr(item,'in_out',None)=='INPUT' and hasattr(item,'default_value'):set_value(finish,item.identifier,get_value(sweep,item.identifier,item.default_value))
    obj['roadlab_staged_surface']=True
    set_input(sweep,'Evaluation stage',1);set_input(finish,'Evaluation stage',2)
    for target,index in ((sweep,0),(modifier,1),(finish,2)):
        at=obj.modifiers.find(target.name)
        if at!=index:obj.modifiers.move(at,index)
    sweep.show_expanded=False;finish.show_expanded=False


def upgrade_sidewalk_foundation(obj):
    """Only upgrade untouched stock profiles; preserve artist-authored profiles."""
    from .native_contacts import input_value
    for modifier in obj.modifiers:
        if modifier.type!='NODES' or not modifier.node_group or not modifier.node_group.name.startswith('WB_EXTENSION_BORDER_EXTRUSION'):continue
        profile=input_value(modifier,'Profile curve')
        if not profile or profile.get('roadlab_slab_foundation_upgraded'):continue
        splines=profile.data.splines
        stock=[(.32,.1524),(2.52,.1524),(2.52,.0524),(.32,.0524)]
        if len(splines)==1 and splines[0].type=='POLY' and len(splines[0].points)==4 and all(abs(p.co.x-x)<1e-6 and abs(p.co.y-y)<1e-6 for p,(x,y) in zip(splines[0].points,stock)):
            for p in list(splines[0].points)[2:]:p.co.y=-.0476
            profile.data.update_tag()
        profile['roadlab_slab_foundation_upgraded']=True
