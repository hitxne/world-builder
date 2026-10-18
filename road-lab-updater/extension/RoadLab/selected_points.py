"""Selection-scoped road editing, with explicit batch application and undo."""
import json
import bpy
from bpy.props import FloatProperty,StringProperty,EnumProperty
from mathutils import Vector
from . import point_settings as data


def road(context):
    obj=context.scene.wb_native.road
    return obj if obj and obj.get('roadlab_new_core') else None

def indices(context):
    obj=road(context)
    return data.selected(context,obj) if obj else []

def junctions(context):
    obj=road(context)
    if not obj:return []
    available={tuple(item['junction']) for item in json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[]) if 'junction' in item}
    return sorted({tuple(round(v,6) for v in data.points(obj)[i].co[:3]) for i in indices(context)} & available)

def bend_points(context):
    obj=road(context)
    if not obj:return []
    selected={tuple(round(v,6) for v in data.points(obj)[i].co[:3]) for i in indices(context)};neighbors={co:set() for co in selected}
    for spline in obj.data.splines:
        coords=[tuple(round(v,6) for v in p.co[:3]) for p in spline.points]
        for i in range(len(coords) if spline.use_cyclic_u else len(coords)-1):
            a,b=coords[i],coords[(i+1)%len(coords)]
            if a in neighbors:neighbors[a].add(b)
            if b in neighbors:neighbors[b].add(a)
    junction_nodes={tuple(p) for p in json.loads(obj.get('roadlab_core_report','{}')).get('junction_nodes',[])}
    result=[]
    for co,arms in neighbors.items():
        if len(arms)!=2 or co in junction_nodes:continue
        a,b=[Vector((p[0]-co[0],p[1]-co[1])).normalized() for p in arms]
        if abs(a.x*b.y-a.y*b.x)>1e-5:result.append(co)
    return sorted(result)


def bend_radius_get(self):
    context=bpy.context;obj=road(context);selected=bend_points(context)
    if not obj or not selected:return 8.
    from .road_core import values
    defaults=values(obj);overrides=data.junction_overrides(obj);items=data.records(obj)
    limits=json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[]);radii=[]
    for co in selected:
        i=next(i for i,item in enumerate(items) if tuple(item['co'])==co)
        inner=next((row['corner'] for row in limits if tuple(row.get('junction',()))==co and row.get('kind','interior')=='interior'),'NW')
        half=data.width(obj,i,defaults['road width'])/2
        radii.append(max(half+.02,items[i].get('bend_radius',overrides.get(co,{}).get(inner,defaults['corner '+inner])+half)))
    return sum(radii)/len(radii)


def bend_radius_set(self,value):
    context=bpy.context;obj=road(context);selected=set(bend_points(context))
    if not obj or not selected:return
    from .road_core import values
    default=values(obj)['road width'];items=data.sync(obj)
    for i,item in enumerate(items):
        if tuple(item['co']) in selected:item['bend_radius']=max(value,data.width(obj,i,default)/2+.02)
    data.save(obj,items);notify(context,obj)


def notify(context,obj):
    from . import road_core
    obj.data.update_tag();obj.update_tag()
    # Parameter dialogs commit once; drag-time scheduling remains in the core.
    key=context.scene.as_pointer();previous=road_core._pending.get(key)
    road_core._pending[key]=(context.scene,{obj}|(previous[1] if previous else set()))
    road_core.flush_pending()


def summarize(values):
    if not values:return '—'
    if max(values)-min(values)<1e-5:return f'{values[0]:.2f} m'
    return f'Mixed ({min(values):.2f}–{max(values):.2f} m)'


class PointOperator:
    bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return bool(indices(context))


class ROADLAB_OT_point_width(PointOperator,bpy.types.Operator):
    bl_idname='roadlab.point_width';bl_label='Set selected point width'
    bl_description='Set an absolute road width at selected points; interpolate to adjacent points'
    value:FloatProperty(name='Width (m)',min=.25,default=6.)
    def invoke(self,context,event):
        from .road_core import values
        obj=road(context);default=values(obj)['road width'];selected=indices(context)
        self.value=sum(data.widths(obj,selected,default))/len(selected)
        return context.window_manager.invoke_props_dialog(self,width=300)
    def draw(self,context):
        self.layout.label(text=f'Applies to {len(indices(context))} selected point(s)')
        self.layout.prop(self,'value')
        self.layout.label(text='Transitions smoothly between points')
    def execute(self,context):
        obj=road(context);selected=indices(context);items=data.sync(obj)
        for i in selected:items[i]['width']=self.value
        data.save(obj,items);notify(context,obj);return {'FINISHED'}


