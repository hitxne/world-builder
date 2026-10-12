using System;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;

// Content-addressed, append-only payloads. Manifest publication is a separate atomic operation.
public sealed class WorkspaceBlobStore
{
    public readonly string Folder;
    readonly HashSet<string> verified=new HashSet<string>();
    public WorkspaceBlobStore(string folder){Folder=Path.GetFullPath(folder);}
    static void Check(string hash){if(hash==null||hash.Length!=64)throw new FormatException("Invalid asset hash");foreach(char c in hash)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))throw new FormatException("Invalid asset hash");}
    public static string Hash(byte[] bytes){using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
    public string Put(byte[] bytes)
    {
        if(bytes==null||bytes.Length>128*1024*1024)throw new IOException("Asset payload exceeds 128 MB limit");string hash=Hash(bytes);Directory.CreateDirectory(Folder);string path=Path.Combine(Folder,hash+".blob");
        if(File.Exists(path)){if(!verified.Contains(hash))Read(hash);verified.Add(hash);return hash;}
        string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try{using(var stream=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None)){stream.Write(bytes,0,bytes.Length);stream.Flush(true);}File.Move(temp,path);verified.Add(hash);}finally{if(File.Exists(temp))File.Delete(temp);}return hash;
    }
    public void PruneSession(HashSet<string> keep)
    {
        if(!Directory.Exists(Folder))return;foreach(string path in Directory.EnumerateFiles(Folder,"*.blob")){string hash=Path.GetFileNameWithoutExtension(path);if(!keep.Contains(hash)){File.Delete(path);verified.Remove(hash);}}
    }
    public byte[] Read(string hash)
    {
        Check(hash);string path=Path.Combine(Folder,hash+".blob");if(!File.Exists(path))throw new FileNotFoundException("Missing shared asset. Keep the project and its asset folder together.",path);
        if(new FileInfo(path).Length>128*1024*1024)throw new IOException("Shared asset exceeds 128 MB limit");byte[] bytes=File.ReadAllBytes(path);if(Hash(bytes)!=hash)throw new IOException("Shared asset is corrupt: "+hash);return bytes;
    }
}
