"""Editable mesh outlines drive terrain-aware pads, islands, medians and lots."""
from .modifier_inputs import integer_operand
import uuid
import bpy
from bpy.props import EnumProperty,FloatProperty,BoolProperty,PointerProperty,IntProperty
from mathutils import Vector
from .native_extension import socket,set_input
KINDS=[('SIDEWALK','Sidewalk','Concrete pad or widened pedestrian area'),('ISLAND','Curb island','Grass island enclosed by curb'),('MEDIAN','Median','Raised grass median enclosed by curb'),('PARKING','Parking lot','Asphalt area defined by an editable outline')]
PRESETS={'SIDEWALK':(.1524,.2,False,'sidewalk'),'ISLAND':(.02,.08,True,'grass'),'MEDIAN':(.02,.08,True,'grass'),'PARKING':(.015,.08,False,'asphalt')}

def group():
    name='RoadLab Surface Bounds';g=bpy.data.node_groups.get(name)
    if g and g.get('roadlab_schema')==2:return g
    if g:g.nodes.clear()
    else:g=bpy.data.node_groups.new(name,'GeometryNodeTree')
    g['roadlab_schema']=2
    socket(g,'Geometry','INPUT','NodeSocketGeometry');socket(g,'Geometry','OUTPUT','NodeSocketGeometry')
    for name,kind,default in [('Entrance guide only','NodeSocketBool',False),('Entrance ramp length','NodeSocketFloat',3.),('Terrain detail','NodeSocketInt',3),('Existing surfaces','NodeSocketCollection',None),('Terrain','NodeSocketObject',None),('Road','NodeSocketObject',None),('Follow terrain','NodeSocketBool',True),('Trim at road','NodeSocketBool',True),('Surface height','NodeSocketFloat',.1524),('Thickness','NodeSocketFloat',.2),('Corner radius','NodeSocketFloat',.5),('Curb','NodeSocketBool',False),('Curb width','NodeSocketFloat',.25),('Curb height','NodeSocketFloat',.1524),('Surface material','NodeSocketMaterial',None),('Curb material','NodeSocketMaterial',None)]:socket(g,name,'INPUT',kind,default)
    N=g.nodes;L=g.links
    def node(kind,label):
        n=N.new(kind);n.label=label;return n
    inp=node('NodeGroupInput','Editable boundary plane');out=node('NodeGroupOutput','Generated surface')
    position=node('GeometryNodeInputPosition','Surface position')
    neighbors=node('GeometryNodeInputMeshEdgeNeighbors','Only outer and hole boundaries')
    boundary=node('FunctionNodeCompare','Boundary edges');boundary.data_type='INT';boundary.operation='EQUAL';integer_operand(boundary,'B').default_value=1;L.new(neighbors.outputs['Face Count'],integer_operand(boundary,'A'))
    outline=node('GeometryNodeMeshToCurve','Editable mesh perimeter');L.new(inp.outputs['Geometry'],outline.inputs['Mesh']);L.new(boundary.outputs['Result'],outline.inputs['Selection'])
    rounder=node('GeometryNodeFilletCurve','Rounded corners');rounder.inputs['Mode'].default_value='Poly';rounder.inputs['Count'].default_value=6;rounder.inputs['Limit Radius'].default_value=True;L.new(outline.outputs['Curve'],rounder.inputs['Curve']);L.new(inp.outputs['Corner radius'],rounder.inputs['Radius'])
    fill=node('GeometryNodeFillCurve','Fill concave bounds and holes');fill.inputs['Mode'].default_value='N-gons';L.new(rounder.outputs['Curve'],fill.inputs['Curve'])
    origin=node('ShaderNodeVectorMath','Ray origin');origin.operation='ADD';origin.inputs[1].default_value=(0,0,10000);L.new(position.outputs['Position'],origin.inputs[0])
    elevation=node('ShaderNodeSeparateXYZ','Target elevation field');L.new(position.outputs['Position'],elevation.inputs['Vector'])
    def ray(target,label):
        r=node('GeometryNodeRaycast',label);r.data_type='FLOAT';r.inputs['Ray Direction'].default_value=(0,0,-1);r.inputs['Ray Length'].default_value=20000;L.new(target,r.inputs['Target Geometry']);L.new(origin.outputs['Vector'],r.inputs['Source Position']);L.new(elevation.outputs['Z'],r.inputs['Attribute']);return r
    authored=ray(inp.outputs['Geometry'],'Preserve authored elevation')
    authored_z=node('ShaderNodeSeparateXYZ','Authoring plane height');L.new(authored.outputs['Hit Position'],authored_z.inputs['Vector'])
    authored_position=node('ShaderNodeSeparateXYZ','Source plane elevation');L.new(position.outputs['Position'],authored_position.inputs['Vector'])
    nearest_z=node('GeometryNodeSampleNearestSurface','Boundary height fallback');nearest_z.data_type='FLOAT';L.new(inp.outputs['Geometry'],nearest_z.inputs['Mesh']);L.new(authored_position.outputs['Z'],nearest_z.inputs['Value']);L.new(position.outputs['Position'],nearest_z.inputs['Sample Position'])
    source_height=node('GeometryNodeSwitch','Stable authored height at edges');source_height.input_type='FLOAT';L.new(authored.outputs['Is Hit'],source_height.inputs['Switch']);L.new(authored.outputs['Attribute'],source_height.inputs['True']);L.new(nearest_z.outputs['Value'],source_height.inputs['False'])
    terrain=node('GeometryNodeObjectInfo','Assigned terrain');terrain.transform_space='RELATIVE';L.new(inp.outputs['Terrain'],terrain.inputs['Object'])
    road=node('GeometryNodeObjectInfo','Assigned road');road.transform_space='RELATIVE';L.new(inp.outputs['Road'],road.inputs['Object'])
    road_mesh=node('GeometryNodeSeparateComponents','Road mesh only');L.new(road.outputs['Geometry'],road_mesh.inputs['Geometry'])
    contact=node('GeometryNodeInputNamedAttribute','Ground-contact roads');contact.data_type='BOOLEAN';contact.inputs['Name'].default_value='roadlab_ground_contact'
    contact_choice=node('GeometryNodeSwitch','Respect bridge cuts');contact_choice.input_type='BOOLEAN';contact_choice.inputs['False'].default_value=True;L.new(contact.outputs['Exists'],contact_choice.inputs['Switch']);L.new(contact.outputs['Attribute'],contact_choice.inputs['True'])
    ground_road=node('GeometryNodeSeparateGeometry','Exclude bridge decks');ground_road.domain='FACE';L.new(road_mesh.outputs['Mesh'],ground_road.inputs['Geometry']);L.new(contact_choice.outputs['Output'],ground_road.inputs['Selection'])
    ground=node('GeometryNodeJoinGeometry','Terrain and ground road');L.new(terrain.outputs['Geometry'],ground.inputs['Geometry']);L.new(ground_road.outputs['Selection'],ground.inputs['Geometry'])
    ground_hit=ray(ground.outputs['Geometry'],'Fit surface to ground')
    ground_z=node('ShaderNodeSeparateXYZ','Ground elevation');L.new(ground_hit.outputs['Hit Position'],ground_z.inputs['Vector'])
    lifted=node('ShaderNodeMath','Surface clearance');lifted.operation='ADD';L.new(ground_hit.outputs['Attribute'],lifted.inputs[0]);L.new(inp.outputs['Surface height'],lifted.inputs[1])
    follow=node('FunctionNodeBooleanMath','Follow only when ground exists');follow.operation='AND';L.new(inp.outputs['Follow terrain'],follow.inputs[0]);L.new(ground_hit.outputs['Is Hit'],follow.inputs[1])
    height=node('GeometryNodeSwitch','Terrain or authored height');height.input_type='FLOAT';L.new(follow.outputs['Boolean'],height.inputs['Switch']);L.new(source_height.outputs['Output'],height.inputs['False']);L.new(lifted.outputs[0],height.inputs['True'])
    # Detect changing ground normals. Flat and uniformly sloped pads keep a
    # single planar face; uneven ground gets an interior mesh before projection.
    area_bounds=node('GeometryNodeBoundBox','Surface sampling extent');L.new(inp.outputs['Geometry'],area_bounds.inputs['Geometry'])
    extent=node('ShaderNodeVectorMath','Sampling size');extent.operation='SUBTRACT';L.new(area_bounds.outputs['Max'],extent.inputs[0]);L.new(area_bounds.outputs['Min'],extent.inputs[1])
    extent_xyz=node('ShaderNodeSeparateXYZ','Sampling width and depth');L.new(extent.outputs['Vector'],extent_xyz.inputs['Vector'])
    center_sum=node('ShaderNodeVectorMath','Bounds center sum');center_sum.operation='ADD';L.new(area_bounds.outputs['Max'],center_sum.inputs[0]);L.new(area_bounds.outputs['Min'],center_sum.inputs[1])
    center=node('ShaderNodeVectorMath','Sampling center');center.operation='SCALE';center.inputs['Scale'].default_value=.5;L.new(center_sum.outputs['Vector'],center.inputs[0])
    probe=node('GeometryNodeMeshGrid','Ground variation probes');probe.inputs['Vertices X'].default_value=5;probe.inputs['Vertices Y'].default_value=5;L.new(extent_xyz.outputs['X'],probe.inputs['Size X']);L.new(extent_xyz.outputs['Y'],probe.inputs['Size Y'])
    probe_place=node('GeometryNodeTransform','Place ground probes');L.new(probe.outputs['Mesh'],probe_place.inputs['Geometry']);L.new(center.outputs['Vector'],probe_place.inputs['Translation'])
    variation=node('GeometryNodeAttributeStatistic','Ground normal variation');variation.data_type='FLOAT_VECTOR';variation.domain='POINT';L.new(probe_place.outputs['Geometry'],variation.inputs['Geometry']);L.new(ground_hit.outputs['Is Hit'],variation.inputs['Selection']);L.new(ground_hit.outputs['Hit Normal'],variation.inputs['Attribute'])
    variation_length=node('ShaderNodeVectorMath','Normal variance magnitude');variation_length.operation='LENGTH';L.new(variation.outputs['Variance'],variation_length.inputs[0])
    uneven=node('ShaderNodeMath','Ground is uneven');uneven.operation='GREATER_THAN';uneven.inputs[1].default_value=.000001;L.new(variation_length.outputs['Value'],uneven.inputs[0])
    follow_detail=node('FunctionNodeBooleanMath','Detail on uneven ground');follow_detail.operation='AND';L.new(inp.outputs['Follow terrain'],follow_detail.inputs[0]);L.new(uneven.outputs[0],follow_detail.inputs[1])
    authored_bounds=node('ShaderNodeSeparateXYZ','Authored height range');L.new(extent.outputs['Vector'],authored_bounds.inputs['Vector'])
    authored_uneven=node('ShaderNodeMath','Authored heights vary');authored_uneven.operation='GREATER_THAN';authored_uneven.inputs[1].default_value=.0001;L.new(authored_bounds.outputs['Z'],authored_uneven.inputs[0])
    manual=node('FunctionNodeBooleanMath','Manual height mode');manual.operation='NOT';L.new(inp.outputs['Follow terrain'],manual.inputs[0])
    manual_detail=node('FunctionNodeBooleanMath','Preserve shaped elevations');manual_detail.operation='AND';L.new(manual.outputs['Boolean'],manual_detail.inputs[0]);L.new(authored_uneven.outputs[0],manual_detail.inputs[1])
    needs_detail=node('FunctionNodeBooleanMath','Detail only when needed');needs_detail.operation='OR';L.new(follow_detail.outputs['Boolean'],needs_detail.inputs[0]);L.new(manual_detail.outputs['Boolean'],needs_detail.inputs[1])
    triangles=node('GeometryNodeFillCurve','Concave-safe detail seed');triangles.inputs['Mode'].default_value='Triangles';L.new(rounder.outputs['Curve'],triangles.inputs['Curve'])
    detail=node('GeometryNodeSubdivisionSurface','Interior terrain samples');detail.inputs['Edge Crease'].default_value=1;detail.inputs['Vertex Crease'].default_value=1;detail.inputs['Limit Surface'].default_value=False;L.new(triangles.outputs['Mesh'],detail.inputs['Mesh']);L.new(inp.outputs['Terrain detail'],detail.inputs['Level'])
    mesh_choice=node('GeometryNodeSwitch','Planar slab or terrain mesh');mesh_choice.input_type='GEOMETRY';L.new(needs_detail.outputs['Boolean'],mesh_choice.inputs['Switch']);L.new(fill.outputs['Mesh'],mesh_choice.inputs['False']);L.new(detail.outputs['Mesh'],mesh_choice.inputs['True'])
    top_height=node('GeometryNodeStoreNamedAttribute','Capture sampled top height');top_height.data_type='FLOAT';top_height.domain='POINT';top_height.inputs['Name'].default_value='roadlab_surface_top_z';L.new(mesh_choice.outputs['Output'],top_height.inputs['Geometry']);L.new(height.outputs['Output'],top_height.inputs['Value'])
    sampled=node('GeometryNodeInputNamedAttribute','Stable sampled height');sampled.data_type='FLOAT';sampled.inputs['Name'].default_value='roadlab_surface_top_z'
    xyz=node('ShaderNodeSeparateXYZ','Boundary XY');L.new(position.outputs['Position'],xyz.inputs['Vector'])
    top_position=node('ShaderNodeCombineXYZ','Top elevation');L.new(xyz.outputs['X'],top_position.inputs['X']);L.new(xyz.outputs['Y'],top_position.inputs['Y']);L.new(sampled.outputs['Attribute'],top_position.inputs['Z'])
    top=node('GeometryNodeSetPosition','Conforming slab top');L.new(top_height.outputs['Geometry'],top.inputs['Geometry']);L.new(top_position.outputs['Vector'],top.inputs['Position'])
    bottom_z=node('ShaderNodeMath','Slab underside');bottom_z.operation='SUBTRACT';L.new(sampled.outputs['Attribute'],bottom_z.inputs[0]);L.new(inp.outputs['Thickness'],bottom_z.inputs[1])
    bottom_position=node('ShaderNodeCombineXYZ','Bottom elevation');L.new(xyz.outputs['X'],bottom_position.inputs['X']);L.new(xyz.outputs['Y'],bottom_position.inputs['Y']);L.new(bottom_z.outputs[0],bottom_position.inputs['Z'])
    bottom=node('GeometryNodeSetPosition','Slab bottom');L.new(top.outputs['Geometry'],bottom.inputs['Geometry']);L.new(bottom_position.outputs['Vector'],bottom.inputs['Position'])
    up=node('ShaderNodeCombineXYZ','Slab thickness');L.new(inp.outputs['Thickness'],up.inputs['Z'])
    extrude=node('GeometryNodeExtrudeMesh','Solid slab');extrude.mode='FACES';extrude.inputs['Individual'].default_value=False;extrude.inputs['Offset Scale'].default_value=1;L.new(bottom.outputs['Geometry'],extrude.inputs['Mesh']);L.new(up.outputs['Vector'],extrude.inputs['Offset'])
    floor=node('GeometryNodeFlipFaces','Close slab underside');L.new(bottom.outputs['Geometry'],floor.inputs['Mesh'])
    slab=node('GeometryNodeJoinGeometry','Closed slab');L.new(extrude.outputs['Mesh'],slab.inputs['Geometry']);L.new(floor.outputs['Mesh'],slab.inputs['Geometry'])
    weld=node('GeometryNodeMergeByDistance','Weld slab base');weld.inputs['Distance'].default_value=.00001;L.new(slab.outputs['Geometry'],weld.inputs['Geometry'])
    surface_material=node('GeometryNodeSetMaterial','Chosen surface');L.new(weld.outputs['Geometry'],surface_material.inputs['Geometry']);L.new(inp.outputs['Surface material'],surface_material.inputs['Material'])
    rim=node('GeometryNodeMeshToCurve','Conforming curb path');L.new(top.outputs['Geometry'],rim.inputs['Mesh']);L.new(boundary.outputs['Result'],rim.inputs['Selection'])
    profile=node('GeometryNodeCurvePrimitiveQuadrilateral','Curb cross section');profile.mode='RECTANGLE';L.new(inp.outputs['Curb width'],profile.inputs['Width']);L.new(inp.outputs['Curb height'],profile.inputs['Height'])
    half=node('ShaderNodeMath','Half curb height');half.operation='MULTIPLY';half.inputs[1].default_value=.5;L.new(inp.outputs['Curb height'],half.inputs[0])
    curb_center=node('ShaderNodeMath','Curb foot at terrain');curb_center.operation='SUBTRACT';L.new(inp.outputs['Surface height'],curb_center.inputs[0]);L.new(half.outputs[0],curb_center.inputs[1])
    shift=node('ShaderNodeCombineXYZ','Vertical curb profile');L.new(curb_center.outputs[0],shift.inputs['Y'])
    profile_shift=node('GeometryNodeTransform','Place curb cross section');L.new(profile.outputs['Curve'],profile_shift.inputs['Geometry']);L.new(shift.outputs['Vector'],profile_shift.inputs['Translation'])
    sweep=node('GeometryNodeCurveToMesh','Boundary curb');sweep.inputs['Fill Caps'].default_value=True;L.new(rim.outputs['Curve'],sweep.inputs['Curve']);L.new(profile_shift.outputs['Geometry'],sweep.inputs['Profile Curve'])
    curb_material=node('GeometryNodeSetMaterial','Concrete curb');L.new(sweep.outputs['Mesh'],curb_material.inputs['Geometry']);L.new(inp.outputs['Curb material'],curb_material.inputs['Material'])
    optional_curb=node('GeometryNodeSwitch','Optional boundary curb');optional_curb.input_type='GEOMETRY';L.new(inp.outputs['Curb'],optional_curb.inputs['Switch']);L.new(curb_material.outputs['Geometry'],optional_curb.inputs['True'])
    all_surfaces=node('GeometryNodeJoinGeometry','Slab and curb');L.new(surface_material.outputs['Geometry'],all_surfaces.inputs['Geometry']);L.new(optional_curb.outputs['Output'],all_surfaces.inputs['Geometry'])
    union=node('GeometryNodeMeshBoolean','Remove internal overlaps');union.operation='UNION';union.solver='EXACT';union.inputs['Self Intersection'].default_value=True;L.new(all_surfaces.outputs['Geometry'],union.inputs['Mesh 2'])
    use_union=node('GeometryNodeSwitch','Union only with curb');use_union.input_type='GEOMETRY';L.new(inp.outputs['Curb'],use_union.inputs['Switch']);L.new(surface_material.outputs['Geometry'],use_union.inputs['False']);L.new(union.outputs['Mesh'],use_union.inputs['True'])
    edges=node('GeometryNodeCollectionInfo','Existing curbs and sidewalks');edges.transform_space='RELATIVE';L.new(inp.outputs['Existing surfaces'],edges.inputs['Collection'])
    realized=node('GeometryNodeRealizeInstances','Realize edge surfaces');L.new(edges.outputs['Instances'],realized.inputs['Geometry'])
    components=node('GeometryNodeSeparateComponents','Edge mesh only');L.new(realized.outputs['Geometry'],components.inputs['Geometry'])
    normal=node('GeometryNodeInputNormal','Upward edge surfaces');normal_z=node('ShaderNodeSeparateXYZ','Face normal Z');L.new(normal.outputs['Normal'],normal_z.inputs['Vector'])
    upward=node('ShaderNodeMath','Top faces');upward.operation='GREATER_THAN';upward.inputs[1].default_value=.1;L.new(normal_z.outputs['Z'],upward.inputs[0])
    edge_grade=node('ShaderNodeMath','Height above ground');edge_grade.operation='SUBTRACT';L.new(elevation.outputs['Z'],edge_grade.inputs[0]);L.new(ground_hit.outputs['Attribute'],edge_grade.inputs[1])
    nearby_grade=node('ShaderNodeMath','Exclude elevated structures');nearby_grade.operation='LESS_THAN';nearby_grade.inputs[1].default_value=2;L.new(edge_grade.outputs[0],nearby_grade.inputs[0])
    edge_selection=node('FunctionNodeBooleanMath','Ground edge tops only');edge_selection.operation='AND';L.new(upward.outputs[0],edge_selection.inputs[0]);L.new(nearby_grade.outputs[0],edge_selection.inputs[1])
    edge_tops=node('GeometryNodeSeparateGeometry','Clip against ground-level edges');edge_tops.domain='FACE';L.new(components.outputs['Mesh'],edge_tops.inputs['Geometry']);L.new(edge_selection.outputs['Boolean'],edge_tops.inputs['Selection'])
    footprint=node('GeometryNodeJoinGeometry','Road and existing sidewalk footprints');L.new(ground_road.outputs['Selection'],footprint.inputs['Geometry']);L.new(edge_tops.outputs['Selection'],footprint.inputs['Geometry'])
    # Crop by complete face bounds, not just centroids: long sidewalk slabs may
    # cross this pad even when their center is far away. This keeps booleans local.
    bounds=node('GeometryNodeBoundBox','Authoring bounds');L.new(inp.outputs['Geometry'],bounds.inputs['Geometry'])
    bounds_min=node('ShaderNodeSeparateXYZ','Bounds minimum');bounds_max=node('ShaderNodeSeparateXYZ','Bounds maximum');L.new(bounds.outputs['Min'],bounds_min.inputs['Vector']);L.new(bounds.outputs['Max'],bounds_max.inputs['Vector'])
    face_index=node('GeometryNodeInputIndex','Face index');tests=[]
    for axis in ('X','Y'):
        extremes=[]
        for maximum in (False,True):
            corners=node('GeometryNodeCornersOfFace','Face '+axis+(' maximum' if maximum else ' minimum'));L.new(face_index.outputs['Index'],corners.inputs['Face Index']);L.new(xyz.outputs[axis],corners.inputs['Weights'])
            if not maximum:total=corners.outputs['Total']
            if maximum:
                last=node('ShaderNodeMath','Last sorted corner');last.operation='SUBTRACT';last.inputs[1].default_value=1;L.new(total,last.inputs[0]);L.new(last.outputs[0],corners.inputs['Sort Index'])
            sample=node('GeometryNodeSampleIndex','Face corner position');sample.data_type='FLOAT_VECTOR';sample.domain='CORNER';L.new(footprint.outputs['Geometry'],sample.inputs['Geometry']);L.new(position.outputs['Position'],sample.inputs['Value']);L.new(corners.outputs['Corner Index'],sample.inputs['Index'])
            component=node('ShaderNodeSeparateXYZ','Corner '+axis);L.new(sample.outputs['Value'],component.inputs['Vector']);extremes.append(component.outputs[axis])
        left=node('ShaderNodeMath','Face extends past lower bound');left.operation='GREATER_THAN';L.new(extremes[1],left.inputs[0]);L.new(bounds_min.outputs[axis],left.inputs[1]);tests.append(left.outputs[0])
        right=node('ShaderNodeMath','Face begins before upper bound');right.operation='LESS_THAN';L.new(extremes[0],right.inputs[0]);L.new(bounds_max.outputs[axis],right.inputs[1]);tests.append(right.outputs[0])
    selected=tests[0]
    for test in tests[1:]:
        both=node('FunctionNodeBooleanMath','Overlapping face bounds');both.operation='AND';L.new(selected,both.inputs[0]);L.new(test,both.inputs[1]);selected=both.outputs['Boolean']
    local_footprint=node('GeometryNodeSeparateGeometry','Only nearby road and sidewalk faces');local_footprint.domain='FACE';L.new(footprint.outputs['Geometry'],local_footprint.inputs['Geometry']);L.new(selected,local_footprint.inputs['Selection'])
    cutter_base=node('GeometryNodeTransform','Road clearance base');cutter_base.inputs['Translation'].default_value=(0,0,-100);L.new(local_footprint.outputs['Selection'],cutter_base.inputs['Geometry'])
    cutter_height=node('ShaderNodeCombineXYZ','Cutter extrusion vector');cutter_height.inputs['Z'].default_value=200
    road_extrude=node('GeometryNodeExtrudeMesh','Road footprint cutter');road_extrude.mode='FACES';road_extrude.inputs['Individual'].default_value=False;road_extrude.inputs['Offset Scale'].default_value=1;road_extrude.inputs['Offset'].default_value=(0,0,200);L.new(cutter_base.outputs['Geometry'],road_extrude.inputs['Mesh']);L.new(cutter_height.outputs['Vector'],road_extrude.inputs['Offset'])
    road_floor=node('GeometryNodeFlipFaces','Close road cutter');L.new(cutter_base.outputs['Geometry'],road_floor.inputs['Mesh'])
    road_closed=node('GeometryNodeJoinGeometry','Closed road cutter');L.new(road_extrude.outputs['Mesh'],road_closed.inputs['Geometry']);L.new(road_floor.outputs['Mesh'],road_closed.inputs['Geometry'])
    road_weld=node('GeometryNodeMergeByDistance','Weld road cutter');road_weld.inputs['Distance'].default_value=.00001;L.new(road_closed.outputs['Geometry'],road_weld.inputs['Geometry'])
    cutter_union=node('GeometryNodeMeshBoolean','Union adjoining footprints');cutter_union.operation='UNION';cutter_union.solver='EXACT';cutter_union.inputs['Self Intersection'].default_value=True;L.new(road_weld.outputs['Geometry'],cutter_union.inputs['Mesh 2'])
    clip=node('GeometryNodeMeshBoolean','Keep asphalt clear');clip.operation='DIFFERENCE';clip.solver='EXACT';clip.inputs['Self Intersection'].default_value=True;L.new(use_union.outputs['Output'],clip.inputs['Mesh 1']);L.new(cutter_union.outputs['Mesh'],clip.inputs['Mesh 2'])
    road_size=node('GeometryNodeAttributeDomainSize','Ground road exists');road_size.component='MESH';L.new(local_footprint.outputs['Selection'],road_size.inputs['Geometry'])
    road_exists=node('ShaderNodeMath','Has road faces');road_exists.operation='GREATER_THAN';L.new(road_size.outputs['Face Count'],road_exists.inputs[0])
    trim_enabled=node('FunctionNodeBooleanMath','Trim only with road');trim_enabled.operation='AND';L.new(inp.outputs['Trim at road'],trim_enabled.inputs[0]);L.new(road_exists.outputs[0],trim_enabled.inputs[1])
    trimmed=node('GeometryNodeSwitch','Optional road trim');trimmed.input_type='GEOMETRY';L.new(trim_enabled.outputs['Boolean'],trimmed.inputs['Switch']);L.new(use_union.outputs['Output'],trimmed.inputs['False']);L.new(clip.outputs['Mesh'],trimmed.inputs['True'])
    flat=node('GeometryNodeSetShadeSmooth','Flat concrete and asphalt');flat.domain='FACE';flat.inputs['Shade Smooth'].default_value=False;L.new(trimmed.outputs['Output'],flat.inputs['Geometry'])
    # A separate object sharing the authored mesh uses only this upstream top.
    # It never reads the sidewalk being deformed, avoiding a dependency cycle.
    guide_weight=node('GeometryNodeStoreNamedAttribute','Parking entrance weight');guide_weight.data_type='FLOAT';guide_weight.domain='POINT';guide_weight.inputs['Name'].default_value='roadlab_crossing_weight';guide_weight.inputs['Value'].default_value=1;L.new(top.outputs['Geometry'],guide_weight.inputs['Geometry'])
    guide_run=node('GeometryNodeStoreNamedAttribute','Equal entrance and exit ramp length');guide_run.data_type='FLOAT';guide_run.domain='POINT';guide_run.inputs['Name'].default_value='roadlab_crossing_run';L.new(inp.outputs['Entrance ramp length'],guide_run.inputs['Value']);L.new(guide_weight.outputs['Geometry'],guide_run.inputs['Geometry'])
    guide_kind=node('GeometryNodeStoreNamedAttribute','Parking crossing identity');guide_kind.data_type='FLOAT';guide_kind.domain='POINT';guide_kind.inputs['Name'].default_value='roadlab_parking_entrance';guide_kind.inputs['Value'].default_value=1;L.new(guide_run.outputs['Geometry'],guide_kind.inputs['Geometry'])
    output=node('GeometryNodeSwitch','Surface or independent entrance footprint');output.input_type='GEOMETRY';L.new(inp.outputs['Entrance guide only'],output.inputs['Switch']);L.new(flat.outputs['Geometry'],output.inputs['False']);L.new(guide_kind.outputs['Geometry'],output.inputs['True']);L.new(output.outputs['Output'],out.inputs['Geometry'])
    for i,n in enumerate(N):n.location=((i%8)*240,-(i//8)*240)
    return g

def sync_contacts(road):
    from .native_layers import model_for
    collection=road.get('roadlab_surface_contacts')
    if collection is None:
        collection=bpy.data.collections.new('RoadLab Surface Contacts');road['roadlab_surface_contacts']=collection
    model=model_for(road)
    wanted={layer.object for layer in model.wb_layers if layer.enabled and layer.kind in ('curb','sidewalk') and layer.object} if model else set()
    for obj in list(collection.objects):
        if obj not in wanted:collection.objects.unlink(obj)
    for obj in wanted:
        if obj.name not in collection.objects:collection.objects.link(obj)
    return collection

def update(self,context):
    obj=self.id_data
    if not isinstance(obj,bpy.types.Object) or not obj.get('roadlab_surface_bounds'):return
    mod=next((m for m in obj.modifiers if m.type=='NODES' and m.node_group and m.node_group.get('roadlab_schema')==2 and m.node_group.name.startswith('RoadLab Surface Bounds')),None)
    if mod is None:return
    from . import material
    terrain=self.terrain
    helper=terrain.get('roadlab_core_terrain_mesh') if terrain else None
    for name,value in [('Terrain detail',self.detail),('Existing surfaces',sync_contacts(self.road) if self.road else None),('Terrain',helper or terrain),('Road',self.road),('Follow terrain',self.follow),('Trim at road',self.trim),('Surface height',self.rise),('Thickness',self.thickness),('Corner radius',self.radius),('Curb',self.curb),('Curb width',self.curb_width),('Curb height',self.curb_height),('Surface material',material(PRESETS[self.kind][3])),('Curb material',material('concrete'))]:set_input(mod,name,value)
    if obj.get('roadlab_surface_kind')!=self.kind:obj['roadlab_surface_kind']=self.kind
    obj.update_tag()
    from .parking_entrances import sync_scene
    if context and context.scene:sync_scene(context.scene)

def kind_update(self,context):
    rise,thickness,curb,_=PRESETS[self.kind]
    self.rise=rise;self.thickness=thickness;self.curb=curb
    update(self,context)

class RoadLabSurfaceSettings(bpy.types.PropertyGroup):
    entrances:BoolProperty(name='Driveway crossings',default=True,description='Lower overlapping road curbs and sidewalks for parking access, with matching ramps on both sides',update=update)
    entrance_run:FloatProperty(name='Ramp length (m)',default=3.,min=.5,max=12,description='Same transition length on both sides of every driveway crossing',update=update)
    detail:IntProperty(name='Terrain detail',default=3,min=1,max=5,description='Interior subdivision on uneven ground only; higher values cost more geometry',update=update)
    kind:EnumProperty(name='Surface',items=KINDS,default='SIDEWALK',description='Choose a surface preset; resets material, height, thickness and curb defaults',update=kind_update)
    follow:BoolProperty(name='Follow terrain',default=True,description='Fit boundary to assigned terrain and ground-contact road; disable to edit elevations',update=update)
    trim:BoolProperty(name='Trim overlaps',default=True,description='Remove overlap with the assigned road and existing curb/sidewalk layers',update=update)
    rise:FloatProperty(name='Surface height (m)',default=.1524,min=0,max=5,update=update)
    thickness:FloatProperty(name='Slab thickness (m)',default=.2,min=.01,max=2,update=update)
    radius:FloatProperty(name='Corner radius (m)',default=.5,min=0,max=20,update=update)
    curb:BoolProperty(name='Boundary curb',default=False,update=update)
    curb_width:FloatProperty(name='Curb width (m)',default=.25,min=.05,max=2,update=update)
    curb_height:FloatProperty(name='Curb height (m)',default=.1524,min=.02,max=1,update=update)
    terrain:PointerProperty(name='Terrain',type=bpy.types.Object,update=update)
    road:PointerProperty(name='Road',type=bpy.types.Object,update=update)

def validate_outline(coords):
    from mathutils.geometry import intersect_line_line_2d
    if len(coords)<3:raise ValueError('Draw at least three corners')
    if any((Vector(a)-Vector(b)).length<.01 for a,b in zip(coords,coords[1:]+coords[:1])):raise ValueError('Corners are too close together')
    for i,(a,b) in enumerate(zip(coords,coords[1:]+coords[:1])):
        for j,(c,d) in enumerate(zip(coords,coords[1:]+coords[:1])):
            if j<=i or (j-i)%len(coords) in (1,len(coords)-1):continue
            if intersect_line_line_2d(Vector(a[:2]),Vector(b[:2]),Vector(c[:2]),Vector(d[:2])) is not None:raise ValueError('The outline crosses itself; move or remove a corner')
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(coords,coords[1:]+coords[:1]))/2
    if abs(area)<.01:raise ValueError('The outline needs an area')
    return list(reversed(coords)) if area<0 else coords

def create_surface(context,coords,kind=None):
    coords=validate_outline(list(coords));kind=kind or context.scene.roadlab_surface_kind
    rise,thickness,curb,_=PRESETS[kind]
    mesh=bpy.data.meshes.new('RoadLab Editable Surface Plane');mesh.from_pydata([(x,y,z+rise) for x,y,z in coords],[],[tuple(range(len(coords)))]);mesh.update()
    obj=bpy.data.objects.new('RoadLab '+dict((k,n) for k,n,_ in KINDS)[kind],mesh);context.collection.objects.link(obj);obj['roadlab_surface_bounds']=True;obj['roadlab_surface_id']=uuid.uuid4().hex;obj['roadlab_surface_schema']=1
    mod=obj.modifiers.new('RoadLab Surface Bounds','NODES');mod.node_group=group();mod.show_in_editmode=True
    settings=obj.roadlab_surface;settings.kind=kind;settings.rise=rise;settings.thickness=thickness;settings.curb=curb
    settings.terrain=context.scene.wb_native.terrain;settings.road=context.scene.wb_native.road;update(settings,context)
    for item in context.view_layer.objects:item.select_set(False)
    obj.select_set(True);context.view_layer.objects.active=obj
    return obj

class ROADLAB_OT_surface_plane(bpy.types.Operator):
    bl_idname='roadlab.surface_plane';bl_label='Create surface plane';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT'
    def execute(self,context):
        c=context.scene.cursor.location;coords=[(c.x+x,c.y+y,c.z) for x,y in [(-2,-2),(2,-2),(2,2),(-2,2)]]
        create_surface(context,coords);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        self.report({'INFO'},'Edit the plane boundary to shape the surface')
        return {'FINISHED'}

class ROADLAB_OT_draw_surface(bpy.types.Operator):
    bl_idname='roadlab.draw_surface';bl_label='Draw surface bounds';bl_options={'REGISTER','UNDO'}
    bl_description='Click boundary corners; Enter or click the first corner to finish; Backspace removes; Esc cancels'
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and context.area is not None and context.area.type=='VIEW_3D'
    def pick(self,context,event):
        from bpy_extras import view3d_utils
        from mathutils.geometry import intersect_line_plane
        region=self.region;xy=(event.mouse_x-region.x,event.mouse_y-region.y)
        origin=view3d_utils.region_2d_to_origin_3d(region,context.space_data.region_3d,xy)
        direction=view3d_utils.region_2d_to_vector_3d(region,context.space_data.region_3d,xy)
        hits=[]
        for tree in self.trees:
            point,normal,index,distance=tree.ray_cast(origin,direction)
            if point is not None:hits.append((distance,point))
        if hits:return min(hits,key=lambda item:item[0])[1]
        return intersect_line_plane(origin,origin+direction,Vector((0,0,context.scene.cursor.location.z)),Vector((0,0,1)))
    def invoke(self,context,event):
        from mathutils.bvhtree import BVHTree
        self.region=next(r for r in context.area.regions if r.type=='WINDOW');self.area=context.area;self.coords=[];self.hover=None;self.trees=[]
        terrain=context.scene.wb_native.terrain;road=context.scene.wb_native.road
        for obj in [terrain.get('roadlab_core_terrain_mesh') or terrain if terrain else None,road.get('roadlab_core_mesh') if road else None]:
            if obj and obj.type=='MESH' and obj.data.polygons:self.trees.append(BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],[tuple(p.vertices) for p in obj.data.polygons]))
        kind=dict((k,n) for k,n,_ in KINDS)[context.scene.roadlab_surface_kind]
        self.area.header_text_set(kind+' bounds | Click corners | Enter or close outline: finish | Backspace: undo corner | Esc: cancel')
        self.handler=bpy.types.SpaceView3D.draw_handler_add(self.draw_preview,(),'WINDOW','POST_VIEW')
        context.window.cursor_set('CROSSHAIR');context.window_manager.modal_handler_add(self)
        if context.region.type=='WINDOW' and event.type=='LEFTMOUSE':
            point=self.pick(context,event)
            if point is not None:self.coords.append(tuple(point))
        return {'RUNNING_MODAL'}
    def draw_preview(self):
        if bpy.context.area!=self.area:return
        import gpu
        from gpu_extras.batch import batch_for_shader
        coords=list(self.coords)
        if self.hover is not None:coords.append(tuple(self.hover))
        if len(coords)<2:return
        lines=[]
        for a,b in zip(coords,coords[1:]):lines.extend((a,b))
        if len(coords)>2:lines.extend((coords[-1],coords[0]))
        shader=gpu.shader.from_builtin('UNIFORM_COLOR');batch=batch_for_shader(shader,'LINES',{'pos':[(x,y,z+.02) for x,y,z in lines]})
        gpu.state.depth_test_set('NONE');gpu.state.line_width_set(2)
        try:shader.bind();shader.uniform_float('color',(1.,.6,.08,1.));batch.draw(shader)
        finally:gpu.state.line_width_set(1)
    def cleanup(self,context):
        if getattr(self,'handler',None) is not None:bpy.types.SpaceView3D.draw_handler_remove(self.handler,'WINDOW');self.handler=None
        self.area.header_text_set(None);context.window.cursor_set('DEFAULT');self.area.tag_redraw()
    def cancel(self,context):self.cleanup(context)
    def finish(self,context):
        try:obj=create_surface(context,self.coords)
        except ValueError as error:self.report({'WARNING'},str(error));return {'RUNNING_MODAL'}
        self.cleanup(context);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        self.report({'INFO'},'Surface created. Edit the plane boundary to refine its shape.')
        return {'FINISHED'}
    def modal(self,context,event):
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        self.area.tag_redraw()
        if event.type in ('ESC','RIGHTMOUSE') and event.value=='PRESS':self.cleanup(context);return {'CANCELLED'}
        if event.type=='BACK_SPACE' and event.value=='PRESS':
            if self.coords:self.coords.pop()
            return {'RUNNING_MODAL'}
        if event.type in ('RET','NUMPAD_ENTER','SPACE') and event.value=='PRESS':return self.finish(context)
        if event.type=='MOUSEMOVE':self.hover=self.pick(context,event);return {'RUNNING_MODAL'}
        if event.type=='LEFTMOUSE' and event.value=='PRESS':
            if self.coords and len(self.coords)>=3:
                pixel=location_3d_to_region_2d(self.region,context.space_data.region_3d,Vector(self.coords[0]));mouse=Vector((event.mouse_x-self.region.x,event.mouse_y-self.region.y))
                if pixel is not None and (pixel-mouse).length<12:return self.finish(context)
            point=self.pick(context,event)
            if point is not None:self.coords.append(tuple(point))
            return {'RUNNING_MODAL'}
        if event.type in ('MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE'):return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}

