import bpy,json,copy,math
from bpy.props import EnumProperty,FloatProperty,IntProperty,PointerProperty
from . import bridge_supports,network
_items={}
def roads(self,context):
 try:g=json.loads(context.scene.wb_graph)
 except Exception:return [('NONE','Load connected world','')]
 key=tuple((r['id'],r.get('name',r['id'])) for r in g.get('roads',[]) if r.get('terrain_mode')=='bridge')
 if key not in _items:_items[key]=[(id,name,'Elevated bridge alignment') for id,name in key] or [('NONE','No bridge roads','')]
 return _items[key]

def change_bridge(self,context):
 try:
  g=json.loads(context.scene.wb_graph)
  for key,value in g.get('bridge_support_defaults',{}).get(self.road_id,{}).items():setattr(self,key,value)
  self.index=0;context.scene['wb_selected_support_id']=''
 except (ValueError,KeyError,AttributeError):pass

class WBBridgeSettings(bpy.types.PropertyGroup):
 road_id:EnumProperty(name='Bridge',items=roads,update=change_bridge)
 spacing:FloatProperty(name='Support spacing (m)',default=34,min=3)
 diameter:FloatProperty(name='Column diameter (m)',default=1.3,min=.2)
 cap_width:FloatProperty(name='Cap span across road (m)',default=6.5,min=.2)
 cap_length:FloatProperty(name='Cap length along road (m)',default=2.2,min=.2)
 cap_height:FloatProperty(name='Cap thickness (m)',default=1,min=.1)
 clearance:FloatProperty(name='Base edge clearance (m)',default=.25,min=0)
 index:IntProperty(name='Support index',default=0,min=0)
 station:FloatProperty(name='Distance along bridge (m)',default=85,min=0)
 offset:FloatProperty(name='Lateral offset (m)',default=0)

def selected(context):
 g=json.loads(context.scene.wb_graph);s=context.scene.wb_bridge;points=[p for p in g.get('bridge_supports',[]) if p['road_id']==s.road_id]
 if s.index>=len(points):raise ValueError('Select an existing support index and load it')
 return g,points[s.index]

class WB_OT_space_supports(bpy.types.Operator):
 bl_idname='wb.space_bridge_supports';bl_label='Generate supports';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  from .terrain_ui import terrain_object
  from .bridge_blender import refresh
  try:
   g=json.loads(context.scene.wb_graph);s=context.scene.wb_bridge;road=next(r for r in g['roads'] if r['id']==s.road_id);length=network.road_samples(road,g['settings']['sample_spacing'])[-1][0];points=[];skipped=[]
   defaults={k:getattr(s,k) for k in ('spacing','diameter','cap_width','cap_length','cap_height','clearance')};g.setdefault('bridge_support_defaults',{})[s.road_id]=defaults
   overrides={p['id']:p for p in g.get('bridge_supports',[]) if p['road_id']==s.road_id and p.get('manual_override')}
   obstacles=network.build(g)[0];station=s.spacing/2;i=0
   while station<length:
    p={'id':'pier-'+s.road_id+'-'+str(i),'road_id':s.road_id,'station':station,'offset':0,**{k:v for k,v in defaults.items() if k!='spacing'}}
    if p['id'] in overrides:p=copy.deepcopy(overrides.pop(p['id']))
    try:bridge_supports.build(g,p,lambda x,y:-100);bridge_supports.check_placement(g,p,obstacles);points.append(p)
    except ValueError as exc:
     if p.get('manual_override'):raise
     skipped.append(str(exc))
    station+=s.spacing;i+=1
   for p in overrides.values():bridge_supports.check_placement(g,p,obstacles);points.append(p)
   if not points:raise ValueError('No valid support positions at this spacing; change spacing or individual placement')
   g['bridge_supports']=[p for p in g.get('bridge_supports',[]) if p['road_id']!=s.road_id]+points
   network.validate(g);refresh(context.scene,terrain_object(),g);context.scene['wb_support_skipped']=json.dumps(skipped);s.index=0;s.station=points[0]['station'];s.offset=0
   self.report({'INFO'},f'Created {len(points)} supports; skipped {len(skipped)} blocked positions')
  except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
  return {'FINISHED'}

class WB_OT_load_support(bpy.types.Operator):
 bl_idname='wb.load_bridge_support';bl_label='Read support'
 def execute(self,context):
  try:
   g,p=selected(context);s=context.scene.wb_bridge
   for key in ('station','offset','diameter','cap_width','cap_length','cap_height','clearance'):setattr(s,key,p.get(key,.25 if key=='clearance' else 0))
   context.scene['wb_selected_support_id']=p['id']
  except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
  return {'FINISHED'}

class WB_OT_move_support(bpy.types.Operator):
 bl_idname='wb.move_bridge_support';bl_label='Move support';bl_options={'REGISTER','UNDO'}
 def execute(self,context):
  from .terrain_ui import terrain_object
  from .bridge_blender import refresh
  try:
   g,p=selected(context);s=context.scene.wb_bridge
   if context.scene.get('wb_selected_support_id')!=p['id']:raise ValueError('Load this individual support before applying changes')
   for key in ('station','offset','diameter','cap_width','cap_length','cap_height','clearance'):p[key]=getattr(s,key)
   p['manual_override']=True
   bridge_supports.check_placement(g,p);network.validate(g);refresh(context.scene,terrain_object(),g)
  except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
  return {'FINISHED'}

class WB_PT_bridge(bpy.types.Panel):
 bl_label='Bridge supports';bl_idname='WB_PT_bridge';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
 @classmethod
 def poll(cls,context):
  from .native_extension import is_roadlab_scene
  return not is_roadlab_scene(context.scene)
 def draw(self,context):
  l=self.layout;s=context.scene.wb_bridge
  if not context.scene.wb_graph:l.label(text='Load a connected world first');return
  l.prop(s,'road_id')
  box=l.box();box.label(text='Support shape')
  for key in ('diameter','cap_width','cap_length','cap_height'):box.prop(s,key)
  box=l.box();box.label(text='Automatic placement')
  box.prop(s,'spacing');box.prop(s,'clearance');box.operator('wb.space_bridge_supports')
  box=l.box();box.label(text='Individual placement')
  row=box.row(align=True);row.prop(s,'index');row.operator('wb.load_bridge_support')
  box.prop(s,'station');box.prop(s,'offset');box.operator('wb.move_bridge_support')
  for warning in json.loads(context.scene.get('wb_support_skipped','[]'))[:3]:l.label(text=warning,icon='ERROR')

classes=(WBBridgeSettings,WB_OT_space_supports,WB_OT_load_support,WB_OT_move_support,WB_PT_bridge)
def register():
 for cls in classes:bpy.utils.register_class(cls)
 bpy.types.Scene.wb_bridge=PointerProperty(type=WBBridgeSettings)
def unregister():
 del bpy.types.Scene.wb_bridge
 for cls in reversed(classes):bpy.utils.unregister_class(cls)
