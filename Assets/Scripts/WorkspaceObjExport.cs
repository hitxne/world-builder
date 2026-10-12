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
        foreach (var filter in root.GetComponentsInChildren<MeshFilter>())
        {
            Transform child=filter.transform;
            if (!child.gameObject.activeInHierarchy) continue;
            if (filter == null) continue;
            var mesh = filter.sharedMesh;
            string name = "object_" + number++ + "_" + System.Text.RegularExpressions.Regex.Replace(child.name, "[^A-Za-z0-9_-]", "_"), material = name + "_material";
            obj.Append("o ").Append(name).Append('\n');
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
            var materials=child.GetComponent<Renderer>().sharedMaterials;
            for(int group=0;group<mesh.subMeshCount;group++) {
                string matName=material+"_"+group;
                obj.Append("usemtl ").Append(matName).Append('\n');
                var triangles = mesh.GetTriangles(group);
                for (int i = 0; i < triangles.Length; i += 3) {
                    obj.Append("f");
                    for (int c = 0; c < 3; c++) {
                        int corner = mirrored && c > 0 ? 3 - c : c;
                        int id = offset + triangles[i + corner];
                        obj.Append(' ').Append(id).Append('/').Append(id).Append('/').Append(id);
                    }
                    obj.Append('\n');
                }
                Color color = WorkspaceProject.ReadColor(materials[Mathf.Min(group,materials.Length-1)]);
                mtl.Append("# Source material: ").Append(materials[Mathf.Min(group,materials.Length-1)].name.Replace("\n"," ").Replace("\r"," ")).Append('\n');
                mtl.Append("newmtl ").Append(matName).Append("\nKd ").Append(V(new Vector3(color.r, color.g, color.b))).Append("\nd ").Append(F(color.a)).Append('\n');
                var textures=child.GetComponent<WorkspaceIdentity>()?.albedo;
                if(textures!=null&&group<textures.Length&&textures[group]!=null) {
                    string extension=Path.GetExtension(textures[group].name).ToLowerInvariant();
                    if(extension!=".png"&&extension!=".jpg"&&extension!=".jpeg")throw new FormatException("Unsupported export texture extension");
                    string filename="WorldBuilder_"+matName+extension;
                    string destination=Path.Combine(Path.GetDirectoryName(path),filename);
                    if(!string.IsNullOrEmpty(textures[group].sourcePath)&&string.Equals(Path.GetFullPath(destination),Path.GetFullPath(textures[group].sourcePath),StringComparison.OrdinalIgnoreCase))
                        throw new IOException("Choose another export folder to preserve the imported texture source.");
                    WorkspaceAtomicFile.WriteBytes(destination,Convert.FromBase64String(textures[group].base64));
                    mtl.Append("map_Kd ").Append(filename).Append('\n');
                }
            }
            var appearance=child.GetComponent<WorkspaceIdentity>()?.sourceAppearance;
            if(appearance!=null) {
                string folder=Path.Combine(Path.GetDirectoryName(path),"WorldBuilder_"+name+"_source");Directory.CreateDirectory(folder);
                WorkspaceAtomicFile.Write(Path.Combine(folder,"manifest.json"),appearance.manifestJson??"{}");
                foreach(var resource in appearance.resources??new WorkspaceTexture[0]) {
                    if(resource==null||Path.GetFileName(resource.name)!=resource.name)throw new FormatException("Invalid source appearance resource name");
                    WorkspaceAtomicFile.WriteBytes(Path.Combine(folder,resource.name),Convert.FromBase64String(resource.base64));
                }
            }
            offset += vertices.Length;
        }
        if (number == 0) throw new InvalidOperationException("Add at least one object before exporting.");
        WorkspaceAtomicFile.Write(Path.Combine(Path.GetDirectoryName(path), materialFile), mtl.ToString());
        WorkspaceRoadExport.Write(root,path);
        WorkspaceAtomicFile.Write(path, obj.ToString());
    }
}
