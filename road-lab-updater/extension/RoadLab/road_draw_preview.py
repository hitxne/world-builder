"""Transient edit-mode road ribbons; no compiled meshes or terrain per move."""
import bpy,math
from collections import defaultdict,deque
from . import point_settings
_COMMITTED={}
_QUEUED={}
_PREVIEWS={}
_HANDLE=None

def edges(road,width):
    records=point_settings.records(road);count=sum(len(s.points) for s in road.data.splines)
    use_records=len(records)==count;offset=0;result=[];by_coordinate=defaultdict(deque)
    for item in records:by_coordinate[tuple(item['co'])].append(item)
    for spline in road.data.splines:
        row=[]
        for p in spline.points:
            if use_records:item=records[offset]
            else:
                matches=by_coordinate[tuple(round(c,6) for c in p.co[:3])];item=matches.popleft() if matches else {}
            fallback=row[-1][1] if row and not item else width*p.radius
            w=item.get('width',fallback)
            row.append((tuple(p.co[:3]),max(.25,w)));offset+=1
        for i in range(len(row) if spline.use_cyclic_u else len(row)-1):result.append((row[i],row[(i+1)%len(row)]))
    return result

def key(edge):return tuple(sorted((tuple(round(c,6) for c in p)+(round(w,5),) for p,w in edge)))

def remember(road,width):
    _COMMITTED[road.as_pointer()]=(width,{key(e) for e in edges(road,width)})
    _PREVIEWS.pop(road.as_pointer(),None);_QUEUED.pop(road.as_pointer(),None)

def ribbons(road):
    entry=_COMMITTED.get(road.as_pointer())
    if entry is None:return []
    width,previous=entry;quads=[]
    from mathutils import Vector
    for edge in edges(road,width):
        if key(edge) in previous:continue
        (a,wa),(b,wb)=edge;dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<1e-6:continue
        nx,ny=-dy/length,dx/length
        quads.append([tuple(road.matrix_world@Vector((p[0]+nx*w*side*.5,p[1]+ny*w*side*.5,p[2]+.035))) for p,w,side in ((a,wa,-1),(b,wb,-1),(b,wb,1),(a,wa,1))])
    return quads

def queue(scene,roads):
    for road in roads:
        if road.mode=='EDIT':_QUEUED[road.as_pointer()]=(scene,road)
    if _QUEUED and not bpy.app.timers.is_registered(refresh):bpy.app.timers.register(refresh,first_interval=.025)

def refresh():
    queued=list(_QUEUED.items());_QUEUED.clear()
    for pointer,(scene,road) in queued:
        try:_PREVIEWS[pointer]=(scene,road,ribbons(road),None)
        except (ReferenceError,RuntimeError):_PREVIEWS.pop(pointer,None)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()
    return None

def draw():
    scene=bpy.context.scene
    if bpy.context.mode!='EDIT_CURVE':return
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA');gpu.state.depth_test_set('NONE')
    try:
        for pointer,(owner,road,quads,batch) in list(_PREVIEWS.items()):
            if owner!=scene or not quads:continue
            if batch is None:
                coords=[v for q in quads for v in q];indices=[(i,i+1,i+2) for i in range(0,len(coords),4)]+[(i,i+2,i+3) for i in range(0,len(coords),4)]
                batch=batch_for_shader(shader,'TRIS',{'pos':coords},indices=indices);_PREVIEWS[pointer]=(owner,road,quads,batch)
            shader.bind();shader.uniform_float('color',(.12,.5,1.,.4));batch.draw(shader)
    finally:gpu.state.depth_test_set('NONE');gpu.state.blend_set('NONE')

@bpy.app.handlers.persistent
def clear(_):_COMMITTED.clear();_QUEUED.clear();_PREVIEWS.clear()

def register():
    global _HANDLE
    _HANDLE=bpy.types.SpaceView3D.draw_handler_add(draw,(),'WINDOW','POST_VIEW')
    bpy.app.handlers.load_pre.append(clear)
def unregister():
    global _HANDLE
    if bpy.app.timers.is_registered(refresh):bpy.app.timers.unregister(refresh)
    if _HANDLE is not None:bpy.types.SpaceView3D.draw_handler_remove(_HANDLE,'WINDOW');_HANDLE=None
    if clear in bpy.app.handlers.load_pre:bpy.app.handlers.load_pre.remove(clear)
    clear(None)
