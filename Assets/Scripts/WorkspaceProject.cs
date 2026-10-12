using System;
using System.IO;
using UnityEngine;

// Stores mesh data rather than a dependency on the original imported OBJ.
[Serializable]
public sealed class WorkspaceProject
{
    public int version = 1;
    public string name = "Untitled", source = "";
    public string id, parentId;
    public WorldConstruction construction;
    // JsonUtility can recreate a serialized null class as an empty object.
    public bool HasConstruction => construction!=null&&!string.IsNullOrWhiteSpace(construction.kind);
    public void NormalizeConstruction(){if(!HasConstruction)construction=null;}
    public Color[] materialColors;
    public float[] metallic, smoothness;
    public WorkspaceTriangles[] submeshes;
    public WorkspaceTexture[] albedo;
    public string libraryId;
    public Color color = new Color(0.65f, 0.72f, 0.78f, 1);
    public Vector3 position, rotation, scale = Vector3.one;
    public Vector3[] vertices, normals;
    public Vector2[] uv;
    public int[] triangles;

    public static WorkspaceProject Capture(GameObject model, string source)
    {
        var mesh = model.GetComponent<MeshFilter>().sharedMesh;
        return new WorkspaceProject {
            construction = model.GetComponent<WorkspaceIdentity>()?.construction,
            libraryId = model.GetComponent<WorkspaceIdentity>()?.libraryId,
            albedo = model.GetComponent<WorkspaceIdentity>()?.albedo,
            parentId = model.transform.parent?.GetComponent<WorkspaceIdentity>()?.id,
            submeshes = CaptureSubmeshes(mesh), materialColors = CaptureColors(model.GetComponent<Renderer>()),
            metallic=CaptureProperty(model.GetComponent<Renderer>(),"_Metallic"),smoothness=CaptureProperty(model.GetComponent<Renderer>(),"_Smoothness"),
            id = model.GetComponent<WorkspaceIdentity>()?.id ?? Guid.NewGuid().ToString("N"),
            color = ReadColor(model.GetComponent<Renderer>().sharedMaterial),
            name = model.name, source = source, position = model.transform.localPosition,
            rotation = model.transform.localEulerAngles, scale = model.transform.localScale,
            vertices = mesh.vertices, normals = mesh.normals, uv = mesh.uv, triangles = mesh.triangles
        };
    }
    static WorkspaceTriangles[] CaptureSubmeshes(Mesh mesh)
    {
        var result = new WorkspaceTriangles[mesh.subMeshCount];
        for(int i=0;i<result.Length;i++)result[i]=new WorkspaceTriangles{indices=mesh.GetTriangles(i)};
        return result;
    }
    static float[] CaptureProperty(Renderer renderer,string name)
    {
        var materials=renderer.sharedMaterials;var values=new float[materials.Length];
        for(int i=0;i<values.Length;i++)values[i]=materials[i]!=null&&materials[i].HasProperty(name)?materials[i].GetFloat(name):0;
        return values;
    }
    static Color[] CaptureColors(Renderer renderer)
    {
        var materials=renderer.sharedMaterials; var colors=new Color[materials.Length];
        for(int i=0;i<materials.Length;i++)colors[i]=ReadColor(materials[i]);
        return colors;
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
        if (submeshes != null && submeshes.Length > 0) {
            mesh.subMeshCount = submeshes.Length;
            for (int i=0;i<submeshes.Length;i++) {
                if (submeshes[i] == null || submeshes[i].indices == null || submeshes[i].indices.Length % 3 != 0) throw new FormatException("Invalid submesh triangles");
                foreach (int index in submeshes[i].indices) if(index<0||index>=vertices.Length)throw new FormatException("Invalid submesh index");
                mesh.SetTriangles(submeshes[i].indices, i);
            }
        } else mesh.triangles = triangles;
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

[Serializable]
public sealed class WorkspaceTriangles { public int[] indices; }

[Serializable]
public sealed class WorkspaceTexture { public string name, base64, sourcePath; }
