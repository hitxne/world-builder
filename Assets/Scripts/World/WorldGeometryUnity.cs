using System.Collections.Generic;
using UnityEngine;

public static class WorldGeometryUnity
{
    public static WorkspaceProject Project(WorldConstruction p)
    {
        var mesh=WorldGeometry.Build(p);var vertices=new Vector3[mesh.vertices.Length];var uv=new Vector2[vertices.Length];
        for(int i=0;i<vertices.Length;i++){vertices[i]=new Vector3(mesh.vertices[i].x,mesh.vertices[i].y,mesh.vertices[i].z);uv[i]=new Vector2(mesh.uv[i*2],mesh.uv[i*2+1]);}
        var groups=new WorkspaceTriangles[mesh.groups.Length];var triangles=new List<int>();
        for(int i=0;i<groups.Length;i++){groups[i]=new WorkspaceTriangles{indices=mesh.groups[i]};triangles.AddRange(mesh.groups[i]);}
        var colors=WorldMaterials.Construction(p.kind);
        return new WorkspaceProject{construction=p,vertices=vertices,uv=uv,triangles=triangles.ToArray(),submeshes=groups,materialColors=colors,color=colors[0]};
    }
}
