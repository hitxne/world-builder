"""Stroke-local road height, perimeter and paint updates without compilation."""
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree
from . import road_heightfield as field
from .sculpt_preview import HeightPreview
from .road_grade_preview import RoadGradePreview

class RoadStrokePreview:
    def __init__(self,scene,road):
        self.road=road;self.values=field.decode(road.get('roadlab_sculpt_field',''));self.base_cache={};self.bounds=None
        from .road_sculpt import base_tree
        self.tree=base_tree(road)
        self.grade=RoadGradePreview(scene,road)
        self.surface=HeightPreview(road,road['roadlab_core_mesh'],self.values)
        outline=road['roadlab_core_outline'];self.outline=outline;self.original_outline=outline.data
        outline.data=outline.data.copy();self.points=[];self.rest=[]
        for spline in outline.data.splines:
            for p in spline.points:
                self.points.append(p);self.rest.append(p.co.z-field.sample(self.values,p.co.x,p.co.y))
        self.index=KDTree(len(self.points))
        for i,p in enumerate(self.points):self.index.insert(Vector((p.co.x,p.co.y,0)),i)
        self.index.balance()
        self.paint=[]
        for key in ('roadlab_marking_object','roadlab_manual_marking_object'):
            target=road.get(key)
            if target is not None and target.type=='MESH' and target.data.polygons and target.matrix_world==road.matrix_world:
                self.paint.append(HeightPreview(road,target,self.values))
    def base_height(self,x,y):
        key=(x,y)
        if key not in self.base_cache:
            from .road_sculpt import base_height
            self.base_cache[key]=base_height(self.road,x,y)
        return self.base_cache[key]
    def stamp(self,center,mode,radius,strength,dt,target=None):
        patch=field.stamp_patch(self.values,center,radius,strength,dt,mode,self.base_height,target)
        if not patch:return False
        self.values.update(patch);self.update(center,radius);return True
    def update(self,center,radius):
        box=(center[0]-radius,center[1]-radius,center[0]+radius,center[1]+radius)
        self.bounds=box if self.bounds is None else (min(self.bounds[0],box[0]),min(self.bounds[1],box[1]),max(self.bounds[2],box[2]),max(self.bounds[3],box[3]))
        self.surface.update(center,radius)
        for paint in self.paint:paint.update(center,radius)
        for _,i,_ in self.index.find_range(Vector((center[0],center[1],0)),radius+1.5):
            p=self.points[i];p.co.z=self.rest[i]+field.sample(self.values,p.co.x,p.co.y)
        self.outline.data.update_tag();self.grade.update(center,radius)
    def close(self,commit=False):
        if commit:
            self.road['roadlab_sculpt_field']=field.encode(self.values)
            # A previously flat terrain cell needs local detail to carry the
            # new road hill. Refine once on commit, never per brush sample.
            terrain=self.grade.terrain
            if terrain is not None and self.grade.helper is not None and self.grade.bindings and self.bounds is not None:
                from . import terrain_sculpt
                matrix=terrain.matrix_world.inverted()@self.road.matrix_world
                a,b,c,d=self.bounds;points=[matrix@Vector((x,y,0)) for x,y in ((a,b),(a,d),(c,b),(c,d))]
                lo=(min(p.x for p in points),min(p.y for p in points));hi=(max(p.x for p in points),max(p.y for p in points))
                center=((lo[0]+hi[0])/2,(lo[1]+hi[1])/2);radius=max(hi[0]-lo[0],hi[1]-lo[1])/2+terrain.roadlab_core_blend
                terrain_sculpt.mark(terrain,center,radius)
        self.grade.close();self.surface.close()
        for paint in self.paint:paint.close()
        temporary=self.outline.data;self.outline.data=self.original_outline
        if temporary.users==0:bpy.data.curves.remove(temporary)
