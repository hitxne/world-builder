"""Local inward-offset limits carried from actual rounded pavement borders."""
import math,bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

def limits(verts,loops,report):
    arcs=[]
    boundary={i for loop in loops for i in loop}
    for corner in report['radius_limits']:
        if corner.get('kind')!='interior' or not corner.get('exposed',True):continue
        c=corner.get('arc_center');r=corner['applied']
        if not c or r<=0:continue
        points=[verts[i] for i in boundary if abs(math.hypot(verts[i][0]-c[0],verts[i][1]-c[1])-r)<2e-4]
        angles=sorted(math.atan2(p[1]-c[1],p[0]-c[0]) for p in points)
        gaps=sorted((b-a)%math.tau for a,b in zip(angles,angles[1:]+angles[:1]))
        chord=max(gaps[:-1],default=0.)
        safe=max(.01,r*math.cos(chord/2)-.05)
        for p in points:arcs.append((p,safe))
    if not arcs:return [1e6]*len(verts)
    tree=KDTree(len(arcs))
    for i,(p,r) in enumerate(arcs):tree.insert(Vector((p[0],p[1],0)),i)
    tree.balance()
    return [min(arcs[i][1]+distance for _,i,distance in tree.find_n(Vector((p[0],p[1],0)),min(8,len(arcs)))) for p in verts]

def border_fields(group,output):
    if group.get('roadlab_offset_fields'):return
    N=group.nodes;L=group.links
    border=next(n for n in N if n.bl_idname=='GeometryNodeStoreNamedAttribute' and n.inputs['Name'].default_value=='parts' and n.inputs['Value'].default_value==7)
    mesh=next(n for n in N if n.bl_idname=='GeometryNodeObjectInfo' and n.inputs['Object'].default_value==output)
    position=N.new('GeometryNodeInputPosition');attr=N.new('GeometryNodeInputNamedAttribute');attr.data_type='FLOAT';attr.inputs['Name'].default_value='roadlab_offset_limit'
    nearest=N.new('GeometryNodeSampleNearest');nearest.domain='POINT';L.new(mesh.outputs['Geometry'],nearest.inputs['Geometry']);L.new(position.outputs['Position'],nearest.inputs['Sample Position'])
    sample=N.new('GeometryNodeSampleIndex');sample.data_type='FLOAT';sample.domain='POINT';L.new(mesh.outputs['Geometry'],sample.inputs['Geometry']);L.new(attr.outputs['Attribute'],sample.inputs['Value']);L.new(nearest.outputs['Index'],sample.inputs['Index'])
    store=N.new('GeometryNodeStoreNamedAttribute');store.data_type='FLOAT';store.domain='POINT';store.inputs['Name'].default_value='roadlab_offset_limit';store.label='Safe inward sidewalk offset'
    targets=[link.to_socket for link in border.outputs['Geometry'].links];L.new(border.outputs['Geometry'],store.inputs['Geometry']);L.new(sample.outputs['Value'],store.inputs['Value'])
    for socket in targets:L.new(store.outputs['Geometry'],socket)
    group['roadlab_offset_fields']=True
