using System;

// Engine-independent editable source data. Generated Unity meshes are derived output.
[Serializable]
public struct WorldPoint
{
    public float x, y, z;
    public WorldPoint(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    public static WorldPoint operator +(WorldPoint a, WorldPoint b) => new WorldPoint(a.x+b.x,a.y+b.y,a.z+b.z);
    public static WorldPoint operator -(WorldPoint a, WorldPoint b) => new WorldPoint(a.x-b.x,a.y-b.y,a.z-b.z);
    public static WorldPoint operator *(WorldPoint a, float b) => new WorldPoint(a.x*b,a.y*b,a.z*b);
    public float Length => (float)Math.Sqrt(x*x+y*y+z*z);
    public WorldPoint Unit => Length < 0.000001f ? new WorldPoint(1,0,0) : this * (1/Length);
}
[Serializable]
public sealed class WorldOpening
{
    public string kind;
    public float center, width = 1, bottom, height = 2.1f;
}
[Serializable]
public sealed class WorldConstruction
{
    public string kind;
    public WorldPoint size = new WorldPoint(10,3,10);
    public WorldPoint[] points = new WorldPoint[0];
    public WorldOpening[] openings = new WorldOpening[0];
    public int resolution = 65, seed = 1337, openingIndex = -1;
    public float[] heights;
    public int[] paint;
    public float width = 6, sidewalk = 1.2f, waterLevel = 1;
    public string surface = "asphalt";
    public float friction = 1;
}
public sealed class WorldGeometryMesh
{
    public WorldPoint[] vertices;
    public float[] uv;
    public int[][] groups;
}
