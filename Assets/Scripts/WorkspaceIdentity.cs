using UnityEngine;
public sealed class WorkspaceIdentity : MonoBehaviour
{
    public string id, source;
    public WorldConstruction construction;
    public string libraryId;
    public WorkspaceTexture[] albedo;
    public Texture2D[] ownedTextures;
    public Mesh ownedMesh;
    public Material[] ownedMaterials;
    public Material ownedMaterial;
    void OnDestroy()
    {
        if (ownedTextures != null) foreach(var texture in ownedTextures) if(texture!=null) Destroy(texture);
        if (ownedMesh != null) Destroy(ownedMesh);
        if (ownedMaterials != null) { foreach(var material in ownedMaterials) if(material != null) Destroy(material); }
        else if (ownedMaterial != null) Destroy(ownedMaterial);
    }
}
