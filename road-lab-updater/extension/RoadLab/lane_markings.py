"""Portable marking placement. Coordinates are road-local meters, not screen icons."""
import json
from pathlib import Path
from math import hypot, isfinite
from functools import lru_cache
from .lane_logic import Lane, road_width

ROOT=Path(__file__).parent/'assets'/'markings'
ARROWS={frozenset({'THROUGH'}):'arrow_through',frozenset({'LEFT'}):'arrow_left',frozenset({'RIGHT'}):'arrow_right',frozenset({'LEFT','THROUGH'}):'arrow_left_through',frozenset({'RIGHT','THROUGH'}):'arrow_right_through',frozenset({'LEFT','RIGHT'}):'arrow_left_right',frozenset({'LEFT','RIGHT','THROUGH'}):'arrow_all',frozenset({'UTURN'}):'arrow_uturn_left'}

@lru_cache(maxsize=1)
def manifest():return {a['id']:a for a in json.loads((ROOT/'manifest.json').read_text())['assets']}

def arrow_id(movements,side='RIGHT'):
    if side not in ('RIGHT','LEFT'):raise ValueError('Invalid map driving side')
    try:asset=ARROWS[frozenset(movements)]
    except KeyError:raise ValueError('No marking for this movement combination')
    return 'arrow_uturn_right' if asset=='arrow_uturn_left' and side=='LEFT' else asset

def plan(a,b,incoming,outgoing,width,side='RIGHT',median=0.,trim_start=0.,trim_end=0.,spacing=18.):
    """Incoming travels a -> b. Lane order is each driver's left -> right.

    End clearances are supplied by the topology adapter. Never draw through a
    junction or silently widen the road. Extra width remains shoulder allowance.
    """
    if side not in ('RIGHT','LEFT'):raise ValueError('Invalid map driving side')
    if not all(isfinite(x) and x>=0 for x in (width,median,trim_start,trim_end)) or not isfinite(spacing) or spacing<=0:raise ValueError('Invalid placement dimensions')
    _,minimum=road_width(incoming,outgoing,median)
    if minimum>width+1e-6:raise ValueError(f'Lanes require {minimum:.2f} m; road has {width:.2f} m')
    dx,dy=b[0]-a[0],b[1]-a[1];length=hypot(dx,dy)
    if length<1e-6:return []
    forward=(dx/length,dy/length);right=(forward[1],-forward[0]);sign=1 if side=='RIGHT' else -1
    ni=sum(l.width for l in incoming);no=sum(l.width for l in outgoing)
    # Center the full carriageway; median may be off the alignment for asymmetric counts.
    center=sign*(no-ni)/2
    start=trim_start;end=length-trim_end
    if end<=start:return []
    assets=manifest();result=[]
    def add(asset,station,lateral,direction=1,size=None):
        if size is None:size=assets[asset]['physical_canvas_m']
        result.append({'asset':asset,'center':[a[0]+forward[0]*station+right[0]*lateral,a[1]+forward[1]*station+right[1]*lateral,a[2]+(b[2]-a[2])*station/length], 'forward':[direction*forward[0],direction*forward[1]],'size':list(size)})
    for lanes,direction,total in ((incoming,1,ni),(outgoing,-1,no)):
        cursor=0
        for lane in lanes:
            distance=cursor+lane.width/2 if side=='RIGHT' else total-cursor-lane.width/2
            offset=center+sign*direction*(median/2+distance);cursor+=lane.width
            asset=arrow_id(lane.movements,side);w,h=assets[asset]['physical_canvas_m']
            anchor=assets[asset]['anchor_uv'][0]
            scale=min(1.,(lane.width/2-.15)/(w*max(anchor,1-anchor)))
            if scale<=0:continue
            w*=scale;h*=scale
            station=end-h/2-1 if direction==1 else start+h/2+1
            while station-h/2>=start and station+h/2<=end:
                anchor=assets[asset]['anchor_uv'][0]
                add(asset,station,offset+direction*(.5-anchor)*w,direction,(w,h));station-=direction*spacing
        cursor=0
        for lane in lanes[:-1]:
            cursor+=lane.width;distance=cursor if side=='RIGHT' else total-cursor
            offset=center+sign*direction*(median/2+distance)
            # Physical 10/30 ft tile; partial end tiles retain UV phase.
            period=assets['broken_white']['physical_canvas_m'][1];s=start
            while s<end:
                span=min(period,end-s);add('broken_white',s+span/2,offset,direction,(.1524,span));result[-1]['v_range']=[0,span/period];s+=period
        if lanes:
            add('line_white',(start+end)/2,center+sign*direction*(median/2+total),direction,(.1524,end-start))
    if bool(incoming)!=bool(outgoing):
        direction=1 if incoming else -1
        add('line_white',(start+end)/2,center+sign*direction*median/2,direction,(.1524,end-start))
    if incoming and outgoing:
        if median==0:add('double_yellow',(start+end)/2,center,size=(.4064,end-start))
        else:
            for direction in (-1,1):add('line_yellow',(start+end)/2,center+sign*direction*median/2,size=(.1524,end-start))
    return result


def patch_grid(marking,max_step=.4):
    """Subdivide each textured patch for bank/sculpt surface projection."""
    from math import ceil
    w,h=marking['size'];nx=max(1,ceil(w/max_step));ny=max(1,ceil(h/max_step))
    fx,fy=marking['forward'];rx,ry=fy,-fx;cx,cy,cz=marking['center'];v0,v1=marking.get('v_range',[0,1]);verts=[];uv=[]
    for j in range(ny+1):
        for i in range(nx+1):
            x=(i/nx-.5)*w;y=(j/ny-.5)*h
            verts.append((cx+rx*x+fx*y,cy+ry*x+fy*y,cz));uv.append((i/nx,v0+(v1-v0)*j/ny))
    faces=[]
    for j in range(ny):
        for i in range(nx):
            k=j*(nx+1)+i;faces.append((k,k+1,k+nx+2,k+nx+1))
    return verts,faces,uv
