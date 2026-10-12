using System;
using System.Collections.Generic;
using UnityEngine;

// Unity adapter over the shared, engine-independent read-only decoder.
public static class SimsMeshPreview
{
    static WorkspaceProject Project(SimsDecodedMesh mesh)
    {
        var vertices=new Vector3[mesh.vertices.Length];var uv=new Vector2[mesh.vertices.Length];
        for(int i=0;i<vertices.Length;i++)vertices[i]=new Vector3(mesh.vertices[i].x,mesh.vertices[i].y,mesh.vertices[i].z);
        return new WorkspaceProject{name=mesh.name,id=mesh.id,source=mesh.source,vertices=vertices,uv=uv,triangles=mesh.triangles};
    }
    public static List<WorkspaceProject> Decode(SimsPackage package,SimsPackage.Entry entry)
    {
        var result=new List<WorkspaceProject>();foreach(var mesh in SimsMeshReader.Decode(package,entry))result.Add(Project(mesh));return result;
    }
    public static WorkspaceProject Geometry(byte[] format,byte[] vertices,byte[] indices,int offset,int count,int firstIndex,int triangles)
        =>Project(SimsMeshReader.Geometry(format,vertices,indices,offset,count,firstIndex,triangles));
}
