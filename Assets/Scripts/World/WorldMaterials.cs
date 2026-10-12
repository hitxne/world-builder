using UnityEngine;

// Shared material palette for construction, the inspector and procedural defaults.
public static class WorldMaterials
{
    public static readonly string[] Names={"Asphalt","Concrete","Brick","Stucco","Wood","Glass","Metal","Plastic","Stone","Sand","Grass","Soil","Mud","Water"};
    public static Color Color(string name)
    {
        switch(name) {
            case "Asphalt":return new Color(0.11f,0.12f,0.14f);
            case "Concrete":return new Color(0.57f,0.59f,0.61f);
            case "Brick":return new Color(0.55f,0.23f,0.14f);
            case "Wood":return new Color(0.36f,0.25f,0.12f);
            case "Glass":return new Color(0.28f,0.53f,0.65f);
            case "Metal":return new Color(0.65f,0.68f,0.7f);
            case "Plastic":return new Color(0.25f,0.3f,0.35f);
            case "Stone":return new Color(0.5f,0.48f,0.43f);
            case "Sand":return new Color(0.77f,0.68f,0.45f);
            case "Grass":return new Color(0.2f,0.4f,0.19f);
            case "Soil":return new Color(0.3f,0.22f,0.14f);
            case "Mud":return new Color(0.17f,0.14f,0.09f);
            case "Water":return new Color(0.06f,0.35f,0.5f);
            default:return new Color(0.8f,0.75f,0.64f);
        }
    }
    public static Color[] Road(WorldConstruction p)
    {
        string surface=p.surface=="concrete"?"Concrete":p.surface=="dirt"?"Soil":p.surface=="gravel"?"Stone":"Asphalt";
        return new[]{Color(surface),Color("Concrete"),p.oneWay?UnityEngine.Color.white:new Color(0.94f,0.84f,0.35f),UnityEngine.Color.white,Color("Concrete")};
    }
    public static Color[] Construction(string kind)
    {
        if(kind=="terrain")return new[]{Color("Grass"),Color("Sand"),Color("Grass")};
        if(kind=="road")return new[]{Color("Asphalt"),Color("Concrete"),new Color(0.94f,0.84f,0.35f)};
        if(kind=="water")return new[]{Color("Water"),UnityEngine.Color.white,UnityEngine.Color.white};
        if(kind=="tree")return new[]{Color("Wood"),Color("Grass"),Color("Grass")};
        if(kind=="lot")return new[]{new Color(0.85f,0.7f,0.28f),UnityEngine.Color.white,UnityEngine.Color.white};
        if(kind=="roof")return new[]{Color("Brick"),Color("Stucco"),UnityEngine.Color.white};
        if(kind=="window")return new[]{UnityEngine.Color.white,Color("Glass"),UnityEngine.Color.white};
        return new[]{Color("Stucco"),Color("Concrete"),UnityEngine.Color.white};
    }
}
