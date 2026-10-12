using System;
using System.Collections.Generic;
using System.IO;
using System.Text;


// Limited static MLOD geometry reader. Unknown layouts fail explicitly rather than
// producing guessed geometry. Supported appearance data is preserved separately.
public static class SimsMeshReader
{
    sealed class Chunk { public byte[] Bytes; public uint Type, Group; public ulong Instance; }
    sealed class Rcol { public List<Chunk> Chunks = new List<Chunk>(); public List<Chunk> External = new List<Chunk>(); public int Public; }
    static Rcol Container(byte[] bytes)
    {
        var result = new Rcol();
        using (var stream = new MemoryStream(bytes))
        using (var reader = new BinaryReader(stream)) {
            uint version = reader.ReadUInt32();
            if (version != 3) throw new NotSupportedException("Unsupported RCOL version " + version);
            result.Public = reader.ReadInt32(); reader.ReadUInt32(); int ext = reader.ReadInt32(), count = reader.ReadInt32();
            if (ext < 0 || ext > 4096 || count < 1 || count > 4096 || result.Public < 0 || result.Public > count) throw new FormatException("Invalid RCOL counts.");
            for (int i = 0; i < count + ext; i++) {
                var key = new Chunk { Instance = reader.ReadUInt64(), Type = reader.ReadUInt32(), Group = reader.ReadUInt32() };
                (i < count ? result.Chunks : result.External).Add(key);
            }
            for (int i = 0; i < count; i++) {
                uint offset = reader.ReadUInt32(); int size = reader.ReadInt32();
                if (count == 1) offset = checked((uint)(44 + ext * 16));
                if (size < 4 || offset > bytes.Length - size) throw new FormatException("Invalid RCOL chunk bounds.");
                result.Chunks[i].Bytes = new byte[size]; Buffer.BlockCopy(bytes, (int)offset, result.Chunks[i].Bytes, 0, size);
            }
        }
        return result;
    }
    public static List<string> ModelMlodKeys(byte[] bytes)
    {
        var container=Container(bytes);var result=new List<string>();
        foreach(var chunk in container.Chunks) {
            if(Encoding.ASCII.GetString(chunk.Bytes,0,4)!="MODL")continue;
            using(var r=new BinaryReader(new MemoryStream(chunk.Bytes))) {
                r.ReadUInt32();uint version=r.ReadUInt32();int count=r.ReadInt32();
                if(count<0||count>1024)throw new FormatException("Invalid model LOD count");
                r.ReadBytes(24);
                if(version==258){int extra=r.ReadInt32();if(extra<0||extra>1024)throw new FormatException("Invalid extra bounds count");r.ReadBytes(checked(extra*24+8));}
                else if(version==0x300)r.ReadBytes(20);
                else if(version!=256&&version!=257)throw new NotSupportedException("Unsupported MODL version "+version);
                for(int i=0;i<count;i++) {
                    uint reference=r.ReadUInt32();r.ReadBytes(16);int index=(int)(reference&0x0fffffff)-1;uint kind=reference>>28;
                    if(reference==0)continue;if(kind==1)index+=container.Public;
                    var list=kind==3?container.External:container.Chunks;
                    if((kind!=0&&kind!=1&&kind!=3)||index<0||index>=list.Count)throw new FormatException("Invalid model LOD reference");
                    var key=list[index];if(key.Type==SimsPackage.Mlod)result.Add(SimsCatalogReader.Key(key.Type,key.Group,key.Instance));
                }
            }
        }return result;
    }
    static byte[] Resolve(SimsPackage package, Rcol rcol, uint reference, string tag, Func<uint,uint,ulong,byte[]> externalResource)
    {
        int index = checked((int)(reference & 0x0fffffffu)) - 1, kind = (int)(reference >> 28);
        if (kind == 1) index += rcol.Public;
        Chunk key;
        if (kind == 0 || kind == 1) {
            if (index < 0 || index >= rcol.Chunks.Count) throw new FormatException("Invalid local chunk reference.");
            key = rcol.Chunks[index];
        } else if (kind == 3) {
            if (index < 0 || index >= rcol.External.Count) throw new FormatException("Invalid external reference.");
            key = rcol.External[index];
            var entry = package.Entries.Find(e => e.Type == key.Type && e.Group == key.Group && e.Instance == key.Instance);
            if (entry == null && externalResource == null) throw new NotSupportedException("Mesh dependency is in another package; no resolver was supplied.");
            var external = Container(entry!=null?package.Read(entry):externalResource(key.Type,key.Group,key.Instance));
            key = external.Chunks.Find(c => Encoding.ASCII.GetString(c.Bytes, 0, 4) == tag);
            if (key == null) throw new FormatException("External dependency has no " + tag + " chunk.");
        } else throw new NotSupportedException("Unsupported chunk reference class.");
        if (Encoding.ASCII.GetString(key.Bytes, 0, 4) != tag) throw new FormatException("Expected " + tag + " dependency.");
        return key.Bytes;
    }
    static SimsMaterialReader.Material Material(SimsPackage package,Rcol rcol,uint reference,Func<uint,uint,ulong,byte[]> external,int depth=0)
    {
        if(reference==0)return null;if(depth>8)throw new FormatException("Material reference cycle");
        int index=(int)(reference&0x0fffffff)-1,kind=(int)(reference>>28);if(kind==1)index+=rcol.Public;
        Chunk chunk;
        if(kind==0||kind==1){if(index<0||index>=rcol.Chunks.Count)throw new FormatException("Invalid material reference");chunk=rcol.Chunks[index];}
        else if(kind==3) {
            if(index<0||index>=rcol.External.Count)throw new FormatException("Invalid external material reference");var key=rcol.External[index];
            var entry=package.Entries.Find(e=>e.Type==key.Type&&e.Group==key.Group&&e.Instance==key.Instance);
            if(entry==null&&external==null)throw new NotSupportedException("Missing cross-package material resolver");
            rcol=Container(entry!=null?package.Read(entry):external(key.Type,key.Group,key.Instance));
            chunk=rcol.Chunks.Find(c=>c.Type==key.Type&&c.Group==key.Group&&c.Instance==key.Instance);
            if(chunk==null){var matches=rcol.Chunks.FindAll(c=>Encoding.ASCII.GetString(c.Bytes,0,4)=="MATD"||Encoding.ASCII.GetString(c.Bytes,0,4)=="MTST");if(matches.Count!=1)throw new NotSupportedException("Ambiguous external material chunk");chunk=matches[0];}
        }else throw new NotSupportedException("Unsupported material reference class");
        string tag=Encoding.ASCII.GetString(chunk.Bytes,0,4);
        if(tag=="MTST") {
            if(chunk.Bytes.Length<16)throw new FormatException("Truncated material set");uint version=BitConverter.ToUInt32(chunk.Bytes,4);
            if(version!=0x200&&version!=0x300)throw new NotSupportedException("Unsupported material set version");
            return Material(package,rcol,BitConverter.ToUInt32(chunk.Bytes,12),external,depth+1);
        }
        return SimsMaterialReader.Read(chunk.Bytes);
    }
    public static List<SimsDecodedMesh> Decode(SimsPackage package, SimsPackage.Entry entry, Func<uint,uint,ulong,byte[]> externalResource=null)
    {
        if (entry.Type != SimsPackage.Mlod) throw new NotSupportedException("Only object MLOD geometry is supported.");
        var rcol = Container(package.Read(entry));
        var mlod = rcol.Chunks.Find(c => Encoding.ASCII.GetString(c.Bytes, 0, 4) == "MLOD");
        if (mlod == null) throw new FormatException("Resource contains no MLOD chunk.");
        var models = new List<SimsDecodedMesh>();
        using (var stream = new MemoryStream(mlod.Bytes))
        using (var reader = new BinaryReader(stream)) {
            stream.Position = 4; uint version = reader.ReadUInt32();
            if (version < 0x201 || version > 0x204) throw new NotSupportedException("Unsupported MLOD version 0x" + version.ToString("X"));
            int count = reader.ReadInt32(); if (count < 1 || count > 256) throw new FormatException("Invalid MLOD mesh count.");
            for (int i = 0; i < count; i++) {
                uint size = reader.ReadUInt32(); long start = stream.Position;
                if (size < 72 || size > stream.Length - start) throw new FormatException("Invalid MLOD mesh record.");
                uint name = reader.ReadUInt32(),materialRef=reader.ReadUInt32();
                uint formatRef = reader.ReadUInt32(), verticesRef = reader.ReadUInt32(), indicesRef = reader.ReadUInt32();
                uint primitive = reader.ReadUInt32(); int offset = checked((int)reader.ReadUInt32());
                reader.ReadInt32(); int firstIndex = reader.ReadInt32(); reader.ReadInt32();
                int vertices = reader.ReadInt32(), triangles = reader.ReadInt32();
                if ((primitive & 255) != 3) throw new NotSupportedException("Only triangle-list Sims meshes are supported.");
                if (vertices < 1 || vertices > 1000000 || triangles < 1 || triangles > 1000000 || offset < 0 || firstIndex < 0) throw new FormatException("Invalid mesh geometry count.");
                SimsMaterialReader.Material material=null;string appearanceWarning=null;
                try {material=Material(package,rcol,materialRef,externalResource);appearanceWarning=material?.warning;}catch(Exception error){appearanceWarning=error.Message;}
                var model = Geometry(Resolve(package, rcol, formatRef, "VRTF", externalResource), Resolve(package, rcol, verticesRef, "VBUF", externalResource), Resolve(package, rcol, indicesRef, "IBUF", externalResource), offset, vertices, firstIndex, triangles,material?.uvScale??1f/32767);
                model.material=material;if(!string.IsNullOrEmpty(appearanceWarning))model.appearanceWarning=appearanceWarning;
                model.name = "Sims mesh " + name.ToString("X8"); model.id = entry.Key + ":" + i; model.source = package.Path;
                models.Add(model); stream.Position = start + size;
            }
        }
        return models;
    }
    static float PackedNormal(byte value)=>value==0?-1:((value+1)/128f)-1;
    static float Half(ushort value){int sign=(value&0x8000)!=0?-1:1,exponent=(value>>10)&31,mantissa=value&1023;if(exponent==31)return mantissa==0?sign*float.PositiveInfinity:float.NaN;return sign*(float)(exponent==0?mantissa*Math.Pow(2,-24):(1+mantissa/1024.0)*Math.Pow(2,exponent-15));}
    public static SimsDecodedMesh Geometry(byte[] format, byte[] vertices, byte[] indices, int offset, int count, int firstIndex, int triangles,float uvScale=1f/32767)
    {
        if (format == null || vertices == null || indices == null || format.Length < 24 || vertices.Length < 16 || indices.Length < 16
            || count < 1 || count > 1000000 || triangles < 1 || triangles > 1000000 || offset < 0 || firstIndex < 0)
            throw new FormatException("Invalid Sims geometry buffers/ranges.");
        if (Encoding.ASCII.GetString(format, 0, 4) != "VRTF" || Encoding.ASCII.GetString(vertices, 0, 4) != "VBUF" || Encoding.ASCII.GetString(indices, 0, 4) != "IBUF")
            throw new FormatException("Invalid Sims geometry tags.");
        var model = new SimsDecodedMesh { vertices = new WorldPoint[count], uv = new WorldPoint[count], triangles = new int[checked(triangles * 3)] };
        int stride, posOffset = -1, posFormat = -1,uvOffset=-1,uvFormat=-1,normalOffset=-1,normalFormat=-1;
        using (var stream = new MemoryStream(format))
        using (var reader = new BinaryReader(stream)) {
            stream.Position = 8; stride = reader.ReadInt32(); int elements = reader.ReadInt32(); reader.ReadUInt32();
            if (stride < 1 || stride > 512 || elements < 1 || elements > 64) throw new FormatException("Invalid vertex layout.");
            for (int i = 0; i < elements; i++) {
                byte usage = reader.ReadByte(),usageIndex=reader.ReadByte(); byte encoding = reader.ReadByte(), location = reader.ReadByte();
                if (usage == 0) { posOffset = location; posFormat = encoding; }
                if(usage==2&&usageIndex==0){uvOffset=location;uvFormat=encoding;}
                if(usage==1){normalOffset=location;normalFormat=encoding;}
            }
        }
        int positionBytes = posFormat == 2 ? 12 : posFormat == 3 ? 16 : posFormat == 7 || posFormat == 12 ? 8 : -1;
        if (posOffset < 0 || positionBytes < 0 || posOffset + positionBytes > stride) throw new NotSupportedException("Unsupported Sims position layout.");
        uint vflags = BitConverter.ToUInt32(vertices, 8);
        if ((vflags & ~1u) != 0) throw new NotSupportedException("Differenced/collapsed Sims vertex buffers are not yet supported.");
        if ((long)16 + offset + (long)count * stride > vertices.Length) throw new FormatException("Vertex buffer is truncated.");
        for (int i = 0; i < count; i++) {
            int at = checked(16 + offset + i * stride + posOffset);
            if (posFormat == 2 || posFormat == 3) model.vertices[i] = new WorldPoint(BitConverter.ToSingle(vertices, at), BitConverter.ToSingle(vertices, at + 4), BitConverter.ToSingle(vertices, at + 8));
            else {
                float divisor = BitConverter.ToUInt16(vertices, at + 6); if (divisor == 0) divisor = posFormat == 7 ? 32767 : 511;
                model.vertices[i] = new WorldPoint(BitConverter.ToInt16(vertices, at), BitConverter.ToInt16(vertices, at + 2), BitConverter.ToInt16(vertices, at + 4)) * (1/divisor);
            }
        }
        model.hasUv=uvOffset>=0;model.normals=normalOffset>=0?new WorldPoint[count]:null;
        for(int i=0;i<count;i++) {
            int start=16+offset+i*stride;
            if(uvOffset>=0) {
                int uvBytes=uvFormat==1?8:uvFormat==6||uvFormat==9||uvFormat==11||uvFormat==15?4:-1;
                if(uvBytes<0||uvOffset+uvBytes>stride){model.hasUv=false;model.appearanceWarning="Unsupported UV layout "+uvFormat;}
                else {
                    int p=start+uvOffset;float u,v;
                    if(uvFormat==1){u=BitConverter.ToSingle(vertices,p);v=BitConverter.ToSingle(vertices,p+4);}
                    else if(uvFormat==15){u=Half(BitConverter.ToUInt16(vertices,p));v=Half(BitConverter.ToUInt16(vertices,p+2));}
                    else if(uvFormat==11){u=BitConverter.ToUInt16(vertices,p)/65535f;v=BitConverter.ToUInt16(vertices,p+2)/65535f;}
                    else {float scale=uvFormat==6?uvScale:1f/32767;u=BitConverter.ToInt16(vertices,p)*scale;v=BitConverter.ToInt16(vertices,p+2)*scale;}
                    if(float.IsNaN(u)||float.IsNaN(v)||float.IsInfinity(u)||float.IsInfinity(v))throw new FormatException("Non-finite UV");model.uv[i]=new WorldPoint(u,v,0);
                }
            }
            if(model.normals!=null) {
                int normalBytes=normalFormat==2?12:normalFormat==5?4:-1;
                if(normalBytes<0||normalOffset+normalBytes>stride){model.normals=null;model.appearanceWarning="Unsupported normal layout "+normalFormat;}
                else {int p=start+normalOffset;model.normals[i]=normalFormat==2?new WorldPoint(BitConverter.ToSingle(vertices,p),BitConverter.ToSingle(vertices,p+4),BitConverter.ToSingle(vertices,p+8)):new WorldPoint(PackedNormal(vertices[p+2]),PackedNormal(vertices[p+1]),PackedNormal(vertices[p]));}
            }
        }
        uint flags = BitConverter.ToUInt32(indices, 8);
        if ((flags & ~3u) != 0) throw new NotSupportedException("Sims display-list index buffers are unsupported.");
        int size = (flags & 2) != 0 ? 4 : 2;
        if ((long)16 + ((long)firstIndex + model.triangles.Length) * size > indices.Length) throw new FormatException("Index buffer is truncated.");
        int previous = 0;
        for (int i = 0; i < firstIndex + model.triangles.Length; i++) {
            int at = checked(16 + i * size);
            int value = size == 4 ? BitConverter.ToInt32(indices, at) : (flags & 1) != 0 ? BitConverter.ToInt16(indices, at) : BitConverter.ToUInt16(indices, at);
            if ((flags & 1) != 0) value = checked(value + previous); previous = value;
            if (i >= firstIndex) { if (value < 0 || value >= count) throw new FormatException("Invalid Sims triangle index."); model.triangles[i - firstIndex] = value; }
        }
        return model;
    }
}

public sealed class SimsDecodedMesh
{
    public string name,id,source;
    public WorldPoint[] vertices,uv,normals;
    public bool hasUv;public string appearanceWarning;public SimsMaterialReader.Material material;
    public int[] triangles;
}
