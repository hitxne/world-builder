using System;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

public static class WorkspaceObjExport
{
    static string F(float x) => x.ToString("R", CultureInfo.InvariantCulture);
    static string V(Vector3 v) => F(v.x) + " " + F(v.y) + " " + F(v.z);
    public static void Export(Transform root, string path)
    {
        var obj = new StringBuilder("# World Builder; world-space coordinates, meters, Y-up\n");
        var mtl = new StringBuilder("# World Builder base-color materials\n");
        string materialFile = Path.GetFileNameWithoutExtension(path) + ".mtl";
        obj.Append("mtllib ").Append(materialFile).Append('\n');
        int offset = 1, number = 0;
        foreach (Transform child in root)
        {
            if (!child.gameObject.activeSelf) continue;
            var filter = child.GetComponent<MeshFilter>();
            if (filter == null) continue;
            var mesh = filter.sharedMesh;
            string name = "object_" + number++ + "_" + System.Text.RegularExpressions.Regex.Replace(child.name, "[^A-Za-z0-9_-]", "_"), material = name + "_material";
            obj.Append("o ").Append(name).Append('\n').Append("usemtl ").Append(material).Append('\n');
            var vertices = mesh.vertices; var uv = mesh.uv; var normals = mesh.normals;
            var normalMatrix = child.localToWorldMatrix.inverse.transpose;
            for (int i = 0; i < vertices.Length; i++) obj.Append("v ").Append(V(child.TransformPoint(vertices[i]))).Append('\n');
            for (int i = 0; i < vertices.Length; i++) {
                Vector2 t = uv.Length == vertices.Length ? uv[i] : Vector2.zero;
                obj.Append("vt ").Append(F(t.x)).Append(' ').Append(F(t.y)).Append('\n');
            }
            for (int i = 0; i < vertices.Length; i++) {
                Vector3 n = normals.Length == vertices.Length ? normals[i] : Vector3.up;
                obj.Append("vn ").Append(V(normalMatrix.MultiplyVector(n).normalized)).Append('\n');
            }
            bool mirrored = child.localToWorldMatrix.determinant < 0;
            var triangles = mesh.triangles;
            for (int i = 0; i < triangles.Length; i += 3) {
                obj.Append("f");
                for (int c = 0; c < 3; c++) {
                    int corner = mirrored && c > 0 ? 3 - c : c;
                    int id = offset + triangles[i + corner];
                    obj.Append(' ').Append(id).Append('/').Append(id).Append('/').Append(id);
                }
                obj.Append('\n');
            }
            Color color = WorkspaceProject.ReadColor(child.GetComponent<Renderer>().sharedMaterial);
            mtl.Append("newmtl ").Append(material).Append("\nKd ").Append(V(new Vector3(color.r, color.g, color.b))).Append("\nd 1\n");
            offset += vertices.Length;
        }
        if (number == 0) throw new InvalidOperationException("Add at least one object before exporting.");
        WorkspaceAtomicFile.Write(Path.Combine(Path.GetDirectoryName(path), materialFile), mtl.ToString());
        WorkspaceAtomicFile.Write(path, obj.ToString());
    }
}
