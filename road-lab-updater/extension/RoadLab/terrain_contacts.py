"""Cached concrete footprint mask shared by final terrain and live sculpting."""
import json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
import bpy

class ContactMask:
    def __init__(self,scene,terrain,blend):
        self.blend=max(.1,blend);self.points=[];self.triangles=[];self.tree=None;self.cache={}
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
                if road and road.get('roadlab_bridge_cuts'):
                    paths=[[tuple(p.co[:3]) for p in s.points] for s in road.data.splines]
                    local=[road.matrix_world.inverted()@evaluated.matrix_world@v.co for v in mesh.vertices]
                    mask=contact_mask(paths,json.loads(road['roadlab_bridge_cuts']),local,faces);faces=[f for f,keep in zip(faces,mask) if keep]
                offset=len(self.points);self.points.extend(vertices);self.triangles.extend(tuple(offset+i for i in f) for f in faces)
            finally:evaluated.to_mesh_clear()
        if self.triangles:self.tree=BVHTree.FromPolygons([(p.x,p.y,0) for p in self.points],self.triangles,all_triangles=True)
    def sample(self,x,y):
        key=(x,y)
        if key not in self.cache:
            if len(self.cache)>=65536:self.cache.clear()
            self.cache[key]=self._sample(x,y)
        return self.cache[key]
    def _sample(self,x,y):
        if self.tree is None:return 1.,None
        point,_,index,distance=self.tree.find_nearest(Vector((x,y,0)))
        if point is None or distance>=self.blend:return 1.,None
        ids=self.triangles[index];ps=[self.points[i] for i in ids]
        flat=[Vector((p.x,p.y,0)) for p in ps]
        roof=barycentric_transform(point,*flat,*[Vector((0,0,p.z)) for p in ps]).z
        t=min(1.,max(0.,distance/self.blend));return t*t*t*(t*(t*6-15)+10),roof
    def weight(self,x,y):return self.sample(float(x),float(y))[0]
    def grade(self,x,y,baseline,sculpted):
        weight,roof=self.sample(float(x),float(y))
        if roof is not None and weight<1e-8:baseline=min(baseline,roof-.005)
        return baseline+(sculpted-baseline)*weight
