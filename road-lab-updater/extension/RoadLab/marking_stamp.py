"""Surface-projected manual road decals, anchored to editable road segments."""
import bpy,json,math,hashlib
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
from bpy.props import EnumProperty,FloatProperty,PointerProperty,BoolProperty
from . import lane_markings,point_settings

_views={};_preview=None;_draw=None;_trees={}
ASSETS=[(key,row['label'],row['category']) for key,row in lane_markings.manifest().items()]

def road(context):
    obj=context.active_object
    return obj if obj and obj.type=='CURVE' and obj.get('roadlab_new_core') else None

def records(obj):return json.loads(obj.get('roadlab_manual_markings','[]'))

def projection(obj):
    helper=obj.get('roadlab_core_mesh')
    if helper is None or not helper.data.polygons:return None
    mesh=helper.data;key=obj.as_pointer();signature=(mesh.as_pointer(),obj.get('roadlab_core_signature'))
    cached=_trees.get(key)
    if cached and cached[0]==signature:return cached[1]
    tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[list(p.vertices) for p in mesh.polygons])
    if len(_trees)>64:_trees.clear()
    _trees[key]=(signature,tree);return tree

def sample(tree,p):
    hits=[];origin=p.z+10000
    for _ in range(32):
        hit,n,face,d=tree.ray_cast(Vector((p.x,p.y,origin)),Vector((0,0,-1)),20000)
        if hit is None:break
        hits.append((abs(hit.z-p.z),hit,n));origin=hit.z-.001
    if not hits:return None
    _,hit,n=min(hits,key=lambda h:h[0]);return hit+n*.008

def anchor(obj,p):
    if obj.mode=='EDIT':obj.update_from_editmode()
    items=point_settings.sync(obj);ps=point_settings.points(obj);best=None;offset=0
    for spline in obj.data.splines:
        count=len(spline.points)
        for i in range(count if spline.use_cyclic_u else count-1):
            a,b=offset+i,offset+(i+1)%count;pa,pb=Vector(ps[a].co[:3]),Vector(ps[b].co[:3]);delta=pb-pa;length=delta.xy.length
            if length<1e-6:continue
            t=max(0.,min(1.,(p.xy-pa.xy).dot(delta.xy)/length**2));q=pa+delta*t;distance=(q-p).length
            if best is None or distance<best[0]:best=(distance,{'endpoints':[items[a]['id'],items[b]['id']],'t':t,'lateral':(p.xy-q.xy).dot(Vector((delta.y,-delta.x))/length)})
        offset+=count
    if best is None:raise ValueError('Road has no usable segment')
    return best[1]

def placement(obj,stamp):
    items=point_settings.records(obj);lookup={r['id']:i for i,r in enumerate(items)};ps=point_settings.points(obj)
    if any(v not in lookup for v in stamp['endpoints']):return None
    a,b=[Vector(ps[lookup[v]].co[:3]) for v in stamp['endpoints']];d=b-a;length=d.xy.length
    if length<1e-6:return None
    f=d.xy/length;r=Vector((f.y,-f.x));p=a+d*stamp['t'];p.x+=r.x*stamp['lateral'];p.y+=r.y*stamp['lateral']
    angle=stamp.get('rotation',0.);forward=Vector((f.x*math.cos(angle)-f.y*math.sin(angle),f.x*math.sin(angle)+f.y*math.cos(angle)))
    w,h=lane_markings.manifest()[stamp['asset']]['physical_canvas_m'];scale=stamp.get('scale',1.)
    return {'asset':stamp['asset'],'center':list(p),'forward':list(forward),'size':[w*scale,h*scale]}