class ROADLAB_OT_point_height(PointOperator,bpy.types.Operator):
    bl_idname='roadlab.point_height';bl_label='Edit selected point height'
    bl_description='Set world height or shift selected points while preserving their relative heights'
    mode:EnumProperty(items=[('SET','Set height','Set all selected points to the same world height'),('OFFSET','Raise / lower','Add the same height change, preserving relative elevations')])
    value:FloatProperty(name='Height (m)',default=0.)
    def invoke(self,context,event):
        obj=road(context);ps=data.points(obj);selected=indices(context)
        self.value=sum((obj.matrix_world@Vector(ps[i].co[:3])).z for i in selected)/len(selected) if self.mode=='SET' else 0.
        return context.window_manager.invoke_props_dialog(self,width=300)
    def draw(self,context):
        self.layout.label(text=f'Applies to {len(indices(context))} selected point(s)')
        self.layout.prop(self,'value',text='World height (m)' if self.mode=='SET' else 'Height change (m)')
    def execute(self,context):
        obj=road(context);ps=data.points(obj);inverse=obj.matrix_world.inverted()
        for i in indices(context):
            world=obj.matrix_world@Vector(ps[i].co[:3]);world.z=self.value if self.mode=='SET' else world.z+self.value
            ps[i].co=(*tuple(inverse@world),1)
        notify(context,obj);return {'FINISHED'}


class ROADLAB_OT_point_corner(PointOperator,bpy.types.Operator):
    bl_idname='roadlab.point_corner';bl_label='Set selected corner radius'
    bl_description='Override this corner at selected bends or junctions; shared coincident points use the same junction setting'
    corner:StringProperty(default='NW')
    value:FloatProperty(name='Radius (m)',default=4.,min=.02)
    @classmethod
    def poll(cls,context):return bool(junctions(context))
    def invoke(self,context,event):
        from .road_core import values
        obj=road(context);default=values(obj)['corner '+self.corner];overrides=data.junction_overrides(obj)
        applicable={tuple(x['junction']) for x in json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[]) if x['corner']==self.corner} & set(junctions(context))
        self.value=sum(overrides.get(p,{}).get(self.corner,default) for p in applicable)/len(applicable)
        return context.window_manager.invoke_props_dialog(self,width=300)
    def draw(self,context):
        self.layout.label(text=f'{self.corner}: {len(junctions(context))} selected corner point(s)')
        self.layout.prop(self,'value')
        self.layout.label(text='Stored radius is kept if the corner merges')
    def execute(self,context):
        obj=road(context);selected=set(junctions(context));items=data.sync(obj)
        available={tuple(x['junction']) for x in json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[]) if x.get('corner')==self.corner}
        selected &= available
        effective=data.junction_overrides(obj)
        for item in items:
            if tuple(item['co']) in selected:
                if 'bend_radius' in item:item.setdefault('corners',{}).update(effective.get(tuple(item['co']),{}))
                item.pop('bend_radius',None);item.setdefault('corners',{})[self.corner]=self.value
        data.save(obj,items);notify(context,obj);return {'FINISHED'}


class ROADLAB_OT_corner_lift(PointOperator,bpy.types.Operator):
    bl_idname='roadlab.corner_lift';bl_label='Lift selected corner'
    bl_description='Add a smooth local elevation offset at this corner; the curve remains the road height reference'
    corner:EnumProperty(items=[(v,v,v+' corner') for v in ('NW','NE','SW','SE')])
    value:FloatProperty(name='Corner lift (m)',default=0.,soft_min=-5,soft_max=5)
    @classmethod
    def poll(cls,context):return bool(junctions(context))
    def invoke(self,context,event):
        obj=road(context);lifts=data.corner_lifts(obj);selected=junctions(context)
        self.value=sum(lifts.get(p,{}).get(self.corner,0.) for p in selected)/len(selected)
        return context.window_manager.invoke_props_dialog(self,width=300)
    def draw(self,context):
        self.layout.label(text=self.corner+' elevation relative to the road')
        self.layout.prop(self,'value')
    def execute(self,context):
        obj=road(context);selected=set(junctions(context));items=data.sync(obj)
        available={tuple(x['junction']) for x in json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[]) if x.get('corner')==self.corner and x.get('exposed',True)}
        for item in items:
            if tuple(item['co']) in selected & available:item.setdefault('corner_lifts',{})[self.corner]=self.value
        data.save(obj,items);notify(context,obj);return {'FINISHED'}


class ROADLAB_OT_point_reset(PointOperator,bpy.types.Operator):
    bl_idname='roadlab.point_reset';bl_label='Use network defaults'
    field:EnumProperty(items=[('WIDTH','Width','Clear width overrides at selected points'),('CORNERS','Corners','Clear radius overrides for selected junctions')])
    def execute(self,context):
        obj=road(context);items=data.sync(obj)
        if self.field=='WIDTH':
            ps=data.points(obj)
            for i in indices(context):items[i].pop('width',None);ps[i].radius=1.
        else:
            selected=set(junctions(context))
            for item in items:
                if tuple(item['co']) in selected:item.pop('corners',None);item.pop('corner_lifts',None);item.pop('bend_radius',None)
        data.save(obj,items);notify(context,obj);return {'FINISHED'}


class ROADLAB_OT_choose_corner(bpy.types.Operator):
    bl_idname='roadlab.choose_corner';bl_label='Select corner';bl_options={'INTERNAL'}
    corner:EnumProperty(items=[(v,v,v+' corner') for v in ('NW','NE','SW','SE')])
    def execute(self,context):
        context.scene.roadlab_active_corner=self.corner;return {'FINISHED'}


