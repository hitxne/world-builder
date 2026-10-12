using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;

// World and lot construction use the same objects, material service, history,
// project manifest, selection and export as the Asset Creator.
public sealed partial class WorldBuilderRuntime
{
    string workspaceMode="World", constructionTool="select", activeLotId;
    GameObject activeLot;
    VisualElement constructionPanel, referencePane,toolSettings;
    Label toolStatus,modeHeading;
    Button cancelToolButton;
    string toolCategory="Terrain";
    readonly Dictionary<string,Button> modeButtons=new Dictionary<string,Button>();
    readonly Dictionary<string,Button> toolButtons=new Dictionary<string,Button>();
    float brushRadius=8, brushStrength=0.5f, gridSize=1, wallHeight=3, roadWidth=6;
    int floorLevel;
    float islandWidth=160,islandDepth=160;
    int islandSeed=1337;
    bool stroke, objectGesture,constructionDrag,constructionDragValid;
    Vector3 constructionDragEnd;
    Transform gestureObject;
    Vector3 gesturePosition, gestureScale, gestureWorldStart, gestureHitStart;
    Quaternion gestureRotation;
    Vector2 gestureScreenStart;
    Plane gesturePlane;
    string pendingLibraryPath;
    GameObject pendingCopySource;
    float placementYaw;
    bool gridEnabled=true,offGrid,repeatPlacement;
    Slider brushRadiusSlider;
    bool HasPlacement => !string.IsNullOrEmpty(pendingLibraryPath)||pendingCopySource!=null;
    Vector3? firstCorner;
    readonly List<WorldPoint> roadPoints=new List<WorldPoint>();
    float flattenHeight, lastAutosave;
    string RecoveryPath => Path.Combine(Application.persistentDataPath,"Recovery.wbworld");
    static WorldPoint P(Vector3 v)=>new WorldPoint(v.x,v.y,v.z);
    static Vector3 V(WorldPoint v)=>new Vector3(v.x,v.y,v.z);
    Transform PlacementParent()=>workspaceMode=="Lot"&&activeLot!=null?activeLot.transform:world;
    void InitializeWorldTools()
    {
        var sidebar=root.Q<VisualElement>(className:"sidebar");
        var navigation=root.Q<VisualElement>("mode-navigation");
        modeButtons["World"]=Button(navigation,"World",()=>SetMode("World"));
        modeButtons["Lot"]=Button(navigation,"Lot",EnterLot);
        modeButtons["Asset"]=Button(navigation,"Assets",()=>SetMode("Asset"));
        constructionPanel=root.Q<ScrollView>("construction-catalog").contentContainer;
        modeHeading=Label(navigation,"","mode-heading");
        var editing=root.Q<VisualElement>("editing-tools");
        ToolChoice(editing,"Select","select");ToolChoice(editing,"Move","move");ToolChoice(editing,"Rotate","rotate");ToolChoice(editing,"Scale","scale");ToolChoice(editing,"Copy","eyedropper");ToolChoice(editing,"Delete","delete");
        referencePane=referenceImage.parent;
        SetMode("World");
        Status("Start with Generate Island or Florida Island Test, then draw roads and lots.");
        string last=PlayerPrefs.GetString("worldbuilder.lastProject","");
        if(File.Exists(last))Button(sidebar,"Open Last Project",()=>ConfirmDiscard(()=>Try(()=>{
            Restore(WorkspaceDocument.Open(last));projectPath=last;history.Reset(State());savedState=State();FrameAll();Refresh();Status("Last project opened.");
        })));
        if(File.Exists(RecoveryPath))Button(sidebar,"Open Recovery",()=>ConfirmDiscard(()=>Try(()=>{
            Restore(WorkspaceDocument.Open(RecoveryPath)); projectPath=""; history.Reset(State()); savedState=""; FrameAll(); Refresh(); Status("Recovery loaded. Save As to keep it.");
        })));
    }
    void SetMode(string mode)
    {
        CancelConstruction();workspaceMode=mode;toolCategory=mode=="World"?"Terrain":mode=="Lot"?"Structure":"Import";
        referencePane.style.display=mode=="Asset"?DisplayStyle.Flex:DisplayStyle.None;
        referenceCamera.enabled=mode=="Asset";
        if(mode=="Lot"&&activeLot!=null){selected=activeLot;FrameSelected();}
        BuildConstructionPanel();Refresh();
    }
    GameObject SelectedLot()
    {
        for(var ancestor=selected!=null?selected.transform:null;ancestor!=null&&ancestor!=world;ancestor=ancestor.parent)
            if(ancestor.GetComponent<WorkspaceIdentity>()?.construction?.kind=="lot")return ancestor.gameObject;
        return null;
    }
    void EnterLot()
    {
        var selectedLot=SelectedLot();if(selectedLot!=null)activeLot=selectedLot;
        if(activeLot==null){Status("Select a lot or use Draw Lot in World Mode first.");return;}
        activeLotId=activeLot.GetComponent<WorkspaceIdentity>().id;SetMode("Lot");
    }
    void BuildConstructionPanel()
    {
        root.Q<ScrollView>("construction-catalog").EnableInClassList("buy-catalog",toolCategory=="Objects"||toolCategory=="Furnish"||toolCategory=="Library"||toolCategory=="Roads"&&roadsideObjects);
        ApplyLayout();
        constructionPanel.Clear();
        var categories=Row(constructionPanel,"catalog-tabs");
        string[] names=workspaceMode=="World"?new[]{"Terrain","Roads","Lots","Objects"}:workspaceMode=="Lot"?new[]{"Structure","Openings","Floors","Furnish"}:new[]{"Import","Primitives","Library"};
        foreach(var category in names){var c=category;var button=Button(categories,CategoryTitle(c),()=>{CancelConstruction();toolCategory=c;BuildConstructionPanel();});if(c==toolCategory)button.AddToClassList("selected");}
        var content=Row(constructionPanel,"catalog-content");
        var choices=new VisualElement();choices.AddToClassList("catalog-choices");content.Add(choices);
        var settings=new VisualElement();toolSettings=settings;settings.AddToClassList("catalog-settings");content.Add(settings);

        if(workspaceMode=="World") {
            if(toolCategory=="Terrain") {
                ToolChoice(choices,"Raise","raise");ToolChoice(choices,"Lower","lower");ToolChoice(choices,"Smooth","smooth");ToolChoice(choices,"Flatten","flatten");ToolChoice(choices,"Paint Sand","sand");ToolChoice(choices,"Paint Grass","grass");
                brushRadiusSlider=BrushSlider(settings,"Brush radius (m)",brushRadius,1,40,v=>brushRadius=v);BrushSlider(settings,"Strength",brushStrength,0.05f,2,v=>brushStrength=v);
            } else if(toolCategory=="Roads") {
                RoadBuildCatalog(choices,settings);
            } else if(toolCategory=="Lots") {ToolChoice(choices,"Draw Lot","lot");Button(choices,"Build Selected Lot",EnterLot);}
            else if(toolCategory=="Objects"){BuildAssetCatalog(choices);}
            else {
                Button(choices,"Generate Island",()=>ConfirmDiscard(GenerateIsland));Button(choices,"Florida Island Test",()=>ConfirmDiscard(BuildFloridaTest));
                Number(settings,"Island width",islandWidth,32,512,v=>islandWidth=v);Number(settings,"Island depth",islandDepth,32,512,v=>islandDepth=v);Number(settings,"Seed",islandSeed,0,100000,v=>islandSeed=(int)v);
            }
        } else if(workspaceMode=="Lot") {
            Label(settings,activeLot==null?"No active lot":activeLot.name,"hint");
            if(toolCategory=="Structure"){ToolChoice(choices,"Room","room");ToolChoice(choices,"Wall","wall");ToolChoice(choices,"Floor","floor");ToolChoice(choices,"Roof","roof");}
            else if(toolCategory=="Openings"){ToolChoice(choices,"Door","door");ToolChoice(choices,"Window","window");}
            else if(toolCategory=="Floors"){ToolChoice(choices,"Stairs","stairs");Button(choices,"Floor Down",()=>{floorLevel=Math.Max(0,floorLevel-1);RefreshWorldTools();});Button(choices,"Floor Up",()=>{floorLevel=Math.Min(5,floorLevel+1);RefreshWorldTools();});}
            else {BuildAssetCatalog(choices);Button(settings,"Save Selection",SaveLibrary);}
        } else {
            if(toolCategory=="Import"){Button(choices,"Import model",Import);Button(choices,"Reimport selected",ReimportSelected);Label(settings,"OBJ + MTL + supported textures. Imported sources stay untouched.","hint");}
            else if(toolCategory=="Primitives"){
                Button(choices,"Cube",()=>AddPrimitive(PrimitiveType.Cube,"Cube"));Button(choices,"Plane",()=>AddPrimitive(PrimitiveType.Plane,"Plane"));Button(choices,"Sphere",()=>AddPrimitive(PrimitiveType.Sphere,"Sphere"));Button(choices,"Cylinder",()=>AddPrimitive(PrimitiveType.Cylinder,"Cylinder"));
            } else {BuildAssetCatalog(choices);Button(settings,"Save selected to library",SaveLibrary);}
        }
        cancelToolButton=Button(settings,"Cancel",()=>{CancelConstruction();Status("Cancelled. Select an object or choose a tool.");});
        toolStatus=statusLabel;RefreshWorldTools();
    }
    static string CategoryTitle(string category)
    {
        if(category=="Furnish")return "Buy objects";if(category=="Structure")return "Build";if(category=="Openings")return "Doors & Windows";if(category=="Floors")return "Floors & Stairs";return category;
    }
    void ToolChoice(VisualElement parent,string label,string tool){toolButtons[tool]=Button(parent,label,()=>SetTool(tool));}
    void SetTool(string tool){CancelConstruction();constructionTool=tool;RefreshWorldTools();Status(ToolInstruction());}
    void CancelConstruction(){constructionDrag=false;EndRoadNode(true);EndRoadDrag(true);ClearRoadDragPreview();ClearPlacementPreview();EndObjectGesture(true);pendingLibraryPath=null;pendingCopySource=null;placementYaw=0;ConstructionPointerUp();firstCorner=null;roadPoints.Clear();constructionTool="select";RefreshWorldTools();}
    string ToolInstruction()
    {
        if(HasPlacement)return "Click to place. Comma/period or right-click rotate 45°. Shift repeats placement. Escape cancels.";
        if(constructionTool=="eyedropper")return "Click an object to copy it, then click to place. Comma/period rotate; Escape cancels.";
        if(constructionTool=="delete")return "Click an object to delete it. Ctrl+Z restores it. Escape returns to selection.";
        if(constructionTool=="move")return "Drag an object on its horizontal plane. Grid snapping applies. Escape restores its position.";
        if(constructionTool=="rotate")return "Drag an object horizontally to rotate around its local vertical axis. Escape cancels.";
        if(constructionTool=="scale")return "Drag an object horizontally to scale uniformly. Escape cancels.";
        if(constructionTool=="road")return "Drag to preview a road; release to build. Snaps to 45° and road ends. Alt draws freely; Escape cancels.";
        if(constructionTool=="roadnode")return "Drag road control points. Connected ends slide along the junction side; Escape restores the edit.";
        if(constructionTool=="junction")return "Click to place a junction. Set its size/radius, then attach roads through Road settings > Connections.";
        if(constructionTool=="roadcurve")return "Click route points, then Finish route or Enter. Escape cancels.";
        if(constructionTool=="room"||constructionTool=="lot"||constructionTool=="floor"||constructionTool=="roof"||constructionTool=="wall")return "Drag to size, then release to build. Escape cancels; grid snapping applies.";
        if(constructionTool=="door"||constructionTool=="window")return "Click an existing wall to create an opening and frame.";
        if(IsBrush())return "Hold left mouse over terrain to sculpt or paint. Release records one undo step.";
        if(constructionTool=="tree"||constructionTool=="stairs")return "Click to place. Objects can be moved in Properties.";
        return "Left click selects; right drag pans; middle drag orbits; wheel zooms. H moves, E copies, K deletes.";
    }
    bool BeginObjectGesture(Vector2 point)
    {
        if(constructionTool!="move"&&constructionTool!="rotate"&&constructionTool!="scale")return false;
        Try(()=>{
            Physics.SyncTransforms();
            if(!Physics.Raycast(WorkRay(point),out var hit,10000,1<<31)){Status("Click an object to transform it.");return;}
            var target=hit.collider.gameObject;
            // A selected building/lot moves as a unit when its child is clicked.
            if(selected==null||!target.transform.IsChildOf(selected.transform))selected=target;
            gestureObject=selected.transform;gesturePosition=gestureObject.localPosition;
            gestureRotation=gestureObject.localRotation;gestureScale=gestureObject.localScale;
            gestureWorldStart=gestureObject.position;gestureScreenStart=point;
            gesturePlane=new Plane(Vector3.up,gestureWorldStart);
            if(constructionTool=="move") {
                if(!gesturePlane.Raycast(WorkRay(point),out float distance)){Status("Use an angled or top view to move this object.");return;}
                gestureHitStart=WorkRay(point).GetPoint(distance);
            }
            objectGesture=true;Refresh();
        });
        return true;
    }
    void UpdateObjectGesture(Vector2 point)
    {
        if(!objectGesture||gestureObject==null)return;
        Try(()=>{
            if(constructionTool=="move") {
                if(!gesturePlane.Raycast(WorkRay(point),out float distance))return;
                var next=gestureWorldStart+WorkRay(point).GetPoint(distance)-gestureHitStart;
                var parent=gestureObject.parent;var local=parent==null?next:parent.InverseTransformPoint(next);
                if(gridEnabled&&!offGrid){local.x=Mathf.Round(local.x/gridSize)*gridSize;local.z=Mathf.Round(local.z/gridSize)*gridSize;}
                // Move within a lot without silently moving furniture outside its bounds.
                if(workspaceMode=="Lot"&&activeLot!=null&&parent==activeLot.transform) {
                    var size=activeLot.GetComponent<WorkspaceIdentity>().construction.size;
                    if(Mathf.Abs(local.x)>size.x/2||Mathf.Abs(local.z)>size.z/2){Status("Keep the object origin inside the active lot.");return;}
                }
                gestureObject.localPosition=local;
            } else if(constructionTool=="rotate")gestureObject.localRotation=gestureRotation*Quaternion.Euler(0,offGrid?(point.x-gestureScreenStart.x)*0.5f:Mathf.Round((point.x-gestureScreenStart.x)*0.5f/45)*45,0);
            else if(constructionTool=="scale")gestureObject.localScale=gestureScale*Mathf.Clamp(Mathf.Exp((point.x-gestureScreenStart.x)*0.01f),0.05f,20);
            Physics.SyncTransforms();Status(constructionTool+": "+gestureObject.name+" — release to apply, Escape to cancel.");
        });
    }
    void EndObjectGesture(bool cancel)
    {
        if(!objectGesture)return;objectGesture=false;
        if(gestureObject!=null) {
            if(cancel){gestureObject.localPosition=gesturePosition;gestureObject.localRotation=gestureRotation;gestureObject.localScale=gestureScale;Physics.SyncTransforms();Refresh();Status("Transform cancelled.");}
            else {Changed();Status("Transform applied. Undo is available.");}
        }
        gestureObject=null;
    }
    bool IsBrush()=>constructionTool=="raise"||constructionTool=="lower"||constructionTool=="smooth"||constructionTool=="flatten"||constructionTool=="sand"||constructionTool=="grass";
    Ray WorkRay(Vector2 point)
    {
        var rect=workImage.contentRect;
        return workCamera.ViewportPointToRay(new Vector3(point.x/rect.width,1-point.y/rect.height,0));
    }
    bool Ground(Vector2 point,out Vector3 position,out GameObject terrain)
    {
        Physics.SyncTransforms();terrain=null;position=Vector3.zero;var ray=WorkRay(point);
        if(workspaceMode=="Lot"&&activeLot!=null) {
            var plane=new Plane(activeLot.transform.up,activeLot.transform.TransformPoint(new Vector3(0,floorLevel*3.2f,0)));
            if(!plane.Raycast(ray,out float distance))return false;position=ray.GetPoint(distance);return true;
        }
        var hits=Physics.RaycastAll(ray,10000,1<<31);float closest=float.MaxValue;
        foreach(var hit in hits)if(hit.collider.GetComponent<WorkspaceIdentity>()?.construction?.kind=="terrain"&&hit.distance<closest){closest=hit.distance;position=hit.point;terrain=hit.collider.gameObject;}
        if(terrain!=null)return true;
        var ground=new Plane(Vector3.up,Vector3.zero);if(!ground.Raycast(ray,out float at))return false;position=ray.GetPoint(at);return true;
    }
    Vector3 Snap(Vector3 worldPoint)
    {
        if(workspaceMode=="Lot"&&activeLot!=null) {
            var local=activeLot.transform.InverseTransformPoint(worldPoint);
            if(gridEnabled&&!offGrid){local.x=Mathf.Round(local.x/gridSize)*gridSize;local.z=Mathf.Round(local.z/gridSize)*gridSize;}local.y=floorLevel*3.2f;
            var size=activeLot.GetComponent<WorkspaceIdentity>().construction.size;
            if(Mathf.Abs(local.x)>size.x/2||Mathf.Abs(local.z)>size.z/2)throw new InvalidOperationException("Construction must stay inside the active lot.");
            return activeLot.transform.TransformPoint(local);
        }
        if(gridEnabled&&!offGrid){worldPoint.x=Mathf.Round(worldPoint.x/gridSize)*gridSize;worldPoint.z=Mathf.Round(worldPoint.z/gridSize)*gridSize;}return worldPoint;
    }
    bool ConstructionPointerDown(Vector2 point)
    {
        if(HasPlacement) {
            Try(()=>{
                if(!Ground(point,out var hit,out var terrain))return;var placement=Snap(hit);
                if(pendingCopySource!=null){selected=CloneObject(pendingCopySource,PlacementParent());selected.transform.position=placement;selected.transform.Rotate(Vector3.up,placementYaw,Space.Self);if(!repeatPlacement)pendingCopySource=null;Changed();}
                else {PlaceLibrary(pendingLibraryPath,placement);if(!repeatPlacement)pendingLibraryPath=null;}
                if(!repeatPlacement)placementYaw=0;RefreshWorldTools();Status("Object placed. Ctrl+Z undoes placement.");
            });return true;
        }
        if(constructionTool=="eyedropper"||constructionTool=="delete") {
            Pick(point);
            if(selected!=null){if(constructionTool=="delete")Delete();else {var source=selected;SetTool("select");pendingCopySource=source;RefreshWorldTools();Status(ToolInstruction());}}
            return true;
        }
        if(constructionTool=="select"||workspaceMode=="Asset")return false;
        if(constructionTool=="roadnode"){Try(()=>BeginRoadNode(point));return true;}
        Try(()=>{
            if(constructionTool=="door"||constructionTool=="window"){PlaceOpening(point);return;}
            if(!Ground(point,out var hit,out var terrain))return;
            if(IsBrush()) {
                if(terrain==null){Status("Generate an island first.");return;}
                stroke=true;flattenHeight=terrain.transform.InverseTransformPoint(hit).y;ApplyBrush(terrain,hit);return;
            }
            hit=Snap(hit);
            if(constructionTool=="junction"){CreateConstruction("Junction",CopyRoad(junctionStyle),hit,world);Changed();return;}
            if(constructionTool=="road"){BeginRoadDrag(hit);return;}
            if(constructionTool=="roadcurve"){if(roadPoints.Count==0)CacheRoadEnds();roadPoints.Add(P(RoadEndSnap(hit)));Status("Road points: "+roadPoints.Count+". Finish Road to create it.");return;}
            if(constructionTool=="tree"){CreateConstruction("Palm",new WorldConstruction{kind="tree",size=new WorldPoint(1,6,1)},hit,world);Changed();return;}
            if(constructionTool=="stairs"){CreateConstruction("Stairs",new WorldConstruction{kind="stairs",size=new WorldPoint(1.5f,3.2f,4)},hit,PlacementParent());Changed();return;}
            firstCorner=hit;constructionDragEnd=hit;constructionDragValid=true;constructionDrag=true;
            Status("Drag to size; release to build. Escape cancels.");
        });return true;
    }
    void ConstructionPointerMove(Vector2 point)
    {
        if(constructionDrag){constructionDragValid=false;Try(()=>{if(workImage.contentRect.Contains(point)&&Ground(point,out var hit,out var terrain)){constructionDragEnd=Snap(hit);constructionDragValid=true;}});return;}
        if(roadNodeDrag){Try(()=>{if(Ground(point,out var hit,out var terrain))MoveRoadNode(hit);});return;}
        if(roadDrag){Try(()=>{if(Ground(point,out var hit,out var terrain))UpdateRoadDrag(hit);});return;}
        if(!stroke||!IsBrush())return;
        Try(()=>{if(Ground(point,out var hit,out var terrain)&&terrain!=null)ApplyBrush(terrain,hit);});
    }
    void ConstructionPointerUp(bool cancelRoad=false){Try(()=>{EndConstructionDrag(cancelRoad);EndRoadNode(cancelRoad);EndRoadDrag(cancelRoad);});if(!stroke)return;stroke=false;Changed();}
    void EndConstructionDrag(bool cancel)
    {
        if(!constructionDrag)return;constructionDrag=false;var start=firstCorner;firstCorner=null;
        if(cancel||!constructionDragValid||!start.HasValue)return;var end=constructionDragEnd;
        if(Vector3.Distance(start.Value,end)<0.25f)return;
        if(constructionTool!="wall"&&(Mathf.Abs(start.Value.x-end.x)<0.25f||Mathf.Abs(start.Value.z-end.z)<0.25f))return;
        if(constructionTool=="wall")CreateWall(start.Value,end);else if(constructionTool=="lot")CreateLot(start.Value,end);else if(constructionTool=="room")CreateRoom(start.Value,end);else CreateRectangle(constructionTool,start.Value,end);
        Changed();Status("Built "+constructionTool+". Drag again to continue; Ctrl+Z undoes it.");
    }
    void ApplyBrush(GameObject terrain,Vector3 point)
    {
        var identity=terrain.GetComponent<WorkspaceIdentity>();
        WorldGeometry.Brush(identity.construction,P(terrain.transform.InverseTransformPoint(point)),brushRadius,brushStrength,constructionTool,flattenHeight);
        RebuildConstruction(terrain);
        if(constructionTool!="sand"&&constructionTool!="grass")RefreshTerrainRoads(terrain,point,brushRadius);
        Status("Terrain "+constructionTool+" • radius "+brushRadius+" m");
    }
    WorldPoint? ProjectRoadVertex(Transform road,WorkspaceIdentity[] terrains,WorldPoint vertex,float clearance)
    {
        var point=road.TransformPoint(V(vertex));bool found=false;float height=float.NegativeInfinity;
        foreach(var terrain in terrains) {
            var source=terrain.construction;if(source?.kind!="terrain")continue;
            var local=terrain.transform.InverseTransformPoint(point);
            if(Mathf.Abs(local.x)>source.size.x/2||Mathf.Abs(local.z)>source.size.z/2)continue;
            local.y=WorldGeometry.Height(source,local.x,local.z);
            float candidate=terrain.transform.TransformPoint(local).y;
            height=Mathf.Max(height,candidate);found=true;
        }
        if(!found)return null;
        point.y=height+clearance;return P(road.InverseTransformPoint(point));
    }
    void RefreshTerrainRoads(GameObject terrain=null,Vector3? center=null,float radius=0)
    {
        float extent=0;
        if(terrain!=null&&center.HasValue){var p=terrain.GetComponent<WorkspaceIdentity>().construction;var scale=terrain.transform.lossyScale;float cell=Mathf.Max(p.size.x,p.size.z)/(p.resolution-1);extent=(radius+2*cell)*Mathf.Max(Mathf.Abs(scale.x),Mathf.Abs(scale.z));}
        foreach(var identity in world.GetComponentsInChildren<WorkspaceIdentity>()) {
            if((identity.construction?.kind!="road"&&identity.construction?.kind!="junction")||!identity.construction.FollowTerrain)continue;
            if(center.HasValue){var bounds=identity.GetComponent<Renderer>().bounds;var areaMin=center.Value-new Vector3(extent,0,extent);var areaMax=center.Value+new Vector3(extent,0,extent);if(!WorldGeometry.IntersectsXZ(P(bounds.min),P(bounds.max),P(areaMin),P(areaMax)))continue;}
            RebuildConstruction(identity.gameObject);
        }
        Physics.SyncTransforms();
    }
    GameObject CreateConstruction(string name,WorldConstruction construction,Vector3 position,Transform parent)
    {
        var data=ConstructionData(construction);data.name=name;data.id=Guid.NewGuid().ToString("N");data.position=parent.InverseTransformPoint(position);
        var go=Model(data,parent,31);if((construction.kind=="road"||construction.kind=="junction")&&construction.FollowTerrain)RebuildConstruction(go);selected=go;return go;
    }
    WorkspaceProject ConstructionData(WorldConstruction p)=>WorldGeometryUnity.Project(p);
    void RebuildConstruction(GameObject go)
    {
        var identity=go.GetComponent<WorkspaceIdentity>();
        var terrains=world.GetComponentsInChildren<WorkspaceIdentity>();
        var data=WorldGeometryUnity.Project(identity.construction,(vertex,clearance)=>ProjectRoadVertex(go.transform,terrains,vertex,clearance));var mesh=data.CreateMesh();
        var old=identity.ownedMesh;identity.ownedMesh=mesh;go.GetComponent<MeshFilter>().sharedMesh=mesh;
        var collider=go.GetComponent<MeshCollider>();collider.sharedMesh=null;collider.sharedMesh=mesh;
        if(old!=null)Destroy(old);
        if((identity.construction.kind=="road"||identity.construction.kind=="junction")) {
            var oldMaterials=identity.ownedMaterials;identity.ownedMaterials=Array.ConvertAll(data.materialColors,c=>Material(c));identity.ownedMaterial=identity.ownedMaterials[0];go.GetComponent<MeshRenderer>().sharedMaterials=identity.ownedMaterials;
            foreach(var material in oldMaterials??new Material[0])if(material!=null)Destroy(material);
        }
        if(identity.construction.kind=="wall")foreach(Transform child in go.transform) {
            var attachment=child.GetComponent<WorkspaceIdentity>();var recipe=attachment?.construction;
            if(recipe==null||(recipe.kind!="door"&&recipe.kind!="window")||recipe.openingIndex<0||recipe.openingIndex>=identity.construction.openings.Length)continue;
            var opening=identity.construction.openings[recipe.openingIndex];var start=V(identity.construction.points[0]);var end=V(identity.construction.points[1]);
            child.localPosition=start+(end-start).normalized*opening.center+Vector3.up*opening.bottom;
            recipe.points=(WorldPoint[])identity.construction.points.Clone();RebuildConstruction(child.gameObject);
        }
    }
    void GenerateIsland()
    {
        NewProject();var terrain=WorldGeometry.Island(islandWidth,islandDepth,islandSeed);
        CreateConstruction("Island terrain",terrain,Vector3.zero,world);
        CreateConstruction("Ocean",new WorldConstruction{kind="water",size=new WorldPoint(islandWidth*1.5f,0,islandDepth*1.5f)},new Vector3(0,1,0),world);
        title="Florida Island";workAngles=new Vector2(45,-25);workCenter=new Vector3(0,3,0);workDistance=Mathf.Max(islandWidth,islandDepth)*1.5f;
        Changed();Status("Editable island created. Sculpt, paint, draw a road, then draw a lot.");
    }
    void CreateLot(Vector3 a,Vector3 b)
    {
        float width=Mathf.Abs(a.x-b.x),depth=Mathf.Abs(a.z-b.z);if(width<4||depth<4)throw new ArgumentException("Lot must be at least 4 × 4 meters.");
        var center=(a+b)/2;float level=Mathf.Max(a.y,b.y);
        var terrain=FindConstruction("terrain");
        if(terrain!=null) {
            var recipe=terrain.GetComponent<WorkspaceIdentity>().construction;
            var first=terrain.transform.InverseTransformPoint(a);var second=terrain.transform.InverseTransformPoint(b);
            var localCenter=terrain.transform.InverseTransformPoint(center);
            float localLevel=Mathf.Max(Mathf.Max(first.y,second.y),WorldGeometry.Height(recipe,localCenter.x,localCenter.z));
            WorldGeometry.FlattenRectangle(recipe,Mathf.Min(first.x,second.x),Mathf.Max(first.x,second.x),Mathf.Min(first.z,second.z),Mathf.Max(first.z,second.z),localLevel);
            RebuildConstruction(terrain);RefreshTerrainRoads();level=terrain.transform.TransformPoint(new Vector3(localCenter.x,localLevel,localCenter.z)).y;
        }
        center.y=level+0.15f;
        activeLot=CreateConstruction("Lot",new WorldConstruction{kind="lot",size=new WorldPoint(width,0.1f,depth)},center,world);
        activeLotId=activeLot.GetComponent<WorkspaceIdentity>().id;Status("Lot created. Choose Lot mode to build inside it.");
    }
    Vector3 LotPoint(Vector3 worldPoint)=>PlacementParent().InverseTransformPoint(worldPoint);
    void CreateWall(Vector3 a,Vector3 b)
    {
        if(Vector3.Distance(a,b)<0.25f)throw new ArgumentException("Wall endpoints are too close.");
        CreateConstruction("Wall",new WorldConstruction{kind="wall",size=new WorldPoint(1,wallHeight,1),width=0.18f,points=new[]{P(LotPoint(a)),P(LotPoint(b))}},PlacementParent().position,PlacementParent());
    }
    void CreateRectangle(string kind,Vector3 a,Vector3 b)
    {
        Vector3 la=LotPoint(a),lb=LotPoint(b);float width=Mathf.Abs(la.x-lb.x),depth=Mathf.Abs(la.z-lb.z);
        if(width<1||depth<1)throw new ArgumentException("Rectangle must be at least 1 × 1 meter.");
        var center=(la+lb)/2;if(kind=="roof")center.y+=wallHeight;
        CreateConstruction(kind=="roof"?"Gable roof":"Floor",new WorldConstruction{kind=kind,size=new WorldPoint(width+(kind=="roof"?0.5f:0),kind=="roof"?1.4f:0.15f,depth+(kind=="roof"?0.5f:0))},PlacementParent().TransformPoint(center),PlacementParent());
    }
    void CreateRoom(Vector3 a,Vector3 b)
    {
        var parent=PlacementParent();Vector3 la=parent.InverseTransformPoint(a),lb=parent.InverseTransformPoint(b);
        float x0=Mathf.Min(la.x,lb.x),x1=Mathf.Max(la.x,lb.x),z0=Mathf.Min(la.z,lb.z),z1=Mathf.Max(la.z,lb.z),y=la.y;
        if(x1-x0<1||z1-z0<1)throw new ArgumentException("Room must be at least 1 × 1 meter.");
        CreateRectangle("floor",a,b);
        var corners=new[]{new Vector3(x0,y,z0),new Vector3(x1,y,z0),new Vector3(x1,y,z1),new Vector3(x0,y,z1)};
        for(int i=0;i<4;i++)CreateWall(parent.TransformPoint(corners[i]),parent.TransformPoint(corners[(i+1)%4]));
        Status("Room created with a floor and four editable walls.");
    }
    void PlaceOpening(Vector2 point)
    {
        Physics.SyncTransforms();if(!Physics.Raycast(WorkRay(point),out var hit,10000,1<<31))return;
        var wall=hit.collider.gameObject;var identity=wall.GetComponent<WorkspaceIdentity>();var data=identity?.construction;
        if(data?.kind!="wall"){Status("Click an existing wall.");return;}
        if(activeLot!=null&&!wall.transform.IsChildOf(activeLot.transform))throw new InvalidOperationException("Wall is outside the active lot.");
        Vector3 start=V(data.points[0]),end=V(data.points[1]),dir=(end-start).normalized;
        float length=Vector3.Distance(start,end),center=Vector3.Dot(wall.transform.InverseTransformPoint(hit.point)-start,dir);
        bool door=constructionTool=="door";float width=door?1:1.5f,height=door?2.1f:1.2f,bottom=door?0:0.9f;
        if(length<width+0.2f)throw new InvalidOperationException("Wall is too short for this opening.");
        center=Mathf.Clamp(Mathf.Round(center/gridSize)*gridSize,width/2+0.05f,length-width/2-0.05f);
        foreach(var opening in data.openings)if(Mathf.Abs(opening.center-center)<(opening.width+width)/2+0.05f)throw new InvalidOperationException("Opening overlaps another opening.");
        var list=new List<WorldOpening>(data.openings){new WorldOpening{kind=constructionTool,center=center,width=width,bottom=bottom,height=height}};
        var previous=data.openings;data.openings=list.ToArray();
        try {RebuildConstruction(wall);}catch{data.openings=previous;throw;}
        CreateConstruction(door?"Door frame":"Window",new WorldConstruction{kind=constructionTool,size=new WorldPoint(width,height,0.25f),openingIndex=data.openings.Length-1,points=new[]{P(start),P(end)}},wall.transform.TransformPoint(start+dir*center+Vector3.up*bottom),wall.transform);
        Changed();Status("Opening cut into wall; frame placed. Undo restores the wall.");
    }
    void FinishRoad()
    {
        if(roadPoints.Count<2){if(constructionTool=="roadcurve")Status("Add at least two route points.");return;}
        CreateConstruction(roadPreset,RoadRecipe(roadPoints.ToArray()),Vector3.zero,world);
        roadPoints.Clear();Changed();Status("Editable spline road created with sidewalks and center markings.");
    }
    void BuildFloridaTest()
    {
        islandWidth=160;islandDepth=160;islandSeed=1337;GenerateIsland();
        var terrain=FindConstruction("terrain");var p=terrain.GetComponent<WorkspaceIdentity>().construction;
        WorldGeometry.Brush(p,new WorldPoint(0,0,0),90,2,"flatten",5);RebuildConstruction(terrain);
        CreateConstruction("Neighborhood road",new WorldConstruction{kind="road",points=new[]{new WorldPoint(-35,5,-20),new WorldPoint(-5,5,-18),new WorldPoint(30,5,-20)},width=6},Vector3.zero,world);
        CreateLot(new Vector3(-12,5,-10),new Vector3(12,5,14));SetMode("Lot");
        Vector3 a=activeLot.transform.TransformPoint(new Vector3(-4,0,-4)),b=activeLot.transform.TransformPoint(new Vector3(4,0,4));CreateRoom(a,b);CreateRectangle("roof",a,b);
        for(int i=0;i<3;i++)CreateConstruction("Palm",new WorldConstruction{kind="tree",size=new WorldPoint(1,6,1)},new Vector3(-17+i*17,5,-11),world);
        SetMode("World");title="Florida Island Test";FrameAll();Changed();Status("Island, water, road, lot and editable house created. Save to keep the world.");
    }
    GameObject FindConstruction(string kind)
    {
        foreach(var id in world.GetComponentsInChildren<WorkspaceIdentity>())if(id.construction?.kind==kind)return id.gameObject;return null;
    }
    void RefreshWorldTools()
    {
        roadEditButton?.SetEnabled(selected?.GetComponent<WorkspaceIdentity>()?.construction?.kind=="road");junctionEditButton?.SetEnabled(selected?.GetComponent<WorkspaceIdentity>()?.construction?.kind=="junction");
        if(finishRouteButton!=null)finishRouteButton.style.display=constructionTool=="roadcurve"?DisplayStyle.Flex:DisplayStyle.None;
        if(modeHeading!=null)modeHeading.text=(workspaceMode=="Lot"&&activeLot!=null?"Lot: "+activeLot.name:workspaceMode=="Asset"?"Asset editor":"World")+"  ›  "+CategoryTitle(toolCategory);
        if(toolButtons.TryGetValue("scale",out var scaleButton))scaleButton.style.display=workspaceMode=="Asset"?DisplayStyle.Flex:DisplayStyle.None;
        foreach(var pair in modeButtons)pair.Value.EnableInClassList("selected",pair.Key==workspaceMode);
        foreach(var pair in toolButtons)pair.Value.EnableInClassList("selected",!HasPlacement&&pair.Key==constructionTool);
        if(cancelToolButton!=null)cancelToolButton.style.display=HasPlacement||constructionTool!="select"?DisplayStyle.Flex:DisplayStyle.None;
        if(toolSettings!=null){toolSettings.EnableInClassList("compact-settings",toolSettings.childCount<=1);toolSettings.style.display=toolSettings.childCount>1||HasPlacement||constructionTool!="select"?DisplayStyle.Flex:DisplayStyle.None;}
        if(modeButtons.TryGetValue("Lot",out var lotButton)){bool available=activeLot!=null||SelectedLot()!=null;lotButton.SetEnabled(available);lotButton.tooltip=available?"Build on the selected or active lot":"Draw a lot in World mode first";}
        if(toolStatus!=null)toolStatus.text=(workspaceMode=="Lot"?"Floor "+floorLevel+" • ":"")+(HasPlacement?"Place object":constructionTool)+" — "+ToolInstruction();
    }
    void ResetWorldTools(){activeLot=null;activeLotId=null;floorLevel=0;CancelConstruction();if(constructionPanel!=null)SetMode("World");}
    void ReconnectWorldTools()
    {
        activeLot=null;foreach(var id in world.GetComponentsInChildren<WorkspaceIdentity>())if(id.id==activeLotId&&id.construction?.kind=="lot")activeLot=id.gameObject;
        if(activeLot==null&&workspaceMode=="Lot")SetMode("World");
    }
    void AddConstructionInspector()
    {
        var p=selected?.GetComponent<WorkspaceIdentity>()?.construction;if(p==null)return;
        Label(inspector,"EDITABLE "+p.kind.ToUpperInvariant(),"section");
        if(p.kind=="lot")Button(inspector,"Enter Lot Build Mode",EnterLot);
        if(p.kind=="junction"){Button(inspector,"Junction size and radius",()=>OpenJunctionSettings(selected));return;}
        if(p.kind=="road"){Button(inspector,"Road settings",()=>OpenRoadSettings(selected));Button(inspector,"Drag road nodes",()=>SetTool("roadnode"));Button(inspector,"Grade terrain to road",()=>GradeRoadTerrain(selected));return;}
        if(p.kind=="road"||p.kind=="wall") {
            for(int i=0;i<p.points.Length;i++) {
                int at=i;Label(inspector,"CONTROL POINT "+(i+1),"section");
                Number(inspector,"X",p.points[i].x,-2000,2000,v=>{p.points[at].x=v;RebuildConstruction(selected);Changed();});
                Number(inspector,"Y",p.points[i].y,-100,200,v=>{p.points[at].y=v;RebuildConstruction(selected);Changed();});
                Number(inspector,"Z",p.points[i].z,-2000,2000,v=>{p.points[at].z=v;RebuildConstruction(selected);Changed();});
            }
        }
        if(p.kind=="wall")Number(inspector,"Wall height",p.size.y,2,6,v=>{float previous=p.size.y;p.size.y=v;try{RebuildConstruction(selected);}catch{p.size.y=previous;throw;}Changed();});
        if(p.kind=="roof")Number(inspector,"Roof rise",p.size.y,0.2f,4,v=>{p.size.y=v;RebuildConstruction(selected);Changed();});
        if(p.kind=="water")Label(inspector,"Change Position Y to adjust the independent water level.","hint");
    }
    Slider BrushSlider(VisualElement parent,string label,float value,float min,float max,Action<float> apply)
    {
        var slider=new Slider(label,min,max){value=value,showInputField=true};parent.Add(slider);
        slider.RegisterValueChangedCallback(e=>{
            if(float.IsNaN(e.newValue)||float.IsInfinity(e.newValue)){slider.SetValueWithoutNotify(e.previousValue);return;}
            float bounded=Mathf.Clamp(e.newValue,min,max);slider.SetValueWithoutNotify(bounded);apply(bounded);
        });return slider;
    }
    FloatField Number(VisualElement parent,string label,float value,float min,float max,Action<float> apply)
    {
        var field=new FloatField(label){value=value,isDelayed=true};parent.Add(field);
        field.RegisterValueChangedCallback(e=>Try(()=>{if(float.IsNaN(e.newValue)||float.IsInfinity(e.newValue)||e.newValue<min||e.newValue>max)throw new ArgumentException(label+" must be between "+min+" and "+max);apply(e.newValue);}));
        return field;
    }
    void WorldUpdate()
    {
        if(Time.unscaledTime-lastAutosave<60||modal!=null||stroke||objectGesture||roadDrag||roadNodeDrag||constructionDrag)return;lastAutosave=Time.unscaledTime;
        if(State()==savedState)return;
        Try(()=>{Directory.CreateDirectory(Application.persistentDataPath);WorkspaceDocument.Capture(world,title).Save(RecoveryPath);Status("Recovery autosave written. Save your project normally to keep a named copy.");});
    }
    void DisposeWorldTools(){stroke=false;ClearPlacementPreview();}
}