def rebuild(obj,force=False):
    stamps=records(obj);helper=obj.get('roadlab_core_mesh');target=obj.get('roadlab_manual_marking_object')
    if helper is None or not stamps:return
    signature=hashlib.sha256(json.dumps(['stamp-erase-v1',stamps,obj.get('roadlab_core_signature'),helper.data.as_pointer()]).encode()).hexdigest()
    owned=target is not None and target.get('roadlab_manual_owner')==obj
    if not force and owned and obj.get('roadlab_manual_marking_signature')==signature:
        target.matrix_world=obj.matrix_world.copy();return
    tree=projection(obj);verts=[];faces=[];uvs=[];slots=[];materials=[];skipped=0;visible=[]
    for stamp_index,stamp in enumerate(stamps):
        mark=placement(obj,stamp)
        if mark is None:skipped+=1;continue
        pv,pf,pu=lane_markings.patch_grid(mark);projected=[sample(tree,Vector(p)) for p in pv]
        # Reject the entire footprint rather than producing a torn decal at the edge.
        if any(p is None for p in projected):skipped+=1;continue
        visible.append(stamp_index)
        if mark['asset'] not in slots:slots.append(mark['asset'])
        base=len(verts);verts.extend(tuple(p) for p in projected);uvs.extend(pu);faces.extend(tuple(base+i for i in f) for f in pf);materials.extend([slots.index(mark['asset'])]*len(pf))
    mesh=bpy.data.meshes.new('RoadLab Manual Markings');mesh.from_pydata(verts,[],faces);mesh.update()
    uv=mesh.uv_layers.new(name='UVMap');uv.data.foreach_set('uv',[c for loop in mesh.loops for c in uvs[loop.vertex_index]])
    from .lane_editor import paint_material
    for asset in slots:mesh.materials.append(paint_material(asset))
    for p,index in zip(mesh.polygons,materials):p.material_index=index
    if not owned:
        target=bpy.data.objects.new('RoadLab Manual Markings',mesh);obj.users_collection[0].objects.link(target);target['roadlab_manual_owner']=obj;obj['roadlab_manual_marking_object']=target
    else:
        old=target.data;target.data=mesh
        if old.users==0:bpy.data.meshes.remove(old)
    target.matrix_world=obj.matrix_world.copy();target.hide_select=True;obj['roadlab_manual_marking_signature']=signature;obj['roadlab_manual_marking_skipped']=skipped;obj['roadlab_manual_visible']=json.dumps(visible)

def add(obj,point,asset,scale=1.,rotation=0.):
    if asset not in lane_markings.manifest():raise ValueError('Choose a valid marking')
    if not math.isfinite(scale) or scale<=0 or not math.isfinite(rotation):raise ValueError('Invalid stamp dimensions')
    stamp={**anchor(obj,Vector(point)),'asset':asset,'scale':scale,'rotation':rotation}
    mark=placement(obj,stamp);tree=projection(obj)
    if tree is None or mark is None or any(sample(tree,Vector(p)) is None for p in lane_markings.patch_grid(mark)[0]):raise ValueError('Entire stamp must fit on the road; reduce size or move inward')
    rows=records(obj);rows.append(stamp);obj['roadlab_manual_markings']=json.dumps(rows);rebuild(obj,True)
    return stamp

