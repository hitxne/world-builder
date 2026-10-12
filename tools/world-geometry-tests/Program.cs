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
        Check(WorldGeometry.IntersectsXZ(new WorldPoint(0,-100,0),new WorldPoint(10,-50,10),new WorldPoint(9,100,9),new WorldPoint(20,200,20)),"dependency footprint ignores elevation");
        Check(!WorldGeometry.IntersectsXZ(new WorldPoint(0,0,0),new WorldPoint(10,0,10),new WorldPoint(11,0,0),new WorldPoint(20,0,10)),"unrelated road footprint excluded");
        Check(WorldGeometry.IntersectsXZ(new WorldPoint(0,0,0),new WorldPoint(10,0,10),new WorldPoint(10,0,0),new WorldPoint(20,0,10)),"chunk boundary footprint included");
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
        Check(JsonSerializer.Deserialize<WorldConstruction>("{}",new JsonSerializerOptions{IncludeFields=true}).FollowTerrain,"legacy roads default to terrain following");
        var advanced=new WorldConstruction{kind="road",points=new[]{new WorldPoint(0,2,0),new WorldPoint(0,2,40)},width=15,sidewalk=1,lanes=4,median=1,shoulderLeft=2,shoulderRight=3,banking=10,elevationOffset=2,edgeLines=true,markings=3};
        var advancedMesh=WorldGeometry.Build(advanced);Valid(advancedMesh,"advanced road");
        Check(advancedMesh.groups[3].Length>0&&advancedMesh.groups[4].Length>0,"lane markings and median geometry");
        Check(Math.Abs(advancedMesh.vertices.Min(v=>v.x)+10.5f)<0.001f&&Math.Abs(advancedMesh.vertices.Max(v=>v.x)-11.5f)<0.001f,"asymmetric shoulders and sidewalks extent");
        var projected=WorldGeometry.Build(advanced);WorldGeometry.ConformRoad(projected,(v,up)=>new WorldPoint(v.x,10+up,v.z));
        foreach(int index in projected.groups[0])Check(Math.Abs(projected.vertices[index].y-(12.05f+projected.vertices[index].x*(float)Math.Tan(Math.PI/18)))<0.001f,"bank and offset survive terrain projection");
        var graded=WorldGeometry.Island(100,100,99);Array.Clear(graded.heights,0,graded.heights.Length);var paintBefore=(int[])graded.paint.Clone();
        var gradeSource=new WorldConstruction{kind="road",points=new[]{new WorldPoint(0,3,-30),new WorldPoint(0,3,30)},width=8,sidewalk=0,elevationOffset=1};WorldGeometry.GradeRoadTerrain(graded,gradeSource,3);
        Check(Math.Abs(WorldGeometry.Height(graded,0,0)-4)<0.001f,"road cut/fill center height");Check(WorldGeometry.Height(graded,30,0)==0,"grading preserves distant terrain");Check(graded.paint.SequenceEqual(paintBefore),"grading preserves terrain paint");
        var junction=new WorldConstruction{kind="junction",size=new WorldPoint(24,0,20),junctionRadius=4};var junctionMesh=WorldGeometry.Build(junction);Valid(junctionMesh,"rounded junction");
        Check(Math.Abs(junctionMesh.vertices.Max(v=>v.x)-12)<0.001f&&Math.Abs(junctionMesh.vertices.Max(v=>v.z)-10)<0.001f,"junction footprint bounds");
        Check(!junctionMesh.vertices.Any(v=>Math.Abs(v.x)>11.99f&&Math.Abs(v.z)>9.99f),"junction radius removes square corner");
        var north=WorldGeometry.JunctionPort(junction,0,-3,6);var south=WorldGeometry.JunctionPort(junction,2,2,6);var east=WorldGeometry.JunctionPort(junction,1,-2,6);var west=WorldGeometry.JunctionPort(junction,3,1,6);
        Check(north.x==-3&&north.z==10&&south.x==2&&south.z==-10,"opposite roads have independent lateral offsets");Check(east.x==12&&east.z==-2&&west.x==-12&&west.z==1,"perpendicular roads connect on distinct sides");
        Check(WorldGeometry.JunctionPort(junction,0,100,6).x==5,"port slide clamps before rounded corner and road edge");
        var advancedJson=JsonSerializer.Serialize(advanced,new JsonSerializerOptions{IncludeFields=true,IgnoreReadOnlyProperties=true});var advancedSaved=JsonSerializer.Deserialize<WorldConstruction>(advancedJson,new JsonSerializerOptions{IncludeFields=true});Check(advancedSaved.banking==10&&advancedSaved.lanes==4&&advancedSaved.shoulderRight==3,"advanced road recipe roundtrip");
        var flatTerrain=WorldGeometry.Island(100,100,7);Array.Clear(flatTerrain.heights,0,flatTerrain.heights.Length);
        var crossing=new WorldConstruction{kind="road",points=new[]{new WorldPoint(-30,0,0),new WorldPoint(30,0,0)}};
        WorldGeometry.Brush(flatTerrain,new WorldPoint(0,0,0),10,1,"raise",0);
        var raisedRoad=WorldGeometry.Build(crossing);WorldGeometry.ConformRoad(raisedRoad,(v,up)=>new WorldPoint(v.x,WorldGeometry.Height(flatTerrain,v.x,v.z)+up,v.z));
        Valid(raisedRoad,"terrain-following road");Check(raisedRoad.vertices.Any(v=>Math.Abs(v.x)<5&&v.y>0.05f),"road responds between control points");
        WorldGeometry.Brush(flatTerrain,new WorldPoint(0,0,0),10,2,"lower",0);
        var loweredRoad=WorldGeometry.Build(crossing);WorldGeometry.ConformRoad(loweredRoad,(v,up)=>new WorldPoint(v.x,WorldGeometry.Height(flatTerrain,v.x,v.z)+up,v.z));
        Check(loweredRoad.vertices.Where((v,i)=>Math.Abs(v.x)<5&&v.y<raisedRoad.vertices[i].y).Any(),"road follows lowering");
        for(int g=0;g<3;g++)foreach(int index in loweredRoad.groups[g]){var v=loweredRoad.vertices[index];float up=g==1?0.15f:g==2?0.07f:0.05f;Check(Math.Abs(v.y-WorldGeometry.Height(flatTerrain,v.x,v.z)-up)<0.0001f,"road/sidewalk/marking clearance");}
        var uncovered=WorldGeometry.Build(crossing);var unchanged=(WorldPoint[])uncovered.vertices.Clone();WorldGeometry.ConformRoad(uncovered,(v,up)=>null);Check(uncovered.vertices.SequenceEqual(unchanged),"uncovered spans unchanged");
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
