using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    bool junctionCatalog,roadNodeDrag;
    int roadNodeIndex=-1;
    GameObject roadNodeObject;
    WorldConstruction roadNodeBefore;
    void OpenJunctionSettings(GameObject target=null)
    {
        var draft=target!=null?CopyRoad(target.GetComponent<WorkspaceIdentity>().construction):new WorldConstruction{kind="junction",size=new WorldPoint(20,0,20),junctionRadius=4};
        Dialog(target==null?"New junction":"Junction settings — "+target.name,"Radius rounds the corners. Roads connect to separate sides and slide along those sides.",box=>{
            Number(box,"Width (m)",draft.size.x,4,100,v=>draft.size.x=v);Number(box,"Depth (m)",draft.size.z,4,100,v=>draft.size.z=v);Number(box,"Corner radius (m)",draft.junctionRadius,0,50,v=>draft.junctionRadius=v);
            Number(box,"Height offset (m)",draft.elevationOffset,-100,200,v=>draft.elevationOffset=v);
            Button(box,"Apply",()=>{WorldGeometry.Build(draft);if(target!=null){ValidateJunctionChange(target,draft);target.GetComponent<WorkspaceIdentity>().construction=draft;RebuildConstruction(target);Changed();}else{junctionStyle=draft;SetTool("junction");}CloseDialog();});Button(box,"Cancel",CloseDialog);
        });
    }
    WorldConstruction junctionStyle=new WorldConstruction{kind="junction",size=new WorldPoint(20,0,20),junctionRadius=4};
    Dictionary<string,WorkspaceIdentity> Junctions()
    {
        var result=new Dictionary<string,WorkspaceIdentity>();foreach(var identity in world.GetComponentsInChildren<WorkspaceIdentity>())if(identity.construction?.kind=="junction"&&!string.IsNullOrEmpty(identity.id))result[identity.id]=identity;return result;
    }
    void ValidateJunctionChange(GameObject target,WorldConstruction draft)
    {
        string id=target.GetComponent<WorkspaceIdentity>().id;
        foreach(var road in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            var p=road.construction;if(p?.kind!="road")continue;
            if(p.startJunction==id)WorldGeometry.JunctionPort(draft,p.startPort,p.startConnectionOffset,p.width*road.transform.lossyScale.x/target.transform.lossyScale.x);
            if(p.endJunction==id)WorldGeometry.JunctionPort(draft,p.endPort,p.endConnectionOffset,p.width*road.transform.lossyScale.x/target.transform.lossyScale.x);
        }
    }
    void ValidateRoadConnections(GameObject road,WorldConstruction p)
    {
        var junctions=Junctions();var copy=CopyRoad(p);
        foreach(bool start in new[]{true,false}) {
            string id=start?p.startJunction:p.endJunction;if(string.IsNullOrEmpty(id))continue;
            if(!junctions.TryGetValue(id,out var junction))throw new InvalidOperationException("The selected junction no longer exists.");
            var port=WorldGeometry.JunctionPort(junction.construction,start?p.startPort:p.endPort,start?p.startConnectionOffset:p.endConnectionOffset,p.width*road.transform.lossyScale.x/junction.transform.lossyScale.x);
            copy.points[start?0:copy.points.Length-1]=P(road.transform.InverseTransformPoint(junction.transform.TransformPoint(V(port))));
        }
        WorldGeometry.Build(copy);
    }
    void UpdateRoadConnections()
    {
        if(world==null)return;var junctions=Junctions();
        foreach(var road in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            var p=road.construction;if(p?.kind!="road"||p.points==null||p.points.Length<2)continue;bool changed=false;
            foreach(bool start in new[]{true,false}) {
                string id=start?p.startJunction:p.endJunction;if(string.IsNullOrEmpty(id))continue;
                if(!junctions.TryGetValue(id,out var junction)){if(start)p.startJunction=null;else p.endJunction=null;continue;}
                int port=start?p.startPort:p.endPort;float offset=start?p.startConnectionOffset:p.endConnectionOffset;
                var local=WorldGeometry.JunctionPort(junction.construction,port,offset,p.width*road.transform.lossyScale.x/junction.transform.lossyScale.x);
                float effective=port%2==0?local.x:local.z;if(start)p.startConnectionOffset=effective;else p.endConnectionOffset=effective;
                var point=P(road.transform.InverseTransformPoint(junction.transform.TransformPoint(V(local))));int at=start?0:p.points.Length-1;
                if((point-p.points[at]).Length>0.00001f){p.points[at]=point;changed=true;}
            }
            if(changed)RebuildConstruction(road.gameObject);
        }
    }
    Vector3 RoadNodeDisplay(GameObject road,WorldPoint point,WorkspaceIdentity[] terrains)
    {
        var p=road.GetComponent<WorkspaceIdentity>().construction;
        if(p.FollowTerrain){var projected=ProjectRoadVertex(road.transform,terrains,point,p.elevationOffset+0.08f);if(projected.HasValue)return road.transform.TransformPoint(V(projected.Value));}
        return road.transform.TransformPoint(V(point)+Vector3.up*(p.elevationOffset+0.08f));
    }
    bool BeginRoadNode(Vector2 pointer)
    {
        if(selected==null||selected.GetComponent<WorkspaceIdentity>()?.construction?.kind!="road"){Pick(pointer);if(selected==null||selected.GetComponent<WorkspaceIdentity>()?.construction?.kind!="road")return false;}
        var p=selected.GetComponent<WorkspaceIdentity>().construction;float closest=20;int index=-1;
        var terrains=world.GetComponentsInChildren<WorkspaceIdentity>();
        for(int i=0;i<p.points.Length;i++){var view=workCamera.WorldToViewportPoint(RoadNodeDisplay(selected,p.points[i],terrains));if(view.z<=0)continue;float distance=Vector2.Distance(pointer,new Vector2(view.x*workImage.contentRect.width,(1-view.y)*workImage.contentRect.height));if(distance<closest){closest=distance;index=i;}}
        if(index<0){Status("Click a road control point to drag it.");return false;}
        roadNodeObject=selected;roadNodeIndex=index;roadNodeBefore=CopyRoad(p);roadNodeDrag=true;return true;
    }
    void MoveRoadNode(Vector3 point)
    {
        var p=roadNodeObject.GetComponent<WorkspaceIdentity>().construction;point=Snap(point);
        bool start=roadNodeIndex==0,end=roadNodeIndex==p.points.Length-1;string id=start?p.startJunction:end?p.endJunction:null;
        if(!string.IsNullOrEmpty(id)&&Junctions().TryGetValue(id,out var junction)) {
            int port=start?p.startPort:p.endPort;var local=junction.transform.InverseTransformPoint(point);float offset=port%2==0?local.x:local.z;
            if(start)p.startConnectionOffset=offset;else p.endConnectionOffset=offset;UpdateRoadConnections();
        } else {var local=P(roadNodeObject.transform.InverseTransformPoint(point));if(!p.FollowTerrain)local.y=p.points[roadNodeIndex].y;p.points[roadNodeIndex]=local;RebuildConstruction(roadNodeObject);}
    }
    void EndRoadNode(bool cancel)
    {
        if(!roadNodeDrag)return;roadNodeDrag=false;
        if(roadNodeObject!=null){if(cancel){roadNodeObject.GetComponent<WorkspaceIdentity>().construction=roadNodeBefore;RebuildConstruction(roadNodeObject);Refresh();}else Changed();}
        roadNodeObject=null;roadNodeBefore=null;roadNodeIndex=-1;
    }
}
