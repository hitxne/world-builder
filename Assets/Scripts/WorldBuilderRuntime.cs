using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime : MonoBehaviour
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
    VisualElement sceneDock;
    ScrollView catalogDock;
    string hierarchyQuery="";
    bool sceneVisible=true, propertiesVisible=true, sceneDrawer, propertiesDrawer;
    float sceneWidth=220, propertiesWidth=255, catalogHeight=240;
    Button sceneToggle, propertiesToggle;
    readonly WorkspaceHistory history = new WorkspaceHistory();
    string projectPath = "", title = "Untitled world", savedState = "";
    int theme;
    Vector2 workAngles = new Vector2(25, -25), referenceAngles = new Vector2(25, -25);
    Vector3 workCenter, referenceCenter;
    float workDistance = 12, referenceDistance = 8;
    bool quitting;
    int previewGeneration;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Bootstrap()
    {
        if (FindAnyObjectByType<WorldBuilderRuntime>() == null)
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
        InitializeWorldTools();
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
        PositionCamera(workCamera, workAngles, workCenter, workDistance);
        PositionCamera(referenceCamera, referenceAngles, referenceCenter, referenceDistance);
        WorldUpdate();
    }
    static void PositionCamera(Camera camera, Vector2 angles, Vector3 center, float distance)
    {
        var orbit = Quaternion.Euler(Mathf.Clamp(angles.x, -89, 89), angles.y, 0);
        camera.transform.position = center + orbit * Vector3.back * distance;
        camera.transform.LookAt(center);
    }
    void BuildUI()
    {
        panel = ScriptableObject.CreateInstance<PanelSettings>();
        panel.scaleMode = PanelScaleMode.ConstantPixelSize;
        panel.referenceResolution = new Vector2Int(1440, 900);
        ui = gameObject.AddComponent<UIDocument>(); ui.panelSettings = panel;
        root = ui.rootVisualElement; root.style.flexGrow = 1;
        root.style.position = Position.Absolute; root.style.left = 0; root.style.right = 0; root.style.top = 0; root.style.bottom = 0;
        var sheet = Resources.Load<StyleSheet>("Workspace"); if (sheet != null) root.styleSheets.Add(sheet);
        theme = PlayerPrefs.GetInt("worldbuilder.theme", 0); ApplyTheme();
        var top = Row(root, "topbar"); Label(top, "WORLD BUILDER", "brand");
        titleLabel = Label(top, title, "project-title");
        Button(top, "Project", () => Dialog("Project", "Open, save or export your world.", box => {
            Button(box,"New",()=>{CloseDialog();ConfirmDiscard(NewProject);});
            Button(box,"Open",()=>{CloseDialog();ConfirmDiscard(OpenProject);});
            Button(box,"Save As",()=>{CloseDialog();Save(true);});
            Button(box,"Export OBJ",()=>{CloseDialog();Export();}); Button(box,"Close",CloseDialog);
        }));
        Button(top,"Save",()=>Save(false));
        undoButton = Button(top,"Undo",Undo); redoButton = Button(top,"Redo",Redo);
        Button(top,"Theme",()=>{theme=(theme+1)%3;ApplyTheme();PlayerPrefs.SetInt("worldbuilder.theme",theme);PlayerPrefs.Save();});
        Button(top,"Layout",OpenLayoutSettings);
        var navigation = Row(root,"mode-navigation"); navigation.name="mode-navigation";
        var body = Row(root, "body");
        var left = new VisualElement(); left.AddToClassList("sidebar"); body.Add(left); sceneDock=left;
        Label(left,"SCENE OBJECTS","section");
        var search=new TextField("Search"); left.Add(search);
        search.RegisterValueChangedCallback(e=>{hierarchyQuery=e.newValue??"";Refresh();});
        hierarchy = new ScrollView(); hierarchy.AddToClassList("dock-scroll"); left.Add(hierarchy);
        var center = new VisualElement(); center.AddToClassList("center"); body.Add(center);
        var tools = Row(center, "toolbar");
        sceneToggle=Button(tools,"Scene",()=>{if(root.contentRect.width<760){sceneDrawer=!sceneDrawer;propertiesDrawer=false;}else{sceneVisible=!sceneVisible;SaveLayout();}ApplyLayout();});
        propertiesToggle=Button(tools,"Properties",()=>{if(root.contentRect.width<1060){propertiesDrawer=!propertiesDrawer;sceneDrawer=false;}else{propertiesVisible=!propertiesVisible;SaveLayout();}ApplyLayout();});
        Button(tools, "Frame Selected", FrameSelected);
        Button(tools, "Frame All", FrameAll);
        Button(tools, "Duplicate", Duplicate); Button(tools, "Delete", Delete);
        Button(tools,"Camera",()=>Dialog("Camera views","Choose the editable viewport orientation.",box=>{
            Button(box,"Perspective",()=>{workCamera.orthographic=false;CloseDialog();});
            Button(box,"Top",()=>SetCameraView(new Vector2(89,0)));
            Button(box,"Front",()=>SetCameraView(new Vector2(0,0)));
            Button(box,"Side",()=>SetCameraView(new Vector2(0,90)));Button(box,"Close",CloseDialog);
        }));
        var views = Row(center, "views");
        referenceImage = View(views, "REFERENCE — read only", referenceTexture, false);
        workImage = View(views, "EDITABLE SCENE", workTexture, true);
        Label(center, "Left click: select   •   Right drag: orbit   •   Middle drag: pan   •   Wheel: zoom", "hint");
        inspector = new ScrollView(); inspector.AddToClassList("inspector"); body.Add(inspector);
        var catalog = new ScrollView(); catalog.name="construction-catalog"; catalog.AddToClassList("catalog"); root.Add(catalog); catalogDock=catalog;
        statusLabel = Label(root, "Ready. Create objects or import a Blender OBJ.", "status");
        sceneVisible=PlayerPrefs.GetInt("worldbuilder.layout.scene",1)!=0;
        propertiesVisible=PlayerPrefs.GetInt("worldbuilder.layout.properties",1)!=0;
        sceneWidth=PlayerPrefs.GetFloat("worldbuilder.layout.sceneWidth",220);
        propertiesWidth=PlayerPrefs.GetFloat("worldbuilder.layout.propertiesWidth",255);
        catalogHeight=PlayerPrefs.GetFloat("worldbuilder.layout.catalogHeight",240);
        root.RegisterCallback<GeometryChangedEvent>(e=>ApplyLayout());ApplyLayout();
        root.RegisterCallback<KeyDownEvent>(e => {
            if (modal != null || e.target is TextField || e.target is FloatField || e.target is TextElement) return;
            if (e.ctrlKey && e.keyCode == KeyCode.S) { Save(false); e.StopPropagation(); }
            if (e.ctrlKey && e.keyCode == KeyCode.Z) { EndObjectGesture(true); Undo(); e.StopPropagation(); }
            if (e.ctrlKey && e.keyCode == KeyCode.Y) { EndObjectGesture(true); Redo(); e.StopPropagation(); }
            if(!e.ctrlKey&&!e.altKey&&e.target==workImage) {
                if(e.keyCode==KeyCode.G)SetTool("move");if(e.keyCode==KeyCode.R)SetTool("rotate");if(e.keyCode==KeyCode.S)SetTool("scale");
            }
            if (e.keyCode == KeyCode.F) FrameSelected();
            if(e.keyCode==KeyCode.Return) FinishRoad();
            if(e.keyCode==KeyCode.Escape) CancelConstruction();
        });
    }
    void SetCameraView(Vector2 angles)
    {
        workAngles=angles;workCamera.orthographic=true;workCamera.orthographicSize=workDistance*0.4f;CloseDialog();
    }
    void SaveLayout()
    {
        PlayerPrefs.SetInt("worldbuilder.layout.scene",sceneVisible?1:0);PlayerPrefs.SetInt("worldbuilder.layout.properties",propertiesVisible?1:0);
        PlayerPrefs.SetFloat("worldbuilder.layout.sceneWidth",sceneWidth);PlayerPrefs.SetFloat("worldbuilder.layout.propertiesWidth",propertiesWidth);
        PlayerPrefs.SetFloat("worldbuilder.layout.catalogHeight",catalogHeight);PlayerPrefs.Save();
    }
    void ApplyLayout()
    {
        if(sceneDock==null||inspector==null||catalogDock==null)return;
        float width=root.contentRect.width,height=root.contentRect.height;
        bool narrowScene=width>0&&width<760,narrowProperties=width>0&&width<1060;
        bool showScene=narrowScene?sceneDrawer:sceneVisible,showProperties=narrowProperties?propertiesDrawer:propertiesVisible;
        sceneDock.style.position=narrowScene?Position.Absolute:Position.Relative;
        sceneDock.style.left=narrowScene?new StyleLength(0f):new StyleLength(StyleKeyword.Auto);
        sceneDock.style.top=narrowScene?new StyleLength(0f):new StyleLength(StyleKeyword.Auto);
        sceneDock.style.bottom=narrowScene?new StyleLength(0f):new StyleLength(StyleKeyword.Auto);
        inspector.style.position=narrowProperties?Position.Absolute:Position.Relative;
        inspector.style.right=narrowProperties?new StyleLength(0f):new StyleLength(StyleKeyword.Auto);
        inspector.style.top=narrowProperties?new StyleLength(0f):new StyleLength(StyleKeyword.Auto);
        inspector.style.bottom=narrowProperties?new StyleLength(0f):new StyleLength(StyleKeyword.Auto);
        if(narrowScene&&showScene&&sceneDock.parent.IndexOf(sceneDock)!=sceneDock.parent.childCount-1)sceneDock.BringToFront();
        else if(!narrowScene&&sceneDock.parent.IndexOf(sceneDock)!=0)sceneDock.parent.Insert(0,sceneDock);
        if(showProperties&&inspector.parent.IndexOf(inspector)!=inspector.parent.childCount-1)inspector.BringToFront();
        sceneDock.style.display=showScene?DisplayStyle.Flex:DisplayStyle.None;
        inspector.style.display=showProperties?DisplayStyle.Flex:DisplayStyle.None;
        sceneDock.style.width=Mathf.Clamp(sceneWidth,180,320);inspector.style.width=Mathf.Clamp(propertiesWidth,220,360);
        catalogDock.style.height=height>0?Mathf.Min(catalogHeight,Mathf.Max(120,height*0.32f)):catalogHeight;
        sceneToggle.EnableInClassList("selected",showScene);propertiesToggle.EnableInClassList("selected",showProperties);
        sceneToggle.SetEnabled(true);propertiesToggle.SetEnabled(true);
        sceneToggle.tooltip="Show or hide scene hierarchy. Opens a temporary drawer in narrow windows.";
        propertiesToggle.tooltip="Show or hide properties. Opens a temporary drawer in narrow windows.";
    }
    void OpenLayoutSettings()
    {
        Dialog("Workspace layout","Sizes and panel visibility are remembered between launches. Narrow windows temporarily collapse side panels.",box=>{
            Number(box,"Scene width",sceneWidth,180,320,v=>{sceneWidth=v;SaveLayout();ApplyLayout();});
            Number(box,"Properties width",propertiesWidth,220,360,v=>{propertiesWidth=v;SaveLayout();ApplyLayout();});
            Number(box,"Catalog height",catalogHeight,120,320,v=>{catalogHeight=v;SaveLayout();ApplyLayout();});
            Button(box,"Restore Default Layout",()=>{sceneVisible=propertiesVisible=true;sceneDrawer=propertiesDrawer=false;sceneWidth=220;propertiesWidth=255;catalogHeight=240;SaveLayout();ApplyLayout();CloseDialog();});
            Button(box,"Close",CloseDialog);
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
            if (e.button == 0 && editable) {
                if (BeginObjectGesture(e.localPosition) || ConstructionPointerDown(e.localPosition)) { image.CapturePointer(e.pointerId); }
                else Pick(e.localPosition);
            }
            if (e.button == 1 || e.button == 2) { drag = e.button; previous = e.position; image.CapturePointer(e.pointerId); }
            e.StopPropagation();
        });
        image.RegisterCallback<PointerMoveEvent>(e => {
            if (editable && modal == null) { UpdateObjectGesture(e.localPosition); if(!objectGesture)ConstructionPointerMove(e.localPosition); }
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
        image.RegisterCallback<PointerUpEvent>(e => { if (editable) {EndObjectGesture(false);ConstructionPointerUp();} drag = -1; image.ReleasePointer(e.pointerId); });
        image.RegisterCallback<PointerCaptureOutEvent>(e => { drag = -1; if(editable) {EndObjectGesture(false);ConstructionPointerUp();} });
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
        var pipeline=UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline;
        var template=Resources.Load<Material>(pipeline==null?"WorldBuilderDefault":pipeline.GetType().Name.Contains("HDRender")?"WorldBuilderHDRP":"WorldBuilderURP");
        var shader = template!=null?template.shader:pipeline==null?Shader.Find("Standard"):Shader.Find("HDRP/Lit") ?? Shader.Find("Universal Render Pipeline/Lit");
        shader=shader??Shader.Find("Unlit/Color");
        if (shader == null) throw new InvalidOperationException("No compatible material shader is available.");
        var material = new Material(shader);
        if (material.HasProperty("_BaseColor")) material.SetColor("_BaseColor", color); else material.color = color;
        if(material.HasProperty("_Smoothness"))material.SetFloat("_Smoothness",0.25f);
        return material;
    }
    GameObject Model(WorkspaceProject data, Transform parent, int layer)
    {
        if(data.construction!=null) {
            var derived=ConstructionData(data.construction);
            data.vertices=derived.vertices;data.uv=derived.uv;data.triangles=derived.triangles;data.submeshes=derived.submeshes;data.normals=null;
            if(data.materialColors==null)data.materialColors=derived.materialColors;
        }
        Mesh mesh = data.CreateMesh();
        var go = new GameObject(data.name); go.transform.SetParent(parent, false); go.layer = layer;
        var identity = go.AddComponent<WorkspaceIdentity>(); identity.ownedMesh = mesh;
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        var colors = data.materialColors ?? new[] { data.color };
        if(colors.Length == 0) colors=new[] { data.color };
        identity.ownedMaterials = new Material[colors.Length];
        for(int i=0;i<colors.Length;i++) {
            var material=identity.ownedMaterials[i]=Material(colors[i]);
            if(data.metallic!=null&&i<data.metallic.Length&&material.HasProperty("_Metallic"))material.SetFloat("_Metallic",Mathf.Clamp01(data.metallic[i]));
            if(data.smoothness!=null&&i<data.smoothness.Length&&material.HasProperty("_Smoothness"))material.SetFloat("_Smoothness",Mathf.Clamp01(data.smoothness[i]));
        }
        identity.ownedMaterial=identity.ownedMaterials[0];
        identity.construction=data.construction; identity.libraryId=data.libraryId; identity.albedo=data.albedo;
        if(data.albedo!=null) {
            identity.ownedTextures=new Texture2D[data.albedo.Length];
            for(int i=0;i<data.albedo.Length&&i<identity.ownedMaterials.Length;i++)if(data.albedo[i]!=null) {
                if(string.IsNullOrEmpty(data.albedo[i].base64)||data.albedo[i].base64.Length>12*1024*1024)throw new FormatException("Invalid texture payload.");
                byte[] bytes=Convert.FromBase64String(data.albedo[i].base64);var texture=new Texture2D(2,2);identity.ownedTextures[i]=texture;
                if(!texture.LoadImage(bytes)||texture.width>8192||texture.height>8192)throw new FormatException("Unsupported or oversized texture image.");
                var material=identity.ownedMaterials[i];
                if(material.HasProperty("_BaseColorMap"))material.SetTexture("_BaseColorMap",texture);else material.mainTexture=texture;
            }
        }
        go.AddComponent<MeshRenderer>().sharedMaterials = identity.ownedMaterials;
        var collider=go.AddComponent<MeshCollider>(); collider.sharedMesh=mesh;
        if(data.construction?.kind=="water") collider.enabled=false;
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
            var data = WorkspaceObjMaterials.Import(path,out string warning);
            selected = Model(data, PlacementParent(), 31); Preview(data); FrameSelected(); Changed();
            Status(string.IsNullOrEmpty(warning)?"Imported OBJ; supplied supported material and texture references are preserved.":"Imported with warnings: "+warning);
        });
    }
    void Preview(WorkspaceProject data)
    {
        SetMode("Asset");
        Clear(reference); var model = Model(data, reference, 30);
        model.transform.localPosition = Vector3.zero; model.transform.localRotation = Quaternion.identity; model.transform.localScale = Vector3.one;
        var bounds = model.GetComponent<Renderer>().bounds;
        referenceCenter = bounds.center; referenceDistance = Mathf.Max(2, bounds.extents.magnitude * 3);
    }
    void Duplicate()
    {
        if (selected == null) return;
        var original=selected;
        GameObject CloneObject(GameObject source,Transform parent)
        {
            var data=JsonUtility.FromJson<WorkspaceProject>(JsonUtility.ToJson(WorkspaceProject.Capture(source,source.GetComponent<WorkspaceIdentity>().source)));
            data.id=Guid.NewGuid().ToString("N");data.name+=" copy";
            var copy=Model(data,parent,31);
            foreach(Transform child in source.transform)if(child.GetComponent<MeshFilter>()!=null)CloneObject(child.gameObject,copy.transform);
            return copy;
        }
        selected=CloneObject(original,original.transform.parent);
        selected.transform.localPosition+=Vector3.right;
        Changed();
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
        foreach(var renderer in selected.GetComponentsInChildren<Renderer>())bounds.Encapsulate(renderer.bounds);
        workCenter = bounds.center; workDistance = Mathf.Max(2, bounds.extents.magnitude * 3);
        workCamera.orthographicSize = workDistance * 0.4f;
    }
    void FrameAll()
    {
        bool found = false; var bounds = new Bounds();
        foreach (var renderer in world.GetComponentsInChildren<Renderer>()) {
            var b = renderer.bounds; if (!found) bounds = b; else bounds.Encapsulate(b); found = true;
        }
        workCenter = found ? bounds.center : Vector3.zero; workDistance = found ? Mathf.Max(2, bounds.extents.magnitude * 3) : 12;
        workCamera.orthographicSize = workDistance * 0.4f;
    }
    string State() => JsonUtility.ToJson(WorkspaceDocument.Capture(world, title));
    void Changed() { history.Record(State()); Refresh(); }
    void Undo() { CancelConstruction(); string state = history.Undo(); if (state != null) Restore(JsonUtility.FromJson<WorkspaceDocument>(state)); }
    void Redo() { CancelConstruction(); string state = history.Redo(); if (state != null) Restore(JsonUtility.FromJson<WorkspaceDocument>(state)); }
    void Restore(WorkspaceDocument document)
    {
        // Construct everything in a staging root first: invalid files leave the scene intact.
        var stage = new GameObject("Project staging").transform;
        try {
            var ids=new Dictionary<string,GameObject>();
            foreach (var data in document.objects) {
                var model=Model(data, stage, 31);
                string id=model.GetComponent<WorkspaceIdentity>().id;
                if(ids.ContainsKey(id))throw new FormatException("Duplicate object ID"); ids[id]=model;
            }
            foreach(var data in document.objects) if(!string.IsNullOrEmpty(data.parentId)) {
                if(!ids.TryGetValue(data.parentId,out var parent))throw new FormatException("Missing parent object");
                var child=ids[data.id];
                if(parent==child || parent.transform.IsChildOf(child.transform))throw new FormatException("Cyclic object parenting");
                child.transform.SetParent(parent.transform,false);
            }
        } catch { Clear(stage); Destroy(stage.gameObject); throw; }
        Clear(world);
        while (stage.childCount > 0) stage.GetChild(0).SetParent(world, false);
        Destroy(stage.gameObject); title = document.title; selected = null; ReconnectWorldTools(); Refresh();
    }
    void NewProject()
    {
        Clear(world); Clear(reference); selected = null; projectPath = ""; title = "Untitled world";
        ResetWorldTools(); history.Reset(State()); savedState = State(); Refresh(); Status("New world. Generate an island or use Florida Island Test.");
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
            projectPath = path; title = document.title; PlayerPrefs.SetString("worldbuilder.lastProject",path);PlayerPrefs.Save(); history.Record(State()); savedState = State(); Refresh(); Status("Saved " + Path.GetFileName(path));
        });
    }
    void Export()
    {
        Try(() => {
            string path = WorkspaceFiles.Pick(true, "Export scene OBJ + MTL", "obj"); if (string.IsNullOrEmpty(path)) return;
            foreach (var identity in world.GetComponentsInChildren<WorkspaceIdentity>()) {
                var source = identity.source;
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
        foreach (var identity in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            var go = identity.gameObject;
            if(hierarchyQuery.Length>0 && go.name.IndexOf(hierarchyQuery,StringComparison.OrdinalIgnoreCase)<0)continue;
            var button = Button(hierarchy, go.name, () => { selected = go; Refresh(); });
            int depth=0;for(var ancestor=go.transform.parent;ancestor!=null&&ancestor!=world;ancestor=ancestor.parent)depth++;
            button.style.marginLeft=3+depth*12;
            if (go == selected) button.AddToClassList("selected");
        }
        inspector.Clear(); Label(inspector, "PROPERTIES", "section");
        RefreshWorldTools();
        if (selected == null) { Label(inspector, "Select an object in the scene or hierarchy.", "hint"); return; }
        var name = new TextField("Name") { value = selected.name, isDelayed = true }; inspector.Add(name);
        name.RegisterValueChangedCallback(e => { if (selected != null && !string.IsNullOrWhiteSpace(e.newValue)) { selected.name = e.newValue; Changed(); } });
        AddConstructionInspector();
        VectorFields("Position", selected.transform.localPosition, v => selected.transform.localPosition = v);
        VectorFields("Rotation", selected.transform.localEulerAngles, v => selected.transform.localEulerAngles = v);
        VectorFields("Scale", selected.transform.localScale, v => { if (Mathf.Abs(v.x * v.y * v.z) < 0.000001f) throw new ArgumentException("Scale must be non-zero."); selected.transform.localScale = v; });
        Label(inspector, "MATERIAL", "section");
        var materialPicker=new DropdownField("Preset",new List<string>(WorldMaterials.Names),0);inspector.Add(materialPicker);
        materialPicker.RegisterValueChangedCallback(e=>{
            var material=selected.GetComponent<Renderer>().sharedMaterial;var color=WorldMaterials.Color(e.newValue);
            if(material.HasProperty("_BaseColor"))material.SetColor("_BaseColor",color);else material.color=color;
            if(material.HasProperty("_Metallic"))material.SetFloat("_Metallic",e.newValue=="Metal"?0.85f:0);
            if(material.HasProperty("_Smoothness"))material.SetFloat("_Smoothness",e.newValue=="Metal"||e.newValue=="Glass"?0.7f:0.2f);
            Changed();
        });
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
        EndObjectGesture(true); CloseDialog(); modal = new VisualElement(); modal.AddToClassList("modal"); root.Add(modal);
        var box = new VisualElement(); box.AddToClassList("dialog"); modal.Add(box);
        Label(box, titleText, "section"); var content = new ScrollView(); content.AddToClassList("dialog-scroll"); box.Add(content); Label(content, text, "hint"); actions(content);
    }
    void CloseDialog() { previewGeneration++; if (modal != null) modal.RemoveFromHierarchy(); modal = null; }
    void GameBrowser()
    {
        Dialog("Game Asset Browser", "Read-only game preview adapters: Sims MLOD subsets and plain Forza float/SNORM mesh parts. Missing textures, unsupported versions, compression and encrypted archives report their limits.", box => {
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
            Button(box, "Export Game Diagnostic", ExportGameDiagnostic);
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
                            if (ext == ".obj" || ext == ".package" || ext == ".modelbin" || ext == ".swatchbin" || ext == ".zip" || ext == ".minizip") result.Add(file);
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
                else if (Path.GetExtension(file).Equals(".package", StringComparison.OrdinalIgnoreCase))
                    Button(list, "Inspect Sims package: " + Path.GetFileName(file), () => InspectSims(selectedFile));
                else if (Path.GetExtension(file).Equals(".modelbin", StringComparison.OrdinalIgnoreCase))
                    Button(list, "Inspect Forza model: " + Path.GetFileName(file), () => InspectForza(selectedFile));
                else if (Path.GetExtension(file).Equals(".zip", StringComparison.OrdinalIgnoreCase))
                    Button(list, "Browse model archive: " + Path.GetFileName(file), () => InspectForzaZip(selectedFile));
                else Label(list, Path.GetFileName(file) + " — texture/MiniZip adapter pending", "hint");
            }
            Status("Scan found " + files.Count + " files (limit 250). Inspect a package/model to browse its geometry resources.");
        } catch (Exception e) { if (this != null) Status("Scan failed: " + e.Message); }
    }
    async void ExportGameDiagnostic()
    {
        string destination;
        try { destination = WorkspaceFiles.Pick(true, "Save game metadata diagnostic", "json"); }
        catch (Exception e) { Status(e.Message); return; }
        if (string.IsNullOrEmpty(destination)) return;
        var names = new[] { "Forza Horizon 5", "The Sims 4" };
        var paths = new[] { PlayerPrefs.GetString("worldbuilder.gamePath.0", ""), PlayerPrefs.GetString("worldbuilder.gamePath.1", "") };
        Status("Collecting bounded game metadata report…");
        try {
            var report = await Task.Run(() => GameAssetDiagnostic.Scan(names, paths));
            if (this == null) return;
            WorkspaceAtomicFile.Write(destination, JsonUtility.ToJson(report, true));
            Status("Diagnostic saved. Review and share the JSON report; no game resource bytes are included.");
        } catch (Exception e) { if (this != null) Status("Diagnostic failed: " + e.Message); }
    }

    async void InspectSims(string path)
    {
        Status("Reading Sims package resource index…");
        try {
            var package = await Task.Run(() => new SimsPackage(path));
            if (this == null) return;
            Dialog("Sims package resources", Path.GetFileName(path) + " • " + package.Entries.Count + " resources. MLOD previews are neutral geometry only; cross-package dependencies, textures and unsupported vertex layouts remain pending.", box => {
                var list = new ScrollView(); list.style.height = 320; box.Add(list);
                int shown = 0;
                foreach (var entry in package.Entries) if (!entry.IsDeleted && entry.Type == SimsPackage.Mlod && shown++ < 250) {
                    var resource = entry;
                    Button(list, "Preview MLOD " + resource.Instance.ToString("X16"), () => PreviewSims(package, resource));
                }
                if (shown == 0) Label(list, "No object MLOD resources in this package. CAS GEOM is not implemented.", "hint");
                if (shown > 250) Label(list, "Showing first 250 geometry resources. Search/pagination is pending.", "hint");
                Button(box, "Back to game folders", GameBrowser); Button(box, "Close", CloseDialog);
            });
            Status("Package index loaded. Preview buttons attempt supported geometry decoding; compatibility is checked on selection.");
        } catch (Exception e) { if (this != null) Status("Package inspection: " + e.Message); }
    }
    async void PreviewSims(SimsPackage package, SimsPackage.Entry resource)
    {
        int generation = ++previewGeneration;
        Status("Decoding Sims object geometry…");
        try {
            var data = await Task.Run(() => SimsMeshPreview.Decode(package, resource));
            if (this == null || generation != previewGeneration) return;
            PreviewModels(data); CloseDialog(); Status("Sims neutral-geometry reference preview. Textures/materials not decoded. Game file remains read-only.");
        } catch (Exception e) { if (this != null) Status("Sims preview unavailable: " + e.Message); }
    }
    async void InspectForzaZip(string path)
    {
        Status("Reading archive model directory…");
        try {
            var archive = await Task.Run(() => GameArchiveDiagnostic.Inspect(path));
            if (this == null) return;
            Dialog("Archive model resources", Path.GetFileName(path) + " • " + archive.MeshEntries + " model files. Only stored/deflated, unencrypted entries are opened. Select a model part; skeleton files may have no mesh.", box => {
                var list = new ScrollView(); list.style.height = 320; box.Add(list); int shown = 0;
                foreach (var member in archive.Members) if (Path.GetExtension(member.Name).Equals(".modelbin", StringComparison.OrdinalIgnoreCase) && shown++ < 500) {
                    var resource = member;
                    var button = Button(list, member.Name, () => OpenArchivedModel(path, resource));
                    if (member.Encrypted || (member.Method != 0 && member.Method != 8)) {
                        button.SetEnabled(false); button.tooltip = "Unsupported encrypted/compressed entry.";
                    }
                }
                if (shown == 0) Label(list, "No modelbin names in this archive. MiniZip geometry uses a separate format.", "hint");
                Button(box, "Back to game folders", GameBrowser); Button(box, "Close", CloseDialog);
            });
        } catch (Exception e) { if (this != null) Status("Archive browser: " + e.Message); }
    }
    async void OpenArchivedModel(string path, GameArchiveDiagnostic.Member member)
    {
        Status("Opening selected model in memory…");
        try {
            var bundle = await Task.Run(() => new ForzaBundle(GameArchiveRead.Read(path, member), path + "::" + member.Name));
            if (this == null) return;
            ShowForzaMeshes(bundle, member.Name);
        } catch (Exception e) { if (this != null) Status("Archived model: " + e.Message); }
    }
    void ShowForzaMeshes(ForzaBundle bundle, string name)
    {
        Dialog("Forza model mesh parts", name + " • " + bundle.Blobs.Count + " blobs. Preview shows supported mesh parts with neutral shading. Assembly, materials, textures and other packed layouts remain pending.", box => {
            var list = new ScrollView(); list.style.height = 320; box.Add(list); int shown = 0;
            foreach (var blob in bundle.Blobs) if (blob.Tag == ForzaBundle.MeshTag && shown++ < 250) {
                var resource = blob;
                Button(list, "Preview " + (string.IsNullOrEmpty(blob.Name) ? "mesh at " + blob.Offset : blob.Name) + " v" + blob.Major + "." + blob.Minor,
                    () => PreviewForza(bundle, resource));
            }
            if (shown == 0) Label(list, "No mesh blobs in this bundle (it may be a skeleton-only file).", "hint");
            Button(box, "Back to game folders", GameBrowser); Button(box, "Close", CloseDialog);
        });
    }

    async void InspectForza(string path)
    {
        Status("Reading Forza model directory…");
        try {
            var bundle = await Task.Run(() => new ForzaBundle(path));
            if (this == null) return;
            ShowForzaMeshes(bundle, Path.GetFileName(path));
        } catch (Exception e) { if (this != null) Status("Forza inspection: " + e.Message); }
    }
    async void PreviewForza(ForzaBundle bundle, ForzaBundle.Blob resource)
    {
        int generation = ++previewGeneration;
        Status("Decoding Forza mesh buffer…");
        try {
            var data = await Task.Run(() => ForzaMeshPreview.Decode(bundle, resource));
            if (this == null || generation != previewGeneration) return;
            PreviewModels(new List<WorkspaceProject> { data }); CloseDialog();
            Status("Forza local-part buffer preview only. Assembly, textures and game materials are not reproduced.");
        } catch (Exception e) { if (this != null) Status("Forza preview unavailable: " + e.Message); }
    }
    void PreviewModels(List<WorkspaceProject> objects)
    {
        SetMode("Asset");
        var stage = new GameObject("Reference preview staging").transform;
        try { foreach (var data in objects) Model(data, stage, 30); }
        catch { Clear(stage); Destroy(stage.gameObject); throw; }
        Clear(reference);
        while (stage.childCount > 0) stage.GetChild(0).SetParent(reference, false);
        Destroy(stage.gameObject);
        var bounds = reference.GetChild(0).GetComponent<Renderer>().bounds;
        foreach (Transform child in reference) bounds.Encapsulate(child.GetComponent<Renderer>().bounds);
        referenceCenter = bounds.center; referenceDistance = Mathf.Max(2, bounds.extents.magnitude * 3);
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
        var button = new Button(() => Try(action)) { text = text, tooltip = text }; parent.Add(button); return button;
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
        DisposeWorldTools();
        if (world != null) Destroy(world.gameObject); if (reference != null) Destroy(reference.gameObject);
        if (sun != null) Destroy(sun);
        if (workCamera != null) Destroy(workCamera.gameObject); if (referenceCamera != null) Destroy(referenceCamera.gameObject);
        if (displayCamera != null) Destroy(displayCamera.gameObject);
        if (workTexture != null) { workTexture.Release(); Destroy(workTexture); }
        if (referenceTexture != null) { referenceTexture.Release(); Destroy(referenceTexture); }
        if (ui != null) Destroy(ui); if (panel != null) Destroy(panel);
    }
}
