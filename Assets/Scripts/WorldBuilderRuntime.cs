using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

// An intentionally small, self-contained first runnable slice: dual preview cameras,
// OBJ import (triangles, groups, normals, UVs) and a persistent local source reference.
public sealed class WorldBuilderRuntime : MonoBehaviour
{
    Camera referenceCamera, workCamera;
    RenderTexture referenceTexture, workTexture;
    GameObject referenceRoot, workRoot;
    string modelPath = "", status = "Import a Blender OBJ to begin.";
    string installationStatus = "Not scanned";
    string[] gameNames = { "Forza Horizon 5", "The Sims 4" };
    string[] gamePaths = new string[2];
    List<string> catalog = new List<string>();
    Vector2 catalogScroll;
    bool showBrowser = false;
    int selectedGame = 0;
    Vector2 referenceAngles = new Vector2(25, -25), workAngles = new Vector2(25, -25);
    float referenceDistance = 8f, workDistance = 8f;
    Vector3 referenceCenter, workCenter;
    int activeView = -1;
    static readonly CultureInfo C = CultureInfo.InvariantCulture;

    void Start()
    {
        referenceRoot = new GameObject("Reference Model");
        workRoot = new GameObject("Editable Model");
        referenceCamera = CreateCamera("Reference Camera", out referenceTexture);
        workCamera = CreateCamera("Work Camera", out workTexture);
        MakePrimitive(referenceRoot.transform, PrimitiveType.Cube, new Vector3(0, 0.5f, 0));
        MakePrimitive(workRoot.transform, PrimitiveType.Cube, new Vector3(0, 0.5f, 0));
        for (int i = 0; i < gamePaths.Length; i++) gamePaths[i] = PlayerPrefs.GetString("worldbuilder.gamePath." + i, "");
        LocateInstallations();
    }

    static Camera CreateCamera(string name, out RenderTexture target)
    {
        var obj = new GameObject(name);
        var camera = obj.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = new Color(0.075f, 0.095f, 0.12f);
        camera.fieldOfView = 48f;
        camera.nearClipPlane = 0.02f;
        camera.farClipPlane = 10000;
        target = new RenderTexture(960, 600, 24);
        target.Create();
        camera.targetTexture = target;
        var key = new GameObject(name + " Light").AddComponent<Light>();
        key.type = LightType.Directional;
        key.intensity = 1.4f;
        key.transform.rotation = Quaternion.Euler(45, -35, 0);
        return camera;
    }

    static void MakePrimitive(Transform parent, PrimitiveType type, Vector3 pos)
    {
        var go = GameObject.CreatePrimitive(type);
        go.transform.SetParent(parent, false);
        go.transform.position = pos;
        go.name = "Sample geometry (replace by importing OBJ)";
    }

    void Update()
    {
        if (Input.GetMouseButton(0) && activeView >= 0)
        {
            var delta = new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y")) * 3f;
            if (activeView == 0) referenceAngles += new Vector2(-delta.y, delta.x);
            else workAngles += new Vector2(-delta.y, delta.x);
        }
        float scroll = Input.mouseScrollDelta.y;
        if (activeView == 0) referenceDistance = Mathf.Clamp(referenceDistance * Mathf.Exp(-scroll * 0.12f), 0.25f, 10000f);
        if (activeView == 1) workDistance = Mathf.Clamp(workDistance * Mathf.Exp(-scroll * 0.12f), 0.25f, 10000f);
        Position(referenceCamera, referenceAngles, referenceCenter, referenceDistance);
        Position(workCamera, workAngles, workCenter, workDistance);
    }

    static void Position(Camera camera, Vector2 angles, Vector3 target, float distance)
    {
        angles.x = Mathf.Clamp(angles.x, -89, 89);
        var orbit = Quaternion.Euler(angles.x, angles.y, 0);
        camera.transform.position = target + orbit * (Vector3.back * distance);
        camera.transform.LookAt(target);
    }

