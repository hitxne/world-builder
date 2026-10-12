using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    const int SimsAppearanceVersion=2;
    [Serializable] sealed class SimsAppearanceManifest {public int version;public string source;public SimsAppearanceMaterial[] materials;}
    [Serializable] sealed class SimsAppearanceMaterial {public string name,rawMaterial,warning;public uint shader;public SimsAppearanceMap[] maps;}
    [Serializable] sealed class SimsAppearanceMap {public string key,rawTexture,converted,error;public uint semantic;}
    readonly Dictionary<string,WorkspaceProject> simsAppearanceCache=new Dictionary<string,WorkspaceProject>();
    async Task UpgradeSavedSimsLibrary()
    {
        await Task.Yield();if(this==null||libraryImportRunning||PlayerPrefs.GetInt("worldbuilder.simsAppearanceVersion",0)>=SimsAppearanceVersion)return;
        string installation=PlayerPrefs.GetString("worldbuilder.gamePath.1","");
        if(!Directory.Exists(Path.Combine(installation,"Data","Client")))return;
        var progress=new Label();Status("Updating existing Sims assets: names, categories and appearance…");
        bool success=await ExtractAndImportSims(installation,progress);
        if(this!=null&&success&&!cancelLibraryImport){PlayerPrefs.SetInt("worldbuilder.simsAppearanceVersion",SimsAppearanceVersion);PlayerPrefs.Save();RefreshWorldTools();}
    }
    static string SimsAppearanceFingerprint(string file)
    {
        string manifest=file+".appearance.json";if(!File.Exists(manifest))return null;
        using(var hash=SHA256.Create())return BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(manifest))).Replace("-","");
    }
    static WorkspaceSourceAppearance ReadSimsAppearance(string file)
    {
        string sidecar=file+".appearance.json";if(!File.Exists(sidecar))return null;
        if(new FileInfo(sidecar).Length>4*1024*1024)throw new IOException("Appearance manifest exceeds 4 MB limit");
        string json=File.ReadAllText(sidecar);var manifest=JsonUtility.FromJson<SimsAppearanceManifest>(json);
        if(manifest==null||manifest.version!=SimsAppearanceVersion||manifest.materials==null)throw new FormatException("Unsupported appearance manifest");
        string folder=file+".appearance";var names=new HashSet<string>();var resources=new List<WorkspaceTexture>();long total=0;
        if(!string.IsNullOrEmpty(manifest.source))names.Add(manifest.source);
        foreach(var material in manifest.materials) {
            if(!string.IsNullOrEmpty(material.rawMaterial))names.Add(material.rawMaterial);
            foreach(var map in material.maps??new SimsAppearanceMap[0]){if(!string.IsNullOrEmpty(map.rawTexture))names.Add(map.rawTexture);if(!string.IsNullOrEmpty(map.converted))names.Add(map.converted);}
        }
        foreach(string name in names) {
            if(name!=Path.GetFileName(name))throw new FormatException("Invalid appearance resource path");
            string path=Path.Combine(folder,name);long length=new FileInfo(path).Length;total+=length;
            if(length>16*1024*1024||total>48*1024*1024)throw new IOException("Source appearance exceeds import storage limit");
            resources.Add(new WorkspaceTexture{name=name,sourcePath=path,base64=Convert.ToBase64String(File.ReadAllBytes(path))});
        }
        return new WorkspaceSourceAppearance{manifestJson=json,resources=resources.ToArray()};
    }
    static void AttachSimsAppearance(WorkspaceProject item,string file)
    {
        item.sourceAppearance=ReadSimsAppearance(file);item.appearanceFingerprint=SimsAppearanceFingerprint(file);
    }
    static string AppearanceWarning(WorkspaceProject item,string warning)
    {
        if(item.sourceAppearance==null)return warning;
        var manifest=JsonUtility.FromJson<SimsAppearanceManifest>(item.sourceAppearance.manifestJson);var errors=new List<string>();if(!string.IsNullOrEmpty(warning))errors.Add(warning);
        if(item.albedo==null||!item.albedo.Any(t=>t!=null))errors.Add("No supported diffuse texture was bound; source appearance is preserved.");
        foreach(var material in manifest.materials??new SimsAppearanceMaterial[0]){if(!string.IsNullOrEmpty(material.warning))errors.Add(material.warning);foreach(var map in material.maps??new SimsAppearanceMap[0])if(!string.IsNullOrEmpty(map.error))errors.Add(map.key+": "+map.error); }
        return string.Join("; ",errors.Distinct());
    }
    bool UpgradeSimsAppearance(string target,string file)
    {
        string fingerprint=SimsAppearanceFingerprint(file);if(fingerprint==null)return false;
        var document=WorkspaceDocument.Open(target);if(document.objects.Count!=1)return false;
        var old=document.objects[0];if(old.appearanceFingerprint==fingerprint)return false;
        var item=WorkspaceObjMaterials.Import(file,out string warning);AttachSimsAppearance(item,file);warning=AppearanceWarning(item,warning);
        item.id=old.id;item.libraryId=old.libraryId;item.parentId=old.parentId;item.position=old.position;item.rotation=old.rotation;item.scale=old.scale;item.name=old.name;
        document.objects[0]=item;document.Save(target);simsAppearanceCache[Path.GetFileNameWithoutExtension(target)]=item;
        var metadata=ReadAssetMetadata(target);if(metadata!=null){metadata.warning=warning;WorkspaceAtomicFile.Write(target+".metadata.json",JsonUtility.ToJson(metadata,true));}
        if(File.Exists(target+".preview.png"))File.Delete(target+".preview.png");return true;
    }
    static void CopySimsAppearance(WorkspaceProject target,WorkspaceProject source)
    {
        target.vertices=source.vertices;target.normals=source.normals;target.uv=source.uv;target.triangles=source.triangles;target.submeshes=source.submeshes;
        target.materialColors=source.materialColors;target.materialNames=source.materialNames;target.albedo=source.albedo;target.metallic=source.metallic;target.smoothness=source.smoothness;
        target.sourceAppearance=source.sourceAppearance;target.appearanceFingerprint=source.appearanceFingerprint;
    }
    void SyncSimsLibraryAppearance(WorkspaceProject item)
    {
        if(string.IsNullOrEmpty(item.libraryId)||Path.GetFileName(item.libraryId)!=item.libraryId)return;
        if(!simsAppearanceCache.TryGetValue(item.libraryId,out var latest)) {
            string path=Path.Combine(LibraryFolder,item.libraryId+".wbworld");if(!File.Exists(path))return;
            var document=WorkspaceDocument.Open(path);latest=document.objects.Count==1&&document.objects[0].sourceAppearance!=null?document.objects[0]:null;
            simsAppearanceCache[item.libraryId]=latest;
        }
        if(latest!=null&&latest.appearanceFingerprint!=item.appearanceFingerprint) {
            CopySimsAppearance(item,latest);
            if(item.name==Path.GetFileNameWithoutExtension(item.source)){var metadata=ReadAssetMetadata(Path.Combine(LibraryFolder,item.libraryId+".wbworld"));if(!string.IsNullOrEmpty(metadata?.name))item.name=metadata.name;}
        }
    }
    void RefreshPlacedSimsAppearance()
    {
        bool changed=false;
        foreach(var identity in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            if(string.IsNullOrEmpty(identity.libraryId)||!simsAppearanceCache.TryGetValue(identity.libraryId,out var latest)||latest==null||identity.appearanceFingerprint==latest.appearanceFingerprint)continue;
            var data=WorkspaceProject.Capture(identity.gameObject,identity.source);CopySimsAppearance(data,latest);data.libraryId=null;
            var stage=new GameObject("Sims appearance upgrade staging").transform;
            try {
                var replacement=Model(data,stage,identity.gameObject.layer);var next=replacement.GetComponent<WorkspaceIdentity>();
                var oldMesh=identity.ownedMesh;var oldMaterials=identity.ownedMaterials;var oldTextures=identity.ownedTextures;
                identity.GetComponent<MeshFilter>().sharedMesh=next.ownedMesh;identity.GetComponent<MeshRenderer>().sharedMaterials=next.ownedMaterials;
                var collider=identity.GetComponent<MeshCollider>();if(collider!=null)collider.sharedMesh=next.ownedMesh;
                identity.ownedMesh=next.ownedMesh;identity.ownedMaterials=next.ownedMaterials;identity.ownedMaterial=next.ownedMaterial;identity.ownedTextures=next.ownedTextures;
                if(identity.name==Path.GetFileNameWithoutExtension(identity.source)){var metadata=ReadAssetMetadata(Path.Combine(LibraryFolder,identity.libraryId+".wbworld"));if(!string.IsNullOrEmpty(metadata?.name))identity.name=metadata.name;}
                identity.albedo=next.albedo;identity.sourceAppearance=next.sourceAppearance;identity.appearanceFingerprint=next.appearanceFingerprint;
                next.ownedMesh=null;next.ownedMaterials=null;next.ownedMaterial=null;next.ownedTextures=null;
                if(oldMesh!=null)Destroy(oldMesh);foreach(var material in oldMaterials??new Material[0])if(material!=null)Destroy(material);foreach(var texture in oldTextures??new Texture2D[0])if(texture!=null)Destroy(texture);changed=true;
            }finally {stage.gameObject.SetActive(false);Destroy(stage.gameObject);}
        }
        if(changed)Changed();
    }
}
