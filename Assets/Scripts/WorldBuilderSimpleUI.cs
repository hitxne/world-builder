using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    VisualElement startCard;
    void InitializeStartCard(Image image)
    {
        startCard=new VisualElement();startCard.AddToClassList("start-card");image.Add(startCard);
        startCard.RegisterCallback<PointerDownEvent>(e=>e.StopPropagation());
        Label(startCard,"Start your world","brand");
        Label(startCard,"Create an island, or open a saved project.","hint");
        Button(startCard,"Create island",OpenIslandSetup);
        Button(startCard,"Open project",()=>ConfirmDiscard(OpenProject));
    }
    void OpenIslandSetup()
    {
        Dialog("Create island","Set the size, then create your editable terrain.",box=>{
            Number(box,"Width (m)",islandWidth,32,512,v=>islandWidth=v);
            Number(box,"Depth (m)",islandDepth,32,512,v=>islandDepth=v);
            Number(box,"Seed",islandSeed,0,100000,v=>islandSeed=(int)v);
            Button(box,"Create island",()=>{CloseDialog();ConfirmDiscard(GenerateIsland);});
            Button(box,"Create sample neighborhood",()=>{CloseDialog();ConfirmDiscard(BuildFloridaTest);});
            Button(box,"Cancel",CloseDialog);
        });
    }
    void OpenCameraMenu()
    {
        Dialog("View","Choose your camera view.",box=>{
            Button(box,"Perspective",()=>{workCamera.orthographic=false;CloseDialog();});
            Button(box,"Top",()=>SetCameraView(new Vector2(89,0)));
            Button(box,"Front",()=>SetCameraView(new Vector2(0,0)));
            Button(box,"Side",()=>SetCameraView(new Vector2(0,90)));Button(box,"Close",CloseDialog);
        });
    }
    void OpenWorkspaceMenu()
    {
        Dialog("Menu","",box=>{
            Button(box,"Resume",CloseDialog);
            Button(box,"Project",()=>Dialog("Project","",project=>{
                Button(project,"Create island",OpenIslandSetup);Button(project,"Open project",()=>{CloseDialog();ConfirmDiscard(OpenProject);});
                Button(project,"New empty project",()=>{CloseDialog();ConfirmDiscard(NewProject);});Button(project,"Save as",()=>{CloseDialog();Save(true);});
                Button(project,"Export OBJ",()=>{CloseDialog();Export();});Button(project,"Back",OpenWorkspaceMenu);
            }));
            Button(box,"Asset library",OpenLibrary);
            Button(box,"Add Sims assets",SelectSimsExecutable);
            Button(box,"Settings",OpenAppSettings);
            Button(box,"Advanced tools",()=>Dialog("Advanced tools","",advanced=>{
                Button(advanced,"Import OBJ",()=>{CloseDialog();Import();});Button(advanced,"Reimport selected",()=>{CloseDialog();ReimportSelected();});
                Button(advanced,"Save selected to library",()=>{CloseDialog();SaveLibrary();});Button(advanced,"Game resource browser",GameBrowser);
                Button(advanced,"Back",OpenWorkspaceMenu);
            }));
        });
    }
    void OpenAppSettings()
    {
        Dialog("Settings","Changes are saved automatically.",box=>{
            var layout=Row(box,"settings-layout");var tabs=new VisualElement();tabs.AddToClassList("settings-navigation");layout.Add(tabs);var body=new VisualElement();body.AddToClassList("settings-content");layout.Add(body);
            var buttons=new System.Collections.Generic.Dictionary<string,Button>();
            void Show(string category) {
                foreach(var entry in buttons)entry.Value.EnableInClassList("selected",entry.Key==category);
                body.Clear();Label(body,category,"section");
                if(category=="Appearance") {
                    var themes=new System.Collections.Generic.List<string>{"Dark","Light","High contrast"};var field=new DropdownField("Theme",themes,theme);body.Add(field);
                    field.RegisterValueChangedCallback(e=>{theme=themes.IndexOf(e.newValue);ApplyTheme();PlayerPrefs.SetInt("worldbuilder.theme",theme);PlayerPrefs.Save();});
                    var size=new Slider("UI size",0.8f,1.5f){value=panel.scale,showInputField=true};body.Add(size);size.RegisterValueChangedCallback(e=>{if(float.IsNaN(e.newValue)||float.IsInfinity(e.newValue)){size.SetValueWithoutNotify(e.previousValue);return;}panel.scale=Mathf.Clamp(e.newValue,0.8f,1.5f);PlayerPrefs.SetFloat("worldbuilder.uiScale",panel.scale);PlayerPrefs.Save();});
                } else if(category=="Workspace") {
                    var scene=new Toggle("Scene objects panel"){value=sceneVisible};body.Add(scene);scene.RegisterValueChangedCallback(e=>{sceneVisible=e.newValue;sceneDrawer=e.newValue;SaveLayout();ApplyLayout();});
                    var properties=new Toggle("Properties panel"){value=propertiesVisible};body.Add(properties);properties.RegisterValueChangedCallback(e=>{propertiesVisible=e.newValue;propertiesDrawer=e.newValue;SaveLayout();ApplyLayout();});
                    Button(body,"Panel sizes and restore defaults",OpenLayoutSettings);
                } else if(category=="Editing") {
                    var snap=new Toggle("Grid snapping"){value=gridEnabled};body.Add(snap);snap.RegisterValueChangedCallback(e=>{gridEnabled=e.newValue;PlayerPrefs.SetInt("worldbuilder.gridEnabled",gridEnabled?1:0);PlayerPrefs.Save();RefreshWorldTools();});
                    Number(body,"Grid (m)",gridSize,0.25f,5,v=>{gridSize=v;PlayerPrefs.SetFloat("worldbuilder.gridSize",v);PlayerPrefs.Save();});Number(body,"Wall height (m)",wallHeight,2,6,v=>{wallHeight=v;PlayerPrefs.SetFloat("worldbuilder.wallHeight",v);PlayerPrefs.Save();});
                } else if(category=="Graphics") {
                    var names=new System.Collections.Generic.List<string>(QualitySettings.names);
                    if(names.Count>0){var quality=new DropdownField("Quality",names,Mathf.Clamp(QualitySettings.GetQualityLevel(),0,names.Count-1));body.Add(quality);quality.RegisterValueChangedCallback(e=>{int at=names.IndexOf(e.newValue);if(at>=0){QualitySettings.SetQualityLevel(at,true);PlayerPrefs.SetInt("worldbuilder.quality",at);PlayerPrefs.Save();}});}
                    Label(body,"These are the configured Unity quality levels. Large-world streaming is not implemented yet.","hint");
                } else Label(body,"Left click Select/build • Right drag Pan • Middle drag Orbit • Wheel Zoom\nH Move • E Copy • K Delete • R Properties • B Wall\nComma/period Rotate • Alt Free placement • Shift Repeat\nG Snap • F5 Grid spacing • Brackets Brush size\nPageUp/PageDown Floor • T Top view • F Focus\nCtrl+S Save • Ctrl+Z Undo • Ctrl+Y Redo • Esc Cancel","hint");
            }
            foreach(string category in new[]{"Appearance","Workspace","Editing","Graphics","Controls"}){string name=category;buttons[name]=Button(tabs,name,()=>Show(name));}
            Show("Appearance");Button(box,"Done",CloseDialog);
        });
    }
}