class ROADLAB_WST_surface_bounds(bpy.types.WorkSpaceTool):
    bl_idname='roadlab.surface_bounds';bl_label='Surface Bounds';bl_description='Draw sidewalk pads, curb islands, medians and parking areas';bl_space_type='VIEW_3D';bl_context_mode='OBJECT';bl_icon='ops.mesh.primitive_plane_add';bl_widget=None
    bl_keymap=(('roadlab.draw_surface',{'type':'LEFTMOUSE','value':'PRESS'},{}),)
    @staticmethod
    def draw_settings(context,layout,tool):
        layout.prop(context.scene,'roadlab_surface_kind',text='Surface');layout.label(text='Click corners · Enter to finish')

class ROADLAB_PT_surface_bounds(bpy.types.Panel):
    bl_label='Surface Bounds';bl_idname='ROADLAB_PT_surface_bounds';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        layout=self.layout;obj=context.active_object
        if obj and obj.get('roadlab_surface_bounds'):
            settings=obj.roadlab_surface;layout.use_property_split=True
            layout.prop(settings,'kind');layout.prop(settings,'radius');layout.prop(settings,'follow')
            if not settings.follow:layout.label(text='Edit plane vertices to shape elevation.',icon='EDITMODE_HLT')
            elif not settings.terrain and not settings.road:layout.label(text='No ground assigned; using plane height.',icon='INFO')
            if settings.follow:layout.prop(settings,'rise')
            layout.prop(settings,'thickness');layout.prop(settings,'curb')
            if settings.curb:layout.prop(settings,'curb_width');layout.prop(settings,'curb_height')
            layout.prop(settings,'trim')
            if settings.kind=='PARKING':
                layout.prop(settings,'entrances')
                if settings.entrances:layout.prop(settings,'entrance_run')
            if context.mode=='OBJECT':layout.operator('object.mode_set',text='Edit boundary',icon='EDITMODE_HLT').mode='EDIT'
            else:layout.label(text='Move, extrude, or subdivide boundary vertices.')
        else:
            layout.prop(context.scene,'roadlab_surface_kind',text='Surface')
            row=layout.row();row.enabled=context.mode=='OBJECT';row.operator('wm.tool_set_by_id',text='Draw bounds',icon='GREASEPENCIL').name='roadlab.surface_bounds'
            row=layout.row();row.enabled=context.mode=='OBJECT';row.operator('roadlab.surface_plane',text='Create editable plane',icon='MESH_PLANE')
            if context.mode!='OBJECT':layout.label(text='Tab to Object Mode to add a surface.',icon='INFO')

