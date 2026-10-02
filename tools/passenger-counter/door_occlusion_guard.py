"""Experimental rejection of a partial box strictly within a still-valid door."""
def contained_shrink(reference, candidate, min_iou=.75, margin=.02):
    if reference is None or candidate is None:
        return False
    x1,y1,x2,y2=reference; a,b,c,d=candidate
    w,h=x2-x1,y2-y1;cw,ch=c-a,d-b
    if min(w,h,cw,ch)<=0:
        return False
    return (a>=x1-margin*w and c<=x2+margin*w and b>=y1-margin*h and d<=y2+margin*h
            and .5<=cw/w<=1 and .5<=ch/h<=1 and cw*ch/(w*h)<min_iou)
