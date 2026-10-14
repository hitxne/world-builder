"""Independent, reusable node groups. No original upstream groups modified."""
import bpy

def socket(g,name,direction,type,default=None):
 s=g.interface.new_socket(name=name,in_out=direction,socket_type=type)
 if default is not None:s.default_value=default
 return s

def create_groups():
 existing=[bpy.data.node_groups.get(name) for name in ('WB_ROAD_PROFILE','WB_CURB_PROFILE')]
 if all(existing) and any(n.bl_idname=='GeometryNodeInputRadius' for n in existing[0].nodes):return existing
 groups=[]
 # Simple asymmetric sweep proof. Source alignment must carry a stable curve normal.
 name='WB_ROAD_PROFILE'
 old=bpy.data.node_groups.get(name)
 if old and old.library is None:old.name=name+'_previous'
 g=bpy.data.node_groups.new(name,'GeometryNodeTree');g.use_fake_user=True
 socket(g,'Curve','INPUT','NodeSocketGeometry');socket(g,'Left width','INPUT','NodeSocketFloat',3.0);socket(g,'Right width','INPUT','NodeSocketFloat',3.0);socket(g,'Sample length','INPUT','NodeSocketFloat',.5);socket(g,'Material','INPUT','NodeSocketMaterial');socket(g,'Mesh','OUTPUT','NodeSocketGeometry')
 inp=g.nodes.new('NodeGroupInput');out=g.nodes.new('NodeGroupOutput');inp.location=(-600,0);out.location=(500,0)
 res=g.nodes.new('GeometryNodeResampleCurve');res.inputs['Mode'].default_value='Length';g.links.new(inp.outputs['Curve'],res.inputs['Curve']);g.links.new(inp.outputs['Sample length'],res.inputs['Length'])
 neg=g.nodes.new('ShaderNodeMath');neg.operation='MULTIPLY';neg.inputs[1].default_value=-1;g.links.new(inp.outputs['Right width'],neg.inputs[0])
 left=g.nodes.new('ShaderNodeCombineXYZ');right=g.nodes.new('ShaderNodeCombineXYZ');g.links.new(inp.outputs['Left width'],left.inputs['X']);g.links.new(neg.outputs[0],right.inputs['X'])
 line=g.nodes.new('GeometryNodeCurvePrimitiveLine');line.mode='POINTS';g.links.new(right.outputs[0],line.inputs['Start']);g.links.new(left.outputs[0],line.inputs['End'])
 sweep=g.nodes.new('GeometryNodeCurveToMesh');g.links.new(res.outputs['Curve'],sweep.inputs['Curve']);g.links.new(line.outputs['Curve'],sweep.inputs['Profile Curve']);radius=g.nodes.new('GeometryNodeInputRadius');g.links.new(radius.outputs['Radius'],sweep.inputs['Scale'])
 mat=g.nodes.new('GeometryNodeSetMaterial');g.links.new(sweep.outputs['Mesh'],mat.inputs['Geometry']);g.links.new(inp.outputs['Material'],mat.inputs['Material']);g.links.new(mat.outputs['Geometry'],out.inputs['Mesh']);groups.append(g)
 # Rectangular concrete profile sweep; full depressed curb logic resides in portable kernel.
 name='WB_CURB_PROFILE';old=bpy.data.node_groups.get(name)
 if old and old.library is None:old.name=name+'_previous'
 g=bpy.data.node_groups.new(name,'GeometryNodeTree');g.use_fake_user=True
 socket(g,'Curve','INPUT','NodeSocketGeometry');socket(g,'Width','INPUT','NodeSocketFloat',.32);socket(g,'Height','INPUT','NodeSocketFloat',.1524);socket(g,'Mesh','OUTPUT','NodeSocketGeometry')
 inp=g.nodes.new('NodeGroupInput');out=g.nodes.new('NodeGroupOutput');profile=g.nodes.new('GeometryNodeCurvePrimitiveQuadrilateral');profile.mode='RECTANGLE';g.links.new(inp.outputs['Width'],profile.inputs['Width']);g.links.new(inp.outputs['Height'],profile.inputs['Height'])
 sweep=g.nodes.new('GeometryNodeCurveToMesh');sweep.inputs['Fill Caps'].default_value=True;g.links.new(inp.outputs['Curve'],sweep.inputs['Curve']);g.links.new(profile.outputs['Curve'],sweep.inputs['Profile Curve']);g.links.new(sweep.outputs['Mesh'],out.inputs['Mesh']);groups.append(g)
 return groups
