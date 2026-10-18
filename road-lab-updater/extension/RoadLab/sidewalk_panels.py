"""Separate capped concrete panels along the actual pavement perimeter."""
def prepare(group,geometry):
    N,L=group.nodes,group.links
    # Slab identity belongs to the map footprint, not the growing 3D arc
    # length of a sculpted hill. Keep height in its existing border attribute.
    position=N.new('GeometryNodeInputPosition')
    xy=N.new('ShaderNodeVectorMath');xy.operation='MULTIPLY';xy.inputs[1].default_value=(1,1,0);L.new(position.outputs['Position'],xy.inputs[0])
    flat=N.new('GeometryNodeSetPosition');L.new(geometry,flat.inputs['Geometry']);L.new(xy.outputs['Vector'],flat.inputs['Position']);geometry=flat.outputs['Geometry']
    parameter=N.new('GeometryNodeSplineParameter')
    length=N.new('GeometryNodeSplineLength')
    index=N.new('GeometryNodeInputIndex')
    for name,domain,value in [('roadlab_panel_loop','CURVE',index.outputs['Index']),('roadlab_panel_factor','POINT',parameter.outputs['Factor']),('roadlab_panel_length','POINT',length.outputs['Length'])]:
        store=N.new('GeometryNodeStoreNamedAttribute');store.domain=domain;store.data_type='FLOAT';store.inputs['Name'].default_value=name;L.new(geometry,store.inputs['Geometry']);L.new(value,store.inputs['Value']);geometry=store.outputs['Geometry']
    original=N.new('GeometryNodeInputNamedAttribute');original.data_type='FLOAT_VECTOR';original.inputs['Name'].default_value='wb_edge_position'
    restore=N.new('GeometryNodeSetPosition');L.new(geometry,restore.inputs['Geometry']);L.new(original.outputs['Attribute'],restore.inputs['Position'])
    return restore.outputs['Geometry']

def curves(group,wire,enabled,block_length,gap):
    N,L=group.nodes,group.links
    position=N.new('GeometryNodeInputPosition')
    xy=N.new('ShaderNodeVectorMath');xy.operation='MULTIPLY';xy.inputs[1].default_value=(1,1,0);L.new(position.outputs['Position'],xy.inputs[0])
    flat=N.new('GeometryNodeSetPosition');L.new(wire,flat.inputs['Geometry']);L.new(xy.outputs['Vector'],flat.inputs['Position']);wire=flat.outputs['Geometry']
    def math(op,a,b=None):
        n=N.new('ShaderNodeMath');n.operation=op
        for i,v in enumerate((a,b)):
            if v is not None:
                if hasattr(v,'node'):L.new(v,n.inputs[i])
                else:n.inputs[i].default_value=v
        return n.outputs[0]
    attrs={}
    for name in ('loop','factor','length'):
        n=N.new('GeometryNodeInputNamedAttribute');n.data_type='FLOAT';n.inputs['Name'].default_value='roadlab_panel_'+name;attrs[name]=n.outputs['Attribute']
    endpoints=N.new('GeometryNodeInputMeshEdgeVertices')
    factors=[]
    for socket in ('Vertex Index 1','Vertex Index 2'):
        sample=N.new('GeometryNodeSampleIndex');sample.domain='POINT';sample.data_type='FLOAT';L.new(wire,sample.inputs['Geometry']);L.new(attrs['factor'],sample.inputs['Value']);L.new(endpoints.outputs[socket],sample.inputs['Index']);factors.append(sample.outputs['Value'])
    midpoint=math('MULTIPLY',math('ADD',*factors),.5)
    wrapped=math('GREATER_THAN',math('ABSOLUTE',math('SUBTRACT',*factors)),.5)
    choose=N.new('GeometryNodeSwitch');choose.input_type='FLOAT';L.new(wrapped,choose.inputs['Switch']);L.new(midpoint,choose.inputs['False']);choose.inputs['True'].default_value=.999999
    count=math('MAXIMUM',math('ROUND',math('DIVIDE',attrs['length'],block_length)),1.)
    panel=math('FLOOR',math('MULTIPLY',choose.outputs['Output'],count))
    group_id=math('ADD',math('MULTIPLY',attrs['loop'],1000000.),panel)
    split=N.new('GeometryNodeSplitToInstances');split.domain='EDGE';split.label='Separate concrete panels';L.new(wire,split.inputs['Geometry']);L.new(group_id,split.inputs['Group ID'])
    realize=N.new('GeometryNodeRealizeInstances');L.new(split.outputs['Instances'],realize.inputs['Geometry'])
    choice=N.new('GeometryNodeSwitch');choice.input_type='GEOMETRY';L.new(enabled,choice.inputs['Switch']);L.new(wire,choice.inputs['False']);L.new(realize.outputs['Geometry'],choice.inputs['True'])
    curve=N.new('GeometryNodeMeshToCurve');L.new(choice.outputs['Output'],curve.inputs['Mesh'])
    length_node=N.new('GeometryNodeSplineLength')
    half_gap=math('MULTIPLY',gap,.5)
    fraction=math('MINIMUM',math('DIVIDE',half_gap,length_node.outputs['Length']),.1)
    trim=N.new('GeometryNodeTrimCurve');trim.mode='FACTOR';L.new(curve.outputs['Curve'],trim.inputs['Curve']);L.new(fraction,trim.inputs['Start']);L.new(math('SUBTRACT',1.,fraction),trim.inputs['End'])
    select=N.new('GeometryNodeSwitch');select.input_type='GEOMETRY';L.new(enabled,select.inputs['Switch']);L.new(curve.outputs['Curve'],select.inputs['False']);L.new(trim.outputs['Curve'],select.inputs['True'])
    original=N.new('GeometryNodeInputNamedAttribute');original.data_type='FLOAT_VECTOR';original.inputs['Name'].default_value='wb_edge_tangent'
    tangent=N.new('GeometryNodeInputTangent');alignment=N.new('ShaderNodeVectorMath');alignment.operation='DOT_PRODUCT';L.new(original.outputs['Attribute'],alignment.inputs[0]);L.new(tangent.outputs['Tangent'],alignment.inputs[1])
    mean=N.new('GeometryNodeFieldOnDomain');mean.data_type='FLOAT';mean.domain='CURVE';L.new(alignment.outputs['Value'],mean.inputs['Value'])
    reverse=N.new('GeometryNodeReverseCurve');L.new(select.outputs['Output'],reverse.inputs['Curve']);L.new(math('LESS_THAN',mean.outputs['Value'],0.),reverse.inputs['Selection'])
    border=N.new('GeometryNodeInputNamedAttribute');border.data_type='FLOAT_VECTOR';border.inputs['Name'].default_value='wb_edge_position'
    restore=N.new('GeometryNodeSetPosition');L.new(reverse.outputs['Curve'],restore.inputs['Geometry']);L.new(border.outputs['Attribute'],restore.inputs['Position'])
    return restore.outputs['Geometry']

