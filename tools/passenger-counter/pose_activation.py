"""Activate expensive auxiliary inference from current automatic-door observations."""
import math

def pose_due(door,boxes,settings):
    if settings is None:return True
    low=settings.get('low',.9);high=settings.get('high',1.2);margin=settings.get('margin',.1)
    if not all(math.isfinite(x) for x in (low,high,margin)) or not 0<=low<high<=2 or not 0<=margin<=1:
        raise ValueError('Invalid pose activation band')
    if door is None:return False
    x1,y1,x2,y2=door
    if x2<=x1 or y2<=y1:return False
    for box in boxes:
        if len(box)!=4 or not all(math.isfinite(x) for x in box):continue
        u=(box[3]-y1)/(y2-y1);v=((box[0]+box[2])/2-x1)/(x2-x1)
        if low<=u<=high and -margin<=v<=1+margin:return True
    return False
