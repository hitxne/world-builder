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

    [Test] public void HistoryDropsRedoAfterNewEdit()
    {
        var history = new WorkspaceHistory(); history.Reset("a"); history.Record("b"); history.Record("c");
        Assert.AreEqual("b", history.Undo()); history.Record("d");
        Assert.IsFalse(history.CanRedo); Assert.AreEqual("b", history.Undo()); Assert.AreEqual("d", history.Redo());
    }
    [Test] public void WorldSavesMultipleObjectsAndStableIds()
    {
        var root = new GameObject("World");
        try {
            for (int i = 0; i < 2; i++) {
                var child = GameObject.CreatePrimitive(PrimitiveType.Cube); child.transform.SetParent(root.transform);
                child.AddComponent<WorkspaceIdentity>().id = "stable-" + i; child.transform.position = new Vector3(i * 3, 1, 0);
            }
            string path = Path.Combine(folder, "world.wbworld");
            WorkspaceDocument.Capture(root.transform, "Test").Save(path);
            var loaded = WorkspaceDocument.Open(path);
            Assert.AreEqual(2, loaded.objects.Count); Assert.AreEqual("stable-1", loaded.objects[1].id);
            Assert.AreEqual(new Vector3(3, 1, 0), loaded.objects[1].position);
        } finally { UnityEngine.Object.DestroyImmediate(root); }
    }
    [Test] public void ObjExportBakesTransformsAndReimportsGeometry()
    {
        var root = new GameObject("Export"); Mesh imported = null;
        try {
            var child = GameObject.CreatePrimitive(PrimitiveType.Cube); child.transform.SetParent(root.transform);
            child.transform.position = new Vector3(4, 0, 0); child.transform.localScale = new Vector3(2, 1, 1);
            string path = Path.Combine(folder, "export.obj"); WorkspaceObjExport.Export(root.transform, path);
            imported = WorldBuilderObj.Load(path);
            Assert.IsTrue(File.Exists(Path.Combine(folder, "export.mtl")));
            Assert.AreEqual(4, imported.bounds.center.x, 0.0001f);
            Assert.AreEqual(2, imported.bounds.size.x, 0.0001f);
        } finally { if (imported != null) UnityEngine.Object.DestroyImmediate(imported); UnityEngine.Object.DestroyImmediate(root); }
    }
}