class ROADLAB_PT_selected(bpy.types.Panel):
    bl_label='Selected points';bl_idname='ROADLAB_PT_selected';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_order=-1;bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return road(context) is not None
    def draw(self,context):
        selected=indices(context)
        if selected:
            self.layout.label(text=f'{len(selected)} point(s) · {len(junctions(context))} with corners',icon='EDITMODE_HLT')
            self.layout.label(text='Edits apply only to this selection')
        else:
            self.layout.label(text='Select road points in Edit Mode')
            if context.mode!='EDIT_CURVE':self.layout.operator('wb.edit_road_curve',text='Edit road points',icon='EDITMODE_HLT')


class SelectedPanel:
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_parent_id='ROADLAB_PT_selected';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return bool(indices(context))


class ROADLAB_PT_point_geometry(SelectedPanel,bpy.types.Panel):
    bl_label='Road geometry';bl_idname='ROADLAB_PT_point_geometry';bl_order=0
    def draw(self,context):
        from .road_core import values
        obj=road(context);ps=data.points(obj);selected=indices(context);default=values(obj)['road width']
        row=self.layout.row(align=True);row.operator('roadlab.point_width',text='Width: '+summarize(data.widths(obj,selected,default)))
        row.operator('roadlab.point_reset',text='',icon='LOOP_BACK').field='WIDTH'
        if bend_points(context):
            self.layout.prop(context.scene,'roadlab_bend_radius',text='Bend radius (m)',slider=True)
            self.layout.label(text='Centerline radius · keeps road width')
            bends=set(bend_points(context));limits=json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[])
            if any(tuple(c.get('junction',())) in bends and c['applied']<c['requested']-1e-4 for c in limits):self.layout.label(text='Limited by adjacent points',icon='INFO')
        self.layout.label(text='Move points with G, then Z for elevation')
        self.layout.label(text='Reset arrow restores the network width')


class ROADLAB_PT_point_corners(SelectedPanel,bpy.types.Panel):
    bl_label='Corners';bl_idname='ROADLAB_PT_point_corners';bl_order=1
    @classmethod
    def poll(cls,context):return bool(junctions(context))
    def draw(self,context):
        from .road_core import values
        obj=road(context);selected=junctions(context);defaults=values(obj);overrides=data.junction_overrides(obj)
        limits=json.loads(obj.get('roadlab_core_report','{}')).get('radius_limits',[])
        relevant=[item for item in limits if tuple(item.get('junction',())) in selected]
        available=[c for c in ('NW','NE','SW','SE') if any(x['corner']==c for x in relevant)]
        active=context.scene.roadlab_active_corner
        if active not in available:active=available[0]
        self.layout.label(text='Choose a corner')
        for pair in [('NW','NE'),('SW','SE')]:
            if not any(c in available for c in pair):continue
            row=self.layout.row(align=True)
            for corner in pair:
                if corner not in available:row.label(text='');continue
                row.operator('roadlab.choose_corner',text=corner,depress=corner==active).corner=corner
        current_items=[x for x in relevant if x['corner']==active]
        applicable=sorted({tuple(x['junction']) for x in current_items})
        kinds={x.get('kind','interior') for x in current_items}
        kind='Outer' if kinds=={'exterior'} else 'Inner' if kinds=={'interior'} else 'Corner'
        self.layout.label(text=f'{active} · {kind} · {len(applicable)} point(s)')
        current=[overrides.get(p,{}).get(active,defaults['corner '+active]) for p in applicable]
        self.layout.operator('roadlab.point_corner',text='Radius: '+summarize(current)).corner=active
        exposed={tuple(x['junction']) for x in current_items if x.get('exposed',True)}
        if exposed:
            lifts=data.corner_lifts(obj);heights=[lifts.get(p,{}).get(active,0.) for p in sorted(exposed)]
            self.layout.operator('roadlab.corner_lift',text='Lift: '+summarize(heights)).corner=active
        self.layout.label(text='Directions follow road-local X/Y')
        for item in current_items:
            if item['applied']<item['requested']-1e-5:
                self.layout.label(text=f"{item['corner']}: limited to {item['applied']:.2f} m",icon='INFO')
        self.layout.operator('roadlab.point_reset',text='Reset all selected corners',icon='LOOP_BACK').field='CORNERS'


classes=(ROADLAB_OT_point_width,ROADLAB_OT_point_height,ROADLAB_OT_point_corner,ROADLAB_OT_corner_lift,ROADLAB_OT_point_reset,ROADLAB_OT_choose_corner,ROADLAB_PT_selected,ROADLAB_PT_point_geometry,ROADLAB_PT_point_corners)
def register():
    bpy.types.Scene.roadlab_bend_radius=FloatProperty(name='Bend radius',description='Round selected road bends with a centerline radius; road width is preserved and available length limits the result',min=.02,soft_max=50.,get=bend_radius_get,set=bend_radius_set)
    bpy.types.Scene.roadlab_active_corner=StringProperty(default='NW')
    for cls in classes:bpy.utils.register_class(cls)
def unregister():
    del bpy.types.Scene.roadlab_bend_radius
    del bpy.types.Scene.roadlab_active_corner
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
