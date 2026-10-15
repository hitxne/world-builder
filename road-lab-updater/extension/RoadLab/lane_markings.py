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

def plan(a,b,incoming,outgoing,width,side='RIGHT',median=0.,trim_start=0.,trim_end=0.,spacing=18.,solid_approach=20.,transition_length=30.,emerging_incoming=(),emerging_outgoing=(),control_incoming="NONE",control_outgoing="NONE",stop_setback=1.22,arrow_approach=35.,junction_start=None,junction_end=None,allowed_incoming=None,allowed_outgoing=None,crosswalk_incoming=False,crosswalk_outgoing=False,crosswalk_depth=3.048,crosswalk_gap=1.,crosswalk_tactile=False,crosswalk_a=0.,crosswalk_b=0.,crosswalk_ramp=1.9):
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
    if not all(isfinite(x) and x>=0 for x in (solid_approach,transition_length,stop_setback,arrow_approach)):raise ValueError('Invalid approach marking dimensions')
    if control_incoming not in ('NONE','STOP','SIGNAL','YIELD') or control_outgoing not in ('NONE','STOP','SIGNAL','YIELD'):raise ValueError('Invalid approach control')
    junction_start=trim_start>0 if junction_start is None else junction_start
    junction_end=trim_end>0 if junction_end is None else junction_end
    assets=manifest();result=[]
    def add(asset,station,lateral,direction=1,size=None,role=None):
        if size is None:size=assets[asset]['physical_canvas_m']
        result.append({'asset':asset,'center':[a[0]+forward[0]*station+right[0]*lateral,a[1]+forward[1]*station+right[1]*lateral,a[2]+(b[2]-a[2])*station/length], 'forward':[direction*forward[0],direction*forward[1]],'size':list(size),'role':role or [asset,direction]})
    def line_interval(asset,lo,hi,offset,direction,role):
        if hi-lo<1e-6:return
        if asset=='line_white':add(asset,(lo+hi)/2,offset,direction,(.1524,hi-lo),role=role+['solid']);return
        period=assets[asset]['physical_canvas_m'][1]
        # Anchor phase in travel direction, so short end tiles don't reverse the pattern.
        distance=0.;tile=0
        while distance<hi-lo-1e-6:
            span=min(period,hi-lo-distance)
            station=lo+distance+span/2 if direction==1 else hi-distance-span/2
            add(asset,station,offset,direction,(.1524,span),role=role+[asset,tile]);result[-1]['v_range']=[0,span/period];distance+=span;tile+=1
    for enabled,direction,junction in ((crosswalk_incoming,1,junction_end),(crosswalk_outgoing,-1,junction_start)):
        if not enabled:continue
        if crosswalk_depth<=0 or crosswalk_gap<0:raise ValueError('Invalid crosswalk dimensions')
        if end-start<=crosswalk_depth+crosswalk_gap+1:continue
        station=end-crosswalk_gap-crosswalk_depth/2 if direction==1 else start+crosswalk_gap+crosswalk_depth/2
        # Each sidewalk endpoint has its own setback, measured away from the junction.
        sa=station-direction*crosswalk_a;sb=station-direction*crosswalk_b
        ax=a[0]+forward[0]*sa-right[0]*width/2;ay=a[1]+forward[1]*sa-right[1]*width/2
        bx=a[0]+forward[0]*sb+right[0]*width/2;by=a[1]+forward[1]*sb+right[1]*width/2
        distance=hypot(bx-ax,by-ay);tx,ty=(bx-ax)/distance,(by-ay)/distance
        bar_forward=(ty,-tx);bar_width=.6096;period=1.2192
        inset=.15+crosswalk_depth/2*abs(crosswalk_a-crosswalk_b)/max(distance,1e-9)
        available=max(0.,distance-2*inset);count=int((available+period-bar_width)/period)
        if count<1:continue
        used=count*bar_width+(count-1)*(period-bar_width)
        for index in range(count):
            t=((distance-used)/2+bar_width/2+index*period)/distance;z=a[2]+(b[2]-a[2])*(sa+(sb-sa)*t)/length
            add('line_white',station,0,size=(bar_width,crosswalk_depth),role=['crosswalk',direction,index])
            result[-1]['center']=[ax+(bx-ax)*t,ay+(by-ay)*t,z];result[-1]['forward']=list(bar_forward)
            result[-1]['ramp_run']=crosswalk_ramp
            result[-1]['crosswalk_ends']=[[ax,ay,a[2]+(b[2]-a[2])*sa/length],[bx,by,a[2]+(b[2]-a[2])*sb/length]]
        if crosswalk_tactile:
            for side_sign,(x,y,s) in ((-1,(ax,ay,sa)),(1,(bx,by,sb))):
                add('tactile_pad',station,0,size=(crosswalk_depth,.61),role=['tactile',direction,side_sign])
                result[-1]['center']=[x+side_sign*tx*(.08+.61/2),y+side_sign*ty*(.08+.61/2),a[2]+(b[2]-a[2])*s/length]
                result[-1]['forward']=[side_sign*tx,side_sign*ty];result[-1]['on_terrain']=True
        reach=crosswalk_depth/2*abs(bar_forward[0]*forward[0]+bar_forward[1]*forward[1])
        if direction==1:end=min(sa,sb)-reach
        else:start=max(sa,sb)+reach
    for lanes,direction,total,emerging,control,junction in ((incoming,1,ni,set(emerging_incoming),control_incoming,junction_end),(outgoing,-1,no,set(emerging_outgoing),control_outgoing,junction_start)):
        bar=None
        lo,hi=start,end
        if lanes and junction and control in ('STOP','SIGNAL'):
            depth=.6096
            bar=end-stop_setback-depth/2 if direction==1 else start+stop_setback+depth/2
            if bar-depth/2>=start and bar+depth/2<=end:
                add('stop_bar',bar,center+sign*direction*(median/2+total/2),direction,(total,depth),role=['stop',direction])
                if direction==1:hi=bar-depth/2
                else:lo=bar+depth/2
            else:bar=None
        # Directional arrows belong only to an actual junction approach.
        # On short streets connecting two junctions, reserve the other half
        # for departing traffic rather than repeating arrows after the crossing.
        arrow_lo,arrow_hi=lo,hi
        if direction==1:arrow_lo=max(lo,hi-arrow_approach,(start+end)/2 if junction_start else lo)
        else:arrow_hi=min(hi,lo+arrow_approach,(start+end)/2 if junction_end else hi)
        cursor=0
        for lane_index,lane in enumerate(lanes if junction and arrow_approach>0 else []):
            distance=cursor+lane.width/2 if side=='RIGHT' else total-cursor-lane.width/2
            offset=center+sign*direction*(median/2+distance);cursor+=lane.width
            allowed=allowed_incoming if direction==1 else allowed_outgoing
            if allowed is not None and not lane.movements.issubset(allowed):continue
            asset=arrow_id(lane.movements,side);w,h=assets[asset]['physical_canvas_m']
            anchor=assets[asset]['anchor_uv'][0]
            scale=min(1.,(lane.width/2-.15)/(w*max(anchor,1-anchor)))
            if scale<=0:continue
            w*=scale;h*=scale
            station=arrow_hi-h/2-1 if direction==1 else arrow_lo+h/2+1
            repeat=0
            while station-h/2>=arrow_lo and station+h/2<=arrow_hi:
                anchor=assets[asset]['anchor_uv'][0]
                add(asset,station,offset+direction*(.5-anchor)*w,direction,(w,h),role=['arrow',direction,lane_index,repeat]);station-=direction*spacing;repeat+=1
        cursor=0
        for index,lane in enumerate(lanes[:-1]):
            cursor+=lane.width;distance=cursor if side=='RIGHT' else total-cursor
            offset=center+sign*direction*(median/2+distance)
            travel_length=max(0.,hi-lo)
            solid=min(solid_approach,travel_length) if junction else 0.
            dotted=min(transition_length,travel_length-solid) if index in emerging or index+1 in emerging else 0.
            spans=[('dotted_white',0.,dotted),('broken_white',dotted,travel_length-solid),('line_white',travel_length-solid,travel_length)]
            for asset,u,v in spans:
                if direction==1:line_interval(asset,lo+u,lo+v,offset,direction,['divider',direction,index])
                else:line_interval(asset,hi-v,hi-u,offset,direction,['divider',direction,index])
        if lanes:
            add('line_white',(start+end)/2,center+sign*direction*(median/2+total),direction,(.1524,end-start),role=['outer',direction])
    if bool(incoming)!=bool(outgoing):
        direction=1 if incoming else -1
        add('line_white',(start+end)/2,center+sign*direction*median/2,direction,(.1524,end-start),role=['center-white',direction])
    if incoming and outgoing:
        if median==0:add('double_yellow',(start+end)/2,center,size=(.4064,end-start),role=['center-yellow'])
        else:
            for direction in (-1,1):add('line_yellow',(start+end)/2,center+sign*direction*median/2,size=(.1524,end-start),role=['median-yellow',direction])
    return result


def patch_grid(marking,max_step=.4):
    """Subdivide each textured patch for bank/sculpt surface projection."""
    from math import ceil
    if marking.get('path'):
        from mathutils import Vector
        path=[Vector(p) for p in marking['path']];verts=[];uv=[];distance=0.;length=marking['size'][1];width=marking['size'][0]
        period=manifest()[marking['asset']]['physical_canvas_m'][1]
        repeat=marking['asset'] in ('broken_white','dotted_white')
        for i,p in enumerate(path):
            if i:distance+=(p-path[i-1]).length
            before=(p-path[i-1]) if i else path[1]-p;after=(path[i+1]-p) if i<len(path)-1 else before
            before.z=after.z=0;before.normalize();after.normalize();tangent=(before+after).normalized();normal=Vector((tangent.y,-tangent.x,0))
            scale=1/max(.5,tangent.dot(before));v=distance/period if repeat else distance/max(length,1e-9)
            for u,sign in ((0,-1),(1,1)):verts.append(tuple(p+normal*(sign*width*.5*scale)));uv.append((u,v))
        return verts,[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(path)-1)],uv
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
