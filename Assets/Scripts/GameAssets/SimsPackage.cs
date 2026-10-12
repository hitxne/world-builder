using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;

// Read-only implementation of the documented Sims 4 DBPF 2.1 container.
// No resource writes, executable hooks or decryption.
public sealed class SimsPackage
{
    public const uint Mlod = 0x01D10F34;
    public readonly string Path;
    public readonly List<Entry> Entries = new List<Entry>();
    public sealed class Entry
    {
        public uint Type, Group, Offset, StoredSize, Size;
        public ulong Instance;
        public ushort Compression;
        public string Key => Type.ToString("X8") + ":" + Group.ToString("X8") + ":" + Instance.ToString("X16");
    }
    public SimsPackage(string path)
    {
        Path = path;
        using (var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var reader = new BinaryReader(stream)) {
            if (stream.Length < 96 || Encoding.ASCII.GetString(reader.ReadBytes(4)) != "DBPF") throw new FormatException("Not a DBPF package.");
            if (reader.ReadUInt32() != 2 || reader.ReadUInt32() != 1) throw new NotSupportedException("Only DBPF 2.1 is supported.");
            stream.Position = 36; uint count = reader.ReadUInt32(), shortOffset = reader.ReadUInt32(), indexSize = reader.ReadUInt32();
            stream.Position = 64; ulong longOffset = reader.ReadUInt64();
            long offset = shortOffset == 0 ? checked((long)longOffset) : shortOffset;
            if (count > 1000000 || offset < 96 || indexSize < 4 || offset > stream.Length - indexSize) throw new FormatException("Invalid package index bounds.");
            stream.Position = offset;
            uint flags = reader.ReadUInt32(); if ((flags & ~7u) != 0) throw new NotSupportedException("Unknown DBPF index flags.");
            uint type = (flags & 1) != 0 ? reader.ReadUInt32() : 0;
            uint group = (flags & 2) != 0 ? reader.ReadUInt32() : 0;
            uint upper = (flags & 4) != 0 ? reader.ReadUInt32() : 0;
            for (uint i = 0; i < count; i++) {
                var entry = new Entry { Type = (flags & 1) != 0 ? type : reader.ReadUInt32(), Group = (flags & 2) != 0 ? group : reader.ReadUInt32() };
                uint high = (flags & 4) != 0 ? upper : reader.ReadUInt32(); entry.Instance = ((ulong)high << 32) | reader.ReadUInt32();
                entry.Offset = reader.ReadUInt32(); uint stored = reader.ReadUInt32(); entry.StoredSize = stored & 0x7fffffffu;
                entry.Size = reader.ReadUInt32();
                if ((stored & 0x80000000u) != 0) { entry.Compression = reader.ReadUInt16(); reader.ReadUInt16(); }
                if (stream.Position > offset + indexSize) throw new FormatException("Package entry exceeds index.");
                if (entry.Compression != 0xffe0 && (entry.Offset < 96 || entry.Offset > stream.Length - entry.StoredSize)) throw new FormatException("Resource lies outside package.");
                Entries.Add(entry);
            }
        }
    }
    public byte[] Read(Entry entry)
    {
        if (!Entries.Contains(entry)) throw new ArgumentException("Resource does not belong to this package.");
        if (entry.Size > 64 * 1024 * 1024 || entry.StoredSize > 64 * 1024 * 1024) throw new IOException("Resource exceeds 64 MB preview limit.");
        if (entry.Compression != 0 && entry.Compression != 0x5a42) throw new NotSupportedException("Resource compression 0x" + entry.Compression.ToString("X4") + " is not implemented.");
        byte[] bytes;
        using (var stream = File.Open(Path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var reader = new BinaryReader(stream)) { stream.Position = entry.Offset; bytes = reader.ReadBytes(checked((int)entry.StoredSize)); }
        if (bytes.Length != entry.StoredSize) throw new EndOfStreamException("Package changed or is truncated.");
        if (entry.Compression == 0) { if (bytes.Length != entry.Size) throw new FormatException("Resource size mismatch."); return bytes; }
        // Unity's .NET profile supplies raw DEFLATE; validate the zlib wrapper explicitly.
        if (bytes.Length < 6 || (bytes[0] & 15) != 8 || (bytes[0] >> 4) > 7 || ((bytes[0] << 8) + bytes[1]) % 31 != 0 || (bytes[1] & 32) != 0)
            throw new FormatException("Invalid or dictionary-based zlib resource.");
        var output = new byte[checked((int)entry.Size)];
        using (var input = new MemoryStream(bytes, 2, bytes.Length - 6))
        using (var inflate = new DeflateStream(input, CompressionMode.Decompress)) {
            int read = 0;
            while (read < output.Length) { int n = inflate.Read(output, read, output.Length - read); if (n == 0) throw new FormatException("Truncated compressed resource."); read += n; }
            if (inflate.ReadByte() != -1) throw new FormatException("Resource expands beyond declared size.");
        }
        uint a = 1, b = 0; foreach (byte value in output) { a = (a + value) % 65521; b = (b + a) % 65521; }
        int end = bytes.Length - 4; uint checksum = ((uint)bytes[end] << 24) | ((uint)bytes[end + 1] << 16) | ((uint)bytes[end + 2] << 8) | bytes[end + 3];
        if (checksum != (b << 16 | a)) throw new FormatException("Resource zlib checksum mismatch.");
        return output;
    }
}
