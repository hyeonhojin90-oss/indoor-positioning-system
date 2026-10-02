"""Score automatic door candidates by nearby passenger feet, never manual ROI."""
import math
from counter import iou


def passenger_support(door, people, max_distance=1):
    x1,y1,x2,y2=door
    w,h=x2-x1,y2-y1
    if w<=0 or h<=0:
        return 0
    support=0
    for p in people:
        # Near the lower doorway; heads in windows must not vote for a door.
        x,y=(p[0]+p[2])/2,p[3]
        dx=max(x1-x,0,x-x2)/w
        dy=abs(y-y2)/h
        distance=math.hypot(dx,dy)
        if .55 <= (y-y1)/h <= 1.6 and distance <= max_distance:
            support+=1-distance/(max_distance+1e-9)
    return support


def select_door(candidates, people, locked_box=None, min_support=.2,
                switch_margin=.5, max_distance=1):
    if not candidates:
        return None
    scores=[passenger_support(b,people,max_distance) for b in candidates]
    best=max(range(len(scores)),key=lambda i:scores[i])
    if locked_box is not None:
        prior=max(range(len(scores)),key=lambda i:iou(locked_box,candidates[i]))
        if iou(locked_box,candidates[prior])>=.75:
            if scores[best]<=scores[prior]+switch_margin:
                return prior
    return best if scores[best]>=min_support else None


def passenger_search_regions(people,buses,width,height,max_regions=2):
    """Automatic crops from people near a detected bus; no fixed camera ROI."""
    regions=[]
    for p in people:
        pw,ph=p[2]-p[0],p[3]-p[1]
        if min(pw,ph)<=0 or ph<height*.08 or ph/pw<1.3:
            continue
        for bus in buses:
            bw,bh=bus[2]-bus[0],bus[3]-bus[1]
            cx=(p[0]+p[2])/2
            if min(bw,bh)<=0 or not (bus[0]-2*pw<=cx<=bus[2]+2*pw
                    and bus[1]+.35*bh<=p[3]<=bus[3]+.3*bh):
                continue
            r=(max(0,int(max(p[0]-2*pw,bus[0]-.05*bw))),
               max(0,int(max(p[1]-ph,bus[1]))),
               min(width,int(min(p[2]+2*pw,bus[2]+.05*bw))),
               min(height,int(p[3]+.2*ph)))
            if r[2]-r[0]<32 or r[3]-r[1]<32 or any(iou(r,b)>.3 for b in regions):
                continue
            regions.append(r)
            if len(regions)>=max_regions:return regions
    return regions


def locked_search_region(box,width,height):
    x1,y1,x2,y2=box;w,h=x2-x1,y2-y1
    r=(max(0,int(x1-w)),max(0,int(y1-.3*h)),
       min(width,int(x2+w)),min(height,int(y2+.3*h)))
    return [r] if r[2]-r[0]>=32 and r[3]-r[1]>=32 else []
