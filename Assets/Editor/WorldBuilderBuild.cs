#if UNITY_EDITOR
using System;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

public static class WorldBuilderBuild
{
    [MenuItem("World Builder/Build Windows Release")]
    public static void WindowsRelease()=>Build(false);
    [MenuItem("World Builder/Build Windows Development")]
    public static void WindowsDevelopment()=>Build(true);
    static void Build(bool development)
    {
        WorldBuilderRenderResources.Ensure();
        // Generate a separate build-only scene; never overwrite the user's saved scene.
        const string startup = "Assets/WorldBuilderGenerated/Startup.unity";
        System.IO.Directory.CreateDirectory("Assets/WorldBuilderGenerated");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
        EditorSceneManager.SaveScene(scene, startup);
        EditorSceneManager.CloseScene(scene, true);
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { startup },
            locationPathName = development?"Builds/WindowsDevelopment/WorldBuilder.exe":"Builds/Windows/WorldBuilder.exe",
            target = BuildTarget.StandaloneWindows64, options = development?BuildOptions.Development|BuildOptions.AllowDebugging:BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new InvalidOperationException("Windows build failed: " + report.summary.result);
        string folder=development?"Builds/WindowsDevelopment":"Builds/Windows";
        System.IO.File.WriteAllText(folder+"/README.txt","World Builder — world/lot construction development milestone.\nRun WorldBuilder.exe with every companion file in this folder. Unity Editor is not required for the player.\nSave .wbworld inside the app; consult repository docs/WORLD-LOT-MILESTONE.md for capabilities and limitations.\n");
        string archive="Builds/WorldBuilder-Windows-"+(development?"dev-":"release-")+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+".zip";
        System.IO.Compression.ZipFile.CreateFromDirectory(folder,archive);
        UnityEngine.Debug.Log("Windows build and complete ZIP created: "+archive);
    }
}
#endif
