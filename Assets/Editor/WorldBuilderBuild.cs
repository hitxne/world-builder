#if UNITY_EDITOR
using System;
using UnityEditor;
using UnityEditor.Build.Reporting;

public static class WorldBuilderBuild
{
    [MenuItem("World Builder/Build Windows Release")]
    public static void WindowsRelease()
    {
        // Scene generation is explicit at build time, never on editor load.
        WorldBuilderStarter.Create();
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { "Assets/Scenes/AssetCreator.unity" },
            locationPathName = "Builds/Windows/WorldBuilder.exe",
            target = BuildTarget.StandaloneWindows64, options = BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new InvalidOperationException("Windows build failed: " + report.summary.result);
    }
}
#endif
