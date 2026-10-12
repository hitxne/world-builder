using System;
using System.IO;
using System.IO.Compression;
using System.Text;

static class ContainerTests
{
    static byte[] Bytes(Action<BinaryWriter> action){using(var stream=new MemoryStream()){using(var writer=new BinaryWriter(stream,Encoding.UTF8,true))action(writer);return stream.ToArray();}}
    public static void Run()
    {
        string folder=Path.Combine(Path.GetTempPath(),Guid.NewGuid().ToString());Directory.CreateDirectory(folder);
        try {
            byte[] expected=Encoding.UTF8.GetBytes("Original World Builder test resource");byte[] compressed;
            using(var stream=new MemoryStream()){using(var zlib=new ZLibStream(stream,CompressionLevel.Optimal,true))zlib.Write(expected,0,expected.Length);compressed=stream.ToArray();}
            string packagePath=Path.Combine(folder,"test.package");
            File.WriteAllBytes(packagePath,Bytes(w=>{
                w.Write(Encoding.ASCII.GetBytes("DBPF"));w.Write(2u);w.Write(1u);w.Write(new byte[24]);w.Write(1u);w.Write(0u);w.Write(36u);w.Write(new byte[16]);w.Write((ulong)(96+compressed.Length));w.Write(new byte[24]);w.Write(compressed);
                w.Write(0u);w.Write(SimsPackage.Mlod);w.Write(0u);w.Write(0u);w.Write(1u);w.Write(96u);w.Write(0x80000000u|(uint)compressed.Length);w.Write((uint)expected.Length);w.Write((ushort)0x5a42);w.Write((ushort)1);
            }));
            var package=new SimsPackage(packagePath);Assert(Convert.ToBase64String(expected)==Convert.ToBase64String(package.Read(package.Entries[0])),"zlib resource roundtrip");
            byte[] broken=File.ReadAllBytes(packagePath);Array.Copy(BitConverter.GetBytes(1u),0,broken,broken.Length-16,4);File.WriteAllBytes(packagePath,broken);
            var indexed=new SimsPackage(packagePath);Assert(indexed.Entries.Count==1&&indexed.Entries[0].PayloadError.Contains("offset=1"),"invalid payload isolated from valid index");
            bool rejected=false;try{indexed.Read(indexed.Entries[0]);}catch(FormatException){rejected=true;}Assert(rejected,"invalid payload read rejected");
            string zipPath=Path.Combine(folder,"test.zip");
            using(var stream=File.Create(zipPath))using(var zip=new ZipArchive(stream,ZipArchiveMode.Create)) {
                var member=zip.CreateEntry("scene/original.modelbin");using(var output=member.Open())output.Write(expected,0,expected.Length);
            }
            var archive=GameArchiveDiagnostic.Inspect(zipPath);Assert(archive.MeshEntries==1,"mesh name directory scan");
            Assert(Convert.ToBase64String(expected)==Convert.ToBase64String(GameArchiveRead.Read(zipPath,archive.Members[0])),"bounded ZIP read/CRC");
            archive.Members[0].Crc^=1;rejected=false;try{GameArchiveRead.Read(zipPath,archive.Members[0]);}catch(FormatException){rejected=true;}Assert(rejected,"bad CRC rejected");
            archive.Members[0].Flags|=1;rejected=false;try{GameArchiveRead.Read(zipPath,archive.Members[0]);}catch(NotSupportedException){rejected=true;}Assert(rejected,"encrypted entry rejected");
            Console.WriteLine("PASS: container tests (zlib, payload bounds isolation, ZIP directory/member/CRC/encryption).");
        } finally {Directory.Delete(folder,true);}
    }
    static void Assert(bool result,string name){if(!result)throw new Exception(name);}
}
