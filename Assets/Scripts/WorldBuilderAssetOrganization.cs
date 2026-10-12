using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UIElements;

public sealed partial class WorldBuilderRuntime
{
    static readonly string[] AssetRooms={"Unclassified","Living room","Kitchen","Bedroom","Bathroom","Office","Outdoors","Other"};
    static readonly string[] AssetTypes={"Unclassified","Seating","Tables","Beds","Storage","Lighting","Decor","Doors","Windows","Plants","Buildings","Other"};
    LibraryMetadata ReadAssetMetadata(string path)
    {
        string file=path+".metadata.json";return File.Exists(file)?JsonUtility.FromJson<LibraryMetadata>(File.ReadAllText(file)):null;
    }
    void OpenAssetOrganization(string path,bool returnToLibrary)
    {
        var metadata=ReadAssetMetadata(path)??new LibraryMetadata{name=WorkspaceDocument.Open(path).title};
        Dialog("Organize asset","Categories are your library labels. Game catalog categories have not been decoded; unclassified objects are not guessed.",box=>{
            var name=new TextField("Name"){value=metadata.name};box.Add(name);
            var room=new DropdownField("Room",new List<string>(AssetRooms),Mathf.Max(0,Array.IndexOf(AssetRooms,metadata.room)));box.Add(room);
            var category=new DropdownField("Type",new List<string>(AssetTypes),Mathf.Max(0,Array.IndexOf(AssetTypes,metadata.category)));box.Add(category);
            Button(box,"Save",()=>{if(string.IsNullOrWhiteSpace(name.value))throw new ArgumentException("Asset name is required");metadata.name=name.value.Trim();metadata.room=room.value;metadata.category=category.value;WorkspaceAtomicFile.Write(path+".metadata.json",JsonUtility.ToJson(metadata,true));OpenLibraryPreview(path,returnToLibrary);});
            Button(box,"Cancel",()=>OpenLibraryPreview(path,returnToLibrary));
        });
    }
}
