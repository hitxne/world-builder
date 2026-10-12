using System;
using System.Linq;
using System.Text;
using UnityEngine;

// Conservative update policy: unknown provenance is not permission to overwrite local edits.
public static class WorkspaceAssetUpdate
{
    [Serializable] sealed class Shape {public Vector3[] vertices;public int[] triangles;}
    [Serializable] sealed class Appearance {public Color[] colors;public string[] textures;}
    public static string GeometryHash(WorkspaceProject item)=>WorkspaceBlobStore.Hash(Encoding.UTF8.GetBytes(JsonUtility.ToJson(new Shape{vertices=item.vertices,triangles=item.triangles})));
    public static string AppearanceHash(WorkspaceProject item)=>WorkspaceBlobStore.Hash(Encoding.UTF8.GetBytes(JsonUtility.ToJson(new Appearance{colors=item.materialColors,textures=(item.albedo??new WorkspaceTexture[0]).Select(t=>t==null?null:!string.IsNullOrEmpty(t.base64)?WorkspaceBlobStore.Hash(Convert.FromBase64String(t.base64)):t.blob).ToArray()})));
    public static void Baseline(WorkspaceProject item){item.baselineGeometryHash=GeometryHash(item);item.baselineAppearanceHash=AppearanceHash(item);}
    public static string Merge(WorkspaceProject current,WorkspaceProject incoming)
    {
        string beforeShape=GeometryHash(current),beforeAppearance=AppearanceHash(current),incomingShape=GeometryHash(incoming);
        bool geometryEdited=!string.IsNullOrEmpty(current.baselineGeometryHash)?beforeShape!=current.baselineGeometryHash:beforeShape!=incomingShape;
        bool appearanceEdited=!string.IsNullOrEmpty(current.baselineAppearanceHash)?beforeAppearance!=current.baselineAppearanceHash:
            (current.materialColors??new Color[0]).Any(c=>Math.Abs(c.r-0.65f)>0.001f||Math.Abs(c.g-0.72f)>0.001f||Math.Abs(c.b-0.78f)>0.001f);
        bool compatible=current.vertices?.Length==incoming.vertices?.Length&&current.triangles!=null&&incoming.triangles!=null&&current.triangles.SequenceEqual(incoming.triangles);
        bool materialLayoutChanged=(current.submeshes?.Length??1)!=(incoming.submeshes?.Length??1);
        if((geometryEdited&&!compatible)||(appearanceEdited&&materialLayoutChanged)) {
            current.sourceAppearance=incoming.sourceAppearance;current.appearanceFingerprint=incoming.appearanceFingerprint;
            return "Local topology/material layout retained. Updated source appearance is available, but needs manual remapping.";
        }
        var vertices=current.vertices;var normals=current.normals;var colors=current.materialColors;var albedo=current.albedo;
        current.vertices=incoming.vertices;current.normals=incoming.normals;current.uv=incoming.uv;current.triangles=incoming.triangles;current.submeshes=incoming.submeshes;
        current.materialColors=incoming.materialColors;current.materialNames=incoming.materialNames;current.albedo=incoming.albedo;
        current.sourceAppearance=incoming.sourceAppearance;current.appearanceFingerprint=incoming.appearanceFingerprint;
        current.baselineGeometryHash=incoming.baselineGeometryHash??incomingShape;current.baselineAppearanceHash=incoming.baselineAppearanceHash??AppearanceHash(incoming);
        if(geometryEdited){current.vertices=vertices;current.normals=normals;}
        if(appearanceEdited){current.materialColors=colors;current.albedo=albedo;}
        return geometryEdited||appearanceEdited?"Local geometry/material edits retained during source appearance update.":"";
    }
}
