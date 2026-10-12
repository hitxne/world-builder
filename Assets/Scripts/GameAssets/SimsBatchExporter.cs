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
    static string Json(object row)
    {
        var properties=new List<string>();
        foreach(var property in row.GetType().GetProperties()) {
            var value=property.GetValue(row);string encoded=value==null?"null":value is string?Quote((string)value):value is bool?((bool)value?"true":"false"):Convert.ToString(value,CultureInfo.InvariantCulture);
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
            int exported=0,skipped=0,failed=packageFailures;
            foreach(var package in packages) {
                string relative=Path.GetRelativePath(input,package.Path);string packageId;
                using(var sha=SHA256.Create())packageId=BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(relative.ToUpperInvariant()))).Replace("-","").Substring(0,24);
                string destination=Path.Combine(output,packageId);Directory.CreateDirectory(destination);
                foreach(var entry in package.Entries.Where(e=>e.Type==SimsPackage.Mlod)) {
                    if(Cancelled())break;
                    string file=Path.Combine(destination,entry.Key.Replace(':','_')+".obj");
                    if(entry.IsDeleted||entry.IsEmpty){skipped++;Log(new{status="empty-or-deleted",source=relative,key=entry.Key});continue;}
                    if(File.Exists(file)){skipped++;Log(new{status="existing-output",source=relative,key=entry.Key,output=file});continue;}
                    try {
                        var meshes=SimsMeshReader.Decode(package,entry,Resolve);WriteObj(file,meshes);exported++;
                        Log(new{status="geometry-only",source=relative,key=entry.Key,output=file,parts=meshes.Count,vertices=meshes.Sum(m=>m.vertices.Length),triangles=meshes.Sum(m=>m.triangles.Length/3),textures=false,uvs=false,catalogLinked=false});
                    }catch(Exception error){failed++;Log(new{status="unsupported-or-invalid",source=relative,key=entry.Key,error=error.Message});}
                }
                progress?.Invoke($"Exported {exported}, skipped {skipped}, unsupported/failed {failed} — {relative}");if(Cancelled())break;
            }
            Log(new{status="summary",cancelled=Cancelled(),packages=packages.Count,exported,skipped,failed,coverage="Supported object MLOD geometry; not a complete Build/Buy catalog export"});
            progress?.Invoke($"Report: {reportPath}");return Cancelled()?130:failed>0?1:0;
        }
    }
}
