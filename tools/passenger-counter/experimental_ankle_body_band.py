"""Frozen-trace hypothesis only: use the existing pose approach band for feet."""
from multi_anchor_counter import DualAnchorCounter

class ApproachBandAnkleCounter(DualAnchorCounter):
    def update(self,tid,person_box,foot,door,now,frame=None):
        gate=self.require_body_transition
        prior=self.body.tracks.get(tid)
        x1,y1,x2,y2=person_box
        u=(y1+self.anchor_y*(y2-y1)-door[1])/(door[3]-door[1])
        v=((x1+x2)/2-door[0])/(door[2]-door[0])
        left,right=self.body.transverse_low,self.body.transverse_high
        if prior and prior.outside_kind=='lateral' and self.body.lateral_inset is not None:
            left,right=max(left,self.body.lateral_inset),min(right,1-self.body.lateral_inset)
        # 1.2 is the already-used pose approach activation upper bound, not
        # tuned against an event window. Missing feet add no new evidence.
        relaxed=(gate and self.defer_ankle and foot is not None and prior and prior.side=='high'
                 and 0<=u<=1.2 and left<=v<=right)
        if relaxed:self.require_body_transition=False
        try:return super().update(tid,person_box,foot,door,now,frame)
        finally:self.require_body_transition=gate
