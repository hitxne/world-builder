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
        int page=0;string browse="By room",filter="All";
        var top=Row(host,"buy-catalog-header");var search=new TextField("Search"){tooltip="Search object names"};search.AddToClassList("buy-search");top.Add(search);
        var browseTabs=Row(top,"buy-browse-tabs");var tabButtons=new Dictionary<string,Button>();
        var content=Row(host,"buy-catalog-content");var categoryRail=new ScrollView();categoryRail.AddToClassList("buy-category-rail");content.Add(categoryRail);
        var results=new VisualElement();results.AddToClassList("buy-results");content.Add(results);
        var gridScroll=new ScrollView();gridScroll.AddToClassList("buy-grid-scroll");results.Add(gridScroll);
        var grid=new VisualElement();grid.AddToClassList("asset-grid");gridScroll.Add(grid);
        var navigation=Row(results,"buy-pagination");var pageLabel=Label(navigation,"","buy-result-heading");
        Button previous=null,next=null;
        void Populate() {
            grid.Clear();int matched=0,shown=0;bool more=false;
            if(Directory.Exists(LibraryFolder))foreach(string path in Directory.EnumerateFiles(LibraryFolder,"*.wbworld")) {
                try {
                    string metaPath=path+".metadata.json";var metadata=File.Exists(metaPath)?JsonUtility.FromJson<LibraryMetadata>(File.ReadAllText(metaPath)):null;
                    string name=metadata?.name??WorkspaceDocument.Open(path).title;
                    string classification=browse=="By room"?(metadata?.room??"Unclassified"):(metadata?.category??"Unclassified");
                    if(string.IsNullOrWhiteSpace(classification))classification="Unclassified";
                    if(browse!="All objects"&&filter!="All"&&classification!=filter&&Array.IndexOf((browse=="By room"?metadata?.rooms:metadata?.categories)??new string[0],filter)<0)continue;
                    if(simsOnly&&string.IsNullOrEmpty(metadata?.catalogSource)&&!name.StartsWith("The Sims 4 /",StringComparison.OrdinalIgnoreCase))continue;
                    if(name.IndexOf(search.value??"",StringComparison.OrdinalIgnoreCase)<0)continue;
                    if(matched++<page*12)continue;if(shown>=12){more=true;break;}shown++;
                    string assetPath=path;var card=new VisualElement();card.AddToClassList("asset-card");grid.Add(card);
                    var tile=new Button(()=>Try(()=>BeginLibraryPlacement(assetPath)));tile.AddToClassList("asset-tile");card.Add(tile);
                    var image=new Image{scaleMode=ScaleMode.ScaleToFit,pickingMode=PickingMode.Ignore};image.AddToClassList("asset-thumbnail");tile.Add(image);
                    string label=string.IsNullOrEmpty(metadata?.catalogSource)?Path.GetFileNameWithoutExtension(name):name;if(name.StartsWith("The Sims 4 /",StringComparison.OrdinalIgnoreCase)&&label.Length>24&&string.IsNullOrEmpty(metadata?.catalogSource))label="Sims object "+label.Substring(label.Length-12);var caption=new Label(label){pickingMode=PickingMode.Ignore};caption.AddToClassList("asset-caption");tile.Add(caption);
                    tile.tooltip=name+"\nClick to place; use ⋯ for preview and details."+(string.IsNullOrEmpty(metadata?.warning)?"":"\n"+metadata.warning);RequestThumbnail(path,image);
                    var details=new Button(()=>Try(()=>OpenLibraryPreview(assetPath,returnToLibrary))){text="⋯",tooltip="3D preview and asset details"};details.AddToClassList("asset-details");card.Add(details);
                } catch(Exception error){Label(grid,"Asset unavailable: "+error.Message,"hint");}
            }
            pageLabel.text=(filter=="All"?"All objects":filter)+" • Page "+(page+1);previous?.SetEnabled(page>0);next?.SetEnabled(more);
            if(shown==0)Label(grid,simsOnly?"No matching Sims objects. Use Add Sims Assets or adjust search.":"No matching assets. Add Sims assets or save an object to the library.","hint");
        }
        previous=Button(navigation,"‹",()=>{page=Math.Max(0,page-1);Populate();});previous.tooltip="Previous objects";
        next=Button(navigation,"›",()=>{page++;Populate();});next.tooltip="Next objects";
        void Categories() {
            categoryRail.Clear();categoryRail.style.display=browse=="All objects"?DisplayStyle.None:DisplayStyle.Flex;
            var values=new List<string>{"All"};if(browse=="By room")values.AddRange(AssetRooms);else if(browse=="By function")values.AddRange(AssetTypes);
            foreach(string value in values) {
                string label=value;var button=new Button(()=>{filter=label;page=0;Categories();Populate();});button.AddToClassList("buy-category-button");
                if(label==filter)button.AddToClassList("selected");button.Add(new CatalogCategoryIcon(label));button.Add(new Label(label=="All"?"All objects":label){pickingMode=PickingMode.Ignore});categoryRail.Add(button);
            }
            foreach(var pair in tabButtons)pair.Value.EnableInClassList("selected",pair.Key==browse);
        }
        foreach(string mode in new[]{"By room","By function","All objects"}) {string value=mode;tabButtons[value]=Button(browseTabs,value,()=>{browse=value;filter="All";page=0;Categories();Populate();});}
        search.RegisterValueChangedCallback(e=>{page=0;Populate();});Categories();Populate();
    }
    sealed class CatalogCategoryIcon:VisualElement
    {
        readonly string category;
        public CatalogCategoryIcon(string category){this.category=category;pickingMode=PickingMode.Ignore;AddToClassList("buy-category-icon");generateVisualContent+=Draw;}
        void Draw(MeshGenerationContext context) {
            var p=context.painter2D;p.strokeColor=resolvedStyle.color;p.lineWidth=1.6f;
            void Line(float x,float y,float a,float b){p.BeginPath();p.MoveTo(new Vector2(x,y));p.LineTo(new Vector2(a,b));p.Stroke();}
            void Box(float x,float y,float w,float h){p.BeginPath();p.MoveTo(new Vector2(x,y));p.LineTo(new Vector2(x+w,y));p.LineTo(new Vector2(x+w,y+h));p.LineTo(new Vector2(x,y+h));p.ClosePath();p.Stroke();}
            if(category=="Bedroom"||category=="Beds"){Box(3,8,22,14);Box(5,9,7,4);Box(15,9,7,4);Line(3,15,25,15);}
            else if(category=="Living room"||category=="Seating"){Box(6,9,16,12);Box(3,14,4,8);Box(22,14,4,8);Line(7,17,22,17);}
            else if(category=="Kitchen"||category=="Appliances"){Box(5,4,18,20);Box(7,7,14,4);Box(8,15,12,7);}
            else if(category=="Bathroom"||category=="Plumbing"){Box(3,13,22,9);Line(5,9,5,13);Line(5,9,10,9);Line(7,22,7,25);Line(22,22,22,25);}
            else if(category=="Office"||category=="Tables"||category=="Dining room"){Box(3,13,22,3);Line(6,16,6,25);Line(22,16,22,25);Box(9,3,10,8);Line(14,11,14,13);}
            else if(category=="Outdoors"||category=="Plants"){Line(14,15,14,25);Line(14,2,3,17);Line(3,17,25,17);Line(25,17,14,2);}
            else if(category=="Lighting"){Line(14,14,14,25);Line(8,25,20,25);Line(9,4,5,14);Line(5,14,23,14);Line(23,14,19,4);Line(19,4,9,4);}
            else if(category=="Doors"||category=="Windows"){Box(5,3,18,23);Line(14,3,14,26);if(category=="Windows")Line(5,14,23,14);}
            else {Box(4,4,8,8);Box(16,4,8,8);Box(4,16,8,8);Box(16,16,8,8);}
        }
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
