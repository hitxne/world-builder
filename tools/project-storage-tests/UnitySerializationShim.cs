// Test-only data/serialization shim. Does not validate Unity SDK APIs or JsonUtility behavior.
using System;
using System.Text.Json;
namespace UnityEngine {
 public static class JsonUtility {static readonly JsonSerializerOptions options=new JsonSerializerOptions{IncludeFields=true,IgnoreReadOnlyProperties=true};public static string ToJson(object value,bool pretty=false)=>JsonSerializer.Serialize(value,value.GetType(),options);public static T FromJson<T>(string value)=>JsonSerializer.Deserialize<T>(value,options);}
 public struct Vector2 {public float x,y;public Vector2(float x,float y){this.x=x;this.y=y;}}
 public struct Vector3 {public float x,y,z;public Vector3(float x,float y,float z){this.x=x;this.y=y;this.z=z;}public static Vector3 zero=>new Vector3();public static Vector3 one=>new Vector3(1,1,1);}
 public struct Color {public float r,g,b,a;public Color(float r,float g,float b,float a=1){this.r=r;this.g=g;this.b=b;this.a=a;}public static Color gray=>new Color(.5f,.5f,.5f);public static Color white=>new Color(1,1,1);}
 public static class Mathf {public static float Abs(float v)=>Math.Abs(v);}
 public class Material {public Color color;public string name;public bool HasProperty(string n)=>false;public Color GetColor(string n)=>color;public float GetFloat(string n)=>0;}
 public class Renderer {public Material[] sharedMaterials;public Material sharedMaterial;}
 public class Transform {public Transform parent;public bool gameObjectActive;public GameObject gameObject;public Vector3 localPosition,localEulerAngles,localScale;public T GetComponent<T>()=>default;public T[] GetComponentsInChildren<T>()=>new T[0];}
 public class GameObject {public string name;public bool activeInHierarchy;public Transform transform;public T GetComponent<T>()=>default;}
 public class MeshFilter {public Mesh sharedMesh;}
 public class Mesh {public Rendering.IndexFormat indexFormat;public string name;public Vector3[] vertices,normals;public Vector2[] uv;public int[] triangles;public int subMeshCount;public int[] GetTriangles(int i)=>triangles;public void SetTriangles(int[] t,int i){}public void RecalculateNormals(){}public void RecalculateBounds(){}}
 namespace Rendering {public enum IndexFormat {UInt32}}
}
public sealed class WorkspaceIdentity {public UnityEngine.GameObject gameObject;public T GetComponent<T>()=>default;public string id,source,libraryId,appearanceFingerprint,baselineGeometryHash,baselineAppearanceHash;public WorldConstruction construction;public WorkspaceTexture[] albedo;public WorkspaceSourceAppearance sourceAppearance;}
