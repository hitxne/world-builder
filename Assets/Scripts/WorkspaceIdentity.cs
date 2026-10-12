using UnityEngine;
public sealed class WorkspaceIdentity : MonoBehaviour
{
    public string id, source;
    public Mesh ownedMesh;
    public Material ownedMaterial;
    void OnDestroy()
    {
        if (ownedMesh != null) Destroy(ownedMesh);
        if (ownedMaterial != null) Destroy(ownedMaterial);
    }
}
