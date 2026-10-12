using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

// Limited static MLOD geometry reader. Unknown layouts fail explicitly rather than
// producing guessed geometry. Textures/material assembly are not implemented.
public static class SimsMeshPreview
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
    static byte[] Resolve(SimsPackage package, Rcol rcol, uint reference, string tag)
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
            if (entry == null) throw new NotSupportedException("Mesh dependency is in another package; cross-package resolution is pending.");
            var external = Container(package.Read(entry));
            key = external.Chunks.Find(c => Encoding.ASCII.GetString(c.Bytes, 0, 4) == tag);
            if (key == null) throw new FormatException("External dependency has no " + tag + " chunk.");
        } else throw new NotSupportedException("Unsupported chunk reference class.");
        if (Encoding.ASCII.GetString(key.Bytes, 0, 4) != tag) throw new FormatException("Expected " + tag + " dependency.");
        return key.Bytes;
    }
    public static List<WorkspaceProject> Decode(SimsPackage package, SimsPackage.Entry entry)
    {
        if (entry.Type != SimsPackage.Mlod) throw new NotSupportedException("Only object MLOD geometry is supported.");
        var rcol = Container(package.Read(entry));
        var mlod = rcol.Chunks.Find(c => Encoding.ASCII.GetString(c.Bytes, 0, 4) == "MLOD");
        if (mlod == null) throw new FormatException("Resource contains no MLOD chunk.");
        var models = new List<WorkspaceProject>();
        using (var stream = new MemoryStream(mlod.Bytes))
        using (var reader = new BinaryReader(stream)) {
            stream.Position = 4; uint version = reader.ReadUInt32();
            if (version < 0x201 || version > 0x204) throw new NotSupportedException("Unsupported MLOD version 0x" + version.ToString("X"));
            int count = reader.ReadInt32(); if (count < 1 || count > 256) throw new FormatException("Invalid MLOD mesh count.");
            for (int i = 0; i < count; i++) {
                uint size = reader.ReadUInt32(); long start = stream.Position;
                if (size < 72 || size > stream.Length - start) throw new FormatException("Invalid MLOD mesh record.");
                uint name = reader.ReadUInt32(); reader.ReadUInt32();
                uint formatRef = reader.ReadUInt32(), verticesRef = reader.ReadUInt32(), indicesRef = reader.ReadUInt32();
                uint primitive = reader.ReadUInt32(); int offset = checked((int)reader.ReadUInt32());
                reader.ReadInt32(); int firstIndex = reader.ReadInt32(); reader.ReadInt32();
                int vertices = reader.ReadInt32(), triangles = reader.ReadInt32();
                if ((primitive & 255) != 3) throw new NotSupportedException("Only triangle-list Sims meshes are supported.");
                if (vertices < 1 || vertices > 1000000 || triangles < 1 || triangles > 1000000 || offset < 0 || firstIndex < 0) throw new FormatException("Invalid mesh geometry count.");
                var model = Geometry(Resolve(package, rcol, formatRef, "VRTF"), Resolve(package, rcol, verticesRef, "VBUF"), Resolve(package, rcol, indicesRef, "IBUF"), offset, vertices, firstIndex, triangles);
                model.name = "Sims mesh " + name.ToString("X8"); model.id = entry.Key + ":" + i; model.source = package.Path;
                models.Add(model); stream.Position = start + size;
            }
        }
        return models;
    }
    public static WorkspaceProject Geometry(byte[] format, byte[] vertices, byte[] indices, int offset, int count, int firstIndex, int triangles)
    {
        if (format == null || vertices == null || indices == null || format.Length < 24 || vertices.Length < 16 || indices.Length < 16
            || count < 1 || count > 1000000 || triangles < 1 || triangles > 1000000 || offset < 0 || firstIndex < 0)
            throw new FormatException("Invalid Sims geometry buffers/ranges.");
        if (Encoding.ASCII.GetString(format, 0, 4) != "VRTF" || Encoding.ASCII.GetString(vertices, 0, 4) != "VBUF" || Encoding.ASCII.GetString(indices, 0, 4) != "IBUF")
            throw new FormatException("Invalid Sims geometry tags.");
        var model = new WorkspaceProject { vertices = new Vector3[count], uv = new Vector2[count], triangles = new int[checked(triangles * 3)] };
        int stride, posOffset = -1, posFormat = -1;
        using (var stream = new MemoryStream(format))
        using (var reader = new BinaryReader(stream)) {
            stream.Position = 8; stride = reader.ReadInt32(); int elements = reader.ReadInt32(); reader.ReadUInt32();
            if (stride < 1 || stride > 512 || elements < 1 || elements > 64) throw new FormatException("Invalid vertex layout.");
            for (int i = 0; i < elements; i++) {
                byte usage = reader.ReadByte(); reader.ReadByte(); byte encoding = reader.ReadByte(), location = reader.ReadByte();
                if (usage == 0) { posOffset = location; posFormat = encoding; }
            }
        }
        int positionBytes = posFormat == 2 ? 12 : posFormat == 3 ? 16 : posFormat == 7 || posFormat == 12 ? 8 : -1;
        if (posOffset < 0 || positionBytes < 0 || posOffset + positionBytes > stride) throw new NotSupportedException("Unsupported Sims position layout.");
        uint vflags = BitConverter.ToUInt32(vertices, 8);
        if ((vflags & ~1u) != 0) throw new NotSupportedException("Differenced/collapsed Sims vertex buffers are not yet supported.");
        if ((long)16 + offset + (long)count * stride > vertices.Length) throw new FormatException("Vertex buffer is truncated.");
        for (int i = 0; i < count; i++) {
            int at = checked(16 + offset + i * stride + posOffset);
            if (posFormat == 2 || posFormat == 3) model.vertices[i] = new Vector3(BitConverter.ToSingle(vertices, at), BitConverter.ToSingle(vertices, at + 4), BitConverter.ToSingle(vertices, at + 8));
            else {
                float divisor = BitConverter.ToUInt16(vertices, at + 6); if (divisor == 0) divisor = posFormat == 7 ? 32767 : 511;
                model.vertices[i] = new Vector3(BitConverter.ToInt16(vertices, at), BitConverter.ToInt16(vertices, at + 2), BitConverter.ToInt16(vertices, at + 4)) / divisor;
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
