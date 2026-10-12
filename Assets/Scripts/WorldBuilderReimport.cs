using System;
using System.IO;
using UnityEngine;

public sealed partial class WorldBuilderRuntime
{
    void ReimportSelected()
    {
        if(selected==null){Status("Select an imported OBJ object first.");return;}
        var original=selected;var identity=original.GetComponent<WorkspaceIdentity>();string source=identity.source;
        if(string.IsNullOrEmpty(source)||!source.EndsWith(".obj",StringComparison.OrdinalIgnoreCase)||!File.Exists(source)) {
            Status("The selected object has no available OBJ source.");return;
        }
        Dialog("Reimport OBJ","Replace this object's geometry/materials from its source? Object identity and transforms are kept. Undo can restore the current version.",box=>{
            Button(box,"Reimport",()=>{
                if(original==null)throw new InvalidOperationException("Selected object no longer exists");
                var data=WorkspaceObjMaterials.Import(source,out string warning);
                data.id=identity.id;data.libraryId=identity.libraryId;data.appearanceFingerprint=identity.appearanceFingerprint;data.sourceAppearance=identity.sourceAppearance;data.baselineGeometryHash=identity.baselineGeometryHash;data.baselineAppearanceHash=identity.baselineAppearanceHash;data.position=original.transform.localPosition;
                data.rotation=original.transform.localEulerAngles;data.scale=original.transform.localScale;data.name=original.name;
                var replacement=Model(data,original.transform.parent,31);
                while(original.transform.childCount>0)original.transform.GetChild(0).SetParent(replacement.transform,false);
                original.SetActive(false);Destroy(original);selected=replacement;CloseDialog();Changed();Preview(data);
                Status(string.IsNullOrEmpty(warning)?"Reimported source; identity and transforms preserved.":"Reimported with warnings: "+warning);
            });Button(box,"Cancel",CloseDialog);
        });
    }
}