def alpha_hit(mark,point):
    """Test visible paint, not the transparent rectangular decal canvas."""
    fx,fy=mark['forward'];dx=point[0]-mark['center'][0];dy=point[1]-mark['center'][1];w,h=mark['size']
    u=.5+(dx*fy-dy*fx)/w;v=.5+(dx*fx+dy*fy)/h
    if mark.get('path'):
        from math import hypot
        nearest=None;travel=0.
        for a,b in zip(mark['path'],mark['path'][1:]):
            vx,vy=b[0]-a[0],b[1]-a[1];length=hypot(vx,vy)
            if length<1e-9:continue
            t=max(0.,min(1.,((point[0]-a[0])*vx+(point[1]-a[1])*vy)/(length*length)))
            px,py=a[0]+t*vx,a[1]+t*vy;distance=hypot(point[0]-px,point[1]-py)
            candidate=(distance,.5+((point[0]-px)*vy-(point[1]-py)*vx)/(length*w),(travel+t*length)/h)
            if nearest is None or candidate[0]<nearest[0]:nearest=candidate
            travel+=length
        if nearest is None:return False
        _,u,v=nearest
        if mark['asset'] in ('broken_white','dotted_white'):
            from . import lane_markings
            v=(v*h/lane_markings.manifest()[mark['asset']]['physical_canvas_m'][1])%1

    if not (0<=u<=1 and 0<=v<=1):return False
    v0,v1=mark.get('v_range',[0,1]);v=v0+(v1-v0)*v
    from .lane_editor import paint_material
    material=paint_material(mark['asset']);image=next(n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE')
    width,height=image.size
    if width<1 or height<1:return False
    x=min(width-1,int(u*width));y=min(height-1,int(v*height));channels=image.channels
    return channels<4 or image.pixels[(y*width+x)*channels+3]>.1


def erase(obj,point,scene):
    """Remove one visible patch; generated patches use persistent exclusions."""
    from . import lane_editor
    rebuild(obj);lane_editor.rebuild(obj,scene)
    tree=projection(obj)
    def visible_here(mark):
        if not alpha_hit(mark,point):return False
        surface=sample(tree,Vector((point[0],point[1],mark['center'][2])))
        return surface is not None and abs(surface.z-point[2])<.05
    stamps=records(obj);visible=set(json.loads(obj.get('roadlab_manual_visible','[]')))
    for index in reversed(range(len(stamps))):
        mark=placement(obj,stamps[index])
        if index in visible and mark and visible_here(mark):
            stamps.pop(index);obj['roadlab_manual_markings']=json.dumps(stamps)
            if stamps:rebuild(obj,True)
            else:
                target=obj.get('roadlab_manual_marking_object')
                if target and target.get('roadlab_manual_owner')==obj:
                    mesh=target.data;bpy.data.objects.remove(target,do_unlink=True)
                    if mesh.users==0:bpy.data.meshes.remove(mesh)
                if 'roadlab_manual_marking_object' in obj:del obj['roadlab_manual_marking_object']
                obj['roadlab_manual_visible']='[]'
            return 'manual stamp'
    for mark in reversed(json.loads(obj.get('roadlab_generated_marking_catalog','[]'))):
        if visible_here(mark):
            hidden=set(json.loads(obj.get('roadlab_hidden_lane_markings','[]')));hidden.add(mark['id']);obj['roadlab_hidden_lane_markings']=json.dumps(sorted(hidden));lane_editor.rebuild(obj,scene,True)
            return 'generated marking'
    return None


class StampSettings(bpy.types.PropertyGroup):
    asset:EnumProperty(name='Marking',items=ASSETS,default='arrow_through')
    scale:FloatProperty(name='Size',default=1.,min=.1,max=10.)
    rotation:FloatProperty(name='Rotation',subtype='ANGLE',default=0.)

def hit(context,event):
    obj=road(context)
    if obj is None:return None
    from bpy_extras.view3d_utils import region_2d_to_origin_3d,region_2d_to_vector_3d
    xy=(event.mouse_region_x,event.mouse_region_y);region=context.region;rv=context.space_data.region_3d
    origin=region_2d_to_origin_3d(region,rv,xy);direction=region_2d_to_vector_3d(region,rv,xy);inv=obj.matrix_world.inverted()
    tree=projection(obj)
    if tree is None:return None
    result=tree.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())
    return result[0]

class ROADLAB_OT_stamp_hover(bpy.types.Operator):
    bl_idname='roadlab.stamp_hover';bl_label='Preview marking stamp'
    def invoke(self,context,event):
        global _preview
        obj=road(context);p=hit(context,event)
        if obj is None or p is None:_preview=None
        else:
            if getattr(event,'alt',False):
                corners=[Vector((p.x+x,p.y+y,p.z+.02)) for x,y in ((-.35,-.35),(.35,-.35),(-.35,.35),(.35,.35))]
                _preview=(context.area.as_pointer(),[obj.matrix_world@v for v in corners],False);context.area.tag_redraw();return {'FINISHED'}
            settings=context.scene.roadlab_stamp_settings
            try:
                mark=placement(obj,{**anchor(obj,p),'asset':settings.asset,'scale':settings.scale,'rotation':settings.rotation})
                corners=lane_markings.patch_grid(mark,max_step=100)[0];tree=projection(obj);valid=all(sample(tree,Vector(v)) is not None for v in lane_markings.patch_grid(mark)[0])
                _preview=(context.area.as_pointer(),[obj.matrix_world@Vector(v) for v in corners],valid)
            except ValueError:_preview=None
        context.area.tag_redraw();return {'FINISHED'}

