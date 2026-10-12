using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;


// Read-only local exporter. No Unity/game process, package edits or decryption.
public static class SimsBatchExporter
{

    static string Quote(string value)
    {
        var text=new StringBuilder("\"");
        foreach(char c in value??"") {
            if(c=='"'||c=='\\')text.Append('\\').Append(c);
            else if(c<32)text.Append("\\u").Append(((int)c).ToString("x4"));else text.Append(c);
        }
        return text.Append('"').ToString();
    }
    static string Encode(object value)
    {
        if(value==null)return "null";if(value is string)return Quote((string)value);if(value is bool)return (bool)value?"true":"false";
        if(value is System.Collections.IEnumerable sequence){var items=new List<string>();foreach(var item in sequence)items.Add(Encode(item));return "["+string.Join(",",items)+"]";}
        if(value.GetType().IsPrimitive||value is decimal)return Convert.ToString(value,CultureInfo.InvariantCulture);
        return Json(value);
    }
    static string Json(object row)
    {
        var properties=new List<string>();
        foreach(var property in row.GetType().GetProperties()) {
            var value=property.GetValue(row);string encoded=Encode(value);
            properties.Add(Quote(property.Name)+":"+encoded);
        }
        foreach(var field in row.GetType().GetFields())properties.Add(Quote(field.Name)+":"+Encode(field.GetValue(row)));
        return "{"+string.Join(",",properties)+"}";
    }
    public static string InstallationFromExe(string executable)
    {
        executable=Path.GetFullPath(executable);
        if(!File.Exists(executable))throw new FileNotFoundException("Sims executable not found",executable);
        string name=Path.GetFileName(executable);
        if(!name.Equals("TS4_x64.exe",StringComparison.OrdinalIgnoreCase)&&!name.Equals("TS4_DX9_x64.exe",StringComparison.OrdinalIgnoreCase)&&!name.Equals("TS4.exe",StringComparison.OrdinalIgnoreCase))throw new ArgumentException("Select the Sims 4 executable (TS4_x64.exe or TS4_DX9_x64.exe).");
        var directory=new DirectoryInfo(Path.GetDirectoryName(executable));
        for(int i=0;i<8&&directory!=null;i++,directory=directory.Parent)
            if(Directory.Exists(Path.Combine(directory.FullName,"Data","Client")))return directory.FullName;
        throw new DirectoryNotFoundException("The Sims 4 Data/Client folder was not found above this executable.");
    }
    static string Key(uint type,uint group,ulong instance)=>$"{type:X8}:{group:X8}:{instance:X16}";
    static string Number(float value){if(float.IsNaN(value)||float.IsInfinity(value))throw new FormatException("Non-finite vertex");return value.ToString("R",CultureInfo.InvariantCulture);}
    static void WriteObj(string path,List<SimsDecodedMesh> meshes,string materialFile=null)
    {
        string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {
            using(var writer=new StreamWriter(temp,false,new UTF8Encoding(false))) {
                writer.WriteLine("# Sims MLOD appearance export v2; unsupported appearance is reported.");if(materialFile!=null)writer.WriteLine("mtllib "+materialFile);int offset=1,uvOffset=1,normalOffset=1,part=0;
                foreach(var mesh in meshes) {
                    writer.WriteLine("o "+mesh.id.Replace(':','_'));writer.WriteLine("usemtl sims_part_"+part++);
                    foreach(var v in mesh.vertices)writer.WriteLine("v "+Number(v.x)+" "+Number(v.y)+" "+Number(v.z));
                    if(mesh.hasUv)foreach(var uv in mesh.uv)writer.WriteLine("vt "+Number(uv.x)+" "+Number(1-uv.y));
                    if(mesh.normals!=null)foreach(var n in mesh.normals)writer.WriteLine("vn "+Number(n.x)+" "+Number(n.y)+" "+Number(n.z));
                    string Corner(int index)=>Number(offset+index)+(mesh.hasUv||mesh.normals!=null?"/"+(mesh.hasUv?(uvOffset+index).ToString(CultureInfo.InvariantCulture):"")+(mesh.normals!=null?"/"+(normalOffset+index).ToString(CultureInfo.InvariantCulture):""):"");
                    for(int i=0;i<mesh.triangles.Length;i+=3)writer.WriteLine("f "+Corner(mesh.triangles[i])+" "+Corner(mesh.triangles[i+1])+" "+Corner(mesh.triangles[i+2]));
                    if(mesh.hasUv)uvOffset+=mesh.vertices.Length;if(mesh.normals!=null)normalOffset+=mesh.vertices.Length;
                    offset+=mesh.vertices.Length;
                }
            }
            if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);
        } finally {if(File.Exists(temp))File.Delete(temp);}
    }
    static void Atomic(string path,byte[] bytes)
    {
        string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {File.WriteAllBytes(temp,bytes);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}finally{if(File.Exists(temp))File.Delete(temp);}
    }
    static string Hash(byte[] bytes){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
    static bool Upgraded(string file){using(var r=new StreamReader(file))return r.ReadLine()=="# Sims MLOD appearance export v2; unsupported appearance is reported.";}
    static bool WriteAppearance(string file,List<SimsDecodedMesh> meshes,Func<uint,uint,ulong,byte[]> resolve,byte[] source,Action<object> log)
    {
        string folder=file+".appearance";Directory.CreateDirectory(folder);Atomic(Path.Combine(folder,"source.mlod.bin"),source);
        var materialRows=new List<object>();var mtl=new StringBuilder("# Supported Sims diffuse appearance; original shader data retained in sidecar\n");bool textured=false;
        for(int i=0;i<meshes.Count;i++) {
            var mesh=meshes[i];var material=mesh.material;string name="sims_part_"+i;
            mtl.Append("newmtl ").Append(name).Append("\nKd ").Append(material==null?"0.65 0.72 0.78":string.Join(" ",material.color.Select(Number))).Append("\nd 1\n");
            if(!string.IsNullOrEmpty(mesh.appearanceWarning))log(new{status="appearance-unresolved",output=file,part=i,error=mesh.appearanceWarning});
            if(material==null){materialRows.Add(new{name,shader=0u,rawMaterial=(string)null,maps=new object[0]});continue;}
            string rawMaterial="material_"+i+".bin";Atomic(Path.Combine(folder,rawMaterial),material.original);var maps=new List<object>();
            foreach(var map in material.maps) {
                string rawTexture=map.Key.Replace(':','_')+".bin",converted=null,error=null,sha256=null;
                try {
                    byte[] bytes=resolve(map.type,map.group,map.instance);sha256=Hash(bytes);Atomic(Path.Combine(folder,rawTexture),bytes);
                    try {converted=map.Key.Replace(':','_')+".png";Atomic(Path.Combine(folder,converted),SimsTextureReader.Png(bytes));}
                    catch(Exception conversion){converted=null;error=conversion.Message;}
                    if(map.semantic==0x6CC0FD85&&converted!=null&&mesh.hasUv){mtl.Append("map_Kd ").Append(Path.GetFileName(folder)).Append('/').Append(converted).Append('\n');textured=true;}
                }catch(Exception missing){rawTexture=null;error=missing.Message;}
                if(error!=null)log(new{status="texture-unresolved",output=file,part=i,key=map.Key,error});
                maps.Add(new{semantic=map.semantic,key=map.Key,rawTexture,converted,error,sha256});
            }
            materialRows.Add(new{name,material.shader,color=material.color,uvScale=material.uvScale,rawMaterial,maps,warning=material.warning});
        }
        Atomic(Path.ChangeExtension(file,".mtl"),Encoding.UTF8.GetBytes(mtl.ToString()));
        string manifest=Json(new{version=2,materials=materialRows,source="source.mlod.bin",sourceHash=Hash(source),limitations="Default material state and UV0 diffuse approximation; original shader records/maps retained"});
        Atomic(file+".appearance.json",Encoding.UTF8.GetBytes(manifest));return textured;
    }
    public static int Run(string input,string output,Action<string> progress=null,Func<bool> isCancelled=null)
    {
        bool Cancelled()=>isCancelled?.Invoke()??false;
        input=Path.GetFullPath(input).TrimEnd(Path.DirectorySeparatorChar);output=Path.GetFullPath(output).TrimEnd(Path.DirectorySeparatorChar);
        if(!Directory.Exists(input))throw new DirectoryNotFoundException(input);
        if(output.Equals(input,StringComparison.OrdinalIgnoreCase)||output.StartsWith(input+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Output must be outside the source/game folder.");
        Directory.CreateDirectory(output);
        string reportPath=Path.Combine(output,"report-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N")+".jsonl");
        using(var report=new StreamWriter(reportPath,false,new UTF8Encoding(false))){
            void Log(object row){report.WriteLine(Json(row));report.Flush();}
            var packages=new List<SimsPackage>();var resources=new Dictionary<string,List<(SimsPackage package,SimsPackage.Entry entry)>>();
            int packageFailures=0;
            foreach(string path in Directory.EnumerateFiles(input,"*.package",SearchOption.AllDirectories).OrderBy(p=>p,StringComparer.OrdinalIgnoreCase)) {
                if(Cancelled())break;
                try {
                    var package=new SimsPackage(path);packages.Add(package);
                    foreach(var entry in package.Entries) {
                        if(entry.IsDeleted||entry.IsEmpty||!string.IsNullOrEmpty(entry.PayloadError))continue;
                        if(!resources.TryGetValue(entry.Key,out var matches))resources[entry.Key]=matches=new List<(SimsPackage,SimsPackage.Entry)>();matches.Add((package,entry));
                    }
                }catch(Exception error){packageFailures++;Log(new{status="package-error",source=path,error=error.Message});}
            }
            var canonical=new Dictionary<string,(SimsPackage package,SimsPackage.Entry entry)>();
            (SimsPackage package,SimsPackage.Entry entry) Canonical(string key) {
                if(canonical.TryGetValue(key,out var known))return known;
                if(!resources.TryGetValue(key,out var matches)||matches.Count==0)throw new NotSupportedException("Missing dependency "+key);
                if(matches.Count>1) {
                    string expected=Hash(matches[0].package.Read(matches[0].entry));
                    foreach(var duplicate in matches.Skip(1))if(Hash(duplicate.package.Read(duplicate.entry))!=expected)throw new NotSupportedException("Conflicting dependency "+key+"; patch precedence not validated");
                }
                return canonical[key]=matches[0];
            }
            byte[] Unique(string key){var match=Canonical(key);return match.package.Read(match.entry);}
            byte[] Resolve(uint type,uint group,ulong instance)=>Unique(Key(type,group,instance));
            var wantedNames=new HashSet<uint>();
            foreach(var catalog in resources.Values.Where(v=>v[0].entry.Type==SimsCatalogReader.Catalog)) {
                if(Cancelled())break;
                try {wantedNames.Add(SimsCatalogReader.NameHash(Unique(catalog[0].entry.Key)));}catch(Exception){/* Catalog pass reports invalid records. */}
            }
            var displayNames=new Dictionary<uint,string>();var conflictingNames=new HashSet<uint>();
            progress?.Invoke("Reading Sims object display names…");
            foreach(var tables in resources.Values.Where(v=>v[0].entry.Type==0x220557DA&&(v[0].entry.Instance>>56)==0)) {
                if(Cancelled())break;
                foreach(var table in tables)try {
                    foreach(var pair in SimsCatalogReader.Strings(table.package.Read(table.entry),wantedNames)) {
                        if(displayNames.TryGetValue(pair.Key,out string previous)&&previous!=pair.Value)conflictingNames.Add(pair.Key);else displayNames[pair.Key]=pair.Value;
                    }
                }catch(Exception error){Log(new{status="names-unresolved",key=table.entry.Key,error=error.Message});}
            }
            foreach(uint hash in conflictingNames){displayNames.Remove(hash);Log(new{status="name-conflict",hash});}
            var definitions=new Dictionary<ulong,List<(SimsPackage package,SimsPackage.Entry entry)>>();
            foreach(var candidates in resources.Values.Where(v=>v[0].entry.Type==SimsCatalogReader.Definition))try {
                var definition=Canonical(candidates[0].entry.Key);if(!definitions.TryGetValue(definition.entry.Instance,out var list))definitions[definition.entry.Instance]=list=new List<(SimsPackage,SimsPackage.Entry)>();list.Add(definition);
            }catch(Exception error){Log(new{status="catalog-unlinked",key=candidates[0].entry.Key,error=error.Message});}
            var catalogTags=new Dictionary<string,List<uint>>();var catalogKeys=new Dictionary<string,List<string>>();var catalogNames=new Dictionary<string,string>();
            var modelCache=new Dictionary<string,List<string>>();int linked=0,catalogFailures=0;
            progress?.Invoke("Decoding Sims catalog categories…");
            foreach(var candidates in resources.Values.Where(v=>v[0].entry.Type==SimsCatalogReader.Catalog)) {
                if(Cancelled())break;
                try {
                    var c=Canonical(candidates[0].entry.Key);byte[] catalogBytes=c.package.Read(c.entry);var tags=SimsCatalogReader.Tags(catalogBytes);uint nameHash=SimsCatalogReader.NameHash(catalogBytes);
                    if(!definitions.TryGetValue(c.entry.Instance,out var defs)||defs.Count!=1)throw new NotSupportedException("Missing or ambiguous object definition");
                    var d=defs[0];var models=SimsCatalogReader.Models(d.package.Read(d.entry),out string name);
                    if(displayNames.TryGetValue(nameHash,out string displayName)&&!string.IsNullOrWhiteSpace(displayName))name=displayName;
                    else Log(new{status="name-unresolved",key=c.entry.Key,nameHash,fallback="OBJD internal name"});
                    foreach(string model in models) {
                        if(!modelCache.TryGetValue(model,out var meshes))modelCache[model]=meshes=SimsMeshReader.ModelMlodKeys(Unique(model));
                        foreach(string mesh in meshes) {
                            Canonical(mesh);
                            if(!catalogTags.ContainsKey(mesh)){catalogTags[mesh]=new List<uint>();catalogKeys[mesh]=new List<string>();}
                            catalogTags[mesh].AddRange(tags);catalogKeys[mesh].Add(c.entry.Key);
                            if(!string.IsNullOrWhiteSpace(name)&&(!catalogNames.ContainsKey(mesh)||string.CompareOrdinal(name,catalogNames[mesh])<0))catalogNames[mesh]=name;
                        }
                    }
                    linked++;
                }catch(Exception error){catalogFailures++;Log(new{status="catalog-unlinked",key=candidates[0].entry.Key,error=error.Message});}
            }
            Log(new{status="catalog-summary",linked,catalogFailures});
            void WriteCatalog(string file,string meshKey) {
                if(!catalogTags.TryGetValue(meshKey,out var tags))return;
                catalogNames.TryGetValue(meshKey,out string name);var data=SimsCatalogReader.Classify(tags,name,catalogKeys[meshKey]);
                string sidecar=file+".catalog.json",temp=sidecar+"."+Guid.NewGuid().ToString("N")+".tmp";
                try {File.WriteAllText(temp,Json(new{data.name,data.room,data.category,data.rooms,data.categories,data.catalogTags,data.catalogKeys,data.catalogSource}),new UTF8Encoding(false));if(File.Exists(sidecar))File.Replace(temp,sidecar,null);else File.Move(temp,sidecar);}
                finally {if(File.Exists(temp))File.Delete(temp);}
            }
            int exported=0,skipped=0,failed=packageFailures;
            foreach(var package in packages) {
                string relative=Path.GetRelativePath(input,package.Path);string packageId;
                using(var sha=SHA256.Create())packageId=BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(relative.ToUpperInvariant()))).Replace("-","").Substring(0,24);
                string destination=Path.Combine(output,packageId);Directory.CreateDirectory(destination);
                foreach(var entry in package.Entries.Where(e=>e.Type==SimsPackage.Mlod)) {
                    if(Cancelled())break;
                    string file=Path.Combine(destination,entry.Key.Replace(':','_')+".obj");
                    if(entry.IsDeleted||entry.IsEmpty){skipped++;Log(new{status="empty-or-deleted",source=relative,key=entry.Key});continue;}
                    if(File.Exists(file)&&Upgraded(file)){WriteCatalog(file,entry.Key);skipped++;Log(new{status="existing-output",source=relative,key=entry.Key,output=file});continue;}
                    try {
                        var meshes=SimsMeshReader.Decode(package,entry,Resolve);bool textured=WriteAppearance(file,meshes,Resolve,package.Read(entry),Log);WriteObj(file,meshes,Path.GetFileName(Path.ChangeExtension(file,".mtl")));WriteCatalog(file,entry.Key);exported++;
                        Log(new{status=textured?"appearance-supported":"geometry-only",source=relative,key=entry.Key,output=file,parts=meshes.Count,vertices=meshes.Sum(m=>m.vertices.Length),triangles=meshes.Sum(m=>m.triangles.Length/3),textures=textured,uvs=meshes.All(m=>m.hasUv),catalogLinked=catalogTags.ContainsKey(entry.Key)});
                    }catch(Exception error){failed++;Log(new{status="unsupported-or-invalid",source=relative,key=entry.Key,error=error.Message});}
                }
                progress?.Invoke($"Exported {exported}, skipped {skipped}, unsupported/failed {failed} — {relative}");if(Cancelled())break;
            }
            Log(new{status="summary",cancelled=Cancelled(),packages=packages.Count,exported,skipped,failed,coverage="Supported object MLOD geometry; not a complete Build/Buy catalog export"});
            progress?.Invoke($"Report: {reportPath}");return Cancelled()?130:failed>0?1:0;
        }
    }
}
