using System;
using System.IO;
using UnityEngine;

// Stores mesh data rather than a dependency on the original imported OBJ.
[Serializable]
public sealed class WorkspaceProject
{
    public int version = 1;
    public string name = "Untitled", source = "";
    public Vector3 position, rotation, scale = Vector3.one;
    public Vector3[] vertices, normals;
    public Vector2[] uv;
    public int[] triangles;

    public static WorkspaceProject Capture(GameObject model, string source)
    {
        var mesh = model.GetComponent<MeshFilter>().sharedMesh;
        return new WorkspaceProject {
            name = model.name, source = source, position = model.transform.localPosition,
            rotation = model.transform.localEulerAngles, scale = model.transform.localScale,
            vertices = mesh.vertices, normals = mesh.normals, uv = mesh.uv, triangles = mesh.triangles
        };
    }
    public Mesh CreateMesh()
    {
        if (version != 1) throw new FormatException("Unsupported project version: " + version);
        if (vertices == null || vertices.Length == 0 || triangles == null || triangles.Length % 3 != 0)
            throw new FormatException("Invalid project geometry");
        foreach (var index in triangles)
            if (index < 0 || index >= vertices.Length) throw new FormatException("Invalid triangle index");
        var mesh = new Mesh { indexFormat = UnityEngine.Rendering.IndexFormat.UInt32, name = name };
        mesh.vertices = vertices;
        mesh.triangles = triangles;
        if (uv != null && uv.Length == vertices.Length) mesh.uv = uv;
        if (normals != null && normals.Length == vertices.Length) mesh.normals = normals;
        else mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }
    public void Save(string path)
    {
        string temporary = path + ".tmp";
        // Flush to disk before atomically replacing the previous manifest.
        using (var stream = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None))
        using (var writer = new StreamWriter(stream)) {
            writer.Write(JsonUtility.ToJson(this, true)); writer.Flush(); stream.Flush(true);
        }
        if (File.Exists(path)) File.Replace(temporary, path, path + ".bak");
        else File.Move(temporary, path);
    }
    public static WorkspaceProject Open(string path)
    {
        var project = JsonUtility.FromJson<WorkspaceProject>(File.ReadAllText(path));
        if (project == null || project.version != 1) throw new FormatException("Invalid or unsupported project");
        return project;
    }
}
