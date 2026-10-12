using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

// Transient feedback is outside the editable world: never saved/exported or picked.
public sealed partial class WorldBuilderRuntime
{
    VisualElement feedbackOverlay;
    Label previewBadge;
    readonly List<Vector3[]> feedbackPaths=new List<Vector3[]>();
    Vector2 feedbackPointer;
    bool feedbackHover,feedbackValid=true,previewFailed;
    Transform placementPreview;
    GameObject placementPreviewObject,feedbackSelection;
    Quaternion previewRotation;
    string previewKey;
    Renderer[] selectedRenderers;
    void InitializeFeedback(Image image)
    {
        feedbackOverlay=new VisualElement{pickingMode=PickingMode.Ignore};feedbackOverlay.AddToClassList("viewport-feedback");image.Add(feedbackOverlay);
        previewBadge=new Label("PLACEMENT PREVIEW — click to place • Escape cancels"){pickingMode=PickingMode.Ignore};previewBadge.AddToClassList("preview-badge");image.Add(previewBadge);
        feedbackOverlay.generateVisualContent+=context=>{
            var painter=context.painter2D;painter.lineWidth=2;painter.strokeColor=feedbackOverlay.resolvedStyle.color;
            foreach(var path in feedbackPaths)for(int i=1;i<path.Length;i++) {
                Vector3 a=workCamera.WorldToViewportPoint(path[i-1]),b=workCamera.WorldToViewportPoint(path[i]);
                if(a.z<=workCamera.nearClipPlane||b.z<=workCamera.nearClipPlane)continue;
                painter.BeginPath();painter.MoveTo(new Vector2(a.x*image.contentRect.width,(1-a.y)*image.contentRect.height));
                painter.LineTo(new Vector2(b.x*image.contentRect.width,(1-b.y)*image.contentRect.height));painter.Stroke();
            }
        };
        image.RegisterCallback<PointerEnterEvent>(e=>feedbackHover=true);
        image.RegisterCallback<PointerLeaveEvent>(e=>{feedbackHover=false;if(placementPreview!=null)placementPreview.gameObject.SetActive(false);});
        image.RegisterCallback<PointerMoveEvent>(e=>{feedbackPointer=e.localPosition;feedbackHover=true;});
    }
    void ClearPlacementPreview()
    {
        if(placementPreview!=null){placementPreview.gameObject.SetActive(false);Destroy(placementPreview.gameObject);}
        placementPreview=null;placementPreviewObject=null;previewKey=null;previewFailed=false;
    }
    void PreparePlacementPreview()
    {
        string key=pendingCopySource!=null?"copy:"+pendingCopySource.GetInstanceID():pendingLibraryPath;
        if(key==previewKey)return;ClearPlacementPreview();previewKey=key;
        placementPreview=new GameObject("Placement preview — transient").transform;
        try {
            if(pendingCopySource!=null)placementPreviewObject=CloneObject(pendingCopySource,placementPreview);
            else {
                var document=WorkspaceDocument.Open(pendingLibraryPath);var objects=new Dictionary<string,GameObject>();int roots=0;
                foreach(var item in document.objects){if(objects.ContainsKey(item.id))throw new FormatException("Duplicate preview ID");var go=Model(item,placementPreview,31);objects.Add(item.id,go);if(string.IsNullOrEmpty(item.parentId)){placementPreviewObject=go;roots++;}}
                if(roots!=1)throw new FormatException("Preview requires one root");
                foreach(var item in document.objects)if(!string.IsNullOrEmpty(item.parentId)) {
                    if(!objects.TryGetValue(item.parentId,out var parent))throw new FormatException("Preview parent missing");var child=objects[item.id];
                    if(parent==child||parent.transform.IsChildOf(child.transform))throw new FormatException("Preview parent cycle");child.transform.SetParent(parent.transform,false);
                }
            }
            foreach(var collider in placementPreview.GetComponentsInChildren<Collider>())collider.enabled=false;
            previewRotation=placementPreviewObject.transform.localRotation;
        } catch(Exception error){previewFailed=true;placementPreview.gameObject.SetActive(false);Status("Preview unavailable: "+error.Message);throw;}
    }
    void FeedbackBounds(Renderer[] renderers)
    {
        if(renderers==null||renderers.Length==0)return;bool found=false;var bounds=new Bounds();
        foreach(var renderer in renderers)if(renderer!=null&&renderer.gameObject.activeInHierarchy){if(!found)bounds=renderer.bounds;else bounds.Encapsulate(renderer.bounds);found=true;}
        if(!found)return;var a=bounds.min;var b=bounds.max;
        var low=new[]{new Vector3(a.x,a.y,a.z),new Vector3(b.x,a.y,a.z),new Vector3(b.x,a.y,b.z),new Vector3(a.x,a.y,b.z)};
        var high=new[]{new Vector3(a.x,b.y,a.z),new Vector3(b.x,b.y,a.z),new Vector3(b.x,b.y,b.z),new Vector3(a.x,b.y,b.z)};
        feedbackPaths.Add(new[]{low[0],low[1],low[2],low[3],low[0]});feedbackPaths.Add(new[]{high[0],high[1],high[2],high[3],high[0]});
        for(int i=0;i<4;i++)feedbackPaths.Add(new[]{low[i],high[i]});
    }
    void UpdateFeedback()
    {
        if(feedbackOverlay==null||workImage==null)return;feedbackPaths.Clear();feedbackValid=true;previewBadge.style.display=HasPlacement&&modal==null?DisplayStyle.Flex:DisplayStyle.None;
        if(selected!=feedbackSelection){feedbackSelection=selected;selectedRenderers=selected!=null?selected.GetComponentsInChildren<Renderer>():null;}
        if(modal==null)FeedbackBounds(selectedRenderers);
        if(!HasPlacement&&placementPreview!=null)ClearPlacementPreview();
        if(modal==null&&feedbackHover&&(HasPlacement||IsBrush()||firstCorner.HasValue||constructionTool=="road")) {
            try {
                if(Ground(feedbackPointer,out var hit,out var terrain)) {
                    if(HasPlacement) {
                        PreparePlacementPreview();if(!previewFailed){var point=Snap(hit);placementPreview.rotation=PlacementParent().rotation;placementPreview.localScale=PlacementParent().lossyScale;placementPreviewObject.transform.localRotation=previewRotation*Quaternion.Euler(0,placementYaw,0);placementPreviewObject.transform.position=point;placementPreview.gameObject.SetActive(true);FeedbackBounds(placementPreview.GetComponentsInChildren<Renderer>());}
                    } else if(IsBrush()&&terrain!=null) {
                        var center=terrain.transform.InverseTransformPoint(hit);var ring=new Vector3[49];var source=terrain.GetComponent<WorkspaceIdentity>().construction;
                        for(int i=0;i<ring.Length;i++){float angle=i*Mathf.PI*2/48;var local=center+new Vector3(Mathf.Cos(angle)*brushRadius,0,Mathf.Sin(angle)*brushRadius);local.y=WorldGeometry.Height(source,local.x,local.z)+0.08f;ring[i]=terrain.transform.TransformPoint(local);}feedbackPaths.Add(ring);
                    } else {
                        var point=Snap(hit);
                        if(constructionTool=="road"){var points=new List<Vector3>();foreach(var p in roadPoints)points.Add(V(p));points.Add(point);if(points.Count>1)feedbackPaths.Add(points.ToArray());}
                        else if(firstCorner.HasValue){var start=firstCorner.Value;if(constructionTool=="wall")feedbackPaths.Add(new[]{start,point});else feedbackPaths.Add(new[]{start,new Vector3(point.x,start.y,start.z),point,new Vector3(start.x,point.y,point.z),start});}
                    }
                }
            } catch(Exception error){feedbackValid=false;if(placementPreview!=null)placementPreview.gameObject.SetActive(false);if(!previewFailed)Status(error.Message);}
        }
        if(modal==null&&workspaceMode=="Lot"&&activeLot!=null&&gridEnabled&&!offGrid) {
            var source=activeLot.GetComponent<WorkspaceIdentity>().construction;float spacing=gridSize*Mathf.Max(1,Mathf.Ceil(Mathf.Max(source.size.x,source.size.z)/(40*gridSize)));float y=floorLevel*3.2f+0.03f;
            for(float x=-source.size.x/2;x<=source.size.x/2;x+=spacing)feedbackPaths.Add(new[]{activeLot.transform.TransformPoint(new Vector3(x,y,-source.size.z/2)),activeLot.transform.TransformPoint(new Vector3(x,y,source.size.z/2))});
            for(float z=-source.size.z/2;z<=source.size.z/2;z+=spacing)feedbackPaths.Add(new[]{activeLot.transform.TransformPoint(new Vector3(-source.size.x/2,y,z)),activeLot.transform.TransformPoint(new Vector3(source.size.x/2,y,z))});
        }
        feedbackOverlay.EnableInClassList("invalid",!feedbackValid);feedbackOverlay.MarkDirtyRepaint();
    }
}
