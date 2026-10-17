"""Session-local height preview. No topology compiler or marking work per stamp.

The source and completed mesh remain intact until commit. The temporary mesh is
refined only in newly brushed coarse areas, with a hard vertex budget.
"""
import math
from functools import lru_cache
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import barycentric_transform
from . import road_heightfield as field

PREVIEW_VERTEX_BUDGET=60000

class HeightPreview:
    def __init__(self,owner,helper,values,weights=None,contact_mask=None):
        self.contact_mask=contact_mask
        self.owner=owner;self.helper=helper;self.original=helper.data
        self.mesh=self.original.copy();helper.data=self.mesh
        self.values=values;self.initial=dict(values);self.revision=0;self.changed_vertices=0
        self.mesh.calc_loop_triangles()
        self.reference=[tuple(v.co) for v in self.mesh.vertices]
        self.ray_height=max((v[2] for v in self.reference),default=0.)+1.
        self.triangles=[tuple(t.vertices) for t in self.mesh.loop_triangles]
        self.weights=list(weights) if weights is not None else [1.]*len(self.reference)
        if len(self.weights)!=len(self.reference):raise ValueError('Preview weight count differs from terrain vertices')
        self.tree=BVHTree.FromPolygons(self.reference,self.triangles,all_triangles=True)
        self.index=None;self.rest=[];self.vertex_weights=[];self.detail_center=None;self.detail_radius=None
        self.reindex()
    @lru_cache(maxsize=65536)
    def reference_at(self,x,y):
        location,normal,index,distance=self.tree.ray_cast(Vector((x,y,self.ray_height)),Vector((0,0,-1)))
        if location is None:return None
        ids=self.triangles[index];a,b,c=[Vector(self.reference[i]) for i in ids]
        weight=barycentric_transform(location,a,b,c,Vector((0,0,self.weights[ids[0]])),Vector((0,0,self.weights[ids[1]])),Vector((0,0,self.weights[ids[2]]))).z
        if self.contact_mask is not None:weight=min(weight,self.contact_mask.weight(x,y))
        return location.z,max(0.,min(1.,weight))
    def height(self,x,y):
        item=self.reference_at(x,y)
        if item is None:return None
        z,w=item
        return z+w*(field.sample(self.values,x,y)-field.sample(self.initial,x,y))
    def reindex(self):
        self.index=KDTree(len(self.mesh.vertices));self.rest=[];self.vertex_weights=[]
        for v in self.mesh.vertices:
            x,y,z=v.co;item=self.reference_at(x,y)
            if item is None:rest,w=z,0.
            else:
                initial_z,w=item;rest=initial_z-w*field.sample(self.initial,x,y)
            self.rest.append(rest);self.vertex_weights.append(w)
            self.index.insert(Vector((x,y,0)),v.index)
        self.index.balance()
    def ensure_detail(self,center,radius):
        """Refine coarse preview faces locally, never the completed terrain topology."""
        if self.detail_center is not None and radius==self.detail_radius and math.dist(center,self.detail_center)<max(.5,radius*.3):return False
        self.detail_center=tuple(center);self.detail_radius=radius
        import bmesh
        spacing=max(1.,radius/8);bm=bmesh.new();bm.from_mesh(self.mesh);changed=False
        try:
            for _ in range(10):
                edges=[]
                for edge in bm.edges:
                    a,b=(v.co for v in edge.verts);dx,dy=b.x-a.x,b.y-a.y
                    length2=dx*dx+dy*dy
                    if length2<=spacing*spacing*1.01:continue
                    t=max(0.,min(1.,((center[0]-a.x)*dx+(center[1]-a.y)*dy)/length2))
                    distance=math.hypot(a.x+t*dx-center[0],a.y+t*dy-center[1])
                    # Include a transition band so a large face enclosing the brush
                    # acquires interior samples even if its original edges are far away.
                    if distance<=radius+math.sqrt(length2):edges.append(edge)
                if not edges:break
                if len(bm.verts)+len(edges)*4>PREVIEW_VERTEX_BUDGET:break
                bmesh.ops.subdivide_edges(bm,edges=edges,cuts=1,use_grid_fill=True)
                changed=True
            if changed:
                bm.to_mesh(self.mesh);self.mesh.update();self.reindex()
                self.update(center,radius+spacing*3,all_vertices=True)
        finally:bm.free()
        return changed
    def update(self,center,radius,all_vertices=False):
        candidates=((None,v.index,None) for v in self.mesh.vertices) if all_vertices else self.index.find_range(Vector((center[0],center[1],0)),radius+1.5)
        changed=0
        for _,i,_ in candidates:
            v=self.mesh.vertices[i];z=self.rest[i]+self.vertex_weights[i]*field.sample(self.values,v.co.x,v.co.y)
            if abs(v.co.z-z)>1e-7:v.co.z=z;changed+=1
        if changed:self.mesh.update();self.revision+=1
        self.changed_vertices=changed
        return changed
    def ray_cast(self,origin,direction):
        """Intersect cached reference, then correct for current brush displacement."""
        p=self.tree.ray_cast(origin,direction)[0]
        if p is None:return None
        if abs(direction.z)<1e-7:return p
        for _ in range(12):
            z=self.height(p.x,p.y)
            if z is None:return None
            delta=(z-p.z)/direction.z
            if abs(delta)<1e-4:return p
            p=p+direction*delta
        # A near-tangent ray can fail to converge on steep edits: avoid showing
        # or painting an inaccurate point instead of returning a false hit.
        z=self.height(p.x,p.y)
        return p if z is not None and abs(z-p.z)<.01 else None
    def close(self):
        self.helper.data=self.original
        if self.mesh.users==0:bpy.data.meshes.remove(self.mesh)
        self.reference_at.cache_clear()
