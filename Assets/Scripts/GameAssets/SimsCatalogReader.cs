using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

// Independently implemented binary readers; format references in docs/SIMS-CATALOG-DECODING.md.
// No scanning for magic tag numbers or name-based category guesses.
public static class SimsCatalogReader
{
    public const uint Catalog=0x319E4F1D, Definition=0xC0DB5AE7;
    [Serializable] public sealed class Metadata {
        public string name,room,category,catalogSource;
        public string[] rooms=new string[0],categories=new string[0],catalogKeys=new string[0];
        public uint[] catalogTags=new uint[0];
    }
    public static uint NameHash(byte[] bytes)
    {
        if(bytes.Length<12)throw new FormatException("Truncated COBJ name reference");
        using(var r=new BinaryReader(new MemoryStream(bytes))){r.ReadUInt32();r.ReadUInt32();return r.ReadUInt32();}
    }
    public static Dictionary<uint,string> Strings(byte[] bytes,HashSet<uint> wanted=null)
    {
        var strings=new Dictionary<uint,string>();
        using(var r=new BinaryReader(new MemoryStream(bytes))) {
            if(r.ReadUInt32()!=0x4C425453||r.ReadUInt16()!=5)throw new NotSupportedException("Unsupported STBL header/version");
            if(r.ReadByte()!=0)throw new NotSupportedException("Internally compressed STBL is unsupported");
            ulong count=r.ReadUInt64();r.ReadUInt16();r.ReadUInt32();
            if(count>1000000||count>(ulong)((bytes.Length-r.BaseStream.Position)/7))throw new FormatException("Invalid STBL entry count");
            var utf8=new System.Text.UTF8Encoding(false,true);
            for(ulong i=0;i<count;i++) {
                uint hash=r.ReadUInt32();r.ReadByte();int length=r.ReadUInt16();
                if(length>r.BaseStream.Length-r.BaseStream.Position)throw new FormatException("Truncated STBL string");
                byte[] text=r.ReadBytes(length);if(wanted!=null&&!wanted.Contains(hash))continue;
                string value=utf8.GetString(text);
                if(strings.TryGetValue(hash,out var previous)&&previous!=value)throw new FormatException("Conflicting STBL string hash");
                strings[hash]=value;
            }
        }return strings;
    }
    public static uint[] Tags(byte[] bytes)
    {
        using(var r=new BinaryReader(new MemoryStream(bytes))) {
            r.ReadUInt32();uint common=r.ReadUInt32();
            if(common<1||common>11)throw new NotSupportedException("Unsupported COBJ common version "+common);
            r.ReadBytes(24);int styles=r.ReadByte();r.ReadBytes(checked(styles*16));
            if(common>=10)r.ReadBytes(12);else if(r.ReadByte()>0)r.ReadByte();
            uint count=r.ReadUInt32();int width=common>=11?4:2;
            if(count>65536||count>(r.BaseStream.Length-r.BaseStream.Position)/width)throw new FormatException("Invalid catalog tag count");
            var tags=new uint[count];for(int i=0;i<tags.Length;i++)tags[i]=width==4?r.ReadUInt32():r.ReadUInt16();return tags;
        }
    }
    public static List<string> Models(byte[] bytes,out string name)
    {
        name=null;var models=new List<string>();
        using(var r=new BinaryReader(new MemoryStream(bytes))) {
            r.ReadUInt16();uint table=r.ReadUInt32();
            if(table<6||table>bytes.Length-2)throw new FormatException("Invalid OBJD property table");
            r.BaseStream.Position=table;int count=r.ReadUInt16();if(count>(bytes.Length-table-2)/8)throw new FormatException("Invalid OBJD property count");
            var properties=new List<(uint id,uint offset)>();for(int i=0;i<count;i++)properties.Add((r.ReadUInt32(),r.ReadUInt32()));
            foreach(var p in properties) {
                if(p.offset<6||p.offset>=table)throw new FormatException("Invalid OBJD property offset");
                r.BaseStream.Position=p.offset;
                if(p.id==0xE7F07786) {int length=r.ReadInt32();if(length<0||length>table-r.BaseStream.Position)throw new FormatException("Invalid OBJD name");name=System.Text.Encoding.ASCII.GetString(r.ReadBytes(length));}
                if(p.id!=0x8D20ACC6)continue;
                int words=r.ReadInt32();if(words<0||words%4!=0||words/4>1024||words*4L>table-r.BaseStream.Position)throw new FormatException("Invalid OBJD model list");
                for(int i=0;i<words/4;i++){ulong raw=r.ReadUInt64();ulong instance=(raw<<32)|(raw>>32);uint type=r.ReadUInt32(),group=r.ReadUInt32();models.Add(Key(type,group,instance));}
            }
        }return models;
    }
    public static string Key(uint type,uint group,ulong instance)=>$"{type:X8}:{group:X8}:{instance:X16}";
    public static Metadata Classify(IEnumerable<uint> tags,string name,IEnumerable<string> keys)
    {
        var values=tags.Distinct().OrderBy(t=>t).ToArray();var rooms=new SortedSet<string>();var types=new SortedSet<string>();
        foreach(uint tag in values) {
            switch(tag){case 270:rooms.Add("Living room");break;case 271:rooms.Add("Bathroom");break;case 272:rooms.Add("Bedroom");break;case 273:rooms.Add("Dining room");break;case 274:rooms.Add("Kitchen");break;case 275:rooms.Add("Outdoors");break;case 276:rooms.Add("Office");break;}
            if(tag>=217&&tag<=224)types.Add("Seating");
            else if(tag>=210&&tag<=216||tag==228)types.Add("Tables");
            else if(tag==225)types.Add("Beds");
            else if(tag==226||tag==227||tag==230)types.Add("Storage");
            else if(tag>=203&&tag<=206||tag==208||tag==310)types.Add("Lighting");
            else if(tag==202||tag==558)types.Add("Plants");
            else if(tag==535||tag==918||tag==974)types.Add("Doors");
            else if(tag==428||tag==536)types.Add("Windows");
            else if(tag>=194&&tag<=201||tag==207||tag==209||tag==446)types.Add("Decor");
            else if(tag>=180&&tag<=184||tag==192)types.Add("Plumbing");
            else if(tag>=185&&tag<=191||tag==193)types.Add("Appliances");
            else if(tag>=161&&tag<=164||tag>=169&&tag<=172||tag==177)types.Add("Electronics");
            else if(tag==165||tag==173||tag==174||tag==175||tag==440||tag==441||tag==456||tag==457)types.Add("Activities");
        }
        return new Metadata{name=name,room=rooms.FirstOrDefault()??"Unclassified",category=types.FirstOrDefault()??"Unclassified",rooms=rooms.ToArray(),categories=types.ToArray(),catalogTags=values,catalogKeys=keys.Distinct().OrderBy(k=>k).ToArray(),catalogSource="Sims COBJ → OBJD → MODL → MLOD"};
    }
}
