using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    Camera libraryPreviewCamera;
    RenderTexture libraryPreviewTexture;
    Transform libraryPreviewRoot;
    Vector2 libraryPreviewAngles=new Vector2(20,-30);
    Vector3 libraryPreviewCenter;
    float libraryPreviewDistance=4;
    void UpdateLibraryPreviewCamera()
    {
        if(libraryPreviewCamera!=null)PositionCamera(libraryPreviewCamera,libraryPreviewAngles,libraryPreviewCenter,libraryPreviewDistance);
    }
    void DisposeLibraryPreview()
    {
        if(libraryPreviewCamera!=null){libraryPreviewCamera.enabled=false;Destroy(libraryPreviewCamera.gameObject);}
        if(libraryPreviewRoot!=null){libraryPreviewRoot.gameObject.SetActive(false);Destroy(libraryPreviewRoot.gameObject);}
        if(libraryPreviewTexture!=null){libraryPreviewTexture.Release();Destroy(libraryPreviewTexture);}
        libraryPreviewCamera=null;libraryPreviewRoot=null;libraryPreviewTexture=null;
    }
    void OpenLibraryPreview(string path,bool returnToLibrary=false)
    {
        Try(()=>{
            var document=WorkspaceDocument.Open(path);
            string metadataPath=path+".metadata.json";
            var metadata=File.Exists(metadataPath)?JsonUtility.FromJson<LibraryMetadata>(File.ReadAllText(metadataPath)):null;
            Dialog(metadata?.name??document.title,"Read-only asset preview. Right-drag to orbit, middle-drag to pan and wheel to zoom. Choose Place when ready.",box=>{
                try {
                    libraryPreviewRoot=new GameObject("Library preview — read only").transform;
                    var objects=new Dictionary<string,GameObject>();int roots=0;
                    foreach(var item in document.objects){if(string.IsNullOrEmpty(item.id)||objects.ContainsKey(item.id))throw new FormatException("Invalid preview object ID");objects.Add(item.id,Model(item,libraryPreviewRoot,29));if(string.IsNullOrEmpty(item.parentId))roots++;}
                    if(roots!=1)throw new FormatException("Library preview requires one root");
                    foreach(var item in document.objects)if(!string.IsNullOrEmpty(item.parentId)){
                        if(!objects.TryGetValue(item.parentId,out var parent))throw new FormatException("Missing preview parent");var child=objects[item.id];
                        if(child==parent||parent.transform.IsChildOf(child.transform))throw new FormatException("Cyclic preview parent");child.transform.SetParent(parent.transform,false);
                    }
                    foreach(var collider in libraryPreviewRoot.GetComponentsInChildren<Collider>())collider.enabled=false;
                    bool found=false;var bounds=new Bounds();int vertices=0,triangles=0;
                    foreach(var renderer in libraryPreviewRoot.GetComponentsInChildren<Renderer>()){if(!found)bounds=renderer.bounds;else bounds.Encapsulate(renderer.bounds);found=true;var mesh=renderer.GetComponent<MeshFilter>().sharedMesh;vertices+=mesh.vertexCount;triangles+=mesh.triangles.Length/3;}
                    if(!found)throw new FormatException("Asset contains no renderable mesh");
                    libraryPreviewCenter=bounds.center;libraryPreviewDistance=Mathf.Max(1,bounds.extents.magnitude*3);libraryPreviewAngles=new Vector2(20,-30);
                    libraryPreviewCamera=CameraFor("Library preview camera",29,out libraryPreviewTexture);
                    var image=new Image{image=libraryPreviewTexture,scaleMode=ScaleMode.StretchToFill};image.AddToClassList("library-preview-image");box.Add(image);
                    int drag=-1;Vector2 previous=Vector2.zero;
                    image.RegisterCallback<PointerDownEvent>(e=>{if(e.button!=1&&e.button!=2)return;drag=e.button;previous=e.position;image.CapturePointer(e.pointerId);e.StopPropagation();});
                    image.RegisterCallback<PointerMoveEvent>(e=>{if(drag<0)return;Vector2 point=e.position,delta=point-previous;previous=point;if(drag==1){libraryPreviewAngles+=new Vector2(delta.y,delta.x)*0.25f;libraryPreviewAngles.x=Mathf.Clamp(libraryPreviewAngles.x,-89,89);}else libraryPreviewCenter+=(-libraryPreviewCamera.transform.right*delta.x+libraryPreviewCamera.transform.up*delta.y)*libraryPreviewDistance*0.002f;e.StopPropagation();});
                    image.RegisterCallback<PointerUpEvent>(e=>{drag=-1;image.ReleasePointer(e.pointerId);});image.RegisterCallback<PointerCaptureOutEvent>(e=>drag=-1);
                    image.RegisterCallback<WheelEvent>(e=>{libraryPreviewDistance=Mathf.Clamp(libraryPreviewDistance*Mathf.Exp(e.delta.y*0.08f),0.1f,10000);e.StopPropagation();});
                    image.RegisterCallback<GeometryChangedEvent>(e=>{if(libraryPreviewTexture==null||e.newRect.width<2||e.newRect.height<2)return;libraryPreviewTexture.Release();libraryPreviewTexture.width=Mathf.Clamp(Mathf.RoundToInt(e.newRect.width),128,1280);libraryPreviewTexture.height=Mathf.Clamp(Mathf.RoundToInt(e.newRect.height),128,720);libraryPreviewTexture.Create();libraryPreviewCamera.aspect=e.newRect.width/e.newRect.height;});
                    Label(box,vertices+" vertices • "+triangles+" triangles • "+document.objects.Count+" parts","hint");
                    if(!string.IsNullOrEmpty(metadata?.warning))Label(box,"Import warning: "+metadata.warning,"hint");
                    Button(box,"Place in world / active lot",()=>BeginLibraryPlacement(path));
                } catch(Exception error){DisposeLibraryPreview();Label(box,"Preview unavailable: "+error.Message,"hint");}
                Button(box,"Organize asset",()=>OpenAssetOrganization(path,returnToLibrary));
                Button(box,"Back to catalog",()=>{if(returnToLibrary)OpenLibrary();else CloseDialog();});Button(box,"Close",CloseDialog);
            });
        });
    }
}
