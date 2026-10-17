"""Tool-owned hover feedback for all current road and terrain sculpt brushes.

Blender calls test_select on hover; returning -1 leaves painting and selection
untouched. The cached BVH is invalidated by completed geometry signatures.
"""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROAD_TOOLS={'roadlab.'+m for m in ('raise','lower','flatten','smooth','widen','bank','slice')}
TERRAIN_TOOLS={'roadlab.terrain_'+m for m in ('raise','lower','flatten','smooth')}
_mesh_revisions={}

@bpy.app.handlers.persistent
def geometry_changed(scene,depsgraph):
    for update in depsgraph.updates:
        data=update.id.original
        if update.is_updated_geometry and isinstance(data,bpy.types.Mesh):
            key=data.as_pointer();_mesh_revisions[key]=_mesh_revisions.get(key,0)+1

@bpy.app.handlers.persistent
def clear_geometry_cache(_):_mesh_revisions.clear()

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

class ROADLAB_GT_brush_cursor(bpy.types.Gizmo):
    bl_idname='ROADLAB_GT_brush_cursor'
    def setup(self):
        self.center=None;self.cache_key=None;self.tree=None;self.hide_select=False
    def test_select(self,context,location):
        self.center=None
        active=active_brush(context)
        if active is None:return -1
        from . import road_sculpt,terrain_sculpt
        if road_sculpt.is_painting() or terrain_sculpt.is_active():return -1
        obj,settings,kind=active;mesh,signature=display_mesh(obj,kind)
        if mesh is None:return -1
        key=(obj.as_pointer(),mesh.as_pointer(),len(mesh.vertices),signature,_mesh_revisions.get(mesh.as_pointer(),0))
        if key!=self.cache_key:
            self.tree=BVHTree.FromPolygons([v.co for v in mesh.vertices],[tuple(f.vertices) for f in mesh.polygons]);self.cache_key=key
            self.ray_height=max((v.co.z for v in mesh.vertices),default=0.)+1.
        from bpy_extras import view3d_utils
        rv=context.region_data;region=context.region
        origin=view3d_utils.region_2d_to_origin_3d(region,rv,location)
        direction=view3d_utils.region_2d_to_vector_3d(region,rv,location);inv=obj.matrix_world.inverted()
        self.center=self.tree.ray_cast(inv@origin,(inv.to_3x3()@direction).normalized())[0]
        context.area.tag_redraw()
        return -1
    def draw(self,context):
        if self.center is None or self.tree is None:return
        active=active_brush(context)
        if active is None:return
        obj,settings,kind=active
        def height(x,y):
            p=self.tree.ray_cast(Vector((x,y,self.ray_height)),Vector((0,0,-1)))[0]
            return p.z if p is not None else None
        draw_rings(obj,self.center,settings.radius,height,(.3,1.,.4,1) if kind=='terrain' else (1.,.45,.08,1))
    def draw_select(self,context,select_id):pass

class ROADLAB_GGT_brush_cursor(bpy.types.GizmoGroup):
    bl_idname='ROADLAB_GGT_brush_cursor';bl_label='RoadLab brush footprint'
    bl_space_type='VIEW_3D';bl_region_type='WINDOW';bl_options={'3D','PERSISTENT','SELECT','SHOW_MODAL_ALL'}
    @classmethod
    def poll(cls,context):return active_brush(context) is not None
    def setup(self,context):self.gizmos.new(ROADLAB_GT_brush_cursor.bl_idname)

def register():
    bpy.utils.register_class(ROADLAB_GT_brush_cursor);bpy.utils.register_class(ROADLAB_GGT_brush_cursor)
    bpy.app.handlers.depsgraph_update_post.append(geometry_changed)
    bpy.app.handlers.load_post.append(clear_geometry_cache)
def unregister():
    if geometry_changed in bpy.app.handlers.depsgraph_update_post:bpy.app.handlers.depsgraph_update_post.remove(geometry_changed)
    if clear_geometry_cache in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(clear_geometry_cache)
    _mesh_revisions.clear()
    bpy.utils.unregister_class(ROADLAB_GGT_brush_cursor);bpy.utils.unregister_class(ROADLAB_GT_brush_cursor)
