using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text;
using UnityEngine;

// Version 2 keeps instance state in JSON and deduplicates immutable mesh/texture/source payloads.
public static class WorkspaceProjectStorage
{
    [Serializable] sealed class Geometry {public Vector3[] vertices,normals;public Vector2[] uv;public int[] triangles;public WorkspaceTriangles[] submeshes;}
    static WorkspaceProject Copy(WorkspaceProject item){var result=new WorkspaceProject();foreach(var field in typeof(WorkspaceProject).GetFields(BindingFlags.Instance|BindingFlags.Public))field.SetValue(result,field.GetValue(item));return result;}
    sealed class TextReferences:IEqualityComparer<string>{public bool Equals(string a,string b)=>ReferenceEquals(a,b);public int GetHashCode(string text)=>RuntimeHelpers.GetHashCode(text);}
    static byte[] Text(string value)=>Encoding.UTF8.GetBytes(value);
    public static WorkspaceDocument Compact(WorkspaceDocument document,WorkspaceBlobStore store,string folder)
    {
        var result=new WorkspaceDocument{version=2,title=document.title,assetFolder=folder};var textures=new Dictionary<string,string>(new TextReferences());
        WorkspaceTexture[] CompactTextures(WorkspaceTexture[] input) {
            if(input==null)return null;var output=new WorkspaceTexture[input.Length];
            for(int i=0;i<input.Length;i++)if(input[i]!=null) {
                var t=input[i];string hash=null;
                if(!string.IsNullOrEmpty(t.base64)){if(!textures.TryGetValue(t.base64,out hash))textures[t.base64]=hash=store.Put(Convert.FromBase64String(t.base64));}
                else if(!string.IsNullOrEmpty(t.blob))hash=t.blob;
                output[i]=new WorkspaceTexture{name=t.name,sourcePath=t.sourcePath,blob=hash};
            }return output;
        }
        foreach(var item in document.objects) {
            var copy=Copy(item);
            if(!item.HasConstruction&&item.vertices!=null)copy.meshRef=store.Put(Text(JsonUtility.ToJson(new Geometry{vertices=item.vertices,normals=item.normals,uv=item.uv,triangles=item.triangles,submeshes=item.submeshes})));
            copy.vertices=null;copy.normals=null;copy.uv=null;copy.triangles=null;copy.submeshes=null;copy.albedo=CompactTextures(item.albedo);
            if(item.sourceAppearance!=null)copy.sourceAppearance=new WorkspaceSourceAppearance{manifestJson=item.sourceAppearance.manifestJson,resources=CompactTextures(item.sourceAppearance.resources)};
            result.objects.Add(copy);
        }return result;
    }
    public static string StoreGeometry(Mesh mesh,WorkspaceBlobStore store)
    {
        var groups=new WorkspaceTriangles[mesh.subMeshCount];for(int i=0;i<groups.Length;i++)groups[i]=new WorkspaceTriangles{indices=mesh.GetTriangles(i)};
        return store.Put(Text(JsonUtility.ToJson(new Geometry{vertices=mesh.vertices,normals=mesh.normals,uv=mesh.uv,triangles=mesh.triangles,submeshes=groups})));
    }
    public static WorkspaceDocument Expand(WorkspaceDocument document,WorkspaceBlobStore store)
    {
        var geometry=new Dictionary<string,Geometry>();var textures=new Dictionary<string,string>();long bytesRead=0;
        byte[] Read(string hash){var bytes=store.Read(hash);bytesRead+=bytes.Length;if(bytesRead>512L*1024*1024)throw new IOException("Unique project assets exceed the 512 MB loading budget");return bytes;}
        void ExpandTextures(WorkspaceTexture[] list){foreach(var texture in list??new WorkspaceTexture[0])if(texture!=null&&!string.IsNullOrEmpty(texture.blob)){if(!textures.TryGetValue(texture.blob,out string value))textures[texture.blob]=value=Convert.ToBase64String(Read(texture.blob));texture.base64=value;}}
        foreach(var item in document.objects) {
            if(item==null)throw new FormatException("Null project object");item.NormalizeConstruction();
            if(!string.IsNullOrEmpty(item.meshRef)) {
                if(!geometry.TryGetValue(item.meshRef,out var data)){data=JsonUtility.FromJson<Geometry>(Encoding.UTF8.GetString(Read(item.meshRef)));if(data==null||data.vertices==null||data.triangles==null)throw new FormatException("Invalid shared geometry");geometry[item.meshRef]=data;}
                item.vertices=data.vertices;item.normals=data.normals;item.uv=data.uv;item.triangles=data.triangles;item.submeshes=data.submeshes;
            } else if(item.HasConstruction&&item.vertices==null) {
                var data=WorldGeometryUnity.Project(item.construction);item.vertices=data.vertices;item.normals=data.normals;item.uv=data.uv;item.triangles=data.triangles;item.submeshes=data.submeshes;
            } else if(item.vertices==null)throw new FormatException("Project object has no geometry/source reference");
            ExpandTextures(item.albedo);if(item.sourceAppearance!=null)ExpandTextures(item.sourceAppearance.resources);
        }
        document.version=1;return document;
    }
    public static HashSet<string> References(IEnumerable<string> snapshots)
    {
        var result=new HashSet<string>();
        void TextureRefs(WorkspaceTexture[] list){foreach(var texture in list??new WorkspaceTexture[0])if(!string.IsNullOrEmpty(texture?.blob))result.Add(texture.blob);}
        foreach(string snapshot in snapshots){var document=JsonUtility.FromJson<WorkspaceDocument>(snapshot);foreach(var item in document.objects){if(!string.IsNullOrEmpty(item.meshRef))result.Add(item.meshRef);TextureRefs(item.albedo);if(item.sourceAppearance!=null)TextureRefs(item.sourceAppearance.resources);}}
        return result;
    }
    public static string Serialize(WorkspaceDocument document,WorkspaceBlobStore store,string folder)=>JsonUtility.ToJson(Compact(document,store,folder),false);
    public static WorkspaceDocument Read(string text,WorkspaceBlobStore store)=>Expand(JsonUtility.FromJson<WorkspaceDocument>(text),store);
}
