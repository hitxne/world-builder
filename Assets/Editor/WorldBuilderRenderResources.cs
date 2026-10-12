#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.UIElements;

// Canonical shader references prevent Shader.Find-only materials being stripped
// from standalone builds. Generated assets are isolated from user scene data.
public static class WorldBuilderRenderResources
{
    [InitializeOnLoadMethod]
    static void Schedule()=>EditorApplication.delayCall+=Ensure;
    public static void Ensure()
    {
        const string folder="Assets/WorldBuilderGenerated/Resources";
        if(!Directory.Exists(folder)){Directory.CreateDirectory(folder);AssetDatabase.Refresh();}
        // TSS imports Unity's control geometry/fonts; Workspace.uss supplies our tokens.
        const string themePath=folder+"/WorldBuilderRuntimeTheme.tss";
        if(!File.Exists(themePath))File.WriteAllText(themePath,"@import url(\"unity-theme://default\");\n");
        AssetDatabase.ImportAsset(themePath,ImportAssetOptions.ForceUpdate);
        if(AssetDatabase.LoadAssetAtPath<ThemeStyleSheet>(themePath)==null)
            throw new System.InvalidOperationException("World Builder runtime theme could not be imported: "+themePath);
        foreach(string name in new[]{"Standard","HDRP/Lit","Universal Render Pipeline/Lit"}) {
            string file=name=="Standard"?"WorldBuilderDefault":name=="HDRP/Lit"?"WorldBuilderHDRP":"WorldBuilderURP";
            string path=folder+"/"+file+".mat";
            if(File.Exists(path))continue;
            var shader=Shader.Find(name);if(shader!=null)AssetDatabase.CreateAsset(new Material(shader),path);
        }
        AssetDatabase.SaveAssets();
    }
}
#endif
