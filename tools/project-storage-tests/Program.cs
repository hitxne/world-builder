using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
class Program {
 static void Check(bool value,string message){if(!value)throw new Exception(message);}
 static WorkspaceProject Item(string id)=>new WorkspaceProject{id=id,name="Chair",vertices=new[]{new Vector3(0,0,0),new Vector3(1,0,0),new Vector3(0,1,0)},triangles=new[]{0,1,2},materialColors=new[]{new Color(.65f,.72f,.78f)},albedo=new[]{new WorkspaceTexture{name="fabric.png",base64=Convert.ToBase64String(new byte[]{1,2,3,4})}}};
 static void Main(){string folder=Path.Combine(Path.GetTempPath(),"WorldBuilderStorageTest-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(folder);
 try {
  var first=Item("one");var second=Item("two");second.position=new Vector3(10,2,3);string path=Path.Combine(folder,"world.wbworld");
  var doc=new WorkspaceDocument{objects=new List<WorkspaceProject>{first,second}};doc.Save(path);
  Check(File.ReadAllText(path).Contains("\"version\":2"),"versioned compact manifest");Check(!File.ReadAllText(path).Contains("AQIDBA=="),"no embedded texture bytes");
  Check(Directory.GetFiles(path+".assets","*.blob").Length==2,"one geometry and one texture for two instances");
  var loaded=WorkspaceDocument.Open(path);Check(loaded.objects[1].position.x==10,"instance transform survives");Check(loaded.objects[0].albedo[0].base64==first.albedo[0].base64,"texture restored");Check(ReferenceEquals(loaded.objects[0].vertices,loaded.objects[1].vertices),"shared geometry hydration");
  loaded.objects[0].position.x=5;loaded.Save(path);Check(Directory.GetFiles(path+".assets","*.blob").Length==2,"incremental save reuses assets");Check(WorkspaceDocument.Open(path+".bak").objects[0].position.x==0,"previous manifest remains recoverable");
  string legacy=Path.Combine(folder,"legacy.wbworld");File.WriteAllText(legacy,JsonUtility.ToJson(doc));Check(WorkspaceDocument.Open(legacy).objects.Count==2,"legacy JSON remains readable");
  var terrain=new WorkspaceProject{id="terrain",construction=WorldGeometry.Island(40,40,1)};var terrainDoc=new WorkspaceDocument{objects=new List<WorkspaceProject>{terrain}};string terrainPath=Path.Combine(folder,"terrain.wbworld");terrainDoc.Save(terrainPath);Check(WorkspaceDocument.Open(terrainPath).objects[0].vertices.Length>0,"procedural geometry rebuilt from source");
  var store=new WorkspaceBlobStore(Path.Combine(folder,"history"));string snapshot=WorkspaceProjectStorage.Serialize(doc,store,"history");var history=new WorkspaceHistory();history.Reset(snapshot);doc.objects[0].position.x=9;history.Record(WorkspaceProjectStorage.Serialize(doc,store,"history"));Check(WorkspaceProjectStorage.Read(history.Undo(),store).objects[0].position.x==0,"reference-based undo");Check(WorkspaceProjectStorage.Read(history.Redo(),store).objects[0].position.x==9,"reference-based redo");
  var edited=Item("edited");WorkspaceAssetUpdate.Baseline(edited);edited.vertices[0].x=4;var incoming=Item("incoming");incoming.uv=new[]{new Vector2(0,0),new Vector2(1,0),new Vector2(0,1)};WorkspaceAssetUpdate.Baseline(incoming);Check(WorkspaceAssetUpdate.Merge(edited,incoming).Contains("retained"),"edit conflict reported");Check(edited.vertices[0].x==4&&edited.uv[1].x==1,"compatible edits survive appearance update");
  var topology=Item("topology");WorkspaceAssetUpdate.Baseline(topology);topology.triangles=new[]{2,1,0};Check(WorkspaceAssetUpdate.Merge(topology,incoming).Contains("topology"),"incompatible topology retained");Check(topology.triangles[0]==2,"topology not overwritten");
  var tinted=Item("tinted");WorkspaceAssetUpdate.Baseline(tinted);tinted.materialColors[0]=new Color(1,0,0);WorkspaceAssetUpdate.Merge(tinted,incoming);Check(tinted.materialColors[0].r==1&&tinted.materialColors[0].g==0,"material edits retained");
  var slots=Item("slots");WorkspaceAssetUpdate.Baseline(slots);slots.materialColors[0]=new Color(1,0,0);var moreSlots=Item("moreSlots");moreSlots.submeshes=new[]{new WorkspaceTriangles{indices=new[]{0,1,2}},new WorkspaceTriangles{indices=new int[0]}};Check(WorkspaceAssetUpdate.Merge(slots,moreSlots).Contains("layout"),"material layout conflict held");Check(slots.submeshes==null,"custom material mapping remains intact");
  string unused=store.Put(new byte[]{7,8,9});store.PruneSession(WorkspaceProjectStorage.References(history.Snapshots));Check(!File.Exists(Path.Combine(store.Folder,unused+".blob")),"unreachable session payload removed");Check(WorkspaceProjectStorage.Read(history.Undo(),store).objects.Count==2,"undo payload survives session pruning");
  string blob=Directory.GetFiles(path+".assets","*.blob")[0];File.WriteAllBytes(blob,new byte[]{9});bool corrupt=false;try{WorkspaceDocument.Open(path);}catch(IOException){corrupt=true;}Check(corrupt,"corrupt payload rejected");
  bool traversal=false;try{store.Read("../bad");}catch(FormatException){traversal=true;}Check(traversal,"invalid blob reference rejected");
  Console.WriteLine("PASS real storage/update source: shared payloads, incremental save, backup, legacy loading, procedural source, undo/redo, geometry/material conflicts, corruption/path rejection. Serialization shim; not Unity verification.");
 }finally{Directory.Delete(folder,true);}}
}
