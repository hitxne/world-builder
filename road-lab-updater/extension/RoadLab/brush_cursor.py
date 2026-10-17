"""Native tool cursor feedback, independent of clicks and gizmo hit testing."""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROAD_TOOLS={'roadlab.'+m for m in ('raise','lower','flatten','smooth','widen','bank','slice')}
TERRAIN_TOOLS={'roadlab.terrain_'+m for m in ('raise','lower','flatten','smooth')}
_mesh_revisions={}
_pickers={}

@bpy.app.handlers.persistent
def geometry_changed(scene,depsgraph):
    for update in depsgraph.updates:
        data=update.id.original
        if update.is_updated_geometry and isinstance(data,bpy.types.Mesh):
            key=data.as_pointer();_mesh_revisions[key]=_mesh_revisions.get(key,0)+1

@bpy.app.handlers.persistent
def clear_geometry_cache(_):
    _mesh_revisions.clear();_pickers.clear()

def active_brush(context):
    if context.mode!='OBJECT' or not hasattr(context.scene,'wb_native'):return None
    tool=context.workspace.tools.from_space_view3d_mode(context.mode,create=False)
    if tool is None:return None
    if tool.idname in TERRAIN_TOOLS:
        obj=context.scene.wb_native.terrain;settings=context.scene.roadlab_terrain_brush;kind='terrain'
    elif tool.idname in ROAD_TOOLS:
        obj=context.scene.wb_native.road;settings=context.scene.roadlab_road_brush;kind='road'
    else:return None
    if obj is None or obj!=context.active_object:return None
    return obj,settings,kind

def display_mesh(obj,kind):
    if kind=='terrain':
        helper=obj.get('roadlab_core_terrain_mesh')
        if helper and obj.get('roadlab_core_terrain_signature'):return helper.data,obj.get('roadlab_core_terrain_signature')
        return obj.data,''
    helper=obj.get('roadlab_core_mesh')
    return (helper.data,obj.get('roadlab_core_signature')) if helper else (None,'')

def draw_rings(obj,center,radius,height,color):
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA');gpu.state.depth_test_set('LESS_EQUAL')
    try:
        for factor,alpha in ((1.,1.),(.5,.35)):
            segments=[]
            for i in range(65):
                a=i*math.tau/64;x=center.x+radius*factor*math.cos(a);y=center.y+radius*factor*math.sin(a)
                z=height(x,y)
                segments.append(obj.matrix_world@Vector((x,y,(center.z if z is None else z)+.025)))
            shader.bind();shader.uniform_float('color',(*color[:3],alpha))
            batch_for_shader(shader,'LINE_STRIP',{'pos':segments}).draw(shader)
    finally:gpu.state.depth_test_set('NONE');gpu.state.blend_set('NONE')

class HoverPicker:
    def __init__(self):self.cache_key=None;self.tree=None
    def pick(self,context,location,obj,kind):
        mesh,signature=display_mesh(obj,kind)
        if mesh is None:return None
        key=(obj.as_pointer(),mesh.as_pointer(),len(mesh.vertices),signature,_mesh_revisions.get(mesh.as_pointer(),0))
        if key!=self.cache_key:
            self.tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(f.vertices) for f in mesh.polygons]);self.cache_key=key
            self.ray_height=max((v.co.z for v in mesh.vertices),default=0.)+1.
        from bpy_extras import view3d_utils
        origin=view3d_utils.region_2d_to_origin_3d(context.region,context.region_data,location)
        direction=view3d_utils.region_2d_to_vector_3d(context.region,context.region_data,location);inv=obj.matrix_world.inverted()
        return self.tree.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())[0]
    def height(self,x,y):
        p=self.tree.ray_cast(Vector((x,y,self.ray_height)),Vector((0,0,-1)))[0]
        return p.z if p is not None else None

def draw_tool_cursor(context,tool,location):
    # Blender invokes the native cursor hook on hover, even with gizmos hidden.
    context=bpy.context
    if context.region is None or context.region.type!='WINDOW' or context.region_data is None:return
    active=active_brush(context)
    if active is None:return
    from . import road_sculpt,terrain_sculpt
    if road_sculpt.is_painting() or terrain_sculpt.is_active():return
    obj,settings,kind=active
    picker=_pickers.setdefault((context.area.as_pointer(),context.region.as_pointer()),HoverPicker())
    center=picker.pick(context,location,obj,kind)
    if center is None:return
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    color=(.3,1.,.4) if kind=='terrain' else (1.,.45,.08)
    gpu.state.blend_set('ALPHA')
    try:
        for factor,alpha in ((1.,1.),(.5,.35)):
            points=[]
            for i in range(65):
                a=i*math.tau/64;x=center.x+settings.radius*factor*math.cos(a);y=center.y+settings.radius*factor*math.sin(a)
                z=picker.height(x,y)
                world=obj.matrix_world@Vector((x,y,center.z if z is None else z))
                p=location_3d_to_region_2d(context.region,context.region_data,world)
                if p is None:break
                points.append(p)
            if len(points)!=65:continue
            shader.bind();shader.uniform_float('color',(*color,alpha))
            batch_for_shader(shader,'LINE_STRIP',{'pos':points}).draw(shader)
    finally:gpu.state.blend_set('NONE')

def register():
    bpy.app.handlers.depsgraph_update_post.append(geometry_changed)
    bpy.app.handlers.load_post.append(clear_geometry_cache)
def unregister():
    if geometry_changed in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.remove(geometry_changed)
    if clear_geometry_cache in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(clear_geometry_cache)
    clear_geometry_cache(None)
