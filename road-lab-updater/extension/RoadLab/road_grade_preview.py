"""Height-only road grading during a stroke; completed terrain stays untouched."""
from mathutils import Vector
from mathutils.kdtree import KDTree
from . import terrain_quads,terrain_grading,road_heightfield
from mathutils.bvhtree import BVHTree
from .surface_network import perimeter

class RoadGradePreview:
    def __init__(self,scene,road):
        self.terrain=scene.wb_native.terrain;self.helper=None;self.bindings=[];self.road=road
        terrain=self.terrain
        if terrain is None or not terrain.roadlab_core_terrain_enabled:return
        helper=terrain.get('roadlab_core_terrain_mesh')
        if helper is None:return
        self.helper=helper;self.original=helper.data;self.mesh=self.original.copy();helper.data=self.mesh
        inv=terrain.matrix_world.inverted();segments=[];blend=terrain.roadlab_core_blend
        terrain.data.calc_loop_triangles()
        ground=BVHTree.FromPolygons([v.co for v in terrain.data.vertices],[tuple(t.vertices) for t in terrain.data.loop_triangles],all_triangles=True)
        sculpt=road_heightfield.decode(terrain.get('roadlab_terrain_field',''))
        self.blend=blend
        for owner in scene.objects:
            if owner.type!='CURVE' or not owner.get('roadlab_new_core') or not owner.roadlab_core_ground_contact:continue
            source=owner.get('roadlab_core_mesh')
            if source is None:continue
            mesh=terrain_quads.base_mesh(source);matrix=inv@source.matrix_world
            verts=[matrix@v.co for v in mesh.vertices];contact=mesh.attributes.get('roadlab_ground_contact')
            faces=[list(f.vertices) for f in mesh.polygons if contact is None or contact.data[f.index].value]
            for loop in perimeter(verts,faces):
                for a,b in zip(loop,loop[1:]+loop[:1]):
                    segments.append((owner,a,b,verts[a],verts[b]))
        tree=KDTree(len(segments))
        for i,(_,a,b,p,q) in enumerate(segments):tree.insert(Vector(((p.x+q.x)/2,(p.y+q.y)/2,0)),i)
        tree.balance()
        if not segments:return
        for vertex in self.mesh.vertices:
            p=vertex.co.xy;best=None
            for _,i,_ in tree.find_n(Vector((*p,0)),min(16,len(segments))):
                owner,a,b,u,v=segments[i];d=v.xy-u.xy
                t=max(0.,min(1.,(p-u.xy).dot(d)/max(d.length_squared,1e-12)));q=u+(v-u)*t;dist=(p-q.xy).length
                if best is None or dist<best[0]:best=(dist,owner,a,b,t,q)
            dist,owner,a,b,t,q=best
            if owner!=road or dist>=blend:continue
            hit=ground.ray_cast(Vector((p.x,p.y,100000)),Vector((0,0,-1)))[0]
            source=(hit.z if hit is not None else 0.)+road_heightfield.sample(sculpt,p.x,p.y)
            before=terrain_grading.height(source,q.z,dist,blend)
            self.bindings.append((vertex.index,a,b,t,dist,source,before,vertex.co.z))
        self.matrix=inv@road['roadlab_core_mesh'].matrix_world
        source=terrain_quads.base_mesh(road['roadlab_core_mesh'])
        self.index=KDTree(len(self.bindings))
        for i,(_,a,b,t,*_) in enumerate(self.bindings):
            q=source.vertices[a].co.lerp(source.vertices[b].co,t)
            self.index.insert(Vector((q.x,q.y,0)),i)
        self.index.balance()
    def update(self,center=None,radius=None):
        if self.helper is None or not self.bindings:return
        mesh=terrain_quads.base_mesh(self.road['roadlab_core_mesh']);positions={}
        def point(i):
            if i not in positions:positions[i]=self.matrix@mesh.vertices[i].co
            return positions[i]
        candidates=(range(len(self.bindings)) if center is None else
                    (item[1] for item in self.index.find_range(Vector((center[0],center[1],0)),radius+1.5)))
        for binding in candidates:
            i,a,b,t,dist,source,before,z=self.bindings[binding]
            u,v=point(a),point(b);q=u+(v-u)*t
            vertex=self.mesh.vertices[i];after=terrain_grading.height(source,q.z,dist,self.blend)
            vertex.co.z=z+after-before
        self.mesh.update()
    def close(self):
        if self.helper is None:return
        self.helper.data=self.original
        import bpy
        if self.mesh.users==0:bpy.data.meshes.remove(self.mesh)
        self.helper=None
