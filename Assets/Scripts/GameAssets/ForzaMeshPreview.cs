using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

// Per-part, neutral-material preview: this is not assembled car/world rendering.
// Bone poses, damage morphs, materials and textures need separate adapters.
public static class ForzaMeshPreview
{
    sealed class Usage { public int Id, Slot, Stride, Offset; }
    sealed class Element { public int Semantic, SemanticIndex, Slot, Format, Offset; }
    public static WorkspaceProject Decode(ForzaBundle bundle, ForzaBundle.Blob mesh)
    {
        if (mesh.Tag != ForzaBundle.MeshTag || mesh.Major != 1 || mesh.Minor < 8 || mesh.Minor > 10)
            throw new NotSupportedException("Supported mesh blob versions: 1.8–1.10 only.");
        byte[] data = bundle.Read(mesh);
        int indexBuffer, indexOffset, drawOffset, vertexOffset, indexCount, layout;
        bool wide; Vector3 scale, translate;
        var usages = new List<Usage>();
        using (var stream = new MemoryStream(data))
        using (var reader = new BinaryReader(stream)) {
            reader.ReadBytes(mesh.Minor >= 9 ? 8 : 2); reader.ReadInt16(); reader.ReadUInt16();
            reader.ReadByte(); reader.ReadByte(); reader.ReadUInt16(); reader.ReadByte();
            byte skin = reader.ReadByte(); if (mesh.Minor >= 10) reader.ReadUInt32(); else reader.ReadByte();
            reader.ReadBoolean(); wide = reader.ReadBoolean(); ushort topology = reader.ReadUInt16();
            if (skin != 0) throw new NotSupportedException("Skinned mesh preview is pending.");
            if (topology != 4) throw new NotSupportedException("Only triangle-list Forza meshes are supported.");
            indexBuffer = reader.ReadInt32(); indexOffset = reader.ReadInt32(); drawOffset = reader.ReadInt32(); vertexOffset = reader.ReadInt32();
            indexCount = reader.ReadInt32(); reader.ReadInt32(); reader.ReadSingle(); reader.ReadUInt32();
            layout = reader.ReadInt32(); int count = reader.ReadInt32();
            if (count < 1 || count > 16) throw new FormatException("Invalid vertex buffer count.");
            for (int i = 0; i < count; i++) usages.Add(new Usage { Id = reader.ReadInt32(), Slot = reader.ReadInt32(), Stride = reader.ReadInt32(), Offset = reader.ReadInt32() });
            reader.ReadInt32(); reader.ReadInt32(); int constantBuffers = reader.ReadInt32();
            if (constantBuffers < 0 || constantBuffers > 256) throw new FormatException("Invalid constant-buffer count.");
            for (int i = 0; i < constantBuffers; i++) reader.ReadInt32();
            reader.ReadUInt32();
            if (reader.ReadBytes(80).Length != 80) throw new EndOfStreamException("Missing UV-transform table.");
            scale = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle()); reader.ReadSingle();
            translate = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle()); reader.ReadSingle();
            if (scale == Vector3.zero) throw new NotSupportedException("Zero mesh quantization scale needs validated handling.");
        }
        if (indexCount < 3 || indexCount > 3000000 || indexCount % 3 != 0 || indexOffset < 0 || drawOffset < 0 || vertexOffset < 0)
            throw new FormatException("Invalid mesh index range.");
        var layoutBlob = bundle.Resolve(ForzaBundle.LayoutTag, layout);
        var names = new List<string>(); var elements = new List<Element>();
        using (var stream = new MemoryStream(bundle.Read(layoutBlob)))
        using (var reader = new BinaryReader(stream)) {
            int namesCount = reader.ReadUInt16(); if (namesCount > 64) throw new FormatException("Invalid semantic count.");
            for (int i = 0; i < namesCount; i++) {
                int length = reader.ReadInt32(); if (length < 0 || length > 256 || length > stream.Length - stream.Position) throw new FormatException("Invalid semantic name.");
                names.Add(Encoding.UTF8.GetString(reader.ReadBytes(length)).TrimEnd('\0'));
            }
            int count = reader.ReadUInt16(); if (count > 64) throw new FormatException("Invalid layout element count.");
            for (int i = 0; i < count; i++) {
                var e = new Element { Semantic = reader.ReadInt16(), SemanticIndex = reader.ReadInt16(), Slot = reader.ReadInt16() };
                int classification = reader.ReadInt16(); e.Format = reader.ReadInt32(); e.Offset = reader.ReadInt32(); int rate = reader.ReadInt32();
                if (e.Semantic < 0 || e.Semantic >= names.Count || classification != 0 || rate != 0) throw new NotSupportedException("Instanced/unknown layout is unsupported.");
                elements.Add(e);
            }
            if (layoutBlob.Major >= 1) for (int i = 0; i < count; i++) {
                int packed = reader.ReadInt32();
                if (packed != 0 && packed != elements[i].Format) throw new NotSupportedException("Packed Forza layout needs a dedicated decoder.");
            }
        }
        var position = elements.Find(e => names[e.Semantic] == "POSITION" && e.SemanticIndex == 0);
        if (position == null || (position.Format != 6 && position.Format != 2 && position.Format != 13)) throw new NotSupportedException("Preview supports float3/float4 and SNORM16x4 positions only.");
        var usage = usages.Find(u => u.Slot == position.Slot);
        int positionBytes = position.Format == 13 ? 8 : position.Format == 2 ? 16 : 12;
        if (usage == null || usage.Stride < positionBytes || usage.Stride > 1024 || usage.Offset < 0 || position.Offset < 0 || position.Offset + positionBytes > usage.Stride)
            throw new NotSupportedException("Unsupported vertex stream layout.");
        var iblob = bundle.Resolve(ForzaBundle.IndexTag, indexBuffer); var vblob = bundle.Resolve(ForzaBundle.VertexTag, usage.Id);
        byte[] ib = Buffer(bundle.Read(iblob), iblob.Major), vb = Buffer(bundle.Read(vblob), vblob.Major);
        int indexSize = wide ? 4 : 2, min = int.MaxValue, max = -1;
        long indexStart = (long)indexOffset + (long)drawOffset * indexSize;
        if (indexStart + (long)indexCount * indexSize > ib.Length) throw new FormatException("Index range exceeds buffer.");
        int[] indices = new int[indexCount];
        for (int i = 0; i < indexCount; i++) {
            int at = checked((int)(indexStart + i * indexSize)); int value = wide ? BitConverter.ToInt32(ib, at) : BitConverter.ToUInt16(ib, at);
            if (value < 0) throw new FormatException("Invalid vertex index."); indices[i] = value; min = Math.Min(min, value); max = Math.Max(max, value);
        }
        int vertexCount = checked(max - min + 1); if (vertexCount > 1000000) throw new IOException("Mesh exceeds preview vertex limit.");
        var model = new WorkspaceProject { name = string.IsNullOrEmpty(mesh.Name) ? "Forza mesh" : mesh.Name,
            source = bundle.Path, id = "forza:" + mesh.Offset, vertices = new Vector3[vertexCount], triangles = indices };
        for (int i = 0; i < vertexCount; i++) {
            long at = usage.Offset + ((long)min + i + vertexOffset) * usage.Stride + position.Offset;
            if (at < 0 || at + positionBytes > vb.Length) throw new FormatException("Vertex range exceeds buffer.");
            Vector3 raw;
            if (position.Format == 13) raw = new Vector3(Math.Max(-1f, BitConverter.ToInt16(vb, (int)at) / 32767f), Math.Max(-1f, BitConverter.ToInt16(vb, (int)at + 2) / 32767f), Math.Max(-1f, BitConverter.ToInt16(vb, (int)at + 4) / 32767f));
            else raw = new Vector3(BitConverter.ToSingle(vb, (int)at), BitConverter.ToSingle(vb, (int)at + 4), BitConverter.ToSingle(vb, (int)at + 8));
            model.vertices[i] = Vector3.Scale(raw, scale) + translate;
        }
        for (int i = 0; i < indices.Length; i++) indices[i] -= min;
        return model;
    }
    static byte[] Buffer(byte[] blob, byte major)
    {
        int header = major >= 1 ? 16 : 12;
        if (blob.Length < header) throw new FormatException("Truncated buffer header.");
        int count = BitConverter.ToInt32(blob, 0), size = BitConverter.ToInt32(blob, 4), stride = BitConverter.ToUInt16(blob, 8);
        if (size == 0) size = checked(count * stride);
        if (count < 0 || size < 0 || size > blob.Length - header) throw new FormatException("Invalid buffer payload size.");
        var bytes = new byte[size]; System.Buffer.BlockCopy(blob, header, bytes, 0, size); return bytes;
    }
}