    void OnGUI()
    {
        var scale = Mathf.Max(0.7f, Mathf.Min(Screen.width / 1280f, Screen.height / 720f));
        var matrix = GUI.matrix;
        GUI.matrix = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(scale, scale, 1));
        var w = Screen.width / scale;
        var h = Screen.height / scale;
        GUI.color = new Color(0.08f, 0.105f, 0.14f);
        GUI.DrawTexture(new Rect(0, 0, w, h), Texture2D.whiteTexture);
        GUI.color = Color.white;
        GUI.Label(new Rect(24, 12, 550, 28), "WORLD BUILDER  /  ASSET CREATOR  /  v0.2 preview");
        if (GUI.Button(new Rect(w - 635, 10, 130, 32), "Game Browser")) showBrowser = !showBrowser;
        if (GUI.Button(new Rect(w - 495, 10, 130, 32), "Import OBJ")) Import();
        if (GUI.Button(new Rect(w - 355, 10, 155, 32), "Refresh Game Paths")) LocateInstallations();
        if (GUI.Button(new Rect(w - 190, 10, 165, 32), "Reimport")) ImportExisting();

        var padding = 22f;
        var top = 58f;
        var footer = 174f;
        var viewWidth = (w - padding * 3) / 2;
        var viewHeight = Mathf.Max(100, h - top - footer);
        var left = new Rect(padding, top, viewWidth, viewHeight);
        var right = new Rect(padding * 2 + viewWidth, top, viewWidth, viewHeight);
        GUI.DrawTexture(left, referenceTexture, ScaleMode.StretchToFill, false);
        GUI.DrawTexture(right, workTexture, ScaleMode.StretchToFill, false);
        GUI.Label(new Rect(left.x + 10, top + 10, 220, 22), "REFERENCE");
        GUI.Label(new Rect(right.x + 10, top + 10, 270, 22), "EDITABLE ASSET");
        var mouse = Event.current.mousePosition;
        activeView = left.Contains(mouse) ? 0 : right.Contains(mouse) ? 1 : -1;
        GUI.Label(new Rect(24, h - 159, w - 48, 28), "SOURCE  " + (string.IsNullOrWhiteSpace(modelPath) ? "No imported model" : modelPath));
        GUI.Label(new Rect(24, h - 133, w - 48, 26), "STATUS  " + status);
        GUI.Label(new Rect(24, h - 107, w - 48, 26), "GAME INSTALLATIONS  " + installationStatus);
        GUI.Label(new Rect(24, h - 76, w - 48, 26), "Controls: hover viewport • left-drag orbit • mouse wheel zoom • Import OBJ / Reimport");
        GUI.Label(new Rect(24, h - 50, w - 48, 26), "Browser indexes loose OBJ files only. Proprietary Sims/Forza packages are not decoded.");
        if (showBrowser) DrawGameBrowser(w, h);
        GUI.matrix = matrix;
    }

    void Import()
    {
#if UNITY_EDITOR
        string selected = UnityEditor.EditorUtility.OpenFilePanel("Import Blender OBJ", Path.GetDirectoryName(modelPath), "obj");
        if (!string.IsNullOrEmpty(selected)) modelPath = selected;
#endif
        if (string.IsNullOrWhiteSpace(modelPath))
        {
            status = "In editor use Import OBJ. For standalone builds, set WORLD_BUILDER_OBJ_PATH to an absolute OBJ path.";
            modelPath = Environment.GetEnvironmentVariable("WORLD_BUILDER_OBJ_PATH") ?? "";
        }
        ImportExisting();
    }

    void ImportExisting()
    {
        if (string.IsNullOrWhiteSpace(modelPath) || !File.Exists(modelPath)) { status = "No valid OBJ path selected."; return; }
        try
        {
            var mesh = LoadObj(modelPath);
            foreach (Transform child in workRoot.transform) Destroy(child.gameObject);
            var model = new GameObject(Path.GetFileNameWithoutExtension(modelPath));
            model.transform.SetParent(workRoot.transform, false);
            var filter = model.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;
            var renderer = model.AddComponent<MeshRenderer>();
            var shader = Shader.Find("HDRP/Lit") ?? Shader.Find("Standard") ?? Shader.Find("Unlit/Color");
            renderer.sharedMaterial = new Material(shader);
            var bounds = mesh.bounds;
            workCenter = bounds.center;
            workDistance = Mathf.Max(2f, bounds.extents.magnitude * 3f);
            status = "Imported " + mesh.vertexCount + " vertices, " + mesh.triangles.Length / 3 + " triangles. Geometry/UV/normals only in this first slice.";
            PlayerPrefs.SetString("worldbuilder.lastObj", modelPath);
            PlayerPrefs.Save();
        }
        catch (Exception e) { status = "Import error: " + e.Message; Debug.LogException(e); }
    }

    static Mesh LoadObj(string path)
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
            string line = raw.Trim();
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
                    var key = tokens[i];
                    if (!unique.TryGetValue(key, out var vertexIndex))
                    {
                        var parts = key.Split('/');
                        int posId = Index(parts[0], positions.Count);
                        if (posId < 0 || posId >= positions.Count) throw new FormatException("OBJ face references nonexistent vertex");
                        vertexIndex = outPos.Count;
                        unique[key] = vertexIndex;
                        outPos.Add(positions[posId]);
                        outUV.Add(parts.Length > 1 && parts[1].Length > 0 ? uvs[Index(parts[1], uvs.Count)] : Vector2.zero);
                        outNormal.Add(parts.Length > 2 && parts[2].Length > 0 ? normals[Index(parts[2], normals.Count)] : Vector3.zero);
                    }
                    corners.Add(vertexIndex);
                }
                for (int i = 1; i + 1 < corners.Count; i++)
                {
                    triangles.Add(corners[0]); triangles.Add(corners[i]); triangles.Add(corners[i + 1]);
                }
            }
        }
        var mesh = new Mesh { name = Path.GetFileNameWithoutExtension(path) };
        mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
        mesh.SetVertices(outPos);
        mesh.SetUVs(0, outUV);
        mesh.SetTriangles(triangles, 0);
        bool hasNormals = outNormal.Exists(n => n.sqrMagnitude > 0.00001f);
        if (hasNormals) mesh.SetNormals(outNormal); else mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static float Parse(string s) => float.Parse(s, NumberStyles.Float, C);
    static int Index(string s, int count) { var i = int.Parse(s, C); return i > 0 ? i - 1 : count + i; }

    void LocateInstallations()
    {
        string[] defaults = {
            @"C:\Program Files (x86)\Steam\steamapps\common\ForzaHorizon5",
            @"C:\Program Files\EA Games\The Sims 4"
        };
        for (int i = 0; i < gamePaths.Length; i++)
            if (string.IsNullOrWhiteSpace(gamePaths[i]) && Directory.Exists(defaults[i])) gamePaths[i] = defaults[i];
        installationStatus = "Forza: " + (Directory.Exists(gamePaths[0]) ? "folder detected" : "choose folder")
            + " | Sims 4: " + (Directory.Exists(gamePaths[1]) ? "folder detected" : "choose folder");
    }

    void ChooseGameFolder()
    {
#if UNITY_EDITOR
        string path = UnityEditor.EditorUtility.OpenFolderPanel("Locate " + gameNames[selectedGame], gamePaths[selectedGame], "");
        if (string.IsNullOrWhiteSpace(path)) return;
        gamePaths[selectedGame] = path;
        PlayerPrefs.SetString("worldbuilder.gamePath." + selectedGame, path);
        PlayerPrefs.Save();
        LocateInstallations();
        ScanLooseModels();
#else
        status = "Folder picker is currently Editor-only; native Windows picker is planned.";
#endif
    }

    void ScanLooseModels()
    {
        catalog.Clear();
        string path = gamePaths[selectedGame];
        if (!Directory.Exists(path)) { status = "Select an existing game folder first."; return; }
        try
        {
            // Only loose, readable OBJ files. No proprietary package parsing or extraction.
            // Bound the scan to avoid blocking the Editor on huge installations.
            var pending = new Queue<string>();
            pending.Enqueue(path);
            int folders = 0;
            while (pending.Count > 0 && folders < 250 && catalog.Count < 250)
            {
                var folder = pending.Dequeue();
                folders++;
                try
                {
                    foreach (var file in Directory.EnumerateFiles(folder, "*.obj"))
                    {
                        catalog.Add(file);
                        if (catalog.Count >= 250) break;
                    }
                    foreach (var child in Directory.EnumerateDirectories(folder))
                        if (pending.Count < 1000) pending.Enqueue(child);
                }
                catch (UnauthorizedAccessException) { }
                catch (IOException) { }
            }
            status = "Indexed " + catalog.Count + " loose OBJ models in " + folders +
                " folders. Proprietary game archives are not supported.";
        }
        catch (Exception e) { status = "Scan failed: " + e.Message; }
    }

    void DrawGameBrowser(float w, float h)
    {
        float width = Mathf.Min(630f, w - 40f);
        var panel = new Rect((w - width) / 2f, 52f, width, Mathf.Min(h - 110f, 570f));
        GUI.Box(panel, "");
        float x = panel.x + 16f, y = panel.y + 12f, inner = panel.width - 32f;
        GUI.Label(new Rect(x, y, inner - 85f, 24f), "GAME ASSET BROWSER  /  read-only discovery");
        if (GUI.Button(new Rect(panel.xMax - 85f, y, 65f, 25f), "Close")) showBrowser = false;
        y += 36f;
        if (GUI.Button(new Rect(x, y, inner / 2f - 5f, 30f), "Forza Horizon 5"))
            { selectedGame = 0; catalog.Clear(); }
        if (GUI.Button(new Rect(x + inner / 2f + 5f, y, inner / 2f - 5f, 30f), "The Sims 4"))
            { selectedGame = 1; catalog.Clear(); }
        y += 38f;
        GUI.Label(new Rect(x, y, inner, 36f), gameNames[selectedGame] + ": " +
            (Directory.Exists(gamePaths[selectedGame]) ? gamePaths[selectedGame] : "No folder selected"));
        y += 40f;
        if (GUI.Button(new Rect(x, y, 155f, 30f), "Choose Folder")) ChooseGameFolder();
        if (GUI.Button(new Rect(x + 165f, y, 160f, 30f), "Scan Loose OBJ")) ScanLooseModels();
        y += 38f;
        GUI.Label(new Rect(x, y, inner, 22f), "Found " + catalog.Count + " compatible loose .obj files (max 250)");
        y += 26f;
        var scrollRect = new Rect(x, y, inner, Mathf.Max(65f, panel.yMax - y - 48f));
        var contentRect = new Rect(0, 0, inner - 25f, Mathf.Max(scrollRect.height, catalog.Count * 32f));
        catalogScroll = GUI.BeginScrollView(scrollRect, catalogScroll, contentRect);
        for (int i = 0; i < catalog.Count; i++)
        {
            string file = catalog[i];
            if (GUI.Button(new Rect(0, i * 32f, inner - 32f, 28f), Path.GetFileName(file)))
            {
                modelPath = file;
                ImportExisting();
                showBrowser = false;
            }
        }
        GUI.EndScrollView();
        GUI.Label(new Rect(x, panel.yMax - 34f, inner, 28f), "No decoding, extraction, or redistribution of proprietary game assets.");
    }

    void OnDestroy()
    {
        if (referenceTexture != null) { referenceTexture.Release(); Destroy(referenceTexture); }
        if (workTexture != null) { workTexture.Release(); Destroy(workTexture); }
    }
}
