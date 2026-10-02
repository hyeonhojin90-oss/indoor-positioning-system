"""Bounded image search around actual bus detections, without manual person ROI."""
import math


def search_regions(boxes,width,height,padding=.2,max_regions=1):
    if type(max_regions) is not int or not 1<=max_regions<=2 or not 0<=padding<=.5:
        raise ValueError('Invalid bounded bus crop policy')
    if width<=0 or height<=0:
        raise ValueError('Invalid image size')
    regions=[]
    for box in boxes:
        if len(box)!=4 or not all(math.isfinite(x) for x in box):
            raise ValueError('Invalid observed bus box')
        x1,y1,x2,y2=box
        if not 0<=x1<x2<=width or not 0<=y1<y2<=height:
            raise ValueError('Observed bus outside frame')
        bw,bh=x2-x1,y2-y1
        region=(max(0,math.floor(x1-padding*bw)),max(0,math.floor(y1-padding*bh)),
                min(width,math.ceil(x2+padding*bw)),min(height,math.ceil(y2+padding*bh)))
        if min(region[2]-region[0],region[3]-region[1])<32:
            continue
        # Full-image crops add cost without additional magnification.
        area=(region[2]-region[0])*(region[3]-region[1])
        if area/(width*height)>=.9:
            continue
        regions.append(region)
    return sorted(set(regions),key=lambda r:(r[2]-r[0])*(r[3]-r[1]),reverse=True)[:max_regions]


def restore_observation(box,region,width,height,edge_margin=2):
    """Reject clipped crops; never extend an observed person beyond actual ROI."""
    x1,y1,x2,y2=box;rx1,ry1,rx2,ry2=region
    if not all(math.isfinite(x) for x in box) or min(x2-x1,y2-y1)<=0:
        return None
    cw,ch=rx2-rx1,ry2-ry1
    if not 0<=x1<x2<=cw or not 0<=y1<y2<=ch:
        return None
    # A crop boundary hides body extent. Image boundaries do not establish full
    # extent either, so this conservative diagnostic rejects both cases.
    if x1<=edge_margin or y1<=edge_margin or cw-x2<=edge_margin or ch-y2<=edge_margin:
        return None
    restored=[x1+rx1,y1+ry1,x2+rx1,y2+ry1]
    return restored if 0<=restored[0]<restored[2]<=width and 0<=restored[1]<restored[3]<=height else None
