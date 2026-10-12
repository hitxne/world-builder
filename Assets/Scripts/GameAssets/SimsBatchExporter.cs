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
        return Convert.ToString(value,CultureInfo.InvariantCulture);
    }
    static string Json(object row)
    {
        var properties=new List<string>();
        foreach(var property in row.GetType().GetProperties()) {
            var value=property.GetValue(row);string encoded=Encode(value);
            properties.Add(Quote(property.Name)+":"+encoded);
        }
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
    static void WriteObj(string path,List<SimsDecodedMesh> meshes)
    {
        string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {
            using(var writer=new StreamWriter(temp,false,new UTF8Encoding(false))) {
                writer.WriteLine("# Sims object MLOD geometry only: UVs, materials and textures are not decoded.");int offset=1;
                foreach(var mesh in meshes) {
                    writer.WriteLine("o "+mesh.id.Replace(':','_'));
                    foreach(var v in mesh.vertices)writer.WriteLine("v "+Number(v.x)+" "+Number(v.y)+" "+Number(v.z));
                    for(int i=0;i<mesh.triangles.Length;i+=3)writer.WriteLine($"f {offset+mesh.triangles[i]} {offset+mesh.triangles[i+1]} {offset+mesh.triangles[i+2]}");
                    offset+=mesh.vertices.Length;
                }
            }
            File.Move(temp,path);
        } finally {if(File.Exists(temp))File.Delete(temp);}
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
            byte[] Resolve(uint type,uint group,ulong instance){
                string key=Key(type,group,instance);
                if(!resources.TryGetValue(key,out var matches))throw new NotSupportedException("Missing cross-package dependency "+key);
                if(matches.Count!=1)throw new NotSupportedException("Ambiguous cross-package dependency "+key+"; patch precedence not yet validated");
                return matches[0].package.Read(matches[0].entry);
            }
            byte[] Unique(string key) {
                if(!resources.TryGetValue(key,out var matches)||matches.Count!=1)throw new NotSupportedException("Missing or ambiguous catalog dependency "+key);
                return matches[0].package.Read(matches[0].entry);
            }
            var wantedNames=new HashSet<uint>();
            foreach(var catalog in resources.Values.Where(v=>v[0].entry.Type==SimsCatalogReader.Catalog)) {
                if(Cancelled())break;
                if(catalog.Count==1)try {wantedNames.Add(SimsCatalogReader.NameHash(catalog[0].package.Read(catalog[0].entry)));}catch(Exception){/* Catalog pass reports invalid records. */}
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
            var definitions=resources.Values.Where(v=>v.Count==1&&v[0].entry.Type==SimsCatalogReader.Definition).Select(v=>v[0]).GroupBy(v=>v.entry.Instance).ToDictionary(g=>g.Key,g=>g.ToList());
            var catalogTags=new Dictionary<string,List<uint>>();var catalogKeys=new Dictionary<string,List<string>>();var catalogNames=new Dictionary<string,string>();
            var modelCache=new Dictionary<string,List<string>>();int linked=0,catalogFailures=0;
            progress?.Invoke("Decoding Sims catalog categories…");
            foreach(var candidates in resources.Values.Where(v=>v[0].entry.Type==SimsCatalogReader.Catalog)) {
                if(Cancelled())break;
                try {
                    if(candidates.Count!=1)throw new NotSupportedException("Ambiguous catalog resource; patch precedence not validated");
                    var c=candidates[0];byte[] catalogBytes=c.package.Read(c.entry);var tags=SimsCatalogReader.Tags(catalogBytes);uint nameHash=SimsCatalogReader.NameHash(catalogBytes);
                    if(!definitions.TryGetValue(c.entry.Instance,out var defs)||defs.Count!=1)throw new NotSupportedException("Missing or ambiguous object definition");
                    var d=defs[0];var models=SimsCatalogReader.Models(d.package.Read(d.entry),out string name);
                    if(displayNames.TryGetValue(nameHash,out string displayName)&&!string.IsNullOrWhiteSpace(displayName))name=displayName;
                    else Log(new{status="name-unresolved",key=c.entry.Key,nameHash,fallback="OBJD internal name"});
                    foreach(string model in models) {
                        if(!modelCache.TryGetValue(model,out var meshes))modelCache[model]=meshes=SimsMeshReader.ModelMlodKeys(Unique(model));
                        foreach(string mesh in meshes) {
                            if(!resources.TryGetValue(mesh,out var meshMatches)||meshMatches.Count!=1)throw new NotSupportedException("Missing or ambiguous mesh for catalog association "+mesh);
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
                    if(File.Exists(file)){WriteCatalog(file,entry.Key);skipped++;Log(new{status="existing-output",source=relative,key=entry.Key,output=file});continue;}
                    try {
                        var meshes=SimsMeshReader.Decode(package,entry,Resolve);WriteObj(file,meshes);WriteCatalog(file,entry.Key);exported++;
                        Log(new{status="geometry-only",source=relative,key=entry.Key,output=file,parts=meshes.Count,vertices=meshes.Sum(m=>m.vertices.Length),triangles=meshes.Sum(m=>m.triangles.Length/3),textures=false,uvs=false,catalogLinked=catalogTags.ContainsKey(entry.Key)});
                    }catch(Exception error){failed++;Log(new{status="unsupported-or-invalid",source=relative,key=entry.Key,error=error.Message});}
                }
                progress?.Invoke($"Exported {exported}, skipped {skipped}, unsupported/failed {failed} — {relative}");if(Cancelled())break;
            }
            Log(new{status="summary",cancelled=Cancelled(),packages=packages.Count,exported,skipped,failed,coverage="Supported object MLOD geometry; not a complete Build/Buy catalog export"});
            progress?.Invoke($"Report: {reportPath}");return Cancelled()?130:failed>0?1:0;
        }
    }
}
