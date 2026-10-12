#if UNITY_EDITOR
using System;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

public static class WorldBuilderBuild
{
    [MenuItem("World Builder/Build Windows Release")]
    public static void WindowsRelease()
    {
        // Generate a separate build-only scene; never overwrite the user's saved scene.
        const string startup = "Assets/WorldBuilderGenerated/Startup.unity";
        System.IO.Directory.CreateDirectory("Assets/WorldBuilderGenerated");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
        EditorSceneManager.SaveScene(scene, startup);
        EditorSceneManager.CloseScene(scene, true);
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { startup },
            locationPathName = "Builds/Windows/WorldBuilder.exe",
            target = BuildTarget.StandaloneWindows64, options = BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new InvalidOperationException("Windows build failed: " + report.summary.result);
    }
}
#endif
