using System;
using System.IO;
using NUnit.Framework;
using UnityEngine;

public class FoundationTests
{
    string folder;
    [SetUp] public void Setup() { folder = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString()); Directory.CreateDirectory(folder); }
    [TearDown] public void Cleanup() { Directory.Delete(folder, true); }
    Mesh Obj(string text) { string path = Path.Combine(folder, "sample.obj"); File.WriteAllText(path, text); return WorldBuilderObj.Load(path); }

    [Test] public void RelativeIndicesResolveAtEachFace()
    {
        var mesh = Obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\nv 0 0 1\nf -3 -2 -1 # next face\n");
        try { Assert.AreEqual(4, mesh.vertexCount); Assert.AreEqual(6, mesh.triangles.Length); }
        finally { UnityEngine.Object.DestroyImmediate(mesh); }
    }
    [TestCase("v 0 0 0\nf 0 1 1")]
    [TestCase("v 0 0 0\nf 1/1 1/1 1/1")]
    [TestCase("v NaN 0 0")]
    [TestCase("v 0 0 0")]
    public void InvalidGeometryIsRejected(string text) { Assert.Throws<FormatException>(() => Obj(text)); }

    [Test] public void ProjectRoundTripSurvivesMissingSourceAndKeepsBackup()
    {
        var original = GameObject.CreatePrimitive(PrimitiveType.Cube);
        original.transform.localPosition = new Vector3(2, 3, 4);
        original.transform.localScale = new Vector3(2, 1, 3);
        string path = Path.Combine(folder, "test.wbasset");
        Mesh restored = null;
        try {
            var project = WorkspaceProject.Capture(original, "missing.obj"); project.Save(path); project.Save(path);
            Assert.IsTrue(File.Exists(path + ".bak"));
            var loaded = WorkspaceProject.Open(path); restored = loaded.CreateMesh();
            Assert.AreEqual(original.transform.localPosition, loaded.position);
            Assert.AreEqual(original.transform.localScale, loaded.scale);
            CollectionAssert.AreEqual(original.GetComponent<MeshFilter>().sharedMesh.vertices, restored.vertices);
            CollectionAssert.AreEqual(original.GetComponent<MeshFilter>().sharedMesh.triangles, restored.triangles);
        } finally { if (restored != null) UnityEngine.Object.DestroyImmediate(restored); UnityEngine.Object.DestroyImmediate(original); }
    }
    [Test] public void FutureProjectVersionIsRejected()
    {
        string path = Path.Combine(folder, "future.wbasset"); File.WriteAllText(path, "{\"version\":99}");
        Assert.Throws<FormatException>(() => WorkspaceProject.Open(path));
    }
}
