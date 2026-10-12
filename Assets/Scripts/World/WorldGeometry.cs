using System;
using System.Collections.Generic;

// No Unity/editor dependencies: geometry is testable on an ordinary .NET runtime.
public static class WorldGeometry
{
    const float Pi = (float)Math.PI;
    static float Clamp(float x, float lo, float hi) => Math.Max(lo, Math.Min(hi,x));
    public static bool IntersectsXZ(WorldPoint minA,WorldPoint maxA,WorldPoint minB,WorldPoint maxB)
        =>minA.x<=maxB.x&&maxA.x>=minB.x&&minA.z<=maxB.z&&maxA.z>=minB.z;
    public static WorldConstruction Island(float width, float depth, int seed, int resolution = 65)
    {
        if (width < 10 || depth < 10 || width > 2000 || depth > 2000 || resolution < 9 || resolution > 129)
            throw new ArgumentException("Island dimensions/resolution outside editing limits.");
        var p = new WorldConstruction { kind="terrain", size=new WorldPoint(width,10,depth), seed=seed, resolution=resolution,
            heights=new float[resolution*resolution], paint=new int[(resolution-1)*(resolution-1)] };
        for (int z=0; z<resolution; z++) for (int x=0; x<resolution; x++) {
            float nx=x/(float)(resolution-1)*2-1, nz=z/(float)(resolution-1)*2-1;
            float angle=(float)Math.Atan2(nz,nx), radius=(float)Math.Sqrt(nx*nx+nz*nz);
            float coast=0.76f+0.06f*(float)Math.Sin(angle*5+seed)+0.035f*(float)Math.Cos(angle*9-seed);
            float distance=coast-radius;
            float inland=Clamp(distance*15,-2,7);
            float variation=Clamp((distance-0.12f)*4,0,1)*(float)(Math.Sin(nx*11+seed)*Math.Cos(nz*9-seed))*0.8f;
            p.heights[z*resolution+x]=inland+variation;
            if (x<resolution-1 && z<resolution-1) p.paint[z*(resolution-1)+x]=inland<2.8f ? 1 : 0;
        }
        return p;
    }
    public static float Height(WorldConstruction p, float x, float z)
    {
        CheckTerrain(p); int n=p.resolution;
        float gx=Clamp((x/p.size.x+0.5f)*(n-1),0,n-1), gz=Clamp((z/p.size.z+0.5f)*(n-1),0,n-1);
        int ix=Math.Min(n-2,(int)gx), iz=Math.Min(n-2,(int)gz); float tx=gx-ix,tz=gz-iz;
        float a=p.heights[iz*n+ix]*(1-tx)+p.heights[iz*n+ix+1]*tx;
        float b=p.heights[(iz+1)*n+ix]*(1-tx)+p.heights[(iz+1)*n+ix+1]*tx;
        return a*(1-tz)+b*tz;
    }
    public static void Brush(WorldConstruction p, WorldPoint center, float radius, float strength, string operation, float targetHeight)
    {
        CheckTerrain(p);
        if (radius <= 0 || float.IsNaN(strength) || float.IsInfinity(strength)) throw new ArgumentException("Invalid brush.");
        int n=p.resolution; float[] before=(float[])p.heights.Clone();
        for (int z=0;z<n;z++) for(int x=0;x<n;x++) {
            float px=(x/(float)(n-1)-0.5f)*p.size.x, pz=(z/(float)(n-1)-0.5f)*p.size.z;
            float dx=px-center.x,dz=pz-center.z,d=(float)Math.Sqrt(dx*dx+dz*dz);
            if(d>radius)continue; float falloff=1-d/radius; int at=z*n+x;
            if(operation=="raise")p.heights[at]+=strength*falloff;
            else if(operation=="lower")p.heights[at]-=strength*falloff;
            else if(operation=="flatten")p.heights[at]+=(targetHeight-p.heights[at])*Clamp(strength*falloff,0,1);
            else if(operation=="smooth") {
                float total=0; int count=0;
                for(int zz=Math.Max(0,z-1);zz<=Math.Min(n-1,z+1);zz++)for(int xx=Math.Max(0,x-1);xx<=Math.Min(n-1,x+1);xx++){total+=before[zz*n+xx];count++;}
                p.heights[at]+=(total/count-before[at])*Clamp(strength*falloff,0,1);
            } else if(operation=="sand" || operation=="grass") {
                if(x<n-1&&z<n-1)p.paint[z*(n-1)+x]=operation=="sand"?1:0;
            } else throw new ArgumentException("Unknown terrain brush.");
            p.heights[at]=Clamp(p.heights[at],-100,200);
        }
    }
    public static void FlattenRectangle(WorldConstruction p,float x0,float x1,float z0,float z1,float height)
    {
        CheckTerrain(p);
        if(x0>=x1||z0>=z1||float.IsNaN(height)||float.IsInfinity(height))throw new ArgumentException("Invalid lot grading rectangle.");
        int n=p.resolution;
        for(int z=0;z<n;z++)for(int x=0;x<n;x++) {
            float px=(x/(float)(n-1)-0.5f)*p.size.x,pz=(z/(float)(n-1)-0.5f)*p.size.z;
            float dx=Math.Max(x0-px,Math.Max(0,px-x1)),dz=Math.Max(z0-pz,Math.Max(0,pz-z1));
            float outside=(float)Math.Sqrt(dx*dx+dz*dz);if(outside>2)continue;
            float weight=1-outside/2;int at=z*n+x;p.heights[at]+=(height-p.heights[at])*weight;
        }
    }
    static void CheckTerrain(WorldConstruction p)
    {
        if(p==null||p.resolution<2||p.resolution>129||p.size.x<=0||p.size.z<=0||p.heights==null||p.heights.Length!=p.resolution*p.resolution
            ||p.paint==null||p.paint.Length!=(p.resolution-1)*(p.resolution-1))throw new ArgumentException("Invalid heightfield source.");
    }
    public static WorldGeometryMesh Build(WorldConstruction p)
    {
        if(p==null||p.kind==null)throw new ArgumentException("Missing construction source.");
        var b=new Builder(p.kind=="road"||p.kind=="junction"?5:3);
        if(p.kind=="terrain") {
            CheckTerrain(p); int n=p.resolution;
            for(int z=0;z<n;z++)for(int x=0;x<n;x++)b.Vertex(new WorldPoint((x/(float)(n-1)-0.5f)*p.size.x,p.heights[z*n+x],(z/(float)(n-1)-0.5f)*p.size.z),x/(float)(n-1)*20,z/(float)(n-1)*20);
            for(int z=0;z<n-1;z++)for(int x=0;x<n-1;x++) {
                int a=z*n+x,group=p.paint[z*(n-1)+x]; if(group<0||group>1)throw new ArgumentException("Invalid terrain paint layer.");
                b.Triangle(a,a+n,a+1,group);b.Triangle(a+1,a+n,a+n+1,group);
            }
        } else if(p.kind=="road") Road(p,b);
        else if(p.kind=="junction") Junction(p,b);
        else if(p.kind=="wall") Wall(p,b);
        else if(p.kind=="roof") Roof(p,b);
        else if(p.kind=="door"||p.kind=="window") Frame(p,b);
        else if(p.kind=="lot") {
            Box(b,new WorldPoint(0,0,-p.size.z/2),new WorldPoint(p.size.x,0.08f,0.12f),0);
            Box(b,new WorldPoint(0,0,p.size.z/2),new WorldPoint(p.size.x,0.08f,0.12f),0);
            Box(b,new WorldPoint(-p.size.x/2,0,0),new WorldPoint(0.12f,0.08f,p.size.z),0);
            Box(b,new WorldPoint(p.size.x/2,0,0),new WorldPoint(0.12f,0.08f,p.size.z),0);
        } else if(p.kind=="water") {
            float x=p.size.x/2,z=p.size.z/2;
            b.Quad(new WorldPoint(-x,0,-z),new WorldPoint(-x,0,z),new WorldPoint(x,0,z),new WorldPoint(x,0,-z),0);
        } else if(p.kind=="floor"||p.kind=="foundation") Box(b,new WorldPoint(0,-p.size.y/2,0),p.size,0);
        else if(p.kind=="tree") Tree(p,b);
        else if(p.kind=="stairs") {
            int steps=Math.Max(2,Math.Min(40,(int)(p.size.y/0.2f)));
            for(int i=0;i<steps;i++){float height=p.size.y*(i+1)/steps;Box(b,new WorldPoint(0,height/2,-p.size.z/2+p.size.z*(i+0.5f)/steps),new WorldPoint(p.size.x,height,p.size.z/steps),0);}
        } else throw new ArgumentException("Unknown construction type: "+p.kind);
        return b.Result();
    }
    static WorldPoint Catmull(WorldPoint a,WorldPoint b,WorldPoint c,WorldPoint d,float t)
    {
        float t2=t*t,t3=t2*t;
        return (b*2+(c-a)*t+(a*2-b*5+c*4-d)*t2+(b*3-a-c*3+d)*t3)*0.5f;
    }
    // Project every generated strip vertex, not just sparse spline control points.
    // The callback supports transformed terrain/roads and preserves uncovered spans.
    public static void ConformRoad(WorldGeometryMesh mesh,Func<WorldPoint,float,WorldPoint?> project)
    {
        if(mesh==null||project==null)throw new ArgumentNullException();
        var original=(WorldPoint[])mesh.vertices.Clone();
        for(int group=0;group<mesh.groups.Length;group++) {
            float clearance=group==1?0.15f:group==2?0.07f:0.05f;
            var visited=new HashSet<int>();
            foreach(int index in mesh.groups[group])if(visited.Add(index)) {
                float offset=mesh.roadClearance!=null&&index<mesh.roadClearance.Length&&!float.IsNaN(mesh.roadClearance[index])?mesh.roadClearance[index]:clearance;
                var result=project(original[index],offset);
                if(result.HasValue)mesh.vertices[index]=result.Value;
            }
        }
    }
    static void CheckJunction(WorldConstruction p)
    {
        foreach(float value in new[]{p.size.x,p.size.z,p.junctionRadius,p.elevationOffset})if(float.IsNaN(value)||float.IsInfinity(value))throw new ArgumentException("Invalid junction value");
        if(p.size.x<4||p.size.z<4||p.size.x>100||p.size.z>100||p.junctionRadius<0||p.junctionRadius>Math.Min(p.size.x,p.size.z)/2)throw new ArgumentException("Invalid junction size or radius");
    }
    public static WorldPoint JunctionPort(WorldConstruction p,int port,float offset,float roadWidth)
    {
        CheckJunction(p);if(float.IsNaN(offset)||float.IsInfinity(offset)||float.IsNaN(roadWidth)||float.IsInfinity(roadWidth)||port<0||port>3||roadWidth<=0)throw new ArgumentException("Invalid junction connection");
        float limit=(port%2==0?p.size.x:p.size.z)/2-p.junctionRadius-roadWidth/2;
        if(limit<0)throw new ArgumentException("Widen the junction or reduce its radius to fit this road");
        offset=Math.Max(-limit,Math.Min(limit,offset));
        return port==0?new WorldPoint(offset,p.elevationOffset,p.size.z/2):port==1?new WorldPoint(p.size.x/2,p.elevationOffset,offset):port==2?new WorldPoint(offset,p.elevationOffset,-p.size.z/2):new WorldPoint(-p.size.x/2,p.elevationOffset,offset);
    }
    static void Junction(WorldConstruction p,Builder b)
    {
        CheckJunction(p);var outline=new List<WorldPoint>();float x=p.size.x/2,z=p.size.z/2,r=p.junctionRadius,y=p.elevationOffset+0.05f;
        if(r==0){outline.Add(new WorldPoint(x,y,z));outline.Add(new WorldPoint(-x,y,z));outline.Add(new WorldPoint(-x,y,-z));outline.Add(new WorldPoint(x,y,-z));}
        else for(int corner=0;corner<4;corner++)for(int step=0;step<=12;step++) {
            float angle=(corner*90+step*90f/12)*(float)Math.PI/180,cx=corner==0||corner==3?x-r:-x+r,cz=corner<2?z-r:-z+r;
            outline.Add(new WorldPoint(cx+r*(float)Math.Cos(angle),y,cz+r*(float)Math.Sin(angle)));
        }
        var center=new WorldPoint(0,y,0);for(int i=0;i<outline.Count;i++)b.Face(center,outline[(i+1)%outline.Count],outline[i],0,y);
    }
    public static List<WorldPoint> RoadSamples(WorldConstruction p)
    {
        foreach(float value in new[]{p.width,p.sidewalk,p.shoulderLeft,p.shoulderRight,p.median,p.banking,p.elevationOffset,p.friction,p.speedLimitMph})if(float.IsNaN(value)||float.IsInfinity(value))throw new ArgumentException("Invalid road value");
        if(p.points==null||p.points.Length<2||p.points.Length>256||p.width<1||p.width>40||p.sidewalk<0||p.sidewalk>10
            ||p.lanes<0||p.lanes>8||p.markings<0||p.markings>3||p.subdivisions<0||p.subdivisions>64||p.curveMode<0||p.curveMode>1
            ||p.shoulderLeft<0||p.shoulderLeft>10||p.shoulderRight<0||p.shoulderRight>10||p.median<0||p.median>=p.width
            ||p.banking<-30||p.banking>30||p.elevationOffset<-100||p.elevationOffset>200)throw new ArgumentException("Invalid road cross-section or spline");
        foreach(var point in p.points)if(float.IsNaN(point.x)||float.IsNaN(point.y)||float.IsNaN(point.z)||float.IsInfinity(point.x)||float.IsInfinity(point.y)||float.IsInfinity(point.z))throw new ArgumentException("Invalid road point");
        var samples=new List<WorldPoint>();int steps=p.subdivisions==0?12:p.subdivisions;
        for(int i=0;i<p.points.Length-1;i++)for(int s=0;s<steps;s++)samples.Add(p.curveMode==1?p.points[i]+(p.points[i+1]-p.points[i])*(s/(float)steps):Catmull(p.points[Math.Max(0,i-1)],p.points[i],p.points[i+1],p.points[Math.Min(p.points.Length-1,i+2)],s/(float)steps));
        samples.Add(p.points[p.points.Length-1]);float length=0;for(int i=0;i<samples.Count-1;i++){var delta=samples[i+1]-samples[i];length+=(float)Math.Sqrt(delta.x*delta.x+delta.z*delta.z);}
        if(length<0.1f)throw new ArgumentException("Road points must span at least 0.1 m");return samples;
    }
    static void Road(WorldConstruction p,Builder b)
    {
        var samples=RoadSamples(p);int lanes=p.lanes==0?2:p.lanes;if(p.lanes>0&&((p.width-p.median)/lanes<0.5f||(p.width-p.median)/lanes>8))throw new ArgumentException("Lane width must be between 0.5 and 8 m");float bank=(float)Math.Tan(p.banking*Math.PI/180),distance=0;
        if(!p.oneWay&&lanes%2!=0)throw new ArgumentException("Two-way roads need an even lane count; enable one-way for odd counts");
        if(p.median>0&&(lanes%2!=0||p.oneWay))throw new ArgumentException("A median requires an even number of two-way lanes");
        for(int i=0;i<samples.Count-1;i++) {
            WorldPoint a=samples[i],c=samples[i+1],direction=c-a;direction.y=0;float length=direction.Length;
            if(length<0.0001f)continue;var right=new WorldPoint(direction.z,0,-direction.x).Unit;
            void Surface(float left,float rightEdge,int group,float up)=>RoadStrip(b,a,c,right,left,rightEdge,group,up+p.elevationOffset,bank);
            if(p.median==0)Surface(-p.width/2,p.width/2,0,0.05f);
            else {Surface(-p.width/2,-p.median/2,0,0.05f);Surface(p.median/2,p.width/2,0,0.05f);Surface(-p.median/2,p.median/2,4,0.2f);}
            if(p.shoulderLeft>0)Surface(-p.width/2-p.shoulderLeft,-p.width/2,0,0.05f);
            if(p.shoulderRight>0)Surface(p.width/2,p.width/2+p.shoulderRight,0,0.05f);
            if(p.sidewalk>0){Surface(-p.width/2-p.shoulderLeft-p.sidewalk,-p.width/2-p.shoulderLeft,1,0.15f);Surface(p.width/2+p.shoulderRight,p.width/2+p.shoulderRight+p.sidewalk,1,0.15f);}
            void Line(float at,int group,bool dashed) {
                if(!dashed){Surface(at-0.05f,at+0.05f,group,0.07f);return;}
                float cursor=0;
                while(cursor<length){float phase=(distance+cursor)%12,run=Math.Min(length-cursor,phase<6?6-phase:12-phase);if(run<0.00001f)run=Math.Min(0.0001f,length-cursor);
                    if(phase<6)RoadStrip(b,a+(c-a)*(cursor/length),a+(c-a)*((cursor+run)/length),right,at-0.05f,at+0.05f,group,0.07f+p.elevationOffset,bank);cursor+=run;}
            }
            if(p.markings!=1) {
                if(!p.oneWay&&p.median==0){if(p.markings==3){Line(-0.12f,2,false);Line(0.12f,2,false);}else Line(0,2,p.markings==0);}
                if(lanes>2||p.oneWay)for(int lane=1;lane<lanes;lane++) {
                    float laneWidth=(p.width-p.median)/lanes;float at=p.median>0&&lane>lanes/2?p.median/2+laneWidth*(lane-lanes/2):-p.width/2+laneWidth*lane;
                    if(!p.oneWay&&lane==lanes/2)continue;if(Math.Abs(at)<p.median/2)continue;Line(at,3,true);
                }
                if(p.edgeLines){Line(-p.width/2+0.12f,3,false);Line(p.width/2-0.12f,3,false);}
            }distance+=length;
        }
    }
    static void RoadStrip(Builder b,WorldPoint a,WorldPoint c,WorldPoint r,float left,float right,int group,float up,float bank)
    {
        float low=up+bank*left,high=up+bank*right;
        b.Quad(a+r*left+new WorldPoint(0,low,0),c+r*left+new WorldPoint(0,low,0),c+r*right+new WorldPoint(0,high,0),a+r*right+new WorldPoint(0,high,0),group,new[]{low,low,high,high});
    }
    public static void GradeRoadTerrain(WorldConstruction terrain,WorldConstruction road,float feather)
    {
        CheckTerrain(terrain);if(feather<0||feather>20)throw new ArgumentException("Invalid grading feather");var samples=RoadSamples(road);
        float left=road.width/2+road.shoulderLeft+road.sidewalk,right=road.width/2+road.shoulderRight+road.sidewalk,extent=Math.Max(left,right)+feather;
        float minX=float.MaxValue,maxX=float.MinValue,minZ=float.MaxValue,maxZ=float.MinValue;
        foreach(var point in samples){minX=Math.Min(minX,point.x);maxX=Math.Max(maxX,point.x);minZ=Math.Min(minZ,point.z);maxZ=Math.Max(maxZ,point.z);}
        float bank=(float)Math.Tan(road.banking*Math.PI/180);int n=terrain.resolution;
        for(int z=0;z<n;z++)for(int x=0;x<n;x++) {
            float px=(x/(float)(n-1)-0.5f)*terrain.size.x,pz=(z/(float)(n-1)-0.5f)*terrain.size.z;
            if(px<minX-extent||px>maxX+extent||pz<minZ-extent||pz>maxZ+extent)continue;
            float closest=float.MaxValue,target=0,signed=0;
            for(int i=0;i<samples.Count-1;i++){var a=samples[i];var d=samples[i+1]-a;float squared=d.x*d.x+d.z*d.z;if(squared<0.000001f)continue;float t=Math.Max(0,Math.Min(1,((px-a.x)*d.x+(pz-a.z)*d.z)/squared));float dx=px-a.x-d.x*t,dz=pz-a.z-d.z*t,dist=(float)Math.Sqrt(dx*dx+dz*dz);
                if(dist<closest){closest=dist;signed=(dx*d.z-dz*d.x)/(float)Math.Sqrt(squared);target=a.y+d.y*t+road.elevationOffset+signed*bank;}}
            float boundary=signed<0?left:right;if(closest>boundary+feather)continue;
            float weight=closest<=boundary?1:feather>0?1-(closest-boundary)/feather:0;int at=z*n+x;terrain.heights[at]+=(target-terrain.heights[at])*weight;
        }
    }
    static void Wall(WorldConstruction p,Builder b)
    {
        if(p.points==null||p.points.Length!=2||p.size.y<=0||p.width<=0)throw new ArgumentException("Invalid wall source.");
        var start=p.points[0];var dir=(p.points[1]-start);dir.y=0;float length=dir.Length;
        if(length<0.1f)throw new ArgumentException("Wall must be at least 0.1 m long.");dir=dir.Unit;
        var xs=new SortedSet<float>{0,length};var ys=new SortedSet<float>{0,p.size.y};
        foreach(var hole in p.openings??new WorldOpening[0]) {
            if(hole.width<=0||hole.height<=0||hole.center-hole.width/2<0||hole.center+hole.width/2>length||hole.bottom<0||hole.bottom+hole.height>p.size.y)
                throw new ArgumentException("Opening must fit inside wall.");
            xs.Add(hole.center-hole.width/2);xs.Add(hole.center+hole.width/2);ys.Add(hole.bottom);ys.Add(hole.bottom+hole.height);
        }
        var xx=new List<float>(xs);var yy=new List<float>(ys);
        for(int x=0;x<xx.Count-1;x++)for(int y=0;y<yy.Count-1;y++){
            float midx=(xx[x]+xx[x+1])/2,midy=(yy[y]+yy[y+1])/2;bool opening=false;
            foreach(var h in p.openings??new WorldOpening[0])if(midx>h.center-h.width/2&&midx<h.center+h.width/2&&midy>h.bottom&&midy<h.bottom+h.height)opening=true;
            if(!opening)OrientedBox(b,start+dir*midx+new WorldPoint(0,midy,0),new WorldPoint(xx[x+1]-xx[x],yy[y+1]-yy[y],p.width),dir,0);
        }
    }
    static void Frame(WorldConstruction p,Builder b)
    {
        if(p.points==null||p.points.Length!=2)throw new ArgumentException("Opening frame needs direction.");
        var direction=(p.points[1]-p.points[0]).Unit;float w=p.size.x,h=p.size.y,t=0.08f;
        OrientedBox(b,new WorldPoint(0,h/2,0)+direction*(-w/2),new WorldPoint(t,h,p.size.z),direction,0);
        OrientedBox(b,new WorldPoint(0,h/2,0)+direction*(w/2),new WorldPoint(t,h,p.size.z),direction,0);
        OrientedBox(b,new WorldPoint(0,h,0),new WorldPoint(w,t,p.size.z),direction,0);
        if(p.kind=="window") {
            OrientedBox(b,new WorldPoint(0,0,0),new WorldPoint(w,t,p.size.z),direction,0);
            OrientedBox(b,new WorldPoint(0,h/2,0),new WorldPoint(w-t,h-t,0.025f),direction,1);
        }
    }
    static void Roof(WorldConstruction p,Builder b)
    {
        float x=p.size.x/2,z=p.size.z/2,h=p.size.y;
        if(x<=0||z<=0||h<=0)throw new ArgumentException("Invalid roof dimensions.");
        b.Quad(new WorldPoint(-x,0,-z),new WorldPoint(-x,0,z),new WorldPoint(0,h,z),new WorldPoint(0,h,-z),0);
        b.Quad(new WorldPoint(0,h,-z),new WorldPoint(0,h,z),new WorldPoint(x,0,z),new WorldPoint(x,0,-z),0);
        b.Face(new WorldPoint(-x,0,-z),new WorldPoint(0,h,-z),new WorldPoint(x,0,-z),1);
        b.Face(new WorldPoint(x,0,z),new WorldPoint(0,h,z),new WorldPoint(-x,0,z),1);
    }
    static void Tree(WorldConstruction p,Builder b)
    {
        float height=p.size.y;
        for(int i=0;i<10;i++)OrientedBox(b,new WorldPoint((float)Math.Sin(i*0.12f)*0.25f,height*(i+0.5f)/10,0),new WorldPoint(0.26f,height/10,0.26f),new WorldPoint(1,0,0),0);
        for(int i=0;i<10;i++) {
            float angle=i*Pi/5;var direction=new WorldPoint((float)Math.Cos(angle),0,(float)Math.Sin(angle));var side=new WorldPoint(-direction.z,0,direction.x);
            WorldPoint a=new WorldPoint(0,height,0),c=a+direction*2+new WorldPoint(0,0.15f,0),d=a+direction*3.6f+new WorldPoint(0,-0.8f,0);
            b.Quad(a,c+side*0.35f,d,c-side*0.35f,1);b.Quad(a,c-side*0.35f,d,c+side*0.35f,1);
        }
    }
    static void Box(Builder b,WorldPoint center,WorldPoint size,int group)=>OrientedBox(b,center,size,new WorldPoint(1,0,0),group);
    static void OrientedBox(Builder b,WorldPoint center,WorldPoint size,WorldPoint direction,int group)
    {
        WorldPoint x=direction.Unit*(size.x/2),y=new WorldPoint(0,size.y/2,0),z=new WorldPoint(-direction.z,0,direction.x).Unit*(size.z/2);
        WorldPoint a=center-x-y-z,c=center+x-y-z,d=center+x-y+z,e=center-x-y+z;
        WorldPoint f=a+y*2,g=c+y*2,h=d+y*2,j=e+y*2;
        b.Quad(a,c,d,e,group);b.Quad(f,j,h,g,group);b.Quad(a,f,g,c,group);b.Quad(c,g,h,d,group);b.Quad(d,h,j,e,group);b.Quad(e,j,f,a,group);
    }
    sealed class Builder
    {
        readonly List<WorldPoint> vertices=new List<WorldPoint>();readonly List<float> uv=new List<float>();readonly List<float> offsets=new List<float>();readonly List<int>[] groups;
        public Builder(int count){groups=new List<int>[count];for(int i=0;i<count;i++)groups[i]=new List<int>();}
        public int Vertex(WorldPoint p,float u=0,float v=0){int at=vertices.Count;vertices.Add(p);uv.Add(u);uv.Add(v);offsets.Add(float.NaN);return at;}
        public void Triangle(int a,int b,int c,int group){groups[group].Add(a);groups[group].Add(b);groups[group].Add(c);}
        public void Face(WorldPoint a,WorldPoint b,WorldPoint c,int group,float clearance=float.NaN){int at=Vertex(a,0,0);Vertex(b,0,1);Vertex(c,1,0);if(!float.IsNaN(clearance))for(int i=0;i<3;i++)offsets[at+i]=clearance;Triangle(at,at+1,at+2,group);}
        public void Quad(WorldPoint a,WorldPoint b,WorldPoint c,WorldPoint d,int group,float[] clearance=null){int at=Vertex(a,0,0);Vertex(b,0,1);Vertex(c,1,1);Vertex(d,1,0);if(clearance!=null)for(int i=0;i<4;i++)offsets[at+i]=clearance[i];Triangle(at,at+1,at+2,group);Triangle(at,at+2,at+3,group);}
        public WorldGeometryMesh Result(){var arrays=new int[groups.Length][];for(int i=0;i<groups.Length;i++)arrays[i]=groups[i].ToArray();return new WorldGeometryMesh{vertices=vertices.ToArray(),uv=uv.ToArray(),groups=arrays,roadClearance=offsets.ToArray()};}
    }
}
