bl_info={'name':'RoadLab','author':'World Builder','version':(0,18,11),'blender':(5,1,0),'location':'View3D > Sidebar > RoadLab','category':'Object'}
import bpy,json,math
from pathlib import Path
from bpy.props import StringProperty,FloatProperty,BoolProperty,EnumProperty,FloatVectorProperty,CollectionProperty,PointerProperty
from bpy_extras.io_utils import ImportHelper,ExportHelper
from . import model,geometry,core

COLORS={'asphalt':(.045,.053,.066,1),'concrete':(.52,.53,.51,1),'sidewalk':(.66,.65,.60,1),'gutter':(.38,.40,.39,1),'white':(.94,.94,.88,1),'yellow':(.95,.65,.025,1),'grass':(.12,.25,.08,1),'warning':(.9,.50,.035,1),'bike-green':(.12,.54,.22,1),'guide':(.04,.65,.9,1)}
def material(name):
 name='WB_'+name;mat=bpy.data.materials.get(name)
 if not mat:
  mat=bpy.data.materials.new(name);mat.diffuse_color=COLORS.get(name[3:],(.5,.5,.5,1));mat.use_nodes=True
  p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=mat.diffuse_color;p.inputs['Roughness'].default_value=.88
 return mat

def delete_collection(collection):
 for child in list(collection.children):
  if child.get('wb_owned'):delete_collection(child)
 for obj in list(collection.objects):
  data=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
  if data and data.users==0:
   if isinstance(data,bpy.types.Mesh):bpy.data.meshes.remove(data)
   elif isinstance(data,bpy.types.Curve):bpy.data.curves.remove(data)
 bpy.data.collections.remove(collection)

def create_spec(collection,spec):
 if 'points' in spec:
  data=bpy.data.curves.new('WB_'+spec['id'],'CURVE');data.dimensions='3D';data.bevel_depth=.045;data.bevel_resolution=2
  spl=data.splines.new('POLY');spl.points.add(len(spec['points'])-1)
  for point,co in zip(spl.points,spec['points']):point.co=(*co,1)
 else:
  data=bpy.data.meshes.new('WB_'+spec['id']);data.from_pydata(spec['verts'],[],spec['faces']);data.update()
  layer=data.uv_layers.new(name='WB_world_m')
  for loop in data.loops:layer.data[loop.index].uv=data.vertices[loop.vertex_index].co.xy
 obj=bpy.data.objects.new('WB_'+spec['id'],data);collection.objects.link(obj);data.materials.append(material(spec['material']));obj['wb_id']=spec['id'];obj['wb_category']=spec['category'];obj['wb_metadata']=json.dumps(spec.get('metadata',{}))
 if spec['category']=='guide':obj.hide_render=True
 return obj

def parking_sources(scene,graph,reset=False):
 col=bpy.data.collections.get('WB_PARKING_OUTLINES')
 if graph['fixture']!='parking':
  if col:col.hide_viewport=True
  return
 if reset and col:delete_collection(col);col=None
 if not col:col=bpy.data.collections.new('WB_PARKING_OUTLINES');scene.collection.children.link(col)
 col.hide_viewport=False;lot=graph['parking'];entities=[(lot,'lot')]+[(island,'island') for island in lot['islands']]
 for entity,kind in entities:
  obj=next((obj for obj in col.objects if obj.get('wb_parking_id')==entity['id']),None)
  if obj:continue
  data=bpy.data.curves.new('WB_Outline_'+entity['id'],'CURVE');data.dimensions='3D';spline=data.splines.new('POLY');spline.points.add(len(entity['vertices'])-1);spline.use_cyclic_u=True
  for p,co in zip(spline.points,entity['vertices']):p.co=(*co,.18,1)
  obj=bpy.data.objects.new('WB_Outline_'+entity['id'],data);col.objects.link(obj);obj.hide_render=True;obj.show_in_front=True;obj['wb_parking_id']=entity['id'];obj['wb_parking_kind']=kind

