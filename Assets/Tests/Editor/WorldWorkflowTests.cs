using System;
using System.IO;
using System.Collections.Generic;
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
}
