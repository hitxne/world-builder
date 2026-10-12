using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

public static class WorldBuilderObj
{
    static readonly CultureInfo C = CultureInfo.InvariantCulture;
    public static Mesh Load(string path)
    {
        var positions = new List<Vector3>();
        var uvs = new List<Vector2>();
        var normals = new List<Vector3>();
        var outPos = new List<Vector3>();
        var outUV = new List<Vector2>();
        var outNormal = new List<Vector3>();
        var triangles = new List<int>();
        var unique = new Dictionary<string, int>();
        foreach (var raw in File.ReadLines(path))
        {
            string line = raw.Split('#')[0].Trim();
            if (line.Length == 0 || line.StartsWith("#")) continue;
            var tokens = line.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
            if (tokens.Length < 2) continue;
            if (tokens[0] == "v" && tokens.Length >= 4)
                positions.Add(new Vector3(Parse(tokens[1]), Parse(tokens[2]), Parse(tokens[3])));
            else if (tokens[0] == "vt" && tokens.Length >= 3)
                uvs.Add(new Vector2(Parse(tokens[1]), Parse(tokens[2])));
            else if (tokens[0] == "vn" && tokens.Length >= 4)
                normals.Add(new Vector3(Parse(tokens[1]), Parse(tokens[2]), Parse(tokens[3])));
            else if (tokens[0] == "f" && tokens.Length >= 4)
            {
                var corners = new List<int>();
                for (int i = 1; i < tokens.Length; i++)
                {
                    var parts = tokens[i].Split('/');
                    int pi = Index(parts[0], positions.Count);
                    int ti = parts.Length > 1 && parts[1].Length > 0 ? Index(parts[1], uvs.Count) : -1;
                    int ni = parts.Length > 2 && parts[2].Length > 0 ? Index(parts[2], normals.Count) : -1;
                    var key = pi + "/" + ti + "/" + ni;
                    if (!unique.TryGetValue(key, out var vertexIndex))
                    {
                        int posId = pi;
                        if (posId < 0 || posId >= positions.Count) throw new FormatException("OBJ face references nonexistent vertex");
                        vertexIndex = outPos.Count;
                        unique[key] = vertexIndex;
                        outPos.Add(positions[posId]);
                        outUV.Add(parts.Length > 1 && parts[1].Length > 0 ? uvs[ti] : Vector2.zero);
                        outNormal.Add(parts.Length > 2 && parts[2].Length > 0 ? normals[ni] : Vector3.zero);
                    }
                    corners.Add(vertexIndex);
                }
                for (int i = 1; i + 1 < corners.Count; i++)
                {
                    triangles.Add(corners[0]); triangles.Add(corners[i]); triangles.Add(corners[i + 1]);
                }
            }
        }
        if (triangles.Count == 0) throw new FormatException("OBJ contains no faces");
        var mesh = new Mesh { name = Path.GetFileNameWithoutExtension(path) };
        mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
        mesh.SetVertices(outPos);
        mesh.SetUVs(0, outUV);
        mesh.SetTriangles(triangles, 0);
        bool hasNormals = outNormal.TrueForAll(n => n.sqrMagnitude > 0.00001f);
        if (hasNormals) mesh.SetNormals(outNormal); else mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static float Parse(string s)
    {
        float value = float.Parse(s, NumberStyles.Float, C);
        if (float.IsNaN(value) || float.IsInfinity(value)) throw new FormatException("Non-finite OBJ coordinate");
        return value;
    }
    static int Index(string s, int count)
    {
        int i = int.Parse(s, C), resolved = i > 0 ? i - 1 : count + i;
        if (i == 0 || resolved < 0 || resolved >= count) throw new FormatException("OBJ index outside available data");
        return resolved;
    }

}
