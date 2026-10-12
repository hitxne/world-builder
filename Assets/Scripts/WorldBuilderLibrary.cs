using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    string LibraryFolder=>Path.Combine(Application.persistentDataPath,"Assets");
    void SaveLibrary()
    {
        if(selected==null){Status("Select an object or a lot/building first.");return;}
        Try(()=>{
            Directory.CreateDirectory(LibraryFolder);
            var document=WorkspaceDocument.Capture(selected.transform,selected.name);
            string id=selected.GetComponent<WorkspaceIdentity>().libraryId;
            if(string.IsNullOrEmpty(id))id=Guid.NewGuid().ToString("N");
            string rootId=selected.GetComponent<WorkspaceIdentity>().id;
            foreach(var item in document.objects)if(item.id==rootId){item.parentId=null;item.position=Vector3.zero;}
            document.Save(Path.Combine(LibraryFolder,id+".wbworld"));
            selected.GetComponent<WorkspaceIdentity>().libraryId=id;Changed();Status("Saved reusable asset/building to the local library.");
        });
    }
    void OpenLibrary()
    {
        Dialog("Local Asset Library","Reusable objects and buildings persist between sessions. Select one, then click the terrain or active lot to place an independent editable copy.",box=>{
            var search=new TextField("Search");box.Add(search);var list=new ScrollView();list.style.height=300;box.Add(list);
            void Populate(string query) {
                list.Clear();if(!Directory.Exists(LibraryFolder)){Label(list,"Save a selected object or lot to add your first asset.","hint");return;}
                int count=0;
                foreach(string path in Directory.EnumerateFiles(LibraryFolder,"*.wbworld")) {
                    if(count++>=200)break;
                    try {
                        var document=WorkspaceDocument.Open(path);if(document.title.IndexOf(query??"",StringComparison.OrdinalIgnoreCase)<0)continue;
                        string assetPath=path;Button(list,document.title,()=>BeginLibraryPlacement(assetPath));
                    } catch {Label(list,"Unreadable asset: "+Path.GetFileName(path),"hint");}
                }
            }
            search.RegisterValueChangedCallback(e=>Populate(e.newValue));Populate("");Button(box,"Close",CloseDialog);
        });
    }
    void BeginLibraryPlacement(string path)
    {
        CancelConstruction();
        if(workspaceMode=="Asset")SetMode("World");
        pendingLibraryPath=path;CloseDialog();RefreshWorldTools();Status(ToolInstruction());
    }
    void PlaceLibrary(string path,Vector3 position)
    {
            var document=WorkspaceDocument.Open(path);var mapping=new Dictionary<string,string>();
            int roots=0;
            foreach(var item in document.objects){if(string.IsNullOrEmpty(item.id)||mapping.ContainsKey(item.id))throw new FormatException("Invalid or duplicate asset ID");mapping[item.id]=Guid.NewGuid().ToString("N");if(string.IsNullOrEmpty(item.parentId))roots++;}
            if(roots!=1)throw new FormatException("Library assets must contain exactly one root object");
            var stage=new GameObject("Asset staging").transform;var models=new Dictionary<string,GameObject>();GameObject rootObject=null;
            try {
                foreach(var item in document.objects) {
                    string old=item.id;item.id=mapping[old];item.libraryId=Path.GetFileNameWithoutExtension(path);
                    var go=Model(item,stage,31);models[old]=go;
                    if(string.IsNullOrEmpty(item.parentId))rootObject=go;
                }
                foreach(var item in document.objects)if(!string.IsNullOrEmpty(item.parentId)) {
                    if(!models.ContainsKey(item.parentId))throw new FormatException("Asset is missing a parent");
                    var child=models[FindOldId(mapping,item.id)];var parent=models[item.parentId];
                    if(child==parent||parent.transform.IsChildOf(child.transform))throw new FormatException("Cyclic asset parenting");
                    child.transform.SetParent(parent.transform,false);
                }
                if(rootObject==null)throw new FormatException("Asset has no root");
                while(stage.childCount>0)stage.GetChild(0).SetParent(PlacementParent(),false);
                rootObject.transform.position=position;rootObject.transform.Rotate(Vector3.up,placementYaw,Space.Self);selected=rootObject;Changed();Status("Placed editable library asset. Move, Rotate and Scale are available in the catalog.");
            } catch {Clear(stage);throw;}finally{Destroy(stage.gameObject);}
    }
    static string FindOldId(Dictionary<string,string> mapping,string id)
    {
        foreach(var pair in mapping)if(pair.Value==id)return pair.Key;throw new FormatException("Missing asset ID");
    }
}
