using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

// Editable, engine-independent road recipes accompany flattened OBJ geometry.
public static class WorkspaceRoadExport
{
    [Serializable] sealed class Manifest {public int version=1;public List<Road> roads=new List<Road>();}
    [Serializable] sealed class Road {public string id,name;public Matrix4x4 localToWorld;public WorldConstruction source;}
    public static void Write(Transform root,string objPath)
    {
        var manifest=new Manifest();foreach(var identity in root.GetComponentsInChildren<WorkspaceIdentity>())if(identity.gameObject.activeInHierarchy&&(identity.construction?.kind=="road"||identity.construction?.kind=="junction"))manifest.roads.Add(new Road{id=identity.id,name=identity.name,localToWorld=identity.transform.localToWorldMatrix,source=identity.construction});
        if(manifest.roads.Count>0)WorkspaceAtomicFile.Write(Path.ChangeExtension(objPath,".roads.json"),JsonUtility.ToJson(manifest,true));
    }
}
