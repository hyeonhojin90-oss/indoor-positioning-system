"""Optional initial door ranking by confidence and passenger support."""
import math
from counter import iou
from door_selection import passenger_support

def select_confident_door(candidates,people,confidences,locked_box=None,
                         min_support=.2,switch_margin=.5,max_distance=1):
    if len(confidences)!=len(candidates) or any(isinstance(c,bool) or not isinstance(c,(int,float)) or not math.isfinite(c) or not 0<=c<=1 for c in confidences):
        raise ValueError('One finite confidence in [0,1] is required per door candidate')
    if not candidates:return None
    support=[passenger_support(b,people,max_distance) for b in candidates]
    eligible=[i for i,s in enumerate(support) if s>=min_support]
    best=max(eligible,key=lambda i:support[i]*confidences[i]) if eligible else None
    if locked_box is not None:
        prior=max(range(len(candidates)),key=lambda i:iou(locked_box,candidates[i]))
        if iou(locked_box,candidates[prior])>=.75:
            # Confidence does not release a valid lock or relax its switch margin.
            if best is None or support[best]<=support[prior]+switch_margin:return prior
    return best
