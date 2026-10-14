"""Portable error-guided terrain sampling and brush feature bounds."""
import math

def overlaps(a,b):return a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3]
def feature_bounds(field,cell=1.,tile=8):
    groups={}
    for (x,y),height in field.items():
        if abs(height)<1e-7:continue
        key=(math.floor(x/tile),math.floor(y/tile));box=(x*cell-cell,y*cell-cell,x*cell+cell,y*cell+cell)
        old=groups.get(key);groups[key]=box if old is None else (min(old[0],box[0]),min(old[1],box[1]),max(old[2],box[2]),max(old[3],box[3]))
    return list(groups.values())

def sample(bounds,height_at,features,spacing,tolerance=.02,brush=None,budget=150000):
    """Flat far leaves emit no samples; graded/sculpted leaves retain needed detail."""
    result=set();cache={};visited=0
    def height(x,y):
        key=(x,y)
        if key not in cache:cache[key]=height_at(x,y)
        return cache[key]
    def visit(box,depth):
        nonlocal visited
        visited+=1
        if visited>budget*4:raise ValueError('Adaptive terrain sampling budget exceeded')
        active=[f for f in features if overlaps(box,f)]
        if not active:return
        x0,y0,x1,y1=box;xm=(x0+x1)/2;ym=(y0+y1)/2
        corners=[height(x0,y0),height(x1,y0),height(x1,y1),height(x0,y1)]
        tests=[(xm,ym,sum(corners)/4),(xm,y0,(corners[0]+corners[1])/2),(x1,ym,(corners[1]+corners[2])/2),(xm,y1,(corners[2]+corners[3])/2),(x0,ym,(corners[3]+corners[0])/2)]
        error=max(abs(height(x,y)-expected) for x,y,expected in tests)
        width=max(x1-x0,y1-y0);local=spacing
        if brush and overlaps(box,brush[:4]):local=max(.25,min(spacing,brush[4]/6))
        force=width>local*2
        if width>local and (force or error>tolerance) and depth<24:
            for child in [(x0,y0,xm,ym),(xm,y0,x1,ym),(xm,ym,x1,y1),(x0,ym,xm,y1)]:visit(child,depth+1)
        elif error>tolerance*.15 or max(corners)-min(corners)>tolerance*.15 or (brush and overlaps(box,brush[:4])):
            for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(xm,ym)]:result.add((round(x,6),round(y,6)))
        if len(result)>budget:raise ValueError('Adaptive terrain exceeds sample budget')
    visit(bounds,0)
    return sorted(result)
