using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

// Independent reader for documented MATD shader-data tables. Original bytes remain exportable.
public static class SimsMaterialReader
{
    public sealed class Map { public uint semantic,type,group;public ulong instance;public string Key=>SimsCatalogReader.Key(type,group,instance); }
    public sealed class Material {
        public byte[] original;public string warning;public uint shader;public float[] color={1,1,1};public float uvScale=1f/32767;
        public List<Map> maps=new List<Map>();
    }
    public static Material Read(byte[] bytes)
    {
        try {return Supported(bytes);}catch(Exception error){return new Material{original=bytes,warning=error.Message};}
    }
    static Material Supported(byte[] bytes)
    {
        var result=new Material{original=bytes};
        using(var r=new BinaryReader(new MemoryStream(bytes))) {
            if(r.ReadUInt32()!=0x4454414D)throw new FormatException("Expected MATD");
            uint version=r.ReadUInt32();if(version<0x100||version>0x103)throw new NotSupportedException("Unsupported MATD version");
            r.ReadUInt32();result.shader=r.ReadUInt32();uint length=r.ReadUInt32();if(version>=0x103)r.ReadBytes(8);
            long start=r.BaseStream.Position;if(length>bytes.Length-start)throw new FormatException("Invalid material length");
            string tag=Encoding.ASCII.GetString(r.ReadBytes(4));if(tag!="MTNF"&&tag!="MTRL")throw new NotSupportedException("Unsupported shader-data block");
            r.ReadUInt32();r.ReadUInt32();int count=r.ReadInt32();long dataStart=r.BaseStream.Position+count*16L;
            if(count<0||count>4096||dataStart>start+length)throw new FormatException("Invalid material parameter count");
            var headers=new List<(uint semantic,uint type,int count,uint offset)>();
            for(int i=0;i<count;i++)headers.Add((r.ReadUInt32(),r.ReadUInt32(),r.ReadInt32(),r.ReadUInt32()));
            foreach(var h in headers) {
                long at=start+h.offset;if(h.count<0||h.count>4096||at<dataStart||at+h.count*4L>start+length)throw new FormatException("Invalid shader parameter bounds");
                r.BaseStream.Position=at;
                if(h.type==1&&h.semantic==0x637DAA05&&h.count>=3)result.color=new[]{r.ReadSingle(),r.ReadSingle(),r.ReadSingle()};
                else if(h.type==1&&h.semantic==0x420520E9&&h.count>=3)result.uvScale=r.ReadSingle();
                else if(h.type==4&&(h.count==4||h.count==5)){ulong instance=r.ReadUInt64();uint type=r.ReadUInt32(),group=r.ReadUInt32();result.maps.Add(new Map{semantic=h.semantic,type=type,group=group,instance=instance});}
            }
        }
        foreach(float c in result.color)if(float.IsNaN(c)||float.IsInfinity(c))throw new FormatException("Invalid material color");
        if(float.IsNaN(result.uvScale)||float.IsInfinity(result.uvScale))throw new FormatException("Invalid UV scale");
        return result;
    }
}