def object_fingerprint(obj):
 import hashlib
 if obj.type=='MESH':data={'vertices':[list(v.co) for v in obj.data.vertices],'faces':[list(p.vertices) for p in obj.data.polygons],'matrix':[list(row) for row in obj.matrix_world],'materials':[m.name if m else None for m in obj.data.materials]}
 elif obj.type=='CURVE':data={'splines':[[list(p.co) for p in spline.points] for spline in obj.data.splines],'matrix':[list(row) for row in obj.matrix_world]}
 else:return ''
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def regenerate(scene,graph=None,force=False):
 graph=model.loads(scene.wb_graph) if graph is None else model.validate(graph)
 if graph.get('version')==3:
  from . import terrain_ui
  return terrain_ui.rebuild(scene,graph,force)
 specs,diagnostics,resolved=model.build(graph) # no mutations before validation succeeds
 old=bpy.data.collections.get('WB_GENERATED')
 if old and not force:
  desired={e['id']:e for ends in resolved.values() for e in ends.values()}
  for obj in old.objects:
   if obj.type in ('MESH','CURVE') and obj.get('wb_fingerprint') and object_fingerprint(obj)!=obj['wb_fingerprint']:
    raise ValueError('Direct edit detected on '+obj.name+'. Keep a copy before replacing the example; edit source controls for regeneration.')
   if 'wb_endpoint_id' in obj and list(obj.location)!=json.loads(obj.get('wb_handle_position','[]')):
    e=desired.get(obj['wb_endpoint_id'])
    if not e or e.get('mode')!='manual' or any(abs(obj.location[k]-e['position'][k])>1e-5 for k in range(3)):
     raise ValueError('Moved endpoint handle: capture its manual override before regeneration')
 stage=bpy.data.collections.new('WB_STAGING');scene.collection.children.link(stage)
 try:
  for spec in specs:
   obj=create_spec(stage,spec)
   if spec['category']=='guide':obj.hide_viewport=not graph['settings'].get('show_guides',False)
  # Cut island holes before unioning the explicit parking-road connection.
  cutters=[obj for obj in stage.objects if obj.get('wb_category')=='cutter']
  for cutter in cutters:
   target_id=json.loads(cutter['wb_metadata'])['cut_target'];target=next(obj for obj in stage.objects if obj.get('wb_id')==target_id)
   bpy.context.view_layer.update();modifier=target.modifiers.new('WB planter cut','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
   bpy.context.view_layer.objects.active=target;target.select_set(True);bpy.ops.object.modifier_apply(modifier=modifier.name);target.select_set(False);data=cutter.data;bpy.data.objects.remove(cutter,do_unlink=True)
   if data.users==0:bpy.data.meshes.remove(data)
  # Union intersecting road solids in this explicit at-grade split/merge fixture only.
  union_objects=[obj for obj in stage.objects if json.loads(obj.get('wb_metadata','{}')).get('union_group') in ('interchange','parking')]
  if union_objects:
   main=union_objects[0];bpy.context.view_layer.update()
   source_ids=[obj['wb_id'] for obj in union_objects]
   for branch in union_objects[1:]:
    modifier=main.modifiers.new('WB explicit ramp union','BOOLEAN');modifier.operation='UNION';modifier.solver='EXACT';modifier.object=branch
    bpy.context.view_layer.objects.active=main;main.select_set(True);bpy.ops.object.modifier_apply(modifier=modifier.name);main.select_set(False)
    data=branch.data;bpy.data.objects.remove(branch,do_unlink=True)
    if data.users==0:bpy.data.meshes.remove(data)
   main['wb_union_sources']=json.dumps(source_ids)
  # Editable endpoint handles carry identities. Capture must be explicit; regeneration uses graph.
  for cross_id,ends in resolved.items():
   for key,e in ends.items():
    obj=bpy.data.objects.new('WB_handle_'+e['id'],None);stage.objects.link(obj);obj.empty_display_type='ARROWS';obj.empty_display_size=.6;obj.location=e['position'];obj.rotation_euler.z=e['rotation'];obj['wb_endpoint_id']=e['id'];obj['wb_crosswalk_id']=cross_id;obj['wb_endpoint_key']=key;obj['wb_handle_position']=json.dumps(list(obj.location))
 except Exception:delete_collection(stage);raise
 old=bpy.data.collections.get('WB_GENERATED')
 if old:delete_collection(old)
 stage.name='WB_GENERATED'
 for obj in stage.objects:obj.name='WB_'+(obj['wb_id'] if 'wb_id' in obj else 'handle_'+obj['wb_endpoint_id'])
 for obj in stage.objects:
  if obj.type in ('MESH','CURVE'):obj['wb_fingerprint']=object_fingerprint(obj)
 scene.wb_graph=model.dumps(graph);scene['wb_validation']=json.dumps(diagnostics);scene['wb_mesh_digest']=model.mesh_digest(specs)
 parking_sources(scene,graph,reset=force)
 return specs,diagnostics,resolved

class WBEndpoint(bpy.types.PropertyGroup):
 id:StringProperty();crosswalk_id:StringProperty();key:StringProperty()
 station:FloatProperty(name='Anchor station (m)',min=0,default=26)
 opening_width:FloatProperty(name='Opening width (m)',min=.5,default=3.2)
 transition_left:FloatProperty(name='Left shoulder (m)',min=.1,default=1.8)
 transition_right:FloatProperty(name='Right shoulder (m)',min=.1,default=2.4)
 run:FloatProperty(name='Ramp run (m)',min=.1,default=2)
 warning_depth:FloatProperty(name='Warning depth (m)',min=.1,default=.61)
 rotation_offset:FloatProperty(name='Anchor rotation offset',subtype='ANGLE')
 mode:EnumProperty(name='Position ownership',items=[('auto','Curb anchored','Follow approach station'),('manual','Manual','Keep captured position and rotation')],default='auto')
 position:FloatVectorProperty(name='Manual position (m)',size=3)
 rotation:FloatProperty(name='Manual rotation',subtype='ANGLE')
class WBApproach(bpy.types.PropertyGroup):
 id:StringProperty();label:StringProperty();bearing:FloatProperty(name='Bearing',subtype='ANGLE');offset:FloatProperty(name='Lateral offset (m)');half_width:FloatProperty(name='Half width (m)',min=1);length:FloatProperty(name='Length (m)',min=5)
class WBAuxiliary(bpy.types.PropertyGroup):
 id:StringProperty();side:FloatProperty();start:FloatProperty(name='Start station (m)',min=0);taper:FloatProperty(name='Entry taper (m)',min=1);end:FloatProperty(name='End station (m)',min=1);taper_out:FloatProperty(name='Exit taper (m)',min=1);width:FloatProperty(name='Lane width (m)',min=1)
class WBDriveway(bpy.types.PropertyGroup):
 id:StringProperty();side:FloatProperty();station:FloatProperty(name='Station (m)',min=0);width:FloatProperty(name='Driveway width (m)',min=2);depth:FloatProperty(name='Driveway depth (m)',min=1)
class WBSettings(bpy.types.PropertyGroup):
 fixture:EnumProperty(name='Example',items=[('intersection','Connected intersection','Four distinct corner radii and two crosswalks'),('skew','Skewed intersection','One skewed and one offset approach'),('boulevard','Divided boulevard','Turn pocket consumes median, outer edges fixed'),('arterial','Arterial with driveways','Outside pockets and bike lane patches'),('interchange','Ramp continuations','One lane exits and the opposing ramp adds a lane'),('parking','Polygon parking lot','Road connection, planter islands and stall rows')])
 curb_height:FloatProperty(name='Curb reveal (m)',default=.1524,min=.01,max=.5)
 sidewalk_width:FloatProperty(name='Sidewalk width (m)',default=3.2,min=.6)
 spacing:FloatProperty(name='Sample spacing (m)',default=.5,min=.1,max=2)
 guides:BoolProperty(name='Show lane movement guides',default=False)
 radius_NW:FloatProperty(name='NW (m)',default=7,min=.5)
 radius_NE:FloatProperty(name='NE (m)',default=5,min=.5)
 radius_SW:FloatProperty(name='SW (m)',default=9,min=.5)
 radius_SE:FloatProperty(name='SE (m)',default=11,min=.5)
 lane_width:FloatProperty(name='Lane width (m)',default=3.66,min=2)
 median_width:FloatProperty(name='Median width (m)',default=7.5,min=1)
 pocket_start:FloatProperty(name='Pocket start (m)',default=30,min=0)
 taper_length:FloatProperty(name='Taper length (m)',default=25,min=1)
 pocket_end:FloatProperty(name='Pocket end (m)',default=90,min=1)
 median_end:FloatProperty(name='Median end (m)',default=103,min=2)
 nose_length:FloatProperty(name='Nose length (m)',default=5,min=.5)
 nose_shape:EnumProperty(name='Nose shape',items=[('rounded','Rounded','Elliptical cap'),('tapered','Tapered','Triangular tip')])
 auxiliary:CollectionProperty(type=WBAuxiliary)
 driveways:CollectionProperty(type=WBDriveway)
 split_station:FloatProperty(name='Exit split distance (m)',default=60,min=1)
 merge_station:FloatProperty(name='Entry merge distance (m)',default=70,min=1)
 turn_station:FloatProperty(name='Opposing turn distance (m)',default=72,min=1)
 median_setback:FloatProperty(name='Far median nose setback (m)',default=14,min=4)
 ramp_length:FloatProperty(name='Ramp length (m)',default=65,min=10)
 ramp_offset:FloatProperty(name='Ramp lateral offset (m)',default=40,min=5)
 endpoints:CollectionProperty(type=WBEndpoint)
 approaches:CollectionProperty(type=WBApproach)
 endpoint_index:EnumProperty(name='Endpoint',items=[('0','North A',''),('1','North B',''),('2','South A',''),('3','South B','')])
 approach_index:EnumProperty(name='Approach',items=[('0','East',''),('1','North',''),('2','West',''),('3','South','')])

def sync_controls(scene,g):
 if g.get('version')==3:return
 s=scene.wb_controls;s.fixture=g['fixture'];s.curb_height=g['settings']['curb_height'];s.sidewalk_width=g['settings']['sidewalk_width'];s.spacing=g['settings']['sample_spacing'];s.guides=g['settings'].get('show_guides',False);s.endpoints.clear();s.approaches.clear();s.auxiliary.clear();s.driveways.clear()
 if g['fixture']=='parking':return
 if g['fixture']=='interchange':
  for key in ('lane_width','split_station','merge_station','turn_station','median_setback','ramp_length','ramp_offset','taper_length','median_width'):setattr(s,key,g['interchange'][key])
  return
 if g['fixture'] in ('boulevard','arterial'):
  for key in ('lane_width','median_width','pocket_start','taper_length','pocket_end','median_end','nose_length','nose_shape'):setattr(s,key,g['boulevard'][key])
  if g['fixture']=='arterial':
   for a in g['boulevard']['outer_turns']:
    item=s.auxiliary.add()
    for key in ('id','side','start','taper','end','taper_out','width'):setattr(item,key,a[key])
   for d in g['boulevard']['driveways']:
    item=s.driveways.add()
    for key in ('id','side','station','width','depth'):setattr(item,key,d[key])
 else:
  for label,c in g['junction']['corners'].items():setattr(s,'radius_'+label,c['radius'])
  for a in g['junction']['approaches']:
   item=s.approaches.add()
   for key in ('id','label','bearing','offset','half_width','length'):setattr(item,key,a[key])
  for c in g['crosswalks']:
   for key,e in c['endpoints'].items():
    item=s.endpoints.add();item.id=e['id'];item.crosswalk_id=c['id'];item.key=key
    resolved=geometry.resolve_endpoint(g['junction'],e)
    for name in ('station','opening_width','transition_left','transition_right','run','warning_depth','rotation_offset','mode'):setattr(item,name,e.get(name,0))
    item.position=resolved['position'];item.rotation=resolved['rotation']

def set_parameter(target,key,value):
 # Blender UI floats are float32; retain original JSON double when the control is unchanged.
 old=target.get(key)
 if isinstance(old,(float,int)) and isinstance(value,(float,int)) and not isinstance(old,bool):
  if math.isclose(old,value,rel_tol=1e-7,abs_tol=1e-6):return
 target[key]=value

def controls_graph(scene):
 g=model.loads(scene.wb_graph);s=scene.wb_controls
 if g.get('version')==3:return g

 for key,value in [('curb_height',s.curb_height),('sidewalk_width',s.sidewalk_width),('sample_spacing',s.spacing),('show_guides',s.guides)]:set_parameter(g['settings'],key,value)
 if g['fixture']=='parking':return model.validate(g)
 if g['fixture']=='interchange':
  for key in ('lane_width','split_station','merge_station','turn_station','median_setback','ramp_length','ramp_offset','taper_length','median_width'):set_parameter(g['interchange'],key,getattr(s,key))
  g['revision']=g.get('revision',0)+1;return model.validate(g)
 if g['fixture'] in ('boulevard','arterial'):
  for key in ('lane_width','median_width','pocket_start','taper_length','pocket_end','median_end','nose_length','nose_shape'):set_parameter(g['boulevard'],key,getattr(s,key))
  if g['fixture']=='arterial':
   for item in s.auxiliary:
    a=next(x for x in g['boulevard']['outer_turns'] if x['id']==item.id)
    for key in ('start','taper','end','taper_out','width'):set_parameter(a,key,getattr(item,key))
   for item in s.driveways:
    d=next(x for x in g['boulevard']['driveways'] if x['id']==item.id)
    for key in ('station','width','depth'):set_parameter(d,key,getattr(item,key))
 else:
  for label,c in g['junction']['corners'].items():set_parameter(c,'radius',getattr(s,'radius_'+label))
  for item in s.approaches:
   a=next(a for a in g['junction']['approaches'] if a['id']==item.id)
   for key in ('bearing','offset','half_width','length'):set_parameter(a,key,getattr(item,key))
  for item in s.endpoints:
   e=next(c for c in g['crosswalks'] if c['id']==item.crosswalk_id)['endpoints'][item.key]
   for key in ('station','opening_width','transition_left','transition_right','run','warning_depth','rotation_offset','mode'):set_parameter(e,key,getattr(item,key))
   if item.mode=='manual':e['position']=list(item.position);e['rotation']=item.rotation
 g['revision']=g.get('revision',0)+1;return model.validate(g)

class WB_OT_curve_profile(bpy.types.Operator):
 bl_idname='wb.curve_profile';bl_label='Create selected curve profile (copy)';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  source=context.active_object
  if not source or source.type!='CURVE':self.report({'ERROR'},'Select an editable curve first');return {'CANCELLED'}
  from . import nodes
  import uuid
  groups=nodes.create_groups();obj=source.copy();obj.data=source.data.copy();obj.modifiers.clear();obj.name='WB_Profile_'+source.name;context.scene.collection.objects.link(obj);obj['wb_id']='road-'+uuid.uuid4().hex;obj['wb_source_object']=source.name
  modifier=obj.modifiers.new('WB independent width profile','NODES');modifier.node_group=groups[0]
  for socket in groups[0].interface.items_tree:
   if socket.item_type=='SOCKET' and socket.in_out=='INPUT':
    if socket.name in ('Left width','Right width'):modifier[socket.identifier]=3.
    elif socket.name=='Material':modifier[socket.identifier]=material('asphalt')
  source.select_set(False);obj.select_set(True);context.view_layer.objects.active=obj
  self.report({'INFO'},'Copied alignment; edit left/right widths in its modifier. Terrain integration is separate.');return {'FINISHED'}
class WB_OT_capture_parking(bpy.types.Operator):
 bl_idname='wb.capture_parking';bl_label='Apply edited lot / island outlines';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  try:
   g=model.loads(context.scene.wb_graph)
   if g['fixture']!='parking':raise ValueError('Load the parking example first')
   col=bpy.data.collections.get('WB_PARKING_OUTLINES')
   for obj in col.objects:
    entity=g['parking'] if obj['wb_parking_kind']=='lot' else next(x for x in g['parking']['islands'] if x['id']==obj['wb_parking_id'])
    entity['vertices']=[list((obj.matrix_world @ p.co.xyz)[:2]) for p in obj.data.splines[0].points]
   g['revision']+=1;regenerate(context.scene,g);sync_controls(context.scene,g)
  except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
  return {'FINISHED'}
class WB_OT_add_planter(bpy.types.Operator):
 bl_idname='wb.add_planter';bl_label='Add selected polygon as planter';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  try:
   source=context.active_object
   if not source or source.type!='CURVE' or not source.data.splines or source.data.splines[0].type!='POLY':raise ValueError('Select a closed POLY curve with at least three points')
   spl=source.data.splines[0]
   if not spl.use_cyclic_u or len(spl.points)<3:raise ValueError('Planter outline must be closed')
   import uuid
   g=model.loads(context.scene.wb_graph)
   if g['fixture']!='parking':raise ValueError('Load the parking example first')
   vertices=[list((source.matrix_world @ p.co.xyz)[:2]) for p in spl.points]
   if geometry.area(vertices)<0:vertices.reverse()
   g['parking']['islands'].append({'id':'planter-'+uuid.uuid4().hex,'vertices':vertices});g['revision']+=1;regenerate(context.scene,g)
  except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
  return {'FINISHED'}
class WB_OT_load(bpy.types.Operator):
 bl_idname='wb.load_pilot';bl_label='Generate mesh test fixture';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  try:
   g=model.loads((Path(__file__).parent/'fixtures'/(context.scene.wb_controls.fixture+'.json')).read_text());regenerate(context.scene,g,force=True);sync_controls(context.scene,g)
  except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
  return {'FINISHED'}
class WB_OT_rebuild(bpy.types.Operator):
 bl_idname='wb.rebuild';bl_label='Apply controls / regenerate';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  try:regenerate(context.scene,controls_graph(context.scene))
  except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
  return {'FINISHED'}
class WB_OT_capture(bpy.types.Operator):
 bl_idname='wb.capture_endpoint';bl_label='Capture selected endpoint handle';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  obj=context.active_object
  if not obj or 'wb_endpoint_id' not in obj:self.report({'ERROR'},'Select an endpoint arrow handle');return {'CANCELLED'}
  for item in context.scene.wb_controls.endpoints:
   if item.id==obj['wb_endpoint_id']:item.position=obj.location;item.rotation=obj.rotation_euler.z;item.mode='manual';return {'FINISHED'}
  return {'CANCELLED'}
class WB_OT_legacy(bpy.types.Operator):
 bl_idname='wb.legacy';bl_label='Show / hide WB geometry';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  col=bpy.data.collections.get('WB_GENERATED')
  if col:col.hide_viewport=not col.hide_viewport;col.hide_render=col.hide_viewport
  return {'FINISHED'}
class WB_OT_export(bpy.types.Operator,ExportHelper):
 bl_idname='wb.export_graph';bl_label='Export editable graph';filename_ext='.json';filter_glob:StringProperty(default='*.json',options={'HIDDEN'})
 def execute(self,context):
  try:Path(self.filepath).write_text(model.dumps(controls_graph(context.scene)))
  except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
  return {'FINISHED'}
class WB_OT_import(bpy.types.Operator,ImportHelper):
 bl_idname='wb.import_graph';bl_label='Import editable graph';filter_glob:StringProperty(default='*.json',options={'HIDDEN'})
 def execute(self,context):
  try:g=model.loads(Path(self.filepath).read_text());regenerate(context.scene,g,force=True);sync_controls(context.scene,g)
  except Exception as e:self.report({'ERROR'},str(e));return {'CANCELLED'}
  return {'FINISHED'}
class WB_OT_diagnostics(bpy.types.Operator,ExportHelper):
 bl_idname='wb.export_diagnostics';bl_label='Save diagnostics';filename_ext='.json';filter_glob:StringProperty(default='*.json',options={'HIDDEN'})
 def execute(self,context):
  from . import diagnostics
  Path(self.filepath).write_text(json.dumps(diagnostics.inspect_scene(context.scene),indent=2));return {'FINISHED'}

class WB_PT_panel(bpy.types.Panel):
 bl_label='Mesh test fixtures';bl_idname='WB_PT_panel';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab Debug';bl_options={'DEFAULT_CLOSED'}
 @classmethod
 def poll(cls,context):
  from .native_extension import is_roadlab_scene
  return not is_roadlab_scene(context.scene)
 def draw(self,context):
  l=self.layout;s=context.scene.wb_controls;l.label(text='Standalone mesh tests; no road/terrain editing.',icon='INFO');box=l.box();box.label(text='Test setup');box.prop(s,'fixture');box.operator('wb.load_pilot');box.operator('wb.curve_profile')
  if not context.scene.wb_graph:return
  box=l.box();box.label(text='Road defaults');box.prop(s,'curb_height');box.prop(s,'sidewalk_width');box.prop(s,'spacing',text='Curve sample spacing (m)')
  g=json.loads(context.scene.wb_graph)
  if g.get('version')==3:
   l.label(text='Edit terrain in Terrain sculpting')
   box=l.box();box.label(text='Scene files');row=box.row();row.operator('wb.import_graph');row.operator('wb.export_graph');box.operator('wb.export_diagnostics');return
  if g['fixture'] in ('boulevard','arterial'):
   for key in (('lane_width','median_width') if g['fixture']=='arterial' else ('lane_width','median_width','pocket_start','taper_length','pocket_end','median_end','nose_length','nose_shape')):l.prop(s,key)
  elif g['fixture']=='parking':
   l.label(text='Edit curves in WB_PARKING_OUTLINES')
   l.operator('wb.capture_parking');l.operator('wb.add_planter')
  elif g['fixture']=='interchange':
   l.prop(s,'guides')
   for key in ('lane_width','split_station','merge_station','turn_station','median_setback','ramp_length','ramp_offset','taper_length','median_width'):l.prop(s,key)
  else:
   l.label(text='Corner radii')
   for pair in [('NW','NE'),('SW','SE')]:
    row=l.row()
    for label in pair:row.prop(s,'radius_'+label)
   l.prop(s,'guides')
  l.operator('wb.rebuild');l.operator('wb.legacy')
  box=l.box();box.label(text='Scene files');row=box.row();row.operator('wb.import_graph');row.operator('wb.export_graph');box.operator('wb.export_diagnostics')
  for message in json.loads(context.scene.get('wb_validation','[]')):l.label(text=message,icon='ERROR')
class WB_PT_approach(bpy.types.Panel):
 bl_label='Intersection approaches';bl_parent_id='WB_PT_panel';bl_idname='WB_PT_approach';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab Debug';bl_options={'DEFAULT_CLOSED'}
 def draw(self,context):
  l=self.layout;s=context.scene.wb_controls;l.prop(s,'approach_index');i=int(s.approach_index)
  if i<len(s.approaches):
   a=s.approaches[i]
   for key in ('bearing','offset','half_width','length'):l.prop(a,key)
class WB_PT_endpoint(bpy.types.Panel):
 bl_label='Crosswalk endpoints';bl_parent_id='WB_PT_panel';bl_idname='WB_PT_endpoint';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab Debug';bl_options={'DEFAULT_CLOSED'}
 def draw(self,context):
  l=self.layout;s=context.scene.wb_controls;l.prop(s,'endpoint_index');i=int(s.endpoint_index)
  if i<len(s.endpoints):
   e=s.endpoints[i];l.label(text=e.id);l.prop(e,'mode')
   for key in ('station','opening_width','transition_left','transition_right','run','warning_depth','rotation_offset'):l.prop(e,key)
   if e.mode=='manual':l.prop(e,'position');l.prop(e,'rotation')
   l.operator('wb.capture_endpoint');l.label(text='Off-curb manual anchors show warnings')
class WB_PT_auxiliary(bpy.types.Panel):
 bl_label='Turn lanes and driveways';bl_parent_id='WB_PT_panel';bl_idname='WB_PT_auxiliary';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab Debug';bl_options={'DEFAULT_CLOSED'}
 def draw(self,context):
  l=self.layout;s=context.scene.wb_controls
  for a in s.auxiliary:
   box=l.box();box.label(text=a.id)
   for key in ('start','taper','end','taper_out','width'):box.prop(a,key)
  for d in s.driveways:
   box=l.box();box.label(text=d.id)
   for key in ('station','width','depth'):box.prop(d,key)
classes=(WBEndpoint,WBApproach,WBAuxiliary,WBDriveway,WBSettings,WB_OT_curve_profile,WB_OT_capture_parking,WB_OT_add_planter,WB_OT_load,WB_OT_rebuild,WB_OT_capture,WB_OT_legacy,WB_OT_export,WB_OT_import,WB_OT_diagnostics,WB_PT_panel,WB_PT_approach,WB_PT_endpoint,WB_PT_auxiliary)
def register():
 from . import map_settings
 map_settings.register()
 for cls in classes:bpy.utils.register_class(cls)
 bpy.types.Scene.wb_graph=StringProperty(default='');bpy.types.Scene.wb_controls=PointerProperty(type=WBSettings)
 from . import terrain_ui
 terrain_ui.register()
 from . import bridge_ui
 bridge_ui.register()
 from . import native_layers
 native_layers.register()
 from . import native_extension
 native_extension.register()
 from . import road_core
 road_core.register()
 from . import lane_editor
 lane_editor.register()
 from . import marking_stamp
 marking_stamp.register()
 from . import road_connections
 road_connections.register()
 from . import surface_bounds
 surface_bounds.register()
def unregister():
 from . import surface_bounds
 surface_bounds.unregister()
 from . import road_connections
 road_connections.unregister()
 from . import marking_stamp
 marking_stamp.unregister()
 from . import lane_editor
 lane_editor.unregister()
 from . import road_core
 road_core.unregister()
 from . import native_extension
 native_extension.unregister()
 from . import native_layers
 native_layers.unregister()
 from . import bridge_ui
 bridge_ui.unregister()
 from . import terrain_ui
 terrain_ui.unregister()
 for name in ('wb_controls','wb_graph'):delattr(bpy.types.Scene,name)
 for cls in reversed(classes):bpy.utils.unregister_class(cls)
 from . import map_settings
 map_settings.unregister()