class ROADLAB_OT_stamp_place(bpy.types.Operator):
    bl_idname='roadlab.stamp_place';bl_label='Place road marking';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return road(context) is not None and context.area is not None and context.area.type=='VIEW_3D'
    erase_mode:BoolProperty(default=False,options={'HIDDEN'})
    def invoke(self,context,event):
        obj=road(context);p=hit(context,event);settings=context.scene.roadlab_stamp_settings
        if p is None:self.report({'WARNING'},'Click on the selected road surface');return {'CANCELLED'}
        if self.erase_mode or getattr(event,'alt',False):
            removed=erase(obj,p,context.scene)
            if removed:self.report({'INFO'},'Removed '+removed);return {'FINISHED'}
            self.report({'INFO'},'No road marking under the cursor');return {'CANCELLED'}
        try:add(obj,p,settings.asset,settings.scale,settings.rotation)
        except ValueError as e:self.report({'WARNING'},str(e));return {'CANCELLED'}
        return {'FINISHED'}

class ROADLAB_OT_stamp_restore_auto(bpy.types.Operator):
    bl_idname='roadlab.stamp_restore_auto';bl_label='Restore erased lane markings';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return road(context) is not None and bool(json.loads(road(context).get('roadlab_hidden_lane_markings','[]')))
    def execute(self,context):
        from . import lane_editor
        obj=road(context);obj['roadlab_hidden_lane_markings']='[]';lane_editor.rebuild(obj,context.scene,True);return {'FINISHED'}


class ROADLAB_OT_stamp_remove(bpy.types.Operator):
    bl_idname='roadlab.stamp_remove';bl_label='Remove last stamp';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return road(context) is not None and bool(records(road(context)))
    def execute(self,context):
        obj=road(context);rows=records(obj);rows.pop();obj['roadlab_manual_markings']=json.dumps(rows)
        if rows:rebuild(obj,True)
        else:
            target=obj.get('roadlab_manual_marking_object')
            if target and target.get('roadlab_manual_owner')==obj:
                mesh=target.data;bpy.data.objects.remove(target,do_unlink=True)
                if mesh.users==0:bpy.data.meshes.remove(mesh)
            if 'roadlab_manual_marking_object' in obj:del obj['roadlab_manual_marking_object']
        return {'FINISHED'}

def draw_settings(context,layout,tool):
    s=context.scene.roadlab_stamp_settings;layout.prop(s,'asset');layout.prop(s,'scale');layout.prop(s,'rotation');layout.operator('roadlab.stamp_remove',text='',icon='LOOP_BACK')

def draw_preview():
    if _preview is None or bpy.context.area is None or bpy.context.area.as_pointer()!=_preview[0]:return
    import gpu
    from gpu_extras.batch import batch_for_shader
    points=_preview[1]
    if len(points)!=4:return
    shader=gpu.shader.from_builtin('UNIFORM_COLOR');batch=batch_for_shader(shader,'LINE_STRIP',{'pos':[points[i] for i in (0,1,3,2,0)]})
    gpu.state.blend_set('ALPHA');shader.bind();shader.uniform_float('color',(.15,1.,.4,1.) if _preview[2] else (1.,.2,.1,1.));batch.draw(shader);gpu.state.blend_set('NONE')

def watch_view():
    global _preview
    active=set()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type!='VIEW_3D':continue
            obj=window.view_layer.objects.active;mode='EDIT_CURVE' if obj and obj.type=='CURVE' and obj.mode=='EDIT' else 'OBJECT';tool=window.workspace.tools.from_space_view3d_mode(mode if mode in ('OBJECT','EDIT_CURVE') else 'OBJECT',create=False)
            key=(window.as_pointer(),area.as_pointer());rv=area.spaces.active.region_3d
            obj=window.view_layer.objects.active
            if tool and tool.idname=='roadlab.marking_stamp' and obj and obj.type=='CURVE' and obj.get('roadlab_new_core'):
                active.add(key)
                if key not in _views:
                    _views[key]=(rv,rv.view_rotation.copy(),rv.view_perspective,rv.view_location.copy(),rv.view_distance)
                    rv.view_rotation=Quaternion((1,0,0,0));rv.view_perspective='ORTHO';area.tag_redraw()
            elif key in _views:
                old=_views.pop(key)
                try:old[0].view_rotation=old[1];old[0].view_perspective=old[2];old[0].view_location=old[3];old[0].view_distance=old[4]
                except ReferenceError:pass
                _preview=None;area.tag_redraw()
    for key in set(_views)-active:
        _views.pop(key,None)
    return .2

