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

    [Test] public void RoadSurfaceFollowsRaiseAndLowerBetweenControlPoints()
    {
        var terrain=WorldGeometry.Island(100,100,7);Array.Clear(terrain.heights,0,terrain.heights.Length);
        var road=new WorldConstruction{kind="road",points=new[]{new WorldPoint(-30,0,0),new WorldPoint(30,0,0)}};
        var flat=WorldGeometry.Build(road);
        WorldGeometry.Brush(terrain,new WorldPoint(0,0,0),10,1,"raise",0);
        var raised=WorldGeometry.Build(road);
        WorldGeometry.ConformRoad(raised,(v,clearance)=>new WorldPoint(v.x,WorldGeometry.Height(terrain,v.x,v.z)+clearance,v.z));
        bool middleRaised=false;
        foreach(int index in raised.groups[0]) {
            var v=raised.vertices[index];Assert.AreEqual(WorldGeometry.Height(terrain,v.x,v.z)+0.05f,v.y,0.00001f);
            if(Math.Abs(v.x)<5&&v.y>flat.vertices[index].y)middleRaised=true;
        }
        Assert.IsTrue(middleRaised,"A brush between sparse endpoints must affect road surface vertices");
        WorldGeometry.Brush(terrain,new WorldPoint(0,0,0),10,2,"lower",0);
        var lowered=WorldGeometry.Build(road);WorldGeometry.ConformRoad(lowered,(v,clearance)=>new WorldPoint(v.x,WorldGeometry.Height(terrain,v.x,v.z)+clearance,v.z));
        bool middleLowered=false;
        for(int i=0;i<lowered.vertices.Length;i++)if(Math.Abs(lowered.vertices[i].x)<5&&lowered.vertices[i].y<raised.vertices[i].y)middleLowered=true;
        Assert.IsTrue(middleLowered);
        foreach(int index in lowered.groups[1]){var v=lowered.vertices[index];Assert.AreEqual(WorldGeometry.Height(terrain,v.x,v.z)+0.15f,v.y,0.00001f);}
        foreach(int index in lowered.groups[2]){var v=lowered.vertices[index];Assert.AreEqual(WorldGeometry.Height(terrain,v.x,v.z)+0.07f,v.y,0.00001f);}
    }
    [Test] public void RoadProjectionPreservesUncoveredGeometryAndSplineSource()
    {
        var road=new WorldConstruction{kind="road",points=new[]{new WorldPoint(0,4,0),new WorldPoint(20,4,0)}};
        var mesh=WorldGeometry.Build(road);var original=(WorldPoint[])mesh.vertices.Clone();
        WorldGeometry.ConformRoad(mesh,(v,clearance)=>null);
        CollectionAssert.AreEqual(original,mesh.vertices);Assert.AreEqual(4,road.points[0].y);
    }

    [Test] public void LegacyImportedMeshWithEmptyConstructionSurvivesLibraryRoundtrip()
    {
        string path=Path.Combine(Path.GetTempPath(),Guid.NewGuid()+".wbworld");Mesh mesh=null;
        try {
            var imported=new WorkspaceProject{id="legacy-import",name="Imported mesh",construction=new WorldConstruction{kind=""},vertices=new[]{Vector3.zero,Vector3.right,Vector3.up},triangles=new[]{0,1,2}};
            new WorkspaceDocument{objects=new List<WorkspaceProject>{imported}}.Save(path);
            var loaded=WorkspaceDocument.Open(path).objects[0];
            Assert.IsFalse(loaded.HasConstruction);Assert.IsNull(loaded.construction);
            mesh=loaded.CreateMesh();CollectionAssert.AreEqual(imported.vertices,mesh.vertices);Assert.AreEqual(3,mesh.vertexCount);
        } finally {if(mesh!=null)UnityEngine.Object.DestroyImmediate(mesh);if(File.Exists(path))File.Delete(path);}
    }
    [Test] public void UnknownNonemptyConstructionStillReportsAnError()
    {
        var project=new WorkspaceProject{construction=new WorldConstruction{kind="unsupported-kind"}};
        project.NormalizeConstruction();Assert.IsTrue(project.HasConstruction);
        Assert.Throws<ArgumentException>(()=>WorldGeometry.Build(project.construction));
    }
    [Test] public void ImportedAppearanceSurvivesSaveAndObjExport()
    {
        string folder=Path.Combine(Path.GetTempPath(),Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);
        var root=new GameObject("appearance export fixture");Mesh mesh=null;Material material=null;Texture2D image=null;
        try {
            image=new Texture2D(1,1);image.SetPixel(0,0,Color.red);image.Apply();byte[] png=image.EncodeToPNG();
            string obj=Path.Combine(folder,"chair.obj");File.WriteAllBytes(Path.Combine(folder,"chair.png"),png);
            File.WriteAllText(Path.Combine(folder,"chair.mtl"),"newmtl Chair fabric\nKd 1 1 1\nd 0.8\nmap_Kd chair.png\n");
            File.WriteAllText(obj,"mtllib chair.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nvn 0 0 1\nusemtl Chair fabric\nf 1/1/1 2/2/1 3/3/1\n");
            var item=WorkspaceObjMaterials.Import(obj,out var warning);Assert.IsEmpty(warning);Assert.AreEqual("Chair fabric",item.materialNames[0]);Assert.AreEqual(0.8f,item.materialColors[0].a,0.001f);
            item.appearanceFingerprint="fixture revision";item.sourceAppearance=new WorkspaceSourceAppearance{manifestJson="{\"version\":2}",resources=new[]{new WorkspaceTexture{name="original.bin",base64=Convert.ToBase64String(new byte[]{1,2,3,4})}}};
            string project=Path.Combine(folder,"chair.wbworld");new WorkspaceDocument{objects=new List<WorkspaceProject>{item}}.Save(project);
            var loaded=WorkspaceDocument.Open(project).objects[0];Assert.AreEqual("fixture revision",loaded.appearanceFingerprint);Assert.AreEqual(item.sourceAppearance.resources[0].base64,loaded.sourceAppearance.resources[0].base64);
            CollectionAssert.AreEqual(png,Convert.FromBase64String(loaded.albedo[0].base64));CollectionAssert.AreEqual(item.uv,loaded.uv);
            var go=new GameObject("Chair");go.transform.SetParent(root.transform);mesh=loaded.CreateMesh();go.AddComponent<MeshFilter>().sharedMesh=mesh;
            material=new Material(Shader.Find("Standard")){name="Chair fabric",color=loaded.materialColors[0]};go.AddComponent<MeshRenderer>().sharedMaterials=new[]{material};
            var identity=go.AddComponent<WorkspaceIdentity>();identity.albedo=loaded.albedo;identity.sourceAppearance=loaded.sourceAppearance;
            WorkspaceObjExport.Export(root.transform,Path.Combine(folder,"result.obj"));
            Assert.IsTrue(File.ReadAllText(Path.Combine(folder,"result.mtl")).Contains("map_Kd"));
            CollectionAssert.AreEqual(new byte[]{1,2,3,4},File.ReadAllBytes(Path.Combine(folder,"WorldBuilder_object_0_Chair_source","original.bin")));
            var roundtrip=WorkspaceObjMaterials.Import(Path.Combine(folder,"result.obj"),out warning);Assert.IsEmpty(warning);CollectionAssert.AreEqual(png,Convert.FromBase64String(roundtrip.albedo[0].base64));
        }finally {UnityEngine.Object.DestroyImmediate(root);if(mesh!=null)UnityEngine.Object.DestroyImmediate(mesh);if(material!=null)UnityEngine.Object.DestroyImmediate(material);if(image!=null)UnityEngine.Object.DestroyImmediate(image);Directory.Delete(folder,true);}
    }

}
