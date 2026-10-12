using System;
using System.IO;
using System.Text;
using NUnit.Framework;
using UnityEngine;

public sealed class GameAdapterTests
{
    string folder;
    [SetUp] public void Setup() { folder = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString()); Directory.CreateDirectory(folder); }
    [TearDown] public void Cleanup() { Directory.Delete(folder, true); }
    static byte[] Bytes(Action<BinaryWriter> write)
    {
        using (var stream = new MemoryStream()) { using (var writer = new BinaryWriter(stream, Encoding.UTF8, true)) write(writer); return stream.ToArray(); }
    }
    static void Tag(BinaryWriter writer, string tag) => writer.Write(Encoding.ASCII.GetBytes(tag));
    string Package(byte[] payload, uint type, uint flags = 0, ushort compression = 0, uint logicalSize = 0)
    {
        string path = Path.Combine(folder, Guid.NewGuid().ToString() + ".package");
        var bytes = Bytes(w => {
            Tag(w, "DBPF"); w.Write(2u); w.Write(1u); w.Write(new byte[24]);
            w.Write(1u); w.Write(0u); w.Write(36u);
            w.Write(new byte[16]); w.Write((ulong)(96 + payload.Length)); w.Write(new byte[24]); w.Write(payload);
            w.Write(flags); if ((flags & 1) != 0) w.Write(type); if ((flags & 2) != 0) w.Write(0u); if ((flags & 4) != 0) w.Write(0u);
            if ((flags & 1) == 0) w.Write(type); if ((flags & 2) == 0) w.Write(0u); if ((flags & 4) == 0) w.Write(0u);
            w.Write(1u); w.Write(96u); w.Write(0x80000000u | (uint)payload.Length); w.Write(logicalSize == 0 ? (uint)payload.Length : logicalSize); w.Write(compression); w.Write((ushort)1);
        }); File.WriteAllBytes(path, bytes); return path;
    }
    [TestCase(0u)] [TestCase(1u)] [TestCase(3u)] [TestCase(7u)]
    public void DbpfCommonIndexFlagsReadSameResource(uint flags)
    {
        byte[] resource = Encoding.ASCII.GetBytes("original test resource");
        var package = new SimsPackage(Package(resource, SimsPackage.Mlod, flags));
        Assert.AreEqual(SimsPackage.Mlod, package.Entries[0].Type);
        CollectionAssert.AreEqual(resource, package.Read(package.Entries[0]));
    }
    [Test] public void DbpfUnsupportedCompressionFailsClearly()
    {
        var package = new SimsPackage(Package(new byte[] { 1, 2 }, SimsPackage.Mlod, compression: 0xffff));
        Assert.Throws<NotSupportedException>(() => package.Read(package.Entries[0]));
    }
    [Test] public void DbpfBadIndexBoundsAreRejected()
    {
        string path = Package(new byte[] { 1, 2 }, SimsPackage.Mlod);
        byte[] bytes = File.ReadAllBytes(path); Array.Copy(BitConverter.GetBytes(ulong.MaxValue), 0, bytes, 64, 8); File.WriteAllBytes(path, bytes);
        Assert.Throws<OverflowException>(() => new SimsPackage(path));
    }
    static byte[] Format() => Bytes(w => { Tag(w, "VRTF"); w.Write(2u); w.Write(12); w.Write(1); w.Write(0u); w.Write(new byte[] { 0, 0, 2, 0 }); });
    static byte[] Vertices() => Bytes(w => { Tag(w, "VBUF"); w.Write(1u); w.Write(0u); w.Write(0u); foreach (float f in new float[] { 0,0,0, 1,0,0, 0,1,0 }) w.Write(f); });
    static byte[] Indices() => Bytes(w => { Tag(w, "IBUF"); w.Write(1u); w.Write(0u); w.Write(0u); w.Write((ushort)0); w.Write((ushort)1); w.Write((ushort)2); });
    [Test] public void SimsInlineRcolMlodProducesTriangle()
    {
        byte[] mlod = Bytes(w => {
            Tag(w, "MLOD"); w.Write(0x202u); w.Write(1); w.Write(72u);
            w.Write(0x123u); w.Write(0u); w.Write(0x10000001u); w.Write(0x10000002u); w.Write(0x10000003u);
            w.Write(3u); w.Write(0u); w.Write(0); w.Write(0); w.Write(0); w.Write(3); w.Write(1); w.Write(new byte[24]);
        });
        byte[][] chunks = { mlod, Format(), Vertices(), Indices() };
        byte[] rcol = Bytes(w => {
            w.Write(3u); w.Write(1); w.Write(0u); w.Write(0); w.Write(4);
            for (int i = 0; i < 4; i++) { w.Write((ulong)i); w.Write(0u); w.Write(0u); }
            uint offset = 116;
            foreach (byte[] chunk in chunks) { w.Write(offset); w.Write(chunk.Length); offset += (uint)chunk.Length; }
            foreach (byte[] chunk in chunks) w.Write(chunk);
        });
        var package = new SimsPackage(Package(rcol, SimsPackage.Mlod));
        var models = SimsMeshPreview.Decode(package, package.Entries[0]);
        Assert.AreEqual(1, models.Count); Assert.AreEqual(Vector3.right, models[0].vertices[1]);
        CollectionAssert.AreEqual(new[] { 0, 1, 2 }, models[0].triangles);
    }
    [Test] public void SimsUnknownPositionLayoutIsRejected()
    {
        var format = Format(); format[22] = 255;
        Assert.Throws<NotSupportedException>(() => SimsMeshPreview.Geometry(format, Vertices(), Indices(), 0, 3, 0, 1));
    }
    [Test] public void ForzaNonBundleIsRejectedWithoutDecryptionAttempt()
    {
        string path = Path.Combine(folder, "encrypted.modelbin"); File.WriteAllBytes(path, new byte[32]);
        Assert.Throws<NotSupportedException>(() => new ForzaBundle(path));
    }
    [Test] public void ForzaFloatPositionPartProducesTriangle()
    {
        byte[] mesh = Bytes(w => {
            w.Write((short)0); w.Write((short)0); w.Write((ushort)3); w.Write((byte)0); w.Write((byte)255);
            w.Write((ushort)1); w.Write((byte)0); w.Write((byte)0); w.Write((byte)0); w.Write(false); w.Write(false); w.Write((ushort)4);
            w.Write(3); w.Write(0); w.Write(0); w.Write(0); w.Write(3); w.Write(1); w.Write(0.5f); w.Write(3u);
            w.Write(0); w.Write(1); w.Write(2); w.Write(0); w.Write(12); w.Write(0);
            w.Write(-1); w.Write(-1); w.Write(0); w.Write(0u); w.Write(new byte[80]);
            foreach (float f in new float[] { 1,1,1,0, 0,0,0,0 }) w.Write(f);
        });
        byte[] layout = Bytes(w => { w.Write((ushort)1); w.Write(8); Tag(w, "POSITION"); w.Write((ushort)1); w.Write((short)0); w.Write((short)0); w.Write((short)0); w.Write((short)0); w.Write(6); w.Write(0); w.Write(0); w.Write(0); });
        byte[] vertices = Bytes(w => { w.Write(3); w.Write(36); w.Write((ushort)12); w.Write((ushort)0); w.Write(6); foreach (float f in new float[] {0,0,0, 1,0,0, 0,1,0}) w.Write(f); });
        byte[] indices = Bytes(w => { w.Write(3); w.Write(6); w.Write((ushort)2); w.Write((ushort)0); w.Write(0); w.Write((ushort)0); w.Write((ushort)1); w.Write((ushort)2); });
        byte[][] chunks = { mesh, layout, vertices, indices };
        uint[] tags = { ForzaBundle.MeshTag, ForzaBundle.LayoutTag, ForzaBundle.VertexTag, ForzaBundle.IndexTag };
        string path = Path.Combine(folder, "sample.modelbin");
        File.WriteAllBytes(path, Bytes(w => {
            w.Write(0x47727562u); w.Write((byte)1); w.Write((byte)1); w.Write((ushort)0); w.Write(20u); w.Write(0u); w.Write(4u);
            uint offset = 116;
            for (int i = 0; i < 4; i++) { w.Write(tags[i]); w.Write((byte)1); w.Write((byte)(i == 0 ? 8 : 0)); w.Write((ushort)0); w.Write(0u); w.Write(offset); w.Write((uint)chunks[i].Length); w.Write((uint)chunks[i].Length); offset += (uint)chunks[i].Length; }
            foreach (byte[] chunk in chunks) w.Write(chunk);
        }));
        var bundle = new ForzaBundle(path); var model = ForzaMeshPreview.Decode(bundle, bundle.Blobs[0]);
        Assert.AreEqual(Vector3.up, model.vertices[2]); CollectionAssert.AreEqual(new[] { 0,1,2 }, model.triangles);
    }
}
