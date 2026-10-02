"""Optional class-aware observed-box suppression for RT-DETR experiments only."""
import math

def kept_indices(boxes,scores,classes,iou_threshold):
    if isinstance(iou_threshold,bool) or not isinstance(iou_threshold,(int,float)) or not math.isfinite(iou_threshold) or not 0<iou_threshold<1:
        raise ValueError('Require explicit finite IoU threshold between0 and1')
    if not len(boxes)==len(scores)==len(classes):raise ValueError('Mismatched detections')
    for b,s in zip(boxes,scores):
        if len(b)!=4 or not all(math.isfinite(v) for v in [*b,s]) or b[2]<=b[0] or b[3]<=b[1]:raise ValueError('Invalid observed detection')
    order=sorted(range(len(scores)),key=lambda i:(-scores[i],i));kept=[]
    for i in order:
        suppress=False
        for j in kept:
            if classes[i]!=classes[j]:continue
            a,b=boxes[i],boxes[j];intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
            union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection
            if intersection/union>iou_threshold:suppress=True;break
        if not suppress:kept.append(i)
    return kept

class RTDETRDuplicateFilter:
    def __init__(self,model,iou_threshold):
        kept_indices([],[],[],iou_threshold)
        if model.predictor is not None:raise ValueError('Attach before measured box capture and tracker initialization')
        self.iou=iou_threshold;self.frames=0;self.removed=0
        model.add_callback('on_predict_postprocess_end',self.filter)
    def filter(self,predictor):
        if len(predictor.results)!=1:raise ValueError('Require one observed frame')
        r=predictor.results[0]
        if r.boxes.is_track:raise ValueError('Duplicate filter ran after tracker')
        idx=kept_indices(r.boxes.xyxy.cpu().tolist(),r.boxes.conf.cpu().tolist(),r.boxes.cls.int().cpu().tolist(),self.iou)
        self.frames+=1;self.removed+=len(r.boxes)-len(idx)
        r.update(boxes=r.boxes.data[idx])
