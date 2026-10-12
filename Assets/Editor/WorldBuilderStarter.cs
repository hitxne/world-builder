#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class WorldBuilderStarter
{
    [MenuItem("World Builder/Create Starter Scene")]
    public static void Create()
    {
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = new GameObject("World Builder Runtime");
        root.AddComponent<WorldBuilderRuntime>();
        EditorSceneManager.MarkSceneDirty(scene);
        System.IO.Directory.CreateDirectory("Assets/Scenes");
        EditorSceneManager.SaveScene(scene, "Assets/Scenes/AssetCreator.unity");
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene("Assets/Scenes/AssetCreator.unity", true) };
        Debug.Log("World Builder Asset Creator scene created. Press Play to begin.");
    }
}
#endif
