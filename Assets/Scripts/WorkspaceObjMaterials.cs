using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

// Materials/texture bridge layered on the geometry importer. Source files are read-only.
public static class WorkspaceObjMaterials
{
    sealed class Definition { public string name, texture; public Color color=Color.white; }
    public static WorkspaceProject Import(string path,out string warning)
    {
        warning="";var mesh=WorldBuilderObj.Load(path);
        try {
            var groups=new List<string>();var triangles=new List<List<int>>();string current="default";
            var libraries=new List<string>();var sourceTriangles=mesh.triangles;int cursor=0;
            foreach(string raw in File.ReadLines(path)) {
                string line=raw.Split('#')[0].Trim();int split=line.IndexOfAny(new[]{' ','\t'});
                if(split<0)continue;string key=line.Substring(0,split),value=line.Substring(split).Trim();
                if(key=="mtllib")libraries.Add(value);
                if(key=="usemtl")current=value;
                if(key=="f") {
                    var corners=value.Split((char[])null,StringSplitOptions.RemoveEmptyEntries);
                    int count=(corners.Length-2)*3;if(count<3)continue;
                    int group=groups.IndexOf(current);if(group<0){group=groups.Count;groups.Add(current);triangles.Add(new List<int>());}
                    for(int i=0;i<count;i++)triangles[group].Add(sourceTriangles[cursor++]);
                }
            }
            var definitions=new Dictionary<string,Definition>();var errors=new List<string>();
            foreach(string library in libraries) {
                string file=System.IO.Path.GetFullPath(System.IO.Path.Combine(System.IO.Path.GetDirectoryName(path),library));
                if(!File.Exists(file)){errors.Add("Missing MTL: "+library);continue;}
                if(new FileInfo(file).Length>4*1024*1024)throw new IOException("MTL exceeds 4 MB limit.");
                Definition currentDefinition=null;
                foreach(string raw in File.ReadLines(file)) {
                    string line=raw.Split('#')[0].Trim();int split=line.IndexOfAny(new[]{' ','\t'});if(split<0)continue;
                    string key=line.Substring(0,split),value=line.Substring(split).Trim();
                    if(key=="newmtl"){currentDefinition=new Definition{name=value};definitions[value]=currentDefinition;}
                    else if(currentDefinition!=null&&key=="Kd") {
                        var parts=value.Split((char[])null,StringSplitOptions.RemoveEmptyEntries);if(parts.Length<3)throw new FormatException("Invalid MTL base color.");
                        float r=float.Parse(parts[0],CultureInfo.InvariantCulture),g=float.Parse(parts[1],CultureInfo.InvariantCulture),b=float.Parse(parts[2],CultureInfo.InvariantCulture);
                        if(float.IsNaN(r)||float.IsNaN(g)||float.IsNaN(b)||float.IsInfinity(r)||float.IsInfinity(g)||float.IsInfinity(b))throw new FormatException("Invalid MTL color.");
                        currentDefinition.color=new Color(Mathf.Clamp01(r),Mathf.Clamp01(g),Mathf.Clamp01(b));
                    } else if(currentDefinition!=null&&(key=="d"||key=="Tr")) {
                        float alpha=float.Parse(value,CultureInfo.InvariantCulture);if(float.IsNaN(alpha)||float.IsInfinity(alpha))throw new FormatException("Invalid MTL opacity");currentDefinition.color.a=Mathf.Clamp01(key=="Tr"?1-alpha:alpha);
                    } else if(currentDefinition!=null&&key=="map_Kd") {
                        if(value.StartsWith("-")){errors.Add("Texture-map options require conversion: "+value);continue;}
                        currentDefinition.texture=System.IO.Path.GetFullPath(System.IO.Path.Combine(System.IO.Path.GetDirectoryName(file),value));
                    }
                }
            }
            var colors=new Color[groups.Count];var sets=new WorkspaceTriangles[groups.Count];var textures=new WorkspaceTexture[groups.Count];
            for(int i=0;i<groups.Count;i++) {
                sets[i]=new WorkspaceTriangles{indices=triangles[i].ToArray()};colors[i]=new Color(0.65f,0.72f,0.78f);
                if(!definitions.TryGetValue(groups[i],out var definition)){if(libraries.Count>0)errors.Add("Missing material: "+groups[i]);continue;}
                colors[i]=definition.color;
                if(!string.IsNullOrEmpty(definition.texture)) {
                    if(!File.Exists(definition.texture)){errors.Add("Missing texture: "+System.IO.Path.GetFileName(definition.texture));continue;}
                    if(new FileInfo(definition.texture).Length>8*1024*1024)throw new IOException("Texture exceeds 8 MB limit.");
                    string ext=System.IO.Path.GetExtension(definition.texture).ToLowerInvariant();
                    if(ext!=".png"&&ext!=".jpg"&&ext!=".jpeg"){errors.Add("Unsupported texture format: "+ext);continue;}
                    textures[i]=new WorkspaceTexture{name=System.IO.Path.GetFileName(definition.texture),sourcePath=definition.texture,base64=Convert.ToBase64String(File.ReadAllBytes(definition.texture))};
                }
            }
            warning=string.Join("; ",errors);
            return new WorkspaceProject{materialNames=groups.ToArray(),name=System.IO.Path.GetFileNameWithoutExtension(path),source=path,id=Guid.NewGuid().ToString("N"),vertices=mesh.vertices,normals=mesh.normals,uv=mesh.uv,triangles=sourceTriangles,submeshes=sets,materialColors=colors,albedo=textures};
        } finally {UnityEngine.Object.Destroy(mesh);}
    }
}
