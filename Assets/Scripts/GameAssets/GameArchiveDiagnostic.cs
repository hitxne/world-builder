using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

// Metadata-only ZIP central-directory inspection: never inflates an entry, loads a
// multi-GB archive into memory, or attempts decryption/unsupported compression.
public static class GameArchiveDiagnostic
{
    public sealed class Result
    {
        public int Entries, MeshEntries, EncryptedEntries;
        public string Status;
        public readonly Dictionary<string, int> Methods = new Dictionary<string, int>();
        public readonly List<Member> Members = new List<Member>();
        public readonly List<string> MeshNames = new List<string>();
    }
    public sealed class Member
    {
        public string Name;
        public ushort Flags, Method;
        public uint Crc, CompressedSize, Size, LocalOffset;
        public bool Encrypted => (Flags & 65) != 0;
    }
    public static Result Inspect(string path)
    {
        var result = new Result();
        using (var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var reader = new BinaryReader(stream)) {
            if (stream.Length < 4) throw new FormatException("Archive too short.");
            uint signature = reader.ReadUInt32();
            if (signature != 0x04034b50 && signature != 0x06054b50 && signature != 0x02014b50)
                throw new NotSupportedException("Not a standard ZIP header (signature 0x" + signature.ToString("X8") + "). Custom or encrypted container inspection is pending.");
            int tailSize = (int)Math.Min(stream.Length, 65557); stream.Position = stream.Length - tailSize;
            byte[] tail = reader.ReadBytes(tailSize); int end = -1;
            for (int i = tail.Length - 22; i >= 0; i--)
                if (BitConverter.ToUInt32(tail, i) == 0x06054b50 && i + 22 + BitConverter.ToUInt16(tail, i + 20) == tail.Length) { end = i; break; }
            if (end < 0) throw new NotSupportedException("ZIP directory not found; custom or encrypted archive layout is unsupported.");
            int count = BitConverter.ToUInt16(tail, end + 10); uint size = BitConverter.ToUInt32(tail, end + 12), offset = BitConverter.ToUInt32(tail, end + 16);
            if (count == 65535 || size == uint.MaxValue || offset == uint.MaxValue) throw new NotSupportedException("ZIP64 metadata inspection is pending.");
            if (BitConverter.ToUInt16(tail, end + 4) != 0 || BitConverter.ToUInt16(tail, end + 6) != 0) throw new NotSupportedException("Multi-disk ZIP metadata is unsupported.");
            if (offset > stream.Length - size) throw new FormatException("Invalid ZIP directory bounds.");
            stream.Position = offset;
            for (int i = 0; i < count; i++) {
                long start = stream.Position;
                if (start + 46 > (long)offset + size || reader.ReadUInt32() != 0x02014b50) throw new FormatException("Invalid ZIP directory entry.");
                reader.ReadUInt16(); reader.ReadUInt16(); ushort flags = reader.ReadUInt16(), method = reader.ReadUInt16();
                stream.Position = start + 16;
                uint crc = reader.ReadUInt32(), compressedSize = reader.ReadUInt32(), logicalSize = reader.ReadUInt32();
                stream.Position = start + 42; uint localOffset = reader.ReadUInt32();
                stream.Position = start + 28; int nameLength = reader.ReadUInt16(), extra = reader.ReadUInt16(), comment = reader.ReadUInt16();
                long next = start + 46 + nameLength + extra + comment;
                if (next > (long)offset + size) throw new FormatException("ZIP name exceeds directory bounds.");
                stream.Position = start + 46; string name = Encoding.UTF8.GetString(reader.ReadBytes(nameLength));
                result.Members.Add(new Member { Name = name, Flags = flags, Method = method, Crc = crc, CompressedSize = compressedSize, Size = logicalSize, LocalOffset = localOffset });
                result.Entries++; if ((flags & 1) != 0 || (flags & 64) != 0) result.EncryptedEntries++;
                string format = Path.GetExtension(name).ToLowerInvariant();
                if (format == ".modelbin") { result.MeshEntries++; if (result.MeshNames.Count < 12) result.MeshNames.Add(name); }
                string methodName = method == 0 ? "0 stored" : method == 8 ? "8 deflate" : method == 21 ? "21 LZX (decoder pending)" : method + " unsupported";
                result.Methods[methodName] = result.Methods.TryGetValue(methodName, out int total) ? total + 1 : 1;
                stream.Position = next;
            }
            result.Status = "Directory only; resources not opened. Encrypted entries: " + result.EncryptedEntries + ".";
        }
        return result;
    }
}
