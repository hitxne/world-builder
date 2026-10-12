using System;
using System.IO;
using UnityEngine;

// Stores mesh data rather than a dependency on the original imported OBJ.
[Serializable]
public sealed class WorkspaceProject
{
    public int version = 1;
    public string name = "Untitled", source = "";
    public string id;
    public Color color = new Color(0.65f, 0.72f, 0.78f, 1);
    public Vector3 position, rotation, scale = Vector3.one;
    public Vector3[] vertices, normals;
    public Vector2[] uv;
    public int[] triangles;

    public static WorkspaceProject Capture(GameObject model, string source)
    {
        var mesh = model.GetComponent<MeshFilter>().sharedMesh;
        return new WorkspaceProject {
            id = model.GetComponent<WorkspaceIdentity>()?.id ?? Guid.NewGuid().ToString("N"),
            color = ReadColor(model.GetComponent<Renderer>().sharedMaterial),
            name = model.name, source = source, position = model.transform.localPosition,
            rotation = model.transform.localEulerAngles, scale = model.transform.localScale,
            vertices = mesh.vertices, normals = mesh.normals, uv = mesh.uv, triangles = mesh.triangles
        };
    }
    public static Color ReadColor(Material material)
    {
        if (material == null) return Color.gray;
        return material.HasProperty("_BaseColor") ? material.GetColor("_BaseColor") : material.color;
    }
    public Mesh CreateMesh()
    {
        if (version != 1) throw new FormatException("Unsupported project version: " + version);
        if (vertices == null || vertices.Length == 0 || triangles == null || triangles.Length % 3 != 0)
            throw new FormatException("Invalid project geometry");
        foreach (var vertex in vertices) Validate(vertex);
        Validate(position); Validate(rotation); Validate(scale);
        if (Mathf.Abs(scale.x * scale.y * scale.z) < 0.000001f) throw new FormatException("Object scale must be non-zero");
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
    static void Validate(Vector3 value)
    {
        if (float.IsNaN(value.x) || float.IsNaN(value.y) || float.IsNaN(value.z)
            || float.IsInfinity(value.x) || float.IsInfinity(value.y) || float.IsInfinity(value.z))
            throw new FormatException("Project contains non-finite values");
    }
    public void Save(string path)
    {
        WorkspaceAtomicFile.Write(path, JsonUtility.ToJson(this, true));
    }

    public static WorkspaceProject Open(string path)
    {
        var project = JsonUtility.FromJson<WorkspaceProject>(File.ReadAllText(path));
        if (project == null || project.version != 1) throw new FormatException("Invalid or unsupported project");
        return project;
    }
}
