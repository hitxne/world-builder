#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;

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
