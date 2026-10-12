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

    Camera displayCamera;
    GameObject workspaceLight;
    int capturedView = -1;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Bootstrap()
    {
        if (FindFirstObjectByType<WorldBuilderRuntime>() == null)
            new GameObject("World Builder Runtime").AddComponent<WorldBuilderRuntime>();
    }

    void Start()
    {
        workspaceLight = new GameObject("Workspace Sun");
        var sun = workspaceLight.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = 1.4f;
        sun.transform.rotation = Quaternion.Euler(45, -35, 0);
        referenceRoot = new GameObject("Reference Model");
        workRoot = new GameObject("Editable Model");
        referenceCamera = CreateCamera("Reference Camera", out referenceTexture);
        workCamera = CreateCamera("Work Camera", out workTexture);
        MakePrimitive(referenceRoot.transform, PrimitiveType.Cube, new Vector3(0, 0.5f, 0));
        MakePrimitive(workRoot.transform, PrimitiveType.Cube, new Vector3(0, 0.5f, 0));
        for (int i = 0; i < gamePaths.Length; i++) gamePaths[i] = PlayerPrefs.GetString("worldbuilder.gamePath." + i, "");
        LocateInstallations();
        SetLayer(referenceRoot, 30);
        SetLayer(workRoot, 31);
        referenceCamera.cullingMask = 1 << 30;
        workCamera.cullingMask = 1 << 31;
        // Presentation only: no scene geometry is rendered a third time.
        displayCamera = new GameObject("Workspace Display").AddComponent<Camera>();
        displayCamera.cullingMask = 0;
        displayCamera.clearFlags = CameraClearFlags.SolidColor;
        displayCamera.backgroundColor = Color.black;
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
        var input = WorkspaceInput.Read();
        float scale = Mathf.Max(0.7f, Mathf.Min(Screen.width / 1280f, Screen.height / 720f));
        float w = Screen.width / scale, h = Screen.height / scale;
        float vw = (w - 66f) / 2f, vh = Mathf.Max(100, h - 232f);
        var pointer = new Vector2(input.Position.x, Screen.height - input.Position.y) / scale;
        activeView = showBrowser ? -1 : new Rect(22, 58, vw, vh).Contains(pointer) ? 0
            : new Rect(44 + vw, 58, vw, vh).Contains(pointer) ? 1 : -1;
        if (input.Pressed) capturedView = activeView;
        if (!input.Held || showBrowser) capturedView = -1;
        if (capturedView >= 0)
        {
            var delta = input.Delta * 0.2f;
            if (capturedView == 0) referenceAngles += new Vector2(-delta.y, delta.x);
            else workAngles += new Vector2(-delta.y, delta.x);
        }
        referenceAngles.x = Mathf.Clamp(referenceAngles.x, -89, 89);
        workAngles.x = Mathf.Clamp(workAngles.x, -89, 89);
        if (activeView == 0) referenceDistance = Mathf.Clamp(referenceDistance * Mathf.Exp(-input.Scroll * 0.12f), 0.25f, 10000f);
        if (activeView == 1) workDistance = Mathf.Clamp(workDistance * Mathf.Exp(-input.Scroll * 0.12f), 0.25f, 10000f);
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
        GUI.Label(new Rect(24, 12, 550, 28), "WORLD BUILDER  /  ASSET CREATOR  /  foundation");
        if (GUI.Button(new Rect(24, h - 24, 110, 22), "Save Project")) SaveProject();
        if (GUI.Button(new Rect(140, h - 24, 110, 22), "Open Project")) OpenProject();
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
        try
        {
            string selected = WorkspaceFiles.Pick(false, "Import Blender OBJ", "obj");
            if (string.IsNullOrEmpty(selected)) return;
            modelPath = selected;
        }
        catch (Exception e) { status = e.Message; return; }
        ImportExisting();
    }

    void ImportExisting()
    {
        if (string.IsNullOrWhiteSpace(modelPath) || !File.Exists(modelPath)) { status = "No valid OBJ path selected."; return; }
        try
        {
            var mesh = WorldBuilderObj.Load(modelPath);
            foreach (Transform child in workRoot.transform) Destroy(child.gameObject);
            var model = new GameObject(Path.GetFileNameWithoutExtension(modelPath));
            model.transform.SetParent(workRoot.transform, false);
            var filter = model.AddComponent<MeshFilter>();
            filter.sharedMesh = mesh;
            var renderer = model.AddComponent<MeshRenderer>();
            var shader = Shader.Find("HDRP/Lit") ?? Shader.Find("Standard") ?? Shader.Find("Unlit/Color");
            renderer.sharedMaterial = new Material(shader);
            SetLayer(model, 31);
            var bounds = mesh.bounds;
            workCenter = bounds.center;
            workDistance = Mathf.Max(2f, bounds.extents.magnitude * 3f);
            status = "Imported " + mesh.vertexCount + " vertices, " + mesh.triangles.Length / 3 + " triangles. Geometry/UV/normals only in this first slice.";
            PlayerPrefs.SetString("worldbuilder.lastObj", modelPath);
            PlayerPrefs.Save();
        }
        catch (Exception e) { status = "Import error: " + e.Message; Debug.LogException(e); }
    }

    void SaveProject()
    {
        try {
            if (workRoot.transform.childCount != 1) throw new InvalidOperationException("Save currently supports one editable mesh.");
            string path = WorkspaceFiles.Pick(true, "Save World Builder asset project", "wbasset");
            if (string.IsNullOrEmpty(path)) return;
            WorkspaceProject.Capture(workRoot.transform.GetChild(0).gameObject, modelPath).Save(path);
            status = "Project saved: " + path;
        } catch (Exception e) { status = "Save failed: " + e.Message; }
    }

    void OpenProject()
    {
        try {
            string path = WorkspaceFiles.Pick(false, "Open World Builder asset project", "wbasset");
            if (string.IsNullOrEmpty(path)) return;
            var project = WorkspaceProject.Open(path);
            var mesh = project.CreateMesh(); // validate before replacing the current scene
            var model = new GameObject(project.name);
            model.AddComponent<MeshFilter>().sharedMesh = mesh;
            model.AddComponent<MeshRenderer>().sharedMaterial = new Material(Shader.Find("HDRP/Lit") ?? Shader.Find("Standard"));
            model.transform.SetParent(workRoot.transform, false);
            model.transform.localPosition = project.position;
            model.transform.localEulerAngles = project.rotation;
            model.transform.localScale = project.scale;
            for (int i = workRoot.transform.childCount - 2; i >= 0; i--) Destroy(workRoot.transform.GetChild(i).gameObject);
            SetLayer(model, 31);
            modelPath = project.source;
            workCenter = model.transform.TransformPoint(mesh.bounds.center);
            workDistance = Mathf.Max(2, mesh.bounds.extents.magnitude * model.transform.lossyScale.magnitude * 3);
            status = "Project opened. Geometry is independent of the original source.";
        } catch (Exception e) { status = "Open failed: " + e.Message; }
    }

    static void SetLayer(GameObject root, int layer)
    {
        root.layer = layer;
        foreach (Transform child in root.transform) SetLayer(child.gameObject, layer);
    }

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
        if (workspaceLight != null) Destroy(workspaceLight);
        if (referenceRoot != null) Destroy(referenceRoot);
        if (workRoot != null) Destroy(workRoot);
        if (referenceCamera != null) Destroy(referenceCamera.gameObject);
        if (workCamera != null) Destroy(workCamera.gameObject);
        if (displayCamera != null) Destroy(displayCamera.gameObject);
        if (referenceTexture != null) { referenceTexture.Release(); Destroy(referenceTexture); }
        if (workTexture != null) { workTexture.Release(); Destroy(workTexture); }
    }
}
