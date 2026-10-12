using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UIElements;

public sealed class WorldBuilderRuntime : MonoBehaviour
{
    Transform world, reference;
    Camera workCamera, referenceCamera, displayCamera;
    RenderTexture workTexture, referenceTexture;
    GameObject sun, selected;
    UIDocument ui;
    PanelSettings panel;
    VisualElement root, inspector, modal;
    ScrollView hierarchy;
    Image workImage, referenceImage;
    Label statusLabel, titleLabel;
    Button undoButton, redoButton;
    readonly WorkspaceHistory history = new WorkspaceHistory();
    string projectPath = "", title = "Untitled world", savedState = "";
    int theme;
    Vector2 workAngles = new Vector2(25, -25), referenceAngles = new Vector2(25, -25);
    Vector3 workCenter, referenceCenter;
    float workDistance = 12, referenceDistance = 8;
    bool quitting;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Bootstrap()
    {
        if (FindFirstObjectByType<WorldBuilderRuntime>() == null)
            new GameObject("World Builder Runtime").AddComponent<WorldBuilderRuntime>();
    }
    void Start()
    {
        world = new GameObject("World Builder Editable Scene").transform;
        reference = new GameObject("World Builder Reference").transform;
        workCamera = CameraFor("Editable Camera", 31, out workTexture);
        referenceCamera = CameraFor("Reference Camera", 30, out referenceTexture);
        displayCamera = new GameObject("Workspace Display").AddComponent<Camera>();
        displayCamera.cullingMask = 0;
        displayCamera.clearFlags = CameraClearFlags.SolidColor;
        sun = new GameObject("Workspace Sun");
        var light = sun.AddComponent<Light>(); light.type = LightType.Directional; light.intensity = 1.4f;
        sun.transform.rotation = Quaternion.Euler(45, -35, 0);
        BuildUI();
        AddPrimitive(PrimitiveType.Cube, "Cube", false);
        history.Reset(State()); savedState = State(); Refresh();
        Application.wantsToQuit += WantsToQuit;
    }
    Camera CameraFor(string name, int layer, out RenderTexture texture)
    {
        var camera = new GameObject(name).AddComponent<Camera>();
        camera.cullingMask = 1 << layer; camera.fieldOfView = 48;
        camera.nearClipPlane = 0.02f; camera.farClipPlane = 10000;
        camera.backgroundColor = new Color(0.065f, 0.08f, 0.105f);
        camera.clearFlags = CameraClearFlags.SolidColor;
        texture = new RenderTexture(960, 600, 24); texture.Create(); camera.targetTexture = texture;
        return camera;
    }
    void Update()
    {
        Position(workCamera, workAngles, workCenter, workDistance);
        Position(referenceCamera, referenceAngles, referenceCenter, referenceDistance);
    }
    static void Position(Camera camera, Vector2 angles, Vector3 center, float distance)
    {
        var orbit = Quaternion.Euler(Mathf.Clamp(angles.x, -89, 89), angles.y, 0);
        camera.transform.position = center + orbit * Vector3.back * distance;
        camera.transform.LookAt(center);
    }
    void BuildUI()
    {
        panel = ScriptableObject.CreateInstance<PanelSettings>();
        panel.scaleMode = PanelScaleMode.ScaleWithScreenSize;
        panel.referenceResolution = new Vector2Int(1440, 900);
        ui = gameObject.AddComponent<UIDocument>(); ui.panelSettings = panel;
        root = ui.rootVisualElement; root.style.flexGrow = 1;
        var sheet = Resources.Load<StyleSheet>("Workspace"); if (sheet != null) root.styleSheets.Add(sheet);
        theme = PlayerPrefs.GetInt("worldbuilder.theme", 0); ApplyTheme();
        var top = Row(root, "topbar"); Label(top, "WORLD BUILDER", "brand");
        titleLabel = Label(top, title, "project-title");
        Button(top, "New", () => ConfirmDiscard(NewProject));
        Button(top, "Open", () => ConfirmDiscard(OpenProject));
        Button(top, "Save", () => Save(false)); Button(top, "Save As", () => Save(true));
        Button(top, "Import OBJ", Import); Button(top, "Export OBJ", Export);
        undoButton = Button(top, "Undo", Undo); redoButton = Button(top, "Redo", Redo);
        Button(top, "Theme", () => { theme = (theme + 1) % 3; ApplyTheme(); PlayerPrefs.SetInt("worldbuilder.theme", theme); PlayerPrefs.Save(); });
        var body = Row(root, "body");
        var left = new VisualElement(); left.AddToClassList("sidebar"); body.Add(left);
        Label(left, "SCENE", "section");
        var primitives = Row(left);
        Button(primitives, "+ Cube", () => AddPrimitive(PrimitiveType.Cube, "Cube"));
        Button(primitives, "+ Plane", () => AddPrimitive(PrimitiveType.Plane, "Plane"));
        var more = Row(left);
        Button(more, "+ Sphere", () => AddPrimitive(PrimitiveType.Sphere, "Sphere"));
        Button(more, "+ Cylinder", () => AddPrimitive(PrimitiveType.Cylinder, "Cylinder"));
        Button(left, "Game Asset Browser", GameBrowser);
        hierarchy = new ScrollView(); hierarchy.style.flexGrow = 1; left.Add(hierarchy);
        var center = new VisualElement(); center.AddToClassList("center"); body.Add(center);
        var tools = Row(center, "toolbar");
        Button(tools, "Frame Selected", FrameSelected);
        Button(tools, "Frame All", FrameAll);
        Button(tools, "Duplicate", Duplicate); Button(tools, "Delete", Delete);
        Button(tools, "Perspective / Ortho", () => { workCamera.orthographic = !workCamera.orthographic; workCamera.orthographicSize = workDistance * 0.4f; });
        var views = Row(center, "views");
        referenceImage = View(views, "REFERENCE — read only", referenceTexture, false);
        workImage = View(views, "EDITABLE SCENE", workTexture, true);
        Label(center, "Left click: select   •   Right drag: orbit   •   Middle drag: pan   •   Wheel: zoom", "hint");
        inspector = new ScrollView(); inspector.AddToClassList("inspector"); body.Add(inspector);
        statusLabel = Label(root, "Ready. Create objects or import a Blender OBJ.", "status");
        root.RegisterCallback<KeyDownEvent>(e => {
            if (modal != null || e.target is TextField || e.target is FloatField || e.target is TextElement) return;
            if (e.ctrlKey && e.keyCode == KeyCode.S) { Save(false); e.StopPropagation(); }
            if (e.ctrlKey && e.keyCode == KeyCode.Z) { Undo(); e.StopPropagation(); }
            if (e.ctrlKey && e.keyCode == KeyCode.Y) { Redo(); e.StopPropagation(); }
            if (e.keyCode == KeyCode.F) FrameSelected();
        });
    }
    Image View(VisualElement parent, string titleText, RenderTexture texture, bool editable)
    {
        var box = new VisualElement(); box.AddToClassList("view"); parent.Add(box); Label(box, titleText, "section");
        var image = new Image { image = texture, scaleMode = ScaleMode.StretchToFill, focusable = true };
        image.style.flexGrow = 1; image.style.minHeight = 100; box.Add(image);
        int drag = -1; Vector2 previous = Vector2.zero;
        image.RegisterCallback<PointerDownEvent>(e => {
            if (modal != null) return;
            image.Focus();
            if (e.button == 0 && editable) Pick(e.localPosition);
            if (e.button == 1 || e.button == 2) { drag = e.button; previous = e.position; image.CapturePointer(e.pointerId); }
            e.StopPropagation();
        });
        image.RegisterCallback<PointerMoveEvent>(e => {
            if (drag < 0 || modal != null) return;
            Vector2 point = e.position, delta = point - previous; previous = point;
            if (drag == 1) {
                if (editable) workAngles += new Vector2(delta.y, delta.x) * 0.25f;
                else referenceAngles += new Vector2(delta.y, delta.x) * 0.25f;
            } else {
                var cam = editable ? workCamera : referenceCamera;
                Vector3 movement = (-cam.transform.right * delta.x + cam.transform.up * delta.y) * (editable ? workDistance : referenceDistance) * 0.002f;
                if (editable) workCenter += movement; else referenceCenter += movement;
            }
            workAngles.x = Mathf.Clamp(workAngles.x, -89, 89); referenceAngles.x = Mathf.Clamp(referenceAngles.x, -89, 89);
        });
        image.RegisterCallback<PointerUpEvent>(e => { drag = -1; image.ReleasePointer(e.pointerId); });
        image.RegisterCallback<PointerCaptureOutEvent>(e => drag = -1);
        image.RegisterCallback<WheelEvent>(e => {
            if (modal != null) return;
            if (editable) { workDistance = Mathf.Clamp(workDistance * Mathf.Exp(e.delta.y * 0.08f), 0.25f, 10000); workCamera.orthographicSize = workDistance * 0.4f; }
            else referenceDistance = Mathf.Clamp(referenceDistance * Mathf.Exp(e.delta.y * 0.08f), 0.25f, 10000);
            e.StopPropagation();
        });
        image.RegisterCallback<GeometryChangedEvent>(e => {
            if (e.newRect.width < 2 || e.newRect.height < 2) return;
            // Bounded render resolution adapts to aspect ratio and resizing.
            int width = Mathf.Clamp(Mathf.RoundToInt(e.newRect.width), 128, 1920);
            int height = Mathf.Clamp(Mathf.RoundToInt(e.newRect.height), 128, 1080);
            texture.Release(); texture.width = width; texture.height = height; texture.Create();
            (editable ? workCamera : referenceCamera).aspect = e.newRect.width / e.newRect.height;
        });
        return image;
    }
    void Pick(Vector2 point)
    {
        var size = workImage.contentRect;
        Physics.SyncTransforms();
        var ray = workCamera.ViewportPointToRay(new Vector3(point.x / size.width, 1 - point.y / size.height, 0));
        selected = Physics.Raycast(ray, out var hit, 10000, 1 << 31) ? hit.collider.gameObject : null;
        Refresh();
    }
    Material Material(Color color)
    {
        var shader = Shader.Find("HDRP/Lit") ?? Shader.Find("Standard") ?? Shader.Find("Unlit/Color");
        if (shader == null) throw new InvalidOperationException("No compatible material shader is available.");
        var material = new Material(shader);
        if (material.HasProperty("_BaseColor")) material.SetColor("_BaseColor", color); else material.color = color;
        return material;
    }
    GameObject Model(WorkspaceProject data, Transform parent, int layer)
    {
        Mesh mesh = data.CreateMesh();
        var go = new GameObject(data.name); go.transform.SetParent(parent, false); go.layer = layer;
        var identity = go.AddComponent<WorkspaceIdentity>(); identity.ownedMesh = mesh;
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        identity.ownedMaterial = Material(data.color);
        go.AddComponent<MeshRenderer>().sharedMaterial = identity.ownedMaterial;
        go.AddComponent<MeshCollider>().sharedMesh = mesh;
        identity.id = data.id ?? Guid.NewGuid().ToString("N"); identity.source = data.source;
        go.transform.localPosition = data.position; go.transform.localEulerAngles = data.rotation; go.transform.localScale = data.scale;
        return go;
    }
    void AddPrimitive(PrimitiveType type, string name, bool record = true)
    {
        var go = GameObject.CreatePrimitive(type); go.name = name; go.layer = 31; go.transform.SetParent(world, false);
        go.transform.position = type == PrimitiveType.Plane ? Vector3.zero : new Vector3(0, 0.5f, 0);
        var identity = go.AddComponent<WorkspaceIdentity>(); identity.id = Guid.NewGuid().ToString("N"); identity.source = "";
        // Clone generated mesh so this application's ownership is explicit.
        var filter = go.GetComponent<MeshFilter>(); filter.sharedMesh = Instantiate(filter.sharedMesh);
        identity.ownedMesh = filter.sharedMesh;
        identity.ownedMaterial = Material(new Color(0.62f, 0.72f, 0.8f));
        go.GetComponent<Renderer>().sharedMaterial = identity.ownedMaterial;
        selected = go; if (record) Changed();
    }
    void Import()
    {
        Try(() => {
            string path = WorkspaceFiles.Pick(false, "Import OBJ geometry", "obj"); if (string.IsNullOrEmpty(path)) return;
            if (new FileInfo(path).Length > 32 * 1024 * 1024) throw new IOException("OBJ exceeds the 32 MB import limit.");
            var mesh = WorldBuilderObj.Load(path);
            var data = new WorkspaceProject { name = Path.GetFileNameWithoutExtension(path), source = path,
                id = Guid.NewGuid().ToString("N"), vertices = mesh.vertices, normals = mesh.normals, uv = mesh.uv, triangles = mesh.triangles };
            Destroy(mesh);
            selected = Model(data, world, 31); Preview(data); FrameSelected(); Changed();
            Status("Imported geometry, UVs and normals. Source MTL/textures are not imported yet.");
        });
    }
    void Preview(WorkspaceProject data)
    {
        Clear(reference); var model = Model(data, reference, 30);
        model.transform.localPosition = Vector3.zero; model.transform.localRotation = Quaternion.identity; model.transform.localScale = Vector3.one;
        var bounds = model.GetComponent<Renderer>().bounds;
        referenceCenter = bounds.center; referenceDistance = Mathf.Max(2, bounds.extents.magnitude * 3);
    }
    void Duplicate()
    {
        if (selected == null) return;
        var data = WorkspaceProject.Capture(selected, selected.GetComponent<WorkspaceIdentity>().source);
        data.id = Guid.NewGuid().ToString("N"); data.name += " copy"; data.position += Vector3.right;
        selected = Model(data, world, 31); Changed();
    }
    void Delete()
    {
        if (selected == null) return;
        selected.SetActive(false); Destroy(selected); selected = null; Changed();
    }
    void FrameSelected()
    {
        if (selected == null) { FrameAll(); return; }
        var bounds = selected.GetComponent<Renderer>().bounds;
        workCenter = bounds.center; workDistance = Mathf.Max(2, bounds.extents.magnitude * 3);
        workCamera.orthographicSize = workDistance * 0.4f;
    }
    void FrameAll()
    {
        bool found = false; var bounds = new Bounds();
        foreach (Transform child in world) if (child.gameObject.activeSelf) {
            var b = child.GetComponent<Renderer>().bounds; if (!found) bounds = b; else bounds.Encapsulate(b); found = true;
        }
        workCenter = found ? bounds.center : Vector3.zero; workDistance = found ? Mathf.Max(2, bounds.extents.magnitude * 3) : 12;
        workCamera.orthographicSize = workDistance * 0.4f;
    }
    string State() => JsonUtility.ToJson(WorkspaceDocument.Capture(world, title));
    void Changed() { history.Record(State()); Refresh(); }
    void Undo() { string state = history.Undo(); if (state != null) Restore(JsonUtility.FromJson<WorkspaceDocument>(state)); }
    void Redo() { string state = history.Redo(); if (state != null) Restore(JsonUtility.FromJson<WorkspaceDocument>(state)); }
    void Restore(WorkspaceDocument document)
    {
        // Construct everything in a staging root first: invalid files leave the scene intact.
        var stage = new GameObject("Project staging").transform;
        try {
            foreach (var data in document.objects) Model(data, stage, 31);
        } catch { Clear(stage); Destroy(stage.gameObject); throw; }
        Clear(world);
        while (stage.childCount > 0) stage.GetChild(0).SetParent(world, false);
        Destroy(stage.gameObject); title = document.title; selected = null; Refresh();
    }
    void NewProject()
    {
        Clear(world); Clear(reference); selected = null; projectPath = ""; title = "Untitled world";
        history.Reset(State()); savedState = State(); Refresh(); Status("New empty world. Add a plane and start placing objects.");
    }
    void OpenProject()
    {
        Try(() => {
            string path = WorkspaceFiles.Pick(false, "Open World Builder project", "wbworld"); if (string.IsNullOrEmpty(path)) return;
            WorkspaceDocument document;
            if (Path.GetExtension(path).Equals(".wbasset", StringComparison.OrdinalIgnoreCase))
                document = new WorkspaceDocument { title = Path.GetFileNameWithoutExtension(path), objects = new List<WorkspaceProject> { WorkspaceProject.Open(path) } };
            else document = WorkspaceDocument.Open(path);
            Restore(document); Clear(reference); projectPath = Path.GetExtension(path) == ".wbasset" ? "" : path;
            history.Reset(State()); savedState = State(); FrameAll(); Refresh(); Status("Project opened.");
        });
    }
    void Save(bool saveAs)
    {
        Try(() => {
            string path = saveAs || string.IsNullOrEmpty(projectPath) ? WorkspaceFiles.Pick(true, "Save world project", "wbworld") : projectPath;
            if (string.IsNullOrEmpty(path)) return;
            var document = WorkspaceDocument.Capture(world, Path.GetFileNameWithoutExtension(path)); document.Save(path);
            projectPath = path; title = document.title; history.Record(State()); savedState = State(); Refresh(); Status("Saved " + Path.GetFileName(path));
        });
    }
    void Export()
    {
        Try(() => {
            string path = WorkspaceFiles.Pick(true, "Export scene OBJ + MTL", "obj"); if (string.IsNullOrEmpty(path)) return;
            foreach (Transform child in world) {
                var source = child.GetComponent<WorkspaceIdentity>()?.source;
                if (!string.IsNullOrEmpty(source) && string.Equals(Path.GetFullPath(source), Path.GetFullPath(path), StringComparison.OrdinalIgnoreCase))
                    throw new IOException("Choose a different filename to preserve the imported source model.");
            }
            WorkspaceObjExport.Export(world, path); Status("Exported OBJ + MTL base colors. Import both into Blender.");
        });
    }
    void Refresh()
    {
        if (hierarchy == null) return;
        titleLabel.text = title + (State() != savedState ? " • unsaved" : "");
        undoButton.SetEnabled(history.CanUndo); redoButton.SetEnabled(history.CanRedo);
        hierarchy.Clear();
        foreach (Transform child in world) if (child.gameObject.activeSelf) {
            var go = child.gameObject; var button = Button(hierarchy, go.name, () => { selected = go; Refresh(); });
            if (go == selected) button.AddToClassList("selected");
        }
        inspector.Clear(); Label(inspector, "PROPERTIES", "section");
        if (selected == null) { Label(inspector, "Select an object in the scene or hierarchy.", "hint"); return; }
        var name = new TextField("Name") { value = selected.name, isDelayed = true }; inspector.Add(name);
        name.RegisterValueChangedCallback(e => { if (selected != null && !string.IsNullOrWhiteSpace(e.newValue)) { selected.name = e.newValue; Changed(); } });
        VectorFields("Position", selected.transform.localPosition, v => selected.transform.localPosition = v);
        VectorFields("Rotation", selected.transform.localEulerAngles, v => selected.transform.localEulerAngles = v);
        VectorFields("Scale", selected.transform.localScale, v => { if (Mathf.Abs(v.x * v.y * v.z) < 0.000001f) throw new ArgumentException("Scale must be non-zero."); selected.transform.localScale = v; });
        Label(inspector, "BASE COLOR", "section");
        var colors = Row(inspector);
        foreach (var color in new[] { Color.gray, new Color(0.15f, 0.45f, 0.25f), new Color(0.7f, 0.55f, 0.33f), new Color(0.2f, 0.45f, 0.8f) }) {
            var c = color; var b = Button(colors, "●", () => {
                var material = selected.GetComponent<Renderer>().sharedMaterial;
                if (material.HasProperty("_BaseColor")) material.SetColor("_BaseColor", c); else material.color = c;
                Changed();
            }); b.style.color = c;
        }
        var mesh = selected.GetComponent<MeshFilter>().sharedMesh;
        Label(inspector, mesh.vertexCount + " vertices\n" + mesh.triangles.Length / 3 + " triangles", "hint");
        Label(inspector, "Numeric transforms are editable. Visual gizmos and mesh editing are next.", "hint");
    }
    void VectorFields(string label, Vector3 value, Action<Vector3> apply)
    {
        Label(inspector, label.ToUpperInvariant(), "section");
        for (int i = 0; i < 3; i++) {
            int axis = i; var field = new FloatField(new[] { "X", "Y", "Z" }[i]) { value = value[i], isDelayed = true }; inspector.Add(field);
            field.RegisterValueChangedCallback(e => Try(() => {
                if (float.IsNaN(e.newValue) || float.IsInfinity(e.newValue)) throw new ArgumentException("Enter a finite number.");
                var changed = value; changed[axis] = e.newValue; apply(changed); Changed();
            }));
        }
    }
    void ConfirmDiscard(Action action)
    {
        if (State() == savedState) { action(); return; }
        Dialog("Unsaved changes", "Save your world before replacing it?", box => {
            Button(box, "Save", () => { Save(false); if (State() == savedState) { CloseDialog(); action(); } });
            Button(box, "Discard changes", () => { CloseDialog(); action(); });
            Button(box, "Cancel", CloseDialog);
        });
    }
    bool WantsToQuit()
    {
        if (quitting || State() == savedState) return true;
        ConfirmDiscard(() => { quitting = true; Application.Quit(); }); return false;
    }
    void Dialog(string titleText, string text, Action<VisualElement> actions)
    {
        CloseDialog(); modal = new VisualElement(); modal.AddToClassList("modal"); root.Add(modal);
        var box = new VisualElement(); box.AddToClassList("dialog"); modal.Add(box);
        Label(box, titleText, "section"); Label(box, text, "hint"); actions(box);
    }
    void CloseDialog() { if (modal != null) modal.RemoveFromHierarchy(); modal = null; }
    void GameBrowser()
    {
        Dialog("Game Asset Browser", "Supported loose OBJ models can be previewed. Sims .package and Forza resources require external conversion; no proprietary mesh decoder is implemented.", box => {
            foreach (var game in new[] { "Forza Horizon 5", "The Sims 4" }) {
                int index = game == "The Sims 4" ? 1 : 0;
                var field = new TextField(game) { value = PlayerPrefs.GetString("worldbuilder.gamePath." + index, ""), isDelayed = true }; box.Add(field);
                field.RegisterValueChangedCallback(e => { PlayerPrefs.SetString("worldbuilder.gamePath." + index, e.newValue); PlayerPrefs.Save(); });
#if UNITY_EDITOR
                Button(box, "Choose " + game + " folder", () => {
                    string folder = UnityEditor.EditorUtility.OpenFolderPanel("Choose installation", field.value, "");
                    if (string.IsNullOrEmpty(folder)) return;
                    field.value = folder;
                });
#endif
                Button(box, "Scan " + game, () => ScanCatalog(field.value, box));
            }
            Button(box, "Import authorized OBJ export", () => { CloseDialog(); Import(); });
            Button(box, "Close", CloseDialog);
        });
    }
    async void ScanCatalog(string path, VisualElement box)
    {
        if (!Directory.Exists(path)) { Status("Select an existing installation folder."); return; }
        Status("Scanning compatible files in the background…");
        try {
            var files = await Task.Run(() => {
                var result = new List<string>(); var pending = new Queue<string>(); pending.Enqueue(path); int count = 0;
                while (pending.Count > 0 && count++ < 1000 && result.Count < 250) {
                    var folder = pending.Dequeue();
                    try {
                        foreach (var file in Directory.EnumerateFiles(folder)) {
                            string ext = Path.GetExtension(file).ToLowerInvariant();
                            if (ext == ".obj" || ext == ".package") result.Add(file);
                            if (result.Count >= 250) break;
                        }
                        foreach (var child in Directory.EnumerateDirectories(folder))
                            if (pending.Count < 1000 && (File.GetAttributes(child) & FileAttributes.ReparsePoint) == 0) pending.Enqueue(child);
                    } catch (UnauthorizedAccessException) { } catch (IOException) { }
                }
                return result;
            });
            if (this == null || modal == null || box.panel == null) return;
            var old = box.Q<ScrollView>("catalog"); old?.RemoveFromHierarchy();
            var list = new ScrollView { name = "catalog" }; list.style.height = 220; box.Add(list);
            foreach (var file in files) {
                string selectedFile = file;
                if (Path.GetExtension(file).Equals(".obj", StringComparison.OrdinalIgnoreCase))
                    Button(list, "Preview OBJ: " + Path.GetFileName(file), () => Try(() => {
                        if (new FileInfo(selectedFile).Length > 32 * 1024 * 1024) throw new IOException("OBJ exceeds import limit.");
                        var mesh = WorldBuilderObj.Load(selectedFile);
                        var data = new WorkspaceProject { name = Path.GetFileNameWithoutExtension(selectedFile), vertices = mesh.vertices, normals = mesh.normals, uv = mesh.uv, triangles = mesh.triangles };
                        Destroy(mesh); Preview(data);
                        CloseDialog(); Status("Reference preview only. Use Import OBJ to add it to the editable scene.");
                    }));
                else Label(list, Path.GetFileName(file) + " — package mesh preview unavailable", "hint");
            }
            Status("Scan found " + files.Count + " files (limit 250). Packages are listed, not rendered.");
        } catch (Exception e) { if (this != null) Status("Scan failed: " + e.Message); }
    }
    void ApplyTheme()
    {
        root.RemoveFromClassList("dark"); root.RemoveFromClassList("light"); root.RemoveFromClassList("contrast");
        root.AddToClassList(new[] { "dark", "light", "contrast" }[Mathf.Clamp(theme, 0, 2)]);
    }
    static Label Label(VisualElement parent, string text, string className = null)
    {
        var label = new Label(text); if (className != null) label.AddToClassList(className); parent.Add(label); return label;
    }
    static VisualElement Row(VisualElement parent, string className = null)
    {
        var row = new VisualElement(); row.style.flexDirection = FlexDirection.Row;
        if (className != null) row.AddToClassList(className); parent.Add(row); return row;
    }
    Button Button(VisualElement parent, string text, Action action)
    {
        var button = new Button(() => Try(action)) { text = text }; parent.Add(button); return button;
    }
    void Try(Action action) { try { action(); } catch (Exception e) { Status(e.Message); Debug.LogException(e); Refresh(); } }
    void Status(string text) { if (statusLabel != null) statusLabel.text = text; }
    static void Clear(Transform parent)
    {
        while (parent.childCount > 0) { var child = parent.GetChild(0); child.gameObject.SetActive(false); child.SetParent(null); Destroy(child.gameObject); }
    }
    void OnDestroy()
    {
        Application.wantsToQuit -= WantsToQuit;
        if (world != null) Destroy(world.gameObject); if (reference != null) Destroy(reference.gameObject);
        if (sun != null) Destroy(sun);
        if (workCamera != null) Destroy(workCamera.gameObject); if (referenceCamera != null) Destroy(referenceCamera.gameObject);
        if (displayCamera != null) Destroy(displayCamera.gameObject);
        if (workTexture != null) { workTexture.Release(); Destroy(workTexture); }
        if (referenceTexture != null) { referenceTexture.Release(); Destroy(referenceTexture); }
        if (ui != null) Destroy(ui); if (panel != null) Destroy(panel);
    }
}
