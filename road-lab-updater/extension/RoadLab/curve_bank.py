"""Portable native control-point tilt, blended through neighboring approaches."""
import math

def displacement(paths,tilts,width,x,y):
    numerator=denominator=0.
    for path,angles in zip(paths,tilts):
        for i,(a,b) in enumerate(zip(path,path[1:])):
            if x<min(a[0],b[0])-width*2 or x>max(a[0],b[0])+width*2 or y<min(a[1],b[1])-width*2 or y>max(a[1],b[1])+width*2:continue
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
            if not length:continue
            t=max(0.,min(1.,((x-a[0])*dx+(y-a[1])*dy)/length**2));qx,qy=a[0]+dx*t,a[1]+dy*t
            distance=math.hypot(x-qx,y-qy)
            if distance>width*2:continue
            angle=max(-.6,min(.6,angles[i]+(angles[i+1]-angles[i])*t));lateral=((x-qx)*-dy+(y-qy)*dx)/length
            weight=1/max(distance,.1)**4; numerator+=weight*math.tan(angle)*lateral;denominator+=weight
    return numerator/denominator if denominator else 0.
