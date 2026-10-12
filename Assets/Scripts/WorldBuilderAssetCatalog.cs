using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    sealed class ThumbnailRequest { public string path; public Image image; }
    readonly Queue<ThumbnailRequest> thumbnailQueue=new Queue<ThumbnailRequest>();
    Coroutine thumbnailRoutine;
    Camera thumbnailCamera;
    RenderTexture thumbnailTexture;
    Transform thumbnailRoot;
    void BuildAssetCatalog(VisualElement parent,bool simsOnly=false,bool returnToLibrary=false)
    {
        var host=new VisualElement();host.AddToClassList("asset-catalog");parent.Add(host);
        var search=new TextField("Search assets");host.Add(search);int page=0;
        var grid=new VisualElement();grid.AddToClassList("asset-grid");host.Add(grid);
        var filters=Row(host,"catalog-tabs");var browse=new DropdownField("Browse",new List<string>{"All objects","By room","By type"},0);filters.Add(browse);
        var filter=new DropdownField("Category",new List<string>{"All"},0);filters.Add(filter);
        var pageLabel=Label(host,"","hint");
        void Populate() {
            grid.Clear();int matched=0,shown=0;bool more=false;
            if(Directory.Exists(LibraryFolder))foreach(string path in Directory.EnumerateFiles(LibraryFolder,"*.wbworld")) {
                try {
                    string metaPath=path+".metadata.json";var metadata=File.Exists(metaPath)?JsonUtility.FromJson<LibraryMetadata>(File.ReadAllText(metaPath)):null;
                    string name=metadata?.name??WorkspaceDocument.Open(path).title;
                    string classification=browse.value=="By room"?(metadata?.room??"Unclassified"):(metadata?.category??"Unclassified");
                    if(string.IsNullOrWhiteSpace(classification))classification="Unclassified";
                    if(browse.value!="All objects"&&filter.value!="All"&&classification!=filter.value)continue;
                    if(simsOnly&&!name.StartsWith("The Sims 4 /",StringComparison.OrdinalIgnoreCase))continue;
                    if(name.IndexOf(search.value??"",StringComparison.OrdinalIgnoreCase)<0)continue;
                    if(matched++<page*12)continue;if(shown>=12){more=true;break;}shown++;
                    string assetPath=path;var tile=new Button(()=>Try(()=>OpenLibraryPreview(assetPath,returnToLibrary)));tile.AddToClassList("asset-tile");grid.Add(tile);
                    var image=new Image{scaleMode=ScaleMode.ScaleToFit,pickingMode=PickingMode.Ignore};image.AddToClassList("asset-thumbnail");tile.Add(image);
                    string label=Path.GetFileNameWithoutExtension(name);if(name.StartsWith("The Sims 4 /",StringComparison.OrdinalIgnoreCase)&&label.Length>24)label="Sims object "+label.Substring(label.Length-12);var caption=new Label(label){pickingMode=PickingMode.Ignore};caption.AddToClassList("asset-caption");tile.Add(caption);
                    tile.tooltip=name+(string.IsNullOrEmpty(metadata?.warning)?"":"\n"+metadata.warning);RequestThumbnail(path,image);
                } catch(Exception error){Label(grid,"Asset unavailable: "+error.Message,"hint");}
            }
            pageLabel.text="Page "+(page+1)+" • "+shown+" assets"+(more?" • more available":"");
            if(shown==0)Label(grid,simsOnly?"No matching Sims objects. Use Add Sims Assets or adjust search.":"No matching assets. Add Sims assets or save an object to the library.","hint");
        }
        var navigation=Row(host,"toolbar");Button(navigation,"Previous",()=>{page=Math.Max(0,page-1);Populate();});Button(navigation,"Next",()=>{page++;Populate();});
        browse.RegisterValueChangedCallback(e=>{var values=new List<string>{"All"};if(e.newValue=="By room")values.AddRange(AssetRooms);else if(e.newValue=="By type")values.AddRange(AssetTypes);filter.choices=values;filter.SetValueWithoutNotify("All");filter.style.display=e.newValue=="All objects"?DisplayStyle.None:DisplayStyle.Flex;page=0;Populate();});
        filter.style.display=DisplayStyle.None;filter.RegisterValueChangedCallback(e=>{page=0;Populate();});
        search.RegisterValueChangedCallback(e=>{page=0;Populate();});Populate();
    }
    void RequestThumbnail(string path,Image image)
    {
        Texture2D texture=null;image.RegisterCallback<DetachFromPanelEvent>(e=>{if(texture!=null)Destroy(texture);texture=null;});
        void Load() {
            string file=path+".preview.png";if(!File.Exists(file))return;
            if(new FileInfo(file).Length>4*1024*1024)return;
            texture=new Texture2D(2,2);if(!texture.LoadImage(File.ReadAllBytes(file))){Destroy(texture);texture=null;return;}image.image=texture;
        }
        if(File.Exists(path+".preview.png")){Load();return;}
        image.userData=(Action)Load;thumbnailQueue.Enqueue(new ThumbnailRequest{path=path,image=image});
        if(thumbnailRoutine==null)thumbnailRoutine=StartCoroutine(RenderCatalogThumbnails());
    }
    void ClearThumbnailStage()
    {
        if(thumbnailRoot!=null){thumbnailRoot.gameObject.SetActive(false);Destroy(thumbnailRoot.gameObject);thumbnailRoot=null;}
        if(thumbnailCamera!=null){thumbnailCamera.enabled=false;Destroy(thumbnailCamera.gameObject);thumbnailCamera=null;}
        if(thumbnailTexture!=null){thumbnailTexture.Release();Destroy(thumbnailTexture);thumbnailTexture=null;}
    }
    IEnumerator RenderCatalogThumbnails()
    {
        // Wait for cards to attach, then render one actual asset per frame.
        yield return null;
        while(thumbnailQueue.Count>0) {
            var request=thumbnailQueue.Dequeue();if(request.image.panel==null)continue;
            bool ready=false;
            try {
                var document=WorkspaceDocument.Open(request.path);thumbnailRoot=new GameObject("Catalog thumbnail — transient").transform;
                var objects=new Dictionary<string,GameObject>();
                foreach(var item in document.objects)objects.Add(item.id,Model(item,thumbnailRoot,28));
                foreach(var item in document.objects)if(!string.IsNullOrEmpty(item.parentId)) {
                    if(!objects.TryGetValue(item.parentId,out var parent))throw new FormatException("Thumbnail parent missing");var child=objects[item.id];
                    if(parent==child||parent.transform.IsChildOf(child.transform))throw new FormatException("Thumbnail parent cycle");child.transform.SetParent(parent.transform,false);
                }
                foreach(var collider in thumbnailRoot.GetComponentsInChildren<Collider>())collider.enabled=false;
                bool found=false;var bounds=new Bounds();foreach(var renderer in thumbnailRoot.GetComponentsInChildren<Renderer>()){if(!found)bounds=renderer.bounds;else bounds.Encapsulate(renderer.bounds);found=true;}
                if(!found)throw new FormatException("No thumbnail geometry");
                thumbnailCamera=CameraFor("Catalog thumbnail camera",28,out thumbnailTexture);thumbnailTexture.Release();thumbnailTexture.width=256;thumbnailTexture.height=192;thumbnailTexture.Create();thumbnailCamera.aspect=256f/192;
                PositionCamera(thumbnailCamera,new Vector2(20,-30),bounds.center,Mathf.Max(1,bounds.extents.magnitude*3));ready=true;
            } catch(Exception error){request.image.tooltip="Preview unavailable: "+error.Message;}
            if(ready) {
                yield return new WaitForEndOfFrame();
                var previous=RenderTexture.active;Texture2D capture=null;
                try {
                    RenderTexture.active=thumbnailTexture;capture=new Texture2D(256,192,TextureFormat.RGB24,false);capture.ReadPixels(new Rect(0,0,256,192),0,0);capture.Apply();
                    WorkspaceAtomicFile.WriteBytes(request.path+".preview.png",capture.EncodeToPNG());
                    if(request.image.panel!=null)(request.image.userData as Action)?.Invoke();
                } catch(Exception error){request.image.tooltip="Preview unavailable: "+error.Message;}
                finally {RenderTexture.active=previous;if(capture!=null)Destroy(capture);}
            }
            ClearThumbnailStage();yield return null;
        }
        thumbnailRoutine=null;
    }
    void DisposeCatalogThumbnails()
    {
        if(thumbnailRoutine!=null)StopCoroutine(thumbnailRoutine);thumbnailRoutine=null;thumbnailQueue.Clear();ClearThumbnailStage();
    }
}
