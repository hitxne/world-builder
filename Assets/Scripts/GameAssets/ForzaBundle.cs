using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

// Forza Grub bundle wire layout follows the MIT-licensed ForzaTechStudio
// format implementation. Attribution is retained in THIRD_PARTY_NOTICES.md.
// Only plain, bounded bundle resources are read. Archives/decryption are excluded.
public sealed class ForzaBundle
{
    public const uint MeshTag = 0x4d657368, VertexTag = 0x56657242, IndexTag = 0x496e6442, LayoutTag = 0x564c6179;
    public readonly string Path;
    readonly byte[] memory;
    public readonly List<Blob> Blobs = new List<Blob>();
    public sealed class Blob
    {
        public uint Tag, Offset, Size;
        public byte Major, Minor;
        public int Id = -1;
        public string Name = "";
    }
    public ForzaBundle(string path)
    {
        Path = path;
        Parse(File.Open(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite));
    }
    public ForzaBundle(byte[] bytes, string source)
    {
        if (bytes == null || bytes.Length > 64 * 1024 * 1024) throw new IOException("Model entry exceeds 64 MB limit.");
        Path = source; memory = bytes; Parse(new MemoryStream(memory, false));
    }
    void Parse(Stream stream)
    {
        using (var reader = new BinaryReader(stream)) {
            if (stream.Length < 16 || reader.ReadUInt32() != 0x47727562) throw new NotSupportedException("Not a plain Grub bundle. Archives or encrypted files require a separate supported workflow.");
            byte major = reader.ReadByte(), minor = reader.ReadByte(); uint count;
            if (major == 1 && minor <= 1) {
                if (minor == 1) { reader.ReadUInt16(); reader.ReadUInt32(); reader.ReadUInt32(); count = reader.ReadUInt32(); }
                else { count = reader.ReadUInt16(); stream.Position = 16; }
            } else throw new NotSupportedException("Unsupported Grub container version " + major + "." + minor);
            if (count > 100000 || stream.Position + count * 24L > stream.Length) throw new FormatException("Invalid bundle directory.");
            long start = stream.Position;
            for (uint i = 0; i < count; i++) {
                stream.Position = start + i * 24L;
                var blob = new Blob { Tag = reader.ReadUInt32(), Major = reader.ReadByte(), Minor = reader.ReadByte() };
                ushort metas = reader.ReadUInt16(); uint metaOffset = reader.ReadUInt32(); blob.Offset = reader.ReadUInt32();
                uint compressed = reader.ReadUInt32(), uncompressed = reader.ReadUInt32();
                if (compressed != 0 && uncompressed != 0 && compressed != uncompressed) throw new NotSupportedException("Compressed Grub blobs are not yet supported.");
                blob.Size = uncompressed == 0 ? compressed : uncompressed;
                if (blob.Offset > stream.Length - blob.Size || metaOffset > stream.Length - metas * 8L) throw new FormatException("Invalid blob bounds.");
                for (int m = 0; m < metas; m++) {
                    long header = metaOffset + m * 8L; stream.Position = header;
                    uint tag = reader.ReadUInt32(); int size = reader.ReadUInt16() >> 4; int offset = reader.ReadUInt16();
                    if (header + offset > stream.Length - size) throw new FormatException("Invalid metadata bounds.");
                    stream.Position = header + offset;
                    if (tag == 0x49642020 && size >= 4) blob.Id = reader.ReadInt32();
                    else if (tag == 0x4e616d65) blob.Name = Encoding.UTF8.GetString(reader.ReadBytes(size)).TrimEnd('\0');
                }
                Blobs.Add(blob);
            }
        }
    }
    public byte[] Read(Blob blob)
    {
        if (!Blobs.Contains(blob)) throw new ArgumentException("Blob does not belong to bundle.");
        if (blob.Size > 64 * 1024 * 1024) throw new IOException("Blob exceeds 64 MB preview limit.");
        using (var stream = memory == null ? (Stream)File.Open(Path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite) : new MemoryStream(memory, false))
        using (var reader = new BinaryReader(stream)) {
            stream.Position = blob.Offset; byte[] bytes = reader.ReadBytes(checked((int)blob.Size));
            if (bytes.Length != blob.Size) throw new EndOfStreamException("Truncated bundle blob."); return bytes;
        }
    }
    public Blob Resolve(uint tag, int id)
    {
        if (id < 0) throw new FormatException("Negative bundle reference.");
        var byId = Blobs.Find(b => b.Tag == tag && b.Id == id); if (byId != null) return byId;
        if (tag != LayoutTag && id < Blobs.Count && Blobs[id].Tag == tag) return Blobs[id];
        var ofType = Blobs.FindAll(b => b.Tag == tag);
        if (tag == LayoutTag && id < ofType.Count) return ofType[id];
        throw new FormatException("Missing bundle dependency " + tag.ToString("X8") + ":" + id);
    }
}