def columns(group,geometry,controls,width_attribute,enabled,slab_width,gap):
    N,L=group.nodes,group.links
    def math(op,a,b=None):
        n=N.new('ShaderNodeMath');n.operation=op
        for i,v in enumerate((a,b)):
            if v is not None:
                if hasattr(v,'node'):L.new(v,n.inputs[i])
                else:n.inputs[i].default_value=v
        return n.outputs[0]
    stats=N.new('GeometryNodeAttributeStatistic');stats.data_type='FLOAT';stats.domain='POINT';L.new(controls,stats.inputs['Geometry']);L.new(width_attribute,stats.inputs['Attribute'])
    width=math('MAXIMUM',stats.outputs['Max'],.01)
    count=math('MAXIMUM',math('ROUND',math('DIVIDE',width,slab_width)),1.)
    choice=N.new('GeometryNodeSwitch');choice.input_type='FLOAT';L.new(enabled,choice.inputs['Switch']);choice.inputs['False'].default_value=1;L.new(count,choice.inputs['True'])
    count=choice.outputs['Output']
    dup=N.new('GeometryNodeDuplicateElements');dup.domain='SPLINE';L.new(geometry,dup.inputs['Geometry']);L.new(count,dup.inputs['Amount'])
    u=N.new('GeometryNodeInputNamedAttribute');u.data_type='FLOAT';u.inputs['Name'].default_value='wb_profile_u'
    fraction=math('MINIMUM',math('DIVIDE',math('MULTIPLY',gap,count),width),.1)
    value=math('DIVIDE',math('ADD',math('ADD',math('MULTIPLY',u.outputs['Attribute'],math('SUBTRACT',1.,fraction)),math('MULTIPLY',fraction,.5)),dup.outputs['Duplicate Index']),count)
    store=N.new('GeometryNodeStoreNamedAttribute');store.domain='POINT';store.data_type='FLOAT';store.inputs['Name'].default_value='wb_profile_u';L.new(dup.outputs['Geometry'],store.inputs['Geometry']);L.new(value,store.inputs['Value'])
    result=N.new('GeometryNodeSwitch');result.input_type='GEOMETRY';L.new(enabled,result.inputs['Switch']);L.new(geometry,result.inputs['False']);L.new(store.outputs['Geometry'],result.inputs['True'])
    return result.outputs['Output']
