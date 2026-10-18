"""Cached concrete footprint mask shared by final terrain and live sculpting."""
import json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import bpy

class ContactMask:
    def __init__(self,scene,terrain,blend):
        self.blend=max(.1,blend);self.points=[];self.triangles=[];self.tree=None;self.bottom_tree=None;self.bottom_triangles=[];self.cache={};self.bounds=[]
        from .crosswalk_ramps import layers
        from .road_paths import contact_mask
        depsgraph=bpy.context.evaluated_depsgraph_get();inverse=terrain.matrix_world.inverted();surfaces=[]
        for road in scene.objects:
            if road.type!='CURVE' or not road.get('roadlab_new_core') or not road.roadlab_core_ground_contact:continue
            for layer in layers(road):surfaces.append((layer.object,road))
        for obj in scene.objects:
            if obj.get('roadlab_surface_bounds') and obj.roadlab_surface.kind=='SIDEWALK' and obj.roadlab_surface.terrain==terrain:surfaces.append((obj,None))
        for obj,road in surfaces:
            evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles();matrix=inverse@evaluated.matrix_world
                vertices=[matrix@v.co for v in mesh.vertices];normal_matrix=matrix.to_3x3().inverted().transposed()
                faces=[tuple(t.vertices) for t in mesh.loop_triangles if (normal_matrix@mesh.polygons[t.polygon_index].normal).z>.05]
                bottoms=[tuple(t.vertices) for t in mesh.loop_triangles if (normal_matrix@mesh.polygons[t.polygon_index].normal).z<-.05]
                if road and road.get('roadlab_bridge_cuts'):
                    paths=[[tuple(p.co[:3]) for p in s.points] for s in road.data.splines]
                    local=[road.matrix_world.inverted()@evaluated.matrix_world@v.co for v in mesh.vertices]
                    cuts=json.loads(road['roadlab_bridge_cuts'])
                    mask=contact_mask(paths,cuts,local,faces);faces=[f for f,keep in zip(faces,mask) if keep]
                    mask=contact_mask(paths,cuts,local,bottoms);bottoms=[f for f,keep in zip(bottoms,mask) if keep]
                if faces:
                    used={i for f in faces for i in f}
                    self.bounds.append((min(vertices[i].x for i in used),min(vertices[i].y for i in used),max(vertices[i].x for i in used),max(vertices[i].y for i in used)))
                offset=len(self.points);self.points.extend(vertices);self.triangles.extend(tuple(offset+i for i in f) for f in faces)
                self.bottom_triangles.extend(tuple(offset+i for i in f) for f in bottoms)
            finally:evaluated.to_mesh_clear()
        if self.triangles:self.tree=BVHTree.FromPolygons([(p.x,p.y,0) for p in self.points],self.triangles,all_triangles=True)
        if self.bottom_triangles:self.bottom_tree=BVHTree.FromPolygons([(p.x,p.y,0) for p in self.points],self.bottom_triangles,all_triangles=True)
    def sample(self,x,y):
        return self.contact(x,y)[:2]
    def contact(self,x,y):
        key=(x,y)
        if key not in self.cache:
            if len(self.cache)>=65536:self.cache.clear()
            self.cache[key]=self._sample(x,y)
        return self.cache[key]
    def _sample(self,x,y):
        if self.tree is None:return 1.,None,None
        point,_,index,distance=self.tree.find_nearest(Vector((x,y,0)))
        if point is None or distance>=self.blend:return 1.,None,None
        ids=self.triangles[index];ps=[self.points[i] for i in ids]
        flat=[Vector((p.x,p.y,0)) for p in ps]
        roof=barycentric_transform(point,*flat,*[Vector((0,0,p.z)) for p in ps]).z
        support=roof
        if self.bottom_tree is not None:
            bottom,_,bottom_index,gap=self.bottom_tree.find_nearest(point)
            if bottom is not None and gap<1e-4:
                ps=[self.points[i] for i in self.bottom_triangles[bottom_index]]
                support=min(roof,barycentric_transform(bottom,*[Vector((p.x,p.y,0)) for p in ps],*[Vector((0,0,p.z)) for p in ps]).z)
        t=min(1.,max(0.,distance/self.blend));return t*t*t*(t*(t*6-15)+10),roof,support
    def weight(self,x,y):return self.sample(float(x),float(y))[0]
    def grade(self,x,y,baseline,sculpted,shift=0.):
        weight,roof,support=self.contact(float(x),float(y))
        # Meet the underside, then smoothly return to the road/base grading.
        # Keep the sculpt contribution separate so concrete still masks it.
        target=baseline if support is None else baseline+(support+shift-.005-baseline)*(1-weight)
        return target+(sculpted-baseline)*weight