class ROADLAB_WST_marking_stamp(bpy.types.WorkSpaceTool):
    bl_space_type='VIEW_3D';bl_context_mode='OBJECT';bl_idname='roadlab.marking_stamp';bl_label='Marking Stamp';bl_description='Place manual decals on a selected RoadLab road in top-down orthographic view';bl_icon='brush.paint_texture.clone';bl_widget=None
    bl_keymap=(('roadlab.stamp_hover',{'type':'MOUSEMOVE','value':'ANY'},{}),('roadlab.stamp_place',{'type':'LEFTMOUSE','value':'PRESS','alt':True},{'properties':[('erase_mode',True)]}),('roadlab.stamp_place',{'type':'LEFTMOUSE','value':'PRESS'},{}))
    draw_settings=staticmethod(draw_settings)

class ROADLAB_WST_marking_stamp_edit(bpy.types.WorkSpaceTool):
    bl_space_type='VIEW_3D';bl_context_mode='EDIT_CURVE';bl_idname='roadlab.marking_stamp';bl_label='Marking Stamp';bl_description='Place manual decals on the selected road';bl_icon='brush.paint_texture.clone';bl_widget=None
    bl_keymap=ROADLAB_WST_marking_stamp.bl_keymap
    draw_settings=staticmethod(draw_settings)

class ROADLAB_PT_marking_stamp(bpy.types.Panel):
    bl_label='Marking Stamp';bl_idname='ROADLAB_PT_marking_stamp';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RoadLab';bl_options={'DEFAULT_CLOSED'}
    @classmethod
    def poll(cls,context):return road(context) is not None
    def draw(self,context):
        self.layout.operator('wm.tool_set_by_id',text='Use Marking Stamp',icon='BRUSH_DATA').name='roadlab.marking_stamp'
        draw_settings(context,self.layout,None)
        self.layout.label(text='Click to place · Alt-click to erase')
        self.layout.operator('roadlab.stamp_remove')
        if ROADLAB_OT_stamp_restore_auto.poll(context):self.layout.operator('roadlab.stamp_restore_auto')
        if context.active_object.get('roadlab_manual_marking_skipped',0):self.layout.label(text='Some stamps no longer fit the edited road',icon='INFO')
        if context.active_object.get('roadlab_manual_marking_error'):self.layout.label(text=context.active_object['roadlab_manual_marking_error'],icon='ERROR')

classes=(StampSettings,ROADLAB_OT_stamp_hover,ROADLAB_OT_stamp_place,ROADLAB_OT_stamp_restore_auto,ROADLAB_OT_stamp_remove,ROADLAB_PT_marking_stamp)
def register():
    global _draw
    for cls in classes:bpy.utils.register_class(cls)
    bpy.types.Scene.roadlab_stamp_settings=PointerProperty(type=StampSettings)
    for tool in (ROADLAB_WST_marking_stamp,ROADLAB_WST_marking_stamp_edit):bpy.utils.register_tool(tool,separator=True,group=False)
    _draw=bpy.types.SpaceView3D.draw_handler_add(draw_preview,(),'WINDOW','POST_VIEW')
    bpy.app.timers.register(watch_view,persistent=True)

def unregister():
    global _draw,_preview
    if bpy.app.timers.is_registered(watch_view):bpy.app.timers.unregister(watch_view)
    for old in _views.values():
        try:old[0].view_rotation=old[1];old[0].view_perspective=old[2];old[0].view_location=old[3];old[0].view_distance=old[4]
        except ReferenceError:pass
    _views.clear();_trees.clear();_preview=None
    if _draw is not None:bpy.types.SpaceView3D.draw_handler_remove(_draw,'WINDOW');_draw=None
    for tool in (ROADLAB_WST_marking_stamp_edit,ROADLAB_WST_marking_stamp):bpy.utils.unregister_tool(tool)
    del bpy.types.Scene.roadlab_stamp_settings
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
