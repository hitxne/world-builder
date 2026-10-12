using System;
using System.IO;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

public class WorldWorkflowTests
{
    [Test] public void ParametricTerrainSurvivesWorldSaveWithPaintAndSubmeshes()
    {
        string path=Path.Combine(Path.GetTempPath(),Guid.NewGuid()+".wbworld");Mesh mesh=null;
        try {
            var p=WorldGeometry.Island(80,80,42);WorldGeometry.Brush(p,new WorldPoint(0,0,0),10,1,"sand",0);
            var item=WorldGeometryUnity.Project(p);item.id="terrain";
            new WorkspaceDocument{objects=new List<WorkspaceProject>{item}}.Save(path);
            var loaded=WorkspaceDocument.Open(path).objects[0];
            CollectionAssert.AreEqual(p.heights,loaded.construction.heights);CollectionAssert.AreEqual(p.paint,loaded.construction.paint);
            mesh=loaded.CreateMesh();Assert.AreEqual(3,mesh.subMeshCount);Assert.Greater(mesh.GetTriangles(1).Length,0);
        } finally {if(mesh!=null)UnityEngine.Object.DestroyImmediate(mesh);if(File.Exists(path))File.Delete(path);}
    }
    [Test] public void LotChildRelationshipIsSerialized()
    {
        var lot=new GameObject("Lot");var wall=new GameObject("Wall");Mesh mesh=null;
        try {
            lot.AddComponent<WorkspaceIdentity>().id="lot-id";
            mesh=WorldGeometryUnity.Project(new WorldConstruction{kind="lot",size=new WorldPoint(20,0.1f,20)}).CreateMesh();
            lot.AddComponent<MeshFilter>().sharedMesh=mesh;lot.AddComponent<MeshRenderer>();
            wall.transform.SetParent(lot.transform,false);wall.AddComponent<WorkspaceIdentity>().id="wall-id";
            wall.AddComponent<MeshFilter>().sharedMesh=mesh;wall.AddComponent<MeshRenderer>();
            var document=WorkspaceDocument.Capture(lot.transform,"Lot test");
            Assert.AreEqual(2,document.objects.Count);Assert.AreEqual("lot-id",document.objects[1].parentId);
        } finally {UnityEngine.Object.DestroyImmediate(lot);if(mesh!=null)UnityEngine.Object.DestroyImmediate(mesh);}
    }
    [Test] public void ObjMaterialGroupsProduceReusableAsset()
    {
        string folder=Path.Combine(Path.GetTempPath(),Guid.NewGuid().ToString());Directory.CreateDirectory(folder);
        try {
            File.WriteAllText(Path.Combine(folder,"test.mtl"),"newmtl red\nKd 1 0 0\nnewmtl green\nKd 0 1 0\n");
            string path=Path.Combine(folder,"test.obj");
            File.WriteAllText(path,"mtllib test.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nusemtl red\nf 1 2 3\nusemtl green\nf 1 3 4\n");
            var project=WorkspaceObjMaterials.Import(path,out string warning);
            Assert.IsEmpty(warning);Assert.AreEqual(2,project.submeshes.Length);Assert.AreEqual(Color.red,project.materialColors[0]);Assert.AreEqual(Color.green,project.materialColors[1]);
        } finally {Directory.Delete(folder,true);}
    }

    static void SetRuntime(WorldBuilderRuntime runtime,string name,object value)
        => typeof(WorldBuilderRuntime).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(runtime,value);
    static void EndGesture(WorldBuilderRuntime runtime,bool cancel)
        => typeof(WorldBuilderRuntime).GetMethod("EndObjectGesture",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(runtime,new object[]{cancel});

    [Test] public void GestureCancellationRestoresBuildingAndPreservesChildLocalTransform()
    {
        var host=new GameObject("Runtime test");host.SetActive(false);
        var building=new GameObject("Building");var child=new GameObject("Furniture");
        try {
            var runtime=host.AddComponent<WorldBuilderRuntime>();child.transform.SetParent(building.transform,false);
            child.transform.localPosition=new Vector3(2,1,3);
            SetRuntime(runtime,"gestureObject",building.transform);SetRuntime(runtime,"objectGesture",true);
            SetRuntime(runtime,"gesturePosition",new Vector3(1,0,1));SetRuntime(runtime,"gestureRotation",Quaternion.identity);SetRuntime(runtime,"gestureScale",Vector3.one);
            building.transform.localPosition=new Vector3(8,0,7);building.transform.localRotation=Quaternion.Euler(0,45,0);building.transform.localScale=Vector3.one*2;
            EndGesture(runtime,true);
            Assert.AreEqual(new Vector3(1,0,1),building.transform.localPosition);
            Assert.AreEqual(Quaternion.identity,building.transform.localRotation);Assert.AreEqual(Vector3.one,building.transform.localScale);
            Assert.AreEqual(new Vector3(2,1,3),child.transform.localPosition);
        } finally {UnityEngine.Object.DestroyImmediate(host);UnityEngine.Object.DestroyImmediate(building);}
    }
    [Test] public void GestureCommitCreatesOneReversibleDocumentSnapshot()
    {
        var host=new GameObject("Runtime test");host.SetActive(false);var world=new GameObject("World");
        var model=GameObject.CreatePrimitive(PrimitiveType.Cube);model.transform.SetParent(world.transform,false);model.AddComponent<WorkspaceIdentity>().id="object";
        WorldBuilderRuntime runtime=null;
        try {
            runtime=host.AddComponent<WorldBuilderRuntime>();SetRuntime(runtime,"world",world.transform);
            var history=(WorkspaceHistory)typeof(WorldBuilderRuntime).GetField("history",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(runtime);
            history.Reset(JsonUtility.ToJson(WorkspaceDocument.Capture(world.transform,"Untitled world")));
            SetRuntime(runtime,"gestureObject",model.transform);SetRuntime(runtime,"objectGesture",true);
            model.transform.localPosition=new Vector3(3,0,4);EndGesture(runtime,false);EndGesture(runtime,false);
            Assert.IsTrue(history.CanUndo);var original=JsonUtility.FromJson<WorkspaceDocument>(history.Undo());
            Assert.AreEqual(Vector3.zero,original.objects[0].position);Assert.IsFalse(history.CanUndo);
            var moved=JsonUtility.FromJson<WorkspaceDocument>(history.Redo());Assert.AreEqual(new Vector3(3,0,4),moved.objects[0].position);
        } finally {if(runtime!=null)SetRuntime(runtime,"world",null);UnityEngine.Object.DestroyImmediate(host);UnityEngine.Object.DestroyImmediate(world);}
    }
}
