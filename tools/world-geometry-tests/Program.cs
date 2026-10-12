using System;
using System.Linq;
using System.Text.Json;

class Program
{
    static int checks;
    static void Check(bool condition,string name){if(!condition)throw new Exception(name);checks++;}
    static void Valid(WorldGeometryMesh mesh,string name)
    {
        Check(mesh.vertices.Length>0,name+" vertices");
        foreach(var v in mesh.vertices)Check(float.IsFinite(v.x)&&float.IsFinite(v.y)&&float.IsFinite(v.z),name+" finite vertices");
        foreach(var group in mesh.groups){
            Check(group.Length%3==0,name+" triangle count");foreach(int at in group)Check(at>=0&&at<mesh.vertices.Length,name+" index bounds");
            for(int i=0;i<group.Length;i+=3){var a=mesh.vertices[group[i]];var b=mesh.vertices[group[i+1]];var c=mesh.vertices[group[i+2]];
                var u=b-a;var v=c-a;float area=(new WorldPoint(u.y*v.z-u.z*v.y,u.z*v.x-u.x*v.z,u.x*v.y-u.y*v.x)).Length;
                Check(area>0.000001f,name+" non-degenerate triangles");}
        }
    }
    static void Main()
    {
        var p=WorldGeometry.Island(160,160,1337);
        var second=WorldGeometry.Island(160,160,1337);
        Check(p.heights.SequenceEqual(second.heights),"deterministic seed");
        Check(WorldGeometry.Height(p,0,0)>WorldGeometry.Height(p,80,80),"raised island versus ocean floor");
        Valid(WorldGeometry.Build(p),"terrain");
        float before=WorldGeometry.Height(p,0,0);WorldGeometry.Brush(p,new WorldPoint(0,0,0),8,1,"raise",0);
        Check(WorldGeometry.Height(p,0,0)>before,"raise edits heightfield");
        WorldGeometry.Brush(p,new WorldPoint(0,0,0),20,2,"flatten",5);
        Check(Math.Abs(WorldGeometry.Height(p,0,0)-5)<0.0001,"flatten plateau");
        WorldGeometry.Brush(p,new WorldPoint(0,0,0),8,1,"sand",0);Check(p.paint[(p.resolution-1)/2*(p.resolution-1)+(p.resolution-1)/2]==1,"material paint persists");
        var json=JsonSerializer.Serialize(p,new JsonSerializerOptions{IncludeFields=true,IgnoreReadOnlyProperties=true});
        var restored=JsonSerializer.Deserialize<WorldConstruction>(json,new JsonSerializerOptions{IncludeFields=true,IgnoreReadOnlyProperties=true});
        Check(restored.heights.SequenceEqual(p.heights)&&restored.paint.SequenceEqual(p.paint),"terrain source roundtrip");
        WorldGeometry.FlattenRectangle(p,-10,10,-10,10,4);
        Check(Math.Abs(WorldGeometry.Height(p,5,5)-4)<0.0001,"lot rectangle graded flat");
        var road=new WorldConstruction{kind="road",points=new[]{new WorldPoint(0,0,0),new WorldPoint(0,0,20)},width=6,sidewalk=1};
        var roadMesh=WorldGeometry.Build(road);Valid(roadMesh,"road");
        var roadVertices=roadMesh.groups[0].Select(i=>roadMesh.vertices[i]).ToArray();Check(Math.Abs(roadVertices.Max(v=>v.x)-roadVertices.Min(v=>v.x)-6)<0.001,"road width");
        Check(roadMesh.groups[1].Length>0&&roadMesh.groups[2].Length>0,"sidewalk and marking geometry");
        var wall=new WorldConstruction{kind="wall",width=0.2f,size=new WorldPoint(1,3,1),points=new[]{new WorldPoint(0,0,0),new WorldPoint(6,0,0)},openings=new[]{new WorldOpening{kind="door",center=3,width=1,bottom=0,height=2.1f}}};
        var wallMesh=WorldGeometry.Build(wall);Valid(wallMesh,"wall with aperture");
        // No panel triangle spans the clear center of the doorway on either wall face.
        foreach(var group in wallMesh.groups)for(int i=0;i<group.Length;i+=3){WorldPoint a=wallMesh.vertices[group[i]],b=wallMesh.vertices[group[i+1]],c=wallMesh.vertices[group[i+2]];
            float cx=(a.x+b.x+c.x)/3,cy=(a.y+b.y+c.y)/3;Check(!(cx>2.5f&&cx<3.5f&&cy>0.1f&&cy<2),"door opening has no covering panel");}
        var bad=new WorldConstruction{kind="wall",points=wall.points,width=0.2f,size=wall.size,openings=new[]{new WorldOpening{center=0,width=2,height=2}}};
        bool rejected=false;try{WorldGeometry.Build(bad);}catch(ArgumentException){rejected=true;}Check(rejected,"invalid opening rejected");
        foreach(string kind in new[]{"lot","floor","roof","water","tree","stairs","window"}){
            var model=new WorldConstruction{kind=kind,size=new WorldPoint(6,3,8),points=new[]{new WorldPoint(0,0,0),new WorldPoint(6,0,0)}};Valid(WorldGeometry.Build(model),kind);
        }
        ContainerTests.Run();
        Console.WriteLine("PASS: "+checks+" geometry assertions; island/sculpt/paint/roundtrip/road/openings/primitives. Unity integration not tested here.");
    }
}
