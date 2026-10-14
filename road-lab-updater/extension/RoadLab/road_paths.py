"""Portable polyline projection and terrain-contact span definitions."""
import math

def closest(paths,point,only=None):
    best=None
    for si,path in enumerate(paths):
        if only is not None and si!=only:continue
        total=sum(math.dist(a[:2],b[:2]) for a,b in zip(path,path[1:]));along=0.
        for index,(a,b) in enumerate(zip(path,path[1:])):
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
            if not length:continue
            t=max(0.,min(1.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length**2))
            q=tuple(a[k]+(b[k]-a[k])*t for k in range(3));distance=math.dist(q[:2],point[:2])
            if best is None or distance<best['distance']:
                best={'spline':si,'segment':index,'t':t,'point':q,'tangent':(dx/length,dy/length),'along':along+t*length,'length':total,'distance':distance}
            along+=length
    return best

def contact_mask(paths,cuts,verts,faces):
    spans=[]
    for cut in cuts:
        a=closest(paths,cut['start'],cut['spline']);b=closest(paths,cut['end'],cut['spline'])
        if a and b:spans.append((cut['spline'],min(a['along'],b['along']),max(a['along'],b['along']),cut.get('wrap',False)))
    result=[]
    for face in faces:
        p=tuple(sum(verts[i][k] for i in face)/len(face) for k in range(3));q=closest(paths,p)
        bridge=bool(q and any(q['spline']==si and ((lo<=q['along']<=hi) if not wrap else (q['along']<=lo or q['along']>=hi)) for si,lo,hi,wrap in spans))
        result.append(not bridge)
    return result
