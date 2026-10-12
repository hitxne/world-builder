using System;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    volatile bool libraryImportRunning, cancelLibraryImport;
    [Serializable] sealed class LibraryMetadata { public string name,source,warning; }
    void WriteLibraryMetadata(string path,string name,string source,string warning)
        =>WorkspaceAtomicFile.Write(path+".metadata.json",JsonUtility.ToJson(new LibraryMetadata{name=name,source=source,warning=warning},true));
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
            string path=Path.Combine(LibraryFolder,id+".wbworld");document.Save(path);
            WriteLibraryMetadata(path,document.title,selected.GetComponent<WorkspaceIdentity>().source,"");
            selected.GetComponent<WorkspaceIdentity>().libraryId=id;Changed();Status("Saved reusable asset/building to the local library.");
        });
    }
    void OpenLibrary()
    {
        Dialog("Local Asset Library","Reusable objects and buildings persist between sessions. Select one, then click the terrain or active lot to place an independent editable copy.",box=>{
            Button(box,"Add Sims assets — select game EXE",SelectSimsExecutable);
            Button(box,"Import existing OBJ export folder",OpenSimsExportImport);
            int page=0;var search=new TextField("Search");box.Add(search);var list=new ScrollView();list.style.height=300;box.Add(list);
            void Populate(string query) {
                list.Clear();if(!Directory.Exists(LibraryFolder)){Label(list,"Save a selected object or lot to add your first asset.","hint");return;}
                int count=0,matched=0;
                foreach(string path in Directory.EnumerateFiles(LibraryFolder,"*.wbworld")) {

                    try {
                        string metadataPath=path+".metadata.json";
                        var metadata=File.Exists(metadataPath)?JsonUtility.FromJson<LibraryMetadata>(File.ReadAllText(metadataPath)):null;
                        string name=metadata?.name??WorkspaceDocument.Open(path).title;
                        if(name.IndexOf(query??"",StringComparison.OrdinalIgnoreCase)<0)continue;
                        if(matched++<page*50)continue;if(count++>=50){Label(list,"More results — use Next page.","hint");break;}
                        string assetPath=path;var entry=Button(list,name,()=>BeginLibraryPlacement(assetPath));
                        entry.tooltip=string.IsNullOrEmpty(metadata?.warning)?name:name+"\nImport warning: "+metadata.warning;
                    } catch {Label(list,"Unreadable asset: "+Path.GetFileName(path),"hint");}
                }
            }
            var pages=Row(box);Button(pages,"Previous page",()=>{page=Math.Max(0,page-1);Populate(search.value);});Button(pages,"Next page",()=>{page++;Populate(search.value);});
            search.RegisterValueChangedCallback(e=>{page=0;Populate(e.newValue);});Populate("");Button(box,"Close",CloseDialog);
        });
    }
    void SelectSimsExecutable()
    {
        if(libraryImportRunning){Status("A Sims asset job is already running.");return;}
        Try(()=>{
            string executable=WorkspaceFiles.Pick(false,"Select The Sims 4 executable","exe");if(string.IsNullOrEmpty(executable))return;
            string installation=SimsBatchExporter.InstallationFromExe(executable);
            PlayerPrefs.SetString("worldbuilder.gamePath.1",installation);PlayerPrefs.Save();
            Label progress=null;
            Dialog("Adding Sims assets","World Builder is reading local packages, exporting supported object geometry, then adding it to your library. Unsupported resources are reported; source files are untouched.",box=>{
                progress=Label(box,"Indexing game packages…","hint");
                Button(box,"Cancel",()=>{cancelLibraryImport=true;progress.text="Stopping after the current resource…";});
                Button(box,"Close",()=>{cancelLibraryImport=true;CloseDialog();});
            });
            _ = ExtractAndImportSims(installation,progress);
        });
    }
    async Task ExtractAndImportSims(string installation,Label progress)
    {
        libraryImportRunning=true;cancelLibraryImport=false;
        string output=Path.Combine(Application.persistentDataPath,"SimsExports");
        var messages=new ConcurrentQueue<string>();bool ready=false;
        try {
            var extraction=Task.Run(()=>SimsBatchExporter.Run(installation,output,message=>messages.Enqueue(message),()=>cancelLibraryImport));
            while(!extraction.IsCompleted){if(this==null){cancelLibraryImport=true;break;}while(messages.TryDequeue(out string message))progress.text=message;await Task.Delay(100);}
            int code=await extraction;
            if(this!=null&&!cancelLibraryImport&&code!=130){progress.text="Adding exported objects to the library…";ready=true;}
            else if(this!=null)progress.text="Cancelled. Completed exports remain for the next run.";
        } catch(Exception error){if(this!=null){progress.text="Sims import stopped: "+error.Message;Status(progress.text);}}
        finally {libraryImportRunning=false;}
        if(ready){await ImportSimsExports(output,progress);if(this!=null)Status("Sims asset job finished. Open Local Library; unsupported formats and missing materials remain reported.");}
    }
    void OpenSimsExportImport()
    {
        if(libraryImportRunning){Status("A library import is already running.");return;}
        Dialog("Import Sims Build/Buy exports","Choose a folder of exported OBJ models with their MTL and PNG/JPEG textures. Subfolders are included. This imports local exports; it does not extract game packages.",box=>{
            var folder=new TextField("Export folder"){value=PlayerPrefs.GetString("worldbuilder.simsExportFolder","")};box.Add(folder);
#if UNITY_EDITOR
            Button(box,"Choose export folder",()=>{string chosen=UnityEditor.EditorUtility.OpenFolderPanel("Sims export folder",folder.value,"");if(!string.IsNullOrEmpty(chosen))folder.value=chosen;});
#else
            Button(box,"Choose OBJ inside export folder",()=>{string chosen=WorkspaceFiles.Pick(false,"Choose an OBJ in the export folder","obj");if(!string.IsNullOrEmpty(chosen))folder.value=Path.GetDirectoryName(chosen);});
#endif
            var progress=Label(box,"Ready. Existing library entries are skipped.","hint");
            var start=Button(box,"Import folder",()=>{_ = ImportSimsExports(folder.value,progress);});
            Button(box,"Cancel import",()=>{cancelLibraryImport=true;progress.text="Cancellation requested; completed imports are kept.";});
            Button(box,"Close",()=>{cancelLibraryImport=true;CloseDialog();});
        });
    }
    async Task ImportSimsExports(string folder,Label progress)
    {
        if(libraryImportRunning)return;
        libraryImportRunning=true;cancelLibraryImport=false;
        var report=new StringBuilder();int imported=0,skipped=0,failed=0;
        try {
            folder=Path.GetFullPath(folder);if(!Directory.Exists(folder))throw new DirectoryNotFoundException("Export folder does not exist.");
            PlayerPrefs.SetString("worldbuilder.simsExportFolder",folder);PlayerPrefs.Save();Directory.CreateDirectory(LibraryFolder);
            progress.text="Scanning exported OBJ files…";
            // File discovery only runs in the background; Unity mesh parsing stays on its main thread.
            var files=await Task.Run(()=>Directory.EnumerateFiles(folder,"*.obj",SearchOption.AllDirectories).Take(100001).ToArray());
            if(files.Length>100000)throw new IOException("Export folder exceeds the 100,000-file scan limit; import smaller subfolders.");
            foreach(string file in files) {
                if(cancelLibraryImport||this==null)break;
                try {
                    string id;using(var hash=SHA256.Create())id=BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Path.GetFullPath(file).ToUpperInvariant()))).Replace("-","").ToLowerInvariant();
                    string target=Path.Combine(LibraryFolder,id+".wbworld");
                    if(File.Exists(target)){skipped++;progress.text="Imported "+imported+" • skipped "+skipped+" • failed "+failed+" / "+files.Length;await Task.Yield();continue;}
                    if(new FileInfo(file).Length>32*1024*1024)throw new IOException("OBJ exceeds 32 MB import limit.");
                    var item=WorkspaceObjMaterials.Import(file,out string warning);item.id=Guid.NewGuid().ToString("N");item.libraryId=id;item.parentId=null;item.position=Vector3.zero;
                    string name="The Sims 4 / "+Path.GetRelativePath(folder,file);item.name=Path.GetFileNameWithoutExtension(file);
                    new WorkspaceDocument{title=name,objects=new List<WorkspaceProject>{item}}.Save(target);
                    WriteLibraryMetadata(target,name,file,warning);imported++;
                    if(!string.IsNullOrEmpty(warning))report.AppendLine("WARNING: "+file+" — "+warning);
                } catch(Exception error){failed++;report.AppendLine("FAILED: "+file+" — "+error.Message);}
                progress.text="Imported "+imported+" • skipped "+skipped+" • failed "+failed+" / "+files.Length;
                await Task.Yield();
            }
            if(this!=null){string summary=(cancelLibraryImport?"Cancelled. ":"Finished. ")+"Imported "+imported+", skipped "+skipped+", failed "+failed+".";progress.text=summary;report.Insert(0,summary+Environment.NewLine);WorkspaceAtomicFile.Write(Path.Combine(LibraryFolder,"Sims-import-report.txt"),report.ToString());Status(summary+" Open Local Library and search The Sims 4.");}
        } catch(Exception error){if(this!=null){progress.text="Import stopped: "+error.Message;Status(progress.text);}}
        finally {libraryImportRunning=false;}
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
