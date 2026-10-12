using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    WorldConstruction roadStyle=new WorldConstruction{kind="road",lanes=2,subdivisions=16};
    static WorldConstruction CopyRoad(WorldConstruction p)=>JsonUtility.FromJson<WorldConstruction>(JsonUtility.ToJson(p));
    WorldConstruction RoadRecipe(WorldPoint[] points){var p=CopyRoad(roadStyle);p.kind="road";p.points=points;p.width=roadWidth;p.sidewalk=roadSidewalk;return p;}
    void RoadPreset(string name)
    {
        roadPreset=name;roadStyle=new WorldConstruction{kind="road",lanes=2,subdivisions=16,edgeLines=true};roadWidth=6;roadSidewalk=1.2f;
        if(name=="Two-lane")roadWidth=7;
        if(name=="Multi-lane"){roadWidth=14;roadStyle.lanes=4;}
        if(name=="Highway"){roadWidth=15;roadStyle.lanes=4;roadStyle.median=1;roadStyle.shoulderLeft=2;roadStyle.shoulderRight=2;roadSidewalk=0;roadStyle.markings=3;}
        if(name=="Dirt road"){roadWidth=5;roadSidewalk=0;roadStyle.surface="dirt";roadStyle.friction=0.8f;roadStyle.markings=1;}
        if(name=="Parking lane"||name=="Service road"){roadWidth=name=="Parking lane"?3.5f:4;roadSidewalk=0;roadStyle.lanes=1;roadStyle.oneWay=true;roadStyle.markings=1;}
        if(name=="Footpath"){roadWidth=2;roadSidewalk=0;roadStyle.lanes=1;roadStyle.oneWay=true;roadStyle.surface="concrete";roadStyle.markings=1;}
        SetTool("road");BuildConstructionPanel();
    }
    void OpenRoadSettings(GameObject target=null)
    {
        var source=target!=null?target.GetComponent<WorkspaceIdentity>()?.construction:null;
        bool editing=source?.kind=="road";var draft=editing?CopyRoad(source):RoadRecipe(new[]{new WorldPoint(0,0,0),new WorldPoint(0,0,10)});
        Dialog(editing?"Road settings — "+target.name:"New road defaults",editing?"Changes apply to this road as one undoable edit.":"Settings apply to the next roads you draw.",box=>{
            var tabs=Row(box,"catalog-tabs");var content=new VisualElement();box.Add(content);var buttons=new Dictionary<string,Button>();
            void Show(string tab) {
                content.Clear();foreach(var pair in buttons)pair.Value.EnableInClassList("selected",pair.Key==tab);
                if(tab=="Cross-section") {
                    FloatField count=null,laneWidth=null,total=null;
                    void SyncWidths(){count?.SetValueWithoutNotify(draft.lanes==0?2:draft.lanes);laneWidth?.SetValueWithoutNotify((draft.width-draft.median)/Mathf.Max(1,draft.lanes==0?2:draft.lanes));total?.SetValueWithoutNotify(draft.width);}
                    count=Number(content,"Lanes",draft.lanes==0?2:draft.lanes,1,8,v=>{float lane=(draft.width-draft.median)/Mathf.Max(1,draft.lanes==0?2:draft.lanes);draft.lanes=Mathf.RoundToInt(v);draft.width=Mathf.Clamp(lane*draft.lanes+draft.median,1,40);SyncWidths();});
                    laneWidth=Number(content,"Lane width (m)",(draft.width-draft.median)/Mathf.Max(1,draft.lanes==0?2:draft.lanes),0.5f,8,v=>{draft.width=v*Mathf.Max(1,draft.lanes==0?2:draft.lanes)+draft.median;SyncWidths();});
                    total=Number(content,"Total width (m)",draft.width,1,40,v=>{draft.width=v;SyncWidths();});Number(content,"Sidewalks (m)",draft.sidewalk,0,10,v=>draft.sidewalk=v);
                    Number(content,"Left shoulder (m)",draft.shoulderLeft,0,10,v=>draft.shoulderLeft=v);Number(content,"Right shoulder (m)",draft.shoulderRight,0,10,v=>draft.shoulderRight=v);Number(content,"Median (m)",draft.median,0,10,v=>{draft.median=v;SyncWidths();});
                    var direction=new Toggle("One-way"){value=draft.oneWay};content.Add(direction);direction.RegisterValueChangedCallback(e=>draft.oneWay=e.newValue);
                    Label(content,"Two-way roads need even lane counts. Medians require two-way traffic.","hint");
                } else if(tab=="Markings") {
                    var pattern=new DropdownField("Center line",new List<string>{"Dashed","None","Solid","Double solid"},Mathf.Clamp(draft.markings,0,3));content.Add(pattern);pattern.RegisterValueChangedCallback(e=>draft.markings=pattern.index);
                    var edges=new Toggle("White edge lines"){value=draft.edgeLines};content.Add(edges);edges.RegisterValueChangedCallback(e=>draft.edgeLines=e.newValue);
                    Label(content,"Multi-lane roads add white lane dividers. One-way roads omit the yellow center line.","hint");
                } else if(tab=="Elevation") {
                    var follow=new Toggle("Follow terrain"){value=draft.FollowTerrain};content.Add(follow);follow.RegisterValueChangedCallback(e=>draft.independentElevation=!e.newValue);
                    Number(content,"Height offset (m)",draft.elevationOffset,-100,200,v=>draft.elevationOffset=v);Number(content,"Bank angle (°)",draft.banking,-30,30,v=>draft.banking=v);
                    if(editing)Button(content,"Apply settings and grade terrain",()=>{WorldGeometry.Build(draft);ValidateRoadConnections(target,draft);var previous=target.GetComponent<WorkspaceIdentity>().construction;target.GetComponent<WorkspaceIdentity>().construction=draft;try{GradeRoadTerrain(target);}catch{target.GetComponent<WorkspaceIdentity>().construction=previous;throw;}CloseDialog();});
                    Label(content,"Grading cuts/fills the terrain to the road and locks its elevation. Undo restores both.","hint");
                } else if(tab=="Shape") {
                    var mode=new DropdownField("Curve",new List<string>{"Smooth spline","Straight segments"},draft.curveMode);content.Add(mode);mode.RegisterValueChangedCallback(e=>draft.curveMode=mode.index);
                    Number(content,"Samples per span",draft.subdivisions==0?12:draft.subdivisions,2,64,v=>draft.subdivisions=Mathf.RoundToInt(v));
                    if(!editing){Label(content,"Draw a road, then select it to edit its control points.","hint");return;}
                    if(draft.FollowTerrain)Label(content,"Point heights apply when Follow terrain is off; Height offset always applies.","hint");
                    Button(content,"Reverse road direction",()=>{Array.Reverse(draft.points);draft.banking=-draft.banking;float shoulder=draft.shoulderLeft;draft.shoulderLeft=draft.shoulderRight;draft.shoulderRight=shoulder;string id=draft.startJunction;draft.startJunction=draft.endJunction;draft.endJunction=id;int port=draft.startPort;draft.startPort=draft.endPort;draft.endPort=port;float offset=draft.startConnectionOffset;draft.startConnectionOffset=draft.endConnectionOffset;draft.endConnectionOffset=offset;Show(tab);});
                    for(int i=0;i<draft.points.Length;i++) {
                        int at=i;Label(content,"Point "+(i+1),"section");Number(content,"X",draft.points[i].x,-10000,10000,v=>draft.points[at].x=v);Number(content,"Height",draft.points[i].y,-1000,2000,v=>draft.points[at].y=v);Number(content,"Z",draft.points[i].z,-10000,10000,v=>draft.points[at].z=v);
                        if(i<draft.points.Length-1)Button(content,"Insert midpoint",()=>{var points=draft.points.ToList();points.Insert(at+1,(points[at]+points[at+1])*0.5f);draft.points=points.ToArray();Show(tab);}).SetEnabled(draft.points.Length<256);
                        Button(content,"Remove point",()=>{var points=draft.points.ToList();points.RemoveAt(at);draft.points=points.ToArray();if(at==0)draft.startJunction=null;if(at==points.Count)draft.endJunction=null;Show(tab);}).SetEnabled(draft.points.Length>2);
                    }
                } else if(tab=="Connections") {
                    if(!editing){Label(content,"Select a built road to attach its endpoints to junctions.","hint");return;}
                    var junctions=world.GetComponentsInChildren<WorkspaceIdentity>().Where(i=>i.construction?.kind=="junction").ToArray();
                    var names=new List<string>{"None"};names.AddRange(junctions.Select(i=>i.name+" / "+i.id.Substring(0,Mathf.Min(6,i.id.Length))));
                    for(int end=0;end<2;end++) {
                        int side=end;Label(content,end==0?"Start connection":"End connection","section");string id=end==0?draft.startJunction:draft.endJunction;int index=Array.FindIndex(junctions,j=>j.id==id)+1;
                        var selection=new DropdownField("Junction",names,Mathf.Max(0,index));content.Add(selection);selection.RegisterValueChangedCallback(e=>{string next=selection.index==0?null:junctions[selection.index-1].id;if(side==0)draft.startJunction=next;else draft.endJunction=next;});
                        var port=new DropdownField("Side",new List<string>{"North","East","South","West"},side==0?draft.startPort:draft.endPort);content.Add(port);port.RegisterValueChangedCallback(e=>{if(side==0)draft.startPort=port.index;else draft.endPort=port.index;});
                        Number(content,"Slide offset (m)",side==0?draft.startConnectionOffset:draft.endConnectionOffset,-50,50,v=>{if(side==0)draft.startConnectionOffset=v;else draft.endConnectionOffset=v;});
                    }
                    Label(content,"Each road has its own side and offset. Connected endpoint drags slide along that side, within the junction's usable edge.","hint");
                } else {
                    var surface=new DropdownField("Surface",new List<string>{"asphalt","concrete","dirt","gravel"},Mathf.Max(0,Array.IndexOf(new[]{"asphalt","concrete","dirt","gravel"},draft.surface)));content.Add(surface);surface.RegisterValueChangedCallback(e=>draft.surface=surface.value);
                    Number(content,"Friction metadata",draft.friction,0.1f,2,v=>draft.friction=v);Number(content,"Speed limit (mph)",draft.speedLimitMph,0,150,v=>draft.speedLimitMph=v);Label(content,"Friction and speed are export metadata; driving physics are not simulated here.","hint");
                }
            }
            foreach(string name in new[]{"Cross-section","Markings","Elevation","Shape","Connections","Surface"}){string value=name;buttons[value]=Button(tabs,value,()=>Show(value));}
            var actions=Row(box,"toolbar");Button(actions,"Apply",()=>{
                WorldGeometry.Build(draft);
                if(editing){ValidateRoadConnections(target,draft);target.GetComponent<WorkspaceIdentity>().construction=draft;UpdateRoadConnections();RebuildConstruction(target);Changed();}
                else {roadStyle=draft;roadStyle.startJunction=null;roadStyle.endJunction=null;roadWidth=draft.width;roadSidewalk=draft.sidewalk;}
                CloseDialog();BuildConstructionPanel();
            });Button(actions,"Cancel",CloseDialog);Show("Cross-section");
        });
    }
    void GradeRoadTerrain(GameObject road)
    {
        var p=road.GetComponent<WorkspaceIdentity>().construction;if(p?.kind!="road")return;var changes=new List<(WorkspaceIdentity identity,WorldConstruction source)>();
        foreach(var identity in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            if(identity.construction?.kind!="terrain")continue;var terrain=identity.transform;var rs=road.transform.lossyScale;var ts=terrain.lossyScale;
            if(Vector3.Dot(road.transform.up,Vector3.up)<0.999f||Vector3.Dot(terrain.up,Vector3.up)<0.999f||rs.x<=0||ts.x<=0||Mathf.Abs(rs.x-rs.y)+Mathf.Abs(rs.x-rs.z)+Mathf.Abs(ts.x-ts.y)+Mathf.Abs(ts.x-ts.z)>0.001f)throw new InvalidOperationException("Grading requires upright terrain and roads with uniform positive scale.");
            var local=CopyRoad(p);local.points=Array.ConvertAll(p.points,v=>P(terrain.InverseTransformPoint(road.transform.TransformPoint(V(v)))));float scale=rs.x/ts.x;
            local.width*=scale;local.sidewalk*=scale;local.shoulderLeft*=scale;local.shoulderRight*=scale;local.elevationOffset*=scale;
            var next=CopyRoad(identity.construction);WorldGeometry.GradeRoadTerrain(next,local,3/ts.x);changes.Add((identity,next));
        }
        if(changes.Count==0)throw new InvalidOperationException("Create terrain before grading a road.");foreach(var change in changes){change.identity.construction=change.source;RebuildConstruction(change.identity.gameObject);}p.independentElevation=true;RebuildConstruction(road);RefreshTerrainRoads();Changed();Status("Terrain graded to road; road elevation locked. Undo restores the edit.");
    }
}
