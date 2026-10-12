using System;
using System.IO;
using System.IO.Compression;

// Bounded, read-only access to ordinary stored/deflated ZIP entries. Reads only
// the selected model into memory; never extracts an installation directory.
public static class GameArchiveRead
{
    public static byte[] Read(string path, GameArchiveDiagnostic.Member member)
    {
        if (member.Encrypted) throw new NotSupportedException("Encrypted archive entries are not supported.");
        if (member.Method != 0 && member.Method != 8) throw new NotSupportedException("ZIP method " + member.Method + " is not supported; no decryption/conversion is attempted.");
        if (member.CompressedSize > 64 * 1024 * 1024 || member.Size > 64 * 1024 * 1024) throw new IOException("Selected model exceeds 64 MB limit.");
        byte[] compressed;
        using (var stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var reader = new BinaryReader(stream)) {
            if (member.LocalOffset > stream.Length - 30) throw new FormatException("Invalid local ZIP entry offset.");
            stream.Position = member.LocalOffset;
            if (reader.ReadUInt32() != 0x04034b50) throw new FormatException("Missing local ZIP header.");
            reader.ReadUInt16(); ushort flags = reader.ReadUInt16(), method = reader.ReadUInt16();
            if ((flags & 65) != 0 || method != member.Method) throw new NotSupportedException("Encrypted or inconsistent local ZIP header.");
            stream.Position = member.LocalOffset + 26L; int name = reader.ReadUInt16(), extra = reader.ReadUInt16();
            long offset = member.LocalOffset + 30L + name + extra;
            if (offset > stream.Length - member.CompressedSize) throw new FormatException("ZIP data range exceeds archive.");
            stream.Position = offset; compressed = reader.ReadBytes(checked((int)member.CompressedSize));
            if (compressed.Length != member.CompressedSize) throw new EndOfStreamException("Truncated archive member.");
        }
        byte[] result;
        if (member.Method == 0) {
            if (compressed.Length != member.Size) throw new FormatException("Stored ZIP size mismatch."); result = compressed;
        } else {
            result = new byte[checked((int)member.Size)];
            using (var stream = new MemoryStream(compressed))
            using (var inflate = new DeflateStream(stream, CompressionMode.Decompress)) {
                int done = 0;
                while (done < result.Length) { int n = inflate.Read(result, done, result.Length - done); if (n == 0) throw new FormatException("Truncated deflated model."); done += n; }
                if (inflate.ReadByte() != -1) throw new FormatException("ZIP entry expands beyond declared size.");
            }
        }
        uint crc = uint.MaxValue;
        foreach (byte value in result) {
            crc ^= value;
            for (int i = 0; i < 8; i++) crc = (crc >> 1) ^ ((crc & 1) != 0 ? 0xedb88320u : 0u);
        }
        if (~crc != member.Crc) throw new FormatException("ZIP CRC mismatch; no preview created.");
        return result;
    }
}
