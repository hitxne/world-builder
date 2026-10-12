using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    bool roadDrag,roadsideObjects;
    float roadSidewalk=1.2f;
    string roadPreset="Local street";
    Vector3 roadDragStart,roadDragEnd,roadPreviewEnd;
    GameObject roadDragPreview;
    Button finishRouteButton;
    readonly List<Vector3> roadSnapPoints=new List<Vector3>();
    void RoadBuildCatalog(VisualElement choices,VisualElement settings)
    {
        var sections=Row(choices,"road-sections");
        var draw=Button(sections,"Build roads",()=>{CancelConstruction();roadsideObjects=false;BuildConstructionPanel();});draw.EnableInClassList("selected",!roadsideObjects);
        var props=Button(sections,"Roadside objects",()=>{CancelConstruction();roadsideObjects=true;BuildConstructionPanel();});props.EnableInClassList("selected",roadsideObjects);
        if(roadsideObjects){BuildAssetCatalog(choices);return;}
        var presets=Row(choices,"road-presets");
        foreach(string name in new[]{"Local street","Avenue","Country road"}) {
            string value=name;var tile=Button(presets,value,()=>{roadPreset=value;roadWidth=value=="Avenue"?12:6;roadSidewalk=value=="Country road"?0:value=="Avenue"?1.5f:1.2f;SetTool("road");BuildConstructionPanel();});
            tile.EnableInClassList("selected",value==roadPreset);
        }
        var tools=Row(choices,"road-drawing-tools");ToolChoice(tools,"Straight road","road");ToolChoice(tools,"Curved route","roadcurve");
        finishRouteButton=Button(tools,"Finish route",FinishRoad);finishRouteButton.style.display=constructionTool=="roadcurve"?DisplayStyle.Flex:DisplayStyle.None;
        Number(settings,"Road width (m)",roadWidth,2,20,v=>roadWidth=v);Number(settings,"Sidewalk (m)",roadSidewalk,0,5,v=>roadSidewalk=v);
        var snap=new Toggle("Snap to grid and road ends"){value=gridEnabled};settings.Add(snap);snap.RegisterValueChangedCallback(e=>gridEnabled=e.newValue);
    }
    void CacheRoadEnds()
    {
        roadSnapPoints.Clear();
        foreach(var identity in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            var road=identity.construction;if(road?.kind!="road"||road.points==null||road.points.Length<2)continue;
            roadSnapPoints.Add(identity.transform.TransformPoint(V(road.points[0])));roadSnapPoints.Add(identity.transform.TransformPoint(V(road.points[road.points.Length-1])));
        }
    }
    void BeginRoadDrag(Vector3 point)
    {
        CacheRoadEnds();
        roadDragStart=RoadEndSnap(point);roadDragEnd=roadDragStart;roadPreviewEnd=new Vector3(float.PositiveInfinity,0,0);roadDrag=true;
    }
    Vector3 RoadEndSnap(Vector3 point)
    {
        point=Snap(point);if(!gridEnabled||offGrid)return point;
        float best=Mathf.Max(2,gridSize*2);Vector3 nearest=point;
        foreach(var endpoint in roadSnapPoints){float distance=new Vector2(point.x-endpoint.x,point.z-endpoint.z).magnitude;if(distance<best){best=distance;nearest=endpoint;}}
        return nearest;
    }
    Vector3 RoadDragPoint(Vector3 point)
    {
        point=RoadEndSnap(point);
        if(gridEnabled&&!offGrid) {
            // Exact connection wins over angle snapping.
            foreach(var endpoint in roadSnapPoints)if((point-endpoint).sqrMagnitude<0.0001f)return point;
            Vector3 delta=point-roadDragStart;float length=new Vector2(delta.x,delta.z).magnitude;
            float angle=Mathf.Round(Mathf.Atan2(delta.z,delta.x)/(Mathf.PI/4))*(Mathf.PI/4);
            float step=Mathf.Abs(Mathf.Cos(angle))>0.1f&&Mathf.Abs(Mathf.Sin(angle))>0.1f?gridSize*Mathf.Sqrt(2):gridSize;length=Mathf.Round(length/step)*step;
            point.x=roadDragStart.x+Mathf.Cos(angle)*length;point.z=roadDragStart.z+Mathf.Sin(angle)*length;
        }return point;
    }
    void UpdateRoadDrag(Vector3 point)
    {
        roadDragEnd=RoadDragPoint(point);if((roadDragEnd-roadPreviewEnd).sqrMagnitude<0.0001f)return;roadPreviewEnd=roadDragEnd;ClearRoadDragPreview();
        if(new Vector2(roadDragEnd.x-roadDragStart.x,roadDragEnd.z-roadDragStart.z).magnitude<0.25f)return;
        var data=ConstructionData(new WorldConstruction{kind="road",points=new[]{P(roadDragStart),P(roadDragEnd)},width=roadWidth,sidewalk=roadSidewalk});data.name="Road preview — transient";
        var stage=new GameObject("Road drag preview — transient").transform;
        try {roadDragPreview=Model(data,stage,31);RebuildConstruction(roadDragPreview);roadDragPreview.transform.SetParent(null,false);foreach(var collider in roadDragPreview.GetComponentsInChildren<Collider>())collider.enabled=false;}
        finally {Destroy(stage.gameObject);}
    }
    void ClearRoadDragPreview(){if(roadDragPreview!=null){roadDragPreview.SetActive(false);Destroy(roadDragPreview);roadDragPreview=null;}}
    void EndRoadDrag(bool cancel)
    {
        if(!roadDrag)return;roadDrag=false;ClearRoadDragPreview();
        if(cancel)return;
        if(new Vector2(roadDragEnd.x-roadDragStart.x,roadDragEnd.z-roadDragStart.z).magnitude<0.25f){Status("Drag from one road endpoint to another.");return;}
        CreateConstruction(roadPreset,new WorldConstruction{kind="road",points=new[]{P(roadDragStart),P(roadDragEnd)},width=roadWidth,sidewalk=roadSidewalk},Vector3.zero,world);
        Changed();Status("Road built. Drag the next segment; Escape cancels the tool.");
    }
}