class ROADLAB_PT_surface_targets(bpy.types.Panel):
    bl_label='Ground and Road';bl_idname='ROADLAB_PT_surface_targets';bl_parent_id='ROADLAB_PT_surface_bounds';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return context.active_object is not None and context.active_object.get('roadlab_surface_bounds',False)
    def draw(self,context):
        settings=context.active_object.roadlab_surface
        self.layout.prop(settings,'terrain');self.layout.prop(settings,'road');self.layout.prop(settings,'detail')

classes=(RoadLabSurfaceSettings,ROADLAB_OT_surface_plane,ROADLAB_OT_draw_surface,ROADLAB_PT_surface_bounds,ROADLAB_PT_surface_targets)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Object.roadlab_surface=PointerProperty(type=RoadLabSurfaceSettings)
    bpy.types.Scene.roadlab_surface_kind=EnumProperty(name='Surface',items=KINDS,default='SIDEWALK')
    bpy.utils.register_tool(ROADLAB_WST_surface_bounds,separator=True)
    from . import parking_entrances
    parking_entrances.register()
def unregister():
    from . import parking_entrances
    parking_entrances.unregister()
    bpy.utils.unregister_tool(ROADLAB_WST_surface_bounds)
    del bpy.types.Object.roadlab_surface;del bpy.types.Scene.roadlab_surface_kind
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
